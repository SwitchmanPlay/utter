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
    assert s.speed == 3.0  # clamped to SPEED_MAX
    assert 0.0 <= s.volume <= 1.5
    assert 1 <= s.num_threads <= 16
    assert s.hotkeys.stop == "F1"
    d = s.to_dict()
    json.dumps(d)  # serialisable
    assert "bogus" not in d


def test_overlay_position_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("UTTER_HOME", str(tmp_path))
    s = Settings()
    s.overlay_follow_cursor = False
    s.overlay_pos = [120, 340]
    s.save()
    loaded = Settings.load()
    assert loaded.overlay_follow_cursor is False
    assert loaded.overlay_pos == [120, 340]


def test_overlay_position_is_validated():
    assert Settings.from_dict({"overlay_pos": "nope"}).overlay_pos == []
    assert Settings.from_dict({"overlay_pos": [1]}).overlay_pos == []
    assert Settings.from_dict({"overlay_pos": [1.7, "2"]}).overlay_pos == [1, 2]
    assert Settings.from_dict({"overlay_pos": None}).overlay_pos == []
    assert Settings.from_dict({"read_urls_as": "garbage"}).read_urls_as == "link"
