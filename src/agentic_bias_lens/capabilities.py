"""Capability protocols and provenance-carrying request/result models.

Three capabilities, not six providers: every provider registers one or more of
ChatModel / ImageModel / VisionJudge. Provenance (raw_request/raw_response, and
both prompt strings for images) is a field on the result types, so an adapter
cannot return a result without recording what it actually sent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None


class ChatRequest(BaseModel):
    messages: list[dict]
    temperature: float = 0.7
    seed: int | None = None
    max_tokens: int = 2048

    @classmethod
    def from_prompt(cls, prompt: str, **kw) -> ChatRequest:
        return cls(messages=[{"role": "user", "content": prompt}], **kw)


class ChatResult(BaseModel):
    text: str
    model_id: str
    raw_request: dict  # key-redacted before storage
    raw_response: dict
    usage: Usage | None = None


class ImageRequest(BaseModel):
    prompt: str
    seed: int | None = None
    size: str = "1024x1024"
    n: int = 1


class ImageResult(BaseModel):
    image_path: Path
    prompt_original: str
    prompt_as_sent: str
    model_id: str
    seed: int | None = None
    raw_request: dict
    provenance: str = "synthetic"
    not_authentic: bool = True


class JudgeRequest(BaseModel):
    image_path: Path
    rubric: str
    probe_intent: str  # deliberately NOT the pipeline-specific prompt (blinding)


class MetricScore(BaseModel):
    score: int = Field(ge=1, le=5)
    justification: str = ""


class JudgeResult(BaseModel):
    image_id: str
    judge_id: str
    scores: dict[str, MetricScore]
    features: dict[str, bool] = Field(default_factory=dict)
    raw_response: dict = Field(default_factory=dict)


@runtime_checkable
class ChatModel(Protocol):
    id: str

    async def complete(self, req: ChatRequest) -> ChatResult: ...


@runtime_checkable
class ImageModel(Protocol):
    id: str

    async def generate(self, req: ImageRequest) -> ImageResult: ...


@runtime_checkable
class VisionJudge(Protocol):
    id: str

    async def judge(self, req: JudgeRequest) -> JudgeResult: ...
