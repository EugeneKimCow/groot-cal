# E-017 existing analytical-path shadow parity

Date: 2026-08-16

## Question

Can executable C4 Calls reproduce the supported current analytical paths without
changing production routing or restoring implicit operation-family pipelines?

## Implementation

- `slice/shadow_executor.py` executes only registered C4 Calls and is not
  imported by `engine`.
- `evaluate_metric@v1` reuses the normalized aggregation-algebra evaluator for
  sum, ratio-of-sums, period-end balance, and entity cardinality.
- `contribution@v1`, `rank@v1`, `align_metrics@v1`, `plan_gap@v1`, and provisional
  `drilldown@v1` have deterministic shadow implementations.
- distinct change compiles to `set_transition@v1`, not additive contribution.
- budgets are checked before calls, Plan identity and per-Call status are
  recorded, and source evaluations retain provenance.

The E-016 compiler now emits one explicit contribution branch per default axis,
preserves target-level plus change multi-output intent, clarifies missing plan
vintage and invalid month, and compiles pinned plan comparison directly to
`plan_gap@v1`.

## Parity evidence

- level parity across all five catalog metrics/algebras: 5/5;
- sales change totals and segment deltas across channel, category, and customer
  type: 3/3 axes;
- typed operating-profit and period-end inventory change: parity;
- distinct regional change: parity through `set_transition@v1`, with explicit
  entrant/exit/migration sets;
- rate change: unchanged safe refusal;
- pinned total/scoped plan gap: numeric and segment parity;
- top-three category selection: parity, including stable registered-dimension
  tie order;
- explicit valid nested drilldown: numeric and segment parity;
- enforced semantic shadow corpus: 10/10 normalized outcomes;
- analytical golden-equivalent cases are covered; the three result/report
  workflow cases remain outside Analytical IR and stay on the unchanged route.

## Counterexamples and revisions

The first rank implementation reordered equal-magnitude food and beauty changes
by label. This changed Top-N selection semantics. The executor now preserves the
registered dimension order as the stable tie-break.

A requested product-to-region drilldown fails because region is defined only
inside offline scope. The shadow path refuses at semantic evaluation instead of
inventing region coverage.

Distinct counts cannot safely use ordinary additive contribution. E-017 added a
provisional domain-independent set-transition contract that exposes entrants,
exits, and migrations. Whether this remains a primitive or lowers to set
operations is still open.

## Regression

- E-017 tests: 15/15;
- product: 164 discovered, 163 passed and one environment Seatbelt skip;
- current-route golden: 17/17;
- current-route enforced semantic: 10/10;
- research: 58/58;
- production routing changes: zero.

## Qualification

Numeric, failure, budget, provenance, selection, and evidence-ceiling parity is
supported for the representative current analytical paths. The provisional
`drilldown@v1` implementation performs child evaluations inside its operator;
before routing drilldown, a later experiment must decide whether dynamic Slice
predicates require explicit Ref-capable data-requirement Calls instead.

## Decision

E-017 is sufficient to begin controlled, reversible routing with metric level
only. Contribution, set transition, plan, and drilldown remain shadow until each
capability-specific routing gate passes.
