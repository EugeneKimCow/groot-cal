# E-027 unit-bucket window + Bosch onboarding

Date: 2026-08-18

## Question

Can a calendar-less source enter the window contract by registration — an
anonymized-unit bucket calendar — such that bucket questions execute, calendar
questions refuse by name, and the (a)-direction decision ("구간별 추이 지원")
holds without any metric-name branch?

## Contract extension

- `unit_bucket` window: period label `U{start:04d}`, membership
  `floor(t / width) * width`, declared per metric as
  `properties.unit_bucket.width` + a `time_field` binding — gated by
  `window_bucket_contract`.
- **Month lost its privilege**: `_validate_window` now checks every window
  including month against `available_windows` (default `("month",)` keeps all
  existing metrics unchanged). A calendar-less source refuses "3월 …" by name
  — the symmetric counterpart of E-023's weekly refusal on monthly sources.
- The `dimension_coverage` check was quietly month-hardcoded (vacuous for
  non-month windows since E-023) — now window-aware; dead `_matches` removed.
- Intent path: `U\d{4}` tokens (±"구간", "대비") bind as periods; clause
  contract accepts the label; the LLM prompt documents it.

## Onboarding (instrumented, from bosch.duckdb)

Grain decision: (bucket × line-path) aggregates — 119 rows — over which
rate's Σnum/Σden and count's Σ are exact; the fixture is aggregate statistics,
so it commits cleanly despite the raw data's no-redistribution license.
Two metrics: `quality.failure_rate` (rate, denominator-weighted) and
`quality.inspected_parts` (count). `path` is MECE by construction (one path
per part). Gates 5/5:

- "U0300 구간 불량률은?" → 1.0348% (591/57,110 exact);
- "U0300 구간 L0-L3 불량률은?" → scoped 519/49,802;
- "U0300 대비 U0400 검사수가 왜 변했나?" → Δ−11,400, path-axis identity
  closed;
- "U0300 대비 U0400 불량률이 왜 변했나?" → rate-change contract refusal;
- "3월 불량률은?" → named grain refusal.

## Two system gaps the real data exposed (both fixed + pinned)

1. **Substring value double-binding**: "L0-L3" spawned three filters
   (L0-L3, L0, L3) because dimension-value matching never reserved spans —
   sales values were never substrings of each other. Now global longest-first
   non-overlapping matching.
2. **Silent last-wins filters**: `_emit_calls` built the scope dict by
   overwrite, so the conflicting filters executed as `path=L3` (0.0 rate) —
   a silent-substitution-class hole beyond the proposer. Projection now
   refuses conflicting same-dimension filters ("explicit composition is
   required").

## Regression

E-027 tests 10/10; production 250 on both interpreters; golden 17/17;
semantic 10/10; C2′ rule baseline 10/10; weather/challenge metrics untouched.

## Qualification

- Bucket labels (U0000) are an engineering vocabulary, not user language —
  UX naming is open. Edge buckets (U1700: 2,294 parts) are partial in an
  unknowable way (anonymized axis) — no completeness gate is possible, noted
  in the description document.
- Station-level (52-value) and part-grain questions need a multi-grain
  design (part_station visit grain vs part grain) — deferred, registered
  below.

## Decision

The (a) direction holds: calendar-less time entered as a registered window
with two declarations, and the same gate stack now refuses calendars where
they do not exist. Real data has now broken — and repaired — the system five
times across two onboardings (empty segments, year context, column typing,
substring binding, filter conflicts): the onboarding kit is functioning as
the counterexample generator the research method wanted.
