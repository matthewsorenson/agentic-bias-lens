"""Anthropic chat via the local `claude` CLI (Claude Code subscription), so
Pipeline B can run without a separate ANTHROPIC_API_KEY. Slower than the API
(one subprocess per call) but free under the subscription.
"""

from __future__ import annotations

import asyncio

from ..capabilities import ChatRequest, ChatResult
from ..redaction import redact

# The CLI accepts tier aliases; map our pinned ids to them.
MODEL_ALIAS = {"claude-opus-4-8": "opus", "claude-sonnet-5": "sonnet"}


def _render(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        parts.append(f"[system]\n{content}" if role == "system" else str(content))
    return "\n\n".join(parts)


class ClaudeCliChat:
    def __init__(self, id: str, model_alias: str | None = None, executable: str = "claude"):
        self.id = id
        self.model_alias = model_alias or MODEL_ALIAS.get(id, id)
        self.executable = executable

    async def complete(self, req: ChatRequest) -> ChatResult:
        prompt = _render(req.messages)
        args = [
            self.executable,
            "-p",
            "--model",
            self.model_alias,
            "--output-format",
            "text",
            "--no-session-persistence",
        ]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate(prompt.encode("utf-8"))
        if proc.returncode != 0:
            detail = err.decode("utf-8", "replace")[:200]
            raise RuntimeError(f"claude cli failed (exit {proc.returncode}): {detail}")
        return ChatResult(
            text=out.decode("utf-8", "replace").strip(),
            model_id=self.id,
            raw_request=redact(
                {"backend": "claude-cli", "model": self.model_alias, "prompt": prompt}
            ),
            raw_response={"backend": "claude-cli", "returncode": 0},
        )
