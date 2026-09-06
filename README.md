<p align="center">
  <img src="assets/icon.png" width="96" alt="Utter">
</p>
<h1 align="center">Utter</h1>
<p align="center"><b>Handy, but for text-to-speech.</b><br>
Select text anywhere → press a hotkey → hear it. 100% offline, runs on your CPU, Windows-first.</p>

---

## Why

[Handy](https://handy.computer) made local dictation effortless: one hotkey, no cloud, no subscription.
Nothing equivalent existed for the other direction — hearing an AI reply, an article or an e-mail
without reading it — that was (a) local, (b) multilingual and (c) not a 3 GB GPU project.
Utter is that: a small tray app wrapping the best small neural TTS models of 2026.

## Features

- **Global hotkey read-aloud** — select text in *any* app, press `Ctrl+Alt+R`, Utter copies it, speaks it and restores your clipboard.
- **Read clipboard** hotkey (`Ctrl+Alt+C`), pause/resume (`Ctrl+Alt+Space`), stop (`Ctrl+Alt+X`), show/hide (`Ctrl+Alt+U`). All rebindable.
- **Text pad** — paste or type anything, hit **Speak** (F5), or select a part of it to speak only that. Save as WAV.
- **Mini player** appears next to the cursor while speaking (pause / stop / open) and disappears when done.
- **Tray app** — closes to tray, optional start-with-Windows, single instance.
- **Streaming playback** — sentence 1 plays while sentence 2 is synthesised; first audio in well under a second on a modern CPU.
- **Multiple models, switchable in one click**, downloaded on demand into `%APPDATA%\Utter\models`:

| Model | Languages | Size | Licence | Notes |
|---|---|---|---|---|
| **Supertonic 3 (int8)** ⭐ default | 31 incl. EN/DE/UK/RU | ~150 MB | OpenRAIL-M | Per-sentence language auto-detect, 10 voices, very fast |
| Kokoro 82M v0.19 | EN | ~330 MB | Apache-2.0 | Most natural English in this class, 11 named voices |
| Kokoro 82M v1.1 (int8) | EN + ZH | ~130 MB | Apache-2.0 | 103 voices (unnamed — use Preview) |
| Piper Thorsten | DE | ~65 MB | MIT | Tiny, instant, robotic-ish |
| Piper Lessac | EN-US | ~65 MB | MIT | Tiny fallback |
| Piper Ukrainian | UK | ~65 MB | MIT | Tiny fallback |
| Piper Irina | RU | ~65 MB | MIT | Tiny fallback |

All models run through [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (ONNX Runtime, CPU). No Python ML stack, no CUDA, no internet after the download.

- **Markdown-aware** — `##`, `**bold**`, bullets, links and code fences are stripped or summarised ("code block omitted") so AI answers sound like prose. URLs become the word "link" (configurable).

## Install

**Release build (recommended):** grab `Utter-x.y.z-Setup.exe` or the portable zip from
[Releases](https://github.com/SwitchmanPlay/utter/releases). First launch opens the model manager — download Supertonic 3 and you are done.

**From source** (Windows, Python 3.11/3.12):

```powershell
git clone https://github.com/SwitchmanPlay/utter
cd utter
py -3.12 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## Default hotkeys

| Action | Hotkey |
|---|---|
| Read selected text | `Ctrl+Alt+R` |
| Read clipboard | `Ctrl+Alt+C` |
| Pause / resume | `Ctrl+Alt+Space` |
| Stop | `Ctrl+Alt+X` |
| Show / hide window | `Ctrl+Alt+U` |
| Speak text pad (window focused) | `F5` |
| Stop (window focused) | `Esc` |

Change them under **Tools › Settings › Hotkeys**.

## How "read selection" works

There is no reliable cross-app API for "give me the selected text" on Windows, so Utter does what
every screen reader / clipboard-TTS tool does: it saves your clipboard, releases the hotkey modifiers,
sends `Ctrl+C` to the foreground window, waits ~180 ms, reads the clipboard, restores your previous
clipboard content, and speaks. If nothing was selected it falls back to reading whatever was in the
clipboard already. Apps that block `Ctrl+C` (some terminals, some Electron apps with custom
bindings) will not work with the selection hotkey — copy manually and use `Ctrl+Alt+C` instead.

## Architecture

```
src/utter/
  app.py               wiring: settings + speaker + hotkeys + windows + tray, single instance
  settings.py          JSON settings in %APPDATA%\Utter\settings.json (UTTER_HOME overrides)
  hotkeys.py           pynput GlobalHotKeys, Qt<->pynput key-string conversion, send Ctrl+C
  tts/text.py          markdown stripping, sentence chunking, language detection
  tts/engine.py        sherpa-onnx OfflineTts wrapper (Supertonic / Kokoro / Piper)
  tts/speaker.py       producer/consumer streaming playback via sounddevice, pause/stop
  models/registry.py   model catalogue + on-disk detection
  models/download.py   resumable-ish downloader, safe tar extraction
  ui/                  PySide6: main window, settings dialog (model manager), overlay, tray, theme
packaging/             PyInstaller spec, Inno Setup script
.github/workflows/     CI (lint + unit tests) and Release (tag v* -> Setup.exe + portable zip)
```

## Build a release locally

```powershell
pip install -r requirements-dev.txt
.\scripts\build_windows.ps1 -Installer     # dist\Utter\Utter.exe and dist\Utter-<ver>-Setup.exe
```

Or push a tag — `git tag v0.1.1 && git push --tags` — and the Release workflow builds and attaches both.

## Tests

```powershell
pip install pytest
python -m pytest -q tests
```

The unit tests cover the pure-Python parts (text processing, chunking, language detection,
settings, model registry, hotkey parsing) and need no Qt, models or audio device.

## Status / known gaps (v0.1.0)

Be aware before you rely on it:

- v0.1.0 was written and unit-tested without a Windows box in the loop. The GUI, hotkey, audio and
  PyInstaller paths are straightforward PySide6 / pynput / sounddevice code, but they have **not yet
  been exercised end-to-end**. Expect small fixes in 0.1.x. Please open issues with the log from
  `%APPDATA%\Utter\logs\utter.log`.
- Model archive URLs point at the sherpa-onnx `tts-models` GitHub release. The Supertonic 3 and
  Kokoro entries are confirmed; the four Piper file names follow the release's naming convention but
  were not individually verified. If one 404s, fix the URL in `models/registry.py`.
- Kokoro v1.1 speaker names are not shipped in the archive, so voices show as "Speaker N".
- Language auto-detection is a script + stop-word heuristic, tuned for EN/DE/UK/RU. Fix the language
  in the combo box for anything exotic.
- Windows only for now. macOS/Linux mostly work in principle (Qt + sherpa-onnx are cross-platform) but
  autostart, the installer and the `Ctrl+C` trick are Windows-specific.

## Credits

- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) — the runtime that makes all of this a `pip install`.
- [Supertonic 3](https://github.com/supertone-inc/supertonic) by Supertone, [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad, [Piper](https://github.com/rhasspy/piper) voices.
- [Handy](https://github.com/cjpais/Handy) for showing what a local speech tool should feel like.

## Licence

MIT — see [LICENSE](LICENSE). Model weights keep their own licences (see table above).
