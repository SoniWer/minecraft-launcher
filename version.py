"""Версия лаунчера (совпадает с тегом релиза на GitHub)."""

LAUNCHER_VERSION = "1.4.3"
GITHUB_REPO = "SoniWer/minecraft-launcher"


def launcher_exe_name() -> str:
    return f"MinecraftLauncher-v{LAUNCHER_VERSION}.exe"
