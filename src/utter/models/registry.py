"""Catalogue of downloadable TTS models and detection of what is installed.

All models run through sherpa-onnx (ONNX Runtime, CPU). Adding a model = adding a ModelSpec.
Archives come from the sherpa-onnx `tts-models` GitHub release, which repackages the
upstream weights with the tokenizer/espeak data each engine needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from utter.paths import models_dir

SHERPA_TTS_RELEASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    family: str  # "supertonic" | "kokoro" | "vits" | "pocket" | "kitten"
    url: str
    size_mb: int  # approximate download size, for the UI only
    languages: tuple[str, ...]
    license: str
    blurb: str
    voices: tuple[str, ...] = ()  # names by speaker id; empty -> use num_speakers
    num_speakers: int = 1
    supports_lang_tag: bool = False  # engine takes a per-utterance language code
    recommended: bool = False

    def voice_names(self) -> list[str]:
        if self.family == "pocket":
            # Voice = a reference WAV shipped in the archive; list whatever is actually there.
            wavs = pocket_voice_files(self.install_dir)
            if wavs:
                return [p.stem for p in wavs]
        if self.voices:
            return list(self.voices)
        return [f"Speaker {i}" for i in range(self.num_speakers)]

    @property
    def install_dir(self) -> Path:
        return models_dir() / self.id


def pocket_voice_files(root: Path) -> list[Path]:
    """Reference voices bundled with the Pocket TTS archive (test_wavs/*.wav), sorted by name."""
    if not root.is_dir():
        return []
    wavs = [p for p in root.rglob("*.wav") if p.is_file() and "test_wavs" in p.parts]
    if not wavs:
        wavs = [p for p in root.rglob("*.wav") if p.is_file()]
    return sorted(wavs, key=lambda p: p.name.lower())


_POCKET_VOICES = ("alba", "azelma", "bria", "cosette", "eponine", "fantine", "javert", "jean", "marius")
_KITTEN_VOICES = (
    "expr-voice-2-m", "expr-voice-2-f", "expr-voice-3-m", "expr-voice-3-f",
    "expr-voice-4-m", "expr-voice-4-f", "expr-voice-5-m", "expr-voice-5-f",
)

# Speaker order of kokoro-en-v0_19 as packaged by sherpa-onnx (0..10).
_KOKORO_EN_VOICES = (
    "af (US female, default)", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
)

MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="supertonic-3-int8",
        name="Supertonic 3 (int8) — 31 languages",
        family="supertonic",
        url=SHERPA_TTS_RELEASE + "sherpa-onnx-supertonic-3-tts-int8-2026-05-11.tar.bz2",
        size_mb=150,
        languages=(
            "en", "de", "uk", "ru", "fr", "es", "it", "pl", "pt", "nl", "cs", "sk", "sl", "hr",
            "bg", "ro", "hu", "el", "tr", "da", "sv", "fi", "et", "lt", "lv", "ko", "ja", "ar",
            "hi", "id", "vi",
        ),
        license="OpenRAIL-M",
        blurb="Best all-rounder: German, Ukrainian, Russian and English from one 99M model. "
        "Very fast on CPU, auto language detection per sentence.",
        num_speakers=10,
        supports_lang_tag=True,
        recommended=True,
    ),
    ModelSpec(
        id="kokoro-en-v0_19",
        name="Kokoro 82M v0.19 — English",
        family="kokoro",
        url=SHERPA_TTS_RELEASE + "kokoro-en-v0_19.tar.bz2",
        size_mb=330,
        languages=("en",),
        license="Apache-2.0",
        blurb="The most natural English voices in this size class (Arena #1 at release). "
        "English only.",
        voices=_KOKORO_EN_VOICES,
        num_speakers=len(_KOKORO_EN_VOICES),
    ),
    ModelSpec(
        id="kokoro-int8-multi-lang-v1_1",
        name="Kokoro 82M v1.1 (int8) — English + Chinese, 103 voices",
        family="kokoro",
        url=SHERPA_TTS_RELEASE + "kokoro-int8-multi-lang-v1_1.tar.bz2",
        size_mb=130,
        languages=("en", "zh"),
        license="Apache-2.0",
        blurb="Newer Kokoro with 103 speakers (US/UK English + Mandarin). "
        "Speaker names are not shipped in the archive, use Preview to audition.",
        num_speakers=103,
    ),
    ModelSpec(
        id="pocket-tts-int8",
        name="Pocket TTS (Kyutai, int8) — English, voice cloning",
        family="pocket",
        url=SHERPA_TTS_RELEASE + "sherpa-onnx-pocket-tts-int8-2026-01-26.tar.bz2",
        size_mb=120,
        languages=("en",),
        license="CC-BY-4.0",
        blurb="Newest English model here (Jan 2026 export). Extremely natural prosody, 100M params, "
        "streams on CPU. Voices are reference WAVs: pick a bundled one or clone your own in Settings → Voice.",
        voices=_POCKET_VOICES,
        num_speakers=len(_POCKET_VOICES),
    ),
    ModelSpec(
        id="kitten-nano-en-v0_2",
        name="KittenTTS Nano v0.2 (fp16) — English, 25 MB",
        family="kitten",
        url=SHERPA_TTS_RELEASE + "kitten-nano-en-v0_2-fp16.tar.bz2",
        size_mb=25,
        languages=("en",),
        license="Apache-2.0",
        blurb="15M-parameter model that sounds far better than its size suggests. "
        "Ideal for laptops on battery. 8 expressive voices, English only.",
        voices=_KITTEN_VOICES,
        num_speakers=len(_KITTEN_VOICES),
    ),
    ModelSpec(
        id="kitten-mini-en-v0_1",
        name="KittenTTS Mini v0.1 (fp16) — English, 80 MB",
        family="kitten",
        url=SHERPA_TTS_RELEASE + "kitten-mini-en-v0_1-fp16.tar.bz2",
        size_mb=80,
        languages=("en",),
        license="Apache-2.0",
        blurb="Bigger sibling of Nano (80M). Cleaner consonants, still very light.",
        voices=_KITTEN_VOICES,
        num_speakers=len(_KITTEN_VOICES),
    ),
    ModelSpec(
        id="piper-de-thorsten-medium",
        name="Piper — German (Thorsten, medium)",
        family="vits",
        url=SHERPA_TTS_RELEASE + "vits-piper-de_DE-thorsten-medium.tar.bz2",
        size_mb=65,
        languages=("de",),
        license="MIT",
        blurb="Tiny and instant. More robotic than Supertonic, but rock solid for German.",
    ),
    ModelSpec(
        id="piper-en-lessac-medium",
        name="Piper — English US (Lessac, medium)",
        family="vits",
        url=SHERPA_TTS_RELEASE + "vits-piper-en_US-lessac-medium.tar.bz2",
        size_mb=65,
        languages=("en",),
        license="MIT",
        blurb="Tiny and instant. Good fallback on very weak hardware.",
    ),
    ModelSpec(
        id="piper-uk-ukrainian-medium",
        name="Piper — Ukrainian (medium)",
        family="vits",
        url=SHERPA_TTS_RELEASE + "vits-piper-uk_UA-ukrainian_tts-medium.tar.bz2",
        size_mb=65,
        languages=("uk",),
        license="MIT",
        blurb="Tiny Ukrainian voice. Supertonic sounds better; this is the lightweight option.",
    ),
    ModelSpec(
        id="piper-uk-lada-x_low",
        name="Piper — Ukrainian (Lada, x-low)",
        family="vits",
        url=SHERPA_TTS_RELEASE + "vits-piper-uk_UA-lada-x_low.tar.bz2",
        size_mb=20,
        languages=("uk",),
        license="MIT",
        blurb="Smallest Ukrainian voice (20 MB). Lower fidelity, near-zero latency.",
    ),
    ModelSpec(
        id="piper-ru-irina-medium",
        name="Piper — Russian (Irina, medium)",
        family="vits",
        url=SHERPA_TTS_RELEASE + "vits-piper-ru_RU-irina-medium.tar.bz2",
        size_mb=65,
        languages=("ru",),
        license="MIT",
        blurb="Tiny Russian female voice.",
    ),
    ModelSpec(
        id="piper-ru-denis-medium",
        name="Piper — Russian (Denis, medium)",
        family="vits",
        url=SHERPA_TTS_RELEASE + "vits-piper-ru_RU-denis-medium.tar.bz2",
        size_mb=65,
        languages=("ru",),
        license="MIT",
        blurb="Tiny Russian male voice. Clear stress placement, good for long articles.",
    ),
    ModelSpec(
        id="piper-ru-dmitri-medium",
        name="Piper — Russian (Dmitri, medium)",
        family="vits",
        url=SHERPA_TTS_RELEASE + "vits-piper-ru_RU-dmitri-medium.tar.bz2",
        size_mb=65,
        languages=("ru",),
        license="MIT",
        blurb="Tiny Russian male voice, deeper than Denis.",
    ),
    ModelSpec(
        id="piper-ru-ruslan-medium",
        name="Piper — Russian (Ruslan, medium)",
        family="vits",
        url=SHERPA_TTS_RELEASE + "vits-piper-ru_RU-ruslan-medium.tar.bz2",
        size_mb=65,
        languages=("ru",),
        license="MIT",
        blurb="Tiny Russian male voice, audiobook-style delivery.",
    ),
)

_BY_ID = {m.id: m for m in MODELS}


def get_model(model_id: str) -> ModelSpec | None:
    return _BY_ID.get(model_id)


def default_model() -> ModelSpec:
    return next(m for m in MODELS if m.recommended)


# --------------------------------------------------------------------------- file resolution


@dataclass
class ResolvedFiles:
    """Concrete file paths sherpa-onnx needs, discovered by globbing the install dir."""

    family: str
    root: Path
    files: dict[str, str] = field(default_factory=dict)


def _find_one(root: Path, *patterns: str) -> Path | None:
    for pat in patterns:
        hits = sorted(p for p in root.rglob(pat) if p.is_file())
        if hits:
            return hits[0]
    return None


def _find_dir(root: Path, name: str) -> Path | None:
    if (root / name).is_dir():
        return root / name
    hits = sorted(p for p in root.rglob(name) if p.is_dir())
    return hits[0] if hits else None


def resolve_files(spec: ModelSpec, root: Path | None = None) -> ResolvedFiles | None:
    """Return the files for this model or None if the install is missing/incomplete.

    The archives put everything in one sub-folder whose name we do not want to hard-code,
    so we glob. Returned keys match the sherpa-onnx config field names.
    """
    root = root or spec.install_dir
    if not root.is_dir():
        return None
    r = ResolvedFiles(family=spec.family, root=root)

    if spec.family == "supertonic":
        needed = {
            "duration_predictor": ("duration_predictor*.onnx",),
            "text_encoder": ("text_encoder*.onnx",),
            "vector_estimator": ("vector_estimator*.onnx",),
            "vocoder": ("vocoder*.onnx",),
            "tts_json": ("tts.json",),
            "unicode_indexer": ("unicode_indexer.bin",),
            "voice_style": ("voice.bin", "voice_style*.bin"),
        }
        for key, pats in needed.items():
            p = _find_one(root, *pats)
            if p is None:
                return None
            r.files[key] = str(p)
        return r

    if spec.family == "kokoro":
        model = _find_one(root, "model*.onnx", "*.onnx")
        voices = _find_one(root, "voices.bin")
        tokens = _find_one(root, "tokens.txt")
        data_dir = _find_dir(root, "espeak-ng-data")
        if not (model and voices and tokens and data_dir):
            return None
        r.files = {
            "model": str(model),
            "voices": str(voices),
            "tokens": str(tokens),
            "data_dir": str(data_dir),
        }
        lexicons = sorted(p for p in root.rglob("lexicon*.txt") if p.is_file())
        if lexicons:
            r.files["lexicon"] = ",".join(str(p) for p in lexicons)
        dict_dir = _find_dir(root, "dict")
        if dict_dir:
            r.files["dict_dir"] = str(dict_dir)
        return r

    if spec.family == "pocket":
        needed = {
            "lm_flow": ("lm_flow*.onnx",),
            "lm_main": ("lm_main*.onnx",),
            "encoder": ("encoder*.onnx", "mimi_encoder*.onnx"),
            "decoder": ("decoder*.onnx", "mimi_decoder*.onnx"),
            "text_conditioner": ("text_conditioner*.onnx",),
            "vocab_json": ("vocab*.json", "tokenizer*.json"),
            "token_scores_json": ("token_scores*.json", "*scores*.json"),
        }
        for key, pats in needed.items():
            p = _find_one(root, *pats)
            if p is None:
                return None
            r.files[key] = str(p)
        if not pocket_voice_files(root):
            return None
        return r

    if spec.family == "kitten":
        model = _find_one(root, "model*.onnx", "*.onnx")
        voices = _find_one(root, "voices.bin")
        tokens = _find_one(root, "tokens.txt")
        data_dir = _find_dir(root, "espeak-ng-data")
        if not (model and voices and tokens and data_dir):
            return None
        r.files = {"model": str(model), "voices": str(voices), "tokens": str(tokens), "data_dir": str(data_dir)}
        return r

    if spec.family == "vits":
        model = _find_one(root, "*.onnx")
        tokens = _find_one(root, "tokens.txt")
        data_dir = _find_dir(root, "espeak-ng-data")
        if not (model and tokens):
            return None
        r.files = {"model": str(model), "tokens": str(tokens)}
        if data_dir:
            r.files["data_dir"] = str(data_dir)
        lexicon = _find_one(root, "lexicon.txt")
        if lexicon:
            r.files["lexicon"] = str(lexicon)
        return r

    return None


def is_installed(spec: ModelSpec) -> bool:
    return resolve_files(spec) is not None


def installed_models() -> list[ModelSpec]:
    return [m for m in MODELS if is_installed(m)]
