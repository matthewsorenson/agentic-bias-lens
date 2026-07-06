"""Build the agent list for a condition from config. B and C read their roster;
A is empty; A_prime is a single verbose agent.
"""

from __future__ import annotations

from pathlib import Path

from .config import Settings
from .pipeline import Agent

CHAIN_ROLES = ("research", "accuracy", "bias", "finalizer", "guard")


def _load_template(config_dir: Path, name: str) -> str:
    return (Path(config_dir) / "prompts" / f"{name}.md").read_text(encoding="utf-8")


class PipelineBuilder:
    @staticmethod
    def from_config(settings: Settings, condition: str) -> list[Agent]:
        cd = settings.config_dir
        if condition == "A":
            return []
        if condition == "A_prime":
            model = settings.experiment.get("verbose_model", "claude-opus-4-8")
            return [Agent(role="verbose", model_id=model, template=_load_template(cd, "verbose"))]
        roster = settings.rosters[condition]
        return [
            Agent(role=role, model_id=roster[role], template=_load_template(cd, role))
            for role in CHAIN_ROLES
        ]
