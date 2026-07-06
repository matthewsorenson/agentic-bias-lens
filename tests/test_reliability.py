from dataclasses import dataclass

from agentic_bias_lens.reliability import (
    krippendorff_alpha,
    mean_abs_diff,
    self_preference_delta,
    spearman,
)


def test_krippendorff_perfect_agreement():
    alpha = krippendorff_alpha([(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])
    assert abs(alpha - 1.0) < 1e-9


def test_krippendorff_detects_disagreement():
    # opposite ratings across units -> alpha well below 1
    alpha = krippendorff_alpha([(1, 5), (2, 4), (4, 2), (5, 1)])
    assert alpha < 0.5


def test_spearman_reversed():
    assert spearman([1, 2, 3], [3, 2, 1]) == -1.0


def test_mean_abs_diff():
    assert mean_abs_diff([1, 2], [1, 4]) == 1.0


@dataclass
class _V:
    judge_id: str
    model_id: str
    overall: float


def test_self_preference_positive_when_judge_inflates_own_vendor():
    verdicts = [
        _V("gpt-4o", "gpt-image-1", 5.0),  # same vendor (openai)
        _V("gpt-4o", "qwen-image", 2.0),  # other vendor
        _V("qwen-vl", "gpt-image-1", 3.0),
        _V("qwen-vl", "qwen-image", 3.0),
    ]
    model_vendor = {"gpt-image-1": "openai", "qwen-image": "alibaba"}
    judge_vendor = {"gpt-4o": "openai", "qwen-vl": "alibaba"}
    deltas = self_preference_delta(verdicts, model_vendor, judge_vendor)
    assert deltas["gpt-4o"] > 0  # inflates its own vendor
    assert deltas["qwen-vl"] == 0.0  # neutral
