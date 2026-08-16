# E-019 controlled period-change routing

Date: 2026-08-16

## Question

Can `explain_change` route through the C4 compiler/executor with public parity
for everything downstream consumers actually depend on — per-axis contribution,
set transition, event evidence, reporting, materialization — while the hidden
exploration strategy the research rejected stays out of the routed boundary?

## Implementation

- `compile_shadow_plan` now compiles `explain_change` to the per-axis
  (before, after, contribution|set_transition) triplet DAG that is isomorphic
  to the current public boundary, replacing the E-012 delta-root stub. Axis
  selection mirrors both current pipelines: decomposition-identity dimensions
  when declared, all registered dimensions otherwise, minus scope-fixed axes
  (recorded as excluded, surfaced as runtime-rejected). Rate change refuses at
  compile with the same `change_operator_available` payload the typed route
  emits.
- The commerce event-comparison idiom became an explicit registered Call:
  `event_overlap_scan@v1` wraps the deterministic kernel scan, appears in the
  plan and binding ledger, and passes its legacy evidence rows through without
  canonical pretense. Canonicalizing the Description payload is deferred.
- `result_adapter` learned the canonical `Attribution` change view (total,
  unit, pct with denominator ref, segments) — target-state adapter work, not
  compatibility debt.
- The selector generalized from `c4_level` to `c4` / `c4_or_current`; routed
  families are now `inspect_level` and `explain_change`; `compare_plan` still
  refuses explicitly.

## Declared boundary reduction, by design

The current commerce route also emits `drill:*` (dominant-axis auto-drilldown)
and `vrm:online`. No golden case, H2 expectation, reporter path, or
materialization consumer reads them — they are exactly the hidden pipeline
strategy synthesis §10 removes from core dispatch. The routed boundary
deliberately omits them; nested drilldown returns only as explicit intent
(`drilldown@v1`, E-017) and VRM as a registered operator when its gate comes.
A test pins this as a declared difference, not an accident.

## Parity evidence (both selectors)

- sales three-axis contribution: totals (4200→3860, Δ−340, −8.1%), all
  segment deltas, golden expectations on canonical paths;
- scoped change: fixed axis excluded on both routes, identical segment maps,
  rejection recorded;
- typed operating-profit (−60) and period-end inventory (+10) changes: parity;
- distinct regional change: parity plus explicit entrants/exits/migrations
  (`set_transition@v1`), entrants `c4`,`c5`;
- rate change: deep-equal refusal payload at the same result key;
- event scan: identical evidence rows and overlap flags, identical
  hypotheses-budget consumption, spelled `event_overlap_scan@v1` on both;
- reporting: change memo claims (14) and labels byte-identical, same selected
  result key, lint clean on both routes;
- materialization: deterministic result IDs with declared
  `contribution@v1` identity;
- plan hash stable, binding ledger fully consumed.

## Regression

- E-019 tests: 11/11; E-018 suite updated for the generalized selector;
- product: 189 discovered, all pass in the standard sandbox;
- current-route golden 17/17; enforced semantic 10/10 (routed parity holds in
  the standing H2 gate); research 58/58.

## Qualification

- The executor still stops the whole plan at the first failing call. Current
  fixtures cannot discriminate break-versus-isolate semantics (typed metrics
  are single-axis; commerce gates are global), so failure isolation for
  independent DAG branches is recorded as an open question that must be
  settled before drilldown or multi-source routing.
- Commerce `share_of_change` suppression (§4.1) lives in the legacy kernel and
  has no active consumer through the adapter view; it must become a registered
  check before any renderer consumes shares from the C4 payload.
- `CHANGE_LABEL_CEILING` is declared by the route adapter; ownership belongs
  in the operator registry contract.

## Decision

E-019 passes. Level and period change may run routed where explicitly
selected. The demo increment can proceed on routed capabilities; plan
comparison, drilldown, and non-additive operators remain gated.
