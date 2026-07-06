"""Chat adapters. OpenAICompatChat serves OpenAI, Z.ai/GLM, and DashScope chat;
AnthropicChat is the one bespoke client (Messages API).
"""

from __future__ import annotations

import httpx

from ..capabilities import ChatRequest, ChatResult, Usage
from ..redaction import redact
from ..transports.base import Transport


class OpenAICompatChat:
    def __init__(
        self,
        id: str,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
    ):
        self.id = id
        self.model = model
        self.transport = Transport(
            base_url,
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            client,
        )

    async def complete(self, req: ChatRequest) -> ChatResult:
        payload = {
            "model": self.model,
            "messages": req.messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        if req.seed is not None:
            payload["seed"] = req.seed
        data = await self.transport.post("/chat/completions", payload)
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return ChatResult(
            text=text,
            model_id=self.id,
            raw_request=redact(payload),
            raw_response=data,
            usage=Usage(
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            ),
        )


class AnthropicChat:
    def __init__(
        self,
        id: str,
        api_key: str,
        model: str,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.id = id
        self.model = model
        self.transport = Transport(
            base_url or "https://api.anthropic.com",
            {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            client,
        )

    async def complete(self, req: ChatRequest) -> ChatResult:
        system = None
        messages = []
        for m in req.messages:
            if m.get("role") == "system":
                system = m.get("content")
            else:
                messages.append(m)
        payload = {
            "model": self.model,
            "max_tokens": req.max_tokens,
            "messages": messages,
            "temperature": req.temperature,
        }
        if system:
            payload["system"] = system
        data = await self.transport.post("/v1/messages", payload)
        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
        usage = data.get("usage") or {}
        return ChatResult(
            text=text,
            model_id=self.id,
            raw_request=redact(payload),
            raw_response=data,
            usage=Usage(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
            ),
        )
