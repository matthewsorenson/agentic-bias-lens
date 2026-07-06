from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_bias_lens.capabilities import (
    ChatRequest,
    ImageResult,
    MetricScore,
)


def test_chat_request_from_prompt():
    req = ChatRequest.from_prompt("hi")
    assert req.messages == [{"role": "user", "content": "hi"}]


def test_metric_score_range_enforced():
    MetricScore(score=5)
    with pytest.raises(ValidationError):
        MetricScore(score=6)
    with pytest.raises(ValidationError):
        MetricScore(score=0)


def test_image_result_requires_both_prompts():
    with pytest.raises(ValidationError):
        ImageResult(
            image_path=Path("x.png"),
            prompt_original="a",
            # prompt_as_sent missing
            model_id="m",
            raw_request={},
        )
    ok = ImageResult(
        image_path=Path("x.png"),
        prompt_original="a",
        prompt_as_sent="a (reshaped)",
        model_id="m",
        raw_request={},
    )
    assert ok.not_authentic is True
    assert ok.provenance == "synthetic"
