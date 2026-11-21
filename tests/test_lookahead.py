"""Red tests for the look-ahead limiter exercise.

Every test calls at least one public function from ``limiter.lookahead``.
All stubs raise ``NotImplementedError``, so the initial suite has exactly
15 failures and no collection, import, or syntax errors.
"""

import math

import pytest

from limiter.lookahead import (
    LimiterError,
    apply_gain,
    attack_release,
    delay_signal,
    gain_curve,
    limit_batch,
    peak_envelope,
    true_peak_guard,
    validate_params,
)


def _catmull_rom_peak(samples, oversample):
    """Return the peak of the same Catmull-Rom reconstruction used by the API."""
    if not samples:
        return 0.0

    peak = max(abs(value) for value in samples)
    if len(samples) == 1:
        return peak

    for i in range(len(samples) - 1):
        p0 = samples[max(i - 1, 0)]
        p1 = samples[i]
        p2 = samples[i + 1]
        p3 = samples[min(i + 2, len(samples) - 1)]
        for k in range(oversample + 1):
            t = k / oversample
            value = 0.5 * (
                2.0 * p1
                + (-p0 + p2) * t
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t * t
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t * t * t
            )
            peak = max(peak, abs(value))
    return peak


def test_defect_01_peak_envelope_looks_ahead():
    """A future transient must already appear in the envelope."""
    peaks = peak_envelope([0.2, 0.3, 1.0, 0.3, 0.2], window=3)

    assert peaks == pytest.approx([1.0, 1.0, 1.0, 0.3, 0.2], abs=1e-6)


def test_defect_02_gain_curve_uses_linear_ratio():
    """Gain must be ceiling/peak in linear amplitude, not a dB subtraction."""
    gains = gain_curve([0.0, 0.5, 2.0], ceiling_db=-6.020599913279624)

    assert gains == pytest.approx([1.0, 1.0, 0.25], abs=1e-6)


def test_defect_03_attack_release_has_distinct_time_constants():
    """Recovery must use a slower release coefficient than attack."""
    curve = [0.25, 1.0, 1.0, 1.0]
    smoothed = attack_release(
        curve,
        attack_ms=1.0,
        release_ms=100.0,
        sample_rate=1000.0,
    )

    attack_coeff = math.exp(-1.0)
    release_coeff = math.exp(-0.01)
    after_attack = 0.25 + 0.75 * attack_coeff
    after_first_release = (
        release_coeff * after_attack + (1.0 - release_coeff) * 1.0
    )

    assert smoothed[0] == pytest.approx(after_attack, abs=1e-6)
    assert smoothed[1] == pytest.approx(after_first_release, abs=1e-6)
    assert smoothed[1] < 0.7


def test_defect_04_delay_signal_shifts_exact_sample_count():
    """The delay must be exactly the requested number of samples."""
    delayed = delay_signal([1.0, 2.0, 3.0, 4.0], delay=2)

    assert delayed == pytest.approx([0.0, 0.0, 1.0, 2.0], abs=1e-6)


def test_defect_05_apply_gain_uses_delay_aligned_curve():
    """A delayed source sample must use the curve at its source index."""
    output = apply_gain(
        samples=[1.0, 0.0, 0.0, 0.0],
        curve=[0.5, 0.75, 1.0, 1.0],
        delay=2,
    )

    assert output == pytest.approx([0.0, 0.0, 0.5, 0.0], abs=1e-6)


def test_defect_06_true_peak_guard_oversamples_between_samples():
    """An inter-sample overshoot must be attenuated even below the sample peak."""
    # A 45-degree-phase cosine has sample peak 0.9239 but a reconstructed
    # peak above 0.99.  A -0.5 dBTP ceiling therefore needs true-peak action.
    samples = [
        math.cos(math.pi / 8.0 + 2.0 * math.pi * n / 8.0) for n in range(9)
    ]
    ceiling = 10.0 ** (-0.5 / 20.0)

    assert max(abs(value) for value in samples) < ceiling
    assert _catmull_rom_peak(samples, 4) > ceiling

    guarded = true_peak_guard(samples, ceiling_dbtp=-0.5, oversample=4)

    assert len(guarded) == len(samples)
    assert _catmull_rom_peak(guarded, 4) <= ceiling + 1e-6
    assert max(abs(value) for value in guarded) <= ceiling + 1e-6


def test_defect_07_validate_params_flags_positive_ceiling():
    """A ceiling above full scale must be reported before processing."""
    issues = validate_params(ceiling_db=0.5, attack_ms=5.0, release_ms=20.0)

    assert len(issues) == 1
    assert "ceiling" in issues[0].lower()
    assert validate_params(0.0, 5.0, 20.0) == []


