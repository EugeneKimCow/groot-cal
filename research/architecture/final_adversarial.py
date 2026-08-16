"""E-010 final adversarial boundaries: scenario, causality, distribution."""
from statistics import median


class ScenarioError(ValueError):
    pass


def deterministic_reweight(segment_rates, reference_weights):
    if set(segment_rates) != set(reference_weights):
        raise ScenarioError("rates and weights must align")
    if abs(sum(reference_weights.values()) - 1.0) > 1e-12:
        raise ScenarioError("reference weights must sum to one")
    value = sum(segment_rates[key] * reference_weights[key]
                for key in sorted(segment_rates))
    return {"status": "result", "output_type": "ScenarioValue",
            "value": value, "method": "deterministic_reweighting",
            "causal": False}


def causal_counterfactual_contract(outcome, intervention, model_ref=None,
                                   identification_contract=None):
    missing = []
    if model_ref is None:
        missing.append("causal_model_ref")
    if identification_contract is None:
        missing.append("identification_contract")
    if missing:
        return {"status": "suspended", "missing_inputs": missing,
                "pass_conditions": "registered model and identification contract",
                "prohibited_fallback": "observed-row filtering"}
    return {"status": "result", "output_type": "CounterfactualRequest",
            "outcome": outcome, "intervention": intervention,
            "model_ref": model_ref,
            "identification_contract": identification_contract}


def quantile_additivity_counterexample(baseline, target):
    segments = sorted(set(baseline) | set(target))
    segment_deltas = {
        segment: median(target[segment]) - median(baseline[segment])
        for segment in segments
    }
    baseline_all = [value for segment in segments for value in baseline[segment]]
    target_all = [value for segment in segments for value in target[segment]]
    total_delta = median(target_all) - median(baseline_all)
    return {"segment_delta_sum": sum(segment_deltas.values()),
            "total_delta": total_delta,
            "additive_identity_holds": sum(segment_deltas.values()) == total_delta}

