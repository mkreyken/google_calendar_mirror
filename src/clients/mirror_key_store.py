import atexit
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict

from src.util.filesystem import get_data_location, save_json_file, load_json_file


@dataclass(frozen=True)
class TokenStoreValue:
    token: str
    date_stamp: int  # in the form "YYYYMMDD"
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

    def __init__(self, filename: str, is_empty=False):
        self.path = Path(get_data_location(filename))
        self.token_key_store: Dict[str, TokenStoreValue]
        if not is_empty:
            raw = load_json_file(self.path)
            self.token_key_store = {
                key: TokenStoreValue(**value)
                for key, value in raw.items()
            }
        else:
            self.token_key_store = {}

        # Register save-on-exit
        atexit.register(self._save)

    def _save(self) -> None:
        data = {
            key: asdict(item)
            for key, item in self.token_key_store.items()
        }
        save_json_file(self.path, data)

    def reset(self) -> None:
        """Reset the store to an empty state and save it."""
        self.token_key_store = {}
        save_json_file(self.path, self.token_key_store)

    def save(self) -> None:
        """Persist the current in-memory state to disk."""
        save_json_file(self.path, self.token_key_store)

    def finish(self) -> None:
        """Alias for save() – call when you’re done making changes."""
        self.save()

    def clear(self, key: str) -> None:
        self.token_key_store.pop(key, None)

    def get(self, key:str) -> TokenStoreValue|None:
        return self.token_key_store.get(key, None)

    def set(self, key:str, value: TokenStoreValue) -> None:
        if value is None:
            raise ValueError("Value is null")
        self.token_key_store[key] = value

    def delete(self, key:str) -> None:
        self.token_key_store.pop(key, None)

    def keys(self) -> Any:
        return self.token_key_store.keys()

    def __contains__(self, key) -> bool:
        return key in self.token_key_store

    def __len__(self) -> int:
        return len(self.token_key_store)
