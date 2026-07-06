import pytest

from agentic_bias_lens.adapters.chat import AnthropicChat, OpenAICompatChat
from agentic_bias_lens.adapters.factory import make_capability
from agentic_bias_lens.adapters.image import FalImage, OpenAIImage
from agentic_bias_lens.adapters.judge import Gpt4oJudge
from agentic_bias_lens.config import Settings
from agentic_bias_lens.registry import MissingProvider, Registry


def test_factory_maps_kinds_and_providers(config_dir, tmp_path):
    s = Settings.load(config_dir)
    chat = make_capability("chat", "glm-5.2", s.resolve("glm-5.2"), "zai", "k", tmp_path)
    assert isinstance(chat, OpenAICompatChat)
    anth = make_capability(
        "chat", "claude-opus-4-8", s.resolve("claude-opus-4-8"), "anthropic", "k", tmp_path
    )
    assert isinstance(anth, AnthropicChat)
    img = make_capability("image", "gpt-image-1", s.resolve("gpt-image-1"), "openai", "k", tmp_path)
    assert isinstance(img, OpenAIImage)
    fal = make_capability("image", "seedream", s.resolve("seedream"), "fal", "k", tmp_path)
    assert isinstance(fal, FalImage)
    judge = make_capability("judge", "gpt-4o", s.resolve("gpt-4o"), "openai", "k", tmp_path)
    assert isinstance(judge, Gpt4oJudge)


def test_registry_real_mode_builds_only_available(config_dir, tmp_path):
    s = Settings.load(config_dir)
    reg = Registry.build(s, env={"OPENAI_API_KEY": "k"}, fake=False, images_dir=tmp_path)
    imgs = reg.image_models()
    assert [m.id for m in imgs] == ["gpt-image-1"]  # only openai has a key
    # the openai image adapter is a real adapter, built via the factory
    assert imgs[0].__class__.__name__ == "OpenAIImage"
    with pytest.raises(MissingProvider):
        reg.chat("claude-opus-4-8")  # no anthropic key
