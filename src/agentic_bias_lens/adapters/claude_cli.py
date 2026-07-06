"""Anthropic chat and vision-judge via the local `claude` CLI (Claude Code
subscription), so Pipeline B and the US-lens judge run without an
ANTHROPIC_API_KEY. Slower than the API (one subprocess per call) but free.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from ..capabilities import ChatRequest, ChatResult, JudgeRequest, JudgeResult, MetricScore
from ..redaction import redact
from ..rubric_spec import FEATURE_KEYS, METRICS
from .judge import _judge_instruction

# Map our pinned ids to the CLI's tier aliases.
MODEL_ALIAS = {
    "claude-opus-4-8": "opus",
    "claude-sonnet-5": "sonnet",
    "claude-sonnet-judge": "sonnet",
}


async def _run_claude(executable: str, model_alias: str, prompt: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        executable,
        "-p",
        "--model",
        model_alias,
        "--output-format",
        "text",
        "--no-session-persistence",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate(prompt.encode("utf-8"))
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude cli failed (exit {proc.returncode}): {err.decode('utf-8', 'replace')[:200]}"
        )
    return out.decode("utf-8", "replace").strip()


def _render(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        parts.append(f"[system]\n{content}" if role == "system" else str(content))
    return "\n\n".join(parts)


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in claude cli output")
    return json.loads(match.group(0))


class ClaudeCliChat:
    def __init__(self, id: str, model_alias: str | None = None, executable: str = "claude"):
        self.id = id
        self.model_alias = model_alias or MODEL_ALIAS.get(id, id)
        self.executable = executable

    async def complete(self, req: ChatRequest) -> ChatResult:
        prompt = _render(req.messages)
        text = await _run_claude(self.executable, self.model_alias, prompt)
        return ChatResult(
            text=text,
            model_id=self.id,
            raw_request=redact(
                {"backend": "claude-cli", "model": self.model_alias, "prompt": prompt}
            ),
            raw_response={"backend": "claude-cli", "returncode": 0},
        )


class ClaudeCliJudge:
    """Vision judge: asks the claude CLI to read the image file and score it."""

    def __init__(self, id: str, model_alias: str | None = None, executable: str = "claude"):
        self.id = id
        self.model_alias = model_alias or MODEL_ALIAS.get(id, "sonnet")
        self.executable = executable

    async def judge(self, req: JudgeRequest) -> JudgeResult:
        image = Path(req.image_path).resolve()
        prompt = (
            f"{_judge_instruction(req.rubric, req.probe_intent)}\n\n"
            f"Read the image file at this exact path and score THAT image: {image}\n"
            "Return only the JSON object, no other text."
        )
        last_err: Exception | None = None
        for _ in range(3):
            text = await _run_claude(self.executable, self.model_alias, prompt)
            try:
                parsed = _extract_json(text)
                scores = {m: MetricScore(**parsed["scores"][m]) for m in METRICS}
                features = {k: bool(parsed.get("features", {}).get(k, False)) for k in FEATURE_KEYS}
                return JudgeResult(
                    image_id=image.stem,
                    judge_id=self.id,
                    scores=scores,
                    features=features,
                    raw_response={"backend": "claude-cli"},
                )
            except (KeyError, ValueError, TypeError) as exc:
                last_err = exc
        raise ValueError(f"claude cli judge returned unparseable output: {last_err}")
