from agentic_bias_lens.config import Settings
from agentic_bias_lens.fakes import fake_providers as fp
from agentic_bias_lens.registry import Registry
from agentic_bias_lens.runner import run_experiment


async def test_cache_reuses_cells_and_force_busts(config_dir, tmp_path, monkeypatch):
    calls = {"n": 0}
    original = fp.FakeImage.generate

    async def counting(self, req):
        calls["n"] += 1
        return await original(self, req)

    monkeypatch.setattr(fp.FakeImage, "generate", counting)

    s = Settings.load(config_dir)
    s.experiment["k_img"] = 1
    rd = tmp_path / "run"
    rubric = (config_dir / "rubric.md").read_text(encoding="utf-8")

    reg = Registry.build(s, fake=True, images_dir=rd / "images")
    await run_experiment(s, reg, rd, rubric_text=rubric)
    first = calls["n"]
    assert first == 16

    # second run: every cell is cached, nothing regenerates
    reg2 = Registry.build(s, fake=True, images_dir=rd / "images")
    await run_experiment(s, reg2, rd, rubric_text=rubric)
    assert calls["n"] == first

    # force busts the cache
    reg3 = Registry.build(s, fake=True, images_dir=rd / "images")
    await run_experiment(s, reg3, rd, rubric_text=rubric, force=True)
    assert calls["n"] == first * 2


async def test_agent_chain_is_sequential_order(config_dir, tmp_path):
    # ordering is a correctness property: each role consumes the prior one's output
    s = Settings.load(config_dir)
    s.experiment["k_img"] = 1
    rd = tmp_path / "run"
    reg = Registry.build(s, fake=True, images_dir=rd / "images")
    rubric = (config_dir / "rubric.md").read_text(encoding="utf-8")
    res = await run_experiment(s, reg, rd, rubric_text=rubric)
    b = [t for t in res.transcripts if t.condition == "B"][0]
    assert [t.role for t in b.turns] == ["research", "accuracy", "bias", "finalizer", "guard"]
