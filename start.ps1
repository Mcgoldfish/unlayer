$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$stemPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $stemPython)) { throw 'Install the isolated Python environment first. See README.md.' }
Start-Process -FilePath $stemPython -ArgumentList 'backend.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
node server.cjs
