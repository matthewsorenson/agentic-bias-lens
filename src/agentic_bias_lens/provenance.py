"""Provenance transcript and deterministic artifact writers.

Everything written to a run directory is serialized with sorted keys and a
trailing newline so transcripts diff cleanly. The Transcript is assembled from
capability results, which already carry redacted raw payloads.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

from .capabilities import ChatResult


def dump_json(obj, path: str | Path) -> Path:
    path = Path(path)
    text = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, default=str)
    path.write_text(text + "\n", encoding="utf-8")
    return path


class Turn(BaseModel):
    role: str
    rendered_prompt: str
    output_text: str
    model_id: str


class Transcript(BaseModel):
    probe: str
    condition: str
    final_prompt: str = ""
    turns: list[Turn] = []
    cultural_flags: list = []

    def add_turn(self, role: str, rendered_prompt: str, result: ChatResult) -> None:
        self.turns.append(
            Turn(
                role=role,
                rendered_prompt=rendered_prompt,
                output_text=result.text,
                model_id=result.model_id,
            )
        )


class ImageRecord(BaseModel):
    condition: str
    model_id: str
    prompt_original: str
    prompt_as_sent: str
    image_path: Path
    seed: int | None = None
    sample_index: int = 0


def _rel(path: Path, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path)


def write_prompts(
    run_dir: str | Path,
    transcripts: list[Transcript],
    image_records: list[ImageRecord],
) -> Path:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "conditions": {
            t.condition: {
                "probe": t.probe,
                "final_prompt": t.final_prompt,
                "cultural_flags": t.cultural_flags,
                "turns": [
                    {"role": tn.role, "model_id": tn.model_id, "output": tn.output_text}
                    for tn in t.turns
                ],
            }
            for t in transcripts
        },
        "images": [
            {
                "condition": r.condition,
                "model_id": r.model_id,
                "sample_index": r.sample_index,
                "prompt_original": r.prompt_original,
                "prompt_as_sent": r.prompt_as_sent,
                "image": _rel(r.image_path, run_dir),
            }
            for r in image_records
        ],
    }
    dump_json(payload, run_dir / "prompts.json")
    _write_prompts_md(run_dir / "prompts.md", transcripts, image_records, run_dir)
    return run_dir / "prompts.json"


def _write_prompts_md(path, transcripts, image_records, run_dir) -> None:
    lines = ["# Prompt provenance", ""]
    for t in transcripts:
        lines.append(f"## Condition {t.condition}")
        lines.append("")
        lines.append(f"Probe: {t.probe}")
        lines.append("")
        lines.append(f"Final prompt: {t.final_prompt}")
        lines.append("")
        if t.turns:
            lines.append("Agent chain:")
            for tn in t.turns:
                lines.append(f"- {tn.role} ({tn.model_id}): {tn.output_text}")
            lines.append("")
    lines.append("## Images (exact string sent to each model)")
    lines.append("")
    for r in image_records:
        lines.append(f"- [{r.condition}] {r.model_id}: {r.prompt_as_sent}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest(run_dir: str | Path, data: Mapping) -> Path:
    return dump_json(dict(data), Path(run_dir) / "manifest.json")


def git_info(repo: str | Path) -> dict:
    def _run(args):
        return subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True, text=True, check=False
        ).stdout.strip()

    sha = _run(["rev-parse", "HEAD"]) or "unknown"
    dirty = bool(_run(["status", "--porcelain"]))
    return {"git_sha": sha, "dirty": dirty}
