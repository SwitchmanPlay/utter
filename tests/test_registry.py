from pathlib import Path

from utter.models import registry
from utter.models.registry import MODELS, default_model, get_model, resolve_files


def test_catalogue_is_consistent():
    ids = [m.id for m in MODELS]
    assert len(ids) == len(set(ids))
    assert default_model().id == "supertonic-3-int8"
    for m in MODELS:
        assert m.url.startswith("https://") and m.url.endswith(".tar.bz2")
        assert m.family in ("kokoro", "supertonic", "vits", "pocket", "kitten")
        assert m.num_speakers >= 1
        assert len(m.voice_names()) == m.num_speakers
        assert m.languages


def test_get_model():
    assert get_model("nope") is None
    assert get_model("supertonic-3-int8").supports_lang_tag


def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def test_resolve_supertonic(tmp_path, monkeypatch):
    monkeypatch.setenv("UTTER_HOME", str(tmp_path))
    spec = get_model("supertonic-3-int8")
    root = tmp_path / "models" / spec.id / "inner-folder"
    assert resolve_files(spec) is None
    for name in (
        "duration_predictor.int8.onnx", "text_encoder.int8.onnx", "vector_estimator.int8.onnx",
        "vocoder.int8.onnx", "tts.json", "unicode_indexer.bin",
    ):
        _touch(root / name)
    assert resolve_files(spec) is None  # voice.bin missing
    _touch(root / "voice.bin")
    r = resolve_files(spec)
    assert r is not None
    assert r.files["vocoder"].endswith("vocoder.int8.onnx")
    assert registry.is_installed(spec)


def test_resolve_kokoro_and_vits(tmp_path, monkeypatch):
    monkeypatch.setenv("UTTER_HOME", str(tmp_path))
    k = get_model("kokoro-en-v0_19")
    root = tmp_path / "models" / k.id
    for name in ("model.onnx", "voices.bin", "tokens.txt", "espeak-ng-data/phontab"):
        _touch(root / name)
    r = resolve_files(k)
    assert r and r.files["data_dir"].endswith("espeak-ng-data")

    v = get_model("piper-de-thorsten-medium")
    root = tmp_path / "models" / v.id
    _touch(root / "de_DE-thorsten-medium.onnx")
    assert resolve_files(v) is None
    _touch(root / "tokens.txt")
    r = resolve_files(v)
    assert r and r.files["model"].endswith(".onnx")
