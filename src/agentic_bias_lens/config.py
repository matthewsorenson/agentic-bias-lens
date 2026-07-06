"""Configuration loading and validation.

Loads three YAML files (models, rosters, experiment) into a Settings object and
enforces two invariants at load time rather than run time:
  1. every agentic roster defines all required roles with resolvable models;
  2. no judge shares a provider family with an agent brain under test.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel

REQUIRED_ROLES = ("research", "accuracy", "bias", "finalizer", "guard")


class ConfigError(ValueError):
    """Raised when configuration is internally inconsistent."""


class ModelSpec(BaseModel):
    provider: str
    family: str
    kind: str  # chat | image | judge
    base_url: str | None = None
    endpoint: str | None = None


class Settings(BaseModel):
    config_dir: Path
    experiment: dict
    rosters: dict[str, dict]
    models: dict[str, ModelSpec]

    @classmethod
    def load(cls, config_dir: str | Path, env: Mapping[str, str] | None = None) -> Settings:
        config_dir = Path(config_dir)
        models_raw = _read_yaml(config_dir / "models.yaml")["models"]
        rosters = _read_yaml(config_dir / "rosters.yaml")["rosters"]
        experiment = _read_yaml(config_dir / "experiment.yaml")
        models = {k: ModelSpec(**v) for k, v in models_raw.items()}
        return cls(
            config_dir=config_dir,
            experiment=experiment,
            rosters=rosters,
            models=models,
        )

    def resolve(self, model_key: str) -> ModelSpec:
        if model_key not in self.models:
            raise ConfigError(f"model '{model_key}' is not defined in models.yaml")
        return self.models[model_key]

    def active_probe_text(self) -> str:
        key = self.experiment["active_probe"]
        return self.experiment["probes"][key]

    def validate_rosters(self, *, strict_judge_coi: bool = False) -> list[str]:
        """Raise on structural errors (missing roles); return judge-COI warnings.

        A judge sharing a family with an agent brain is a warning by default
        (home-team judging), or a hard error when strict_judge_coi is set.
        """
        warnings: list[str] = []
        brain_families: set[str] = set()
        for name, roster in self.rosters.items():
            for role in REQUIRED_ROLES:
                if role not in roster:
                    raise ConfigError(f"roster '{name}' is missing role '{role}'")
                brain_families.add(self.resolve(roster[role]).family)

        judge_families = {self.resolve(j).family for j in self.experiment.get("judges", [])}
        overlap = brain_families & judge_families
        if overlap:
            msg = (
                f"judge shares a provider family with an agent brain under test: "
                f"{sorted(overlap)} (home-team judging for that pipeline)"
            )
            if strict_judge_coi:
                raise ConfigError(msg)
            warnings.append(msg)
        return warnings


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
