<p align="center">
  <img src="assets/icon.png" width="96" alt="Utter">
</p>
<h1 align="center">Utter</h1>
<p align="center"><b>Select it. Hear it.</b><br>
A tiny Windows tray app that reads any text aloud with modern neural voices — 100% offline, on your CPU.</p>

<p align="center">
  <a href="https://github.com/SwitchmanPlay/utter/releases/latest"><b>⬇ Download the latest release</b></a>
  · <a href="#install">Install</a>
  · <a href="#models">Models</a>
  · <a href="#build-the-exe-yourself">Build the .exe</a>
  · <a href="CHANGELOG.md">Changelog</a>
</p>

---

## What it does

You are reading an AI answer, a long e-mail, a Wikipedia page. Select the text, press **`Ctrl+Alt+R`**,
and Utter speaks it — in English, German, Ukrainian, Russian or 27 other languages, switching
automatically mid-text. No account, no cloud, no GPU, no telemetry. Models are downloaded once into
`%APPDATA%\Utter\models` and everything after that happens on your machine.

The name: *to utter* = to say something aloud. That is the whole product.

## Features

- **Read selection anywhere** — `Ctrl+Alt+R` copies the selected text from whatever app is in front, speaks it, and restores your clipboard.
- **Read clipboard** (`Ctrl+Alt+C`), **pause/resume** (`Ctrl+Alt+Space`), **stop** (`Ctrl+Alt+X`), **show/hide** (`Ctrl+Alt+U`). All rebindable.
- **Text pad** — paste or type, hit **Speak** (`F5`), select a passage to speak only that, export to WAV (`Ctrl+S`).
- **Mini player** pops up next to the cursor while speaking: pause, stop, or **Open** — which hides the mini player and brings the text into the main window. Drag it by its text to move it; it then stays where you dropped it (also after a restart). Settings → General switches it back to following the cursor.
- **Speed 0.5× – 3×**, live, with a one-click reset.
- **Streaming playback** — sentence 1 plays while sentence 2 is synthesised; first audio typically < 1 s on a modern CPU.
- **Numbers are spoken properly** in EN/DE/RU/UK — years, dates, times, prices, percentages, ordinals, version strings — with Slavic gender/case agreement ("в 2024 году" → "в две тысячи двадцать четвёртом году", "2 книги" → "дві книги"). Toggle in Settings.
- **Brackets become pauses** — "(like this)" is read as a short aside instead of being garbled or swallowed.
- **Markdown-aware** — headings, bold, bullets, links and code fences are cleaned so AI answers sound like prose; URLs are read as "link" (configurable).
- **Language memory** — a chunk like "2024." or "OK." keeps the language of the surrounding paragraph instead of flipping to English.
- **Voice cloning** (Pocket TTS) — point at a 5–10 s WAV of a voice and Pocket TTS speaks English in that voice.
- **Tray app** — closes to tray, single instance, optional start-with-Windows (asked once on first run).

## Models

