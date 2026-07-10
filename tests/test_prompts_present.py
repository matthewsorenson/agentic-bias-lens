from agentic_bias_lens.adapters.judge import GENERIC_JUDGE_POLICY
from agentic_bias_lens.pipeline import GENERIC_PROMPT_POLICY
from agentic_bias_lens.rubric_spec import (
    FEATURE_KEYS,
    METRICS,
    NARROW_DEFAULT_MARKERS,
    OBSERVATIONAL_MARKERS,
)


def test_templates_exist_and_carry_markers(config_dir):
    prompts = config_dir / "prompts"
    for name in ["research", "accuracy", "bias", "finalizer", "guard", "verbose"]:
        text = (prompts / f"{name}.md").read_text(encoding="utf-8")
        assert f"ROLE: {name}" in text

    assert "cultural_flags" in (prompts / "guard.md").read_text(encoding="utf-8")


def test_reusable_prompting_systems_have_no_study_specific_instructions(config_dir):
    prompts = config_dir / "prompts"
    forbidden = [
        "haida",
        "indigenous",
        "native american",
        "northwest coast",
        "pan-plains",
        "potlatch",
        "totem",
        "teepee",
        "warbonnet",
        "nurse",
        "ceo",
        "beautiful person",
        "person from africa",
        "family dinner",
        "criminal",
    ]
    texts = [path.read_text(encoding="utf-8") for path in prompts.glob("*.md")]
    texts.append((config_dir / "rubric.md").read_text(encoding="utf-8"))
    texts.extend([GENERIC_PROMPT_POLICY, GENERIC_JUDGE_POLICY])
    for text in texts:
        text = text.lower()
        for term in forbidden:
            assert term not in text, f"{term!r} leaked into a reusable prompting system"


def test_feature_checklist_is_symmetric_and_separates_harm_from_observation():
    assert set(NARROW_DEFAULT_MARKERS).isdisjoint(OBSERVATIONAL_MARKERS)
    assert "light_skin_visible" in OBSERVATIONAL_MARKERS
    assert "medium_skin_visible" in OBSERVATIONAL_MARKERS
    assert "dark_skin_visible" in OBSERVATIONAL_MARKERS
    assert "western_setting_coded" in OBSERVATIONAL_MARKERS
    assert "non_western_setting_coded" in OBSERVATIONAL_MARKERS
    assert "light_skin_visible" not in NARROW_DEFAULT_MARKERS
    assert "western_setting_coded" not in NARROW_DEFAULT_MARKERS


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
