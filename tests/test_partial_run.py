"""End-to-end real-mode run with only one key present: brain-dependent conditions
are skipped, the one-shot condition runs on the available image model, and the
available judge scores it. Proves graceful degradation with real adapters (HTTP
mocked by respx).
"""

import json

import httpx
import respx

from agentic_bias_lens.config import Settings
from agentic_bias_lens.registry import Registry
from agentic_bias_lens.rubric_spec import FEATURE_KEYS, METRICS
from agentic_bias_lens.runner import run_experiment


def _verdict():
    return json.dumps(
        {
            "scores": {m: {"score": 3, "justification": "j"} for m in METRICS},
            "features": {k: False for k in FEATURE_KEYS},
        }
    )


@respx.mock
async def test_partial_key_run_skips_unavailable_brains(config_dir, tmp_path, png_b64):
    respx.post("https://api.openai.com/v1/images/generations").mock(
        return_value=httpx.Response(200, json={"data": [{"b64_json": png_b64}]})
    )
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": _verdict()}}]})
    )

    s = Settings.load(config_dir)
    s.experiment["k_img"] = 1
    s.experiment["conditions"] = ["A", "B"]  # B needs Anthropic brains
    s.experiment["image_models"] = ["gpt-image-1"]
    s.experiment["judges"] = ["gpt-4o"]
    rd = tmp_path / "run"
    reg = Registry.build(s, env={"OPENAI_API_KEY": "sk-x"}, fake=False, images_dir=rd / "images")

    res = await run_experiment(s, reg, rd, rubric_text="r")

    assert res.skipped_conditions == ["B"]  # no anthropic key, cleanly skipped
    assert res.image_count == 1  # condition A x gpt-image-1 x k_img 1
    assert (rd / "report.md").exists()
    assert len(res.table.raw()) == 1  # one image, one judge
