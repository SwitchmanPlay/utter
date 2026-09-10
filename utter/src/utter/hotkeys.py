"""Global hotkeys (pynput) + the "read selection" trick.

The key-string conversion is pure Python and unit-tested; pynput is imported lazily so the
module can be imported on machines without a display (CI).
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

log = logging.getLogger(__name__)

_MODIFIERS = {
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "alt": "<alt>",
    "shift": "<shift>",
    "meta": "<cmd>",
    "win": "<cmd>",
    "cmd": "<cmd>",
    "super": "<cmd>",
}
_SPECIAL = {
    "space": "<space>",
    "tab": "<tab>",
    "enter": "<enter>",
    "return": "<enter>",
    "esc": "<esc>",
    "escape": "<esc>",
    "backspace": "<backspace>",
    "del": "<delete>",
    "delete": "<delete>",
    "ins": "<insert>",
    "insert": "<insert>",
    "home": "<home>",
    "end": "<end>",
    "pgup": "<page_up>",
    "pageup": "<page_up>",
    "pgdown": "<page_down>",
    "pagedown": "<page_down>",
    "up": "<up>",
    "down": "<down>",
    "left": "<left>",
    "right": "<right>",
    "pause": "<pause>",
    "scrolllock": "<scroll_lock>",
    "printscreen": "<print_screen>",
    "capslock": "<caps_lock>",
    "numlock": "<num_lock>",
}


class HotkeyParseError(ValueError):
    pass


def qt_to_pynput(seq: str) -> str:
    """Convert a Qt key sequence string ("Ctrl+Alt+R", "F5", "Shift+Space") to pynput syntax
    ("<ctrl>+<alt>+r", "<f5>", "<shift>+<space>")."""
    if not seq or not seq.strip():
        raise HotkeyParseError("empty hotkey")
    parts = [p.strip() for p in seq.replace(" ", "").split("+") if p.strip()]
    # "Ctrl++" (plus key) shows up as an empty part; handle it
    if seq.strip().endswith("+") and (not parts or parts[-1].lower() in _MODIFIERS):
        parts.append("+")
    if not parts:
        raise HotkeyParseError(f"cannot parse hotkey {seq!r}")
    out: list[str] = []
    mods: list[str] = []
    key: str | None = None
    for p in parts:
        low = p.lower()
        if low in _MODIFIERS:
            m = _MODIFIERS[low]
            if m not in mods:
                mods.append(m)
            continue
        if key is not None:
            raise HotkeyParseError(f"more than one non-modifier key in {seq!r}")
        if low in _SPECIAL:
            key = _SPECIAL[low]
        elif len(low) >= 2 and low[0] == "f" and low[1:].isdigit() and 1 <= int(low[1:]) <= 24:
            key = f"<{low}>"
        elif len(p) == 1:
            key = low
        else:
            raise HotkeyParseError(f"unsupported key {p!r} in {seq!r}")
    if key is None:
        raise HotkeyParseError(f"hotkey {seq!r} has no main key")
    out.extend(mods)
    out.append(key)
    return "+".join(out)


class HotkeyManager:
    """Registers global hotkeys; callbacks are invoked on pynput's listener thread.

    Wrap callbacks with something that hops to the Qt thread (see app.py).
    """

    def __init__(self):
        self._listener = None
        self._lock = threading.Lock()
        self.active: dict[str, str] = {}  # qt string -> pynput string
        self.failed: dict[str, str] = {}  # qt string -> error

    def start(self, bindings: dict[str, Callable[[], None]]) -> None:
        """bindings: {"Ctrl+Alt+R": callback, ...}. Re-registering replaces everything."""
        self.stop()
        self.active.clear()
        self.failed.clear()
        mapping: dict[str, Callable[[], None]] = {}
        for qt_seq, cb in bindings.items():
            if not qt_seq:
                continue
            try:
                py_seq = qt_to_pynput(qt_seq)
            except HotkeyParseError as exc:
                self.failed[qt_seq] = str(exc)
                continue
            if py_seq in mapping.values():
                self.failed[qt_seq] = "duplicate hotkey"
                continue
            mapping[py_seq] = _guard(cb, qt_seq)
            self.active[qt_seq] = py_seq
        if not mapping:
            return
        try:
            from pynput import keyboard
        except Exception as exc:  # pragma: no cover
            log.error("pynput unavailable: %s", exc)
            for k in list(self.active):
                self.failed[k] = f"pynput unavailable: {exc}"
            self.active.clear()
            return
        with self._lock:
            try:
                self._listener = keyboard.GlobalHotKeys(mapping)
                self._listener.daemon = True
                self._listener.start()
            except Exception as exc:  # pragma: no cover
                log.error("failed to start hotkeys: %s", exc)
                for k in list(self.active):
                    self.failed[k] = str(exc)
                self.active.clear()
                self._listener = None

    def stop(self) -> None:
        with self._lock:
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception:  # pragma: no cover
                    pass
                self._listener = None


def _guard(cb: Callable[[], None], name: str) -> Callable[[], None]:
    def wrapped():
        try:
            cb()
        except Exception:  # pragma: no cover
            log.exception("hotkey handler %s failed", name)

    return wrapped


def send_copy() -> None:
    """Simulate Ctrl+C in the foreground app so the current selection lands in the clipboard.

    Releases our own modifiers first (the user is still holding the hotkey), otherwise the
    target app would see Ctrl+Alt+C.
    """
    from pynput.keyboard import Controller, Key

    kb = Controller()
    for k in (Key.alt, Key.alt_l, Key.alt_r, Key.shift, Key.shift_l, Key.shift_r, Key.cmd, Key.ctrl, Key.ctrl_l, Key.ctrl_r):
        try:
            kb.release(k)
        except Exception:
            pass
    with kb.pressed(Key.ctrl):
        kb.press("c")
        kb.release("c")
