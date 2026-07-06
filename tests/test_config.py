import pytest

from agentic_bias_lens.config import ConfigError, Settings


def test_loads_and_resolves_roster(config_dir):
    s = Settings.load(config_dir)
    assert s.rosters["B"]["research"] == "claude-opus-4-8"
    assert s.resolve("glm-5.2").family == "glm"
    s.validate_rosters()  # the shipped config must be valid


def test_missing_role_raises(config_dir):
    s = Settings.load(config_dir)
    del s.rosters["B"]["guard"]
    with pytest.raises(ConfigError):
        s.validate_rosters()


def test_shipped_config_judge_is_conflict_free(config_dir):
    # the default Gemini judge shares no family with the Anthropic/GLM brains
    assert Settings.load(config_dir).validate_rosters() == []


def test_judge_conflict_of_interest_is_warning_then_strict_raises(config_dir):
    s = Settings.load(config_dir)
    # force a conflict: the Claude judge shares the anthropic family with B's brains
    s.experiment["judges"] = ["claude-sonnet-judge", "qwen-vl"]
    warnings = s.validate_rosters()  # default: warning, does not raise
    assert any("provider family" in w for w in warnings)
    with pytest.raises(ConfigError):
        s.validate_rosters(strict_judge_coi=True)


def test_active_probe_text(config_dir):
    s = Settings.load(config_dir)
    assert "Haida" in s.active_probe_text()
