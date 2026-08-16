# Next experiment

## E-018 — Controlled metric-level routing

Route only `inspect_level` through the C4 compiler/executor behind a reversible
selector while preserving the current public envelope, result payload, storage,
reporting, provenance, and failure behavior.

1. Add an explicit route selector whose default preserves the current route.
2. Adapt only successful and normalized failure metric-level C4 results to the
   existing public bundle boundary; do not add shape probing outside E-014.
3. Run all five metric algebras, scoped level, missing data, bad binding, bad
   scope, label ceiling, materialization, reporting, and provenance cases through
   both selectors.
4. Require byte- or normalized-field parity at the public boundary and preserve
   deterministic Plan/binding identity in the execution record.
5. Refuse any non-level Plan on the routed selector and fall back only by an
   explicit caller choice, never silently.
6. Keep contribution, plan, set-transition, and drilldown routing disabled.

## Discriminating risks

- Existing callers may depend on legacy result field spelling even though E-014
  consumers no longer do. The route adapter must not broaden compatibility debt.
- Current execution records use legacy operator names and short hashes; the C4
  record must preserve public evidence references without pretending identity.
- Report and materialization parity may reveal that the public bundle boundary,
  not arithmetic, is the real migration constraint.

## Sequenced work after E-018

Route period delta next, then additive contribution, explicit nested drilldown,
plan comparison, and registered non-additive operators. Revisit Ref-capable
dynamic Slice requirements before enabling drilldown.
