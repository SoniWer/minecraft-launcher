"""Версия лаунчера (совпадает с тегом релиза на GitHub)."""

LAUNCHER_VERSION = "1.6.15"
GITHUB_REPO = "SoniWer/minecraft-launcher"

# Application ID Discord (публичный, не секрет). Rich Presence.
DISCORD_APPLICATION_ID = "1508101710974029895"


def launcher_exe_name(version: str | None = None) -> str:
    v = (version or LAUNCHER_VERSION).lstrip("v")
    return f"MinecraftLauncher-v{v}.exe"
