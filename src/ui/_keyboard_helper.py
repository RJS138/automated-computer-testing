"""
Full-screen tkinter keyboard test — run as a subprocess by KeyboardTestScreen.

Loads the same XML layout files used by the Textual KeyboardWidget so the
displayed diagram is identical.  All keys are captured via tkinter's native
<KeyPress> binding, including modifiers (Shift, Ctrl, Alt, Cmd) that the
terminal intercepts before the app can see them.

Exit codes:
  0  — Done clicked (all keys registered, or user satisfied)
  1  — Exit Early clicked / window closed without completing
  2  — tkinter not available or no display server
"""

import sys
import platform
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

_KEYBOARDS_DIR = Path(__file__).parent / "keyboards"
_LAYOUT_ORDER = ["macbook_us", "tkl_us", "full_us"]

# ── Tkinter keysym → normalised layout key name ────────────────────────────
# Tk keysym names (e.g. "bracketleft") as returned by event.keysym.

_KEYSYM_MAP: dict[str, str] = {
    "Escape":        "escape",
    **{f"F{i}": f"f{i}" for i in range(1, 13)},
    "grave":         "grave_accent",
    "asciitilde":    "tilde",
    "exclam":        "exclamation_mark",
    "at":            "at",
    "numbersign":    "hash",
    "dollar":        "dollar_sign",
    "percent":       "percent_sign",
    "asciicircum":   "caret",
    "ampersand":     "ampersand",
    "asterisk":      "asterisk",
    "parenleft":     "left_parenthesis",
    "parenright":    "right_parenthesis",
    "minus":         "minus",
    "underscore":    "underscore",
    "equal":         "equal",
    "plus":          "plus",
    "BackSpace":     "backspace",
    "Delete":        "delete",
    "Tab":           "tab",
    "ISO_Left_Tab":  "tab",   # Shift+Tab on Linux/macOS
    "bracketleft":   "left_bracket",
    "bracketright":  "right_bracket",
    "braceleft":     "left_brace",
    "braceright":    "right_brace",
    "backslash":     "backslash",
    "bar":           "pipe",
    "Caps_Lock":     "caps_lock",
    "semicolon":     "semicolon",
    "colon":         "colon",
    "apostrophe":    "apostrophe",
    "quotedbl":      "double_quote",
    "Return":        "enter",
    "KP_Enter":      "enter",
    "Shift_L":       "shift",
    "Shift_R":       "shift",
    "comma":         "comma",
    "less":          "less_than_sign",
    "period":        "period",
    "greater":       "greater_than_sign",
    "slash":         "slash",
    "question":      "question_mark",
    "Control_L":     "ctrl",
    "Control_R":     "ctrl",
    "Alt_L":         "alt",
    "Alt_R":         "alt",
    "Meta_L":        "meta",
    "Meta_R":        "meta",
    "Super_L":       "meta",
    "Super_R":       "meta",
    "space":         "space",
    "Left":          "left",
    "Right":         "right",
    "Up":            "up",
    "Down":          "down",
    "Insert":        "insert",
    "Home":          "home",
    "End":           "end",
    "Prior":         "page_up",
    "Next":          "page_down",
    "Print":         "print_screen",
    "Scroll_Lock":   "scroll_lock",
    "Pause":         "pause",
    "Num_Lock":      "num_lock",
    # Numpad
    "KP_0":          "numpad_0",
    "KP_1":          "numpad_1",
    "KP_2":          "numpad_2",
    "KP_3":          "numpad_3",
    "KP_4":          "numpad_4",
    "KP_5":          "numpad_5",
    "KP_6":          "numpad_6",
    "KP_7":          "numpad_7",
    "KP_8":          "numpad_8",
    "KP_9":          "numpad_9",
    "KP_Decimal":    "numpad_decimal",
    "KP_Add":        "numpad_add",
    "KP_Subtract":   "numpad_subtract",
    "KP_Multiply":   "numpad_multiply",
    "KP_Divide":     "numpad_divide",
}

# ── Character fallback map ──────────────────────────────────────────────────
# On macOS, Tk sometimes delivers event.keysym as the raw character (e.g. ".")
# instead of the named keysym (e.g. "period").  When the keysym lookup misses,
# we try event.char against this table.

