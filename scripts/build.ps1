# Build a one-file windowed Auralis.exe
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

pip install pyinstaller
pyinstaller --onefile --windowed --name Auralis `
    --collect-all pystray `
    auralis/__main__.py

Write-Host "Done: dist/Auralis.exe"
