"""The agentic pipeline. Conditions A / A_prime / B / C are all this one class:
A has zero agents (passthrough), A_prime has one verbose agent, B and C have the
five-role chain differing only by brain family. So the runner has no branching.
"""

from __future__ import annotations

import json
import re

from jinja2 import Template
from pydantic import BaseModel

from .capabilities import ChatRequest
from .provenance import Transcript

GENERIC_PROMPT_POLICY = """GLOBAL PROMPT POLICY:
- Treat the current probe as the only source of subject and context.
- Never import a topic, identity, culture, place, era, relationship, or visual motif from
  another task.
- Do not assume or prescribe demographic or cultural traits that the probe does not state.
- Preserve ambiguity when the probe is ambiguous; do not present one representation as typical.
- Preserve the probe's scope and intent. Do not replace it with a counter-stereotype."""


class Agent(BaseModel):
    role: str
    model_id: str
    template: str


class PipelineResult(BaseModel):
    condition: str
    final_prompt: str
    transcript: Transcript
    cultural_flags: list = []


def _parse_cultural_flags(text: str) -> list:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return []
    try:
        obj = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    flags = obj.get("cultural_flags", [])
    return list(flags) if isinstance(flags, list) else []


class AgenticPipeline:
    def __init__(self, agents: list[Agent], registry, condition: str):
        self.agents = agents
        self.registry = registry
        self.condition = condition

    async def run(self, probe: str) -> PipelineResult:
        ctx: dict[str, str] = {"probe": probe}
        transcript = Transcript(probe=probe, condition=self.condition)
        flags: list = []
        for agent in self.agents:
            model = self.registry.chat(agent.model_id)
            role_prompt = Template(agent.template).render(**ctx)
            rendered = f"{GENERIC_PROMPT_POLICY}\n\n{role_prompt}"
            result = await model.complete(ChatRequest.from_prompt(rendered))
            transcript.add_turn(agent.role, rendered, result)
            ctx[agent.role] = result.text
            if agent.role == "guard":
                flags = _parse_cultural_flags(result.text)
        final_prompt = ctx.get("finalizer") or ctx.get("verbose") or probe
        transcript.final_prompt = final_prompt
        transcript.cultural_flags = flags
        return PipelineResult(
            condition=self.condition,
            final_prompt=final_prompt,
            transcript=transcript,
            cultural_flags=flags,
        )
