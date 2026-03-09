"""
Hardware threshold database — "in spec" ranges backed by manufacturer specs.

Key points encoded here:
  • Intel mobile H/HX TjMax = 100 °C — 95-100 °C under load is WITHIN SPEC.
  • AMD Zen 4 designed to run continuously at 95 °C TjMax — this is normal.
  • AMD RDNA junction temp up to 110 °C is AMD-documented as within spec.
  • NVMe PCIe 4 controllers run hot; Gen is inferred from measured speed.
  • Battery health: Apple's own "Service Battery" threshold is 80 %.
"""

from __future__ import annotations

import re

# ===========================================================================
# CPU
# ===========================================================================

# Format per family:
#   idle_warn  — flag WARN if idle temp exceeds this
#   load_warn  — flag WARN if stress temp exceeds this (but still within spec)
#   fail       — flag FAIL if stress temp exceeds this (truly outside spec)
#   tjmax      — manufacturer's throttle/shutdown point (informational)
#   note       — displayed in report when temp is between load_warn and fail
_CPU_DB: dict[str, dict] = {
    # Intel desktop 10th–14th gen (TjMax 100 °C)
    "intel_desktop_10_14": {
        "idle_warn": 60,
        "load_warn": 85,
        "fail": 100,
        "tjmax": 100,
        "note": None,
    },
    # Intel mobile H/HX 10th–14th gen (TjMax 100 °C — high temps ARE normal)
    "intel_mobile_h": {
        "idle_warn": 65,
        "load_warn": 95,
        "fail": 100,
        "tjmax": 100,
        "note": "Intel mobile H/HX CPUs are designed to operate at 95–100 °C "
        "under sustained load (TjMax = 100 °C). This is within spec.",
    },
    # Intel mobile P/U (low-power, TjMax 100 °C)
    "intel_mobile_u": {
        "idle_warn": 60,
        "load_warn": 90,
        "fail": 100,
        "tjmax": 100,
        "note": "Intel mobile P/U CPUs run up to 90–100 °C under full load (TjMax = 100 °C).",
    },
    # Intel Core Ultra / Arrow Lake (TjMax 105 °C)
    "intel_core_ultra": {
        "idle_warn": 65,
        "load_warn": 95,
        "fail": 105,
        "tjmax": 105,
        "note": "Intel Core Ultra (Arrow/Meteor Lake) TjMax = 105 °C. "
        "Temperatures up to 95 °C under load are within spec.",
    },
    # Intel Celeron / Pentium N/J series (TjMax 105 °C, low power)
    "intel_celeron_n": {
        "idle_warn": 65,
        "load_warn": 85,
        "fail": 100,
        "tjmax": 105,
        "note": None,
    },
    # Intel Xeon (TjMax 100–110 °C depending on model)
    "intel_xeon": {
        "idle_warn": 60,
        "load_warn": 85,
        "fail": 100,
        "tjmax": 100,
        "note": None,
    },
    # AMD Ryzen Zen 2 / Zen 3 (3000 / 5000 series, TjMax ~95 °C)
    "amd_zen2_zen3": {
        "idle_warn": 60,
        "load_warn": 85,
        "fail": 95,
        "tjmax": 95,
        "note": None,
    },
    # AMD Ryzen Zen 4 (7000 series) — AMD designed this to sustain 95 °C
    "amd_zen4": {
        "idle_warn": 65,  # Zen 4 genuinely idles warmer than Zen 3
        "load_warn": 95,
        "fail": 105,  # Above TjMax — unreachable in practice; WARN at 95 °C is correct
        "tjmax": 95,
        "note": "AMD Ryzen 7000 (Zen 4) is designed to run at 95 °C continuously "
        "— AMD explicitly documented this. Temperatures at 95 °C under "
        "load are within spec and expected.",
    },
    # AMD Ryzen Zen 5 (9000 series) — same TjMax, ~7 °C cooler in practice
    "amd_zen5": {
        "idle_warn": 60,
        "load_warn": 92,
        "fail": 95,
        "tjmax": 95,
        "note": "AMD Ryzen 9000 (Zen 5) TjMax = 95 °C. Temperatures up to 92 °C under load are within spec.",
    },
    # Apple M-series with fan (MacBook Pro, Mac Mini, Mac Studio)
    "apple_m_fanned": {
        "idle_warn": 60,
        "load_warn": 90,
        "fail": 100,
        "tjmax": 100,  # unofficial; empirical
        "note": "Apple M-series SoC — fanned models sustain 70–90 °C under load.",
    },
    # Apple M-series fanless (MacBook Air) — throttles rather than cools
    "apple_m_fanless": {
        "idle_warn": 65,
        "load_warn": 100,
        "fail": 110,
        "tjmax": 110,  # unofficial; empirical (Air hits 107–114 °C in stress tests)
        "note": "MacBook Air (fanless) sustains 95–107 °C under heavy load by "
        "design — no fan means the SoC throttles at the thermal limit.",
    },
    # Generic fallback
    "unknown": {
        "idle_warn": 65,
        "load_warn": 85,
        "fail": 100,
        "tjmax": 100,
        "note": None,
    },
}


