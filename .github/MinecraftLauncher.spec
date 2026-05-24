# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parent

_release_notes = root / ".github" / "RELEASE_NOTES.md"
_discord_app_json = root / "discord_app.json"
datas: list = []
if _release_notes.is_file():
    datas.append((str(_release_notes), "."))
if _discord_app_json.is_file():
    datas.append((str(_discord_app_json), "."))
binaries: list = []
icon_file = str(root / "launcher.ico") if (root / "launcher.ico").is_file() else None

hiddenimports = [
    "sv_ttk",
    "windnd",
    "auto_backup",
    "drag_drop",
    "play_time",
    "version_sort",
    "builds",
    "loaders",
    "build_backup",
    "deps_check",
    "extras_ui",
    "game_logs",
    "game_process",
    "java_download",
    "java_manager",
    "jvm_args",
    "jvm_presets",
    "modrinth",
    "modrinth_ui",
    "pack_manager_ui",
    "install_status",
    "changelog",
    "mod_duplicates",
    "mod_updates_ui",
    "play_stats_ui",
    "crash_reports_ui",
    "discord_presence",
    "pypresence",
    "prelaunch_check",
    "ram_advisor",
    "settings",
    "theme",
    "tooltips",
    "ui_async",
    "version_manager",
    "version",
    "launcher_update",
    "launcher_log",
    "disk_check",
    "game_log_collector",
    "build_dialog",
    "splash_screen",
    "ui_assets",
    "modrinth_icons",
    "ui_layout",
    "ui_focus",
]

tmp_ret = collect_all("minecraft_launcher_lib")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

a = Analysis(
    [str(root / "launcher.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MinecraftLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    distpath=str(root),
    icon=icon_file,
)
