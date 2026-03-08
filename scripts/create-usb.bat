@echo off
:: PC Tester — USB Population Script (Windows)
::
:: Populates a Ventoy-formatted USB drive with all platform binaries and the live ISO.
:: Missing files produce warnings only — the USB can be populated incrementally.
::
:: Prerequisites:
::   Ventoy installed on the target USB drive (https://www.ventoy.net)
::   The USB drive volume label must be "Ventoy"
::
:: Usage:
::   scripts\create-usb.bat

setlocal EnableDelayedExpansion

:: Resolve repo root (one level up from this script)
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.."
set "REPO_ROOT=%CD%"
popd

echo === PC Tester - USB Population (Windows) ===
echo Repo root : %REPO_ROOT%

:: --- Find Ventoy drive by volume label ---
set "VENTOY_DRIVE="
for /f "tokens=1,2" %%A in ('wmic logicaldisk get DeviceID^,VolumeName 2^>nul') do (
    if /i "%%B"=="Ventoy" set "VENTOY_DRIVE=%%A"
)

if not defined VENTOY_DRIVE (
    echo.
    echo ERROR: Ventoy USB not found. No drive with volume label "Ventoy" detected.
    echo.
    echo To set up a Ventoy USB drive:
    echo   1. Download Ventoy from https://www.ventoy.net/en/download.html
    echo   2. Run Ventoy2Disk.exe and select your USB drive
    echo   3. Click "Install" -- this will format and set up the drive
    echo   4. The USB will appear with the label "Ventoy" once ready
    echo   5. Re-run this script
    exit /b 1
)

echo Target    : %VENTOY_DRIVE%\

set WARN_COUNT=0

echo.
echo [1/7] Creating folder structure on USB...
for %%D in (win linux macos iso reports) do (
    if not exist "%VENTOY_DRIVE%\%%D\" mkdir "%VENTOY_DRIVE%\%%D"
)
echo   Folders: win\ linux\ macos\ iso\ reports\

echo.
echo [2/7] Copying Windows binaries...
set "WIN_SRC=%REPO_ROOT%\dist\windows"
if exist "%WIN_SRC%\*.exe" (
    copy /Y "%WIN_SRC%\*.exe" "%VENTOY_DRIVE%\win\" >nul
    echo   Copied Windows binaries to win\
) else (
    echo   WARNING: No Windows binaries found in dist\windows\. Run scripts\build-windows.bat.
    set /a WARN_COUNT+=1
)

echo.
echo [3/7] Copying Linux binaries...
set "LINUX_SRC=%REPO_ROOT%\dist\linux"
if exist "%LINUX_SRC%\pctester_*" (
    copy /Y "%LINUX_SRC%\pctester_*" "%VENTOY_DRIVE%\linux\" >nul
    echo   Copied Linux binaries to linux\
) else (
    echo   WARNING: No Linux binaries found in dist\linux\. Run scripts\build-linux.sh on a Linux machine.
    set /a WARN_COUNT+=1
)

echo.
echo [4/7] Copying macOS binaries...
set "MAC_SRC=%REPO_ROOT%\dist\macos"
if exist "%MAC_SRC%\pctester_*" (
    copy /Y "%MAC_SRC%\pctester_*" "%VENTOY_DRIVE%\macos\" >nul
    echo   Copied macOS binaries to macos\
) else (
    echo   WARNING: No macOS binaries found in dist\macos\. Run scripts\build-macos.sh on macOS and copy results into this repo.
    set /a WARN_COUNT+=1
)

echo.
echo [5/7] Copying live ISO...
set "ISO_SRC=%REPO_ROOT%\dist\iso\pctester-live.iso"
if exist "%ISO_SRC%" (
    copy /Y "%ISO_SRC%" "%VENTOY_DRIVE%\iso\pctester-live.iso" >nul
    echo   Copied: iso\pctester-live.iso
    echo   (The ISO will appear in the Ventoy boot menu automatically)
) else (
    echo   WARNING: Live ISO not found at dist\iso\pctester-live.iso. Run scripts\build-iso.sh to build it.
    set /a WARN_COUNT+=1
)

echo.
echo [6/7] Writing marker file and README...

:: Marker file used by the app to detect it is running from USB
type nul > "%VENTOY_DRIVE%\pctester_usb.marker"

(
echo PC Tester -- USB Drive
echo ======================
echo.
echo This USB drive contains diagnostic tools for PC repair technicians.
echo.
echo CONTENTS
echo --------
echo win\         Windows executables (x64, arm64)
echo linux\       Linux binaries (x86_64)
echo macos\       macOS binaries (x86_64, arm64)
echo iso\         Bootable live ISO (boot via Ventoy menu)
echo reports\     Saved diagnostic reports
echo.
echo HOW TO USE
echo ----------
echo Windows:
echo   1. Plug in the USB drive.
echo   2. Open win\ and run the appropriate .exe for your architecture.
echo   3. Reports are saved automatically to the reports\ folder on this drive.
echo.
echo Linux (installed OS):
echo   1. Plug in the USB drive.
echo   2. Open a terminal and run: chmod +x /path/to/linux/pctester_x86_64
echo   3. Run: /path/to/linux/pctester_x86_64
echo.
echo macOS:
echo   1. Plug in the USB drive.
echo   2. Open macos\ and run the binary that matches your architecture ^(x86_64 or arm64^).
echo   3. If macOS blocks it, you may need to remove the quarantine attribute:
echo        xattr -d com.apple.quarantine X:\macos\pctester_*
echo.
echo Bootable ^(for machines that can't boot their own OS^):
echo   1. Plug in the USB drive and boot from it ^(F12 / Del / F2 for boot menu^).
echo   2. The Ventoy boot menu will appear -- select pctester-live.iso.
echo   3. The PC Tester app launches automatically. No login required.
echo   4. Reports are saved to the reports\ folder on this USB drive.
echo.
echo VENTOY
echo ------
echo This drive uses Ventoy for bootable ISO support.
echo To add more ISOs, simply copy them to the iso\ folder.
echo Learn more at https://www.ventoy.net
) > "%VENTOY_DRIVE%\README.txt"

echo   Written: pctester_usb.marker
echo   Written: README.txt

echo.
echo [7/7] Summary
echo   USB path  : %VENTOY_DRIVE%\
echo   Warnings  : %WARN_COUNT%

if %WARN_COUNT% gtr 0 (
    echo.
    echo   Some files are missing (see warnings above).
    echo   The USB can be used now and updated incrementally as builds are added.
) else (
    echo.
    echo   All files copied successfully. USB is ready.
)

echo.
echo Safely eject the USB drive before unplugging it.

endlocal
