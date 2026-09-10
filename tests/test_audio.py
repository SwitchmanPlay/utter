import pytest

np = pytest.importorskip("numpy")

from utter.tts.speaker import squash_silence  # noqa: E402


def test_squash_silence_shortens_long_gaps_only():
    sr = 1000
    speech = np.full(500, 0.5, dtype=np.float32)
    short_gap = np.zeros(300, dtype=np.float32)  # 0.3 s: kept
    long_gap = np.zeros(2500, dtype=np.float32)  # 2.5 s: cut to 0.35 s
    x = np.concatenate([speech, short_gap, speech, long_gap, speech, long_gap])
    y = squash_silence(x, sr, max_gap=0.7, keep=0.35)
    assert y.size == 500 + 300 + 500 + 350 + 500 + 350
    assert np.count_nonzero(y) == 1500  # no speech lost


def test_squash_silence_noop_for_clean_audio():
    sr = 1000
    x = np.random.default_rng(0).uniform(-0.5, 0.5, 3000).astype(np.float32)
    assert squash_silence(x, sr) is x
