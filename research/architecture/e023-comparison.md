# E-023 weekly calendar registration + SQL cross-check

Date: 2026-08-17

## Question

Can a new time grain enter as *registration* — a declared window on the
semantic contract — so that weekly questions pass the same gates monthly ones
do, monthly-only sources refuse by name, and partial weeks suspend honestly?
And does the DuckDB backend compute the same numbers when the identical
estimand is lowered to SQL (pushdown increment 0)?

## Implementation

- `Slice` gained a `window` field (default `month`; monthly wire output is
  byte-unchanged). Registry and evaluator period validation became
  window-keyed (`YYYY-MM` / `YYYY-Wnn`).
- The sales contract registered `available_windows: [month, iso_week]` and a
  `date_field` binding. The four challenge metrics registered nothing — their
  monthly point-in-time sources make weekly questions a *grain refusal*
  (`window_registered`: "iso_week is not registered for this source"), the
  E-007 doctrine executable.
- `evaluate_metric` gained two window gates: registration (declaration-driven,
  no metric-name branch — H1-compatible) and completeness (a selected ISO week
  with fewer than 7 observed days suspends with "N/7일" and a resume
  condition).
- The intent compiler parses "W29"/"2026-W29"/"29주차"(+"대비") into the same
  time roles; the clause contract accepts both period formats (the kind's
  `month` naming is recorded as rename debt, unresolved #23). Weekly targets
  never receive the monthly default baseline — comparison must be explicit,
  otherwise the projection refuses.
- Window propagates through executor segment/drilldown slices. UI examples
  and the LLM prompt carry the weekly format.

## Evidence

- "W29 매출은?" → 832u through all gates; the envelope's time window is
  declared `iso_week/2026-W29`. "29주차" phrasing binds identically.
- "W28 대비 W29 매출이 왜 변했나?" → three-axis weekly contribution,
  Δ=−126 with closed identity; category deltas (식품 −8, 생활용품 −39,
  뷰티 −11, 가전 −68) equal the numbers the earlier ad-hoc chart computed
  outside the gates — same facts, now certified.
- "W31 매출은?" → suspended "(5/7일)" partial-week completeness.
- "W29 재고는?"/"W29 활성 고객 수는?" → named grain refusals.
- Monthly paths untouched: 3860 with `month/2026-07` wire; full regression
  219/219 on both interpreters; golden 17/17; semantic 10/10.

## SQL cross-check (pushdown increment 0)

DuckDB's `strftime(CAST(date AS DATE), '%G-W%V')` reproduces Python's ISO
calendar exactly on this ledger: weekly total (832), weekly per-category
deltas, and the monthly total (3860) all match the operator results. Execution
authority stays with the deterministic operators; this gate proves the SQL
lowering of the same estimand is value-identical, which is the precondition
for a real pushdown increment.

## Qualification

- Onboarding classification: schema-extension (window declarations, date
  binding) + kernel-change (the window subsystem in Slice/evaluator). The
  kernel change is declaration-driven, not metric-named.
- unresolved #17 advances but does not close: weekly works for the daily flow
  source; period-end observation-time selection from a *daily balance* source
  remains open.
- Weekly enters via the intent/demo path only; the legacy Query Spec route
  stays monthly by design.
- Month-ordinal phrasing ("7월 셋째 주") is not bound — ISO week labels only;
  a registered month-week convention would be a calendar-pack addition.

## Decision

Grain entry by registration works: the same gate stack served a new calendar
with two contract declarations, refused it where undeclared, and the SQL
backend agreed on every number it was shown.
