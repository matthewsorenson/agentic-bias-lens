"""Deterministic fake providers implementing the three capability protocols.

These back --dry-run and the whole test suite. The dry-run path and the tests
therefore exercise identical orchestration code, so a green suite means a working
dry run with only live-endpoint risk left for a keyed run.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from PIL import Image

from ..capabilities import (
    ChatRequest,
    ChatResult,
    ImageRequest,
    ImageResult,
    JudgeRequest,
    JudgeResult,
    MetricScore,
)
from ..redaction import redact
from ..rubric_spec import FEATURE_KEYS, METRICS
from ..watermark import finalize_image

_ROLES = ("research", "accuracy", "bias", "finalizer", "guard", "verbose")


def _short(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]


def _role_of(messages: list[dict]) -> str:
    text = " ".join(m.get("content", "") for m in messages if isinstance(m.get("content"), str))
    for role in _ROLES:
        if f"ROLE: {role}" in text:
            return role
    return "unknown"


def _canned(role: str, model_id: str, messages: list[dict]) -> str:
    tag = f"[{model_id}]"
    if role == "research":
        return (
            f"Research brief {tag}: Northwest Coast material culture: cedar longhouses, "
            "monumental totem poles, ocean-going canoes, formline art, temperate rainforest. "
            "Watchlist: pan-Plains stereotype (warbonnet, teepee, horse, prairie)."
        )
    if role == "accuracy":
        return (
            f"Accuracy constraints {tag}: coastal rainforest and Pacific shoreline; "
            "no teepees; no prairie."
        )
    if role == "bias":
        return (
            f"Bias flags {tag}: risk of pan-Indian stereotype; enforce Haida/NW-coast specificity; "
            "avoid frozen-in-the-past framing."
        )
    if role in ("finalizer", "verbose"):
        return (
            f"A documentary photograph {tag} of Haida daily life on the Pacific "
            "Northwest Coast: cedar longhouses, standing totem poles, an ocean-going "
            "cedar canoe, formline designs, temperate rainforest and shoreline, natural light."
        )
    if role == "guard":
        return (
            '{"cultural_flags": [], "notes": '
            '"no sacred or ceremonial content; specificity preserved"}'
        )
    return f"{tag} {_short(str(messages))}"


class FakeChat:
    def __init__(self, id: str, **_kw):
        self.id = id

    async def complete(self, req: ChatRequest) -> ChatResult:
        role = _role_of(req.messages)
        return ChatResult(
            text=_canned(role, self.id, req.messages),
            model_id=self.id,
            raw_request=redact({"model": self.id, "messages": req.messages}),
            raw_response={"fake": True, "role": role},
        )


class FakeImage:
    def __init__(self, id: str, images_dir: str | Path, reshape: bool = False, **_kw):
        self.id = id
        self.images_dir = Path(images_dir)
        self.reshape = reshape

    async def generate(self, req: ImageRequest) -> ImageResult:
        self.images_dir.mkdir(parents=True, exist_ok=True)
        as_sent = req.prompt + (f" [reshaped for {self.id}]" if self.reshape else "")
        # Unique token per call so distinct cells never collide on disk, even if
        # two prompts happen to be byte-identical. The runner renames to a
        # canonical cell path afterwards.
        token = uuid.uuid4().hex[:12]
        stem = _short(f"{self.id}|{as_sent}|{req.seed}")
        color = tuple(int(stem[i : i + 2], 16) for i in (0, 2, 4))
        raw = self.images_dir / f"{token}.raw.png"
        Image.new("RGB", (96, 96), color).save(raw)
        final = self.images_dir / f"{self.id}_{token}.png"
        finalize_image(raw, final)
        raw.unlink(missing_ok=True)
        return ImageResult(
            image_path=final,
            prompt_original=req.prompt,
            prompt_as_sent=as_sent,
            model_id=self.id,
            seed=req.seed,
            raw_request=redact({"model": self.id, "prompt": as_sent, "seed": req.seed}),
        )


class FakeJudge:
    def __init__(self, id: str, bias: int = 0, **_kw):
        self.id = id
        self.bias = bias

    async def judge(self, req: JudgeRequest) -> JudgeResult:
        h = int(_short(f"{self.id}|{req.image_path.name}"), 16)
        scores = {}
        for i, metric in enumerate(METRICS):
            v = 1 + (h >> (i * 3)) % 5
            v = max(1, min(5, v + self.bias))
            scores[metric] = MetricScore(score=v, justification=f"fake {metric}")
        features = {k: bool((h >> j) & 1) for j, k in enumerate(FEATURE_KEYS)}
        return JudgeResult(
            image_id=req.image_path.stem,
            judge_id=self.id,
            scores=scores,
            features=features,
            raw_response={"fake": True},
        )
