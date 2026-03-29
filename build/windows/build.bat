@echo off
REM PC Tester — Windows Build Script
REM
REM Prerequisites:
REM   1. Install UV:  winget install --id=astral-sh.uv  (or https://docs.astral.sh/uv/getting-started/installation/)
REM   2. Run this script — UV handles everything else automatically.
REM
REM UV will:
REM   - Download and pin the correct Python version (.python-version)
REM   - Create a .venv and install all dependencies + PyInstaller
REM   - Build a single self-contained .exe

setlocal

set APP_NAME=Touchstone (Windows x64)
set REPO_ROOT=%~dp0..\..
set DIST_DIR=%REPO_ROOT%\dist\windows
set SENSOR_DUMP_SRC=%REPO_ROOT%\tools\windows\sensor_dump
set SENSOR_DUMP_OUT=%SENSOR_DUMP_SRC%\publish\x64
set SMARTCTL_DIR=%REPO_ROOT%\tools\windows\smartctl
set SMARTCTL_BIN=%SMARTCTL_DIR%\smartctl.exe

echo === Touchstone — Windows Build ===
echo Repo root: %REPO_ROOT%

cd /d "%REPO_ROOT%"

REM Install Python + all deps + PyInstaller into the project venv
echo.
echo [1/4] Syncing dependencies (uv sync --group build)...
uv sync --group build
if %ERRORLEVEL% neq 0 (
    echo ERROR: uv sync failed. Is UV installed?
    echo Install UV: winget install --id=astral-sh.uv
    exit /b 1
)

REM Locate smartctl.exe — bundled copy takes priority, then PATH
REM smartmontools is GPL v2 (https://www.smartmontools.org) — free to bundle.
REM In CI: the workflow installs smartmontools via choco and copies smartctl.exe here.
REM Locally: if smartmontools is installed, the script copies it automatically.
echo.
echo [2/5] Locating smartctl.exe (smartmontools, GPL v2)...
if not exist "%SMARTCTL_DIR%" mkdir "%SMARTCTL_DIR%"
if exist "%SMARTCTL_BIN%" (
    echo   Found pre-staged smartctl.exe in tools\windows\smartctl\
) else (
    where smartctl.exe >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        for /f "delims=" %%P in ('where smartctl.exe') do (
            copy "%%P" "%SMARTCTL_BIN%" >nul
            echo   Copied smartctl.exe from %%P
            goto :smartctl_ok
        )
    )
    echo   WARNING: smartctl.exe not found. SMART drive health data will be unavailable.
    echo            Install smartmontools: winget install -e --id smartmontools.smartmontools
    set SMARTCTL_BIN=
)
:smartctl_ok

REM Build SensorDump.exe — LibreHardwareMonitor sensor bridge (MIT)
echo.
echo [3/5] Building SensorDump.exe (LibreHardwareMonitor bridge)...
dotnet publish "%SENSOR_DUMP_SRC%\SensorDump.csproj" ^
  -c Release ^
  -r win-x64 ^
  --self-contained true ^
  -p:PublishSingleFile=true ^
  -p:PublishTrimmed=true ^
  -o "%SENSOR_DUMP_OUT%"
if %ERRORLEVEL% neq 0 (
    echo WARNING: SensorDump build failed. Continuing without bundled sensor tool.
    echo          Install .NET 6 SDK: https://dotnet.microsoft.com/download
    set SENSOR_DUMP_OUT=
)

echo.
echo [4/5] Running PyInstaller...
if defined SENSOR_DUMP_OUT (
    set SENSOR_DUMP_ARG=--add-data "%SENSOR_DUMP_OUT%\SensorDump.exe;tools/windows"
) else (
    set SENSOR_DUMP_ARG=
)
if defined SMARTCTL_BIN (
    set SMARTCTL_ARG=--add-data "%SMARTCTL_BIN%;."
) else (
    set SMARTCTL_ARG=
)

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
  %SENSOR_DUMP_ARG% ^
  %SMARTCTL_ARG% ^
  --hidden-import psutil ^
  --hidden-import cpuinfo ^
  --hidden-import pySMART ^
  --hidden-import pynvml ^
  --hidden-import GPUtil ^
  --hidden-import wmi ^
  --hidden-import jinja2 ^
  --collect-all PySide6 ^
  --collect-all reportlab ^
  --collect-all cv2 ^
  --collect-submodules src.tests ^
  --collect-submodules src.ui ^
  --collect-submodules src.report ^
  --collect-submodules src.models ^
  --collect-submodules src.utils ^
  main.py

if %ERRORLEVEL% neq 0 (
    echo BUILD FAILED.
    exit /b 1
)

echo.
echo [5/5] Done.
echo Output: "%DIST_DIR%\%APP_NAME%.exe"

endlocal
