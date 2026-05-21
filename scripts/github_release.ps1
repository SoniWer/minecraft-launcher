# New release: tag vX.Y.Z -> GitHub Actions builds EXE
param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { exit 1 }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { exit 1 }
gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "Run: gh auth login"; exit 1 }

$tag = "v$Version"
if ($tag -notmatch '^v\d+\.\d+\.\d+') {
    Write-Host "Use version like 1.0.0"
    exit 1
}

git add -A
if (git status --porcelain) {
    git commit -m "Prepare release $tag"
}

git push origin main 2>$null
if ($LASTEXITCODE -ne 0) { git push -u origin main }

git tag -a $tag -m "Release $tag"
git push origin $tag

Write-Host "Tag $tag pushed. Wait 1-3 min for Actions to build EXE."
$origin = git remote get-url origin 2>$null
if ($origin -match 'github\.com[:/](.+?)(?:\.git)?$') {
    $repo = $Matches[1]
    Write-Host "Actions: https://github.com/$repo/actions"
    Write-Host "Release: https://github.com/$repo/releases/tag/$tag"
}
