#Requires -RunAsAdministrator
<#
.SYNOPSIS
    PC Tester — USB Setup Script (Windows)

.DESCRIPTION
    Installs Ventoy on a USB drive, then downloads the latest PC Tester
    executables from GitHub Releases and copies them onto the drive.

.PARAMETER Update
    Skip Ventoy install and only refresh the executables on an existing
    Ventoy drive.

.EXAMPLE
    # Full setup (run PowerShell as Administrator)
    .\scripts\create_usb.ps1

    # Just update executables on an existing drive
    .\scripts\create_usb.ps1 -Update
#>

param(
    [switch]$Update
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Configuration ─────────────────────────────────────────────────────────────
# Auto-detect from git remote; update the fallback if running as a standalone download.
try {
    $raw = git -C "$PSScriptRoot\.." remote get-url origin 2>$null
    $GithubRepo = $raw -replace '.*github\.com[:/]', '' -replace '\.git$', '' -replace '\s', ''
} catch { $GithubRepo = $null }
if (-not $GithubRepo) { $GithubRepo = "RJS138/touchstone" }

$UsbMarker  = "touchstone_usb.marker"
$ReportsDir = "reports"

# ── Helpers ───────────────────────────────────────────────────────────────────
function Write-Step  { param($Msg) Write-Host "`n$Msg" -ForegroundColor White }
function Write-Info  { param($Msg) Write-Host "   -> $Msg" -ForegroundColor Cyan }
function Write-Ok    { param($Msg) Write-Host "   OK $Msg" -ForegroundColor Green }
function Write-Warn  { param($Msg) Write-Host "   !! $Msg" -ForegroundColor Yellow }
function Fail        { param($Msg) Write-Host "`nERROR: $Msg`n" -ForegroundColor Red; exit 1 }

function Get-GitHubLatestTag {
    param([string]$Repo)
    $api = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -UseBasicParsing
    return $api.tag_name -replace '^v', ''
}

function Invoke-Download {
    # Silent download for small metadata files (SHA256SUMS, hash files, API responses)
    param([string]$Url, [string]$Dest)
    $ProgressPreference = 'SilentlyContinue'
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
        return $true
    } catch {
        return $false
    }
}

function Invoke-DownloadWithProgress {
    # Download with a visible progress bar for large binaries.
    # Prefers curl.exe (ships with Windows 10 1803+) for a clean bar;
    # falls back to Invoke-WebRequest with PowerShell's native progress display.
    param([string]$Url, [string]$Dest)
    $curlExe = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curlExe) {
        & curl.exe -fSL --progress-bar $Url -o $Dest
        return $LASTEXITCODE -eq 0
    } else {
        # Fallback: PowerShell native progress (slower rendering, but visible)
        try {
            $ProgressPreference = 'Continue'
            Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
            return $true
        } catch {
            return $false
        }
    }
}

function Get-ExpectedHash {
    param([string]$SumsFile, [string]$FileName)
    if (-not (Test-Path $SumsFile)) { return $null }
    $line = Get-Content $SumsFile | Where-Object { $_ -match "\s$([regex]::Escape($FileName))$" } | Select-Object -First 1
    if ($line) { return ($line -split '\s+')[0] }
    return $null
}

function Confirm-FileHash {
    param([string]$FilePath, [string]$FileName, [string]$SumsFile)
    if (-not (Test-Path $FilePath)) { return }  # file was skipped
    $expected = Get-ExpectedHash -SumsFile $SumsFile -FileName $FileName
    if (-not $expected) {
        Write-Warn "No checksum entry for $FileName — skipping verification."
        return
    }
    $actual = (Get-FileHash -Path $FilePath -Algorithm SHA256).Hash.ToLower()
    if ($actual -eq $expected.ToLower()) {
        Write-Ok "Checksum OK: $FileName"
    } else {
        Remove-Item -Path $FilePath -Force -ErrorAction SilentlyContinue
        Fail "Checksum MISMATCH for $FileName — file removed. Possible tampering detected.`n  Expected: $expected`n  Got:      $actual"
    }
}

# ── Banner ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Touchstone - USB Setup" -ForegroundColor White
Write-Host "  Repo : $GithubRepo"

