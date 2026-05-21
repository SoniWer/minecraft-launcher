"""Клиент CurseForge API v1 (нужен API-ключ с console.curseforge.com)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

BASE_URL = "https://api.curseforge.com/v1"
MINECRAFT_GAME_ID = 432

# CurseForge ModLoaderType
LOADER_MAP = {
    "forge": 1,
    "fabric": 4,
    "quilt": 5,
    "neoforge": 6,
}


class CurseForgeError(Exception):
    pass


@dataclass(frozen=True)
class CfMod:
    id: int
    name: str
    slug: str
    summary: str
    download_count: int
    logo_url: str


@dataclass(frozen=True)
class CfFile:
    id: int
    display_name: str
    file_name: str
    download_url: str


class CurseForgeClient:
    def __init__(self, api_key: str) -> None:
        key = api_key.strip()
        if not key:
            raise CurseForgeError(
                "Укажите API-ключ CurseForge в Настройках (console.curseforge.com)."
            )
        self._session = requests.Session()
        self._session.headers["x-api-key"] = key
        self._session.headers["User-Agent"] = "MinecraftLauncher/1.3"

    def _get(self, path: str, params: dict | None = None) -> Any:
        url = f"{BASE_URL}{path}"
        try:
            resp = self._session.get(url, params=params or {}, timeout=30)
        except requests.RequestException as exc:
            raise CurseForgeError(f"Сеть: {exc}") from exc
        if resp.status_code == 403:
            raise CurseForgeError("Неверный или просроченный API-ключ CurseForge.")
        if resp.status_code != 200:
            raise CurseForgeError(f"CurseForge HTTP {resp.status_code}")
        data = resp.json()
        if "data" not in data:
            raise CurseForgeError("Неожиданный ответ CurseForge")
        return data["data"]

    def search_mods(
        self,
        query: str,
        *,
        game_version: str = "",
        loader_id: str = "",
        index: int = 0,
        page_size: int = 20,
    ) -> list[CfMod]:
        body: dict[str, Any] = {
            "gameId": MINECRAFT_GAME_ID,
            "searchFilter": query.strip(),
            "sortField": 2,
            "sortOrder": "desc",
            "index": index,
            "pageSize": page_size,
        }
        if game_version:
            body["gameVersion"] = game_version
        lid = LOADER_MAP.get(loader_id)
        if lid is not None:
            body["modLoaderType"] = lid

        try:
            resp = self._session.post(
                f"{BASE_URL}/mods/search",
                json=body,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise CurseForgeError(f"Сеть: {exc}") from exc
        if resp.status_code != 200:
            raise CurseForgeError(f"Поиск: HTTP {resp.status_code}")
        payload = resp.json().get("data") or []
        out: list[CfMod] = []
        for item in payload:
            logo = ""
            if isinstance(item.get("logo"), dict):
                logo = item["logo"].get("thumbnailUrl") or item["logo"].get("url") or ""
            out.append(
                CfMod(
                    id=int(item["id"]),
                    name=str(item.get("name", "")),
                    slug=str(item.get("slug", "")),
                    summary=str(item.get("summary", ""))[:200],
                    download_count=int(item.get("downloadCount") or 0),
                    logo_url=logo,
                )
            )
        return out

    def mod_files(self, mod_id: int, game_version: str = "") -> list[CfFile]:
        params: dict[str, Any] = {"pageSize": 15}
        if game_version:
            params["gameVersion"] = game_version
        data = self._get(f"/mods/{mod_id}/files", params)
        files: list[CfFile] = []
        for item in data:
            url = str(item.get("downloadUrl") or "")
            if not url:
                continue
            files.append(
                CfFile(
                    id=int(item["id"]),
                    display_name=str(item.get("displayName", "")),
                    file_name=str(item.get("fileName", "")),
                    download_url=url,
                )
            )
        return files
