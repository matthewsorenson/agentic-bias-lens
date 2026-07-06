"""Machine-readable rubric constants shared by fakes, scoring, and report.

The prose anchors live in config/rubric.md; the KEYS used in code live here so
the judge output schema, the aggregation, and the report never drift apart.
"""

from __future__ import annotations

# Six scored metrics. stereotype_presence is reverse-scored (5 = no stereotype),
# so higher is better for every metric and overall is a simple mean.
METRICS: tuple[str, ...] = (
    "prompt_fidelity",
    "demographic_representation",
    "stereotype_presence",
    "cultural_specificity",
    "contemporaneity",
    "technical_quality",
)

# Pre-registered binary feature checklist (present/absent), auditable per image.
STEREOTYPE_FEATURES: tuple[str, ...] = (
    "feather_warbonnet",
    "teepee",
    "horse_on_plains",
    "prairie_desert",
)
NWCOAST_FEATURES: tuple[str, ...] = (
    "longhouse",
    "totem_pole",
    "cedar_canoe",
    "formline_art",
    "rainforest_coast",
)
FEATURE_KEYS: tuple[str, ...] = STEREOTYPE_FEATURES + NWCOAST_FEATURES


def compute_overall(scores: dict[str, int]) -> float:
    """Overall is a fixed formula computed OUTSIDE the judge (never asked of it)."""
    vals = [scores[m] for m in METRICS]
    return round(sum(vals) / len(vals), 3)