$TmpDir = Join-Path $env:TEMP "pctester_usb_setup_$(Get-Random)"
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
try {

# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — Select USB disk
# ═════════════════════════════════════════════════════════════════════════════
Write-Step "[1/5] Select USB drive"
Write-Host ""

$usbDisks = @(Get-Disk | Where-Object { $_.BusType -eq 'USB' -and $_.Size -gt 0 })

if ($usbDisks.Count -eq 0) {
    Fail "No USB disks detected. Insert the USB drive and try again."
}

Write-Host "   Disk#  Size        Model" -ForegroundColor Gray
foreach ($d in $usbDisks) {
    $sizeGb = [math]::Round($d.Size / 1GB, 1)
    Write-Host ("   {0,-6}{1,-12}{2}" -f $d.Number, "${sizeGb} GB", $d.FriendlyName)
}

Write-Host ""
$diskNum = Read-Host "  Enter Disk number (e.g. 2)"
$diskNum = $diskNum.Trim()
$targetDisk = Get-Disk -Number $diskNum -ErrorAction SilentlyContinue
if (-not $targetDisk) { Fail "Disk $diskNum not found." }
if ($targetDisk.BusType -ne 'USB') {
    $ans = Read-Host "  Disk $diskNum is NOT a USB disk ($($targetDisk.BusType)). Continue anyway? (yes/no)"
    if ($ans -ne 'yes') { Write-Host "Aborted."; exit 0 }
}

# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — Confirm (full install only)
# ═════════════════════════════════════════════════════════════════════════════
if (-not $Update) {
    Write-Host ""
    $sizeGb = [math]::Round($targetDisk.Size / 1GB, 1)
    Write-Host "  WARNING: ALL data on Disk $diskNum will be permanently erased!" -ForegroundColor Red
    Write-Host "    Disk $diskNum — $sizeGb GB — $($targetDisk.FriendlyName)" -ForegroundColor Gray
    Write-Host ""
    $confirm = Read-Host "  Type YES (all caps) to continue"
    if ($confirm -ne 'YES') { Write-Host "  Aborted."; exit 0 }
}

# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — Ventoy install (or locate existing drive)
# ═════════════════════════════════════════════════════════════════════════════
$VentoyDrive = $null

if (-not $Update) {
    Write-Step "[2/5] Installing Ventoy"

    Write-Info "Fetching latest Ventoy version..."
    try {
        $VentoyVer = Get-GitHubLatestTag "ventoy/ventoy"
    } catch {
        Fail "Could not reach GitHub API. Check network connection."
    }
    Write-Info "Latest Ventoy: v$VentoyVer"

    $ventoyZipUrl = "https://github.com/ventoy/ventoy/releases/download/v${VentoyVer}/ventoy-${VentoyVer}-windows.zip"
    $ventoyZip    = Join-Path $TmpDir "ventoy.zip"
    $ventoyExtDir = Join-Path $TmpDir "ventoy"

    Write-Info "Downloading Ventoy..."
    if (-not (Invoke-DownloadWithProgress $ventoyZipUrl $ventoyZip)) {
        Fail "Failed to download Ventoy from $ventoyZipUrl"
    }

    # Verify Ventoy archive integrity against its published SHA-256
    Write-Info "Verifying Ventoy checksum..."
    $ventoyHashUrl = "https://github.com/ventoy/ventoy/releases/download/v${VentoyVer}/ventoy-${VentoyVer}-windows.zip.sha256"
    $ventoyHashFile = Join-Path $TmpDir "ventoy.zip.sha256"
    if (Invoke-Download $ventoyHashUrl $ventoyHashFile) {
        $ventoyExpected = ((Get-Content $ventoyHashFile) -split '\s+')[0].ToLower()
        $ventoyActual   = (Get-FileHash -Path $ventoyZip -Algorithm SHA256).Hash.ToLower()
        if ($ventoyActual -ne $ventoyExpected) {
            Fail "Ventoy checksum MISMATCH — download may be corrupted or tampered with.`n  Expected: $ventoyExpected`n  Got:      $ventoyActual"
        }
        Write-Ok "Ventoy checksum verified."
    } else {
        Write-Warn "Ventoy checksum file not available for v${VentoyVer} — skipping verification."
    }

    Write-Info "Extracting Ventoy..."
    Expand-Archive -Path $ventoyZip -DestinationPath $ventoyExtDir -Force
    $ventoyExe = Get-ChildItem -Path $ventoyExtDir -Recurse -Filter "Ventoy2Disk.exe" |
                    Select-Object -First 1
    if (-not $ventoyExe) { Fail "Ventoy2Disk.exe not found in downloaded archive." }

    Write-Info "Installing Ventoy on Disk $diskNum (this may take 20-60 seconds)..."
    # -I = force install (no interactive confirmation), targets physical drive by number
    $physDrive = "\\.\PhysicalDrive$diskNum"
    $proc = Start-Process -FilePath $ventoyExe.FullName `
                -ArgumentList "-I", $physDrive `
                -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 0) {
        Fail "Ventoy installation failed (exit code $($proc.ExitCode)). Try running Ventoy2Disk.exe manually."
    }
    Write-Ok "Ventoy installed."

    # Wait for Windows to mount the new VENTOY volume
    Write-Info "Waiting for VENTOY partition to mount..."
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        $vol = Get-Volume -FileSystemLabel "VENTOY" -ErrorAction SilentlyContinue
        if ($vol) { $VentoyDrive = "$($vol.DriveLetter):"; break }
        Start-Sleep -Seconds 1
    }
    if (-not $VentoyDrive) {
        # Offer a manual fallback
        Write-Warn "VENTOY volume not auto-detected. It may need a moment."
        Write-Host ""
        $VentoyDrive = Read-Host "  Enter the VENTOY drive letter (e.g. E)"
        $VentoyDrive = $VentoyDrive.TrimEnd(':').ToUpper() + ":"
    }

} else {
    Write-Step "[2/5] Locating VENTOY drive"
    $vol = Get-Volume -FileSystemLabel "VENTOY" -ErrorAction SilentlyContinue
    if ($vol) {
        $VentoyDrive = "$($vol.DriveLetter):"
    } else {
        $VentoyDrive = Read-Host "  VENTOY drive not found automatically. Enter drive letter (e.g. E)"
        $VentoyDrive = $VentoyDrive.TrimEnd(':').ToUpper() + ":"
    }
}

