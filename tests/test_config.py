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


def test_judge_conflict_of_interest_raises(config_dir):
    s = Settings.load(config_dir)
    # A Claude judge shares the 'anthropic' family with Pipeline B's brains.
    s.models["claude-judge"] = s.models["claude-opus-4-8"].model_copy(update={"kind": "judge"})
    s.experiment["judges"] = ["claude-judge", "qwen-vl"]
    with pytest.raises(ConfigError):
        s.validate_rosters()


def test_active_probe_text(config_dir):
    s = Settings.load(config_dir)
    assert "Haida" in s.active_probe_text()