All models run through [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (ONNX Runtime, CPU only).
Download any of them from **Tools › Settings › Models**; switch with one click.

| Model | Languages | Size | Licence | Why you'd pick it |
|---|---|---|---|---|
| **Supertonic 3 (int8)** ⭐ default | 31 incl. EN/DE/UK/RU | ~150 MB | OpenRAIL-M | Best multilingual quality on CPU, auto language switching, 10 voices, very fast |
| Pocket TTS (int8) | EN | ~100 MB | CC-BY 4.0 | Kyutai's 100M model; most natural English + **voice cloning** from a WAV |
| Kitten TTS Nano v0.2 | EN | ~30 MB | Apache-2.0 | 15M params, absurdly small, instant; 8 voices |
| Kitten TTS Mini v0.1 | EN | ~80 MB | Apache-2.0 | Bigger Kitten, better prosody |
| Kokoro 82M v0.19 | EN | ~330 MB | Apache-2.0 | Classic, very natural English, 11 named voices |
| Kokoro 82M v1.1 (int8) | EN + ZH | ~130 MB | Apache-2.0 | 103 voices (unnamed — use Preview) |
| Piper Thorsten | DE | ~65 MB | MIT | Tiny, instant, a bit robotic |
| Piper Lessac | EN-US | ~65 MB | MIT | Tiny fallback |
| Piper Ukrainian / Lada | UK | ~65 / 20 MB | MIT | Tiny fallbacks |
| Piper Irina / Denis / Dmitri / Ruslan | RU | ~65 MB each | MIT | Four tiny Russian voices |

**Honest quality ranking (Sep 2026, CPU-only):** for English, Pocket TTS ≥ Kokoro ≥ Supertonic 3 > Kitten > Piper.
For German/Ukrainian/Russian, Supertonic 3 is the only modern option that runs on a CPU in real time; the
Piper voices are fallbacks. Bigger open models (Qwen3-TTS, Chatterbox, Fish/OpenAudio, F5) need a GPU and
PyTorch and are not in Utter on purpose.

## Install

**Release build (recommended)** — from [Releases](https://github.com/SwitchmanPlay/utter/releases):

- `Utter-x.y.z-Setup.exe` — installer (per-user, no admin rights needed), adds Start-menu entry, uninstaller.
- `Utter-x.y.z-portable-win64.zip` — unzip anywhere, run `Utter.exe`.

First launch opens the model manager: download **Supertonic 3** (~150 MB) and press `Ctrl+Alt+R` on any text.
Utter then asks once whether it should start with Windows.

Windows SmartScreen may warn because the binary is not code-signed — click *More info › Run anyway*.

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

| Action | Global | In the window |
|---|---|---|
| Read selected text | `Ctrl+Alt+R` | |
| Read clipboard | `Ctrl+Alt+C` | |
| Speak text pad | | `F5` |
| Pause / resume | `Ctrl+Alt+Space` | |
| Stop | `Ctrl+Alt+X` | `Esc` |
| Show / hide window | `Ctrl+Alt+U` | |
| Save as WAV | | `Ctrl+S` |
| Open text file | | `Ctrl+O` |
| Settings | | `Ctrl+,` |

Change them under **Tools › Settings › Hotkeys**.

## Build the .exe yourself

The `.exe` is a [PyInstaller](https://pyinstaller.org) bundle: a folder `dist\Utter\` with `Utter.exe`
(windowed — **no console**), Python, Qt and sherpa-onnx inside. Models are *not* bundled; they are downloaded
by the app on first use.

```powershell
# one-time
py -3.12 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
winget install JRSoftware.InnoSetup      # only needed for -Installer

# build
.\scripts\build_windows.ps1              # -> dist\Utter\Utter.exe  +  dist\Utter-3.0.1-portable.zip
.\scripts\build_windows.ps1 -Installer   # -> also dist\Utter-3.0.1-Setup.exe
```

The script runs the unit tests first (skip with `-SkipTests`), then `pyinstaller packaging\utter.spec`, zips the
folder, and — with `-Installer` — runs Inno Setup on `packaging\installer.iss`.
If PowerShell refuses to run scripts: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

What the `.exe` does that `python run.py` does not: no console window (`console=False` in the spec),
embedded icon, version resource, and a stable install path for the start-with-Windows registry entry.

## Publish a release

Tagging is the release. The `Release` workflow (`.github/workflows/release.yml`) builds on a Windows runner
and attaches `Utter-<ver>-Setup.exe` and `Utter-<ver>-portable-win64.zip` to a GitHub Release automatically.

```powershell
# bump version in pyproject.toml and src/utter/__init__.py, update CHANGELOG.md, then:
git add -A
git commit -m "v3.0.1"
git tag v3.0.1
git push && git push --tags
```

The first push of a fresh repo: `gh repo create SwitchmanPlay/utter --public --source=. --push`.
If you built locally instead: `gh release create v3.0.1 dist\Utter-3.0.1-Setup.exe dist\Utter-3.0.1-portable.zip --notes-file CHANGELOG.md`.

## How "read selection" works

There is no reliable cross-app API for "give me the selected text" on Windows, so Utter does what every
screen reader / clipboard-TTS tool does: it saves your clipboard, releases the hotkey modifiers, sends
`Ctrl+C` to the foreground window, waits ~180 ms, reads the clipboard, restores your previous clipboard
content, and speaks. If nothing was selected it falls back to the clipboard as it was. Apps that block
`Ctrl+C` (some terminals, some Electron apps with custom bindings) will not work with the selection
hotkey — copy manually and use `Ctrl+Alt+C`.

## Architecture

```
src/utter/
  app.py               wiring: settings + speaker + hotkeys + windows + tray, single instance, autostart prompt
  settings.py          JSON settings in %APPDATA%\Utter\settings.json (UTTER_HOME overrides)
  hotkeys.py           pynput GlobalHotKeys, Qt<->pynput key-string conversion, send Ctrl+C
  tts/text.py          markdown stripping, bracket handling, sentence chunking, language detection with memory
  tts/numbers.py       number verbalisation for en/de/ru/uk (years, dates, money, %, ordinals, agreement)
  tts/engine.py        sherpa-onnx OfflineTts wrapper (Supertonic / Kokoro / Piper / Pocket / Kitten)
  tts/speaker.py       producer/consumer streaming playback via sounddevice, pause/stop, per-chunk language
  models/registry.py   model catalogue + on-disk detection
  models/download.py   downloader with safe tar extraction
  ui/                  PySide6: main window, settings dialog (model manager), mini player, tray, theme
packaging/             PyInstaller spec, Inno Setup script
scripts/               build_windows.ps1, make_icon.py
.github/workflows/     CI (lint + unit tests) and Release (tag v* -> Setup.exe + portable zip)
```

## Tests

```powershell
pip install pytest
python -m pytest -q tests
```

The tests cover the pure-Python parts (text cleaning, number verbalisation in four languages, chunking,
language detection, settings, model registry, hotkey parsing) and need no Qt, models or audio device.

## Known gaps (v3.0.1)

- Pocket TTS and Kitten TTS entries follow the sherpa-onnx ≥ 1.12.20 Python API and the `tts-models` release
  archive names as documented, but were added without a Windows box in the loop. If one fails to load,
  the error shows in the status bar and in `%APPDATA%\Utter\logs\utter.log` — please open an issue with that line.
- Number verbalisation is rule-based. It handles the common shapes well; exotic ones ("5 100" with a plain
  space, model numbers like "RTX4060") are read literally. Turn it off in Settings if it gets in your way.
- Language auto-detection is a script + stop-word heuristic tuned for EN/DE/UK/RU. Fix the language in the
  combo box for anything exotic.
- Bringing the main window to the front from the mini player uses the Win32 foreground workarounds (Alt tap,
  then AttachThreadInput). Should work everywhere now; if Windows still only flashes the taskbar button, open an issue.
- Windows only for now. macOS/Linux mostly work in principle (Qt + sherpa-onnx are cross-platform) but
  autostart, the installer and the `Ctrl+C` trick are Windows-specific.

## Credits

- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) — the runtime that makes all of this a `pip install`.
- Voices: [Supertonic 3](https://github.com/supertone-inc/supertonic) (Supertone), [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) (Kyutai),
  [Kitten TTS](https://github.com/KittenML/KittenTTS), [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) (hexgrad), [Piper](https://github.com/rhasspy/piper).

## Licence

MIT — see [LICENSE](LICENSE). Model weights keep their own licences (see table above).
