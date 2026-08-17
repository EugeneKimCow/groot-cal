# E-022 DuckDB storage port + query window

Date: 2026-08-17

## Question

Can the data backend become a real replaceable port (unresolved #12's first
half) with zero observable change at every governed boundary, and can the demo
pipeline surface as an interactive window without touching its authority?

## Implementation — storage port

- `slice/build_duckdb.py` loads the existing sources (sales CSV via the
  legacy loader, four challenge fixtures) into `slice/store/groot.duckdb`
  with an explicit `_seq` column so row order — and therefore the input
  snapshot hash — is preserved exactly. The DB binary is generated, not
  committed.
- `catalog.py` gained a registered `duckdb` loader (lazy import, explicit
  failure naming the venv when the package is absent — no silent fallback to
  fixtures) and env-selectable catalogs (`GROOT_CATALOG`). The default catalog
  is unchanged; `metric_catalog.duckdb.json` reuses the same semantic
  contracts and only swaps the rows source.
- Dependency policy: the contract core stays stdlib-only; DuckDB lives in a
  project venv as a port dependency, exactly where the architecture said
  technology may vary.

## Parity evidence

- all 5 metrics: semantics, rows, and input snapshot hashes byte-identical
  across backends;
- engine bundles byte-identical on both routes (level current, rate level,
  sales change C4, inventory change C4);
- one counterexample found and fixed during the increment: the generated DB
  initially landed in `slice/data/`, which the frozen H2 isolation allowlist
  ships wholesale — the binary broke the resource payload. Relocated to
  `slice/store/`; the frozen H2 runner stayed untouched.

## Implementation — query window

- `slice/ui.py`: stdlib-only ThreadingHTTPServer. Input bar → SSE progress
  lines → evidence-bounded result cards in a scrolling feed. Interpreter
  select (rule / default LLM / accuracy LLM); data-source badge shows which
  backend the session loaded (DuckDB store when built).
- `demo.py` was restructured around `demo_question_events`, a generator
  yielding stage events then the outcome; `demo_question` drains it, so CLI,
  tests, and UI share one pipeline with no duplicated logic.

## Regression

- 209 tests on system python (duckdb gate skips cleanly) and 209 on the venv
  python (duckdb parity gate runs: 3/3);
- golden 17/17, semantic 10/10 unchanged;
- UI smoke: page serves, SSE streams stages and results for executed,
  refused, and LLM-interpreted questions.

## Qualification

This is the *storage* half of the backend port: rows load from DuckDB, but
aggregation still runs in the deterministic operators — SQL pushdown of the
logical Data Requirements (E-006's second half) remains open, and is now the
natural place to test grain declarations (weekly calendars, unresolved #17)
against a real query engine.

## Decision

The port boundary held: swapping storage moved no observable value, hash, or
bundle byte. The window makes the contract's behavior — stages, refusals,
label ceilings — the interface itself.
