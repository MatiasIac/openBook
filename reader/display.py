from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

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

    def __post_init__(self) -> None:
        self._epd = None
        self.width = 400
        self.height = 300

        self.body_font = self._load_font(self.body_font_size)
        self.header_font = self._load_font(self.header_font_size)

        try:
            from waveshare_epd import epd4in2_V2

            self._epd = epd4in2_V2.EPD()
            self._epd.init()
            self.width = int(getattr(self._epd, "width", self.width))
            self.height = int(getattr(self._epd, "height", self.height))
            LOGGER.info("Initialized epd4in2_V2 display (%sx%s).", self.width, self.height)
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

    def _send_to_display(self, image: Image.Image) -> None:
        if self._epd is None:
            return

        try:
            started_at = time.monotonic()
            LOGGER.info("Sending frame to ePaper display.")
            self._epd.init()
            LOGGER.info("ePaper init complete. Starting refresh.")
            self._epd.display(self._epd.getbuffer(image))
            LOGGER.info("ePaper refresh complete. Entering sleep mode.")
            self._epd.sleep()
            LOGGER.info("ePaper sleep complete (%.2fs total).", time.monotonic() - started_at)
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
            self._epd.sleep()
        except Exception:
            LOGGER.exception("Failed while putting ePaper display to sleep.")
