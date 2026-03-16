"""Visual keyboard diagram widget — keys disappear as they are pressed."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from rich.text import Text
from textual.geometry import Size
from textual.widget import Widget

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

UNIT_CHARS: int = 3  # inner text chars per 1.0 unit of key width

_KEYBOARDS_DIR = Path(__file__).parent.parent / "keyboards"

_LAYOUT_ORDER = ["macbook_us", "tkl_us", "full_us"]

# Maps shifted Textual key names → their unshifted equivalents
_SHIFTED_SYMBOLS: dict[str, str] = {
    "exclamation_mark": "1",
    "at": "2",
    "hash": "3",
    "dollar_sign": "4",
    "percent_sign": "5",
    "caret": "6",
    "ampersand": "7",
    "asterisk": "8",
    "left_parenthesis": "9",
    "right_parenthesis": "0",
    "underscore": "minus",
    "plus": "equal",
    "left_brace": "left_bracket",
    "right_brace": "right_bracket",
    "pipe": "backslash",
    "colon": "semicolon",
    "double_quote": "apostrophe",
    "less_than_sign": "comma",
    "greater_than_sign": "period",
    "question_mark": "slash",
    "tilde": "grave_accent",
}


def normalize_key(key: str) -> str:
    """Normalise a Textual key name to its canonical (unshifted) form."""
    # Uppercase letter → lowercase (shift+letter)
    if len(key) == 1 and key.isupper():
        return key.lower()
    return _SHIFTED_SYMBOLS.get(key, key)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Key:
    id: str
    label: str
    width: float
    all_keys: set[str]  # primary + also names (already normalised)
    capturable: bool = True


@dataclass
class Gap:
    width: float


@dataclass
class Row:
    items: list[Key | Gap]


@dataclass
class KeyboardLayout:
    id: str
    name: str
    rows: list[Row]
    key_map: dict[str, Key]  # key_id → Key
    name_map: dict[str, set[str]]  # normalised_key_name → set[key_id]


# ---------------------------------------------------------------------------
# Layout loading helpers
# ---------------------------------------------------------------------------


def load_layout(path: Path) -> KeyboardLayout:
    tree = ET.parse(path)
    root = tree.getroot()

    kb_id = root.get("id", path.stem)
    kb_name = root.get("name", kb_id)

    rows: list[Row] = []
    key_map: dict[str, Key] = {}
    name_map: dict[str, set[str]] = {}

    for row_el in root.findall("row"):
        items: list[Key | Gap] = []
        for child in row_el:
            if child.tag == "gap":
                items.append(Gap(width=float(child.get("width", "1.0"))))

            elif child.tag == "key":
                key_id = child.get("id", "")
                label = child.get("label", "")
                primary = child.get("key", "")
                width = float(child.get("width", "1.0"))
                capturable = child.get("capturable", "true").lower() != "false"
                also_raw = child.get("also", "")

                all_keys: set[str] = set()
                if primary:
                    all_keys.add(normalize_key(primary))
                for k in (x.strip() for x in also_raw.split(",") if x.strip()):
                    all_keys.add(normalize_key(k))

                key = Key(
                    id=key_id,
                    label=label,
                    width=width,
                    all_keys=all_keys,
                    capturable=capturable,
                )
                items.append(key)
                key_map[key_id] = key

                if capturable:
                    for nk in all_keys:
                        name_map.setdefault(nk, set()).add(key_id)

        rows.append(Row(items=items))

    return KeyboardLayout(id=kb_id, name=kb_name, rows=rows, key_map=key_map, name_map=name_map)


def list_layouts() -> list[tuple[str, str]]:
    """Return [(id, name), …] in preferred display order."""
    result = []
    for lid in _LAYOUT_ORDER:
        path = get_layout_path(lid)
        if not path.exists():
            continue
        try:
            root = ET.parse(path).getroot()
            result.append((lid, root.get("name", lid)))
        except Exception:
            pass
    return result


def get_layout_path(layout_id: str) -> Path:
    return _KEYBOARDS_DIR / f"{layout_id}.xml"


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------


class KeyboardWidget(Widget):
    """Renders a keyboard diagram; keys disappear as they are pressed."""

    can_focus = False

    DEFAULT_CSS = """
    KeyboardWidget {
        height: auto;
        width: auto;
        background: $background;
        padding: 0;
    }
    """

    def __init__(self, layout: KeyboardLayout, **kwargs) -> None:
        super().__init__(**kwargs)
        self._layout: KeyboardLayout = layout
        self._pressed: set[str] = set()  # key_ids that have been pressed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_layout(self, layout: KeyboardLayout) -> None:
        """Hot-swap to a different layout and reset pressed keys."""
        self._layout = layout
        self._pressed = set()
        self.refresh()

    def handle_key(self, key: str) -> bool:
        """
        Attempt to mark *key* as pressed.

        Returns True if at least one new key_id was marked.
        """
        norm = normalize_key(key)
        key_ids = self._layout.name_map.get(norm, set())
        new_hits = key_ids - self._pressed
        if new_hits:
            self._pressed.update(new_hits)
            self.refresh()
            return True
        return False

    @property
    def total_keys(self) -> int:
        """Number of capturable keys in the current layout."""
        return sum(1 for k in self._layout.key_map.values() if k.capturable)

    @property
    def pressed_count(self) -> int:
        return len(self._pressed)

    @property
    def all_pressed(self) -> bool:
        return self.pressed_count >= self.total_keys

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return len(self._layout.rows)

    def render(self) -> Text:
        text = Text(no_wrap=True)

        for row in self._layout.rows:
            for item in row.items:
                inner_w = max(1, round(item.width * UNIT_CHARS))

                if isinstance(item, Gap):
                    # Gap fills the same space as a key of equal width
                    text.append(" " * (inner_w + 3))

                elif isinstance(item, Key):
                    raw = item.label
                    label = raw[:inner_w].center(inner_w) if len(raw) <= inner_w else raw[:inner_w]

                    if not item.capturable:
                        # Shown dimmed; not counted
                        text.append(f"[{label}]", style="dim")
                    elif item.id in self._pressed:
                        # Pressed — invisible (blank space, same width)
                        text.append(" " * (inner_w + 2))
                    else:
                        # Waiting to be pressed — bright
                        text.append(f"[{label}]", style="bold bright_white on rgb(50,80,155)")

                    text.append(" ")  # one-char gap between keys

            text.append("\n")

        return text
