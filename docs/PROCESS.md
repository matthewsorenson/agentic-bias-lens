# agentic-bias-lens: the whole process

This document narrates how the project was conceived, designed, hardened, built, and validated. It is
written to be read on its own, so it repeats a little of what lives in the spec and the README. If
you only read one document to understand what this project is and how it came to be, read this one.

## 1. What this is, in one paragraph

`agentic-bias-lens` measures whether wrapping image generation in an agentic prompt pipeline
(research, then accuracy, then bias detection, then a finalizer, then a cultural guard) changes the
cultural bias of the resulting images, compared to a naive single call, and whether the reasoning
model family driving those agents (Anthropic vs GLM) changes the outcome. The subject is a
deliberately hard case: depicting the daily life of the Haida Nation of Haida Gwaii, British
Columbia, where AI image models tend to collapse a specific Northwest Coast culture into a generic
Plains stereotype. The engineering is the deliverable. The report it produces feeds a written
reflection.

## 2. The assignment and the decision to go system-first

The origin was a course assignment: interact with two or three AI tools using the same prompt,
identify biases and blind spots, and reflect on how they show up in the real world and how to address
them. Most people satisfy this with screenshots and an essay. The choice here was to go system-first:
build a real comparison engine whose output is the evidence, and whose very design demonstrates a
mitigation strategy (the agentic pipeline) while also exposing the ways that strategy can fail (bias
laundering, judge disagreement). The reflection then writes itself from the report.

That decision set the bar. A system-first project has to be a real experiment, not a demo, or it
fails the actual assignment (which is about the analysis, not the code).

## 3. The core question

Hold the prompt constant and vary how it is delivered:

- A naive one-shot call sends the bare prompt straight to the image model.
- An agentic pipeline researches the subject, checks accuracy, flags likely bias, and writes a
  detailed corrected prompt before generating.

Run both across US and Chinese image models, and score the results with cross-cultural vision judges.
The question: does the agentic scaffold reduce stereotyping and increase cultural specificity, or
does it just add words? And does a Western vs a Chinese reasoning model correct differently?

## 4. How the design was built: a multiagent design review

Before writing code, the design was pressure-tested by six specialist reviewers working in parallel,
each with a single lens. This was not ceremony. Each reviewer materially changed the design.

- **Experimental methodology.** Caught the fatal flaw: one image per cell is n=1, and bias is a
  distribution, not a single draw. You cannot claim "the agentic pipeline reduced bias" from one
  picture. It also identified the biggest missing control (see A_prime below) and pushed the rubric
  from vibes-based 1 to 5 scores toward an auditable binary feature checklist.
- **Representation ethics.** Reframed the whole project. OCAP and CARE exist to stop outsiders
  producing representations of a Nation without its authority, and synthetic images are arguably the
  sharpest case. This turned "generate images of the Haida" into "document how AI systems depict a
  subject," and produced hard rules: never commit generated images, watermark everything, exclude
  sacred content, and add a present-day probe so the "frozen in the past" trope is measured rather
  than reproduced.
- **Software architecture.** Proposed three capability protocols instead of six provider adapters,
  one shared OpenAI-compatible transport, and a single pipeline class parameterized by a roster so
  conditions do not fork the code. Also proposed the mock layer that makes the whole thing runnable
  and testable without keys.
- **Judge methodology.** Flagged that vendor self-preference falls exactly along the axis being
  measured (a US judge sharing a vendor with a US image model), and required blinding, an anchored
  rubric, inter-rater agreement statistics, and a plan to measure judge bias rather than assume it
  away.
- **Cost and operations.** Found that the two Chinese image models are available through the fal.ai
  aggregator, which removes the two hardest native signups from the critical path, and estimated the
  whole project at coffee-money cost.
- **Repository hygiene.** Locked the secret-safety and commit policy: gitignore real runs, commit one
  redacted mock run as the public example, split the code license from an image and cultural-content
  usage statement, and make the mock run the CI-green spine.

The reviews converged on one structural idea that shaped everything: the mock layer is the committed,
CI-verified, publicly runnable spine, and the one committed example is a mock run.

## 5. The hardened experimental design

Four conditions, all starting from the same probe and feeding the same image models:

- **A, one-shot.** The bare probe. Reveals raw model bias.
- **A_prime, verbose-naive control.** One model call expands the probe into a long, richly detailed
  prompt with no bias reasoning. This isolates verbosity from agentic reasoning. Without it, any
  improvement from A to B could be explained by "the prompt got longer," and the whole claim collapses.
- **B, agentic with Anthropic brains.** research (Opus) to accuracy (Sonnet) to bias (Sonnet) to
  finalizer (Opus) to guard (Sonnet).
- **C, agentic with GLM brains.** The same chain on GLM-5.2 and GLM-4.7.

Four image models: gpt-image-1, Imagen, Seedream, Qwen-Image. Two paired probes (traditional past and
present day) so temporal erasure is a measured axis. Sampling is configurable: the default is one
image per cell for breadth across many prompts, and the design supports several images per cell to
turn each metric into a rate with a confidence interval.

Scoring is blinded. Each image is copied to a neutral hashed filename, presented in a shuffled order,
and scored against the probe intent rather than the pipeline-specific prompt. The judge is given only
the image, the rubric, and the probe intent, with no model, condition, or prompt provenance. The
rubric has six anchored metrics plus a binary feature checklist (present or absent: warbonnet, teepee,
horse, prairie against longhouse, totem pole, cedar canoe, formline, rainforest coast). Reliability is
reported with Krippendorff's alpha and a vendor self-preference delta.

## 6. The Haida probe and the ethics framework

