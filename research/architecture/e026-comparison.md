# E-026 real-data onboarding kit + instrumented dry run

Date: 2026-08-17

## Question

The pilot's oldest registered product risk: what does it actually cost to
register *real* data — data we did not author — into the contract, and does
the gate stack survive contact with it? E-026 builds the onboarding kit and
runs it against a real public dataset (vega-datasets `seattle-weather.csv`,
BSD-3: 1,461 daily observations, 2012–2015), measuring every step.

## The kit (slice/onboard.py)

The design thesis: **the knowledge-acquisition cost is the API signature.**
`profile_csv` collects only machine-derivable facts (column kinds, dimension
value enumeration, null counts, date span); `scaffold_contract`'s keyword
arguments are exactly the declarations only a human can make (identity, type,
unit, sign, value-column choice, MECE judgment, aliases, windows). Completion
is not a document — it is `evaluate_metric` passing.

## The onboarding ledger (Seattle precipitation)

- Machine-derived: 1,461 rows; span 2012-01-01→2015-12-31; `weather` is a
  5-value low-cardinality column; four numeric candidates; zero nulls.
- Human declarations (9): id, name 강수량, aliases, type=amount (daily flow),
  unit=mm (not derivable from data!), value_field=precipitation, sign=
  nonnegative (physical domain), weather as MECE dimension (one label per
  day), windows month+iso_week (daily grain).
- Iterations to green gates: **3** — the two failures were not declaration
  errors but *system gaps that fixtures had never exposed*.

## Three discoveries (real data broke fixture assumptions)

1. **Empty-segment semantics.** February 2015 has zero snow days; the
   weather-axis change decomposition suspended ("rows 2015-02") where the
   truth is *a zero observation over a covered period*. Fixtures always had
   every segment populated. Fixed as a strategy declaration
   (`empty_selection`): additive/cardinality → 0; period-end balance →
   suspended (a missing snapshot is not zero); ratio → the Σdenominator=0
   check already suspends honestly. Period coverage and weekly completeness
   are now computed on period rows, not the predicate selection.
2. **Year-context propagation.** "2015년 2월 대비 3월…" bound the bare 3월 to
   the default year 2026 — the sales corpus is single-year, so this never
   surfaced. Deterministic rule: exactly one explicit year in the question →
   it propagates to bare months; multiple explicit years + a bare month →
   clarification.
3. **Column-level numeric typing.** Per-value int/float normalization (0 vs
   10.9) broke DuckDB DOUBLE round-trip hash parity. Fixture columns are now
   typed per column.

## Gate evidence (all four validation questions)

- "2015년 3월 강수량은?" → 113.5mm through every gate;
- "2015년 2월 대비 3월 강수량이 왜 변했나?" → weather-axis contribution,
  Δ −20.7mm, identity closed, snowless segments as zero observations;
- "2015-W10 강수량은?" → 0.0mm (a genuinely dry week — weekly window worked
  on the onboarded source immediately, since windows are registration);
- "2015-W53 강수량은?" → suspended "(4/7일)" at the data edge.
- The metric is registered in both catalogs (fixture + DuckDB table) and
  visible in the query window; existing metrics and all standing gates are
  untouched (240 tests, both interpreters).

## Qualification

One dataset, clean CSV, no joins, no vintage/correction history — the
easy end of onboarding. The measured shape (9 human declarations, 3 system
gaps, gate-passing as the completion criterion) is the baseline for the real
target: the user's own data, where source documentation and semantics are
the actual bottleneck. Float display precision (−20.69999…) is a rendering
policy the contract does not yet declare.

## Decision

The onboarding kit works against real data and the gates did their job —
every failure was a genuine semantic gap, found and fixed as declarations,
not patches. Ready for a user-supplied dataset.
