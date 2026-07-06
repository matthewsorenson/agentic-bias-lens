"""Key-aware capability registry: the single place that reads env and decides
what is available. Downstream code asks the registry for capabilities and never
touches os.environ. build(fake=True) wires the fake providers used by --dry-run
and the tests, so both exercise identical orchestration code.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from .capabilities import ChatModel, ImageModel, VisionJudge
from .config import Settings
from .fakes import FakeChat, FakeImage, FakeJudge

PROVIDER_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "zai": "ZAI_API_KEY",
    "fal": "FAL_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "byteplus": "BYTEPLUS_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class MissingProvider(RuntimeError):
    def __init__(self, model_id: str, provider: str):
        super().__init__(f"model '{model_id}' needs provider '{provider}' but its API key is absent")
        self.model_id = model_id
        self.provider = provider


class AvailabilityReport(BaseModel):
    available: list[str]
    missing: list[str]


class Registry:
    def __init__(
        self,
        settings: Settings,
        env: Mapping[str, str],
        *,
        fake: bool,
        images_dir: Path | None,
    ):
        self.settings = settings
        self.env = env
        self.fake = fake
        self.images_dir = Path(images_dir) if images_dir else Path("runs/_tmp/images")

    @classmethod
    def build(
        cls,
        settings: Settings,
        env: Mapping[str, str] | None = None,
        *,
        fake: bool = False,
        images_dir: str | Path | None = None,
    ) -> Registry:
        return cls(settings, dict(env or {}), fake=fake, images_dir=images_dir)

    # --- routing ---------------------------------------------------------

    def effective_provider(self, model_key: str) -> str:
        routes = self.settings.experiment.get("routes", {})
        if model_key in routes:
            return routes[model_key]
        return self.settings.resolve(model_key).provider

    def _has_key(self, provider: str) -> bool:
        if self.fake:
            return True
        return bool(self.env.get(PROVIDER_ENV.get(provider, "")))

    def _used_providers(self) -> set[str]:
        used: set[str] = set()
        for roster in self.settings.rosters.values():
            for role, mk in roster.items():
                if role == "family":
                    continue
                used.add(self.effective_provider(mk))
        for mk in self.settings.experiment["image_models"]:
            used.add(self.effective_provider(mk))
        for mk in self.settings.experiment["judges"]:
            used.add(self.effective_provider(mk))
        return used

    def availability_report(self) -> AvailabilityReport:
        used = self._used_providers()
        available = sorted(p for p in used if self._has_key(p))
        missing = sorted(p for p in used if not self._has_key(p))
        return AvailabilityReport(available=available, missing=missing)

    # --- capability access ----------------------------------------------

    def chat(self, model_id: str) -> ChatModel:
        self.settings.resolve(model_id)
        if self.fake:
            return FakeChat(model_id)
        provider = self.effective_provider(model_id)
        if not self._has_key(provider):
            raise MissingProvider(model_id, provider)
        return self._make_real("chat", model_id, provider)

    def image_models(self) -> list[ImageModel]:
        out: list[ImageModel] = []
        for mk in self.settings.experiment["image_models"]:
            if self.fake:
                out.append(FakeImage(mk, self.images_dir))
                continue
            provider = self.effective_provider(mk)
            if self._has_key(provider):
                out.append(self._make_real("image", mk, provider))
        return out

    def judges(self) -> list[VisionJudge]:
        out: list[VisionJudge] = []
        for mk in self.settings.experiment["judges"]:
            if self.fake:
                out.append(FakeJudge(mk))
                continue
            provider = self.effective_provider(mk)
            if self._has_key(provider):
                out.append(self._make_real("judge", mk, provider))
        return out

    def _make_real(self, kind: str, model_id: str, provider: str):
        # Real transports are added in Phase 5. Import lazily so the dry-run
        # spine builds and tests run without them.
        try:
            from .adapters.factory import make_capability
        except ImportError as exc:  # pragma: no cover - until Phase 5 lands
            raise NotImplementedError(
                f"real {kind} adapter for '{model_id}' not wired yet (Phase 5)"
            ) from exc
        spec = self.settings.resolve(model_id)
        api_key = self.env.get(PROVIDER_ENV[provider], "")
        return make_capability(kind, model_id, spec, provider, api_key, self.images_dir)
