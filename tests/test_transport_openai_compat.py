import httpx
import pytest
import respx

from agentic_bias_lens.adapters.chat import OpenAICompatChat
from agentic_bias_lens.capabilities import ChatRequest
from agentic_bias_lens.transports.base import AuthError

URL = "https://api.openai.com/v1/chat/completions"


def _chat():
    return OpenAICompatChat("gpt-4o", "https://api.openai.com/v1", "sk-secretkey123", "gpt-4o")


@respx.mock
async def test_maps_response_and_redacts():
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )
    )
    res = await _chat().complete(ChatRequest.from_prompt("hi"))
    assert res.text == "hello"
    assert res.usage.input_tokens == 5
    assert "sk-secretkey123" not in str(res.raw_request)


@respx.mock
async def test_retries_on_429_then_succeeds():
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(429, text="slow down"),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    res = await _chat().complete(ChatRequest.from_prompt("hi"))
    assert res.text == "ok"
    assert route.call_count == 2


@respx.mock
async def test_401_fails_fast_without_retry():
    route = respx.post(URL).mock(return_value=httpx.Response(401, text="bad key"))
    with pytest.raises(AuthError):
        await _chat().complete(ChatRequest.from_prompt("hi"))
    assert route.call_count == 1