Naming a specific Nation is necessary for the science (the whole point is that Haida material culture
is maximally distinct from the Plains stereotype), which makes the safeguards non-optional rather than
nice to have. They are structural, enforced in code:

- Every surfaced image carries a burned-in banner: AI-GENERATED, not authentic Haida imagery.
- Generated images are never committed. A test fails the build if any image file is tracked under the
  runs directory.
- Findings language describes the model output, never what the Haida are or wear.
- A sacred-content exclusion list is enforced in the finalizer and guard steps, and the guard emits
  cultural flags.
- The sourced research mode grounds in Haida-authored and custodial sources.

The code license is MIT and covers code only. Generated images and cultural content are governed by a
separate usage statement. See ETHICS.md and NOTICE.md.

## 7. System architecture

Three capability protocols sit behind a key-aware registry: a chat model (every agent role), an image
model (text to image), and a vision judge (image plus rubric to structured scores). The request and
result types carry provenance as fields, so an adapter cannot return a result without recording the
exact string it sent. One shared HTTP transport carries a single retry and redaction policy for all
providers.

Conditions A, A_prime, B, and C are one pipeline class parameterized by a YAML roster, so the runner
has no per-condition branching. Adding a third brain family later is a config edit. The registry is
the single place that reads environment variables and decides what is available, and it degrades
gracefully: missing keys, missing brains, and runtime provider failures all skip cleanly and are
recorded rather than crashing the run.

The fake provider layer backs a dry-run mode that exercises the identical orchestration the tests
cover, so a green test suite means a working dry run with only live-endpoint risk left.

## 8. The build

The build followed test-driven development across six phases: scaffold and contracts, then fakes and
the registry and provenance and watermarking, then the pipeline and prompt templates, then blinded
scoring and reliability statistics, then the runner and report and CLI, then the real HTTP transports.
Every phase ended green and committed. Continuous integration runs with no secrets: it installs from a
locked file, lints, runs the tests, runs the dry-run as a gate, and scans for leaked secrets.

## 9. Providers, keys, and two backend decisions

The system needs several providers. Two decisions kept cost and friction down without weakening the
design:

- **Anthropic via the local claude CLI.** Rather than a paid Anthropic API key, Pipeline B runs
  through the Claude Code subscription by shelling out to the claude CLI. It is slower (a subprocess
  per agent call) but free.
- **The judge.** The first instinct was a Claude CLI judge to keep everything on the subscription.
  That was rejected on a blinding argument: the CLI judge is an agent with filesystem access, so it
  could enumerate the un-blinded originals and defeat the blind. An API vision judge receives only
  image bytes, has no filesystem, and is provably blinded. The judge was set to Gemini, which is
  provably blinded, is not OpenAI, uses an already-available key, and does not share a family with the
  agent brains. The only caveat, documented, is that Gemini shares a vendor with Imagen.

## 10. Live validation: what broke and what it taught

Validating against live APIs, not just mocks, surfaced exactly the class of issues mocks cannot:

- **gpt-image-1 rejected a parameter.** The adapter sent response_format, which that model does not
  accept. Fixed by removing it. Mocks had passed because the mock did not enforce the real API's
  parameter rules.
- **Two provider accounts had no balance.** fal.ai returned a locked-account error and Z.ai returned
  an insufficient-balance error. These were not code bugs, they were billing, and they proved the
  adapters were correctly wired (they authenticated and reached the API). They also exposed a real
  gap: a single provider failure was crashing the whole run. The runner now tolerates per-cell and
  per-condition runtime failures, records them, and continues, so a partial run is still useful.
- **The blinding hole.** Described above. The live setup made it concrete that an agentic judge is a
  weaker blind than an API judge, which drove the switch to Gemini.

The core thesis machinery was confirmed working: Pipeline B, running the full five-agent chain through
the Claude CLI, produced a genuinely accurate, non-stereotyped Haida prompt (cedar-plank longhouses,
post-and-beam construction, temperate rainforest, a carved cedar frontal pole in Northwest Coast
style, no teepees, no Plains cliche), and the guard flagged nothing.

## 11. How to run and read results

Run the mock first (no keys): `make mock` or `python -m agentic_bias_lens --dry-run`. Then the real
run: `python -m agentic_bias_lens`, optionally with `--k-img`, `--probe`, or `--image-style`. Each run
writes a directory containing a manifest, the full prompt provenance, the blinded scores, the report,
and a local watermarked contact sheet. The report shows aggregate scores by model and condition,
one-shot versus agentic per model, Anthropic-brain versus GLM-brain, judge disagreement when a second
judge is present, and vendor self-preference deltas. The committed example under the examples
directory shows the full report structure with redacted placeholder tiles.

## 12. Limitations and future work

This is an honest pilot, not a definitive study. It covers a single Nation and a paired probe, so it
does not generalize to all Indigenous nations. Image and judge outputs are not bit-reproducible.
Research runs unsourced by default unless the sourced mode is enabled. Judge vendor overlap is
measured but not eliminated. The default sampling is one image per cell, which favors breadth over
a within-prompt rate. The Chinese image models are sourced through a US aggregator by default, with a
recorded provenance caveat. Future work: more probes and nations, a neutral third judge by default,
native Chinese image routes, and larger samples per cell.

## 13. Where things live

- `docs/superpowers/specs/` the design spec.
- `docs/superpowers/plans/` the implementation plan.
- `config/` probes, rosters, model ids, prompt templates, and the rubric.
- `src/agentic_bias_lens/` the system.
- `examples/mock-run/` a committed mock run with redacted tiles.
- `ETHICS.md`, `NOTICE.md`, `README.md` the public-facing docs.