_CHAR_TO_NAME: dict[str, str] = {
    ".":  "period",        ">": "greater_than_sign",
    ",":  "comma",         "<": "less_than_sign",
    ";":  "semicolon",     ":": "colon",
    "'":  "apostrophe",    '"': "double_quote",
    "[":  "left_bracket",  "{": "left_brace",
    "]":  "right_bracket", "}": "right_brace",
    "-":  "minus",         "_": "underscore",
    "=":  "equal",         "+": "plus",
    "\\":  "backslash",    "|": "pipe",
    "`":  "grave_accent",  "~": "tilde",
    "/":  "slash",         "?": "question_mark",
    "!":  "exclamation_mark",
    "@":  "at",
    "#":  "hash",
    "$":  "dollar_sign",
    "%":  "percent_sign",
    "^":  "caret",
    "&":  "ampersand",
    "*":  "asterisk",
    "(":  "left_parenthesis",
    ")":  "right_parenthesis",
    " ":  "space",
}


def _normalize_keysym(keysym: str) -> str | None:
    """Map a tkinter keysym to a layout key name. Returns None if unknown."""
    if keysym in _KEYSYM_MAP:
        return _KEYSYM_MAP[keysym]
    # Letters and digits only.  Punctuation single-chars (e.g. "." or "/"
    # delivered by macOS Tk instead of "period"/"slash") must return None so
    # the caller falls through to the _CHAR_TO_NAME char-based lookup.
    if len(keysym) == 1 and keysym.isalnum():
        return keysym.lower()
    return None


def _normalize_char(char: str) -> str | None:
    """Map event.char to a layout key name (fallback for macOS Tk quirks)."""
    if not char:
        return None
    if char in _CHAR_TO_NAME:
        return _CHAR_TO_NAME[char]
    if len(char) == 1 and char.isalpha():
        return char.lower()
    return None


# ── Layout data model ──────────────────────────────────────────────────────

@dataclass
class _Key:
    id: str
    label: str
    width: float
    names: set[str]       # all normalised key names for this key
    capturable: bool = True


@dataclass
class _Row:
    items: list           # _Key | float (float = gap width in units)


@dataclass
class _Layout:
    id: str
    name: str
    rows: list[_Row]
    key_map: dict[str, "_Key"]          # key_id → _Key
    capturable_ids: set[str]            # ids of all capturable keys
    name_map: dict[str, set[str]]       # normalised name → set of key_ids


def _load_layout(path: Path) -> _Layout:
    root = ET.parse(path).getroot()
    lid   = root.get("id",   path.stem)
    lname = root.get("name", lid)
    rows: list[_Row] = []
    key_map: dict[str, _Key] = {}
    name_map: dict[str, set[str]] = {}
    capturable_ids: set[str] = set()

    for row_el in root.findall("row"):
        items: list = []
        for child in row_el:
            if child.tag == "gap":
                items.append(float(child.get("width", "1.0")))
            elif child.tag == "key":
                key_id   = child.get("id",    "")
                label    = child.get("label", "")
                primary  = child.get("key",   "")
                width    = float(child.get("width", "1.0"))
                cap      = child.get("capturable", "true").lower() != "false"
                also_raw = child.get("also", "")

                names: set[str] = set()
                if primary:
                    names.add(primary)
                for k in (x.strip() for x in also_raw.split(",") if x.strip()):
                    names.add(k)

                key = _Key(id=key_id, label=label, width=width,
                           names=names, capturable=cap)
                items.append(key)
                key_map[key_id] = key
                if cap:
                    capturable_ids.add(key_id)
                    for n in names:
                        name_map.setdefault(n, set()).add(key_id)
        rows.append(_Row(items=items))

    return _Layout(id=lid, name=lname, rows=rows, key_map=key_map,
                   capturable_ids=capturable_ids, name_map=name_map)


def _list_layouts() -> list[tuple[str, Path]]:
    result = []
    for lid in _LAYOUT_ORDER:
        p = _KEYBOARDS_DIR / f"{lid}.xml"
        if p.exists():
            result.append((lid, p))
    return result


