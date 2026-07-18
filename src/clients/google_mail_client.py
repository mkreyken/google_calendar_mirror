import base64
import os
from email.message import EmailMessage
from typing import Any, Optional, cast, Dict

# noinspection PyPackageRequirements
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow # type: ignore[import-untyped]
from googleapiclient.discovery import build # type: ignore[import-untyped]

from src.services.env import ALL_GOOGLE_AUTH_SCOPES
from src.util.exceptions import google_call
from src.util.filesystem import get_tokens_filename, get_credentials_filename

GoogleMailClientType = Any
GoogleClientJsonType = Dict[str, Any]


class GmailTextSender:
    """
    A deterministic, reproducible Gmail API client for sending reports.
    Handles OAuth, MIME construction, and Gmail API send calls.
    """

    def __init__(self,
                 credentials_file: str = get_credentials_filename(),
                 token_path: str = get_tokens_filename()):  # type: ignore[no-untyped-def]
        self.credentials_file = credentials_file
        self.token_path = token_path
        self.service = self._authorize()

    def _build_flow(self) -> InstalledAppFlow:
        return cast(
            InstalledAppFlow,
            InstalledAppFlow.from_client_secrets_file(
                self.credentials_file,
                ALL_GOOGLE_AUTH_SCOPES,
            ))

    def _authorize(self) -> GoogleMailClientType:
        """
        Perform OAuth desktop flow and return an authenticated Gmail API service.
        Deterministic: token.json is reused until invalid.
        """
        creds = None

        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, ALL_GOOGLE_AUTH_SCOPES)

        if not creds or not creds.valid:
            flow = self._build_flow()
            creds = flow.run_local_server(port=0)

            with open(self.token_path, "w") as f:
                f.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    # noinspection PyMethodMayBeStatic
    def _build_message(
            self,
            to_email: str,
            subject: str,
            body_text: str,
            attachment_path: Optional[str] = None
    ) -> GoogleClientJsonType:
        """
        Build a MIME email with optional attachment.
        Returns a Gmail API-ready base64 encoded message.
        """

        msg = EmailMessage()
        msg["To"] = to_email
        msg["From"] = "me"
        msg["Subject"] = subject
        msg.set_content(body_text)


        # Optional attachment
        if attachment_path:
            with open(attachment_path, "rb") as f:
                data = f.read()

                msg.add_attachment(
                    data,
                    maintype="application",
                    subtype="octet-stream",
                    filename=os.path.basename(attachment_path)
                )

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        return {"raw": raw}

    def send_text(
            self,
            to: str,
            subject: str,
            body: str,
            attachment_path: Optional[str] = None
    ) -> Any:
        """
        Public method: send a report email.
        Returns Gmail API response dict.
        """

        message = self._build_message(
            to_email=to,
            subject=subject,
            body_text=body,
            attachment_path=attachment_path,
        )

        return google_call(
            self.service.users().messages().send,
            userId="me",
            body=message
        )
