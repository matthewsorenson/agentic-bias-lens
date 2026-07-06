"""Markdown report and HTML contact sheet.

Language rule: describe model outputs ("model output for the probe"), never state
what "the Haida" are or wear. Every image caption shows the exact prompt_as_sent.
"""

from __future__ import annotations

import statistics
from pathlib import Path

from jinja2 import Template

from .provenance import ImageRecord, Transcript
from .rubric_spec import NARROW_DEFAULT_MARKERS
from .scoring import ScoringTable

_REPORT = Template(
    """# Bias comparison report

This report describes AI model outputs for one probe. Every image is a synthetic guess produced by
a model, not authentic Haida imagery, and is published only to document how AI systems depict a
subject. See ETHICS.md.

Probe (active): {{ probe }}

## Aggregate scores by model and condition

| model | condition | n | overall | narrow-default marker rate |
|---|---|---|---|---|
{% for row in agg -%}
| {{ row.model_id }} | {{ row.condition }} | {{ row.n }} | {{ row.overall }} | {{ row.narrow }} |
{% endfor %}
## Within-model: one-shot vs agentic (overall score)

| model | {% for c in conditions %}{{ c }} | {% endfor %}
|---|{% for c in conditions %}---|{% endfor %}
{% for m in models -%}
| {{ m }} | {% for c in conditions %}{{ matrix[m][c] }} | {% endfor %}
{% endfor %}
## Anthropic-brain (B) vs GLM-brain (C)

For each model, the overall score under Anthropic-driven agents (B) versus GLM-driven agents (C).
A gap here reflects the reasoning model family, not the image model.

| model | B | C |
|---|---|---|
{% for m in models -%}
| {{ m }} | {{ matrix[m].get('B', 'n/a') }} | {{ matrix[m].get('C', 'n/a') }} |
{% endfor %}
## US judge vs CN judge disagreement

{% if disagreement -%}
| metric | krippendorff alpha | mean abs diff |
|---|---|---|
{% for m, d in disagreement.items() -%}
| {{ m }} | {{ d.krippendorff_alpha }} | {{ d.mean_abs_diff }} |
{% endfor %}
Overall: spearman {{ overall_rel.get('spearman', 'n/a') }}, mean abs diff {{ overall_rel.get('mean_abs_diff', 'n/a') }}.
{% else -%}
Single-judge mode: judge disagreement not available (needs two judges).
{% endif %}
## Vendor self-preference deltas

A judge may share a vendor with one of the image models (for example a judge and an image model from
the same company). A positive delta means the judge scored its own vendor's images higher than others.

{% for j, d in self_pref.items() -%}
- {{ j }}: {{ d }}
{% else -%}
- not computed (single vendor or insufficient data)
{% endfor %}
## Cultural flags raised by the guard agent

{% for c in flags -%}
- [{{ c.condition }}] {{ c.flags }}
{% else -%}
- none raised
{% endfor %}
"""
)

_SHEET = Template(
    """<!doctype html>
<html><head><meta charset="utf-8"><title>Contact sheet</title>
<style>
body{font-family:sans-serif;margin:16px}
.card{display:inline-block;width:230px;margin:8px;vertical-align:top}
img{width:210px;height:auto;border:1px solid #ccc}
.cap{font-size:11px;color:#333;word-wrap:break-word}
.tag{font-weight:bold}
</style></head><body>
<h1>Contact sheet</h1>
<p>AI-generated outputs, not authentic Haida imagery. See ETHICS.md.</p>
{% for im in images %}
<div class="card">
  <img src="{{ im.src }}" alt="ai model output">
  <div class="cap"><span class="tag">[{{ im.condition }}] {{ im.model_id }}</span><br>{{ im.caption }}</div>
</div>
{% endfor %}
</body></html>
"""
)


def _rate(cell: dict, keys) -> float:
    rates = cell["feature_rates"]
    return round(statistics.fmean(rates[k] for k in keys), 3)


def write_report(
    run_dir: str | Path,
    table: ScoringTable,
    transcripts: list[Transcript],
    reliability: dict,
    *,
    probe: str,
    conditions: list[str],
) -> Path:
    run_dir = Path(run_dir)
    agg_raw = table.by_model_condition()

    agg_rows = []
    models: list[str] = []
    matrix: dict[str, dict] = {}
    for _, cell in sorted(agg_raw.items()):
        m, c = cell["model_id"], cell["condition"]
        if m not in models:
            models.append(m)
        matrix.setdefault(m, {})[c] = cell["overall"]
        agg_rows.append(
            {
                "model_id": m,
                "condition": c,
                "n": cell["n"],
                "overall": cell["overall"],
                "narrow": _rate(cell, NARROW_DEFAULT_MARKERS),
            }
        )
    for m in models:
        for c in conditions:
            matrix[m].setdefault(c, "n/a")

    flags = [
        {"condition": t.condition, "flags": t.cultural_flags}
        for t in transcripts
        if t.cultural_flags
    ]

    report_md = _REPORT.render(
        probe=probe,
        agg=agg_rows,
        conditions=conditions,
        models=models,
        matrix=matrix,
        disagreement=reliability.get("per_metric", {}),
        overall_rel=reliability.get("overall", {}),
        self_pref=reliability.get("self_preference_delta", {}),
        flags=flags,
    )
    (run_dir / "report.md").write_text(report_md, encoding="utf-8")

    images = []
    for r in _iter_image_records(run_dir):
        images.append(
            {
                "src": f"images/{Path(r.image_path).name}",
                "condition": r.condition,
                "model_id": r.model_id,
                "caption": r.prompt_as_sent,
            }
        )
    (run_dir / "contact_sheet.html").write_text(_SHEET.render(images=images), encoding="utf-8")
    return run_dir / "report.md"


def _iter_image_records(run_dir: Path):
    """Read the image records back from prompts.json so the sheet matches provenance."""
    import json

    prompts = run_dir / "prompts.json"
    if not prompts.exists():
        return []
    data = json.loads(prompts.read_text(encoding="utf-8"))
    out = []
    for im in data.get("images", []):
        out.append(
            ImageRecord(
                condition=im["condition"],
                model_id=im["model_id"],
                prompt_original=im["prompt_original"],
                prompt_as_sent=im["prompt_as_sent"],
                image_path=run_dir / im["image"],
                sample_index=im.get("sample_index", 0),
            )
        )
    return out
