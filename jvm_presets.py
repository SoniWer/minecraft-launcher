"""Готовые пресеты JVM-аргументов."""

from __future__ import annotations

JVM_PRESETS: dict[str, str] = {
    "По умолчанию": "",
    "Fabric / Quilt": (
        "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200"
    ),
    "Forge / NeoForge": "-XX:+UseG1GC -XX:+ParallelRefProcEnabled",
    "Тяжёлые моды": (
        "-XX:+UseG1GC -XX:+ParallelRefProcEnabled "
        "-XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions"
    ),
    "Слабый ПК": "-XX:+UseSerialGC -XX:MaxRAMPercentage=75.0",
}


def preset_names() -> list[str]:
    return [*JVM_PRESETS.keys(), "Свои"]


def preset_args(name: str) -> str:
    return JVM_PRESETS.get(name, "")


def match_preset(jvm_args: str) -> str:
    text = jvm_args.strip()
    for name, args in JVM_PRESETS.items():
        if args.strip() == text:
            return name
    return "Свои" if text else "По умолчанию"
