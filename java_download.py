"""Скачивание Java (Eclipse Temurin) в папку лаунчера."""

from __future__ import annotations

import io
import json
import platform
import shutil
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path

import requests

API_BASE = "https://api.adoptium.net/v3/assets/latest"
USER_AGENT = "SenkoMinecraftLauncher/1.0"


class JavaDownloadError(Exception):
    pass


def java_install_dir(launcher_dir: Path, major: int) -> Path:
    return launcher_dir / "java" / f"jdk-{major}"


def installed_java_path(launcher_dir: Path, major: int) -> Path | None:
    root = java_install_dir(launcher_dir, major)
    if not root.is_dir():
        return None
    exe = "java.exe" if sys.platform == "win32" else "java"
    for path in (root / "bin" / exe, root / "jre" / "bin" / exe):
        if path.is_file():
            return path
    for path in root.rglob(exe):
        if path.is_file() and path.parent.name == "bin":
            return path
    return None


def _platform_params() -> dict[str, str]:
    if sys.platform == "win32":
        os_name = "windows"
        arch = (
            "x64"
            if platform.machine().lower() in ("amd64", "x86_64", "arm64")
            else "x86"
        )
    elif sys.platform == "darwin":
        os_name = "mac"
        arch = "aarch64" if platform.machine().lower() == "arm64" else "x64"
    else:
        os_name = "linux"
        arch = "x64"
    return {"os": os_name, "architecture": arch, "image_type": "jre", "archive_type": "zip"}


def download_java(
    launcher_dir: Path,
    major: int,
    *,
    on_status: Callable[[str], None] | None = None,
) -> Path:
    def status(msg: str) -> None:
        if on_status:
            on_status(msg)

    existing = installed_java_path(launcher_dir, major)
    if existing:
        return existing

    url = f"{API_BASE}/{major}/hotspot"
    status(f"Поиск Java {major}...")
    response = requests.get(
        url,
        params=_platform_params(),
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    if response.status_code >= 400:
        raise JavaDownloadError(f"API Temurin: {response.status_code}")

    assets = response.json()
    if not assets:
        raise JavaDownloadError(f"Нет сборки Java {major} для вашей ОС.")

    download_link = assets[0]["binary"]["package"]["link"]
    status(f"Скачивание Java {major}...")
    file_response = requests.get(
        download_link, headers={"User-Agent": USER_AGENT}, timeout=300
    )
    file_response.raise_for_status()

    dest_root = java_install_dir(launcher_dir, major)
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

    status("Распаковка...")
    with zipfile.ZipFile(io.BytesIO(file_response.content)) as zf:
        zf.extractall(dest_root)

    java_bin = installed_java_path(launcher_dir, major)
    if not java_bin:
        raise JavaDownloadError("Java установлена, но исполняемый файл не найден.")
    status(f"Java {major} готова: {java_bin}")
    return java_bin
