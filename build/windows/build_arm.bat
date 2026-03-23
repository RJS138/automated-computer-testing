@echo off
REM PC Tester — Windows ARM Build Script
REM
REM Prerequisites:
REM   1. Install UV:  winget install --id=astral-sh.uv  (or https://docs.astral.sh/uv/getting-started/installation/)
REM   2. Run this script on a Windows ARM machine — UV handles everything else automatically.
REM
REM UV will:
REM   - Download and pin the correct Python version (.python-version)
REM   - Create a .venv and install all dependencies + PyInstaller
REM   - Build a single self-contained .exe

setlocal

set APP_NAME=Touchstone (Windows ARM)
set REPO_ROOT=%~dp0..\..
set DIST_DIR=%REPO_ROOT%\dist\windows

echo === Touchstone — Windows ARM Build ===
echo Repo root: %REPO_ROOT%

cd /d "%REPO_ROOT%"

REM Install Python + all deps + PyInstaller into the project venv
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
  --noconsole ^
  --name "%APP_NAME%" ^
  --icon "%REPO_ROOT%\assets\icon.ico" ^
  --distpath "%DIST_DIR%" ^
  --workpath "build\_pyinstaller_work" ^
  --specpath "build\_pyinstaller_spec" ^
  --add-data "%REPO_ROOT%\src\report\templates;src/report/templates" ^
  --add-data "%REPO_ROOT%\src\ui\keyboards;src/ui/keyboards" ^
  --hidden-import psutil ^
  --hidden-import cpuinfo ^
  --hidden-import pySMART ^
  --hidden-import pynvml ^
  --hidden-import GPUtil ^
  --hidden-import wmi ^
  --hidden-import jinja2 ^
  --collect-all PySide6 ^
  --collect-all reportlab ^
  main.py

if %ERRORLEVEL% neq 0 (
    echo BUILD FAILED.
    exit /b 1
)

echo.
echo [3/3] Done.
echo Output: "%DIST_DIR%\%APP_NAME%.exe"

endlocal
