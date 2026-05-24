"""Версия лаунчера (совпадает с тегом релиза на GitHub)."""

LAUNCHER_VERSION = "1.6.2"
GITHUB_REPO = "SoniWer/minecraft-launcher"

# Запасной Application ID Discord (публичный). Обычно используется discord_application_id.txt.
DISCORD_APPLICATION_ID = ""


def launcher_exe_name(version: str | None = None) -> str:
    v = (version or LAUNCHER_VERSION).lstrip("v")
    return f"MinecraftLauncher-v{v}.exe"
