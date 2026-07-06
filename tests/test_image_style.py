from agentic_bias_lens.config import Settings
from agentic_bias_lens.registry import Registry
from agentic_bias_lens.runner import run_experiment


async def test_shared_style_applied_and_recorded_transparently(config_dir, tmp_path):
    s = Settings.load(config_dir)
    s.experiment["k_img"] = 1
    s.experiment["conditions"] = ["A", "B"]
    s.experiment["image_models"] = ["gpt-image-1"]
    s.experiment["image_style"] = "STYLEMARKER-42"
    rd = tmp_path / "run"
    reg = Registry.build(s, fake=True, images_dir=rd / "images")

    res = await run_experiment(s, reg, rd, rubric_text="r")

    assert res.image_records, "expected image records"
    for rec in res.image_records:
        # the shared style reaches the model (as-sent) and is auditable
        assert "STYLEMARKER-42" in rec.prompt_as_sent
        # but the pipeline's finalized prompt stays un-styled for clean provenance
        assert "STYLEMARKER-42" not in rec.prompt_original


async def test_empty_style_is_a_noop(config_dir, tmp_path):
    s = Settings.load(config_dir)
    s.experiment["k_img"] = 1
    s.experiment["conditions"] = ["A"]
    s.experiment["image_models"] = ["gpt-image-1"]
    s.experiment["image_style"] = ""
    rd = tmp_path / "run"
    reg = Registry.build(s, fake=True, images_dir=rd / "images")
    res = await run_experiment(s, reg, rd, rubric_text="r")
    rec = res.image_records[0]
    assert rec.prompt_as_sent == rec.prompt_original  # no style appended
