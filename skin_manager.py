"""Скины и плащи: загрузка, превью, применение (CustomSkinLoader)."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import requests

CSL_CONFIG_REL = Path("config") / "CustomSkinLoader" / "CustomSkinLoader.json"
CSL_SKIN_DIR_NAME = "CustomSkin"


def offline_uuid(username: str) -> str:
    return str(uuid.uuid3(uuid.NAMESPACE_OID, f"OfflinePlayer:{username.strip()}"))


def build_skin_paths(build_root: Path) -> tuple[Path, Path]:
    return build_root / "skin.png", build_root / "cape.png"


def fetch_skin_bytes(username: str) -> bytes:
    name = username.strip()
    if not name:
        raise ValueError("Введите никнейм")
    url = f"https://minotar.net/skin/{name}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    if len(resp.content) < 100:
        raise ValueError("Скин не найден для этого ника")
    return resp.content


def fetch_cape_bytes(username: str) -> bytes:
    name = username.strip()
    if not name:
        raise ValueError("Введите никнейм")
    url = f"https://minotar.net/cape/{name}"
    resp = requests.get(url, timeout=20)
    if resp.status_code == 404:
        raise ValueError("Плащ не найден для этого ника")
    resp.raise_for_status()
    return resp.content


def save_skin_file(build_root: Path, data: bytes) -> Path:
    build_root.mkdir(parents=True, exist_ok=True)
    path = build_skin_paths(build_root)[0]
    path.write_bytes(data)
    return path


def save_cape_file(build_root: Path, data: bytes) -> Path:
    build_root.mkdir(parents=True, exist_ok=True)
    path = build_skin_paths(build_root)[1]
    path.write_bytes(data)
    return path


def apply_skin_to_game(
    game_dir: Path,
    build_root: Path,
    *,
    username: str,
) -> None:
    """Скопировать скин/плащ в game и обновить конфиг CustomSkinLoader."""
    skin_src, cape_src = build_skin_paths(build_root)
    if not skin_src.is_file() and not cape_src.is_file():
        return

    skin_dir = game_dir / CSL_SKIN_DIR_NAME
    skin_dir.mkdir(parents=True, exist_ok=True)

    if skin_src.is_file():
        shutil.copy2(skin_src, skin_dir / "launcher_skin.png")
    if cape_src.is_file():
        shutil.copy2(cape_src, skin_dir / "launcher_cape.png")

    loadlist: list[dict] = []
    entry: dict = {
        "name": "Minecraft Launcher",
        "type": "Legacy",
        "skin": str((skin_dir / "launcher_skin.png").resolve()).replace("\\", "/"),
    }
    if cape_src.is_file():
        entry["cape"] = str((skin_dir / "launcher_cape.png").resolve()).replace("\\", "/")
    if skin_src.is_file():
        loadlist.append(entry)

    config_dir = game_dir / CSL_CONFIG_REL.parent
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = game_dir / CSL_CONFIG_REL
    payload = {
        "version": "14.25",
        "buildNumber": 25,
        "loadlist": loadlist,
    }
    config_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_preview_image(path: Path | None):
    """PIL Image для превью или None."""
    if path is None or not path.is_file():
        return None
    from PIL import Image

    return Image.open(path).convert("RGBA")
