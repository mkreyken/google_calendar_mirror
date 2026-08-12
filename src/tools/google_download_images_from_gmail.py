import base64
import hashlib
import json
from pathlib import Path
from typing import Any, cast

# noinspection PyPackageRequirements
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from src.util.filesystem import get_credentials_filename, get_tokens_filename

# Resource is not exposed
GoogleCalendarClientType = Any

import logging

logger = logging.getLogger(__name__)


# noinspection PyMethodMayBeStatic
class ImageAgent:
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify"
    ]

    PROCESSED_FILE = "processed_emails.json"
    HASH_FILE = "image_hashes.json"

    SUCCESS_LABEL = "Photos-Downloaded"
    FAIL_LABEL = "Photos-Failed"

    MIN_BYTES = 40 * 1024  # Skip images smaller than 40 KB

    credentials_file: str
    token_path: str
    service: GoogleCalendarClientType

    def __init__(self,
                 credentials_file: str = get_credentials_filename(),
                 token_path: str = get_tokens_filename()):  # type: ignore[no-untyped-def]
        self.credentials_file = credentials_file
        self.token_path = token_path
        self.service = self.get_gmail_service()

    def load_json_set(self, path: str) -> set[Any]:
        if not Path(path).exists():
            return set()
        with open(path, "r") as f:
            return set(json.load(f))

    def save_json_set(self, path: str, data_set: set[Any]) -> None:
        with open(path, "w") as f:
            json.dump(sorted(list(data_set)), f, indent=2)

    def _build_flow(self) -> InstalledAppFlow:
        return cast(
            InstalledAppFlow,
            InstalledAppFlow.from_client_secrets_file(
                self.credentials_file,
                self.SCOPES,
            ))

    # noinspection PyMethodMayBeStatic
    def get_gmail_service(self) -> GoogleCalendarClientType:
        creds = None
        token_path = Path("token.json")

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), self.SCOPES)

        if not creds or not creds.valid:
            flow = self._build_flow()
            creds = flow.run_local_server(port=0)

            with open(token_path, "w") as f:
                f.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    def get_or_create_label(self, label_name: str) -> str:
        labels = self.service.users().labels().list(userId="me").execute().get("labels", [])
        for label in labels:
            if label["name"] == label_name:
                return label["id"]

        label_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show"
        }

        created = self.service.users().labels().create(
            userId="me", body=label_body
        ).execute()

        return created["id"]

    def apply_label(self, msg_id, label_id) -> None:
        self.service.users().messages().modify(
            userId="me",
            id=msg_id,
            body={"addLabelIds": [label_id]}
        ).execute()

    # noinspection PyMethodMayBeStatic
    def sha256_bytes(self, data) -> str:
        return hashlib.sha256(data).hexdigest()

    def download_photos_from_inbox(self, output_folder="downloaded_photos") -> None:
        Path(output_folder).mkdir(exist_ok=True)

        processed_ids = self.load_json_set(self.PROCESSED_FILE)
        image_hashes = self.load_json_set(self.HASH_FILE)

        logger.info(f"Loaded {len(processed_ids)} processed emails")
        logger.info(f"Loaded {len(image_hashes)} known image hashes")

        success_label_id = self.get_or_create_label(self.SUCCESS_LABEL)
        fail_label_id = self.get_or_create_label(self.FAIL_LABEL)

        query = "in:inbox has:attachment filename:(jpg OR jpeg OR png)"
        results = self.service.users().messages().list(userId="me", q=query).execute()
        messages = results.get("messages", [])

        logger.info(f"Found {len(messages)} total emails with photo attachments")

        for msg in messages:
            msg_id = msg["id"]

            if msg_id in processed_ids:
                continue

            logger.info(f"Processing email {msg_id}")

            try:
                message = self.service.users().messages().get(userId="me", id=msg_id).execute()
                parts = message.get("payload", {}).get("parts", [])

                downloaded_any = False

                for part in parts:
                    filename = part.get("filename", "")
                    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                        continue

                    attachment_id = part["body"].get("attachmentId")
                    if not attachment_id:
                        continue

                    attachment = (
                        self.service.users()
                        .messages()
                        .attachments()
                        .get(userId="me", messageId=msg_id, id=attachment_id)
                        .execute()
                    )

                    data = base64.urlsafe_b64decode(attachment["data"])

                    # Skip tiny images (logos, icons)
                    if len(data) < self.MIN_BYTES:
                        logger.info(f"Skipping tiny image {filename} ({len(data)} bytes)")
                        continue

                    # Hash dedupe
                    file_hash = self.sha256_bytes(data)
                    if file_hash in image_hashes:
                        logger.info(f"Skipping duplicate image {filename}")
                        continue

                    # Save image
                    filepath = Path(output_folder) / filename
                    with open(filepath, "wb") as f:
                        f.write(data)

                    logger.info(f"Saved: {filepath}")

                    image_hashes.add(file_hash)
                    self.save_json_set(self.HASH_FILE, image_hashes)

                    downloaded_any = True

                # Label success or failure
                if downloaded_any:
                    self.apply_label(msg_id, success_label_id)
                    logger.info(f"Labeled email {msg_id} as {self.SUCCESS_LABEL}")
                else:
                    self.apply_label(msg_id, fail_label_id)
                    logger.info(f"Labeled email {msg_id} as {self.FAIL_LABEL}")

            except Exception as e:
                logger.info(f"Error processing {msg_id}: {e}")
                self.apply_label(msg_id, fail_label_id)

            processed_ids.add(msg_id)
            self.save_json_set(self.PROCESSED_FILE, processed_ids)

        logger.info("Done. All new photos processed.")
