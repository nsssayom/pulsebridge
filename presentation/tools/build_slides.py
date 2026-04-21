#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

import markdown


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "slides.md"
OUTPUT = ROOT / "slides.html"

SLIDE_SPLIT = re.compile(r"^\s*---\s*$", re.MULTILINE)
SLIDE_DIRECTIVE = re.compile(r"^\s*<!--\s*\.slide:\s*(.*?)\s*-->\s*", re.DOTALL)
NOTE_SPLIT = re.compile(r"(?m)^Note:\s*\n")


def md_to_html(text: str) -> str:
    return markdown.markdown(
        text.strip(),
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )


def indent(block: str, spaces: int = 2) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else "" for line in block.splitlines())


def split_notes(raw: str) -> tuple[str, str]:
    match = NOTE_SPLIT.search(raw)
    if not match:
        return raw.strip(), ""
    body = raw[: match.start()].strip()
    notes = raw[match.end() :].strip()
    return body, notes


def parse_slide(raw: str) -> str:
    chunk = raw.strip()
    attrs = ""

    directive = SLIDE_DIRECTIVE.match(chunk)
    if directive:
        attrs = " " + directive.group(1).strip()
        chunk = chunk[directive.end() :].lstrip()

    body, notes = split_notes(chunk)
    body_html = md_to_html(body)

    notes_html = ""
    if notes:
        notes_html = f"\n  <aside class=\"notes\">\n{indent(md_to_html(notes), 4)}\n  </aside>"

    return f"<section{attrs}>\n{indent(body_html, 2)}{notes_html}\n</section>"


def main() -> int:
    slides = [parse_slide(chunk) for chunk in SLIDE_SPLIT.split(SOURCE.read_text()) if chunk.strip()]
    OUTPUT.write_text("\n\n".join(slides) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
