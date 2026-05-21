# First-time: GitHub repo + release v1.0.0 with EXE (requires: gh auth login)
param(
    [string]$RepoName = "minecraft-launcher",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public",
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Write-Host "Install Git"; exit 1 }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Write-Host "Install GitHub CLI"; exit 1 }

gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "Run: gh auth login"; exit 1 }

if (-not (Test-Path ".git")) {
    git init
    git branch -M main
}

$owner = gh api user -q .login
git config user.name $owner
git config user.email "$owner@users.noreply.github.com"

git add .
$prevEa = $ErrorActionPreference
$ErrorActionPreference = "Continue"
git rev-parse --verify HEAD *>$null
$hasHead = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prevEa
if (-not $hasHead) {
    git commit -m "Initial commit: Minecraft Launcher"
} elseif (git status --porcelain) {
    git commit -m "Update before GitHub publish"
}

$fullName = "$owner/$RepoName"
Write-Host "Creating repo: $fullName"

$prevEa = $ErrorActionPreference
$ErrorActionPreference = "Continue"
git remote get-url origin *>$null
$hasRemote = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prevEa
if (-not $hasRemote) {
    gh repo create $RepoName --$Visibility --source=. --remote=origin `
        --description "Minecraft Java Edition launcher. Download EXE from Releases." --push
} else {
    git push -u origin main
}

$readme = Get-Content "README.md" -Raw -Encoding UTF8
$readme = $readme -replace "ВАШ_НИК", $owner
[System.IO.File]::WriteAllText("$Root\README.md", $readme)
git add README.md
git diff --cached --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    git commit -m "README: repo links"
}
git push origin main 2>$null

Write-Host "Repo: https://github.com/$fullName"
& "$Root\scripts\github_release.ps1" -Version $Version
Write-Host "Done. Releases: https://github.com/$fullName/releases"
