from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Iterable

CALIBRATION_VERSION = "HM_PLATT_CALIBRATION_V1"


@dataclass(frozen=True)
class CalibrationArtifact:
    calibration_available: bool
    method: str
    sample_count: int
    slope: float | None
    intercept: float | None
    brier_score: float | None
    calibration_error: float | None
    version: str = CALIBRATION_VERSION

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def fit_platt(scores: Iterable[float], outcomes: Iterable[int], *, min_sample: int) -> CalibrationArtifact:
    xs = [max(0.0, min(100.0, float(v))) / 100.0 for v in scores]
    ys = [1 if int(v) else 0 for v in outcomes]
    if len(xs) != len(ys):
        raise ValueError("calibration_length_mismatch")
    if len(xs) < min_sample or len(set(ys)) < 2:
        return CalibrationArtifact(False, "platt_logistic", len(xs), None, None, None, None)
    slope = 1.0
    intercept = 0.0
    learning_rate = 0.08
    regularization = 0.01
    for _ in range(800):
        grad_s = 0.0
        grad_i = 0.0
        for x, y in zip(xs, ys, strict=True):
            p = _sigmoid(slope * x + intercept)
            error = p - y
            grad_s += error * x
            grad_i += error
        n = float(len(xs))
        grad_s = grad_s / n + regularization * slope
        grad_i /= n
        slope -= learning_rate * grad_s
        intercept -= learning_rate * grad_i
    probs = [_sigmoid(slope * x + intercept) for x in xs]
    brier = sum((p - y) ** 2 for p, y in zip(probs, ys, strict=True)) / len(xs)
    # 10-bin expected calibration error.
    ece = 0.0
    for bucket in range(10):
        lo = bucket / 10.0
        hi = (bucket + 1) / 10.0
        indexes = [idx for idx, p in enumerate(probs) if lo <= p < hi or (bucket == 9 and p == 1.0)]
        if not indexes:
            continue
        avg_p = sum(probs[idx] for idx in indexes) / len(indexes)
        avg_y = sum(ys[idx] for idx in indexes) / len(indexes)
        ece += len(indexes) / len(xs) * abs(avg_p - avg_y)
    return CalibrationArtifact(True, "platt_logistic", len(xs), slope, intercept, brier, ece)


def calibrate_probability(score: float, artifact: CalibrationArtifact) -> float | None:
    if not artifact.calibration_available or artifact.slope is None or artifact.intercept is None:
        return None
    x = max(0.0, min(100.0, float(score))) / 100.0
    return _sigmoid(artifact.slope * x + artifact.intercept)
