@echo off
:: PC Tester — Windows Build Script
::
:: Prerequisites:
::   Install UV:  winget install --id=astral-sh.uv
::                   OR
::               powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
::
:: UV handles Python and all Python dependencies automatically.
:: PDF generation uses ReportLab (pure Python — no system libraries needed).
:: Run this script from any directory; it locates the repo root automatically.

setlocal EnableDelayedExpansion

:: Resolve repo root (one level up from this script's directory)
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.."
set "REPO_ROOT=%CD%"
popd

:: Detect architecture
set "ARCH=x64"
if "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "ARCH=arm64"
if "%PROCESSOR_ARCHITEW6432%"=="ARM64" set "ARCH=arm64"

set "APP_NAME=pctester_%ARCH%.exe"
set "DIST_DIR=%REPO_ROOT%\dist\windows"

echo === PC Tester - Windows Build ===
echo Repo root : %REPO_ROOT%
echo Arch      : %ARCH%
echo Output    : %DIST_DIR%\%APP_NAME%

cd /d "%REPO_ROOT%"

echo.
echo [1/3] Syncing dependencies (uv sync --group build)...
uv sync --group build
if %ERRORLEVEL% neq 0 (
    echo ERROR: uv sync failed. Is UV installed?
    echo Install UV: winget install --id=astral-sh.uv
    exit /b 1
)

echo.
echo [2/3] Running PyInstaller...
uv run pyinstaller ^
  --onefile ^
  --name "%APP_NAME%" ^
  --distpath "%DIST_DIR%" ^
  --workpath ".pyinstaller\work" ^
  --specpath ".pyinstaller\spec" ^
  --add-data "src\report\templates;src/report/templates" ^
  --hidden-import textual ^
  --hidden-import psutil ^
  --hidden-import cpuinfo ^
  --hidden-import pySMART ^
  --hidden-import pynvml ^
  --hidden-import GPUtil ^
  --hidden-import jinja2 ^
  --hidden-import reportlab ^
  --collect-all textual ^
  --collect-all reportlab ^
  main.py
if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

echo.
echo [3/3] Done.
echo Output : %DIST_DIR%\%APP_NAME%
echo Copy to USB drive at: win\%APP_NAME%

endlocal
