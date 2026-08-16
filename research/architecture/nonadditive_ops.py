"""E-005 prototypes for estimands hidden by ordinary deltas."""
from collections import defaultdict


class EstimandError(ValueError):
    pass


def rate_mix_decomposition(baseline, target):
    """Symmetric two-factor decomposition of a ratio-of-sums change.

    Inputs map segment -> (numerator, denominator). The explicit symmetric
    convention allocates interaction equally between within-rate and mix.
    """
    segments = sorted(set(baseline) | set(target))
    totals = {}
    for label, rows in (("baseline", baseline), ("target", target)):
        numerator = sum(rows.get(segment, (0, 0))[0] for segment in segments)
        denominator = sum(rows.get(segment, (0, 0))[1] for segment in segments)
        if denominator <= 0:
            raise EstimandError(f"{label} denominator must be positive")
        totals[label] = (numerator, denominator, numerator / denominator)

    rate_effect = 0.0
    mix_effect = 0.0
    rows = []
    for segment in segments:
        n0, d0 = baseline.get(segment, (0, 0))
        n1, d1 = target.get(segment, (0, 0))
        if d0 <= 0 or d1 <= 0:
            raise EstimandError("symmetric rate/mix requires every segment in both periods")
        r0, r1 = n0 / d0, n1 / d1
        w0 = d0 / totals["baseline"][1]
        w1 = d1 / totals["target"][1]
        rate_part = (r1 - r0) * (w0 + w1) / 2
        mix_part = (w1 - w0) * (r0 + r1) / 2
        rate_effect += rate_part
        mix_effect += mix_part
        rows.append({"segment": segment, "rate_effect": rate_part,
                     "mix_effect": mix_part, "rates": [r0, r1],
                     "weights": [w0, w1]})
    total_change = totals["target"][2] - totals["baseline"][2]
    closed = abs((rate_effect + mix_effect) - total_change) < 1e-12
    if not closed:
        raise EstimandError("rate + mix identity did not close")
    return {"status": "result", "output_type": "Attribution",
            "estimand": "symmetric within-rate and composition effects",
            "convention": "symmetric_two_factor",
            "baseline_rate": totals["baseline"][2],
            "target_rate": totals["target"][2],
            "total_change": total_change, "rate_effect": rate_effect,
            "mix_effect": mix_effect, "segments": rows,
            "checks": [{"check": "identity", "passed": closed}]}


def entity_transitions(baseline, target, entity_field, dimension_field=None):
    """Describe set entry/exit/retention and optional dimension migration."""
    def assignments(rows):
        result = defaultdict(set)
        for row in rows:
            entity = row[entity_field]
            result[entity].add(row.get(dimension_field) if dimension_field else True)
        conflicts = [entity for entity, values in result.items() if len(values) != 1]
        if conflicts:
            raise EstimandError(f"non-functional assignments: {sorted(conflicts)}")
        return {entity: next(iter(values)) for entity, values in result.items()}

    before, after = assignments(baseline), assignments(target)
    before_ids, after_ids = set(before), set(after)
    retained = before_ids & after_ids
    entrants = after_ids - before_ids
    exits = before_ids - after_ids
    migrations = []
    if dimension_field:
        migrations = [{"entity": entity, "from": before[entity], "to": after[entity]}
                      for entity in sorted(retained) if before[entity] != after[entity]]
    checks = [
        {"check": "baseline_identity", "passed": len(before_ids) == len(retained) + len(exits)},
        {"check": "target_identity", "passed": len(after_ids) == len(retained) + len(entrants)},
    ]
    if not all(check["passed"] for check in checks):
        raise EstimandError("set transition identity did not close")
    return {"status": "result", "output_type": "SetTransition",
            "baseline_count": len(before_ids), "target_count": len(after_ids),
            "entrants": sorted(entrants), "exits": sorted(exits),
            "retained": sorted(retained), "migrations": migrations,
            "checks": checks}

