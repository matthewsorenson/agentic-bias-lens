from pathlib import Path

from agentic_bias_lens.capabilities import ChatResult
from agentic_bias_lens.provenance import (
    ImageRecord,
    Transcript,
    dump_json,
    write_manifest,
    write_prompts,
)

PROBE = "A photograph of the daily life of the Haida people."


def _chat(text, model="claude-opus-4-8"):
    return ChatResult(text=text, model_id=model, raw_request={}, raw_response={})


def test_prompts_json_records_probe_turns_and_as_sent(tmp_path):
    t = Transcript(probe=PROBE, condition="B", final_prompt="final coastal prompt")
    t.add_turn("research", "ROLE: research", _chat("brief"))
    t.add_turn("finalizer", "ROLE: finalizer", _chat("final coastal prompt"))
    rec = ImageRecord(
        condition="B",
        model_id="seedream",
        prompt_original="final coastal prompt",
        prompt_as_sent="final coastal prompt [as sent]",
        image_path=tmp_path / "img.png",
    )
    write_prompts(tmp_path, [t], [rec])

    data = (tmp_path / "prompts.json").read_text(encoding="utf-8")
    assert PROBE in data
    assert "final coastal prompt [as sent]" in data
    # turns preserved in order
    turns = __import__("json").loads(data)["conditions"]["B"]["turns"]
    assert [x["role"] for x in turns] == ["research", "finalizer"]


def test_dump_json_is_deterministic(tmp_path):
    obj = {"b": 2, "a": 1, "p": Path("x/y.png")}
    dump_json(obj, tmp_path / "one.json")
    dump_json(obj, tmp_path / "two.json")
    assert (tmp_path / "one.json").read_bytes() == (tmp_path / "two.json").read_bytes()


def test_manifest_has_git_sha(tmp_path):
    write_manifest(tmp_path, {"git_sha": "abc123", "seed": 1})
    assert "abc123" in (tmp_path / "manifest.json").read_text(encoding="utf-8")
