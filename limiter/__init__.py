"""Public API for the look-ahead limiter exercise."""

from .lookahead import (
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

__all__ = [
    "LimiterError",
    "apply_gain",
    "attack_release",
    "delay_signal",
    "gain_curve",
    "limit_batch",
    "peak_envelope",
    "true_peak_guard",
    "validate_params",
]
