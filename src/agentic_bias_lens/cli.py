"""Command line entry point.

`--dry-run` builds a fake registry and runs the full experiment with no keys, so
it exercises the identical orchestration path the tests cover.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .config import Settings
from .provenance import Transcript
from .registry import Registry
from .report import write_report
from .runner import run_experiment
from .scoring import ScoringTable, Verdict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config"


def _parse(argv):
    p = argparse.ArgumentParser(prog="agentic-bias-lens")
    p.add_argument("--dry-run", action="store_true", help="run with fake providers, no keys")
    p.add_argument("--pipelines", help="comma list of conditions, e.g. A,A_prime,B,C")
    p.add_argument("--models", help="comma list of image model keys")
    p.add_argument("--force", action="store_true", help="ignore the cell cache")
    p.add_argument("--k-img", type=int, help="images per prompt per model (overrides config)")
    p.add_argument("--k-prompt", type=int, help="agent-chain re-runs per agentic pipeline")
    p.add_argument("--probe", help="override the probe text for this run")
    p.add_argument("--image-style", help="override the shared image style suffix")
    p.add_argument("--config-dir", default=str(DEFAULT_CONFIG))
    p.add_argument("--out", help="run directory (default runs/<timestamp>)")
    p.add_argument("--report-only", action="store_true", help="rebuild report from an existing run")
    return p.parse_args(argv)


def _load_env(config_dir: Path) -> dict:
    env_path = config_dir.parent / ".env"
    if env_path.exists():
        try:
            from dotenv import dotenv_values

            return {**os.environ, **dotenv_values(env_path)}
        except ImportError:
            pass
    return dict(os.environ)


def main(argv=None) -> int:
    args = _parse(argv)
    config_dir = Path(args.config_dir)
    settings = Settings.load(config_dir)
    settings.validate_rosters()

    if args.pipelines:
        settings.experiment["conditions"] = args.pipelines.split(",")
    if args.models:
        settings.experiment["image_models"] = args.models.split(",")
    if args.k_img is not None:
        settings.experiment["k_img"] = args.k_img
    if args.k_prompt is not None:
        settings.experiment["k_prompt"] = args.k_prompt
    if args.probe:
        settings.experiment["probes"]["_cli"] = args.probe
        settings.experiment["active_probe"] = "_cli"
    if args.image_style is not None:
        settings.experiment["image_style"] = args.image_style

    out = Path(args.out) if args.out else REPO_ROOT / "runs" / datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    if args.report_only:
        return _report_only(out, settings)

    rubric_text = (config_dir / "rubric.md").read_text(encoding="utf-8")
    if args.dry_run:
        registry = Registry.build(settings, fake=True, images_dir=out / "images")
    else:
        env = _load_env(config_dir)
        registry = Registry.build(settings, env=env, fake=False, images_dir=out / "images")

    result = asyncio.run(
        run_experiment(settings, registry, out, force=args.force, rubric_text=rubric_text)
    )

    avail = result.availability
    print(f"run: {result.run_dir}")
    print(f"images: {result.image_count}")
    print(f"providers available: {', '.join(avail.available) or 'none'}")
    if avail.missing:
        print(f"providers skipped (no key): {', '.join(avail.missing)}")
    print(f"report: {result.run_dir / 'report.md'}")
    return 0


def _report_only(out: Path, settings: Settings) -> int:
    run_dir = out if (out / "scores.json").exists() else _latest_run()
    if run_dir is None or not (run_dir / "scores.json").exists():
        print("no run found to rebuild a report from")
        return 1
    scores = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))
    table = ScoringTable(verdicts=[Verdict(**v) for v in scores.get("verdicts", [])])
    reliability = scores.get("reliability", {})
    prompts = json.loads((run_dir / "prompts.json").read_text(encoding="utf-8"))
    transcripts = [
        Transcript(
            probe=c.get("probe", ""),
            condition=name,
            final_prompt=c.get("final_prompt", ""),
            cultural_flags=c.get("cultural_flags", []),
        )
        for name, c in prompts.get("conditions", {}).items()
    ]
    write_report(
        run_dir,
        table,
        transcripts,
        reliability,
        probe=settings.active_probe_text(),
        conditions=list(settings.experiment["conditions"]),
    )
    print(f"report rebuilt: {run_dir / 'report.md'}")
    return 0


def _latest_run() -> Path | None:
    runs = REPO_ROOT / "runs"
    if not runs.exists():
        return None
    candidates = sorted((p for p in runs.iterdir() if p.is_dir()), reverse=True)
    return candidates[0] if candidates else None
