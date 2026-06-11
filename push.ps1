param(
    [string]$Message = "",
    [string]$Remote = "origin",
    [string]$Branch = ""
)

$ErrorActionPreference = "Stop"

function Write-Step($Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

if (-not (Test-Path ".git")) {
    Write-Error "Folder ini bukan Git repository. Jalankan script dari root project mgx."
}

if ([string]::IsNullOrWhiteSpace($Branch)) {
    $Branch = (git branch --show-current).Trim()
}

if ([string]::IsNullOrWhiteSpace($Branch)) {
    Write-Error "Tidak bisa membaca branch aktif."
}

Write-Step "Repository status"
git status --short

if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = Read-Host "Commit message"
}

if ([string]::IsNullOrWhiteSpace($Message)) {
    Write-Error "Commit message wajib diisi."
}

Write-Step "Staging changes"
git add -A

$staged = git diff --cached --name-only
if ([string]::IsNullOrWhiteSpace(($staged -join ""))) {
    Write-Host "Tidak ada perubahan untuk di-commit." -ForegroundColor Yellow
} else {
    Write-Step "Committing"
    git commit -m $Message
}

Write-Step "Pushing to $Remote/$Branch"
git push $Remote $Branch

Write-Step "Done"
git status --short