def detect_cpu_family(brand: str, platform_sys: str, has_battery: bool) -> str:
    """
    Infer CPU threshold family from the brand string, platform, and battery presence.

    Priority: Apple → Xeon → Core Ultra → Celeron/Pentium → Ryzen (gen) → Intel Core.
    Mobile vs desktop for Intel Core: battery presence or Darwin + x86 = mobile.
    """
    b = brand.lower()

    if "apple m" in b:
        return "apple_m_fanned"  # caller can override to apple_m_fanless if no fan

    if "xeon" in b:
        return "intel_xeon"

    if "core ultra" in b:
        return "intel_core_ultra"

    if "celeron" in b or ("pentium" in b and re.search(r"\b[nj]\d{4}", b)):
        return "intel_celeron_n"

    if "ryzen" in b:
        m = re.search(r"(\d{4,5})", b)
        if m:
            num = int(m.group(1))
            if num >= 9000:
                return "amd_zen5"
            if num >= 7000:
                return "amd_zen4"
        return "amd_zen2_zen3"

    if "intel" in b and ("core" in b or "i3" in b or "i5" in b or "i7" in b or "i9" in b):
        # Detect mobile suffix (H, HX, HK, P, U at end of model number)
        is_mobile = has_battery or platform_sys == "Darwin" or bool(re.search(r"\d{4,5}[HhPpUu]", brand))
        if is_mobile:
            # H/HX suffix → high-power mobile; P/U → low-power mobile
            if re.search(r"\d{4,5}[HhXxKk]", brand):
                return "intel_mobile_h"
            return "intel_mobile_u"
        return "intel_desktop_10_14"

    return "unknown"


def get_cpu_thresholds(
    brand: str,
    platform_sys: str,
    has_battery: bool,
    is_fanless: bool = False,
) -> dict:
    """Return the threshold dict for this CPU, with family key attached."""
    family = detect_cpu_family(brand, platform_sys, has_battery)
    if family == "apple_m_fanned" and is_fanless:
        family = "apple_m_fanless"
    result = dict(_CPU_DB[family])
    result["family"] = family
    return result


# ===========================================================================
# GPU
# ===========================================================================

_GPU_DB: dict[str, dict] = {
    "nvidia_geforce": {
        "idle_warn": 50,
        "load_warn": 85,
        "fail": 95,
        "note": "NVIDIA GeForce throttles around 83–85 °C core. "
        "Sustained temps above 90 °C core may indicate cooling issues.",
    },
    "nvidia_professional": {
        "idle_warn": 50,
        "load_warn": 80,
        "fail": 90,
        "note": None,
    },
    # AMD RDNA: junction (hotspot) up to 110 °C is AMD-documented as within spec
    "amd_rdna": {
        "idle_warn": 55,
        "load_warn": 85,
        "fail": 100,
        "note": "AMD RDNA GPUs: junction (hotspot) temperature up to 110 °C is "
        "within AMD specification. Edge (core) temperature is reported here.",
    },
    "amd_pro": {
        "idle_warn": 50,
        "load_warn": 85,
        "fail": 95,
        "note": None,
    },
    "intel_arc": {
        "idle_warn": 55,
        "load_warn": 85,
        "fail": 100,
        "note": None,
    },
    "apple_silicon": {
        "idle_warn": 55,
        "load_warn": 90,
        "fail": 105,
        "note": "Apple Silicon GPU shares the SoC die; temperature reflects combined load.",
    },
    "unknown": {
        "idle_warn": 55,
        "load_warn": 85,
        "fail": 95,
        "note": None,
    },
}


