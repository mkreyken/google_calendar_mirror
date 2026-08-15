import atexit
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.util.filesystem import get_data_location, save_json_file, load_json_file


@dataclass(frozen=True)
class TokenStoreValue:
    token: str
    date_stamp: datetime
    name: str


class SyncTokenStore:
    """
    Stores the sync id for a particular calendar event in a simple,
    in-memory dict that is saved/loaded as a single JSON file.

    The file name is provided at creation, so you can have one
    file per calendar.

    Call save() or finish() when you're done to persist changes.
    Call reset() to clear everything and return to an empty state.

    the key "sync_id" the sync_id for this file
    """
    token_path: Path
    token_key_store: Dict[str, TokenStoreValue]

    def __init__(self, filename: str, is_empty=False):
        self.token_path = Path(get_data_location(filename))
        if not is_empty:
            self.token_key_store = self._load_values()
        else:
            self.token_key_store = {}

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
