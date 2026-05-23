"""Проверка и автоматическая установка обновлений лаунчера с GitHub Releases."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

from app_paths import launcher_dir
from version import GITHUB_REPO, LAUNCHER_VERSION, launcher_exe_name

_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_TIMEOUT = 12
_DOWNLOAD_TIMEOUT = 300
_CHUNK = 256 * 1024


@dataclass(frozen=True)
class UpdateInfo:
    current: str
    latest: str
    download_url: str
    release_page: str

    @property
    def available(self) -> bool:
        return _version_tuple(self.latest) > _version_tuple(self.current)

    @property
    def target_exe_name(self) -> str:
        return launcher_exe_name(self.latest)


def _version_tuple(text: str) -> tuple[int, ...]:
    nums = [int(x) for x in re.findall(r"\d+", text.lstrip("v"))[:3]]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def check_for_update() -> UpdateInfo | None:
    try:
        resp = requests.get(
            _API,
            timeout=_TIMEOUT,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError, KeyError):
        return None

    tag = str(data.get("tag_name", "")).strip() or LAUNCHER_VERSION
    latest = tag.lstrip("v")
    page = str(data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases"))
    download = page
    expected = launcher_exe_name(latest).lower()
    for asset in data.get("assets") or []:
        name = str(asset.get("name", "")).lower()
        if name == expected or name == "minecraftlauncher.exe":
            download = str(asset.get("browser_download_url", page))
            break

    info = UpdateInfo(
        current=LAUNCHER_VERSION,
        latest=latest,
        download_url=download,
        release_page=page,
    )
    return info if info.available else None


def _validate_download_url(url: str, exe_name: str) -> None:
    low = url.lower()
    if not low.endswith(".exe") and exe_name.lower() not in low:
        raise ValueError(
            "В релизе нет прямой ссылки на EXE. "
            f"Скачайте вручную: {launcher_exe_name()}"
        )


def download_update(
    info: UpdateInfo,
    dest: Path,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Скачивает EXE во временный файл, затем переименовывает в dest."""
    _validate_download_url(info.download_url, info.target_exe_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".download")
    if tmp.exists():
        tmp.unlink()

    try:
        with requests.get(
            info.download_url,
            stream=True,
            timeout=_DOWNLOAD_TIMEOUT,
            headers={"Accept": "application/octet-stream"},
        ) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length") or 0)
            done = 0
            with tmp.open("wb") as handle:
                for chunk in resp.iter_content(chunk_size=_CHUNK):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    done += len(chunk)
                    if on_progress is not None:
                        on_progress(done, total)
        if tmp.stat().st_size < 1024 * 1024:
            raise ValueError("Скачанный файл слишком маленький — возможно, это не EXE.")
        if dest.exists():
            dest.unlink()
        tmp.replace(dest)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    return dest


def _ps_literal(path: Path) -> str:
    """Путь для одинарных кавычек в PowerShell."""
    return str(path.resolve()).replace("'", "''")


def cleanup_stale_launcher_exes() -> None:
    """При запуске EXE убирает лишние MinecraftLauncher-v*.exe в папке лаунчера."""
    if not getattr(sys, "frozen", False):
        return
    _cleanup_old_launcher_exes(launcher_dir(), Path(sys.executable))


def _cleanup_old_launcher_exes(folder: Path, keep: Path) -> None:
    """Удаляет старые MinecraftLauncher-v*.exe в папке (кроме новой версии)."""
    keep_resolved = keep.resolve()
    pattern = "MinecraftLauncher-v*.exe"
    for path in folder.glob(pattern):
        try:
            if path.resolve() != keep_resolved and path.is_file():
                path.unlink(missing_ok=True)
        except OSError:
            pass
    legacy = folder / "MinecraftLauncher.exe"
    try:
        if legacy.is_file() and legacy.resolve() != keep_resolved:
            legacy.unlink(missing_ok=True)
    except OSError:
        pass


def _schedule_windows_restart(
    new_exe: Path,
    *,
    parent_pid: int,
) -> None:
    """Фоновый скрипт: ждёт выход лаунчера, удаляет все старые EXE, запускает новый."""
    folder = launcher_dir()
    script = folder / "_launcher_update.ps1"
    new_path = _ps_literal(new_exe.resolve())
    dir_path = _ps_literal(folder.resolve())
    cleanup_block = f"""
$dir = '{dir_path}'
$keep = '{new_path}'
Get-ChildItem -LiteralPath $dir -Filter 'MinecraftLauncher-v*.exe' -ErrorAction SilentlyContinue |
  Where-Object {{ $_.FullName -ne $keep }} |
  ForEach-Object {{ Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }}
$legacy = Join-Path $dir 'MinecraftLauncher.exe'
if ((Test-Path -LiteralPath $legacy) -and ($legacy -ne $keep)) {{
  Remove-Item -LiteralPath $legacy -Force -ErrorAction SilentlyContinue
}}
"""
    content = f"""$ErrorActionPreference = 'SilentlyContinue'
$pidToWait = {parent_pid}
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {{
    Start-Sleep -Milliseconds 400
}}
{cleanup_block}
Start-Process -FilePath '{new_path}'
Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
"""
    script.write_text(content, encoding="utf-8-sig")
    legacy_bat = folder / "_launcher_update.bat"
    legacy_bat.unlink(missing_ok=True)

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(script),
        ],
        creationflags=create_no_window,
        close_fds=True,
        cwd=str(folder),
    )


def apply_self_update(
    info: UpdateInfo,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """
    Скачивает новую версию в папку лаунчера и перезапускает приложение.
    Для собранного EXE на Windows старый файл удаляется после выхода процесса.
    """
    folder = launcher_dir()
    dest = folder / info.target_exe_name
    download_update(info, dest, on_progress=on_progress)

    if getattr(sys, "frozen", False) and sys.platform == "win32":
        _schedule_windows_restart(
            dest.resolve(),
            parent_pid=os.getpid(),
        )
        return dest

    if sys.platform == "win32":
        os.startfile(dest)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(
            [str(dest)],
            cwd=str(folder),
            start_new_session=True,
        )
    return dest
