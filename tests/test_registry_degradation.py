import pytest

from agentic_bias_lens.config import Settings
from agentic_bias_lens.registry import MissingProvider, Registry


def test_fake_mode_all_available(config_dir, tmp_path):
    s = Settings.load(config_dir)
    reg = Registry.build(s, fake=True, images_dir=tmp_path)
    report = reg.availability_report()
    assert report.missing == []
    assert len(reg.image_models()) == 4
    assert len(reg.judges()) == 2
    assert reg.chat("claude-opus-4-8").id == "claude-opus-4-8"


def test_real_mode_subset_degrades(config_dir):
    s = Settings.load(config_dir)
    reg = Registry.build(s, env={"OPENAI_API_KEY": "x"}, fake=False)
    report = reg.availability_report()
    assert report.available == ["openai"]
    assert "anthropic" in report.missing
    assert "fal" in report.missing  # CN image models route to fal by default


def test_chat_missing_provider_raises(config_dir):
    s = Settings.load(config_dir)
    reg = Registry.build(s, env={"OPENAI_API_KEY": "x"}, fake=False)
    with pytest.raises(MissingProvider):
        reg.chat("glm-5.2")


def test_route_switch_changes_provider(config_dir):
    s = Settings.load(config_dir)
    s.experiment["routes"]["seedream"] = "byteplus"
    reg = Registry.build(s, fake=False, env={})
    assert reg.effective_provider("seedream") == "byteplus"
    s.experiment["routes"]["seedream"] = "fal"
    assert reg.effective_provider("seedream") == "fal"
