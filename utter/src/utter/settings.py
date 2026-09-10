"""Persistent user settings (plain JSON, human-editable)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from utter.paths import settings_file

log = logging.getLogger(__name__)


@dataclass
class Hotkeys:
    read_selection: str = "Ctrl+Alt+R"
    read_clipboard: str = "Ctrl+Alt+C"
    pause_resume: str = "Ctrl+Alt+Space"
    stop: str = "Ctrl+Alt+X"
    show_window: str = "Ctrl+Alt+U"


SPEED_MIN = 0.5
SPEED_MAX = 3.0


@dataclass
class Settings:
    # Voice
    model_id: str = "supertonic-3-int8"
    speaker_id: int = 0
    speed: float = 1.0
    language: str = "auto"  # "auto" or an ISO code like "en", "de", "uk", "ru"
    num_steps: int = 8  # Supertonic diffusion steps (quality vs latency)
    verbalize_numbers: bool = True  # "2026" -> "twenty twenty-six" (en/de/ru/uk) before synthesis
    reference_audio: str = ""  # optional WAV for voice-cloning models (Pocket TTS); "" = built-in voice
    # Audio
    output_device: str = ""  # "" = system default; otherwise a device name substring
    volume: float = 1.0
    # Behaviour
    start_minimized: bool = False
    close_to_tray: bool = True
    launch_at_login: bool = False
    asked_autostart: bool = False  # first-run "start with Windows?" prompt already shown
    show_overlay: bool = True
    overlay_follow_cursor: bool = True  # False -> the mini player stays where you dragged it
    overlay_pos: list[int] = field(default_factory=list)  # [x, y] of the last drag; [] = none
    strip_markdown: bool = True
    read_urls_as: str = "link"  # "link" | "skip" | "verbatim"
    num_threads: int = 2
    hotkeys: Hotkeys = field(default_factory=Hotkeys)
    # UI
    window_geometry: str = ""
    last_text: str = ""

    # ---- persistence -------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or settings_file()
        if not path.exists():
            return cls()
        try:
            raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # corrupt file -> start fresh, keep a backup
            log.warning("settings unreadable (%s), resetting", exc)
            try:
                path.rename(path.with_suffix(".json.bak"))
            except OSError:
                pass
            return cls()
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Settings":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in raw.items() if k in known}
        hk_raw = data.pop("hotkeys", {}) or {}
        hk_known = {f.name for f in fields(Hotkeys)}
        hotkeys = Hotkeys(**{k: v for k, v in hk_raw.items() if k in hk_known})
        s = cls(**data)
        s.hotkeys = hotkeys
        s.speed = float(min(max(s.speed, SPEED_MIN), SPEED_MAX))
        s.volume = float(min(max(s.volume, 0.0), 1.5))
        s.num_threads = int(min(max(s.num_threads, 1), 16))
        s.num_steps = int(min(max(s.num_steps, 1), 32))
        s.overlay_pos = _clean_pos(s.overlay_pos)
        s.read_urls_as = s.read_urls_as if s.read_urls_as in ("link", "skip", "verbatim") else "link"
        return s

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path | None = None) -> None:
        path = path or settings_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)


def _clean_pos(raw: Any) -> list[int]:
    """Accept [x, y] of ints (or floats); anything else -> [] (no pinned position)."""
    try:
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            return [int(raw[0]), int(raw[1])]
    except (TypeError, ValueError):
        pass
    return []
