# Architecture proxy metrics

Metrics are evidence aids, not a single objective function.

## Definitions

- Query coverage: fully representable / total corpus. Refusal with the correct
  missing contract counts as safe handling, not analytical coverage.
- Concept count: semantic kinds + planning node kinds + operator kinds + core
  workflow kinds used to explain execution.
- IR node/type count: distinct executable node variants, excluding parameters.
- Canonical operator count: independently specified mathematical estimands.
- Operator reuse ratio: domain analytical patterns using only canonical
  operators / all executable domain patterns.
- Domain exception count: domain-named branches or separate runtimes in core.
- Special planner rule count: non-compositional dispatch rules.
- Deterministic execution ratio: executable plan/math/validation nodes that do
  not require LLM judgment / all executable nodes.
- Planning stability: paraphrase groups normalized to equivalent plans.
- Regression failures: previously passing assertions broken by an experiment.

## Iteration 0 baseline

| Proxy | Observed value | Qualification |
|---|---:|---|
| Current golden queries | 17 | Narrow supported corpus. |
| Golden pass | 17/17 | Current behavior only. |
| Enforced semantic cases | 10/10 | Current behavior only. |
| Metric nominal types | 5 | amount, count, rate, balance, distinct. |
| Registered operators | 8 | Machine registry. |
| Operation families | 3 | Does not include report/staleness side channels. |
| Execution profiles | 2 | commerce extensions and typed core. |
| Domain-named core branches | at least 4 | profile, online VRM, events, channel-only plan. |
| Explicit IR node types | 0 | Query Spec contains no operator nodes. |
| SQL/data planner implementations | 0 | Fixture loaders only. |
| Unit regression | 83 pass, 1 skip | 84 discovered. |

Corpus coverage and concept counts for C0–C4 are intentionally blank until
E-002 defines auditable scoring rules.

## E-002 structural comparison

| Candidate | Initial 40 | Held-out attempt 2 | Revised structural ceiling |
|---|---:|---:|---:|
| C0 current | 10/40 | 10/50 | 10/50 |
| C1 semantic-heavy | 31/40 | 31/50 | 31/50 |
| C2 operator-centric | 26/40 | 26/50 | 26/50 |
| C3 IR-centric | 40/40 | 40/50 | 50/50 |
| C4 three-contract Call DAG | 40/40 | 40/50 | 50/50 |

The final column is not execution coverage. Only E-003/E-004's eight behavior
tests execute prototype IR behavior. The held-out cycle changed the minimum
semantic contract but did not add an IR node form.

After E-005: 13 research behavior/state tests pass. Prototype operator evidence
now covers metric evaluation, requested/nested additive decomposition,
rate/mix identity, and entity-transition identities.

After E-006: 17 research tests pass. Data-planning evidence covers additive and
ratio-of-sums lowering across a many-to-many relationship, including pre-SQL
policy refusal and reconciliation.

After E-007: 22 research tests pass. Temporal evidence covers distinct reducers,
missing-grain refusal, fiscal-period resolution, and daily-to-weekly alignment.

## E-008 second held-out wave

| Candidate | Before Q051–Q060 | Closed-world first score | Revised structural ceiling |
|---|---:|---:|---:|
| C0 current | 10/50 | 10/60 | 10/60 |
| C1 semantic-heavy | 31/50 | 31/60 | 31/60 |
| C2 operator-centric | 26/50 | 26/60 | 26/60 |
| C3 IR-centric | 50/50 | 50/60 | 60/60 |
| C4 three-contract Call DAG | 50/50 | 50/60 | 60/60 |

The revised ceiling is not execution coverage. The convergence observation is
zero new IR node forms across two ten-query held-out waves.

## Final research measurement

- Shared corpus: 60 queries across more than 30 categories.
- Structural ceiling: C0 10/60, C1 31/60, C2 26/60, C3 60/60, C4 60/60.
- Research executable tests: 31/31.
- IR node forms added after the initial Call+Ref hypothesis: 0; typed guard is a
  Call condition, not a node class.
- Current paraphrase planning stability probe: 4/5 equivalent intents.
- Production regressions: 83 pass + one environment skip; golden 17/17;
  enforced semantic baseline 10/10.
- Production files refactored: 0.

Concept counts in candidate manifests remain judgmental proxies. C4's advantage
over C3 is minimal grammar, not proven implementation cost.

## E-011 integrated comparison

