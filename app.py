from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, List

from reader.buttons import ButtonController
from reader.display import EPaperDisplay
from reader.pagination import paginate_text
from reader.storage import Storage
from reader.web import create_web_app

LOGGER = logging.getLogger(__name__)


class ReaderController:
    def __init__(self, storage: Storage, display: EPaperDisplay) -> None:
        self.storage = storage
        self.display = display
        self._lock = threading.Lock()
        self._pages: List[List[str]] = [[""]]
        state = self.storage.load_state()
        self._current_page = int(state.get("current_page", 0))
        self._load_book_and_render(reset_to_start=False)

    def _load_book_pages(self) -> None:
        started_at = time.monotonic()
        text = self.storage.read_book_text()
        LOGGER.info("Paginating book (%s characters)...", format(len(text), ","))
        self._pages = paginate_text(
            text=text,
            font=self.display.body_font,
            max_width=self.display.body_width,
            max_height=self.display.body_height,
            line_spacing=self.display.line_spacing,
        )
        if not self._pages:
            self._pages = [[""]]
        elapsed = time.monotonic() - started_at
        LOGGER.info(
            "Pagination complete: %s pages generated in %.2fs.",
            format(len(self._pages), ","),
            elapsed,
        )

    def _clamp_current_page(self) -> None:
        max_index = len(self._pages) - 1
        self._current_page = min(max(self._current_page, 0), max_index)

    def _persist_state(self) -> None:
        self.storage.save_state(
            current_page=self._current_page,
            book_file=self.storage.book_filename,
        )

    def _render_current_page(self) -> None:
        LOGGER.info(
            "Rendering page %s/%s.",
            self._current_page + 1,
            len(self._pages),
        )
        self.display.render_page(
            lines=self._pages[self._current_page],
            page_index=self._current_page,
            total_pages=len(self._pages),
        )
        LOGGER.info("Render complete.")

    def _load_book_and_render(self, reset_to_start: bool) -> None:
        with self._lock:
            self._load_book_pages()
            if reset_to_start:
                self._current_page = 0
            self._clamp_current_page()
            self._persist_state()
            self._render_current_page()

    def next_page(self) -> None:
        with self._lock:
            if self._current_page >= len(self._pages) - 1:
                return
            self._current_page += 1
            self._persist_state()
            self._render_current_page()

    def previous_page(self) -> None:
        with self._lock:
            if self._current_page <= 0:
                return
            self._current_page -= 1
            self._persist_state()
            self._render_current_page()

    def replace_book(self, payload: bytes) -> None:
        with self._lock:
            LOGGER.info("Replacing book with uploaded file (%s bytes).", format(len(payload), ","))
            self.storage.write_book_bytes(payload)
            self._load_book_pages()
            self._current_page = 0
            self._persist_state()
            self._render_current_page()

    def get_status(self) -> Dict[str, int | str]:
        with self._lock:
            return {
                "current_page": self._current_page,
                "total_pages": len(self._pages),
                "book_file": self.storage.book_filename,
            }


def _read_int_env(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(int(raw), minimum)
    except ValueError:
        LOGGER.warning("Invalid integer value for %s=%r. Using default %s.", name, raw, default)
        return default


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    LOGGER.warning("Invalid boolean value for %s=%r. Using default %s.", name, raw, default)
    return default


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    full_refresh_interval = _read_int_env("EPAPER_FULL_REFRESH_INTERVAL", default=4, minimum=1)
    sleep_between_updates = _read_bool_env("EPAPER_SLEEP_BETWEEN_UPDATES", default=False)

    storage = Storage(data_dir=data_dir)
    display = EPaperDisplay(
        preview_path=data_dir / "last_render.png",
        full_refresh_interval=full_refresh_interval,
        sleep_between_updates=sleep_between_updates,
    )
    controller = ReaderController(storage=storage, display=display)
    buttons = ButtonController(
        on_previous=controller.previous_page,
        on_next=controller.next_page,
    )
    buttons.start()

    host = os.getenv("EPAPER_READER_HOST", "0.0.0.0")
    port = int(os.getenv("EPAPER_READER_PORT", "8000"))

    app = create_web_app(controller)

    try:
        app.run(host=host, port=port, debug=False)
    finally:
        buttons.cleanup()
        display.shutdown()


if __name__ == "__main__":
    main()
