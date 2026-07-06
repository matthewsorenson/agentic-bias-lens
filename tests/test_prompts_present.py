from agentic_bias_lens.rubric_spec import FEATURE_KEYS, METRICS


def test_templates_exist_and_carry_markers(config_dir):
    prompts = config_dir / "prompts"
    for name in ["research", "accuracy", "bias", "finalizer", "guard", "verbose"]:
        text = (prompts / f"{name}.md").read_text(encoding="utf-8")
        assert f"ROLE: {name}" in text

    assert "cultural_flags" in (prompts / "guard.md").read_text(encoding="utf-8")
    for f in ["finalizer", "guard"]:
        assert "no potlatch or ceremony" in (prompts / f"{f}.md").read_text(encoding="utf-8")


def test_rubric_covers_all_metrics_and_features(config_dir):
    rubric = (config_dir / "rubric.md").read_text(encoding="utf-8")
    for m in METRICS:
        assert m in rubric
    for k in FEATURE_KEYS:
        assert k in rubric


def test_no_em_dashes_in_repo_docs(config_dir):
    # owner style rule: no em dashes in repo docs
    for p in list((config_dir / "prompts").glob("*.md")) + [config_dir / "rubric.md"]:
        assert "—" not in p.read_text(encoding="utf-8"), p
