from agentic_bias_lens.config import Settings
from agentic_bias_lens.registry import Registry
from agentic_bias_lens.runner import run_experiment


async def test_dry_run_produces_all_artifacts(config_dir, tmp_path):
    s = Settings.load(config_dir)
    s.experiment["k_img"] = 1  # keep the test fast
    rd = tmp_path / "run"
    reg = Registry.build(s, fake=True, images_dir=rd / "images")
    rubric = (config_dir / "rubric.md").read_text(encoding="utf-8")

    res = await run_experiment(s, reg, rd, rubric_text=rubric)

    for f in [
        "manifest.json",
        "prompts.json",
        "prompts.md",
        "scores.json",
        "report.md",
        "contact_sheet.html",
    ]:
        assert (rd / f).exists(), f

    # 4 conditions x 4 image models x k_img(1)
    assert res.image_count == 16
    assert len(list((rd / "images").glob("*.png"))) == 16
    # two judges scored every image
    assert len(res.table.raw()) == 32


async def test_report_names_outputs_not_the_nation(config_dir, tmp_path):
    s = Settings.load(config_dir)
    s.experiment["k_img"] = 1
    rd = tmp_path / "run"
    reg = Registry.build(s, fake=True, images_dir=rd / "images")
    rubric = (config_dir / "rubric.md").read_text(encoding="utf-8")
    await run_experiment(s, reg, rd, rubric_text=rubric)

    report = (rd / "report.md").read_text(encoding="utf-8")
    assert "judge" in report.lower()
    assert "the Haida are" not in report
    assert "the Haida wear" not in report
    # contact sheet captions each image with its as-sent prompt
    sheet = (rd / "contact_sheet.html").read_text(encoding="utf-8")
    assert "images/" in sheet
