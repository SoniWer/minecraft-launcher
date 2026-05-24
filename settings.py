"""Глобальные настройки лаунчера."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SETTINGS_NAME = "settings.json"
MAX_RECENT_BUILDS = 5
MAX_SAVED_USERNAMES = 8


@dataclass
class LauncherSettings:
    java_path: str = ""
    dark_theme: bool = True
    favorite_versions: list[str] = field(default_factory=list)
    window_width: int = 0
    window_height: int = 0
    recent_builds: list[str] = field(default_factory=list)
    saved_usernames: list[str] = field(default_factory=list)
    last_seen_crash_key: str = ""
    last_seen_launcher_version: str = ""
    show_game_log: bool = False
    discord_presence_enabled: bool = False

    @classmethod
    def load(cls, launcher_dir: Path) -> LauncherSettings:
        path = launcher_dir / SETTINGS_NAME
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls()
            fields = cls.__dataclass_fields__
            kwargs = {}
            for key in fields:
                if key not in data:
                    continue
                val = data[key]
                if key in ("recent_builds", "saved_usernames", "favorite_versions"):
                    kwargs[key] = val if isinstance(val, list) else []
                elif key in ("window_width", "window_height"):
                    kwargs[key] = int(val) if isinstance(val, (int, float)) else 0
                elif key in ("show_game_log", "discord_presence_enabled"):
                    kwargs[key] = bool(val)
                elif key in ("discord_client_id", "discord_presence_consent"):
                    pass
                elif key == "last_seen_launcher_version":
                    kwargs[key] = str(val) if val else ""
                else:
                    kwargs[key] = val
            return cls(**kwargs)
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            return cls()

    def save(self, launcher_dir: Path) -> None:
        path = launcher_dir / SETTINGS_NAME
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def remember_build(self, name: str) -> None:
        name = name.strip()
        if not name:
            return
        rest = [n for n in self.recent_builds if n != name]
        self.recent_builds = ([name] + rest)[:MAX_RECENT_BUILDS]

    def remember_username(self, name: str) -> None:
        name = name.strip()
        if not name:
            return
        rest = [n for n in self.saved_usernames if n != name]
        self.saved_usernames = ([name] + rest)[:MAX_SAVED_USERNAMES]

    def ordered_build_names(self, all_names: list[str]) -> list[str]:
        recent = [n for n in self.recent_builds if n in all_names]
        rest = [n for n in all_names if n not in recent]
        return recent + rest
