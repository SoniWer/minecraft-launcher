# Сборка MinecraftLauncher.exe в папке проекта
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Minecraft Launcher EXE build ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "[1/4] Dependencies..."
python -m pip install -r requirements.txt -q
python -m pip install pyinstaller pillow -q

Write-Host "[2/4] Icon..."
python make_icon.py

Write-Host "[3/4] Import check..."
python -c "from deps_check import require_dependencies; require_dependencies(offer_install=False); import launcher; print('OK')"

if (Test-Path "MinecraftLauncher.exe") {
    Remove-Item "MinecraftLauncher.exe" -Force
}

Write-Host "[4/4] PyInstaller..."
python -m PyInstaller MinecraftLauncher.spec --noconfirm --distpath . --workpath build/pyinstaller-work

if (-not (Test-Path "MinecraftLauncher.exe")) {
    Write-Host "Error: EXE was not created." -ForegroundColor Red
    exit 1
}

$sizeMb = [math]::Round((Get-Item "MinecraftLauncher.exe").Length / 1MB, 1)
Write-Host ""
Write-Host "Done: $PSScriptRoot\MinecraftLauncher.exe (${sizeMb} MiB)" -ForegroundColor Green
Write-Host "Data folders builds/, backups/, settings.json are created on first run."
