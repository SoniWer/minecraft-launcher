# GitHub: репозиторий и автоматические релизы

## Как устроено

- **Ветка `main`** — исходный код (без EXE, без ваших `builds/`).
- **Releases** — готовый `MinecraftLauncher.exe` для скачивания.
- **Actions** — при push в `main` проверяется код; при теге `v1.0.0` собирается EXE и выкладывается в Release.

## Один раз: настройка (5–10 минут)

### 1. Установите Git

[https://git-scm.com/download/win](https://git-scm.com/download/win)

### 2. Установите GitHub CLI

[https://cli.github.com/](https://cli.github.com/)

В PowerShell:

```powershell
gh auth login
```

Выберите GitHub.com → HTTPS → войдите в браузере.

### 3. Создайте репозиторий и залейте код

В папке проекта:

```powershell
cd "C:\Скрипты\minecraft-launcher"
.\scripts\github_setup.ps1
```

Скрипт спросит имя репозитория (по умолчанию `minecraft-launcher`), создаст репозиторий на GitHub, сделает первый push и релиз **v1.0.0** с EXE.

Или вручную:

```powershell
gh repo create minecraft-launcher --public --source=. --remote=origin --push
.\scripts\github_release.ps1 -Version "1.0.0"
```

## Обновление кода (каждый раз после правок)

```powershell
git add .
git commit -m "Описание изменений на русском"
git push
```

Только код — без EXE в репозитории.

## Новый релиз с EXE (для друзей)

После изменений, когда нужен новый EXE:

```powershell
.\scripts\github_release.ps1 -Version "1.0.1"
```

Скрипт создаст тег `v1.0.1`, GitHub Actions соберёт EXE и добавит в Releases (1–3 минуты).

Статус сборки: вкладка **Actions** на GitHub.

## Без скрипта (вручную)

```powershell
git tag v1.0.1
git push origin v1.0.1
```

Workflow **«Релиз с EXE»** запустится автоматически.

## Описание репозитория на GitHub

На сайте: **Settings** → в поле **Description**:

> Лаунчер Minecraft Java Edition: сборки, Modrinth, Java, офлайн. Скачать EXE — в Releases.

**Topics:** `minecraft`, `launcher`, `fabric`, `modrinth`, `python`
