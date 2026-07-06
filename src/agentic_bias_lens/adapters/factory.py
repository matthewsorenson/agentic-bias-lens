"""Map (kind, provider, model) to a concrete adapter. Called by the registry in
real (non-fake) mode.
"""

from __future__ import annotations

from pathlib import Path

from .chat import AnthropicChat, OpenAICompatChat
from .image import (
    FAL_PATHS,
    GEMINI_IMAGE_MODEL,
    ByteplusImage,
    DashscopeImage,
    FalImage,
    GeminiImage,
    OpenAIImage,
)
from .judge import GeminiJudge, Gpt4oJudge, QwenVLJudge

QWEN_VL_MODEL = "qwen-vl-max"
GEMINI_JUDGE_MODEL = {"gemini-judge": "gemini-2.5-flash"}
DASHSCOPE_IMAGE_MODEL = {"qwen-image": "wan2.2-t2i-flash"}
BYTEPLUS_IMAGE_MODEL = {"seedream": "seedream-4-0-250828"}


def make_capability(kind, model_id, spec, provider, api_key, images_dir):
    base = spec.base_url
    imgs = Path(images_dir)

    if kind == "chat":
        if provider == "anthropic":
            return AnthropicChat(model_id, api_key, model=model_id, base_url=base)
        return OpenAICompatChat(model_id, base, api_key, model=model_id)

    if kind == "image":
        if provider == "openai":
            return OpenAIImage(model_id, base, api_key, imgs, model=model_id)
        if provider == "gemini":
            return GeminiImage(
                model_id, base, api_key, imgs, model=GEMINI_IMAGE_MODEL.get(model_id, model_id)
            )
        if provider == "fal":
            return FalImage(model_id, base, api_key, imgs, fal_path=FAL_PATHS[model_id])
        if provider == "dashscope":
            return DashscopeImage(
                model_id, base, api_key, imgs, model=DASHSCOPE_IMAGE_MODEL.get(model_id, model_id)
            )
        if provider == "byteplus":
            return ByteplusImage(
                model_id, base, api_key, imgs, model=BYTEPLUS_IMAGE_MODEL.get(model_id, model_id)
            )

    if kind == "judge":
        if provider == "openai":
            return Gpt4oJudge(model_id, base, api_key, model=model_id)
        if provider == "gemini":
            return GeminiJudge(
                model_id, base, api_key, model=GEMINI_JUDGE_MODEL.get(model_id, "gemini-2.5-flash")
            )
        if provider in ("dashscope", "fal"):
            return QwenVLJudge(model_id, base, api_key, model=QWEN_VL_MODEL)

    raise ValueError(f"no adapter for kind={kind} provider={provider} model={model_id}")
