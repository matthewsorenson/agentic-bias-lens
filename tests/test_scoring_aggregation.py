from PIL import Image

from agentic_bias_lens.capabilities import JudgeRequest
from agentic_bias_lens.fakes import FakeJudge
from agentic_bias_lens.provenance import ImageRecord
from agentic_bias_lens.rubric_spec import METRICS
from agentic_bias_lens.scoring import score_images

MODELS = ["gpt-image-1", "imagen-4-fast", "seedream", "qwen-image"]
CONDITIONS = ["A", "B", "C"]


def _records(tmp_path):
    recs = []
    for cond in CONDITIONS:
        for model in MODELS:
            p = tmp_path / f"{model}_{cond}.png"
            Image.new("RGB", (16, 16), (10, 20, 30)).save(p)
            recs.append(
                ImageRecord(
                    condition=cond,
                    model_id=model,
                    prompt_original="p",
                    prompt_as_sent="p",
                    image_path=p,
                )
            )
    return recs


async def test_scoring_produces_blinded_verdicts(tmp_path):
    recs = _records(tmp_path)  # 12 images
    judges = [FakeJudge("gpt-4o"), FakeJudge("qwen-vl")]
    table, failures = await score_images(
        recs, judges, rubric="r", probe_intent="intent", seed=1, blind_dir=tmp_path / "_b"
    )
    assert failures == []
    assert len(table.raw()) == 24  # 12 images x 2 judges
    for v in table.raw():
        assert set(v.scores) == set(METRICS)
        assert all(1 <= s <= 5 for s in v.scores.values())
        assert v.overall == round(sum(v.scores.values()) / len(METRICS), 3)


async def test_judge_request_carries_no_provenance():
    # blinding guarantee: the judge input type cannot leak model/condition
    fields = set(JudgeRequest.model_fields)
    assert fields == {"image_path", "rubric", "probe_intent"}


async def test_aggregation_groups_by_model_and_condition(tmp_path):
    recs = _records(tmp_path)
    table, failures = await score_images(
        recs, [FakeJudge("gpt-4o")], rubric="r", probe_intent="i", seed=3, blind_dir=tmp_path / "_b"
    )
    assert failures == []
    agg = table.by_model_condition()
    assert len(agg) == 12  # 4 models x 3 conditions
    cell = agg["gpt-image-1|A"]
    assert cell["n"] == 1
    assert set(cell["metric_means"]) == set(METRICS)


class _FlakyJudge:
    """Wraps a real judge but raises on its first N calls, like a transient
    network blip (DNS failure, timeout, rate limit) mid-scoring."""

    id = "flaky-judge"

    def __init__(self, real, fail_count=1):
        self._real = real
        self._remaining_failures = fail_count

    async def judge(self, req):
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("simulated network failure")
        return await self._real.judge(req)


async def test_judge_call_failure_is_tolerated_not_fatal(tmp_path):
    recs = _records(tmp_path)  # 12 images
    flaky = _FlakyJudge(FakeJudge("gpt-4o"), fail_count=1)
    table, failures = await score_images(
        recs, [flaky], rubric="r", probe_intent="i", seed=5, blind_dir=tmp_path / "_b"
    )
    assert len(table.raw()) == 11  # 12 images, one judge call failed and was skipped
    assert len(failures) == 1
    assert failures[0]["judge_id"] == "flaky-judge"
    assert "simulated network failure" in failures[0]["error"]
