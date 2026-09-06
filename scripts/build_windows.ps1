# Build Utter.exe (+ optional installer) on Windows.
#   .\scripts\build_windows.ps1            -> dist\Utter\Utter.exe
#   .\scripts\build_windows.ps1 -Installer -> also dist\Utter-<ver>-Setup.exe (needs Inno Setup 6, `iscc` on PATH)
param(
    [switch]$Installer
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

python -m pytest -q tests

if (Test-Path dist\Utter) { Remove-Item -Recurse -Force dist\Utter }
pyinstaller --noconfirm --clean packaging\utter.spec

$version = (python -c "import sys; sys.path.insert(0,'src'); import utter; print(utter.__version__)").Trim()
Write-Host "Built dist\Utter\Utter.exe (v$version)"

if ($Installer) {
    iscc /DMyAppVersion=$version packaging\installer.iss
    Write-Host "Installer: dist\Utter-$version-Setup.exe"
}
