"""Blinded judge scoring and aggregation.

Judges never see provenance: each image is copied to a neutral hashed filename,
order is shuffled per judge, and the judge is given the fixed probe intent rather
than the pipeline-specific prompt. Overall is computed here, never asked of the
judge.
"""

from __future__ import annotations

import hashlib
import random
import statistics
import tempfile
from pathlib import Path

from pydantic import BaseModel

from .capabilities import JudgeRequest, VisionJudge
from .provenance import ImageRecord
from .rubric_spec import FEATURE_KEYS, METRICS, compute_overall
from .watermark import strip_and_reencode


class Verdict(BaseModel):
    blind_id: str
    condition: str
    model_id: str
    sample_index: int
    judge_id: str
    scores: dict[str, int]
    features: dict[str, bool]
    overall: float
    justifications: dict[str, str] = {}


class ScoringTable(BaseModel):
    verdicts: list[Verdict]

    def raw(self) -> list[Verdict]:
        return self.verdicts

    def by_model_condition(self) -> dict[str, dict]:
        groups: dict[tuple[str, str], list[Verdict]] = {}
        for v in self.verdicts:
            groups.setdefault((v.model_id, v.condition), []).append(v)
        out: dict[str, dict] = {}
        for (model, condition), vs in groups.items():
            metric_means = {
                m: round(statistics.fmean(v.scores[m] for v in vs), 3) for m in METRICS
            }
            feature_rates = {
                k: round(statistics.fmean(1.0 if v.features.get(k) else 0.0 for v in vs), 3)
                for k in FEATURE_KEYS
            }
            out[f"{model}|{condition}"] = {
                "model_id": model,
                "condition": condition,
                "n": len(vs),
                "metric_means": metric_means,
                "overall": round(statistics.fmean(v.overall for v in vs), 3),
                "feature_rates": feature_rates,
            }
        return out


def _blind_id(rec: ImageRecord, seed: int) -> str:
    raw = f"{seed}|{rec.condition}|{rec.model_id}|{rec.sample_index}|{rec.image_path.name}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


async def score_images(
    images: list[ImageRecord],
    judges: list[VisionJudge],
    rubric: str,
    probe_intent: str,
    *,
    seed: int,
    blind_dir: str | Path | None = None,
) -> ScoringTable:
    blind_dir = Path(blind_dir or tempfile.mkdtemp(prefix="abl_blind_"))
    blind_dir.mkdir(parents=True, exist_ok=True)

    blinded: list[tuple[str, ImageRecord, Path]] = []
    for rec in images:
        bid = _blind_id(rec, seed)
        bpath = blind_dir / f"{bid}.png"
        strip_and_reencode(rec.image_path, bpath)
        blinded.append((bid, rec, bpath))

    verdicts: list[Verdict] = []
    for judge in judges:
        order = blinded[:]
        random.Random(f"{seed}:{judge.id}").shuffle(order)
        for bid, rec, bpath in order:
            jr = await judge.judge(
                JudgeRequest(image_path=bpath, rubric=rubric, probe_intent=probe_intent)
            )
            scores = {m: jr.scores[m].score for m in METRICS}
            verdicts.append(
                Verdict(
                    blind_id=bid,
                    condition=rec.condition,
                    model_id=rec.model_id,
                    sample_index=rec.sample_index,
                    judge_id=judge.id,
                    scores=scores,
                    features={k: bool(jr.features.get(k)) for k in FEATURE_KEYS},
                    overall=compute_overall(scores),
                    justifications={m: jr.scores[m].justification for m in METRICS},
                )
            )
    return ScoringTable(verdicts=verdicts)
