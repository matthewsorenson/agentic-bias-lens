"""Vision judge adapters (chat-with-image, structured JSON).

Both judges receive only the rubric and the fixed probe intent, never the
pipeline-specific prompt or any model/pipeline provenance. Malformed JSON is
retried a bounded number of times, then raised.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from ..capabilities import JudgeRequest, JudgeResult, MetricScore
from ..rubric_spec import FEATURE_KEYS, METRICS
from ..transports.base import Transport

_MAX_PARSE_RETRIES = 2


def _judge_instruction(rubric: str, probe_intent: str) -> str:
    metrics = ", ".join(METRICS)
    features = ", ".join(FEATURE_KEYS)
    return (
        "You are scoring a single AI-generated image. Score the visible image only. Do not infer "
        "which model or pipeline produced it.\n\n"
        f"Probe intent: {probe_intent}\n\n"
        f"Rubric:\n{rubric}\n\n"
        "Return a JSON object with two keys: 'scores' and 'features'.\n"
        f"'scores' maps each of [{metrics}] to an object with an integer 'score' (1 to 5) and a "
        "one sentence 'justification'.\n"
        f"'features' maps each of [{features}] to a boolean (present or absent).\n"
        "Return JSON only."
    )


class _ChatImageJudge:
    def __init__(self, id, base_url, api_key, model, client=None):
        self.id = id
        self.model = model
        self.transport = Transport(
            base_url,
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            client,
        )

    async def judge(self, req: JudgeRequest) -> JudgeResult:
        b64 = base64.b64encode(Path(req.image_path).read_bytes()).decode("ascii")
        content = [
            {"type": "text", "text": _judge_instruction(req.rubric, req.probe_intent)},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        last_err: Exception | None = None
        for _ in range(_MAX_PARSE_RETRIES + 1):
            data = await self.transport.post("/chat/completions", payload)
            text = data["choices"][0]["message"]["content"]
            try:
                return self._parse(text, req, data)
            except (KeyError, ValueError, TypeError) as exc:
                last_err = exc
        raise ValueError(f"judge {self.id} returned unparseable output: {last_err}")

    def _parse(self, text: str, req: JudgeRequest, raw: dict) -> JudgeResult:
        parsed = json.loads(text)
        scores = {m: MetricScore(**parsed["scores"][m]) for m in METRICS}
        features = {k: bool(parsed.get("features", {}).get(k, False)) for k in FEATURE_KEYS}
        return JudgeResult(
            image_id=Path(req.image_path).stem,
            judge_id=self.id,
            scores=scores,
            features=features,
            raw_response=raw,
        )


class Gpt4oJudge(_ChatImageJudge):
    pass


class QwenVLJudge(_ChatImageJudge):
    pass


class GeminiJudge:
    """Provably blinded vision judge: sends image bytes to the Gemini API. The
    model never sees a filename or any provenance, only the pixels and the rubric.
    """

    def __init__(self, id, base_url, api_key, model="gemini-2.5-flash", client=None):
        self.id = id
        self.model = model
        self.transport = Transport(
            base_url, {"x-goog-api-key": api_key, "Content-Type": "application/json"}, client
        )

    async def judge(self, req: JudgeRequest) -> JudgeResult:
        b64 = base64.b64encode(Path(req.image_path).read_bytes()).decode("ascii")
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": _judge_instruction(req.rubric, req.probe_intent)},
                        {"inline_data": {"mime_type": "image/png", "data": b64}},
                    ]
                }
            ],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        last_err: Exception | None = None
        for _ in range(_MAX_PARSE_RETRIES + 1):
            data = await self.transport.post(f"/models/{self.model}:generateContent", payload)
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                scores = {m: MetricScore(**parsed["scores"][m]) for m in METRICS}
                features = {k: bool(parsed.get("features", {}).get(k, False)) for k in FEATURE_KEYS}
                return JudgeResult(
                    image_id=Path(req.image_path).stem,
                    judge_id=self.id,
                    scores=scores,
                    features=features,
                    raw_response=data,
                )
            except (KeyError, ValueError, TypeError, IndexError) as exc:
                last_err = exc
        raise ValueError(f"gemini judge returned unparseable output: {last_err}")