- shared query subset: 5
- result and execution-record parity: 5/5
- research tests: 40/40 total, including 9 integrated tests
- C4 node classes / lowering cases: 1 / 0
- C3 node classes / lowering cases: 6 / 6
- C4 authoring bytes: 2,306
- C3 authoring bytes: 1,768
- C3 runtime bytes after lowering: 2,306
- materially better tested C3 errors: 0

## E-012 production shadow increment

- new production contract modules: 3
- new versioned schemas: 2
- existing execution-route files modified by E-012: 0
- shadow/contract tests: 18/18
- production tests: 102 discovered, 101 pass, one environment skip
- golden / semantic / research: 17/17, 10/10, 40/40
- shadow capabilities compiled: metric level, simple period delta
- unsupported capability tested fail-closed: plan comparison
- structured silent-loss attacks rejected: top-level rank, nested breakdown
- natural-language intent recovery added: 0 (explicit limitation)

## E-013 normalized scalar evaluation

- catalog level query parity cases: 6/6
- nominal metric types exercised: 5/5, including new count fixture
- aggregation strategies: 4
- domain metric IDs in evaluator: 0
- per-type arithmetic branches in evaluator: 0
- generic metric-type checks: descriptor vocabulary + strategy admissibility
- duplicate binding attacks rejected by candidate / legacy: 1 / 0
- E-013 tests: 15/15
- production tests: 117 discovered, 116 pass, one environment skip
- golden / semantic / research: 17/17, 10/10, 40/40
- existing execution-route files modified by E-013: 0
- reporter field-shape probes removed: 0 (Increment 2 gate remains open)

## E-014 normalized result boundary

- central result adapters: 1
- downstream legacy scalar/change probes: 0
- public payload migrations: 0
- adapter-focused regression cases: 15
- integrated live duplicate-binding cases: 1
- `LBL02` escalation attacks rejected: 2/2
- production tests: 133 discovered, 132 pass, one environment skip
- golden / semantic / research: 17/17, 10/10, 40/40
- analytical routing changes: 0
- Increment 2 exit gate: complete

## E-015 intent contract discriminator

- annotated shared cases: 12
- successful Plan cases: 7
- byte-identical Plans between candidates: 7/7
- identical refusal/clarify outcomes: 5/5
- required silent-substitution attacks represented: 9/9
- shared versioned binding-record types: 1
- Bound Intent Spec additional contract types / bytes: 1 / 2,646
- Bound Intent Spec duplicated bound values: 34
- direct Plan additional contract types / bytes: 0 / 0
- newly discovered first-objective substitution attacks rejected: 1/1
- E-015 tests: 18/18
- full research regression: 58/58
- product / golden / semantic: 132 pass + one skip / 17/17 / 10/10
- production routing changes: 0

## E-016 shadow intent fidelity

- required adversarial questions accounted: 9/9
- supported lossless Plans / explicit safe refusals: 4 / 5
- silent substitutions: 0
- existing change paraphrases normalized: 5/5
- successful material clauses without Plan consumers: 0
- unregistered refs in successful Plans: 0
- closed source-clause record types: 1
- E-016 tests: 16/16
- product tests: 149 discovered, 148 pass, one environment skip
- golden / semantic / research: 17/17, 10/10, 58/58
- production routing changes: 0

## E-017 executable shadow parity

- metric-level algebra parity: 5/5
- sales change axes with total/segment parity: 3/3
- typed amount / balance / distinct change parity: 3/3
- pinned and scoped plan-gap parity: 2/2
- ranking tie-order attacks found / fixed: 1 / 1
- valid explicit drilldown parity / invalid-scope refusal: 1 / 1
- shadow enforced semantic outcomes: 10/10
- provisional canonical operators added: `set_transition@v1` (1)
- E-017 tests: 15/15
- product tests: 164 discovered, 163 pass, one environment skip
- current golden / semantic / research: 17/17, 10/10, 58/58
- production routing changes: 0

## E-018 controlled metric-level routing

- routed level algebra parity (adapter view): 5/5
- scoped level parity: 1/1
- identical failure payloads at the query_spec boundary: missing month, bad scope
- duplicate-binding fail-closed on both routes: 1/1
- reporting claim text/label parity with clean lint: 1/1
- deterministic materialization IDs with declared operator identity: 2/2 routes
- H2 enforced corpus routed parity: 10/10
- golden level cases normalized on C4 route: 3/3
- silent fallbacks: 0 (non-level refusal is explicit; fallback is caller-chosen)
- public-boundary counterexamples found and fixed: 1 (assumption ledger
  dropped from routed bundles; now shared domain-pack constant)
