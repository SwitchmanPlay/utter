# Changelog

## 0.2.0 — 2026-09-06

Speech quality, models, packaging.

### Speech
- **Numbers are spoken in the right language.** Digits, years, dates (`12.05.2026`, `2026-09-06`), prices (`1 000 €`, `$5.99`), percentages, clock times, versions and ordinals are expanded into words *in the language of the surrounding sentence* (EN / DE / UK / RU, with correct genders and cases) before they reach the model. Toggle in Settings → General.
- **Brackets and quotes read naturally.** `(…)`, `[…]`, `{…}` become short pauses; stray punctuation and repeated dashes no longer produce garbage syllables.
- **Language detection is sticky.** A digit-only or very short chunk inherits the language of the previous sentence instead of falling back to English.
- **Speed up to 3×** (was 2×). Click the speed readout to reset to 1.0×.

### Models
- New: **Pocket TTS** (Kyutai, int8) — English voice-cloning model; pick a bundled voice or point Settings → Audio → “Clone voice from” at your own WAV.
- New: **KittenTTS Nano v0.2** (25 MB) and **Mini v0.1** (80 MB) — tiny English models for battery-powered laptops.
- New Piper voices: Russian **Denis**, **Dmitri**, **Ruslan**; Ukrainian **Lada** (x-low).

### App
- Overlay: the third button is now labelled **Open**; it hides the mini player, loads the text being spoken into the text pad and brings the Utter window to the front (works while speaking from a hotkey, and when the window was behind another app).
- First launch: asks once whether Utter should start with Windows.
- New brand line: *Select it. Hear it.* All “Handy for TTS” wording removed; About dialog explains the name.
- README: how to build `Utter.exe` and the installer, how to publish a GitHub Release.

## 0.1.0 — 2026-09-06

Initial release.

- Global hotkeys: read selection, read clipboard, pause/resume, stop, show/hide (rebindable).
- Text pad with Speak / Pause / Stop / Read clipboard / Save WAV.
- Streaming playback with look-ahead synthesis.
- Model manager: Supertonic 3 (int8), Kokoro v0.19 / v1.1, four Piper voices; download / preview / remove.
- Per-sentence language auto-detection (EN/DE/UK/RU/FR/ES/IT/PL) for Supertonic.
- Markdown stripping, URL handling.
- Tray icon, close-to-tray, start minimized, start with Windows, single instance.
- Mini player overlay near the cursor.
- PyInstaller spec, Inno Setup installer, GitHub Actions CI + Release.
