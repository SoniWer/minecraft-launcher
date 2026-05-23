"""Текст «Что нового» для показа после обновления лаунчера."""

from __future__ import annotations

import re
from pathlib import Path

_SECTION = re.compile(
    r"^##\s+Что нового в v(?P<ver>[\d.]+)\s*$",
    re.MULTILINE,
)
_BULLET = re.compile(r"^-\s+(.+)$", re.MULTILINE)


def _notes_path() -> Path:
    return Path(__file__).resolve().parent / ".github" / "RELEASE_NOTES.md"


def changelog_for_version(version: str) -> str | None:
    ver = version.lstrip("v").strip()
    try:
        text = _notes_path().read_text(encoding="utf-8")
    except OSError:
        return None

    sections: list[tuple[str, str]] = []
    matches = list(_SECTION.finditer(text))
    for index, match in enumerate(matches):
        sec_ver = match.group("ver")
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((sec_ver, text[start:end]))

    for sec_ver, body in sections:
        if sec_ver != ver:
            continue
        bullets = _BULLET.findall(body)
        if bullets:
            return f"Версия {ver}\n\n" + "\n".join(f"• {line}" for line in bullets)
        snippet = body.strip().split("\n\n")[0].strip()
        return f"Версия {ver}\n\n{snippet}" if snippet else f"Версия {ver}"
    return None
