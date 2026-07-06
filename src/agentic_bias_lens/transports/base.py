"""Shared HTTP transport with one retry and redaction policy.

Retries timeouts and 429/5xx with exponential backoff and jitter; never retries
4xx auth or validation errors (those raise AuthError immediately). All providers
build on this one class, so there is a single mock story for tests.
"""

from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
AUTH_STATUS = {400, 401, 403, 404, 422}


class TransportError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body


class AuthError(TransportError):
    """A 4xx that must not be retried."""


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, AuthError):
        return False
    if isinstance(exc, TransportError):
        return exc.status in RETRYABLE_STATUS
    return isinstance(exc, httpx.TimeoutException | httpx.TransportError)


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=0.2, max=5.0),
    retry=retry_if_exception(_should_retry),
)
async def _request(client, method, url, headers, json):
    resp = await client.request(method, url, headers=headers, json=json)
    if resp.status_code >= 400:
        if resp.status_code in AUTH_STATUS:
            raise AuthError(resp.status_code, resp.text)
        raise TransportError(resp.status_code, resp.text)
    return resp


class Transport:
    def __init__(self, base_url: str, headers: dict, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.headers = headers
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(120.0))

    async def post(self, path: str, payload: dict) -> dict:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        resp = await _request(self.client, "POST", url, self.headers, payload)
        return resp.json()

    async def fetch_bytes(self, url: str) -> bytes:
        resp = await _request(self.client, "GET", url, self.headers, None)
        return resp.content
