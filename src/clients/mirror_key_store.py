import atexit
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.services.env import CALENDAR_TOKEN_FILENAME
from src.util.filesystem import save_json_file, load_json_file, get_data_location_as_path


@dataclass(frozen=True)
class TokenStoreValue:
    token: str
    date_stamp: datetime
    name: str


class SyncTokenStore:
    token_path: Path
    token_key_store: Dict[str, TokenStoreValue]
    _instance = None

    def __new__(cls) -> SyncTokenStore:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):  # type: ignore[no-untyped-def]
        # Only run initialization once
        if not hasattr(self, "token_key_store"):
            self.token_path = get_data_location_as_path(CALENDAR_TOKEN_FILENAME)
            self.token_key_store = self._load_values()
            # Register save-on-exit
            atexit.register(self._save)

    def _load_values(self) -> Dict[str, TokenStoreValue]:
        raw = load_json_file(self.token_path)

        def convert(value: dict) -> dict:
            out = dict(value)

            # Convert ONLY the named field
            if "date_stamp" in out and isinstance(out["date_stamp"], str):
                v = out["date_stamp"]

                # Try ISO‑8601 first
                try:
                    out["date_stamp"] = datetime.fromisoformat(v)
                except ValueError:
                    # Try YYYYMMDD fallback
                    try:
                        out["date_stamp"] = datetime.strptime(v, "%Y%m%d")
                    except ValueError:
                        pass  # leave as string if neither format matches

            return out

        return {
            key: TokenStoreValue(**convert(value))
            for key, value in raw.items()
        }

    def _save(self) -> None:
        data = {}

        for key, item in self.token_key_store.items():
            d = asdict(item)

            # Convert datetime fields to ISO strings
            for k, v in d.items():
                if isinstance(v, datetime):
                    d[k] = v.isoformat()

            data[key] = d

        save_json_file(self.token_path, data)

    def reset(self) -> None:
        """Reset the store to an empty state and save it."""
        self.token_key_store = {}
        save_json_file(self.token_path, self.token_key_store)

    def save(self) -> None:
        self._save()

    def finish(self) -> None:
        """Alias for save() – call when you’re done making changes."""
        self.save()

    def clear(self, key: str) -> None:
        self.token_key_store.pop(key, None)

    def get(self, key: str) -> TokenStoreValue | None:
        return self.token_key_store.get(key, None)

    def set(self, key: str, value: TokenStoreValue) -> None:
        if value is None:
            raise ValueError("Value is null")
        self.token_key_store[key] = value

    def delete(self, key: str) -> None:
        self.token_key_store.pop(key, None)

    def items(self) -> Dict[str, TokenStoreValue]:
        return self.token_key_store

    def __contains__(self, key) -> bool:
        return key in self.token_key_store

    def __len__(self) -> int:
        return len(self.token_key_store)

    def summarize(self) -> List[str]:
        lines = []

        for key, item in self.token_key_store.items():
            raw = item.date_stamp

            # Normalize date_stamp into a datetime
            if isinstance(raw, int):
                date_val = datetime.strptime(str(raw), "%Y%m%d")
            elif isinstance(raw, str):
                try:
                    date_val = datetime.fromisoformat(raw)
                except ValueError:
                    date_val = datetime.strptime(raw, "%Y%m%d")
            elif isinstance(raw, datetime):
                date_val = raw
            else:
                continue  # skip invalid

            # Build summary line
            venue = item.name
            date_str = date_val.strftime("%Y-%m-%d")
            hour_str = date_val.strftime("%H:%M")

            lines.append(f"{venue}: {date_str} at {hour_str}")

        return lines