- E-018 tests: 14/14
- production tests: 178 discovered, 178 pass in standard sandbox
- current golden / semantic / research: 17/17, 10/10, 58/58
- default-route behavior changes: 0

## E-019 controlled period-change routing

- sales three-axis contribution parity (values/segments/pct): 3/3 axes
- typed additive change parity: 2/2 (operating profit, period-end inventory)
- distinct set-transition parity with explicit entrants/exits: 1/1
- rate-change refusal deep-equality at the result key: 1/1
- event evidence rows/overlap flags/hypotheses budget parity: 1/1
- change memo report claim parity (14 claims) with clean lint: 1/1
- hidden strategy outputs (drill:*, vrm:*) on routed boundary: 0 (declared)
- deterministic contribution materialization: 1/1
- E-019 tests: 11/11
- production tests: 189 discovered, 189 pass in standard sandbox
- current golden / semantic / research: 17/17, 10/10, 58/58
- default-route behavior changes: 0

## E-020 demo entry point

- adversarial corpus through demo: 9/9 accounted (2 executed, 5 intent
  refusals, 2 named unrouted-capability refusals), substitutions 0
- change paraphrases executed on routed operators: 5/5
- intent-compiler vs Query-Spec-route agreement (category contribution): exact
- level demo vs current route: exact (3860)
- E-020 tests: 8/8
- production tests: 197 discovered, 197 pass in standard sandbox
- current golden / semantic / research: 17/17, 10/10, 58/58
- default CLI/engine behavior changes: 0

## E-021 local LLM proposal adapter (C2′ increment 1)

- fail-closed contract tests (fake transport, no network): 7/7
- live end-to-end level binding (Ollama): 1/1
- governed corpus, gemma3:12b: full agreement 8/14; silent substitutions 0/14;
  wrong numbers 0/14; all 6 divergences = one proposal error (delta for
  contribution), every instance contract-converted to refusal or
  coarser-correct answer
- governed corpus, qwen2.5:72b (6 divergent re-run): 4/6 byte-identical DAG
  convergence; 1 defensible delta reading (correct −340); 1 identical
  fail-closed double-binding
- deterministic guards exercised: span recovery (hallucinated text dropped +
  residual confessed), relative-month recomputation, first-wins overlap
- production tests: 205 discovered, all pass (live LLM test auto-skips
  without Ollama); golden 17/17; semantic 10/10
- default route / rule-based demo behavior changes: 0

## E-022 DuckDB storage port + query window

- backend parity: 5/5 metrics rows·sem·input-hash identical; 4/4 engine
  bundles byte-identical across backends
- counterexamples found/fixed: 1 (DB binary inside the frozen H2 allowlist
  directory; relocated to store/)
- silent fallbacks in the loader: 0 (absent backend fails by name)
- production tests: 209 (system python, duckdb skip) / 209 (venv, all run)
- UI: stdlib-only SSE server; pipeline logic shared with CLI via one
  events generator

## E-023 weekly calendar registration + SQL cross-check

- weekly level/change through full gates: 832u; Δ−126 with closed identity,
  segment map equal to the prior ad-hoc computation (now certified)
- partial-week suspension: 1/1 ("5/7일" + resume condition)
- grain refusals on monthly-only sources: 2/2 (window_registered)
- weekly default-baseline guard: explicit comparison required (1/1)
- monthly wire/values unchanged; regression 219/219 on both interpreters
- SQL cross-check (pushdown increment 0): weekly total, weekly category
  deltas, monthly total — 3/3 value-identical between DuckDB SQL and the
  deterministic operators
- metric-name branches added for the new grain: 0 (declaration-driven)

## E-024 C2′ increment 2 — advisory vs LLM-under-contract

- rule-proposer harness baseline: 10/10 (after fixing a scorer false
  positive: plan_gap subject consumption flagged as substitution)
- initial C2′ (qwen2.5-coder:14b, 50 runs): 40/50; substitutions 0; wrong
  values 0; unstable cases 0; both failures deterministic 5/5
- contract gap found: alias fidelity (subject text need not witness a
  registered alias) — fixed with a deterministic adapter guard + tests
- guarded C2′: **50/50 (100%)** — equal to deterministic enforced on the
  analytical span
- comparison: C1 advisory (frontier model, free execution) ≤29/50 (≤58%);
  C2′ (local 14B under contract) 50/50
- new tests: 5 (harness gates 3 + guard tests 2); production 224 green
