"""Глобальные настройки лаунчера."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SETTINGS_NAME = "settings.json"


@dataclass
class LauncherSettings:
    java_path: str = ""
    dark_theme: bool = True
    favorite_versions: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, launcher_dir: Path) -> LauncherSettings:
        path = launcher_dir / SETTINGS_NAME
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls()
            return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            return cls()

    def save(self, launcher_dir: Path) -> None:
        path = launcher_dir / SETTINGS_NAME
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
