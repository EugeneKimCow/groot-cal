# E-018 controlled metric-level routing

Date: 2026-08-16

## Question

Can `inspect_level` route through the C4 compiler/executor behind a reversible
selector while preserving the public envelope, result payload, storage,
reporting, provenance, and failure behavior — without silent fallback and
without pretending legacy identity?

## Implementation

- `engine.run_question` gains an explicit `route` selector. The default
  `current` preserves the existing route byte-for-byte. `c4_level` executes
  only `inspect_level` through `compile_shadow_plan` → `execute_shadow_plan`
  and refuses every other operation family with a `route_capability` failure.
  `c4_level_or_current` is the caller's explicit fallback choice; nothing falls
  back silently.
- `slice/c4_route.py` adapts the C4 result to the public bundle boundary. The
  success payload is the canonical Result Envelope v1 wire (`MetricScalar`)
  that the E-014 adapter already consumes; no shape probing was added anywhere.
- Semantic validation including input availability runs at the same
  `query_spec` boundary as the current route, so missing months and bad scope
  fail in the same public location with identical payloads.
- The execution record preserves C4 identity — `plan_hash`, per-call records,
  call provenance, binding ledger — and adds the public provenance block
  (`metric_ref`, `input_snapshot_ref`, `as_of`) plus full budget keys consumed
  by the CLI. Operator identity is declared as `evaluate_metric@v1`, never
  spelled as a legacy name.
- Report/staleness workflow questions ignore the selector: they are outside
  Analytical IR (E-017 boundary).

## The discriminating risk, confirmed

The public bundle boundary — not arithmetic — was the migration constraint, as
E-018's design predicted. The first reporting parity run failed because the
commerce route declares an unchecked open-cohort assumption in
`assumption_ledger` and the routed bundle dropped it, silently weakening the
report's declared uncertainty. The assumption belongs to the domain pack, not
the execution path, so it is now a shared `COMMERCE_ASSUMPTION_LEDGER` constant
preserved by both routes. Arithmetic, unit, and label parity never failed.

## Parity evidence (both selectors)

- five metric algebras level: adapter-view value/unit/label parity 5/5
  (3860, 20, 0.66, 190, 5);
- scoped level online 1580: parity;
- missing month and bad scope: identical `query_spec` failure payloads;
- duplicate binding: both routes fail closed with `field_binding_unique`;
- reporting: identical claim texts and labels, lint clean on both routes;
- materialization: deterministic result IDs, declared identity difference
  (`metric_level@v1` vs `evaluate_metric@v1`), same metric/input snapshot refs,
  staleness `fresh`;
- provenance: stable `plan_hash` across runs, zero unconsumed binding-ledger
  clauses, public provenance equal to the current route;
- non-level plans (`explain_change`, `compare_plan`): explicit refusal on
  `c4_level`; deep-equal current-route bundles on the explicit fallback;
- H2 enforced corpus: 10/10 routed parity (envelope statuses, non-level deep
  equality, level adapter-view equality);
- golden level cases: normalized expectations hold on the C4 route, including
  the loss-ratio numerator 132 / denominator 200 /
  `denominator_weighted_mean` preserved inside the canonical value contract.

## Regression

- E-018 tests: 14/14;
- product: 178 discovered, all pass in the standard sandbox (one Seatbelt case
  skips without external sandbox);
- current-route golden 17/17; enforced semantic 10/10; research 58/58;
- default-route behavior unchanged (guard test asserts legacy shape and no
  route marker).

## Qualification

Routing is reversible and opt-in; the default remains the legacy route until
Increment 5 completes per capability. `sales-level` golden assertions on legacy
field spelling (`value_u`) remain tied to the current route; the C4 route holds
the same facts under normalized names, which is the intended end state, not a
compatibility gap. Legacy interpret still silently drops unconsumed year
clauses ("2025년 7월 매출은?" → 2026-07) on both routes — an E-016 intent-
compiler concern scheduled for the demo entry point, not a routing regression.

## Decision

E-018 passes. Metric level may run routed where explicitly selected. Next is
E-019: route period delta the same way, which requires adapting a two-source
`delta@v1` result to the public change boundary and deciding how the C4 payload
declares before/after evidence.
