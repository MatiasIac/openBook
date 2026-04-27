from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

DEFAULT_BOOK_FILENAME = "book.txt"
DEFAULT_STATE_FILENAME = "state.json"
DEFAULT_STATE = {"current_page": 0, "book_file": DEFAULT_BOOK_FILENAME}


@dataclass
class Storage:
    data_dir: Path
    book_filename: str = DEFAULT_BOOK_FILENAME
    state_filename: str = DEFAULT_STATE_FILENAME

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.book_path.exists():
            self.book_path.write_text(
                "Upload a .txt file from the web page to start reading.\n",
                encoding="utf-8",
            )
        if not self.state_path.exists():
            self.save_state(0, self.book_filename)

    @property
    def book_path(self) -> Path:
        return self.data_dir / self.book_filename

    @property
    def state_path(self) -> Path:
        return self.data_dir / self.state_filename

    def load_state(self) -> Dict[str, Any]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return DEFAULT_STATE.copy()

        if not isinstance(raw, dict):
            return DEFAULT_STATE.copy()

        current_page = raw.get("current_page", 0)
        try:
            current_page = int(current_page)
        except (TypeError, ValueError):
            current_page = 0

        current_page = max(current_page, 0)
        book_file = raw.get("book_file") or self.book_filename

        return {
            "current_page": current_page,
            "book_file": str(book_file),
        }

    def save_state(self, current_page: int, book_file: str | None = None) -> None:
        state = {
            "current_page": max(int(current_page), 0),
            "book_file": book_file or self.book_filename,
        }
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def write_book_bytes(self, payload: bytes) -> None:
        self.book_path.write_bytes(payload)

    def read_book_text(self) -> str:
        try:
            return self.book_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self.book_path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""
