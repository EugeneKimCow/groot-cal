# Current architecture inventory

Status: observation baseline, 2026-08-16. This is descriptive, not an
endorsement of the current design.

## End-to-end path

```text
question
  -> catalog.resolve_metric (substring vocabulary match)
  -> interpret.interpret (regex intent/time/scope binding)
  -> Query Spec v1 (metric, operation family, scope, period, comparison)
  -> engine.run_question (profile/report/staleness dispatch)
  -> pipeline.execute_query | typed_pipeline.execute_typed_query
  -> ExecutionRuntime + registered Python operator
  -> Evidence Bundle / Result Envelope
  -> structured reporter + deterministic lint
```

There is no data-requirement IR or SQL planner. Both execution profiles load
fixtures into Python memory. The current `Query Spec` is an execution request,
not a typed operator DAG.

## Observed concepts

### Semantic concepts

- Metric identity, aliases, version, type, unit, generation metadata.
- Metric properties: additivity, aggregation rule, sign, time semantics,
  entity type, field bindings, decomposition identities.
- Dimensions: closed values, MECE declaration, applicability constraints,
  entity-functional declaration.
- Comparison: prior period, year over year, plan vintage, or none.
- Scope filters and an `as_of` date.

Primary artifacts: `slice/semantic.json`, `slice/metric_catalog.json`, challenge
fixtures, `schemas/metric-v1.schema.json`.

### Planning concepts

- `operation_family`: `inspect_level`, `explain_change`, `compare_plan`.
- Question signature retained separately in the envelope but not consumed as a
  general planner contract.
- Exploration budget: depth, segments, hypotheses, operator calls.
- Report and staleness intents are detected by regex in `engine.py` and do not
  pass through Query Spec v1.

Missing from the plan contract: explicit operator nodes, breakdown dimensions,
ranking, limits, derived metric expression, multi-metric inputs, conditional
edges, data requirements, and output selection.

### Operator concepts

Machine registry contains eight operators:

1. `metric_level`
2. `rate_level`
3. `distinct_level`
4. `contrib_decomp`
5. `distinct_decomp`
6. `plan_gap`
7. `vrm_lite`
8. `event_overlap_scan`

The registry currently gates operation family and metric type and records an
output type. Most real preconditions, checks, parameters, and postconditions
remain inside Python implementations. The richer prose registry is therefore
not yet the executable source of truth.

### Execution concepts

- Sum-type status: result, out-of-domain, suspended, budget-exhausted.
- Pre-call budget reservation and post-call actual-size validation.
- Flat runtime DAG record with call id, depth, operator, and status.
- Provenance: query spec, semantic model, metric version, input snapshot, as-of.
- Checks, label ceilings, assumption ledger, and operator references.

### Reporting and persistence concepts

- Result-only reporting capability, deterministic primary-result selection,
  structured claims/slots, source reverse checks, label and causal lint.
- Deterministic materialized-result identity and three staleness policies.
- These are downstream consumers. They should consume a stable evidence
  contract without dictating the analytical IR.

## Physical module boundaries

| Boundary | Modules | Observation |
|---|---|---|
| Catalog | `catalog.py` | Resolves one metric and chooses an execution profile. |
| Interpretation | `interpret.py`, `query_spec.py` | Closed regex vocabulary and semantic validation. |
| Commerce path | `pipeline.py`, `kernel.py` | Richest behavior but coupled to commerce fields/events/online VRM. |
| Typed path | `typed_pipeline.py`, `typed_kernel.py` | Generality probe for amount/rate/balance/distinct. |
| Runtime | `runtime.py` | Useful enforcement shell; records calls but does not execute an IR DAG. |
| Reporting | `reporter.py` | Structured downstream boundary, independent of raw data. |
| Results | `result_store.py`, `result_catalog.py` | Pilot persistence/staleness boundary. |
| Evaluation | `eval_*`, tests, simulations | Strong regression assets but narrow planning coverage. |

## Coupling and duplication

1. `engine.py` branches on `execution_profile`, creating two top-level
   execution architectures.
2. Metric-level and contribution behavior is duplicated between commerce and
   typed kernels with different result field names (`value_u`/`value`,
   `delta_u`/`delta`).
3. Both pipelines independently encode family-to-operator routing.
4. Commerce `explain_change` hardcodes all initial axes, dominant-axis
   selection, second-level drilldowns, online-only VRM, and event scanning.
5. Typed pipeline hardcodes metric-type dispatch and silently has a different
   analysis strategy.
6. The JSON operator registry describes admissibility but is not sufficient to
   bind or invoke operators without Python conditionals.
7. Reporter and result selection compensate for heterogeneous result shapes.
8. The canonical boundary says duplicate field bindings and label ceilings are
   enforced, but `_value_binding` does not reject duplicate bindings and the
   reporter does not consume each result's `label_ceiling`.
9. `count` is registered as a metric type but has no fixture or regression.
10. Kernels instrument calls inconsistently: commerce kernels mutate the
    execution record, while typed kernels are wrapped by adapter closures.

## Current special cases

- Regex side-channel intents for reporting and staleness.
- `commerce_extensions` versus `typed_core` profile switch.
- Online-only VRM and commerce event registry in the core commerce pipeline.
- Plan execution only in the commerce path and only for channel scope.
- Rate change explicitly unavailable; distinct has its own decomposition.
- Dominant axis and drilldown selection embedded in one pipeline.
- Closed 2026 monthly interpretation and fixture-backed data access.

## Valuable assets likely to survive redesign

- Typed semantic properties and explicit field bindings.
- Sum-type failures and no silent fallback.
- Runtime-enforced budget, provenance, and deterministic checks.
- Result-only reporting boundary and structured source references.
- Cross-metric challenge fixtures, golden cases, H2 traces, and adversarial
  gate tests.

## Main architectural fault lines to test

1. Whether operation families are useful intent normalization or merely an
   extra dispatch layer above an explicit analytical DAG.
2. Whether metric `type` should drive dispatch, or operator contracts should
   be satisfied structurally by metric capabilities.
3. Whether distinct/rate/amount need distinct primitive operators or can share
   algebraic primitives plus typed aggregation expressions.
4. Whether diagnosis is a stored layer, a domain idiom, or a conditional DAG.
5. Whether plan/report/staleness are analytical operators, adjacent workflows,
   or separate intents compiled by the same harness.
6. How to introduce data requirements and SQL without leaking vendor/storage
   concepts into semantic or analytical contracts.
7. Whether a normalized result carrier can remove reporter/CLI shape probes
   without erasing distinct laws for levels, attributions, and diagnostics.
