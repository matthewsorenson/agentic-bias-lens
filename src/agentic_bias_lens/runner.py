"""Experiment orchestration.

Concurrency map: agent chains run sequentially within a pipeline but pipelines
run concurrently; image generation and judging fan out under a per-provider
semaphore; cells are cached by content hash so re-runs never re-pay.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata as im
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from .agents import PipelineBuilder
from .capabilities import ImageRequest
from .config import Settings
from .pipeline import AgenticPipeline
from .provenance import (
    ImageRecord,
    Transcript,
    dump_json,
    git_info,
    write_manifest,
    write_prompts,
)
from .registry import AvailabilityReport, Registry
from .reliability import (
    krippendorff_alpha,
    mean_abs_diff,
    self_preference_delta,
    spearman,
)
from .report import write_report
from .rubric_spec import METRICS
from .scoring import ScoringTable, score_images

AGENTIC = {"B", "C"}


class RunResult(BaseModel):
    run_dir: Path
    image_count: int
    availability: AvailabilityReport
    reliability: dict
    table: ScoringTable
    transcripts: list[Transcript]
    image_records: list[ImageRecord]


async def run_experiment(
    settings: Settings,
    registry: Registry,
    run_dir: str | Path,
    *,
    force: bool = False,
    rubric_text: str = "",
) -> RunResult:
    run_dir = Path(run_dir)
    (run_dir / "images").mkdir(parents=True, exist_ok=True)
    probe = settings.active_probe_text()
    conditions = list(settings.experiment["conditions"])
    k_prompt = int(settings.experiment.get("k_prompt", 1))
    k_img = int(settings.experiment.get("k_img", 1))
    seed = int(settings.experiment.get("seed", 0))
    conc = int(settings.experiment.get("concurrency_per_provider", 3))

    # 1. Build prompts for every condition, concurrently.
    async def build(cond: str):
        agents = PipelineBuilder.from_config(settings, cond)
        reps = k_prompt if cond in AGENTIC else 1
        results = [await AgenticPipeline(agents, registry, cond).run(probe) for _ in range(reps)]
        return cond, results

    prompts_by_cond = dict(await asyncio.gather(*(build(c) for c in conditions)))

    # 2. Generate images, fanned out under a per-provider semaphore, with caching.
    image_models = registry.image_models()
    sems: dict[str, asyncio.Semaphore] = {}

    def sem_for(provider: str) -> asyncio.Semaphore:
        return sems.setdefault(provider, asyncio.Semaphore(conc))

    async def gen_cell(cond, pidx, final_prompt, model, sidx):
        provider = registry.effective_provider(model.id)
        raw = f"{cond}|{model.id}|{final_prompt}|{pidx}|{sidx}"
        cell = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        sidecar = run_dir / "images" / f"cell_{cell}.json"
        if sidecar.exists() and not force:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            if Path(data["record"]["image_path"]).exists():
                return ImageRecord(**data["record"])
        async with sem_for(provider):
            res = await model.generate(
                ImageRequest(prompt=final_prompt, seed=seed + pidx * 1000 + sidx)
            )
        # Rename to a canonical, unique cell path so provenance is unambiguous
        # even when two conditions coincidentally produce the same prompt.
        target = run_dir / "images" / f"{cond}_{model.id}_p{pidx}_s{sidx}.png"
        src = Path(res.image_path)
        if src.resolve() != target.resolve():
            src.replace(target)
        rec = ImageRecord(
            condition=cond,
            model_id=model.id,
            prompt_original=res.prompt_original,
            prompt_as_sent=res.prompt_as_sent,
            image_path=target,
            seed=res.seed,
            sample_index=sidx,
        )
        sidecar.write_text(
            json.dumps({"record": rec.model_dump(mode="json")}), encoding="utf-8"
        )
        return rec

    tasks = [
        gen_cell(cond, pidx, pr.final_prompt, model, sidx)
        for cond, results in prompts_by_cond.items()
        for pidx, pr in enumerate(results)
        for model in image_models
        for sidx in range(k_img)
    ]
    image_records = [r for r in await asyncio.gather(*tasks) if r is not None]

    # 3. Score (blinded) with whatever judges are available.
    judges = registry.judges()
    if judges and image_records:
        table = await score_images(
            image_records,
            judges,
            rubric=rubric_text,
            probe_intent=probe,
            seed=seed,
            blind_dir=run_dir / "_blind",
        )
    else:
        table = ScoringTable(verdicts=[])

    reliability = _reliability(table, settings)
    transcripts = [pr.transcript for results in prompts_by_cond.values() for pr in results]

    # 4. Write artifacts (prompts first: the contact sheet reads them back).
    write_prompts(run_dir, transcripts, image_records)
    write_manifest(run_dir, _manifest(settings, registry, seed, probe, image_records))
    dump_json(
        {
            "verdicts": [v.model_dump() for v in table.raw()],
            "by_model_condition": table.by_model_condition(),
            "reliability": reliability,
        },
        run_dir / "scores.json",
    )
    write_report(run_dir, table, transcripts, reliability, probe=probe, conditions=conditions)

    return RunResult(
        run_dir=run_dir,
        image_count=len(image_records),
        availability=registry.availability_report(),
        reliability=reliability,
        table=table,
        transcripts=transcripts,
        image_records=image_records,
    )


def _reliability(table: ScoringTable, settings: Settings) -> dict:
    verdicts = table.raw()
    judge_ids = sorted({v.judge_id for v in verdicts})
    rel: dict = {"judges": judge_ids, "per_metric": {}, "overall": {}}
    if len(judge_ids) == 2:
        j1, j2 = judge_ids
        by_img: dict[str, dict] = {}
        for v in verdicts:
            by_img.setdefault(v.blind_id, {})[v.judge_id] = v
        common = [b for b, d in by_img.items() if j1 in d and j2 in d]
        for m in METRICS:
            pairs = [(by_img[b][j1].scores[m], by_img[b][j2].scores[m]) for b in common]
            rel["per_metric"][m] = {
                "krippendorff_alpha": krippendorff_alpha(pairs),
                "mean_abs_diff": mean_abs_diff(
                    [p[0] for p in pairs], [p[1] for p in pairs]
                ),
            }
        o1 = [by_img[b][j1].overall for b in common]
        o2 = [by_img[b][j2].overall for b in common]
        rel["overall"] = {"spearman": spearman(o1, o2), "mean_abs_diff": mean_abs_diff(o1, o2)}

    model_vendor = {k: v.family for k, v in settings.models.items()}
    judge_vendor = {j: settings.models[j].family for j in judge_ids if j in settings.models}
    rel["self_preference_delta"] = self_preference_delta(verdicts, model_vendor, judge_vendor)
    return rel


def _ver(pkg: str) -> str:
    try:
        return im.version(pkg)
    except im.PackageNotFoundError:
        return "unknown"


def _manifest(settings, registry, seed, probe, image_records) -> dict:
    report = registry.availability_report()
    return {
        **git_info(settings.config_dir.parent),
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "seed": seed,
        "active_probe": probe,
        "conditions": settings.experiment["conditions"],
        "image_models_used": sorted({r.model_id for r in image_records}),
        "available_providers": report.available,
        "missing_providers": report.missing,
        "k_prompt": settings.experiment.get("k_prompt"),
        "k_img": settings.experiment.get("k_img"),
        "fake_mode": registry.fake,
        "lib_versions": {p: _ver(p) for p in ("pydantic", "httpx", "pillow")},
    }
