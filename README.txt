PC TESTER — Portable Hardware Diagnostic Tool
==============================================

RUNNING A PRE-BUILT BINARY (USB Drive)
---------------------------------------
Windows:
  Double-click  win\pctester_x64.exe
  (or pctester_arm64.exe on ARM devices)

Linux:
  chmod +x linux/pctester_x86_64
  ./linux/pctester_x86_64


RUNNING FROM SOURCE (Developers)
----------------------------------
PC Tester uses UV for dependency and environment management.
UV is a single fast binary — no separate Python install needed.

1. Install UV (one-time):
     Windows:   winget install --id=astral-sh.uv
     Linux/Mac: curl -LsSf https://astral.sh/uv/install.sh | sh
     Docs:      https://docs.astral.sh/uv/

2. Clone / copy the project, then from the pc-tester/ directory:

     uv sync                  # creates .venv, installs all deps + correct Python
     uv run pctester          # launch the app

   That's it. UV handles Python version and all packages automatically.

3. Other useful commands:

     uv run python main.py    # alternative launch
     uv add <package>         # add a new dependency (updates pyproject.toml + lockfile)
     uv sync --upgrade        # upgrade all dependencies


BUILDING BINARIES (PyInstaller)
---------------------------------
Binaries must be built natively on the target platform.

Windows (build pctester_x64.exe):
  Run:  build\windows\build.bat
  Requires UV installed (see above). Everything else is automatic.

Linux (build pctester_x86_64 or pctester_aarch64):
  Run:  ./build/linux/build.sh
  Requires UV installed. Auto-detects architecture.

Output lands in dist/windows/ or dist/linux/.
Copy the binary to the matching folder on the USB drive.


WHAT IT TESTS
--------------
  CPU        Model, core count, speed, stress test, peak temperature
  RAM        Capacity, speed, pattern scan (functional check)
  Storage    SMART health, serial numbers, read/write speed
  GPU        Model, VRAM, temperature (NVIDIA/AMD/Intel)
  Network    Adapters, connectivity (ping 8.8.8.8)
  Battery    Health %, design vs current capacity, cycle count
  System     BIOS version, board make/model/serial, OS info
  Manual     Guided LCD, audio, USB, HDMI, keyboard, touchpad checks

Reports (HTML + PDF) are saved to:
  reports/{CustomerName}_{JobNum}_{Date}/

When both a "before" and "after" report exist, a side-by-side
comparison is generated automatically.


NOTES
------
RAM scan:  Userspace pattern check only. For deep hardware faults use MemTest86.
SMART:     Requires smartmontools (smartctl). Bundle with PyInstaller --add-binary
           for fully offline use, or pre-install on the target OS.
Business:  Update BUSINESS_NAME in src/config.py before building.
