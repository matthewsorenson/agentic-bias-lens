import httpx
import respx

from agentic_bias_lens.adapters.chat import AnthropicChat
from agentic_bias_lens.capabilities import ChatRequest


@respx.mock
async def test_anthropic_messages_maps_to_chat_result():
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "hi from claude"}],
                "usage": {"input_tokens": 3, "output_tokens": 4},
            },
        )
    )
    chat = AnthropicChat("claude-opus-4-8", "sk-ant-key", model="claude-opus-4-8")
    res = await chat.complete(ChatRequest.from_prompt("hello"))
    assert res.text == "hi from claude"
    assert res.usage.output_tokens == 4
    assert res.model_id == "claude-opus-4-8"
