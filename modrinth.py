"""Клиент открытого API Modrinth v2."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests

MODRINTH_API = "https://api.modrinth.com/v2"


def modrinth_user_agent() -> str:
    try:
        from version import LAUNCHER_VERSION

        ver = LAUNCHER_VERSION
    except Exception:
        ver = "dev"
    return f"SenkoMinecraftLauncher/{ver} (github.com/SoniWer/minecraft-launcher)"


USER_AGENT = modrinth_user_agent()

CONTENT_FOLDERS = {
    "mod": "mods",
    "resourcepack": "resourcepacks",
    "shader": "shaderpacks",
}

LOADER_IDS = {
    "fabric": "fabric",
    "forge": "forge",
    "neoforge": "neoforge",
    "quilt": "quilt",
}


class ModrinthError(Exception):
    pass


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT}


def _request(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{MODRINTH_API}{path}"
    response = requests.request(method, url, headers=_headers(), timeout=30, **kwargs)
    if response.status_code >= 400:
        raise ModrinthError(f"Modrinth API {response.status_code}: {response.text[:300]}")
    if not response.content:
        return None
    return response.json()


def mc_version_facet_values(mc_version: str) -> list[str]:
    """Варианты версии для поиска (OR): 1.21.1 и 1.21 и т.д."""
    values: list[str] = []
    parts = mc_version.split(".")
    for i in range(len(parts), 1, -1):
        values.append(".".join(parts[:i]))
    return list(dict.fromkeys(values))


def mc_version_match_values(mc_version: str) -> list[str]:
    return mc_version_facet_values(mc_version)


def resolve_loader_param(project_type: str, loader: str | None) -> str | None:
    """Загрузчик для API версий: только моды и modpack."""
    if project_type in ("mod", "modpack"):
        return loader
    return None


# Modrinth: у шейдеров нет categories:fabric — фильтр по платформе шейдеров
SHADER_LOADER_CATEGORIES: dict[str, list[str]] = {
    "fabric": ["iris", "canvas"],
    "quilt": ["iris"],
    "forge": ["optifine"],
    "neoforge": ["iris"],
    "vanilla": ["optifine"],
}


def search_loader_facets(project_type: str, loader: str | None) -> list[list[str]]:
    """Дополнительные facet-группы для /search (внутри группы — OR)."""
    if not loader:
        return []
    if project_type in ("mod", "modpack"):
        return [[f"categories:{loader}"]]
    if project_type == "shader":
        cats = SHADER_LOADER_CATEGORIES.get(loader, ["iris", "optifine"])
        return [[f"categories:{c}" for c in cats]]
    # Текстуры совместимы с любым загрузчиком — только фильтр по версии MC
    return []


def version_supports_mc(version: dict[str, Any], mc_version: str) -> bool:
    game_versions = version.get("game_versions") or []
    if mc_version in game_versions:
        return True
    candidates = mc_version_facet_values(mc_version)
    for gv in game_versions:
        if gv in candidates:
            return True
        for candidate in candidates:
            if gv.startswith(candidate + ".") or candidate.startswith(gv + "."):
                return True
    return False


DEPENDENCY_INSTALL_TYPES = frozenset({"required", "embedded"})
STABLE_VERSION_TYPES = frozenset({"release"})


def is_stable_version(version: dict[str, Any]) -> bool:
    return version.get("version_type") in STABLE_VERSION_TYPES


def pick_stable_version(versions: list[dict[str, Any]]) -> dict[str, Any] | None:
    for version in versions:
        if is_stable_version(version):
            return version
    return None


def default_version_index(versions: list[dict[str, Any]]) -> int:
    """Индекс версии по умолчанию: первая стабильная, иначе 0 (ручной выбор беты)."""
    for index, version in enumerate(versions):
        if is_stable_version(version):
            return index
    return 0 if versions else -1


def version_type_label(version_type: str) -> str:
    labels = {
        "release": "стабильная",
        "beta": "бета",
        "alpha": "альфа",
    }
    return labels.get(version_type, version_type or "?")


def get_version(version_id: str) -> dict[str, Any]:
    path = f"/version/{quote(version_id, safe='')}"
    result = _request("GET", path)
    return result if isinstance(result, dict) else {}


def list_installed_filenames(minecraft_dir: Path, project_type: str) -> set[str]:
    folder = CONTENT_FOLDERS.get(project_type, "mods")
    path = minecraft_dir / folder
    if not path.exists():
        return set()
    return {f.name.lower() for f in path.iterdir() if f.is_file()}


def get_latest_primary_filename(
    project_id: str,
    *,
    mc_version: str,
    project_type: str,
    loader: str | None,
) -> str | None:
    versions = get_project_versions(
        project_id,
        mc_version=mc_version,
        project_type=project_type,
        loader=loader,
    )
    if not versions:
        return None
    chosen = pick_stable_version(versions) or versions[0]
    file_info = pick_primary_file(chosen)
    return file_info["filename"] if file_info else None


def version_filenames(version: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for file_info in version.get("files") or []:
        fn = file_info.get("filename")
        if fn:
            names.append(str(fn))
    primary = pick_primary_file(version)
    if primary:
        fn = primary.get("filename")
        if fn and fn not in names:
            names.append(str(fn))
    return names


def project_is_installed(
    project_id: str,
    *,
    mc_version: str,
    project_type: str,
    loader: str | None,
    installed_files: set[str],
    check_files: bool = True,
    max_versions: int = 16,
) -> tuple[bool, str | None]:
    """Проверяет, есть ли в папке файл любой из совместимых версий проекта."""
    try:
        versions = get_project_versions(
            project_id,
            mc_version=mc_version,
            project_type=project_type,
            loader=loader,
        )
    except Exception:
        versions = []

    for version in versions[:max_versions]:
        for filename in version_filenames(version):
            if not check_files:
                return False, filename
            if filename.lower() in installed_files:
                return True, filename
    return False, None


def version_dest_path(
    version: dict[str, Any], *, minecraft_dir: Path, project_type: str
) -> Path | None:
    file_info = pick_primary_file(version)
    if not file_info:
        return None
    folder = CONTENT_FOLDERS.get(project_type, "mods")
    return minecraft_dir / folder / file_info["filename"]


def search_projects(
    *,
    query: str,
    project_type: str,
    mc_version: str,
    loader: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    version_facets = [f"versions:{v}" for v in mc_version_facet_values(mc_version)]
    facets: list[list[str]] = [
        [f"project_type:{project_type}"],
        version_facets,
    ]
    for group in search_loader_facets(project_type, loader):
        facets.append(group)

    params = {
        "query": query,
        "facets": json.dumps(facets),
        "index": "relevance" if query else "downloads",
        "offset": offset,
        "limit": limit,
    }
    return _request("GET", "/search", params=params)


def get_project_versions(
    project_id: str,
    *,
    mc_version: str,
    project_type: str = "mod",
    loader: str | None = None,
) -> list[dict[str, Any]]:
    path = f"/project/{quote(project_id, safe='')}/version"
    api_loader = resolve_loader_param(project_type, loader)
    game_versions = mc_version_match_values(mc_version)

    params: dict[str, str] = {"game_versions": json.dumps(game_versions)}
    if api_loader:
        params["loaders"] = json.dumps([api_loader])

    result = _request("GET", path, params=params)
    versions = result if isinstance(result, list) else []
    if versions:
        return [v for v in versions if version_supports_mc(v, mc_version)]

    # Запасной вариант: все версии и фильтр на клиенте
    fallback = _request("GET", path)
    all_versions = fallback if isinstance(fallback, list) else []
    filtered = [v for v in all_versions if version_supports_mc(v, mc_version)]
    if api_loader and project_type in ("mod", "modpack"):
        filtered = [
            v
            for v in filtered
            if api_loader in (v.get("loaders") or []) or "minecraft" in (v.get("loaders") or [])
        ]
    return filtered


def file_sha512(path: Path) -> str:
    digest = hashlib.sha512()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lookup_versions_by_hashes(hashes: list[str]) -> dict[str, dict[str, Any]]:
    if not hashes:
        return {}
    result = _request(
        "POST",
        "/version_files",
        json={"hashes": hashes, "algorithm": "sha512"},
    )
    return result if isinstance(result, dict) else {}


def check_file_updates(
    hashes: list[str],
    *,
    mc_version: str,
    loader: str | None,
) -> dict[str, dict[str, Any] | None]:
    if not hashes:
        return {}
    body: dict[str, Any] = {
        "hashes": hashes,
        "algorithm": "sha512",
        "game_versions": mc_version_match_values(mc_version),
    }
    if loader:
        body["loaders"] = [loader]
    result = _request("POST", "/version_files/update", json=body)
    if not isinstance(result, dict):
        return {}
    return {key: value for key, value in result.items()}


@dataclass
class ModUpdateInfo:
    filename: str
    path: Path
    project_title: str
    project_id: str
    current_version: str
    latest_version: str | None
    latest_version_id: str | None
    update_available: bool


def scan_mod_updates(
    mods_dir: Path,
    *,
    mc_version: str,
    loader: str | None,
) -> list[ModUpdateInfo]:
    """Проверяет .jar в mods/ через API Modrinth (sha512)."""
    if not mods_dir.is_dir():
        return []

    jar_files = [
        p
        for p in mods_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".jar" and not p.name.endswith(".disabled")
    ]
    if not jar_files:
        return []

    hash_by_path: dict[str, Path] = {}
    hashes: list[str] = []
    for jar in jar_files:
        try:
            digest = file_sha512(jar)
        except OSError:
            continue
        hash_by_path[digest] = jar
        hashes.append(digest)

    known = lookup_versions_by_hashes(hashes)
    updates = check_file_updates(hashes, mc_version=mc_version, loader=loader)

    results: list[ModUpdateInfo] = []
    for digest, jar in hash_by_path.items():
        current = known.get(digest) or {}
        project_id = str(current.get("project_id") or "")
        project_title = str(current.get("name") or jar.stem)
        current_version = str(current.get("version_number") or current.get("name") or "?")

        latest = updates.get(digest)
        latest_id = None
        latest_name = None
        if isinstance(latest, dict):
            latest_id = str(latest.get("id") or "") or None
            latest_name = str(latest.get("version_number") or latest.get("name") or "") or None

        update_available = bool(latest_id and latest_id != current.get("id"))
        results.append(
            ModUpdateInfo(
                filename=jar.name,
                path=jar,
                project_title=project_title,
                project_id=project_id,
                current_version=current_version,
                latest_version=latest_name,
                latest_version_id=latest_id,
                update_available=update_available,
            )
        )
    results.sort(key=lambda item: (not item.update_available, item.filename.lower()))
    return results


def pick_primary_file(version: dict[str, Any]) -> dict[str, Any] | None:
    files = version.get("files") or []
    for file_info in files:
        if file_info.get("primary"):
            return file_info
    return files[0] if files else None


def download_file(
    url: str,
    destination: Path,
    *,
    on_progress: Callable[[int, int | None], None] | None = None,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=_headers(), stream=True, timeout=120) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0)) or None
        downloaded = 0
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)
    return destination


def install_version(
    version: dict[str, Any],
    *,
    minecraft_dir: Path,
    project_type: str,
    on_progress: Callable[[int, int | None], None] | None = None,
    skip_existing: bool = True,
) -> tuple[Path | None, bool]:
    """Возвращает (путь, уже_был_установлен)."""
    dest = version_dest_path(version, minecraft_dir=minecraft_dir, project_type=project_type)
    if not dest:
        raise ModrinthError("У этой версии нет файлов для скачивания.")

    if skip_existing and dest.exists():
        return dest, True

    file_info = pick_primary_file(version)
    assert file_info is not None
    download_file(file_info["url"], dest, on_progress=on_progress)
    return dest, False


def resolve_dependency_version(
    dep: dict[str, Any],
    *,
    mc_version: str,
    loader: str | None,
) -> dict[str, Any] | None:
    dep_type = dep.get("dependency_type")
    if dep_type == "incompatible":
        return None
    if dep_type not in DEPENDENCY_INSTALL_TYPES:
        return None

    project_id = dep.get("project_id")
    version_id = dep.get("version_id")

    if version_id:
        resolved = get_version(version_id)
        if is_stable_version(resolved):
            return resolved
        project_id = project_id or resolved.get("project_id")

    if not project_id:
        return None
    versions = get_project_versions(
        project_id,
        mc_version=mc_version,
        project_type="mod",
        loader=loader,
    )
    return pick_stable_version(versions)


def collect_install_versions(
    version: dict[str, Any],
    *,
    mc_version: str,
    loader: str | None,
    install_dependencies: bool,
) -> list[dict[str, Any]]:
    seen_versions: set[str] = set()
    order: list[dict[str, Any]] = []

    def visit(current: dict[str, Any]) -> None:
        vid = current.get("id")
        if not vid or vid in seen_versions:
            return

        if install_dependencies:
            for dep in current.get("dependencies") or []:
                resolved = resolve_dependency_version(
                    dep, mc_version=mc_version, loader=loader
                )
                if resolved:
                    visit(resolved)

        seen_versions.add(vid)
        order.append(current)

    visit(version)
    return order


class InstallResult:
    __slots__ = ("path", "project_id", "skipped", "filename")

    def __init__(
        self, path: Path, project_id: str, *, skipped: bool, filename: str
    ) -> None:
        self.path = path
        self.project_id = project_id
        self.skipped = skipped
        self.filename = filename


def install_version_with_dependencies(
    version: dict[str, Any],
    *,
    minecraft_dir: Path,
    project_type: str,
    mc_version: str,
    loader: str | None = None,
    on_progress: Callable[[int, int | None], None] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> list[InstallResult]:
    install_deps = project_type == "mod"
    queue = collect_install_versions(
        version,
        mc_version=mc_version,
        loader=loader,
        install_dependencies=install_deps,
    )
    results: list[InstallResult] = []
    for item in queue:
        file_info = pick_primary_file(item)
        name = file_info["filename"] if file_info else item.get("name", "?")
        project_id = item.get("project_id") or item.get("projectId") or ""

        dest = version_dest_path(
            item, minecraft_dir=minecraft_dir, project_type=project_type
        )
        if dest and dest.exists():
            if on_status:
                on_status(f"Уже установлено: {name}")
            results.append(
                InstallResult(dest, project_id, skipped=True, filename=name)
            )
            continue

        if on_status:
            on_status(f"Скачивание: {name}")
        path, _skipped = install_version(
            item,
            minecraft_dir=minecraft_dir,
            project_type=project_type,
            on_progress=on_progress,
            skip_existing=True,
        )
        if path:
            results.append(
                InstallResult(path, project_id, skipped=False, filename=name)
            )

    if not results:
        main_dest = version_dest_path(
            version, minecraft_dir=minecraft_dir, project_type=project_type
        )
        if main_dest and main_dest.exists():
            fname = pick_primary_file(version)
            name = fname["filename"] if fname else main_dest.name
            return [
                InstallResult(
                    main_dest,
                    version.get("project_id") or "",
                    skipped=True,
                    filename=name,
                )
            ]
        raise ModrinthError("Нечего устанавливать.")
    return results


def pick_mrpack_file(version: dict[str, Any]) -> dict[str, Any] | None:
    for file_info in version.get("files") or []:
        if str(file_info.get("filename", "")).endswith(".mrpack"):
            return file_info
    return pick_primary_file(version)


def _modpack_manifest_path(game_dir: Path) -> Path:
    return game_dir / ".launcher" / "installed_modpacks.json"


def load_installed_modpacks(game_dir: Path) -> list[dict[str, Any]]:
    path = _modpack_manifest_path(game_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_installed_modpacks(game_dir: Path, entries: list[dict[str, Any]]) -> None:
    path = _modpack_manifest_path(game_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def is_modpack_installed(
    game_dir: Path, project_id: str, version_id: str | None = None
) -> bool:
    for entry in load_installed_modpacks(game_dir):
        if entry.get("project_id") != project_id:
            continue
        if version_id is None or entry.get("version_id") == version_id:
            return True
    return False


def project_is_installed_modpack(game_dir: Path, project_id: str) -> bool:
    return is_modpack_installed(game_dir, project_id)


def parse_mrpack_profile(mrpack_path: Path) -> dict[str, str]:
    import minecraft_launcher_lib.mrpack as mll_mrpack

    launch_version = mll_mrpack.get_mrpack_launch_version(mrpack_path)
    info = mll_mrpack.get_mrpack_information(mrpack_path)
    mc_version = info.get("minecraftVersion", "")

    loader = "vanilla"
    with __import__("zipfile").ZipFile(mrpack_path, "r") as zf:
        index = json.loads(zf.read("modrinth.index.json"))
        deps = index.get("dependencies") or {}
        if "fabric-loader" in deps:
            loader = "fabric"
        elif "quilt-loader" in deps:
            loader = "quilt"
        elif "neoforge" in deps:
            loader = "neoforge"
        elif "forge" in deps:
            loader = "forge"

    return {
        "mc_version": mc_version,
        "loader": loader,
        "launch_version": launch_version,
        "name": info.get("name", ""),
    }


class ModpackInstallResult:
    __slots__ = (
        "path",
        "project_id",
        "version_id",
        "filename",
        "skipped",
        "profile",
    )

    def __init__(
        self,
        path: Path,
        project_id: str,
        version_id: str,
        *,
        skipped: bool,
        filename: str,
        profile: dict[str, str],
    ) -> None:
        self.path = path
        self.project_id = project_id
        self.version_id = version_id
        self.filename = filename
        self.skipped = skipped
        self.profile = profile


def install_modpack_version(
    version: dict[str, Any],
    *,
    game_dir: Path,
    shared_dir: Path,
    on_progress: Callable[[int, int | None], None] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> ModpackInstallResult:
    import minecraft_launcher_lib.mrpack as mll_mrpack

    file_info = pick_mrpack_file(version)
    if not file_info:
        raise ModrinthError("У этой версии нет файла .mrpack.")

    project_id = version.get("project_id") or ""
    version_id = version.get("id") or ""
    filename = file_info["filename"]
    cache_dir = game_dir / ".launcher" / "mrpacks"
    cache_dir.mkdir(parents=True, exist_ok=True)
    mrpack_path = cache_dir / filename

    if is_modpack_installed(game_dir, project_id, version_id) and mrpack_path.exists():
        profile = parse_mrpack_profile(mrpack_path)
        if on_status:
            on_status(f"Уже установлено: {filename}")
        return ModpackInstallResult(
            mrpack_path,
            project_id,
            version_id,
            skipped=True,
            filename=filename,
            profile=profile,
        )

    if not mrpack_path.exists():
        if on_status:
            on_status(f"Скачивание: {filename}")
        download_file(file_info["url"], mrpack_path, on_progress=on_progress)

    if on_status:
        on_status(f"Установка сборки: {filename}")

    progress_state = {"max": 100, "value": 0}

    def set_max(value: int) -> None:
        progress_state["max"] = max(value, 1)

    def set_progress(value: int) -> None:
        progress_state["value"] = value
        if on_progress:
            on_progress(progress_state["value"], progress_state["max"])

    callback: dict[str, Callable[..., None]] = {
        "setStatus": on_status or (lambda _t: None),
        "setMax": set_max,
        "setProgress": set_progress,
    }

    mll_mrpack.install_mrpack(
        mrpack_path,
        shared_dir,
        modpack_directory=game_dir,
        callback=callback,
    )

    profile = parse_mrpack_profile(mrpack_path)
    entries = [
        e for e in load_installed_modpacks(game_dir) if e.get("project_id") != project_id
    ]
    entries.append(
        {
            "project_id": project_id,
            "version_id": version_id,
            "filename": filename,
            "name": profile.get("name") or filename,
        }
    )
    save_installed_modpacks(game_dir, entries)

    return ModpackInstallResult(
        mrpack_path,
        project_id,
        version_id,
        skipped=False,
        filename=filename,
        profile=profile,
    )
