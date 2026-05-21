"""Проверка новой версии лаунчера на GitHub Releases."""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from version import GITHUB_REPO, LAUNCHER_VERSION

_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_TIMEOUT = 12


@dataclass(frozen=True)
class UpdateInfo:
    current: str
    latest: str
    download_url: str
    release_page: str

    @property
    def available(self) -> bool:
        return _version_tuple(self.latest) > _version_tuple(self.current)


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
    for asset in data.get("assets") or []:
        if str(asset.get("name", "")).lower() == "minecraftlauncher.exe":
            download = str(asset.get("browser_download_url", page))
            break

    info = UpdateInfo(
        current=LAUNCHER_VERSION,
        latest=latest,
        download_url=download,
        release_page=page,
    )
    return info if info.available else None
