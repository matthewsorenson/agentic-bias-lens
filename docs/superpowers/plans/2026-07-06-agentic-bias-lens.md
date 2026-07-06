# agentic-bias-lens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mock-runnable, tested, public-repo-ready Python system that compares naive vs agentic image-generation prompting for cultural bias across US and Chinese models, with Anthropic vs GLM agent brains and cross-cultural vision judges.

**Architecture:** Three capability protocols (`ChatModel`, `ImageModel`, `VisionJudge`) with a key-aware registry; a single `AgenticPipeline` parameterized by a YAML roster (conditions A, A', B, C); provenance carried on result types; a `--dry-run` fake-provider path that is the CI-green, keyless spine and the test path. Real HTTP transports are added last and are owner-gated.

**Tech Stack:** Python 3.12, httpx, pydantic v2, pydantic-settings, tenacity, jinja2, pyyaml, pillow; pytest, pytest-asyncio, respx, syrupy; ruff, uv.

## Global Constraints

- Python 3.12; dependency manager `uv` with committed `uv.lock`.
- No vendor SDKs. All providers via one shared `httpx.AsyncClient` base.
- Provenance is a return-type obligation: every result carries key-redacted `raw_request`, `raw_response`, `model_id`; image results carry both `prompt_original` and `prompt_as_sent`.
- All recorded JSON written with `sort_keys=True` and stable float formatting; newline-terminated.
- Secrets never committed: `.env` gitignored, `.env.example` placeholders only, gitleaks in pre-commit and CI, redaction pass on everything written to `runs/`.
- `runs/` gitignored; a test fails if any image file is committed under it.
- Every surfaced image carries a burned-in watermark "AI-GENERATED, not authentic Haida imagery".
- Findings and headers say "the model rendered X", never "the Haida ...".
- Model ids are data in `config/models.yaml`, never string literals in `.py`.
- Repo docs in the owner's voice use no em dashes.
- Model ids: Anthropic `claude-opus-4-8` (research, finalizer), `claude-sonnet-5` (accuracy, bias, guard); GLM `glm-5.2` (research, finalizer), `glm-4.7` (accuracy, bias, guard); images `gpt-image-1`, Imagen 4 Fast, Seedream (fal default), Qwen-Image (fal default); judges `gpt-4o`, Qwen-VL.
- Concurrency default 2 to 3 per provider host; tenacity backoff on 429/5xx/timeout; never retry 4xx auth or validation.

---

## Phase 0 — Scaffold and contracts

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `uv.lock`, `Makefile`, `.gitignore`, `.gitattributes`, `.env.example`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `ruff.toml`, `src/agentic_bias_lens/__init__.py`, `tests/conftest.py`, `tests/test_smoke.py`

**Interfaces:**
- Produces: an installable package `agentic_bias_lens`; `make setup`, `make test`, `make lint`, `make mock` targets.

- [ ] Step 1: Write `pyproject.toml` with runtime and dev deps (see Tech Stack) and a `[project.scripts] abl = "agentic_bias_lens.cli:main"` entry.
- [ ] Step 2: Write `.gitignore` (`.env`, `.env.*` except `.env.example`, `runs/`, `*.png`, `*.jpg`, `*.jpeg`, `*.webp`, `__pycache__/`, `.venv/`, `.pytest_cache/`, `*.pyc`), with a negation for `examples/**` placeholder tiles.
- [ ] Step 3: Write `.gitattributes` (`* text=auto eol=lf`) to stop CRLF churn.
- [ ] Step 4: Write `tests/test_smoke.py` with `def test_import(): import agentic_bias_lens`.
- [ ] Step 5: Run `uv sync` then `uv run pytest tests/test_smoke.py -v`. Expected: PASS.
- [ ] Step 6: Write `.github/workflows/ci.yml` (jobs: test = `uv sync --frozen`, `ruff check`, `pytest`, `python -m agentic_bias_lens --dry-run`; secret-scan = gitleaks). No `secrets:` block.
- [ ] Step 7: Commit `chore: project scaffold`.

### Task 2: Capability protocols and provenance-carrying models

**Files:**
- Create: `src/agentic_bias_lens/capabilities.py`
- Test: `tests/test_capabilities.py`

**Interfaces:**
- Produces (the shared contract every later task consumes):

```python
from pathlib import Path
from typing import Protocol, runtime_checkable
from pydantic import BaseModel

class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None

class ChatRequest(BaseModel):
    messages: list[dict]          # OpenAI-style [{"role","content"}]
    temperature: float = 0.7
    seed: int | None = None
    max_tokens: int = 2048
    @classmethod
    def from_prompt(cls, prompt: str, **kw) -> "ChatRequest": ...

class ChatResult(BaseModel):
    text: str
    model_id: str
    raw_request: dict            # key-redacted
    raw_response: dict
    usage: Usage | None = None

class ImageRequest(BaseModel):
    prompt: str
    seed: int | None = None
    size: str = "1024x1024"
    n: int = 1

class ImageResult(BaseModel):
    image_path: Path             # written under runs/<ts>/images, watermarked
    prompt_original: str
    prompt_as_sent: str
    model_id: str
    seed: int | None
    raw_request: dict
    provenance: str = "synthetic"
    not_authentic: bool = True

class JudgeRequest(BaseModel):
    image_path: Path
    rubric: str
    probe_intent: str            # NOT the pipeline prompt (blinding)

class MetricScore(BaseModel):
    score: int                   # 1..5
    justification: str

class JudgeResult(BaseModel):
    image_id: str
    judge_id: str
    scores: dict[str, MetricScore]
    features: dict[str, bool]    # binary checklist detections
    raw_response: dict

@runtime_checkable
class ChatModel(Protocol):
    id: str
    async def complete(self, req: ChatRequest) -> ChatResult: ...

@runtime_checkable
class ImageModel(Protocol):
    id: str
    async def generate(self, req: ImageRequest) -> ImageResult: ...

@runtime_checkable
class VisionJudge(Protocol):
    id: str
    async def judge(self, req: JudgeRequest) -> JudgeResult: ...
```

- [ ] Step 1: Write `tests/test_capabilities.py` asserting `ChatRequest.from_prompt("hi").messages == [{"role":"user","content":"hi"}]`, that `MetricScore(score=6)` raises (range validator 1..5), and that `ImageResult` requires both `prompt_original` and `prompt_as_sent`.
- [ ] Step 2: Run tests. Expected: FAIL (module missing).
- [ ] Step 3: Implement `capabilities.py` as above with a field validator constraining `MetricScore.score` to 1..5.
- [ ] Step 4: Run tests. Expected: PASS.
- [ ] Step 5: Commit `feat: capability protocols and provenance models`.

### Task 3: Redaction

**Files:**
- Create: `src/agentic_bias_lens/redaction.py`
- Test: `tests/test_redaction.py`

**Interfaces:**
- Produces: `redact(obj: dict | str) -> same type` stripping `authorization`, `x-api-key`, `api-key` headers (case-insensitive), `?key=`/`?token=` query params, and `sk-`/`Bearer ` token patterns, replacing with `***REDACTED***`.

- [ ] Step 1: Write test: `redact({"headers":{"Authorization":"Bearer sk-abc"}})` yields `***REDACTED***`; a nested dict and a URL `https://x?key=sk-abc` are both redacted; a clean dict is unchanged.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement recursive `redact` over dict/list/str.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: secret redaction pass`.

### Task 4: Config loading and validation

**Files:**
- Create: `src/agentic_bias_lens/config.py`, `config/experiment.yaml`, `config/rosters.yaml`, `config/models.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings.load(config_dir: Path, env: Mapping) -> Settings` with `.experiment`, `.rosters`, `.models`; `Settings.validate_rosters()` raising if a role is missing, a model is unresolvable, or a judge shares a provider family with a brain under test. `models.yaml` holds `id`, `provider`, `base_url`, `endpoint`, `family` per model. `rosters.yaml` maps `B`/`C` -> role -> model key. `experiment.yaml` holds `probes`, `conditions`, `k_prompt`, `k_img`, `judges`, `research_mode`, provider route switches.

- [ ] Step 1: Write the three YAML files per the spec (roster table in section 5, models in section 6, probes in section 4.1).
- [ ] Step 2: Write test: loading resolves roster `B.research` to `claude-opus-4-8`; a roster missing `guard` raises; a judge set including `claude-*` raises the COI check.
- [ ] Step 3: Run. Expected: FAIL.
- [ ] Step 4: Implement `config.py` (pydantic-settings + pyyaml).
- [ ] Step 5: Run. Expected: PASS.
- [ ] Step 6: Commit `feat: config loading and roster validation`.

---

## Phase 1 — Fakes, registry, provenance, watermark (the dry-run spine)

### Task 5: Fake providers

**Files:**
- Create: `src/agentic_bias_lens/fakes/fake_providers.py`
- Test: `tests/test_fakes.py`

**Interfaces:**
- Consumes: capabilities (Task 2).
- Produces: `FakeChat(id, role_marker)`, `FakeImage(id, reshape=False)`, `FakeJudge(id, bias=0)` implementing the protocols deterministically. `FakeChat.complete` returns role-aware text keyed off a marker in the prompt; `FakeImage.generate` writes a deterministic placeholder PNG and sets `prompt_as_sent` (reshaped if `reshape`); `FakeJudge.judge` returns scores derived from `image_id` hash so aggregation is hand-checkable.

- [ ] Step 1: Write test: `FakeImage(reshape=True)` returns `prompt_as_sent != prompt_original`, both populated; `FakeJudge` returns 6 metric scores in 1..5 and the binary feature dict; `FakeChat` populates redacted `raw_request`.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement fakes (write PNGs via pillow to a passed dir).
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: deterministic fake providers`.

### Task 6: Key-aware registry

**Files:**
- Create: `src/agentic_bias_lens/registry.py`
- Test: `tests/test_registry_degradation.py`

**Interfaces:**
- Consumes: config (Task 4), fakes (Task 5), capabilities (Task 2).
- Produces: `Registry.build(settings, env, *, fake=False) -> Registry`; `.chat(model_id) -> ChatModel` (raises `MissingProvider`); `.image_models() -> list[ImageModel]`; `.judges() -> list[VisionJudge]`; `.availability_report() -> AvailabilityReport` (`available: list[str]`, `missing: list[str]`). `fake=True` registers fakes for all and reports all available.

- [ ] Step 1: Write test: `build(fake=True)` reports all providers available and returns 4 image models + 2 judges; `build(env={"OPENAI_API_KEY":...})` (real mode, subset) reports only OpenAI available and `image_models()` excludes the others; `.chat("glm-5.2")` with no GLM key raises `MissingProvider`.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement registry (env-key map per provider; register capability only if key present).
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: key-aware capability registry with graceful degradation`.

### Task 7: Provenance, transcript, and artifact writers

**Files:**
- Create: `src/agentic_bias_lens/provenance.py`
- Test: `tests/test_provenance.py`

**Interfaces:**
- Consumes: capabilities (Task 2).
- Produces: `Transcript(probe)` with `.add_turn(role, rendered_prompt, ChatResult)`; `write_prompts(run_dir, transcripts, image_results) -> None` producing `prompts.json` and `prompts.md`; `write_manifest(run_dir, ManifestData) -> None`; a `dump_json(obj, path)` helper (`sort_keys=True`, `indent=2`, trailing newline, stable floats). `ManifestData` includes git sha, dirty flag, model ids/endpoints, seed, probes, available/skipped providers, lib versions.

- [ ] Step 1: Write test: after adding two turns and one image result, `prompts.json` contains the verbatim probe, both turns in order, and the image's `prompt_as_sent`; `dump_json` output is byte-identical across two calls (determinism); manifest contains a `git_sha` key.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement provenance writers.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: provenance transcript and artifact writers`.

### Task 8: Watermark and clean re-encode

**Files:**
- Create: `src/agentic_bias_lens/watermark.py`
- Test: `tests/test_watermark.py`

**Interfaces:**
- Produces: `watermark(src: Path, dst: Path, text=DEFAULT_BANNER) -> Path` (burn a banner via pillow) and `strip_and_reencode(src: Path, dst: Path) -> Path` (drop EXIF/metadata, re-encode PNG). `DEFAULT_BANNER = "AI-GENERATED, not authentic Haida imagery"`.

- [ ] Step 1: Write test: `watermark` output opens, has the same or larger size, and has no EXIF; `strip_and_reencode` output has empty `info` metadata.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement with pillow (draw banner strip bottom, save without exif).
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: image watermark and metadata strip`.

---

## Phase 2 — Pipeline and agents

### Task 9: Agent, PipelineBuilder, AgenticPipeline

**Files:**
- Create: `src/agentic_bias_lens/agents.py`, `src/agentic_bias_lens/pipeline.py`
- Test: `tests/test_pipeline_shared_impl.py`

**Interfaces:**
- Consumes: registry (Task 6), provenance (Task 7), capabilities (Task 2), config (Task 4).
- Produces: `Agent(role, model_id, prompt_template)`; `PipelineBuilder.from_config(settings, condition) -> list[Agent]` (A -> [], A' -> [verbose], B/C -> 5 agents from roster); `AgenticPipeline(agents, registry).run(probe) -> PipelineResult(final_prompt, transcript, cultural_flags)`. Chain is sequential; each turn recorded.

- [ ] Step 1: Write test (with `fake=True` registry): B and C both run through `AgenticPipeline.run`, produce a 5-turn transcript in role order `[research, accuracy, bias, finalizer, guard]`, differ only by `model_id`s; condition A returns `final_prompt == probe` with an empty transcript; A' returns one turn.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement `agents.py` and `pipeline.py`; render templates with jinja2; accumulate `ctx[role] = result.text`; `final_prompt = ctx["finalizer"]`; parse `cultural_flags` from the guard turn.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: config-driven agentic pipeline shared by conditions`.

### Task 10: Prompt templates and rubric

**Files:**
- Create: `config/prompts/research.md`, `accuracy.md`, `bias.md`, `finalizer.md`, `guard.md`, `verbose.md`, `config/rubric.md`, `docs/sources.md`
- Test: `tests/test_prompts_present.py`

**Interfaces:**
- Produces: role templates (jinja2) embedding the sacred-content exclusion list in finalizer and guard; guard emits a JSON block with `cultural_flags`; `rubric.md` holds the 6 anchored 1/3/5 scales, the binary feature checklist, and the fixed ground-truth Haida-accuracy reference.

- [ ] Step 1: Write test: all template files exist and load; `guard.md` contains "cultural_flags"; `finalizer.md` and `guard.md` contain the exclusion phrase "no potlatch or ceremony"; `rubric.md` contains all 6 metric names and the feature checklist keys.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Author the templates and rubric per spec sections 3, 5, 7 (no em dashes; findings language "the model rendered X").
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: agent prompt templates, rubric, sources`.

---

## Phase 3 — Scoring and reliability

### Task 11: Scoring (blinded judge fan-out and aggregation)

**Files:**
- Create: `src/agentic_bias_lens/scoring.py`
- Test: `tests/test_scoring_aggregation.py`

**Interfaces:**
- Consumes: capabilities, registry, watermark (for strip), provenance.
- Produces: `score_images(images: list[ImageResult], judges, rubric, probe_intent, *, seed) -> ScoringTable`. Blinds each image (strip/re-encode to a UUID temp), randomizes order per judge with `seed`, scores against `probe_intent`, validates JSON, computes `overall` by a fixed weighted formula outside the judge. `ScoringTable` supports `.by_model_condition()` and `.raw()`.

- [ ] Step 1: Write test (fake judges): 12 images x 2 judges yields 24 verdicts; every metric in 1..5; `overall` equals the fixed formula of the other five; the provenance map maps UUID back to `(model, condition)` and is never passed to the judge; aggregation over a cell returns mean and n.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement scoring with blinding and aggregation.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: blinded judge scoring and aggregation`.

### Task 12: Reliability statistics

**Files:**
- Create: `src/agentic_bias_lens/reliability.py`
- Test: `tests/test_reliability.py`

**Interfaces:**
- Produces: `krippendorff_alpha(pairs, level="ordinal") -> float`; `spearman(a, b) -> float`; `mean_abs_diff(a, b) -> float`; `self_preference_delta(scores, vendor_map, human_baseline=None) -> dict`. Pure functions over lists.

- [ ] Step 1: Write test: perfect-agreement input gives alpha == 1.0; perfectly reversed gives spearman == -1.0; `mean_abs_diff([1,2],[1,4]) == 1.0`; a same-vendor inflation produces a positive self-preference delta.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement (numpy; vetted Krippendorff for two raters ordinal).
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: inter-rater reliability and self-preference stats`.

---

## Phase 4 — Orchestration, reporting, CLI (completes the dry-run spine)

### Task 13: Runner (concurrency, cache, degradation)

**Files:**
- Create: `src/agentic_bias_lens/runner.py`
- Test: `tests/test_concurrency_and_retry.py`, `tests/test_dry_run_e2e.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `run_experiment(settings, registry, run_dir, *, force=False) -> RunResult`. Builds prompts for all active conditions (B/C pipelines concurrent; chain sequential), fans out image generation (per-provider semaphore), caches cells by content hash, scores, writes all artifacts. Skips providers absent from `availability_report`.

- [ ] Step 1: Write `test_dry_run_e2e`: with `fake=True`, `run_experiment` produces a `runs/<ts>/` containing `manifest.json`, `prompts.json`, `prompts.md`, `scores.json`, watermarked images, `report.md`, `contact_sheet.html`; image count == conditions x models x k_img; snapshot the report with a frozen clock (syrupy).
- [ ] Step 2: Write `test_concurrency_and_retry`: an instrumented fake records that the agent chain turns are strictly ordered while image calls overlap; a fake raising 429 twice then succeeding is retried; a 401 fake fails fast and marks the provider unavailable; a second `run_experiment` call reuses cached cells (no new image writes) unless `force=True`.
- [ ] Step 3: Run. Expected: FAIL.
- [ ] Step 4: Implement runner with `asyncio.gather`, `asyncio.Semaphore` per provider, and the cache keyed on `hash(condition, image_model, as_sent_prompt, sample_index)`.
- [ ] Step 5: Run. Expected: PASS.
- [ ] Step 6: Commit `feat: experiment runner with concurrency, cache, degradation`.

### Task 14: Report and contact sheet

**Files:**
- Create: `src/agentic_bias_lens/report.py`, `src/agentic_bias_lens/templates/report.md.j2`, `contact_sheet.html.j2`
- Test: `tests/test_report.py`

**Interfaces:**
- Produces: `write_report(run_dir, scoring_table, transcripts, reliability) -> None` producing `report.md` (aggregate tables: within-model across conditions, brain-vs-brain, US-vs-CN judge disagreement, reliability, self-preference) and `contact_sheet.html` (each image captioned with its exact `prompt_as_sent`, watermark visible). Headers use "model output for probe P" language.

- [ ] Step 1: Write test: report contains a row per (model, condition), a "US vs CN judge disagreement" section, and no occurrence of the string "the Haida are"/"the Haida wear"; contact sheet references each image by relative path with its `prompt_as_sent` caption.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement jinja2 report and contact sheet.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: markdown report and HTML contact sheet`.

### Task 15: CLI

**Files:**
- Create: `src/agentic_bias_lens/cli.py`, `src/agentic_bias_lens/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `main(argv=None) -> int`; flags `--dry-run`, `--pipelines B,C`, `--models`, `--force`, `--config-dir`, `--out`. `--dry-run` builds a `fake=True` registry and calls `run_experiment`.

- [ ] Step 1: Write test: `main(["--dry-run","--out",tmp])` returns 0 and creates a run dir with a report; `python -m agentic_bias_lens --dry-run` importable path works.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement argparse CLI.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: CLI with dry-run`.

---

## Phase 5 — Real transports (owner-gated wire; parallelizable after contracts)

### Task 16: Base transport and OpenAI-compatible chat

**Files:**
- Create: `src/agentic_bias_lens/transports/base.py`, `transports/openai_compat.py`, `src/agentic_bias_lens/adapters/chat.py`
- Test: `tests/test_transport_openai_compat.py` (respx), `tests/fixtures/openai_chat.json`

**Interfaces:**
- Produces: `Transport(base_url, headers, client)` with `_post(path, payload)` wrapped in tenacity (backoff on 429/5xx/timeout, no retry on 4xx) and redaction of `raw_request`; `OpenAICompatChat(base_url, api_key, model, id)` implementing `ChatModel`; serves OpenAI, Z.ai/GLM, DashScope chat.
- Consumes: capabilities (Task 2), redaction (Task 3).

- [ ] Step 1: Write respx test: a mocked `/chat/completions` returns a fixture; `OpenAICompatChat.complete` maps it to `ChatResult` with redacted `raw_request` and correct `text`; a 429-then-200 sequence is retried; a 401 raises without retry.
- [ ] Step 2: Run. Expected: FAIL.
- [ ] Step 3: Implement base + openai_compat + chat adapter.
- [ ] Step 4: Run. Expected: PASS.
- [ ] Step 5: Commit `feat: base transport and OpenAI-compatible chat adapter`.

### Task 17: Anthropic chat adapter

**Files:**
- Create: `src/agentic_bias_lens/transports/anthropic.py`
- Test: `tests/test_transport_anthropic.py`, `tests/fixtures/anthropic_messages.json`

**Interfaces:**
- Produces: `AnthropicChat(api_key, model, id)` implementing `ChatModel` against the Messages API (system top-level, `max_tokens` required, content blocks).

- [ ] Step 1: Write respx test mapping a Messages fixture to `ChatResult`.
- [ ] Step 2..5: Fail, implement, pass, commit `feat: anthropic chat adapter`.

### Task 18: Image adapters

**Files:**
- Create: `src/agentic_bias_lens/transports/gemini.py`, `transports/fal.py`, `transports/byteplus.py`, `transports/dashscope.py`, `src/agentic_bias_lens/adapters/image.py`
- Test: `tests/test_transport_images.py`, `tests/fixtures/{openai_image,gemini_image,fal_seedream,fal_qwen}.json`

**Interfaces:**
- Produces: four `ImageModel` impls (OpenAI images via openai_compat transport; Gemini; Seedream via fal default / byteplus optional; Qwen-Image via fal default / dashscope optional). Each writes bytes, then `strip_and_reencode` then `watermark`, and returns `ImageResult` with both prompt strings. Route selected by config switch.

- [ ] Step 1: Write respx tests: each adapter maps its fixture to a written PNG and correct `prompt_as_sent`; the route switch selects fal vs native.
- [ ] Step 2..5: Fail, implement, pass, commit `feat: image generation adapters (fal default for CN models)`.

### Task 19: Judge adapters

**Files:**
- Create: `src/agentic_bias_lens/adapters/judge.py`
- Test: `tests/test_transport_judges.py`, `tests/fixtures/{gpt4o_judge,qwenvl_judge}.json`

**Interfaces:**
- Produces: `Gpt4oJudge` (openai_compat transport, chat-with-image + JSON schema) and `QwenVLJudge` (dashscope or fal), both implementing `VisionJudge`, returning validated `JudgeResult`.

- [ ] Step 1: Write respx tests mapping judge fixtures to `JudgeResult` with all 6 metrics and features; malformed JSON triggers a bounded retry.
- [ ] Step 2..5: Fail, implement, pass, commit `feat: vision judge adapters`.

---

## Phase 6 — Docs, example, hygiene, green

### Task 20: Public docs

**Files:**
- Create: `README.md`, `NOTICE.md`, `ETHICS.md`, `LICENSE`

**Interfaces:**
- Produces: README per spec section 11 checklist (ethics note near top; Mermaid diagram; key table; mock-first run instructions; reproducibility caveat; limitations; license split); MIT `LICENSE`; `NOTICE.md` (generated images and cultural content usage statement); `ETHICS.md` (the disclaimer, OCAP/CARE, sacred exclusion, takedown invitation, land acknowledgement marked "verify with a Haida source"). No em dashes.

- [ ] Step 1: Write all four docs.
- [ ] Step 2: Grep the docs for " — " (em dash) and "the Haida are"/"the Haida wear"; expect zero.
- [ ] Step 3: Commit `docs: README, NOTICE, ETHICS, LICENSE`.

### Task 21: Committed mock-run example and the no-images guard

**Files:**
- Create: `examples/mock-run/**` (generated), `examples/README.md`, `tests/test_no_images_committed.py`
- Test: `tests/test_no_images_committed.py`

**Interfaces:**
- Produces: a committed mock run (real manifest/prompts/scores/report/HTML) with REDACTED placeholder tiles; a test that walks the git-tracked tree and fails if any image file appears under `runs/` or any non-placeholder image appears under `examples/`.

- [ ] Step 1: Run `abl --dry-run --out examples/mock-run` to generate artifacts; replace image tiles with a committed "REDACTED, see ETHICS.md" placeholder PNG.
- [ ] Step 2: Write `test_no_images_committed` using `git ls-files` to assert no image under `runs/` and only the placeholder under `examples/`.
- [ ] Step 3: Run. Expected: PASS.
- [ ] Step 4: Commit `chore: committed mock-run example and no-images guard`.

### Task 22: Final green and lock

**Files:**
- Modify: `uv.lock`, `README.md` (CI badge)

- [ ] Step 1: `uv run ruff check .` clean; `uv run pytest` all green; `uv run python -m agentic_bias_lens --dry-run` produces a run.
- [ ] Step 2: `pre-commit run --all-files` (gitleaks) clean.
- [ ] Step 3: Add CI badge to README.
- [ ] Step 4: Commit `chore: lockfile, CI badge, green build`.

---

## Self-review notes

- Spec coverage: ethics (Tasks 8, 10, 14, 20, 21), sampling/conditions (Tasks 4, 9, 13), blinding and rubric (Tasks 10, 11), reliability and self-preference (Task 12), transparency/provenance (Tasks 2, 3, 7), architecture/registry/transports (Tasks 2, 6, 16 to 19), cost/cache/degradation (Tasks 6, 13), repo hygiene (Tasks 1, 20, 21, 22). All spec sections map to a task.
- Type consistency: `ChatResult`, `ImageResult`, `JudgeResult`, `AgenticPipeline.run`, `run_experiment`, `Registry.build` names used consistently across tasks.
- Placeholder scan: interface signatures and test intents are concrete; leaf adapter tasks (17 to 19) share the respx pattern established fully in Task 16.
