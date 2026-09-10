"""Pure-numpy audio post-processing. No Qt, no models, so it is unit-testable in CI."""

from __future__ import annotations

import numpy as np


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