def get_gpu_thresholds(vendor: str, name: str) -> dict:
    """Return GPU thresholds based on vendor/name strings."""
    v = vendor.lower()
    n = name.lower()

    if v == "apple" or "apple" in n:
        return dict(_GPU_DB["apple_silicon"])
    if v == "nvidia" or "nvidia" in n:
        if "quadro" in n or "rtx" in n and "a" in n[:10]:
            return dict(_GPU_DB["nvidia_professional"])
        return dict(_GPU_DB["nvidia_geforce"])
    if v in ("amd", "ati") or "radeon" in n or "amd" in n:
        if "pro" in n and "rdna" not in n:
            return dict(_GPU_DB["amd_pro"])
        return dict(_GPU_DB["amd_rdna"])
    if v == "intel" or "intel" in n or "arc" in n:
        return dict(_GPU_DB["intel_arc"])
    return dict(_GPU_DB["unknown"])


# ===========================================================================
# Storage — temperature
# ===========================================================================

_STORAGE_TEMP_DB: dict[str, dict] = {
    "sata_ssd": {
        "warn": 60,
        "fail": 70,
        "note": "NAND data-retention risk accelerates significantly above 60 °C.",
    },
    "nvme_pcie3": {
        "warn": 65,
        "fail": 75,
        "note": None,
    },
    "nvme_pcie4": {
        "warn": 70,
        "fail": 80,
        "note": "PCIe 4.0 NVMe controllers run hot under sustained I/O; a heatsink is strongly recommended.",
    },
    "nvme_pcie5": {
        "warn": 75,
        "fail": 85,
        "note": "PCIe 5.0 NVMe drives require active heatsinks.",
    },
    "hdd": {
        "warn": 50,
        "fail": 60,
        "note": "Backblaze data shows elevated failure rates for HDDs above 45 °C sustained.",
    },
    "unknown": {
        "warn": 65,
        "fail": 75,
        "note": None,
    },
}


# ===========================================================================
# Storage — speed (sequential read / write MB/s)
# ===========================================================================

_STORAGE_SPEED_DB: dict[str, dict] = {
    "hdd_5400": {
        "expected_read": 100,
        "warn_read": 60,
        "fail_read": 40,
        "expected_write": 100,
        "warn_write": 50,
        "fail_write": 35,
    },
    "hdd_7200": {
        "expected_read": 130,
        "warn_read": 80,
        "fail_read": 50,
        "expected_write": 120,
        "warn_write": 70,
        "fail_write": 45,
    },
    "sata_ssd": {
        "expected_read": 500,
        "warn_read": 350,
        "fail_read": 150,
        "expected_write": 450,
        "warn_write": 250,
        "fail_write": 100,
    },
    # NOTE: thresholds below reflect filesystem-level sequential IO (tempfile + fsync),
    # NOT raw disk benchmarks. macOS reads use F_NOCACHE; writes are fsynced to disk.
    # Raw speeds (CrystalDiskMark-style) are typically 2–4× higher.
    "nvme_pcie3": {
        "expected_read": 2000,
        "warn_read": 600,
        "fail_read": 200,
        "expected_write": 1500,
        "warn_write": 300,
        "fail_write": 100,
    },
    "nvme_pcie4": {
        "expected_read": 4000,
        "warn_read": 1200,
        "fail_read": 400,
        "expected_write": 3000,
        "warn_write": 600,
        "fail_write": 200,
    },
    "nvme_pcie5": {
        "expected_read": 7000,
        "warn_read": 2000,
        "fail_read": 700,
        "expected_write": 5000,
        "warn_write": 1200,
        "fail_write": 400,
    },
    "usb": {
        "expected_read": 400,
        "warn_read": 20,
        "fail_read": 5,
        "expected_write": 200,
        "warn_write": 10,
        "fail_write": 3,
    },
}


