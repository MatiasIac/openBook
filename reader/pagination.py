from __future__ import annotations

import textwrap
from typing import List

from PIL import Image, ImageDraw, ImageFont


def _make_draw() -> ImageDraw.ImageDraw:
    canvas = Image.new("1", (1, 1), 255)
    return ImageDraw.Draw(canvas)


def _estimate_chars_per_line(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    max_width: int,
) -> int:
    sample = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    left, _, right, _ = draw.textbbox((0, 0), sample, font=font)
    sample_width = max(right - left, 1)
    avg_char_width = max(sample_width / len(sample), 1.0)
    return max(int(max_width // avg_char_width), 1)


def _estimate_lines_per_page(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    max_height: int,
    line_spacing: int,
) -> int:
    _, top, _, bottom = draw.textbbox((0, 0), "Ag", font=font)
    line_height = max((bottom - top) + line_spacing, 1)
    return max(max_height // line_height, 1)


def wrap_text_to_lines(text: str, chars_per_line: int) -> List[str]:
    lines: List[str] = []

    wrapper = textwrap.TextWrapper(
        width=max(chars_per_line, 1),
        expand_tabs=True,
        replace_whitespace=False,
        drop_whitespace=False,
        break_long_words=True,
        break_on_hyphens=False,
    )

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = normalized.split("\n")

    for paragraph in paragraphs:
        if paragraph.strip() == "":
            lines.append("")
            continue

        wrapped = wrapper.wrap(paragraph)
        if wrapped:
            lines.extend(wrapped)
        else:
            lines.append("")

    while lines and lines[-1] == "":
        lines.pop()

    return lines or [""]


def paginate_lines(
    lines: List[str],
    lines_per_page: int,
) -> List[List[str]]:
    pages: List[List[str]] = []
    for idx in range(0, len(lines), lines_per_page):
        pages.append(lines[idx : idx + lines_per_page])

    return pages or [[""]]


def paginate_text(
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_height: int,
    line_spacing: int = 4,
) -> List[List[str]]:
    draw = _make_draw()
    chars_per_line = _estimate_chars_per_line(
        draw=draw,
        font=font,
        max_width=max_width,
    )
    lines_per_page = _estimate_lines_per_page(
        draw=draw,
        font=font,
        max_height=max_height,
        line_spacing=line_spacing,
    )
    lines = wrap_text_to_lines(text=text, chars_per_line=chars_per_line)
    return paginate_lines(
        lines=lines,
        lines_per_page=lines_per_page,
    )
