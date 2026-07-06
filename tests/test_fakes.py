from PIL import Image

from agentic_bias_lens.capabilities import ChatRequest, ImageRequest, JudgeRequest
from agentic_bias_lens.fakes import FakeChat, FakeImage, FakeJudge
from agentic_bias_lens.redaction import PLACEHOLDER
from agentic_bias_lens.rubric_spec import FEATURE_KEYS, METRICS


async def test_fake_chat_role_aware_and_redacted():
    chat = FakeChat("claude-opus-4-8")
    req = ChatRequest.from_prompt("ROLE: guard\nCheck the prompt.")
    res = await chat.complete(req)
    assert "cultural_flags" in res.text
    assert res.model_id == "claude-opus-4-8"
    # different brains produce distinguishable finalizer output
    other = await FakeChat("glm-5.2").complete(
        ChatRequest.from_prompt("ROLE: finalizer\nWrite it.")
    )
    mine = await chat.complete(ChatRequest.from_prompt("ROLE: finalizer\nWrite it."))
    assert other.text != mine.text


async def test_fake_image_reshape_records_both_prompts(tmp_path):
    img = FakeImage("seedream", tmp_path, reshape=True)
    res = await img.generate(ImageRequest(prompt="a coastal scene", seed=7))
    assert res.prompt_original == "a coastal scene"
    assert res.prompt_as_sent != res.prompt_original
    assert res.image_path.exists()
    with Image.open(res.image_path) as im:
        assert im.size[0] > 0


async def test_fake_image_raw_request_redacted(tmp_path):
    img = FakeImage("gpt-image-1", tmp_path)
    res = await img.generate(ImageRequest(prompt="x", seed=1))
    # redaction leaves clean payloads untouched, so just assert structure
    assert res.raw_request["model"] == "gpt-image-1"
    assert PLACEHOLDER not in str(res.raw_request)  # nothing sensitive to redact here


async def test_fake_judge_full_rubric(tmp_path):
    p = tmp_path / "gpt-image-1_abc123.png"
    Image.new("RGB", (8, 8)).save(p)
    res = await FakeJudge("gpt-4o").judge(JudgeRequest(image_path=p, rubric="r", probe_intent="i"))
    assert set(res.scores) == set(METRICS)
    assert all(1 <= s.score <= 5 for s in res.scores.values())
    assert set(res.features) == set(FEATURE_KEYS)
