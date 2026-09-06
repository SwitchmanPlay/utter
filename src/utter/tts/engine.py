"""Thin wrapper around sherpa-onnx OfflineTts. One instance per loaded model."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import numpy as np

from utter.models.registry import ModelSpec, pocket_voice_files, resolve_files

log = logging.getLogger(__name__)


@dataclass
class Audio:
    samples: np.ndarray  # float32 mono, -1..1
    sample_rate: int

    @property
    def duration(self) -> float:
        return len(self.samples) / float(self.sample_rate) if self.sample_rate else 0.0


class EngineError(RuntimeError):
    pass


class Engine:
    """Loads a model once and synthesizes text chunks. Thread-safe (serialised by a lock)."""

    def __init__(self, spec: ModelSpec, num_threads: int = 2, provider: str = "cpu"):
        self.spec = spec
        self.num_threads = num_threads
        self.provider = provider
        self._lock = threading.Lock()
        self._tts = None
        self.load_seconds = 0.0

    # ---- loading -------------------------------------------------------
    def load(self) -> None:
        if self._tts is not None:
            return
        try:
            import sherpa_onnx  # heavy import, keep it lazy
        except ImportError as exc:  # pragma: no cover
            raise EngineError("sherpa-onnx is not installed. Run: pip install sherpa-onnx") from exc

        files = resolve_files(self.spec)
        if files is None:
            raise EngineError(f"Model '{self.spec.name}' is not installed.")

        t0 = time.perf_counter()
        model_cfg_kwargs = dict(num_threads=self.num_threads, provider=self.provider, debug=False)
        f = files.files
        if self.spec.family == "supertonic":
            model_cfg_kwargs["supertonic"] = sherpa_onnx.OfflineTtsSupertonicModelConfig(
                duration_predictor=f["duration_predictor"],
                text_encoder=f["text_encoder"],
                vector_estimator=f["vector_estimator"],
                vocoder=f["vocoder"],
                tts_json=f["tts_json"],
                unicode_indexer=f["unicode_indexer"],
                voice_style=f["voice_style"],
            )
        elif self.spec.family == "kokoro":
            kw = dict(model=f["model"], voices=f["voices"], tokens=f["tokens"], data_dir=f["data_dir"])
            if "lexicon" in f:
                kw["lexicon"] = f["lexicon"]
            if "dict_dir" in f:
                kw["dict_dir"] = f["dict_dir"]
            model_cfg_kwargs["kokoro"] = sherpa_onnx.OfflineTtsKokoroModelConfig(**kw)
        elif self.spec.family == "kitten":
            cls = getattr(sherpa_onnx, "OfflineTtsKittenModelConfig", None)
            if cls is None:
                raise EngineError("This sherpa-onnx build has no KittenTTS support. Run: pip install -U sherpa-onnx")
            model_cfg_kwargs["kitten"] = cls(
                model=f["model"], voices=f["voices"], tokens=f["tokens"], data_dir=f["data_dir"]
            )
        elif self.spec.family == "pocket":
            cls = getattr(sherpa_onnx, "OfflineTtsPocketModelConfig", None)
            if cls is None:
                raise EngineError("This sherpa-onnx build has no Pocket TTS support. Run: pip install -U sherpa-onnx")
            model_cfg_kwargs["pocket"] = cls(
                lm_flow=f["lm_flow"],
                lm_main=f["lm_main"],
                encoder=f["encoder"],
                decoder=f["decoder"],
                text_conditioner=f["text_conditioner"],
                vocab_json=f["vocab_json"],
                token_scores_json=f["token_scores_json"],
            )
        elif self.spec.family == "vits":
            model_cfg_kwargs["vits"] = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=f["model"],
                tokens=f["tokens"],
                data_dir=f.get("data_dir", ""),
                lexicon=f.get("lexicon", ""),
            )
        else:
            raise EngineError(f"Unknown model family {self.spec.family}")

        cfg = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(**model_cfg_kwargs),
            max_num_sentences=1,
        )
        if not cfg.validate():
            raise EngineError(
                f"sherpa-onnx rejected the config for '{self.spec.name}'. "
                "Try deleting and re-downloading the model."
            )
        self._tts = sherpa_onnx.OfflineTts(cfg)
        self.load_seconds = time.perf_counter() - t0
        log.info("loaded %s in %.2fs", self.spec.id, self.load_seconds)

    @property
    def loaded(self) -> bool:
        return self._tts is not None

    @property
    def sample_rate(self) -> int:
        if self._tts is None:
            return 0
        return int(getattr(self._tts, "sample_rate", 0) or 0)

    # ---- synthesis -----------------------------------------------------
    def synthesize(
        self,
        text: str,
        *,
        speaker_id: int = 0,
        speed: float = 1.0,
        lang: str = "en",
        num_steps: int = 8,
        reference_audio: str = "",
    ) -> Audio:
        """Synthesize one chunk.

        `reference_audio` is only used by voice-cloning families (Pocket TTS): a path to a
        mono WAV of the voice to imitate. Empty -> the bundled voice selected by `speaker_id`.
        """
        if not text.strip():
            return Audio(np.zeros(0, dtype=np.float32), self.sample_rate or 24000)
        self.load()
        import sherpa_onnx

        sid = max(0, min(int(speaker_id), max(self.spec.num_speakers - 1, 0)))
        with self._lock:
            gen = getattr(sherpa_onnx, "GenerationConfig", None)
            if gen is not None:
                gc = gen()
                gc.sid = sid
                gc.speed = float(speed)
                if self.spec.family == "supertonic":
                    gc.num_steps = int(num_steps)
                    try:
                        gc.extra["lang"] = lang
                    except Exception:  # very old wheels without `extra`
                        pass
                elif self.spec.family == "pocket":
                    ref = self._pocket_reference(reference_audio, sid)
                    gc.reference_audio = ref.samples
                    gc.reference_sample_rate = ref.sample_rate
                    gc.num_steps = max(1, min(int(num_steps), 8))
                result = self._tts.generate(text, gc)
            else:  # legacy API (sherpa-onnx < 1.12)
                result = self._tts.generate(text, sid=sid, speed=float(speed))

        samples = np.asarray(result.samples, dtype=np.float32)
        if samples.ndim > 1:
            samples = samples.reshape(-1)
        return Audio(samples, int(result.sample_rate))


    # ---- voice cloning helpers ------------------------------------------
    _ref_cache: dict[str, Audio] = {}

    def _pocket_reference(self, reference_audio: str, sid: int) -> Audio:
        """Load (and cache) the reference voice WAV for Pocket TTS."""
        path = reference_audio.strip()
        if not path:
            wavs = pocket_voice_files(self.spec.install_dir)
            if not wavs:
                raise EngineError("Pocket TTS needs a reference voice WAV, but none were found in the model folder.")
            path = str(wavs[min(sid, len(wavs) - 1)])
        cached = self._ref_cache.get(path)
        if cached is not None:
            return cached
        audio = read_wav(path)
        if audio.duration < 1.0:
            raise EngineError(f"Reference voice '{path}' is too short (need at least ~1 s of clean speech).")
        if audio.duration > 30.0:  # cloning quality plateaus early; keep prompt short and fast
            audio = Audio(audio.samples[: int(30.0 * audio.sample_rate)], audio.sample_rate)
        self._ref_cache[path] = audio
        return audio


def read_wav(path: str) -> Audio:
    """Read a WAV file as float32 mono. Prefers sherpa-onnx's reader, falls back to the stdlib."""
    try:
        import sherpa_onnx

        samples, sr = sherpa_onnx.read_wave(path)
        return Audio(np.asarray(samples, dtype=np.float32).reshape(-1), int(sr))
    except Exception:
        pass
    import wave

    with wave.open(path, "rb") as w:
        n, ch, width, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    if width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif width == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise EngineError(f"Unsupported WAV sample width {width * 8} bit in '{path}'. Use 16-bit PCM.")
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return Audio(np.ascontiguousarray(data, dtype=np.float32), int(sr))


class EngineCache:
    """Keeps the most recently used engines in memory so switching voices is instant."""

    def __init__(self, max_engines: int = 2):
        self.max_engines = max_engines
        self._engines: dict[str, Engine] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def get(self, spec: ModelSpec, num_threads: int) -> Engine:
        with self._lock:
            eng = self._engines.get(spec.id)
            if eng is not None and eng.num_threads != num_threads:
                self._evict(spec.id)
                eng = None
            if eng is None:
                eng = Engine(spec, num_threads=num_threads)
                self._engines[spec.id] = eng
                self._order.append(spec.id)
                while len(self._order) > self.max_engines:
                    self._evict(self._order[0])
            else:
                self._order.remove(spec.id)
                self._order.append(spec.id)
            return eng

    def _evict(self, model_id: str) -> None:
        self._engines.pop(model_id, None)
        if model_id in self._order:
            self._order.remove(model_id)

    def clear(self) -> None:
        with self._lock:
            self._engines.clear()
            self._order.clear()
