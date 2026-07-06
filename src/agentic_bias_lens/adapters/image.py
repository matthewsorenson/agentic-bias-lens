"""Image generation adapters.

Provider response shapes are best-effort and should be verified against the live
APIs before a keyed run (they are owner-gated). Every adapter runs finalize_image
so the returned file is stripped of metadata and carries the AI-GENERATED banner,
and records both prompt_original and prompt_as_sent.
"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

from ..capabilities import ImageRequest, ImageResult
from ..redaction import redact
from ..transports.base import Transport
from ..watermark import finalize_image

# Best-effort model/path mappings. Verify against live APIs.
GEMINI_IMAGE_MODEL = {"imagen-4-fast": "imagen-4.0-fast-generate-001"}
FAL_PATHS = {
    "seedream": "fal-ai/bytedance/seedream/v4/text-to-image",
    "qwen-image": "fal-ai/qwen-image",
}


def _write_image(
    images_dir, model_id, prompt_original, prompt_as_sent, seed, raw_request, data: bytes
) -> ImageResult:
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    tmp = images_dir / f"{token}.raw"
    tmp.write_bytes(data)
    final = images_dir / f"{model_id}_{token}.png"
    finalize_image(tmp, final)
    tmp.unlink(missing_ok=True)
    return ImageResult(
        image_path=final,
        prompt_original=prompt_original,
        prompt_as_sent=prompt_as_sent,
        model_id=model_id,
        seed=seed,
        raw_request=raw_request,
    )


class OpenAIImage:
    def __init__(self, id, base_url, api_key, images_dir, model, client=None):
        self.id = id
        self.model = model
        self.images_dir = images_dir
        self.transport = Transport(
            base_url,
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            client,
        )

    async def generate(self, req: ImageRequest) -> ImageResult:
        payload = {
            "model": self.model,
            "prompt": req.prompt,
            "size": req.size,
            "n": req.n,
            "response_format": "b64_json",
        }
        data = await self.transport.post("/images/generations", payload)
        raw = base64.b64decode(data["data"][0]["b64_json"])
        return _write_image(
            self.images_dir, self.id, req.prompt, req.prompt, req.seed, redact(payload), raw
        )


class GeminiImage:
    def __init__(self, id, base_url, api_key, images_dir, model, client=None):
        self.id = id
        self.model = model
        self.images_dir = images_dir
        self.transport = Transport(
            base_url, {"x-goog-api-key": api_key, "Content-Type": "application/json"}, client
        )

    async def generate(self, req: ImageRequest) -> ImageResult:
        payload = {"instances": [{"prompt": req.prompt}], "parameters": {"sampleCount": 1}}
        data = await self.transport.post(f"/models/{self.model}:predict", payload)
        raw = base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])
        return _write_image(
            self.images_dir, self.id, req.prompt, req.prompt, req.seed, redact(payload), raw
        )


class FalImage:
    def __init__(self, id, base_url, api_key, images_dir, fal_path, client=None):
        self.id = id
        self.fal_path = fal_path
        self.images_dir = images_dir
        self.transport = Transport(
            base_url,
            {"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
            client,
        )

    async def generate(self, req: ImageRequest) -> ImageResult:
        payload = {"prompt": req.prompt}
        data = await self.transport.post(f"/{self.fal_path}", payload)
        url = data["images"][0]["url"]
        raw = await self.transport.fetch_bytes(url)
        return _write_image(
            self.images_dir, self.id, req.prompt, req.prompt, req.seed, redact(payload), raw
        )


class DashscopeImage:
    """Native Alibaba route for Qwen-Image (optional). Verify shape against live API."""

    def __init__(self, id, base_url, api_key, images_dir, model, client=None):
        self.id = id
        self.model = model
        self.images_dir = images_dir
        self.transport = Transport(
            base_url,
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            client,
        )

    async def generate(self, req: ImageRequest) -> ImageResult:
        payload = {"model": self.model, "input": {"prompt": req.prompt}}
        data = await self.transport.post("/services/aigc/text2image/image-synthesis", payload)
        url = data["output"]["results"][0]["url"]
        raw = await self.transport.fetch_bytes(url)
        return _write_image(
            self.images_dir, self.id, req.prompt, req.prompt, req.seed, redact(payload), raw
        )


class ByteplusImage:
    """Native ByteDance route for Seedream (optional). Verify shape against live API."""

    def __init__(self, id, base_url, api_key, images_dir, model, client=None):
        self.id = id
        self.model = model
        self.images_dir = images_dir
        self.transport = Transport(
            base_url,
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            client,
        )

    async def generate(self, req: ImageRequest) -> ImageResult:
        payload = {"model": self.model, "prompt": req.prompt, "response_format": "url"}
        data = await self.transport.post("/images/generations", payload)
        item = data["data"][0]
        if item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])
        else:
            raw = await self.transport.fetch_bytes(item["url"])
        return _write_image(
            self.images_dir, self.id, req.prompt, req.prompt, req.seed, redact(payload), raw
        )
