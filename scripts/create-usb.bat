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
set WIN_COUNT=0
if exist "%WIN_SRC%\PC Tester*.exe" (
    for %%F in ("%WIN_SRC%\PC Tester*.exe") do (
        copy /Y "%%F" "%VENTOY_DRIVE%\win\" >nul
        echo   Copied: win\%%~nxF
        set /a WIN_COUNT+=1
    )
)
if %WIN_COUNT% equ 0 (
    echo   WARNING: No Windows binaries found in dist\windows\. Run scripts\build-windows.bat.
    set /a WARN_COUNT+=1
)

echo.
echo [3/7] Copying Linux binaries...
set "LINUX_SRC=%REPO_ROOT%\dist\linux"
set LINUX_COUNT=0
if exist "%LINUX_SRC%\PC Tester (Linux*" (
    for %%F in ("%LINUX_SRC%\PC Tester (Linux*") do (
        copy /Y "%%F" "%VENTOY_DRIVE%\linux\" >nul
        echo   Copied: linux\%%~nxF
        set /a LINUX_COUNT+=1
    )
)
if %LINUX_COUNT% equ 0 (
    echo   WARNING: No Linux binaries found in dist\linux\. Run scripts\build-linux.sh on a Linux machine.
    set /a WARN_COUNT+=1
)

echo.
echo [4/7] Copying macOS binaries...
set "MAC_SRC=%REPO_ROOT%\dist\macos"
set MAC_COUNT=0
for %%N in ("PC Tester (Apple Silicon)" "PC Tester (Intel)") do (
    if exist "%MAC_SRC%\%%~N" (
        copy /Y "%MAC_SRC%\%%~N" "%VENTOY_DRIVE%\macos\" >nul
        echo   Copied: macos\%%~N
        set /a MAC_COUNT+=1
    )
)
if %MAC_COUNT% equ 0 (
    echo   WARNING: No macOS binaries found in dist\macos\. Run build-macos.sh and/or build-macos-intel.sh on a Mac.
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
echo win\     Windows executables
echo            PC Tester (Windows x64).exe
echo            PC Tester (Windows ARM64).exe
echo linux\   Linux binaries
echo            PC Tester (Linux x86_64)
echo            PC Tester (Linux ARM64)
echo macos\   macOS binaries
echo            PC Tester (Apple Silicon)
echo            PC Tester (Intel)
echo iso\     Bootable live ISO (boot via Ventoy menu)
echo reports\ Saved diagnostic reports
echo.
echo HOW TO USE
echo ----------
echo Windows:
echo   1. Plug in the USB drive.
echo   2. Open win\ and run "PC Tester (Windows x64).exe"
echo      (or "PC Tester (Windows ARM64).exe" for ARM devices).
echo   3. Reports are saved automatically to the reports\ folder on this drive.
echo.
echo Linux (installed OS):
echo   1. Plug in the USB drive.
echo   2. Open a terminal, navigate to the linux\ folder on the USB drive.
echo   3. Run:  chmod +x "PC Tester (Linux x86_64)"
echo            ./"PC Tester (Linux x86_64)"
echo.
echo macOS:
echo   1. Plug in the USB drive.
echo   2. Open macos\ and run "PC Tester (Apple Silicon)" or "PC Tester (Intel)".
echo   3. If macOS blocks it, right-click the file and choose Open.
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
