"""Score architecture manifests against one shared requirement corpus."""
import json
from pathlib import Path


HERE = Path(__file__).parent


def compare():
    corpus = json.loads((HERE / "query_corpus.json").read_text())["queries"]
    manifests = json.loads((HERE / "candidate_manifests.json").read_text())
    # Closed-world by design: a candidate may not claim a capability merely
    # because a new held-out query introduced its name.
    universe = set(manifests["capability_universe"])
    rows = []
    for candidate in manifests["candidates"]:
        if candidate["support_mode"] == "allowlist":
            supported = set(candidate["capabilities"])
        else:
            supported = ((universe - set(candidate["unsupported"]))
                         | set(candidate.get("additional_capabilities", [])))
        covered = []
        gaps = {}
        for query in corpus:
            missing = sorted(set(query["requires"]) - supported)
            if missing:
                gaps[query["id"]] = missing
            else:
                covered.append(query["id"])
        rows.append({
            "candidate": candidate["id"],
            "represented": len(covered),
            "total": len(corpus),
            "coverage_pct": round(100 * len(covered) / len(corpus), 1),
            "core_concepts": candidate["core_concepts"],
            "domain_exceptions": candidate["domain_exceptions"],
            "special_planner_rules": candidate["special_planner_rules"],
            "gaps": gaps,
            "qualification": candidate["notes"],
        })
    return rows


if __name__ == "__main__":
    print(json.dumps(compare(), ensure_ascii=False, indent=2))
