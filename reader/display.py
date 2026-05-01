from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from PIL import Image, ImageDraw, ImageFont

LOGGER = logging.getLogger(__name__)


@dataclass
class EPaperDisplay:
    preview_path: Path | None = None
    margin_x: int = 16
    margin_y: int = 12
    header_height: int = 24
    line_spacing: int = 4
    body_font_size: int = 18
    header_font_size: int = 14
    full_refresh_interval: int = 4
    sleep_between_updates: bool = False

    def __post_init__(self) -> None:
        self._epd = None
        self.width = 400
        self.height = 300
        self._active_init_mode: str | None = None
        self._is_sleeping = False
        self._full_display_method: str | None = None
        self._partial_display_method: str | None = None
        try:
            self._full_refresh_interval = max(int(self.full_refresh_interval), 1)
        except (TypeError, ValueError):
            self._full_refresh_interval = 4
        self._renders_since_full = self._full_refresh_interval

        self.body_font = self._load_font(self.body_font_size)
        self.header_font = self._load_font(self.header_font_size)

        try:
            from waveshare_epd import epd4in2_V2

            self._epd = epd4in2_V2.EPD()
            self.width = int(getattr(self._epd, "width", self.width))
            self.height = int(getattr(self._epd, "height", self.height))
            self._full_display_method = self._resolve_method_name(("display", "Display"))
            self._partial_display_method = self._resolve_method_name(
                (
                    "display_Partial",
                    "displayPartial",
                    "Display_Partial",
                    "DisplayPartial",
                    "display_Fast",
                    "displayFast",
                )
            )
            if self._full_display_method is None:
                raise RuntimeError("Display driver does not expose a full refresh display method.")
            LOGGER.info("Initialized epd4in2_V2 display (%sx%s).", self.width, self.height)
            if self._partial_display_method is None:
                LOGGER.info("Partial refresh not available; using full refresh on every page.")
            else:
                LOGGER.info(
                    "Partial refresh enabled via %s() with full refresh every %s page turns.",
                    self._partial_display_method,
                    self._full_refresh_interval,
                )
        except Exception as exc:
            self._epd = None
            LOGGER.warning("Running in preview mode; ePaper not available: %s", exc)

    @property
    def body_width(self) -> int:
        return self.width - (2 * self.margin_x)

    @property
    def body_height(self) -> int:
        return self.height - self.margin_y - self.header_height - self.margin_y

    def _load_font(self, size: int) -> ImageFont.ImageFont:
        font_candidates = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/arial.ttf",
        )
        for font_path in font_candidates:
            try:
                return ImageFont.truetype(font_path, size=size)
            except OSError:
                continue
        return ImageFont.load_default()

    def render_page(self, lines: List[str], page_index: int, total_pages: int) -> None:
        image = Image.new("1", (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        safe_total = max(total_pages, 1)
        safe_index = max(min(page_index, safe_total - 1), 0)
        header = f"Page {safe_index + 1}/{safe_total}"
        header_y = self.margin_y // 2
        draw.text((self.margin_x, header_y), header, font=self.header_font, fill=0)

        rule_y = self.margin_y + self.header_height - 6
        draw.line(
            (self.margin_x, rule_y, self.width - self.margin_x, rule_y),
            fill=0,
            width=1,
        )

        _, top, _, bottom = draw.textbbox((0, 0), "Ag", font=self.body_font)
        line_height = max((bottom - top) + self.line_spacing, 1)

        y = self.margin_y + self.header_height
        for line in lines:
            draw.text((self.margin_x, y), line, font=self.body_font, fill=0)
            y += line_height

        self._send_to_display(image)
        self._save_preview(image)

    def _resolve_method_name(self, names: Sequence[str]) -> str | None:
        if self._epd is None:
            return None
        for name in names:
            candidate = getattr(self._epd, name, None)
            if callable(candidate):
                return name
        return None

    def _ensure_init_mode(self, mode: str) -> None:
        if self._epd is None:
            return
        if self._active_init_mode == mode and not self._is_sleeping:
            return

        init_names = ("init_fast", "init_Fast") if mode == "fast" else ("init",)
        method_name = self._resolve_method_name(init_names)
        if method_name is None and mode == "fast":
            LOGGER.debug("Fast init method not found; falling back to full init.")
            self._ensure_init_mode("full")
            return
        if method_name is None:
            raise RuntimeError("Display driver does not expose an init method.")

        getattr(self._epd, method_name)()
        self._active_init_mode = mode
        self._is_sleeping = False

    def _prepare_frame(self, image: Image.Image) -> object:
        if self._epd is None:
            return image
        to_buffer = getattr(self._epd, "getbuffer", None)
        if callable(to_buffer):
            return to_buffer(image)
        return image

    def _invoke_display_method(self, method_name: str, frame: object) -> None:
        if self._epd is None:
            return
        renderer = getattr(self._epd, method_name, None)
        if not callable(renderer):
            raise RuntimeError(f"Display method {method_name} is unavailable.")
        renderer(frame)

    def _sleep_display(self) -> None:
        if self._epd is None or self._is_sleeping:
            return
        sleeper = getattr(self._epd, "sleep", None)
        if not callable(sleeper):
            return
        sleeper()
        self._active_init_mode = None
        self._is_sleeping = True

    def _send_to_display(self, image: Image.Image) -> None:
        if self._epd is None:
            return

        try:
            started_at = time.monotonic()
            frame = self._prepare_frame(image)
            can_use_partial = self._partial_display_method is not None and self._full_refresh_interval > 1
            should_full_refresh = (not can_use_partial) or (
                self._renders_since_full >= self._full_refresh_interval
            )

            if should_full_refresh:
                if self._full_display_method is None:
                    raise RuntimeError("Full refresh display method is unavailable.")
                self._ensure_init_mode("full")
                LOGGER.info("Sending full refresh frame to ePaper display.")
                self._invoke_display_method(self._full_display_method, frame)
                self._renders_since_full = 0
            else:
                try:
                    partial_method = self._partial_display_method
                    if partial_method is None:
                        raise RuntimeError("Partial refresh display method is unavailable.")
                    self._ensure_init_mode("fast")
                    LOGGER.info("Sending partial refresh frame to ePaper display.")
                    self._invoke_display_method(partial_method, frame)
                    self._renders_since_full += 1
                except Exception:
                    LOGGER.exception("Partial refresh failed; retrying with a full refresh.")
                    self._partial_display_method = None
                    if self._full_display_method is None:
                        raise RuntimeError("Full refresh display method is unavailable.")
                    self._ensure_init_mode("full")
                    self._invoke_display_method(self._full_display_method, frame)
                    self._renders_since_full = 0

            if self.sleep_between_updates:
                self._sleep_display()
            LOGGER.info("ePaper update complete (%.2fs total).", time.monotonic() - started_at)
        except Exception:
            LOGGER.exception("Failed to render frame on ePaper display.")

    def _save_preview(self, image: Image.Image) -> None:
        if self.preview_path is None:
            return

        try:
            self.preview_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(self.preview_path)
        except Exception:
            LOGGER.exception("Failed to write preview image at %s", self.preview_path)

    def shutdown(self) -> None:
        if self._epd is None:
            return
        try:
            self._sleep_display()
        except Exception:
            LOGGER.exception("Failed while putting ePaper display to sleep.")
