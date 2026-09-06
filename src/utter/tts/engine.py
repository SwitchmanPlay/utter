"""Thin wrapper around sherpa-onnx OfflineTts. One instance per loaded model."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import numpy as np

from utter.models.registry import ModelSpec, resolve_files

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
    ) -> Audio:
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
                result = self._tts.generate(text, gc)
            else:  # legacy API (sherpa-onnx < 1.12)
                result = self._tts.generate(text, sid=sid, speed=float(speed))

        samples = np.asarray(result.samples, dtype=np.float32)
        if samples.ndim > 1:
            samples = samples.reshape(-1)
        return Audio(samples, int(result.sample_rate))


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
