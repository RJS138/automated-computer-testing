# Touchstone — Windows Data Source Diagnostic
# Run this on the target Windows machine to verify all data sources
# used by the app and inspect their raw output format.
#
# Usage (run as Administrator):
#   powershell -ExecutionPolicy Bypass -File debug_windows_data.ps1

$ErrorActionPreference = 'SilentlyContinue'
$sep = "=" * 60

function Show-Section($title) {
    Write-Host ""
    Write-Host $sep -ForegroundColor Cyan
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host $sep -ForegroundColor Cyan
}

function Show-Raw($label, $value) {
    $display = if ($null -eq $value -or $value -eq "") { "<null/empty>" } else { $value }
    Write-Host ("  {0,-35} {1}" -f "$label:", $display)
}

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "1. BIOS / Board / Chassis  (Win32_BIOS, Win32_BaseBoard, Win32_ComputerSystem)"
# ─────────────────────────────────────────────────────────────────────────────
$bios  = Get-CimInstance Win32_BIOS
$board = Get-CimInstance Win32_BaseBoard
$cs    = Get-CimInstance Win32_ComputerSystem

Show-Raw "bios.Manufacturer"          $bios.Manufacturer
Show-Raw "bios.SMBIOSBIOSVersion"     $bios.SMBIOSBIOSVersion
Show-Raw "bios.ReleaseDate (raw)"     $bios.ReleaseDate
Show-Raw "bios.ReleaseDate (fmt)"     $(if ($bios.ReleaseDate) { $bios.ReleaseDate.ToString("yyyy-MM-dd") })
Show-Raw "bios.SerialNumber"          $bios.SerialNumber
Show-Raw "board.Manufacturer"         $board.Manufacturer
Show-Raw "board.Product"              $board.Product
Show-Raw "board.SerialNumber"         $board.SerialNumber
Show-Raw "cs.Manufacturer"            $cs.Manufacturer
Show-Raw "cs.Model"                   $cs.Model

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "2. Operating System  (Win32_OperatingSystem)"
# ─────────────────────────────────────────────────────────────────────────────
$os = Get-CimInstance Win32_OperatingSystem
Show-Raw "os.Caption"                 $os.Caption
Show-Raw "os.Version"                 $os.Version
Show-Raw "os.BuildNumber"             $os.BuildNumber

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "3. CPU  (Win32_Processor)"
# ─────────────────────────────────────────────────────────────────────────────
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Show-Raw "cpu.Name"                   $cpu.Name
Show-Raw "cpu.NumberOfCores"          $cpu.NumberOfCores
Show-Raw "cpu.NumberOfLogicalProcs"   $cpu.NumberOfLogicalProcessors

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "4. RAM  (Win32_PhysicalMemory — summed)"
# ─────────────────────────────────────────────────────────────────────────────
$ramBytes = (Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum
Show-Raw "Total RAM bytes"            $ramBytes
Show-Raw "Total RAM (GB)"            $(if ($ramBytes) { "$([math]::Round($ramBytes / 1GB, 0)) GB" })

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "5. GPU(s)  (Win32_VideoController)"
# ─────────────────────────────────────────────────────────────────────────────
$gpus = Get-CimInstance Win32_VideoController
if ($gpus) {
    $i = 0
    foreach ($g in $gpus) {
        $i++
        Show-Raw "gpu[$i].Name"        $g.Name
        Show-Raw "gpu[$i].AdapterRAM"  $g.AdapterRAM
    }
} else {
    Write-Host "  <no GPU instances returned>" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "6. Storage  (Win32_DiskDrive)"
# ─────────────────────────────────────────────────────────────────────────────
$disks = Get-CimInstance Win32_DiskDrive
if ($disks) {
    $i = 0
    foreach ($d in $disks) {
        $i++
        Show-Raw "disk[$i].Model"   $d.Model
        Show-Raw "disk[$i].Size"    $d.Size
        Show-Raw "disk[$i].Caption" $d.Caption
    }
} else {
    Write-Host "  <no disk instances returned>" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "7. Battery basic  (Win32_Battery)"
# ─────────────────────────────────────────────────────────────────────────────
$bat = Get-CimInstance Win32_Battery | Select-Object -First 1
if ($bat) {
    Show-Raw "bat.DesignCapacity"       $bat.DesignCapacity
    Show-Raw "bat.FullChargeCapacity"   $bat.FullChargeCapacity
    Show-Raw "bat.Chemistry"            $bat.Chemistry
    Show-Raw "bat.EstimatedChargeRemaining" $bat.EstimatedChargeRemaining
} else {
    Write-Host "  <no battery detected — desktop or unrecognised>" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "8. Battery detailed  (root/wmi — BatteryFullChargedCapacity)"
# ─────────────────────────────────────────────────────────────────────────────
$fc = Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity | Select-Object -First 1
if ($fc) {
    Show-Raw "fc.FullChargedCapacity"   $fc.FullChargedCapacity
    Show-Raw "fc (all props)"           ($fc | Format-List | Out-String).Trim()
} else {
    Write-Host "  <BatteryFullChargedCapacity not available>" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "9. Battery cycle count  (root/wmi — BatteryCycleCount)"
# ─────────────────────────────────────────────────────────────────────────────
$cc = Get-CimInstance -Namespace root/wmi -ClassName BatteryCycleCount | Select-Object -First 1
if ($cc) {
    Show-Raw "cc.CycleCount"            $cc.CycleCount
    Show-Raw "cc (all props)"           ($cc | Format-List | Out-String).Trim()
} else {
    Write-Host "  <BatteryCycleCount not available>" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "10. CPU Temperature  (root/wmi — MSAcpi_ThermalZoneTemperature)"
# ─────────────────────────────────────────────────────────────────────────────
$zones = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature
if ($zones) {
    foreach ($z in $zones) {
        $raw   = $z.CurrentTemperature
        $degC  = if ($raw) { [math]::Round($raw / 10.0 - 273.15, 1) } else { $null }
        $name  = $z.InstanceName
        Show-Raw "zone '$name' raw"     $raw
        Show-Raw "zone '$name' °C"      $degC
    }
} else {
    Write-Host "  <no thermal zones returned>" -ForegroundColor Yellow
}

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "11. Full JSON payload  (what the app would send)"
# ─────────────────────────────────────────────────────────────────────────────
$payload = [PSCustomObject]@{
    bios_vendor          = $bios.Manufacturer
    bios_version         = $bios.SMBIOSBIOSVersion
    bios_date            = if ($bios.ReleaseDate) { $bios.ReleaseDate.ToString("yyyy-MM-dd") } else { $null }
    board_serial         = $bios.SerialNumber
    board_manufacturer   = $board.Manufacturer
    board_model          = $board.Product
    board_serial2        = $board.SerialNumber
    chassis_manufacturer = $cs.Manufacturer
    chassis_model        = $cs.Model
    os_name              = $os.Caption
    os_version           = $os.Version
    os_build             = $os.BuildNumber
    cpu_name             = if ($cpu.Name) { $cpu.Name.Trim() } else { $null }
    cpu_cores            = $cpu.NumberOfCores
    cpu_threads          = $cpu.NumberOfLogicalProcessors
    ram_bytes            = $ramBytes
    gpu_list             = @($gpus | Where-Object { $_.Name } | ForEach-Object {
        $n = $_.Name.Trim()
        $v = $_.AdapterRAM
        if ($v -and [long]$v -gt 0) { "$n ($([math]::Round([long]$v/1GB,0)) GB VRAM)" } else { $n }
    })
    disk_list            = @($disks | ForEach-Object {
        $m = if ($_.Model) { $_.Model.Trim() } else { $_.Caption }
        $s = if ($_.Size) { " · $([math]::Round([long]$_.Size/1GB,0)) GB" } else { "" }
        "$m$s"
    })
}

Write-Host ""
$payload | ConvertTo-Json -Depth 3

# ─────────────────────────────────────────────────────────────────────────────
Show-Section "12. wmic fallback check  (wmic bios get ...)"
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "  Testing wmic CLI availability..."
$wmicTest = wmic bios get Manufacturer /format:list 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  wmic is available. Sample output:" -ForegroundColor Green
    $wmicTest | Where-Object { $_ -match '\S' } | ForEach-Object { Write-Host "    $_" }
} else {
    Write-Host "  wmic returned exit code $LASTEXITCODE" -ForegroundColor Yellow
    Write-Host "  (wmic is deprecated in Windows 11 24H2+ but usually still present)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host $sep -ForegroundColor Green
Write-Host "  Diagnostic complete. Paste output above into the issue." -ForegroundColor Green
Write-Host $sep -ForegroundColor Green
Write-Host ""