def _infer_nvme_gen(read_mb_s: float | None) -> str:
    """
    Infer PCIe generation from measured sequential read speed.
    Used when we can't query the link speed directly.
    """
    if read_mb_s is None:
        return "nvme_pcie3"  # conservative default
    if read_mb_s > 7000:
        return "nvme_pcie5"
    if read_mb_s > 3500:
        return "nvme_pcie4"
    return "nvme_pcie3"


def get_storage_thresholds(
    interface: str,
    medium_type: str,
    measured_read_mb_s: float | None = None,
) -> tuple[dict, dict]:
    """
    Return (temp_thresholds, speed_thresholds) for a drive.

    interface   : "NVMe", "SATA", "USB", "Unknown", etc.
    medium_type : "SSD", "HDD", "Unknown"
    measured_read_mb_s : if supplied, used to infer NVMe PCIe generation
    """
    iface = (interface or "").upper()
    mtype = (medium_type or "").upper()

    if "NVME" in iface or "NVM" in iface:
        gen_key = _infer_nvme_gen(measured_read_mb_s)
        temp_key = gen_key.replace("nvme_", "nvme_")  # same key space
        return dict(_STORAGE_TEMP_DB.get(temp_key, _STORAGE_TEMP_DB["nvme_pcie3"])), dict(
            _STORAGE_SPEED_DB.get(gen_key, _STORAGE_SPEED_DB["nvme_pcie3"])
        )

    if "USB" in iface:
        return dict(_STORAGE_TEMP_DB["unknown"]), dict(_STORAGE_SPEED_DB["usb"])

    if "SSD" in mtype:
        return dict(_STORAGE_TEMP_DB["sata_ssd"]), dict(_STORAGE_SPEED_DB["sata_ssd"])

    if "HDD" in mtype or "ROTATING" in mtype:
        return dict(_STORAGE_TEMP_DB["hdd"]), dict(_STORAGE_SPEED_DB["hdd_7200"])

    # Unknown — moderate defaults
    return dict(_STORAGE_TEMP_DB["unknown"]), dict(_STORAGE_SPEED_DB["sata_ssd"])


# ===========================================================================
# Battery
# ===========================================================================

BATTERY_HEALTH_GOOD = 80  # >= 80 %: PASS  (matches Apple's "Service Battery" line)
BATTERY_HEALTH_WARN = 70  # 70–79 %: WARN "Replace soon"
BATTERY_HEALTH_FAIL = 70  # < 70 %: FAIL   (same cutoff — below WARN = FAIL)

# Cycle count warn/fail — keyed by platform hint
_BATTERY_CYCLE_DB: dict[str, dict] = {
    "apple_modern": {"warn": 800, "fail": 1000},  # 1 000-cycle rated
    "apple_legacy": {"warn": 240, "fail": 300},  # 300-cycle rated
    "windows_std": {"warn": 300, "fail": 500},
    "windows_premium": {"warn": 500, "fail": 800},
    "unknown": {"warn": 400, "fail": 600},
}


def get_battery_cycle_thresholds(platform_sys: str, brand: str = "") -> dict:
    """Return battery cycle thresholds appropriate for the detected platform."""
    if platform_sys == "Darwin":
        # Modern Apple Silicon or Intel Macs 2016+ → 1000-cycle rated
        return dict(_BATTERY_CYCLE_DB["apple_modern"])
    if "thinkpad" in brand.lower() or "xps" in brand.lower():
        return dict(_BATTERY_CYCLE_DB["windows_premium"])
    if platform_sys == "Windows":
        return dict(_BATTERY_CYCLE_DB["windows_std"])
    return dict(_BATTERY_CYCLE_DB["unknown"])
