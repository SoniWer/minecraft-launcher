"""Версия лаунчера (совпадает с тегом релиза на GitHub)."""

LAUNCHER_VERSION = "1.4.8"
GITHUB_REPO = "SoniWer/minecraft-launcher"


def launcher_exe_name(version: str | None = None) -> str:
    v = (version or LAUNCHER_VERSION).lstrip("v")
    return f"MinecraftLauncher-v{v}.exe"
