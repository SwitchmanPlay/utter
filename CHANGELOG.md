# Changelog

## 3.0.1 — 2026-09-10

### Repo / CI (source only, binaries unchanged)
- `.gitignore` had `models/`, which also hid `src/utter/models/` from git. The package was never pushed, so every CI run
  since 0.1.0 died with `ModuleNotFoundError: No module named 'utter.models'`. Now `/models/` (repo root only).
- Ruff rule set pinned to `E4, E7, E9, F` in `pyproject.toml`; the unpinned latest ruff on CI flagged 52 style-only
  items that are not errors.
- Removed `.github/workflows/release.yml`. Builds are done locally, releases are uploaded with `gh release create`.

Fixes the 31-language model (Supertonic) going silent and skipping text. English-only models were not affected.

### What was wrong
- 0.2.0 started expanding numbers into words ("12.05.2026" -> "дванадцятого травня дві тисячі двадцять шостого року")
  *after* the text had been cut into chunks of up to 280 characters. The chunk the engine actually received could be
  400+ characters long. Supertonic has a hard budget per call (its own reference code chunks at 300); past that the
  duration predictor saturates, the model voices the beginning, emits dead air and drops the rest. Cyrillic text with
  dates, prices or years hit this constantly; English almost never did, which is why Kokoro/Kitten sounded fine.
- Chunks could mix two languages (an English sentence merged with a Ukrainian one) but were sent with one language tag.

### What changed
- New pipeline order: clean -> sentences -> language per sentence -> numbers to words -> chunk. Chunk length is now
  measured on the text the model really gets, and a chunk never crosses a language boundary.
- Per-family chunk budget: Supertonic 190 chars, Pocket 220, everything else 280 (`MAX_CHARS_BY_FAMILY`).
- Safety net: if the engine returns audio that is implausibly short for the text (< 0.028 s per letter), the chunk
  is re-synthesised in halves and joined, up to three levels deep. Logged as a warning so you can see it happen.
- Dead-air squash: any stretch of near-silence longer than 0.7 s inside one chunk is shortened to 0.35 s
  (Supertonic sometimes pads or inserts seconds of silence). Speech is untouched.
- Save WAV uses the same pipeline.
- Tests: language-boundary chunking, post-expansion chunk length, halve_text, squash_silence.

## 3.0.0 — 2026-09-09

Bug-fix release. No new models; the mini player, the speaker pipeline and the hotkeys got the attention.

### Mini player (overlay)
- **It moves now.** The mini player can be dragged by its label/frame (the buttons still click). It was created with a
  frameless, click-through-ish widget that had no mouse handling at all, so trying to move it did nothing.
- **Remembers where you put it.** After a drag it stays at that spot for the next read and across restarts
  (`overlay_pos` in settings.json). New Settings → General checkbox *"Mini player appears next to the cursor"*
  switches back to follow-the-cursor mode.
- **Shows up for every hotkey read.** Previously it was suppressed whenever the Utter window happened to be the active
  window, so `Ctrl+Alt+R` on text inside Utter itself or right after using the window showed no player.
  Now only reads started from the window's own Speak button skip it.
- **Hides on every stop.** Stop from the tray, the window or the player itself now dismisses it (before only the
  hotkey did); the *Done* fade only runs when the player is actually visible.
- Position is clamped to the screen the cursor is on (multi-monitor safe), and the player never grabs keyboard focus.

### Speaker / playback
- **No more "stuck" or wrong UI state after re-triggering.** Starting a new read while one was playing let the *old*
  worker thread finish later and reset the state to Idle / emit `finished`, which greyed out Pause/Stop and made the
  player fade while audio was still playing. State changes are now tagged with the job they belong to and dropped
  if that job has been replaced.
- **Hotkeys do not freeze the UI.** `speak()` and `stop()` no longer join the old worker thread on the Qt thread
  (up to 2 s freeze when a long chunk was being synthesised). The new worker waits for the old one itself.
- **Model preload no longer clobbers a running read**, and the engine can no longer be loaded twice in parallel
  (preload + first hotkey at the same time). `Engine.load()` is locked.
- Pause/resume reports the right state (Loading vs Speaking) when you unpause before the first audio arrived.

### Hotkeys / clipboard
- **Read selection works in slow apps.** Instead of one fixed 180 ms wait after the simulated `Ctrl+C`, Utter
  polls the clipboard for up to 0.8 s. Browsers and Electron apps often needed longer, which resulted in reading
  the *previous* clipboard content or "Nothing to read."
- `utter --speak-clipboard` while Utter is already running now forwards the request to the running instance
  instead of just showing its window.

### Window
- Bringing the window to the front (hotkey, tray, mini player *Open*) now falls back to `AttachThreadInput` when
  the Alt-tap trick is ignored, clears the minimized state properly and re-activates after the Win32 call.

### Internals
- Cross-thread signals (`_wav_done`, single-instance wake-up) are connected to bound methods instead of lambdas,
  so slots run on the Qt thread and never touch widgets from a worker.
- Settings: `overlay_pos` and `read_urls_as` are validated on load; `save()` creates the settings folder if needed.
- Quality-steps spinner accepts 1 (matches what `Settings.from_dict` allows).

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
