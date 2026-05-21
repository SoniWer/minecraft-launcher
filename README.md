# Minecraft Launcher

Лаунчер **Minecraft Java Edition** на Python: отдельные сборки с модами, Modrinth, выбор Java, офлайн-никнейм.

> **Скачать готовый лаунчер (Windows):** откройте [**Releases**](https://github.com/SoniWer/minecraft-launcher/releases) → последний релиз → **`MinecraftLauncher.exe`**.  
> Подробная инструкция для игроков: [docs/УСТАНОВКА.md](docs/УСТАНОВКА.md)

---

## Возможности

- **Сборки** — изолированные моды, миры и конфиг (`builds/.../game/`)
- **Загрузчики** — Vanilla, Fabric, Forge, NeoForge, Quilt
- **Modrinth** — моды, modpack, текстуры, шейдеры
- **Менеджер модов** — список, обновления Modrinth, «Обновить все»
- **Java** — автоподбор, подсказки, скачивание Temurin
- **Проверка перед запуском** — Java, ОЗУ, моды, crash-report
- **JVM** — пресеты и свои аргументы
- **Экспорт / импорт** сборки (ZIP)
- **Автобэкап** перед modpack и массовым обновлением модов
- **Перетаскивание .jar** на окно (Windows)
- **Избранные версии MC** (★)
- **Время в игре** по каждой сборке
- **Тёмная / светлая тема**

---

## Быстрый старт (разработка)

```powershell
git clone https://github.com/SoniWer/minecraft-launcher.git
cd minecraft-launcher
pip install -r requirements.txt
python launcher.py
```

При первом запуске лаунчер проверит библиотеки и предложит установить их через pip.

---

## Сборка EXE локально

```powershell
.\build_exe.ps1
```

EXE появится в папке проекта. В git он **не попадает** — только в [Releases](docs/GITHUB.md).

---

## Публикация на GitHub

| Действие | Команда |
|----------|---------|
| Первый раз (репозиторий + релиз v1.0.0) | `.\scripts\github_setup.ps1` |
| Новый релиз с EXE | `.\scripts\github_release.ps1 -Version "1.0.1"` |
| Только обновить код | `git add .` → `git commit` → `git push` |

Подробно: [docs/GITHUB.md](docs/GITHUB.md)

**Автоматизация:** GitHub Actions собирает EXE при теге `v*` и прикрепляет к Release.

---

## Версии Java

| Minecraft      | Java |
|----------------|------|
| 1.16 и ниже    | 8    |
| 1.17 – 1.20.4  | 17   |
| 1.20.5+        | 21   |

---

## Документация

| Файл | Для кого |
|------|----------|
| [docs/УСТАНОВКА.md](docs/УСТАНОВКА.md) | Игроки (EXE из Releases) |
| [docs/РАЗРАБОТКА.md](docs/РАЗРАБОТКА.md) | Разработчики |
| [docs/GITHUB.md](docs/GITHUB.md) | Репозиторий и релизы |

---

## Структура данных (рядом с EXE)

| Папка / файл | Описание |
|--------------|----------|
| `builds/` | Сборки (создаётся автоматически) |
| `backups/` | Автобэкапы ZIP |
| `java/` | Скачанная Java (опционально) |
| `settings.json` | Настройки лаунчера |

---

## Примечания

- Офлайн-никнейм (без аккаунта Microsoft).
- Версии Minecraft ставятся в стандартную папку `.minecraft` (как у других лаунчеров).
- Лаунчер не связан с Mojang/Microsoft.

## Лицензия

Проект для личного использования. Minecraft — торговая марка Mojang/Microsoft.
