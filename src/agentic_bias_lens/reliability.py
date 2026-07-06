"""Inter-rater reliability and vendor self-preference statistics.

Two vision judges scoring on an ordinal 1..5 scale need chance-corrected
agreement (Krippendorff's alpha) reported per metric, plus a directly measured
self-preference delta so vendor overlap is quantified rather than assumed away.
"""

from __future__ import annotations

import statistics


def mean_abs_diff(a: list[float], b: list[float]) -> float:
    return statistics.fmean(abs(x - y) for x, y in zip(a, b, strict=True))


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1  # 1-based average rank for ties
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = _rank(a), _rank(b)
    n = len(ra)
    mean_a, mean_b = statistics.fmean(ra), statistics.fmean(rb)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(ra, rb, strict=True))
    var_a = sum((x - mean_a) ** 2 for x in ra)
    var_b = sum((y - mean_b) ** 2 for y in rb)
    if var_a == 0 or var_b == 0:
        return 0.0
    return round(cov / (var_a**0.5 * var_b**0.5), 6)


def krippendorff_alpha(pairs: list[tuple[int, int]], level: str = "ordinal") -> float:
    """Alpha for two raters, ordinal metric, no missing values.

    pairs: one (rater1, rater2) tuple per unit.
    """
    units = [list(p) for p in pairs if len([x for x in p if x is not None]) >= 2]
    if not units:
        return float("nan")

    values = sorted({v for u in units for v in u})
    # observed coincidence matrix
    o: dict[tuple[int, int], float] = {}
    n = 0.0
    for u in units:
        m = len(u)
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                o[(u[i], u[j])] = o.get((u[i], u[j]), 0.0) + 1.0 / (m - 1)
                n += 1.0 / (m - 1)

    marginals = {c: sum(o.get((c, k), 0.0) for k in values) for c in values}

    def ordinal_delta(c: int, k: int) -> float:
        lo, hi = (c, k) if c <= k else (k, c)
        between = sum(marginals[g] for g in values if lo <= g <= hi)
        return (between - (marginals[c] + marginals[k]) / 2.0) ** 2

    do = sum(o.get((c, k), 0.0) * ordinal_delta(c, k) for c in values for k in values)
    de = sum(
        marginals[c] * marginals[k] * ordinal_delta(c, k) for c in values for k in values
    )
    if de == 0:
        return 1.0
    return round(1.0 - (n - 1.0) * do / de, 6)


def self_preference_delta(
    verdicts,
    model_vendor: dict[str, str],
    judge_vendor: dict[str, str],
    human_baseline: dict[str, float] | None = None,
) -> dict[str, float]:
    """Per judge: mean overall on same-vendor images minus mean on other-vendor images."""
    out: dict[str, float] = {}
    judges = {v.judge_id for v in verdicts}
    for jid in judges:
        jv = judge_vendor.get(jid)
        same = [v.overall for v in verdicts if v.judge_id == jid and model_vendor.get(v.model_id) == jv]
        other = [
            v.overall for v in verdicts if v.judge_id == jid and model_vendor.get(v.model_id) != jv
        ]
        if not same or not other:
            continue
        delta = statistics.fmean(same) - statistics.fmean(other)
        if human_baseline and jid in human_baseline:
            delta -= human_baseline[jid]
        out[jid] = round(delta, 4)
    return out
