"""QDialog helper dialogs for manual tests.

Each dialog is launched via dialog.run() (blocking), then the caller
reads dialog.result_str which is "pass", "fail", or "skip".
"""

from ._utils import make_dialog_btn
from .display_dialog import DisplayDialog
from .hdmi_dialog import HdmiDialog
from .keyboard_dialog import KeyboardDialog
from .speakers_dialog import SpeakersDialog
from .touchpad_dialog import TouchpadDialog
from .usb_dialog import UsbDialog
from .webcam_dialog import WebcamDialog

__all__ = [
    "DisplayDialog",
    "HdmiDialog",
    "KeyboardDialog",
    "SpeakersDialog",
    "TouchpadDialog",
    "UsbDialog",
    "WebcamDialog",
    "make_dialog_btn",
]
