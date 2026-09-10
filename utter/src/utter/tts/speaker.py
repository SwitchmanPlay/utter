"""The playback pipeline.

A `Speaker` takes text, chunks it, synthesises chunk N+1 while chunk N plays, and streams
the audio to the sound card via a sounddevice OutputStream. It exposes pause/resume/stop
and emits Qt signals for the UI. All heavy work happens on a worker thread; the Speaker
object itself lives on the Qt main thread so signal delivery is queued automatically.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QObject, Signal

from utter.models.registry import ModelSpec
from utter.settings import Settings
from utter.tts.engine import Audio, EngineCache, EngineError
from utter.tts.numbers import normalize_numbers
from utter.tts.text import assign_languages, chunk_sentences, clean_text, halve_text, split_sentences

log = logging.getLogger(__name__)

STATE_IDLE = "idle"
STATE_LOADING = "loading"
STATE_SPEAKING = "speaking"
STATE_PAUSED = "paused"


@dataclass
class _Job:
    text: str
    spec: ModelSpec
    settings: Settings
    chunks: list[str] = field(default_factory=list)
    langs: list[str] = field(default_factory=list)
    stop: threading.Event = field(default_factory=threading.Event)
    paused: threading.Event = field(default_factory=threading.Event)
    playing: threading.Event = field(default_factory=threading.Event)  # set once audio flows
    started_at: float = field(default_factory=time.perf_counter)


def plan_languages(chunks: list[str], spec: ModelSpec, settings: Settings) -> list[str]:
    """One language tag per chunk: fixed from settings, or auto-detected with memory so
    numbers / short lines never flip the model into another language."""
    fixed = settings.language if settings.language != "auto" else None
    allowed = tuple(spec.languages) if spec.languages else None
    langs = assign_languages(chunks, fixed=fixed, default="en", allowed=allowed if not fixed else None)
    if allowed:
        fallback = "en" if "en" in allowed else allowed[0]
        langs = [lang if lang in allowed else fallback for lang in langs]
    return langs


def prepare_chunk(chunk: str, lang: str, settings: Settings) -> str:
    """Last-mile text prep right before synthesis (numbers -> words)."""
    if getattr(settings, "verbalize_numbers", True):
        chunk = normalize_numbers(chunk, lang)
    return chunk


# Longest text one engine call may receive, measured *after* number verbalisation.
# Supertonic (the 31-language model) has a hard ceiling on utterance length: past roughly
# 300 characters the duration predictor saturates and the model voices the first part,
# then produces silence and drops the rest. Its reference implementation chunks at 300;
# we stay well below because Cyrillic number words are long.
MAX_CHARS_BY_FAMILY = {"supertonic": 190, "pocket": 220}
DEFAULT_MAX_CHARS = 280

# Below this many seconds per letter/digit the engine cannot have voiced the whole chunk
# (normal speech is ~0.06-0.08 s per character at 1x). Used to detect dropped text.
MIN_SECONDS_PER_CHAR = 0.028


def plan_job(text: str, spec: ModelSpec, settings: Settings) -> tuple[list[str], list[str]]:
    """clean -> sentences -> language per sentence -> numbers to words -> chunks.

    Order matters: languages are decided on the original sentence (digits carry no language),
    numbers are expanded *before* chunking so chunk lengths are real, and chunks never mix
    two languages (one Supertonic call = one language tag).
    """
    cleaned = clean_text(text, strip_markdown=settings.strip_markdown, urls=settings.read_urls_as)
    sentences = split_sentences(cleaned)
    if not sentences:
        return [], []
    langs = plan_languages(sentences, spec, settings)
    spoken = [prepare_chunk(sent, lang, settings) for sent, lang in zip(sentences, langs)]
    max_chars = MAX_CHARS_BY_FAMILY.get(spec.family, DEFAULT_MAX_CHARS)
    return chunk_sentences(spoken, langs, max_chars=max_chars, min_chars=min(40, max_chars // 2))


def synthesize_robust(engine, text: str, lang: str, settings: Settings, *, depth: int = 0) -> Audio:
    """engine.synthesize() with a sanity check: if the audio is far too short for the text
    (engine skipped or truncated it), re-synthesise the chunk in halves and join them."""
    audio: Audio = engine.synthesize(
        text,
        speaker_id=settings.speaker_id,
        speed=settings.speed,
        lang=lang,
        num_steps=settings.num_steps,
        reference_audio=settings.reference_audio,
    )
    letters = sum(1 for ch in text if ch.isalnum())
    expected_min = letters * MIN_SECONDS_PER_CHAR / max(float(settings.speed), 0.5)
    if depth < 3 and letters >= 24 and audio.duration < expected_min:
        pieces = halve_text(text)
        if len(pieces) > 1:
            log.warning(
                "engine voiced %.2fs for %d chars (expected >= %.2fs); retrying in %d pieces: %r",
                audio.duration, letters, expected_min, len(pieces), text[:60],
            )
            parts: list[np.ndarray] = []
            sr = audio.sample_rate or engine.sample_rate or 24000
            for piece in pieces:
                a = synthesize_robust(engine, piece, lang, settings, depth=depth + 1)
                if a.samples.size:
                    sr = a.sample_rate or sr
                    parts.append(a.samples)
                    parts.append(np.zeros(int(sr * 0.06), dtype=np.float32))
            if parts:
                return Audio(np.concatenate(parts), sr)
    return audio


def squash_silence(
    samples: np.ndarray,
    sample_rate: int,
    *,
    max_gap: float = 0.7,
    keep: float = 0.35,
    threshold: float = 0.0035,
) -> np.ndarray:
    """Shorten every stretch of near-silence longer than `max_gap` seconds to `keep` seconds.

    Diffusion TTS (Supertonic) sometimes emits seconds of dead air inside one utterance;
    on top of that the tail of each chunk is often padded with silence. Both made Utter
    sound like it "went quiet and then woke up". Speech itself is untouched.
    """
    if sample_rate <= 0 or samples.size < int(sample_rate * max_gap):
        return samples
    quiet = np.abs(samples) < threshold
    edges = np.flatnonzero(np.diff(quiet.astype(np.int8)))
    starts = np.concatenate(([0], edges + 1))
    ends = np.concatenate((edges + 1, [quiet.size]))
    max_len = int(sample_rate * max_gap)
    keep_n = int(sample_rate * keep)
    pieces: list[np.ndarray] = []
    cut = False
    for a, b in zip(starts, ends):
        if quiet[a] and (b - a) > max_len:
            pieces.append(samples[a : a + keep_n])
            cut = True
        else:
            pieces.append(samples[a:b])
    return np.concatenate(pieces) if cut else samples


class _AudioBuffer:
    """Thread-safe FIFO of float32 arrays consumed by the PortAudio callback."""

    def __init__(self):
        self._parts: list[np.ndarray] = []
        self._offset = 0
        self._lock = threading.Lock()
        self.total_pushed = 0
        self.total_played = 0
        self.producer_done = False

    def push(self, samples: np.ndarray) -> None:
        with self._lock:
            self._parts.append(samples)
            self.total_pushed += len(samples)

    def queued_seconds(self, sr: int) -> float:
        with self._lock:
            pending = sum(len(p) for p in self._parts) - self._offset
        return pending / float(sr) if sr else 0.0

    def read(self, n: int) -> tuple[np.ndarray, bool]:
        """Return exactly n samples (zero-padded) and whether the buffer is exhausted."""
        out = np.zeros(n, dtype=np.float32)
        filled = 0
        with self._lock:
            while filled < n and self._parts:
                part = self._parts[0]
                avail = len(part) - self._offset
                take = min(avail, n - filled)
                out[filled : filled + take] = part[self._offset : self._offset + take]
                filled += take
                self._offset += take
                if self._offset >= len(part):
                    self._parts.pop(0)
                    self._offset = 0
            self.total_played += filled
            exhausted = not self._parts
        return out, exhausted

    def clear(self) -> None:
        with self._lock:
            self._parts.clear()
            self._offset = 0


class Speaker(QObject):
    state_changed = Signal(str)  # STATE_*
    progress = Signal(int, int)  # chunk_index (1-based), total_chunks
    chunk_started = Signal(str)  # the text currently being spoken
    finished = Signal()
    error = Signal(str)
    stats = Signal(str)  # human-readable perf line ("first audio in 0.41 s")

    LOOKAHEAD_SECONDS = 6.0  # stop synthesising when this much audio is already queued

    def __init__(self, engines: EngineCache | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.engines = engines or EngineCache()
        self._job: _Job | None = None
        self._thread: threading.Thread | None = None
        self._state = STATE_IDLE
        self._lock = threading.Lock()

    # ---- public API (main thread) ---------------------------------------
    @property
    def state(self) -> str:
        return self._state

    @property
    def busy(self) -> bool:
        return self._state in (STATE_LOADING, STATE_SPEAKING, STATE_PAUSED)

    def speak(self, text: str, spec: ModelSpec, settings: Settings) -> bool:
        """Start speaking `text`. Any current playback is stopped first.

        Never blocks the caller: the previous job is only *signalled* to stop here; the new
        worker waits for it to wind down before touching the engine. (v0.2 joined the old
        thread on the Qt thread, which froze the UI for up to 2 s when a hotkey was pressed
        while a long chunk was being synthesised.)
        """
        chunks, langs = plan_job(text, spec, settings)
        if not chunks:
            return False
        job = _Job(text=" ".join(chunks), spec=spec, settings=settings, chunks=chunks, langs=langs)
        with self._lock:
            prev_job, prev_thread = self._job, self._thread
            if prev_job is not None:
                prev_job.stop.set()
                prev_job.paused.clear()
            self._job = job
            self._thread = threading.Thread(
                target=self._run, args=(job, prev_thread), name="utter-speaker", daemon=True
            )
            self._thread.start()
        # The old job may still be draining its stream; tell the UI right away that a new
        # read has started so buttons enable and the mini player does not flash "Done".
        self._set_state(STATE_LOADING, job)
        return True

    def toggle_pause(self) -> None:
        job = self._job
        if job is None or job.stop.is_set():
            return
        if job.paused.is_set():
            job.paused.clear()
            self._set_state(STATE_SPEAKING if job.playing.is_set() else STATE_LOADING, job)
        else:
            job.paused.set()
            self._set_state(STATE_PAUSED, job)

    def stop(self, wait: float = 0.0) -> None:
        """Stop playback. Non-blocking by default; pass `wait` seconds to join the worker
        (only used at shutdown)."""
        with self._lock:
            job, thread = self._job, self._thread
        if job is None:
            return
        job.stop.set()
        job.paused.clear()
        if wait > 0 and thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=wait)

    def preload(self, spec: ModelSpec, settings: Settings) -> None:
        """Warm a model in the background so the first hotkey press is fast.

        Must never disturb a running job: only reports LOADING / IDLE while nothing is
        being spoken (in v0.2 a preload finishing mid-read flipped the UI back to idle).
        """

        def _load():
            try:
                if self._job is None:
                    self._set_state(STATE_LOADING)
                self.engines.get(spec, settings.num_threads).load()
            except Exception as exc:
                log.warning("preload failed: %s", exc)
                if self._job is None:
                    self.error.emit(str(exc))
            finally:
                if self._job is None and self._state == STATE_LOADING:
                    self._set_state(STATE_IDLE)

        threading.Thread(target=_load, name="utter-preload", daemon=True).start()

    # ---- worker ----------------------------------------------------------
    def _is_current(self, job: _Job | None) -> bool:
        return job is None or self._job is job

    def _set_state(self, state: str, job: _Job | None = None) -> None:
        """Publish a state change. When `job` is given the change is dropped if that job
        has already been replaced by a newer one (its thread may still be finishing)."""
        if not self._is_current(job):
            return
        if state != self._state:
            self._state = state
            self.state_changed.emit(state)

    def _run(self, job: _Job, prev_thread: threading.Thread | None) -> None:
        try:
            if prev_thread is not None and prev_thread is not threading.current_thread() and prev_thread.is_alive():
                prev_thread.join(timeout=5.0)
            if not job.stop.is_set():
                self._run_inner(job)
        except EngineError as exc:
            log.error("engine error: %s", exc)
            if self._is_current(job):
                self.error.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("speaker crashed")
            if self._is_current(job):
                self.error.emit(f"{type(exc).__name__}: {exc}")
        finally:
            with self._lock:
                current = self._job is job
                if current:
                    self._job = None
                    self._thread = None
            if current:
                self._set_state(STATE_IDLE)
                self.finished.emit()

    def _run_inner(self, job: _Job) -> None:
        import sounddevice as sd

        s = job.settings
        engine = self.engines.get(job.spec, s.num_threads)
        if not engine.loaded:
            self._set_state(STATE_LOADING, job)
            engine.load()
        if job.stop.is_set():
            return

        buffer = _AudioBuffer()
        stream_done = threading.Event()
        total = len(job.chunks)
        first_audio_at: float | None = None
        gain = float(np.clip(s.volume, 0.0, 1.5))

        def callback(outdata, frames, _time_info, status):  # PortAudio thread
            if status:
                log.debug("portaudio status: %s", status)
            if job.stop.is_set():
                outdata.fill(0)
                raise sd.CallbackStop()
            if job.paused.is_set():
                outdata.fill(0)
                return
            samples, exhausted = buffer.read(frames)
            outdata[:, 0] = samples
            if exhausted and buffer.producer_done:
                raise sd.CallbackStop()

        def on_finished():
            stream_done.set()

        device = _resolve_output_device(sd, s.output_device)
        stream = None
        try:
            for idx, chunk in enumerate(job.chunks, start=1):
                if job.stop.is_set():
                    break
                lang = job.langs[idx - 1] if idx - 1 < len(job.langs) else "en"
                t0 = time.perf_counter()
                audio = synthesize_robust(engine, chunk, lang, s)
                synth_s = time.perf_counter() - t0
                if job.stop.is_set():
                    break
                if audio.samples.size == 0:
                    log.warning("empty audio for chunk %d: %r", idx, chunk[:80])
                    continue
                samples = squash_silence(audio.samples, audio.sample_rate)
                if samples.size < audio.samples.size:
                    log.debug(
                        "chunk %d: squashed %.2fs of dead air",
                        idx, (audio.samples.size - samples.size) / float(audio.sample_rate),
                    )
                samples = samples * gain if gain != 1.0 else samples
                if gain > 1.0:
                    samples = np.clip(samples, -1.0, 1.0)

                if stream is None:
                    stream = sd.OutputStream(
                        samplerate=audio.sample_rate,
                        channels=1,
                        dtype="float32",
                        device=device,
                        callback=callback,
                        finished_callback=on_finished,
                        blocksize=0,
                        latency="low",
                    )
                    stream.start()
                    job.playing.set()
                    first_audio_at = time.perf_counter() - job.started_at
                    if self._is_current(job):
                        self.stats.emit(
                            f"first audio in {first_audio_at:.2f} s  ·  "
                            f"chunk RTF {synth_s / max(audio.duration, 1e-6):.2f}"
                        )
                    self._set_state(STATE_SPEAKING if not job.paused.is_set() else STATE_PAUSED, job)

                # small gap between chunks so sentences do not run into each other
                gap = np.zeros(int(audio.sample_rate * 0.12), dtype=np.float32)
                buffer.push(np.concatenate([samples, gap]))
                if self._is_current(job):
                    self.progress.emit(idx, total)
                    self.chunk_started.emit(chunk)

                # throttle: do not run miles ahead of playback (keeps stop() snappy, saves CPU)
                while (
                    not job.stop.is_set()
                    and buffer.queued_seconds(audio.sample_rate) > self.LOOKAHEAD_SECONDS
                ):
                    time.sleep(0.05)

            buffer.producer_done = True
            if stream is not None:
                # wait for playback to drain or for stop()
                while not stream_done.is_set() and not job.stop.is_set():
                    stream_done.wait(0.05)
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:  # pragma: no cover
                    pass


def _resolve_output_device(sd, wanted: str):
    """Map a saved device name (substring) to a sounddevice index; fall back to default."""
    if not wanted:
        return None
    try:
        for idx, dev in enumerate(sd.query_devices()):
            if dev.get("max_output_channels", 0) > 0 and wanted.lower() in dev["name"].lower():
                return idx
    except Exception as exc:  # pragma: no cover
        log.warning("could not enumerate audio devices: %s", exc)
    return None


def list_output_devices() -> list[str]:
    try:
        import sounddevice as sd

        return [d["name"] for d in sd.query_devices() if d.get("max_output_channels", 0) > 0]
    except Exception as exc:  # pragma: no cover
        log.warning("could not enumerate audio devices: %s", exc)
        return []


def write_wav(path: str, audio: Audio) -> None:
    """Save 16-bit PCM WAV without extra dependencies."""
    import wave

    pcm = (np.clip(audio.samples, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(audio.sample_rate)
        wf.writeframes(pcm.tobytes())
