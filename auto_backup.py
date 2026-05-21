"""Автоматические бэкапы перед рискованными операциями."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from build_backup import export_build_zip
from builds import Build


def create_auto_backup(build: Build, launcher_dir: Path, tag: str) -> Path:
    backups_dir = launcher_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\-]+", "-", build.name.strip()).strip("-")[:28] or "build"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backups_dir / f"{safe}-{tag}-{stamp}.zip"
    return export_build_zip(build, launcher_dir, dest)
