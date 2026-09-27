$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create the Python environment first. See README.md, Local setup.'
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) {
    throw 'Build the frontend first. See README.md, Local setup.'
}
& $pythonPath -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 --limit-concurrency 32
exit $LASTEXITCODE
