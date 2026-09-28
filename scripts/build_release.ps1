$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path '.venv')) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip build wheel
& .\.venv\Scripts\python.exe -m pip install -r .\requirements\runtime.txt
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\python.exe -m build

Write-Host "Build concluído. Artefatos em: $root\dist"
