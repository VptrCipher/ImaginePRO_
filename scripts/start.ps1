param([switch]$Install, [switch]$Build)
$ErrorActionPreference = 'Stop'
$editorRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $editorRoot
try {
    $editorPython = Join-Path $editorRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $editorPython)) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
        $Install = $true
    }
    if ($Install) {
        & $editorPython -m pip install --timeout 180 -r requirements-app.txt
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
        Push-Location frontend
        try {
            npm.cmd ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        } finally { Pop-Location }
        Push-Location backend/framecraft
        try {
            npm.cmd ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'Framecraft dependency installation failed (Node 22.12+ required).' }
        } finally { Pop-Location }
        $Build = $true
    }
    if ($Build -or -not (Test-Path -LiteralPath 'frontend\out\index.html')) {
        Push-Location frontend
        try {
            npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
        } finally { Pop-Location }
    }
    Write-Host 'ImaginePro: http://127.0.0.1:8765'
    Write-Host 'Keep this window open while using the editor. Ctrl+C stops the server.'
    & $editorPython -X utf8 -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --no-access-log
} finally { Pop-Location }
