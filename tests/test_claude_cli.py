import asyncio

import pytest

import agentic_bias_lens.registry as reg_mod
from agentic_bias_lens.adapters.claude_cli import ClaudeCliChat
from agentic_bias_lens.capabilities import ChatRequest
from agentic_bias_lens.config import Settings
from agentic_bias_lens.registry import Registry


class _FakeProc:
    def __init__(self, out=b"", err=b"", code=0):
        self._out, self._err, self.returncode = out, err, code

    async def communicate(self, data=None):
        return (self._out, self._err)


async def test_claude_cli_reads_stdout(monkeypatch):
    async def fake_exec(*args, **kwargs):
        assert "--model" in args and "opus" in args  # opus alias for opus-4-8
        return _FakeProc(out=b"hello from the cli")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    chat = ClaudeCliChat("claude-opus-4-8", executable="claude")
    assert chat.model_alias == "opus"
    res = await chat.complete(ChatRequest.from_prompt("hi"))
    assert res.text == "hello from the cli"
    assert res.model_id == "claude-opus-4-8"


async def test_claude_cli_nonzero_exit_raises(monkeypatch):
    async def fake_exec(*args, **kwargs):
        return _FakeProc(err=b"boom", code=1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(RuntimeError):
        await ClaudeCliChat("claude-sonnet-5").complete(ChatRequest.from_prompt("hi"))


def _fake_which(name):
    return "/fake/claude" if name == "claude" else None


def test_registry_routes_anthropic_to_cli(config_dir, monkeypatch):
    monkeypatch.setattr(reg_mod.shutil, "which", _fake_which)
    s = Settings.load(config_dir)
    s.experiment["anthropic_backend"] = "cli"
    reg = Registry.build(s, env={}, fake=False)  # no anthropic API key
    assert reg.chat_available("claude-opus-4-8") is True
    assert reg.chat("claude-opus-4-8").__class__.__name__ == "ClaudeCliChat"


def test_registry_anthropic_unavailable_without_key_or_cli(config_dir, monkeypatch):
    monkeypatch.setattr(reg_mod.shutil, "which", lambda name: None)
    s = Settings.load(config_dir)
    s.experiment["anthropic_backend"] = "auto"
    reg = Registry.build(s, env={}, fake=False)
    assert reg.chat_available("claude-opus-4-8") is False
