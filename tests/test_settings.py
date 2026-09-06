import json

from utter.settings import Settings


def test_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("UTTER_HOME", str(tmp_path))
    s = Settings()
    s.speed = 1.35
    s.hotkeys.stop = "F9"
    s.save()
    loaded = Settings.load()
    assert loaded.speed == 1.35
    assert loaded.hotkeys.stop == "F9"
    assert (tmp_path / "settings.json").exists()


def test_load_tolerates_garbage(tmp_path, monkeypatch):
    monkeypatch.setenv("UTTER_HOME", str(tmp_path))
    (tmp_path / "settings.json").write_text("{not json", encoding="utf-8")
    s = Settings.load()
    assert s.model_id == Settings().model_id


def test_from_dict_clamps_and_ignores_unknown():
    s = Settings.from_dict({"speed": 99, "volume": -3, "num_threads": 1000, "bogus": 1, "hotkeys": {"stop": "F1", "nope": 2}})
    assert 0.5 <= s.speed <= 2.0
    assert 0.0 <= s.volume <= 1.5
    assert 1 <= s.num_threads <= 16
    assert s.hotkeys.stop == "F1"
    d = s.to_dict()
    json.dumps(d)  # serialisable
    assert "bogus" not in d
