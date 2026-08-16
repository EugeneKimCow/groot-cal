# E-020 demo entry point — intent compiler to routed executor

Date: 2026-08-16

## Question

Can a Korean question be observed end to end — clause binding ledger → compiled
Plan → execution record → evidence-bounded result — through the governed intent
compiler and only the routed C4 capabilities, with every unrouted capability
named and refused rather than substituted?

## Implementation

- `slice/demo.py`: `demo_question` runs `compile_shadow_intent`, then executes
  the plan only when every call is inside the routed operator vocabulary
  (`evaluate_metric`, `delta`, `contribution`, `set_transition`,
  `event_overlap_scan` @v1). Plans containing shadow-only operators (`rank`,
  `drilldown`, `align_metrics`, `plan_gap`) end at an explicit
  `route_capability` refusal that names the operator and points to the current
  route. `render_demo` prints the four-layer view: binding ledger with spans,
  roles, and refusal reasons; the Call DAG; budget/gate/provenance record; and
  normalized results with label ceilings and set-transition detail.
- `run.py` gains opt-in `--route c4` / `--show-plan`. The default invocation
  is byte-identical to before.

## Gate evidence

- governed adversarial corpus through the demo: 9/9 accounted — 2 executed
  (offline-region change with parity; explicit-2025 question honestly
  `suspended` with resume conditions), 5 clause-local intent refusals, 2
  explicit unrouted-capability refusals (rank, metric alignment); zero
  substitutions;
- change paraphrases: 5/5 compile to `explain_change` and execute entirely on
  routed operators;
- intent-compiled category contribution agrees with the Query-Spec-routed
  `contrib:category` (Δ−340, identical segment map) — the two compilers meet
  at the same executor with the same numbers;
- level demo value equals the current route (3860);
- default engine route untouched.

## Regression

E-020 tests 8/8; product 197 discovered, all pass in the standard sandbox;
golden 17/17; semantic 10/10; research 58/58.

## Qualification

The demo's recall is the governed corpus's: wording outside the registered
vocabulary ends in clarify/out_of_domain by design. That is the honest surface
for the next experiment — the LLM proposal adapter over the clause-binding
contract (C2′) — not a defect of this gate. Rank and drilldown remain the
first capabilities whose routing would visibly enrich the demo.

## Decision

E-020 passes. The closeout demo increment is complete: level and period change
run end to end from Korean text under contract, and refusals are part of the
demonstration.
