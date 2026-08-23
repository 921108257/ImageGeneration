$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3 -m venv .venv
}
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".venv\Scripts\python.exe" scripts\setup.py
& ".venv\Scripts\python.exe" -m unittest discover -s tests -q
Write-Host "Local setup complete. Start with: .\scripts\start.ps1"