def test_defect_08_attack_release_clamps_short_release():
    """A release shorter than attack must be clamped, not jump in one sample."""
    curve = [0.25] * 10 + [1.0, 1.0]
    smoothed = attack_release(
        curve,
        attack_ms=10.0,
        release_ms=0.1,
        sample_rate=1000.0,
    )

    attack_coeff = math.exp(-0.1)
    release_coeff = math.exp(-0.1)
    before_release = 0.25 + 0.75 * math.exp(-1.0)
    after_release = (
        release_coeff * before_release + (1.0 - release_coeff) * 1.0
    )

    assert smoothed[9] == pytest.approx(before_release, abs=1e-6)
    assert smoothed[10] == pytest.approx(after_release, abs=1e-6)
    assert smoothed[10] - smoothed[9] < 0.1


def test_defect_09_batch_isolates_track_envelopes():
    """A loud track must not attenuate a quiet track in the same batch."""
    tracks = [[1.0] * 5, [0.1] * 5]
    config = {
        "ceiling_db": -6.020599913279624,
        "attack_ms": 5.0,
        "release_ms": 50.0,
        "window": 2,
        "sample_rate": 1000.0,
        "oversample": 4,
    }

    result = limit_batch(tracks, config)
    quiet = result["tracks"][1]

    assert quiet[0] == pytest.approx(0.0, abs=1e-6)
    assert quiet[1:] == pytest.approx([0.1, 0.1, 0.1, 0.1], abs=1e-6)


def test_defect_10_batch_rejects_zero_window_before_division():
    """A zero look-ahead window must raise LimiterError, not divide by zero."""
    config = {
        "ceiling_db": -1.0,
        "attack_ms": 1.0,
        "release_ms": 10.0,
        "window": 0,
        "sample_rate": 1000.0,
    }

    with pytest.raises(LimiterError):
        limit_batch([[0.1, 0.2]], config)


def test_all_zero_signal_stays_zero_through_chain():
    """Silence must remain exactly silent at every stage."""
    samples = [0.0] * 8
    peaks = peak_envelope(samples, window=2)
    gains = gain_curve(peaks, ceiling_db=-6.0)
    envelope = attack_release(gains, attack_ms=1.0, release_ms=10.0, sample_rate=1000.0)
    output = apply_gain(samples, envelope, delay=1)
    guarded = true_peak_guard(output, ceiling_dbtp=-6.0, oversample=4)

    assert all(value == 0.0 for value in peaks)
    assert all(value == 0.0 for value in output)
    assert all(value == 0.0 for value in guarded)


def test_zero_db_ceiling_bounds_batch_peak():
    """At 0 dBFS the final output peak must not exceed 1.0."""
    config = {
        "ceiling_db": 0.0,
        "attack_ms": 5.0,
        "release_ms": 50.0,
        "window": 4,
        "sample_rate": 1000.0,
        "oversample": 4,
    }
    result = limit_batch([[0.25, 1.4, -1.1, 0.8, 0.0]], config)
    output = result["tracks"][0]

    assert len(output) == 5
    assert max(abs(value) for value in output) <= 1.0 + 1e-6


def test_peak_envelope_rejects_zero_window():
    """A zero window is invalid at the envelope boundary."""
    with pytest.raises(LimiterError):
        peak_envelope([0.5], window=0)


def test_chain_preserves_output_lengths():
    """Every stage in the limiter chain must preserve the input length."""
    samples = [0.0, 0.4, -1.2, 0.7, 0.1, -0.3]
    window = 3
    delay = window - 1

    peaks = peak_envelope(samples, window)
    gains = gain_curve(peaks, ceiling_db=-3.0)
    envelope = attack_release(gains, 2.0, 30.0, 1000.0)
    delayed = delay_signal(samples, delay)
    output = apply_gain(samples, envelope, delay)
    guarded = true_peak_guard(output, ceiling_dbtp=-3.0, oversample=4)

    lengths = [
        len(samples),
        len(peaks),
        len(gains),
        len(envelope),
        len(delayed),
        len(output),
        len(guarded),
    ]
    assert lengths == [len(samples)] * 7


def test_batch_success_preserves_order_and_values():
    """Successful batches keep track order, values, and the source unchanged."""
    tracks = [[0.1, 0.1, 0.1], [0.25] * 4, [0.0, 0.05]]
    before = [list(track) for track in tracks]
    config = {
        "ceiling_db": -6.020599913279624,
        "attack_ms": 1.0,
        "release_ms": 50.0,
        "window": 1,
        "sample_rate": 1000.0,
        "oversample": 4,
    }

    result = limit_batch(tracks, config)
    output = result["tracks"]

    assert len(output) == len(tracks)
    assert [len(track) for track in output] == [3, 4, 2]
    for actual, expected in zip(output, before):
        assert actual == pytest.approx(expected, abs=1e-6)
    assert result["ceiling_db"] == pytest.approx(
        -6.020599913279624, abs=1e-6
    )
    assert result["window"] == 1
    assert tracks == before
