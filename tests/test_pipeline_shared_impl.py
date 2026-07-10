from agentic_bias_lens.agents import PipelineBuilder
from agentic_bias_lens.config import Settings
from agentic_bias_lens.pipeline import GENERIC_PROMPT_POLICY, AgenticPipeline
from agentic_bias_lens.registry import Registry


async def test_b_and_c_share_impl(config_dir, tmp_path):
    s = Settings.load(config_dir)
    reg = Registry.build(s, fake=True, images_dir=tmp_path)
    b_agents = PipelineBuilder.from_config(s, "B")
    c_agents = PipelineBuilder.from_config(s, "C")
    assert [a.role for a in b_agents] == ["research", "accuracy", "bias", "finalizer", "guard"]

    b = await AgenticPipeline(b_agents, reg, "B").run("PROBE")
    c = await AgenticPipeline(c_agents, reg, "C").run("PROBE")

    assert [t.role for t in b.transcript.turns] == list(
        ["research", "accuracy", "bias", "finalizer", "guard"]
    )
    assert b.transcript.turns[0].model_id == "claude-opus-4-8"
    assert c.transcript.turns[0].model_id == "glm-5.2"
    assert all(
        turn.rendered_prompt.startswith(GENERIC_PROMPT_POLICY)
        for turn in b.transcript.turns + c.transcript.turns
    )
    # different brains produce distinguishable finalized prompts
    assert b.final_prompt != c.final_prompt
    assert isinstance(b.cultural_flags, list)


async def test_condition_a_is_passthrough(config_dir, tmp_path):
    s = Settings.load(config_dir)
    reg = Registry.build(s, fake=True, images_dir=tmp_path)
    a = await AgenticPipeline(PipelineBuilder.from_config(s, "A"), reg, "A").run("PROBE")
    assert a.final_prompt == "PROBE"
    assert a.transcript.turns == []


async def test_a_prime_single_verbose_turn(config_dir, tmp_path):
    s = Settings.load(config_dir)
    reg = Registry.build(s, fake=True, images_dir=tmp_path)
    ap = await AgenticPipeline(
        PipelineBuilder.from_config(s, "A_prime"), reg, "A_prime"
    ).run("PROBE")
    assert len(ap.transcript.turns) == 1
    assert ap.transcript.turns[0].role == "verbose"
    assert ap.transcript.turns[0].rendered_prompt.startswith(GENERIC_PROMPT_POLICY)
    assert ap.final_prompt != "PROBE"
