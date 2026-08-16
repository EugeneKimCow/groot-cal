"""E-009 prototypes for valid-time, disclosure, and freshness constraints."""
from datetime import date


class BoundaryError(ValueError):
    pass


def valid_time_bind(facts, dimension_versions, entity_field, fact_time_field):
    by_entity = {}
    for version in dimension_versions:
        by_entity.setdefault(version[entity_field], []).append(version)
    for versions in by_entity.values():
        versions.sort(key=lambda row: row["valid_from"])
        for left, right in zip(versions, versions[1:]):
            if left["valid_to"] is None or left["valid_to"] > right["valid_from"]:
                raise BoundaryError("overlapping valid-time dimension versions")

    bound = []
    for fact in facts:
        observed = date.fromisoformat(fact[fact_time_field])
        matches = []
        for version in by_entity.get(fact[entity_field], []):
            start = date.fromisoformat(version["valid_from"])
            end = date.max if version["valid_to"] is None else date.fromisoformat(version["valid_to"])
            if start <= observed < end:
                matches.append(version)
        if len(matches) != 1:
            raise BoundaryError(f"valid-time match count={len(matches)} for fact {fact}")
        attributes = {key: value for key, value in matches[0].items()
                      if key not in {entity_field, "valid_from", "valid_to"}}
        bound.append({**fact, **attributes})
    return bound


def suppress_small_groups(rows, count_field, value_field, minimum_count):
    visible = [row for row in rows if row[count_field] >= minimum_count]
    hidden = [row for row in rows if row[count_field] < minimum_count]
    total_value = sum(row[value_field] for row in rows)
    suppressed_value = sum(row[value_field] for row in hidden)
    suppressed_count = sum(row[count_field] for row in hidden)
    visible_value = sum(row[value_field] for row in visible)
    if visible_value + suppressed_value != total_value:
        raise BoundaryError("privacy reconciliation failed")
    return {"status": "result", "visible": visible,
            "suppressed": {"groups": len(hidden), "entity_count": suppressed_count,
                           "value": suppressed_value},
            "total": {"value": total_value},
            "policy": {"kind": "minimum_group_size", "threshold": minimum_count},
            "checks": [{"check": "suppressed_residual_reconciles", "passed": True}]}


def assess_freshness_vector(used_snapshots, current_snapshots):
    sources = []
    for source, used_ref in sorted(used_snapshots.items()):
        current_ref = current_snapshots.get(source)
        if current_ref is None:
            status = "suspended"
        elif current_ref == used_ref:
            status = "fresh"
        else:
            status = "stale"
        sources.append({"source": source, "used_ref": used_ref,
                        "current_ref": current_ref, "status": status})
    if any(row["status"] == "suspended" for row in sources):
        overall = "suspended"
    elif any(row["status"] == "stale" for row in sources):
        overall = "stale"
    else:
        overall = "fresh"
    return {"status": "result" if overall != "suspended" else "suspended",
            "freshness": overall, "sources": sources,
            "label_ceiling": {"freshness": "data_confirmed"}}

