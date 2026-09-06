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


@dataclass
class Settings:
    # Voice
    model_id: str = "supertonic-3-int8"
    speaker_id: int = 0
    speed: float = 1.0
    language: str = "auto"  # "auto" or an ISO code like "en", "de", "uk", "ru"
    num_steps: int = 8  # Supertonic diffusion steps (quality vs latency)
    # Audio
    output_device: str = ""  # "" = system default; otherwise a device name substring
    volume: float = 1.0
    # Behaviour
    start_minimized: bool = False
    close_to_tray: bool = True
    launch_at_login: bool = False
    show_overlay: bool = True
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
        s.speed = float(min(max(s.speed, 0.5), 2.0))
        s.volume = float(min(max(s.volume, 0.0), 1.5))
        s.num_threads = int(min(max(s.num_threads, 1), 16))
        s.num_steps = int(min(max(s.num_steps, 1), 32))
        return s

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path | None = None) -> None:
        path = path or settings_file()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