# ── Visual constants ────────────────────────────────────────────────────────

_BG        = "#1a1a1a"
_KEY_UP    = "#2a5ab8"    # unpressed capturable key
_KEY_DOWN  = "#1a1a1a"    # pressed key (same as bg → invisible)
_KEY_NOCAP = "#333333"    # non-capturable key
_OUTLINE   = "#444444"
_TXT_KEY   = "#ffffff"
_TXT_DIM   = "#555555"
_KEY_GAP   = 4            # px gap between neighbouring keys
_ROW_GAP   = 5            # px gap between rows
_PAD_X     = 28           # canvas horizontal padding
_PAD_Y     = 12           # canvas vertical padding


# ── Main UI ─────────────────────────────────────────────────────────────────

def run_keyboard_test() -> bool:
    try:
        import tkinter as tk
    except ImportError:
        sys.exit(2)

    try:
        root = tk.Tk()
    except Exception:
        sys.exit(2)

    root.title("Keyboard Test")
    if platform.system() == "Darwin":
        # Use native macOS fullscreen — this suppresses system-wide shortcuts
        # (including Mission Control's F11 "Show Desktop") so Tk receives them.
        root.attributes("-fullscreen", True)
        root.createcommand("::tk::mac::Fullscreen", lambda: None)  # swallow Cmd+Ctrl+F
    else:
        root.attributes("-fullscreen", True)
    root.configure(bg=_BG)

    # Load layouts
    layout_list = _list_layouts()
    if not layout_list:
        sys.exit(2)

    layouts: dict[str, _Layout] = {}
    for lid, path in layout_list:
        try:
            layouts[lid] = _load_layout(path)
        except Exception:
            pass
    if not layouts:
        sys.exit(2)

    # Pick platform default
    _default_id = {"Darwin": "macbook_us", "Windows": "full_us"}.get(
        platform.system(), "tkl_us"
    )
    if _default_id not in layouts:
        _default_id = layout_list[0][0]

    active_id = [_default_id]
    pressed: dict[str, set[str]] = {lid: set() for lid in layouts}
    completed = [False]
    key_rects: list[tuple[str, float, float, float, float]] = []  # (key_id, x1, y1, x2, y2)

    # ── Top bar ─────────────────────────────────────────────────────────────
    topbar = tk.Frame(root, bg=_BG)
    topbar.pack(fill="x", padx=16, pady=(12, 0))

    title_var = tk.StringVar()
    tk.Label(topbar, textvariable=title_var, bg=_BG, fg="#4a9eff",
             font=("Courier", 16, "bold")).pack(side="left")

    # ── Layout selector (dropdown) ────────────────────────────────────────────
    # Use Label + tk.Menu popup — tk.OptionMenu ignores bg/fg on macOS just
    # like tk.Button, so we build our own styled dropdown the same way.
    layout_bar = tk.Frame(root, bg=_BG)
    layout_bar.pack(fill="x", padx=16, pady=(6, 0))
    tk.Label(layout_bar, text="Layout:", bg=_BG, fg="#888",
             font=("Courier", 11)).pack(side="left", padx=(0, 8))

    layout_var = tk.StringVar(value=layouts[_default_id].name)
    _DD_BG      = "#252525"
    _DD_HOVER   = "#303030"

    dropdown_lbl = tk.Label(
        layout_bar, textvariable=layout_var,
        bg=_DD_BG, fg="#cccccc",
        font=("Courier", 11),
        padx=14, pady=4, cursor="hand2",
    )
    dropdown_lbl.pack(side="left")
    # Arrow indicator appended as a separate non-interactive label
    tk.Label(layout_bar, text=" ▾", bg=_BG, fg="#666",
             font=("Courier", 11)).pack(side="left")

    layout_menu = tk.Menu(
        root, tearoff=0,
        bg=_DD_BG, fg="#cccccc",
        activebackground="#2a5ab8", activeforeground="white",
        font=("Courier", 11), relief="flat",
    )
    for lid in layouts:
        layout_menu.add_command(
            label=layouts[lid].name,
            command=lambda l=lid: _switch_layout(l),
        )

    def _show_dropdown(event=None):
        x = dropdown_lbl.winfo_rootx()
        y = dropdown_lbl.winfo_rooty() + dropdown_lbl.winfo_height()
        layout_menu.tk_popup(x, y)

    dropdown_lbl.bind("<ButtonPress-1>", _show_dropdown)
    dropdown_lbl.bind("<Enter>", lambda e: dropdown_lbl.configure(bg=_DD_HOVER))
    dropdown_lbl.bind("<Leave>", lambda e: dropdown_lbl.configure(bg=_DD_BG))

    # ── Keyboard canvas ──────────────────────────────────────────────────────
    canvas = tk.Canvas(root, bg=_BG, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # ── Bottom bar ───────────────────────────────────────────────────────────
    bottom = tk.Frame(root, bg=_BG)
    bottom.pack(fill="x", pady=(4, 18))

    _hint = (
        "Press every key — each disappears when registered.  "
        "Right-click any key to mark it manually."
    )
    if platform.system() == "Darwin":
        _hint += "  (F11: if macOS intercepts it, right-click to mark.)"
    tk.Label(
        bottom, text=_hint,
        bg=_BG, fg="#555", font=("Courier", 10),
    ).pack()

    btn_row = tk.Frame(bottom, bg=_BG)
    btn_row.pack(pady=(10, 0))

    # Use Label + mouse bindings instead of tk.Button — on macOS, tk.Button
    # ignores bg/fg and always renders with the native system style (white).
    # Labels correctly honour background colour on all platforms.
    def _make_btn(parent, text, bg, fg, command, hover_bg):
        lbl = tk.Label(
            parent, text=text, bg=bg, fg=fg,
            font=("Courier", 13, "bold"),
            padx=28, pady=8, cursor="hand2",
        )
        lbl.bind("<Enter>",       lambda e, w=lbl, c=hover_bg: w.configure(bg=c))
        lbl.bind("<Leave>",       lambda e, w=lbl, c=bg:       w.configure(bg=c))
        lbl.bind("<ButtonPress-1>",   lambda e: command())
        return lbl

    _make_btn(btn_row, "Fail", "#8b1a1a", "white", root.destroy, "#a02020").pack(
        side="left", padx=10
    )

    # Pass button starts greyed out; activated by _update_title once all keys pressed.
    _PASS_DISABLED_BG = "#2a2a2a"
    _PASS_ENABLED_BG  = "#1a6b1a"
    _PASS_HOVER_BG    = "#228822"

    pass_lbl = tk.Label(
        btn_row, text="Pass", bg=_PASS_DISABLED_BG, fg="#555",
        font=("Courier", 13, "bold"),
        padx=28, pady=8, cursor="arrow",
    )
    pass_lbl.pack(side="left", padx=10)

    _make_btn(btn_row, "Skip", "#3a3a3a", "#aaa", root.destroy, "#4a4a4a").pack(
        side="left", padx=10
    )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _do_done():
        completed[0] = True
        root.destroy()

    def _update_title():
        layout = layouts[active_id[0]]
        ps = pressed[active_id[0]]
        total = len(layout.capturable_ids)
        count = len(ps)
        title_var.set(f"⌨  Keyboard Test  —  {count} / {total} keys")
        all_done = count >= total
        if all_done:
            pass_lbl.configure(bg=_PASS_ENABLED_BG, fg="white", cursor="hand2")
            pass_lbl.bind("<Enter>",         lambda e: pass_lbl.configure(bg=_PASS_HOVER_BG))
            pass_lbl.bind("<Leave>",         lambda e: pass_lbl.configure(bg=_PASS_ENABLED_BG))
            pass_lbl.bind("<ButtonPress-1>", lambda e: _do_done())
        else:
            pass_lbl.configure(bg=_PASS_DISABLED_BG, fg="#555", cursor="arrow")
            pass_lbl.unbind("<Enter>")
            pass_lbl.unbind("<Leave>")
            pass_lbl.unbind("<ButtonPress-1>")

    def _switch_layout(new_id: str):
        active_id[0] = new_id
        layout_var.set(layouts[new_id].name)
        _draw()
        _update_title()

    def _draw():
        canvas.delete("all")
        key_rects.clear()

        layout = layouts[active_id[0]]
        ps = pressed[active_id[0]]

        cw = canvas.winfo_width()  or 900
        ch = canvas.winfo_height() or 400

        def row_units(row: _Row) -> float:
            return sum(item if isinstance(item, float) else item.width
                       for item in row.items)

        max_units = max(row_units(r) for r in layout.rows)
        n_rows    = len(layout.rows)

        unit_w   = min(62.0, (cw - 2 * _PAD_X) / (max_units + 0.4))
        key_h    = min(52.0, (ch - 2 * _PAD_Y) / (n_rows + 0.2))
        kb_w     = max_units * unit_w
        kb_h     = n_rows * key_h
        x0       = (cw - kb_w) / 2          # horizontal centre
        fsize    = max(7, min(12, int(key_h * 0.27)))

        y = (ch - kb_h) / 2                 # vertical centre
        for row in layout.rows:
            x = x0
            for item in row.items:
                if isinstance(item, float):
                    x += item * unit_w
                else:
                    kw = item.width * unit_w - _KEY_GAP
                    kh = key_h - _ROW_GAP

                    if not item.capturable:
                        fill, outline, tc = _KEY_NOCAP, _OUTLINE, _TXT_DIM
                    elif item.id in ps:
                        fill, outline, tc = _BG, _BG, _BG        # invisible
                    else:
                        fill, outline, tc = _KEY_UP, _OUTLINE, _TXT_KEY

                    canvas.create_rectangle(x, y, x + kw, y + kh,
                                            fill=fill, outline=outline, width=1)
                    canvas.create_text(x + kw / 2, y + kh / 2,
                                       text=item.label, fill=tc,
                                       font=("Courier", fsize, "bold"))

                    if item.capturable:
                        key_rects.append((item.id, x, y, x + kw, y + kh))

                    x += item.width * unit_w
            y += key_h

    def _register_name(name: str) -> None:
        """Mark all keys for a layout key name as pressed and redraw if changed."""
        layout = layouts[active_id[0]]
        key_ids = layout.name_map.get(name, set())
        ps = pressed[active_id[0]]
        if key_ids - ps:
            ps.update(key_ids)
            _draw()
            _update_title()

    def _on_key(event) -> None:
        # Primary lookup: Tk keysym name (e.g. "bracketleft", "period")
        name = _normalize_keysym(event.keysym)

        # Fallback: use event.char for macOS Tk quirk where keysym is the raw
        # character ("." instead of "period", "[" instead of "bracketleft", etc.)
        if name is None:
            name = _normalize_char(event.char)

        if name is not None:
            _register_name(name)

    def _on_caps_lock_release(event) -> None:
        # macOS sends KeyRelease (not KeyPress) when Caps Lock turns OFF.
        # Bind KeyRelease so both presses are captured regardless of toggle state.
        _register_name("caps_lock")

    def _on_canvas_rightclick(event) -> None:
        """Right-click a key on the canvas to mark it manually (for OS-intercepted
        keys like F11 which macOS routes to Mission Control before tkinter sees it)."""
        cx, cy = event.x, event.y
        for key_id, x1, y1, x2, y2 in key_rects:
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                layout = layouts[active_id[0]]
                ps = pressed[active_id[0]]
                if key_id not in ps:
                    ps.add(key_id)
                    _draw()
                    _update_title()
                break

    root.bind("<KeyPress>",           _on_key)
    root.bind("<KeyRelease-Caps_Lock>", _on_caps_lock_release)

    # Right-click: Button-2 on macOS (two-finger tap), Button-3 on Linux/Windows
    canvas.bind("<Button-2>", _on_canvas_rightclick)
    canvas.bind("<Button-3>", _on_canvas_rightclick)

    root.focus_force()

    _update_title()
    root.after(100, _draw)   # draw after window geometry is known

    root.mainloop()
    return completed[0]


if __name__ == "__main__":
    try:
        result = run_keyboard_test()
        sys.exit(0 if result else 1)
    except SystemExit:
        raise
    except Exception:
        sys.exit(2)