if (-not (Test-Path $VentoyDrive)) { Fail "Drive $VentoyDrive not accessible." }
Write-Ok "VENTOY drive: $VentoyDrive"

# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — Download executables
# ═════════════════════════════════════════════════════════════════════════════
Write-Step "[3/5] Downloading latest PC Tester release"
Write-Info "Source: https://github.com/$GithubRepo/releases/latest"

$BaseUrl = "https://github.com/$GithubRepo/releases/latest/download"

$dirs = @("$VentoyDrive\windows", "$VentoyDrive\linux", "$VentoyDrive\macos", "$VentoyDrive\$ReportsDir")
foreach ($d in $dirs) { New-Item -ItemType Directory -Path $d -Force | Out-Null }

# Download the checksum manifest first — all binary downloads are verified against it.
Write-Info "Downloading SHA256SUMS..."
$SumsFile = Join-Path $TmpDir "SHA256SUMS"
if (-not (Invoke-Download "$BaseUrl/SHA256SUMS" $SumsFile)) {
    Fail "Could not download SHA256SUMS from release. Cannot verify file integrity."
}
Write-Ok "SHA256SUMS downloaded."

$assets = @(
    @{ Name = "touchstone_windows_x64.exe"; Dest = "$VentoyDrive\windows\touchstone_windows_x64.exe" },
    @{ Name = "touchstone_windows_arm64.exe"; Dest = "$VentoyDrive\windows\touchstone_windows_arm64.exe" },
    @{ Name = "touchstone_linux_x86_64";    Dest = "$VentoyDrive\linux\touchstone_linux_x86_64"      },
    @{ Name = "touchstone_linux_arm64";     Dest = "$VentoyDrive\linux\touchstone_linux_arm64"       },
    @{ Name = "touchstone_macos_arm64.dmg"; Dest = "$VentoyDrive\macos\touchstone_macos_arm64.dmg"   }
)

foreach ($a in $assets) {
    Write-Info "Downloading $($a.Name)..."
    if (Invoke-DownloadWithProgress "$BaseUrl/$($a.Name)" $a.Dest) {
        Confirm-FileHash -FilePath $a.Dest -FileName $a.Name -SumsFile $SumsFile
    } else {
        Write-Warn "$($a.Name) not found in latest release (skipped)."
    }
}

# ═════════════════════════════════════════════════════════════════════════════
# STEP 5 — Marker + README
# ═════════════════════════════════════════════════════════════════════════════
Write-Step "[4/5] Writing marker and README"

New-Item -ItemType File -Path "$VentoyDrive\$UsbMarker" -Force | Out-Null

@"
Touchstone USB Drive
===================

WINDOWS
  Run: windows\touchstone_windows_x64.exe
  Right-click -> "Run as Administrator"

MACOS (Apple Silicon / M-series)
  Run: macos/touchstone_macos_arm64
  First run - remove quarantine flag:
    xattr -d com.apple.quarantine macos/touchstone_macos_arm64

MACOS (Intel)
  Use macos/touchstone_macos_arm64 - runs via Rosetta 2 automatically.

LINUX
  Run: linux/touchstone_linux_x86_64  (requires sudo)

Reports are saved automatically to the reports/ folder on this drive.
To update executables: run scripts\create_usb.ps1 -Update
"@ | Out-File -FilePath "$VentoyDrive\README.txt" -Encoding utf8

Write-Ok "Marker and README written."

# ═════════════════════════════════════════════════════════════════════════════
# STEP 6 — Done
# ═════════════════════════════════════════════════════════════════════════════
Write-Step "[5/5] Done"
Write-Host ""
Write-Host "  USB drive is ready at $VentoyDrive" -ForegroundColor Green
Write-Host "  Safely eject the drive before unplugging." -ForegroundColor Gray
Write-Host ""

} finally {
    Remove-Item -Path $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
}
