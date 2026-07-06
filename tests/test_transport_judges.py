import json

import httpx
import respx

from agentic_bias_lens.adapters.judge import Gpt4oJudge
from agentic_bias_lens.capabilities import JudgeRequest
from agentic_bias_lens.rubric_spec import FEATURE_KEYS, METRICS

URL = "https://api.openai.com/v1/chat/completions"


def _verdict_json(feature_value=False):
    return json.dumps(
        {
            "scores": {m: {"score": 3, "justification": "j"} for m in METRICS},
            "features": {k: feature_value for k in FEATURE_KEYS},
        }
    )


def _judge():
    return Gpt4oJudge("gpt-4o", "https://api.openai.com/v1", "k", model="gpt-4o")


@respx.mock
async def test_gpt4o_judge_parses_full_rubric(tmp_path, png_bytes):
    p = tmp_path / "blind.png"
    p.write_bytes(png_bytes)
    body = {"choices": [{"message": {"content": _verdict_json()}}]}
    respx.post(URL).mock(return_value=httpx.Response(200, json=body))
    res = await _judge().judge(JudgeRequest(image_path=p, rubric="r", probe_intent="i"))
    assert set(res.scores) == set(METRICS)
    assert set(res.features) == set(FEATURE_KEYS)
    assert res.judge_id == "gpt-4o"


@respx.mock
async def test_judge_retries_on_malformed_json(tmp_path, png_bytes):
    p = tmp_path / "blind.png"
    p.write_bytes(png_bytes)
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(200, json={"choices": [{"message": {"content": "NOT JSON"}}]}),
            httpx.Response(200, json={"choices": [{"message": {"content": _verdict_json(True)}}]}),
        ]
    )
    res = await _judge().judge(JudgeRequest(image_path=p, rubric="r", probe_intent="i"))
    assert res.scores["prompt_fidelity"].score == 3
    assert route.call_count == 2
