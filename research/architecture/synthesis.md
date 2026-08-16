# Evidence-backed architecture synthesis

Status: research conclusion, not production migration plan.

## Surviving architecture

groot-cal compiles an analytical question into a typed, replayable plan; binds
that plan against semantic contracts; derives logical data requirements; lowers
them through replaceable backend adapters; executes canonical deterministic
operators and checks; and returns evidence-bounded results to downstream
renderers.

```text
Question
  -> compiler/agent harness
  -> Bound Intent + typed Plan(Call DAG)
       -> Semantic Contract resolution
       -> logical Data Requirements -> backend adapter -> data
       -> Analytical Contract execution/checks
  -> Evidence Results
  -> report/result workflow
```

There are three primary logical contracts. Catalogs and Domain Packs are
authorities feeding them. Data backends, result stores, governance policies,
and renderers are ports or consumers, not extra analytical layers.

## 1. Minimum semantic contract

The minimum is thin about workflow but deliberately rich about data meaning:

- stable metric/expression id and version, unit, sign/bounds/null policy;
- value expression or field bindings and dependency references;
- source grain, entity keys, observation time role, available grain;
- aggregation algebra across dimensions and time, including allowed reducers;
- dimensions/entities, hierarchy, functional dependency and applicability;
- relationships with join cardinality, valid time, allocation/fanout policy;
- registered calendars, windows, cohorts, scenarios and data vintages;
- provenance/source references and known generation limitations.

Aliases and domain language are Domain Pack material. SQL text and diagnostic
workflow are not semantic concepts.

## 2. Minimum analytical operator model

Every operator is a versioned typed contract:

```text
typed inputs + explicit parameters/convention
preconditions/check ids
-> result | out_of_domain | suspended | budget_exhausted
typed output + invariant + provenance + label ceiling
```

The smallest supported core begins with metric evaluation driven by aggregation
algebra, comparison/delta, grouped evaluation/reconciliation, deterministic
selection/ranking, and typed predicates. New primitives require a distinct
estimand and law. E-005 justified rate/mix and entity-transition contracts;
E-010 showed quantiles cannot reuse additive contribution. Changepoint,
uncertainty, distribution, and causal-model operators remain separate when
their assumptions/laws differ. Domain names never justify primitives.

## 3. Minimum Analytical IR grammar

```text
Plan(version, calls, outputs, limits, binding_ledger)
Call(id, operator_ref@version, inputs, parameters, optional typed guard)
Input = literal | semantic_ref | result_ref | Slice
Slice = time/calendar/cohort + predicates + grain expectation
```

References are DAG edges. A false typed guard produces a recorded skipped node.
Data Requirements are compiler output derived from Calls, not a fourth
planner-authored language. The operator registry carries type/law complexity;
the generic Call is safe only if that registry is closed and executable.

## 4. Domain Pack boundary

Domain Packs contain:

- aliases and domain language;
- semantic instances, source mappings and registered relationships;
- preferred dimensions and reusable plan idioms;
- domain policies such as approved allocation or reporting vocabulary.

They do not contain a parallel engine, domain-specific copies of mathematical
operators, free-form SQL, or causal conclusions.

## 5. Diagnosis Layer

A separate logical Diagnosis Layer is unnecessary. Requested breakdown,
dominant selection, nested drilldown, conditional branching, rate/mix analysis,
and transition analysis were expressed as typed Calls and edges. “Diagnosis” is
a reusable plan idiom or runtime behavior, not persistent semantic authority.

## 6. What the LLM decides

- interpret language and resolve ambiguity;
- bind explicit intent clauses to semantic references;
- choose an admissible plan/operator composition and bounded exploration;
- request clarification when material clauses cannot be consumed;
- render evidence into language within result/report contracts.

The compiler must record a binding ledger so metric modifiers, requested axes,
rank/limit, time, comparison, and output constraints cannot disappear silently.
Current regex planning scored only 4/5 on a small paraphrase probe.

## 7. What is deterministic

Schema and semantic validation, type/admissibility checking, Data Requirement
derivation, backend lowering, aggregation and analytical math, result-reference
resolution, guards/selectors, budgets, invariants, provenance, freshness,
privacy reconciliation, evidence ceilings, and report lint. The LLM never
creates numeric results or silently substitutes an estimand.

## 8. SQL position

SQL is a backend-lowering artifact below logical Data Requirements. E-006
showed that source grain, relationship cardinality, allocation policy, and
ratio-of-sums expression must be fixed before SQL. A naive join inflated 160 to
260; validated equal-split lowering reconciled both additive and ratio
components.

## 9. Storage and vendor neutrality

Semantic ids/expressions, Analytical Contracts, Plan/Call/Slice, Data
Requirements, Result/Evidence contracts, and checks are neutral. PostgreSQL,
SQLite, TypeDB, YAML, graph stores, in-memory fixtures, and report formats are
replaceable realizations. Backend-specific capabilities may affect lowering or
suspension but not redefine the logical estimand.

## 10. Current abstractions: retain, merge, redesign, remove

### Retain

- explicit bindings/version/as-of and aggregation properties;
- sum-type failures with no silent fallback;
- runtime budgets, provenance, deterministic gates and label ceilings;
- result-only reporting and structured source references;
- cross-metric fixtures, golden cases, H2 traces and adversarial tests.

### Merge

- `metric_level`, `rate_level`, `distinct_level` orchestration into metric
  evaluation driven by aggregation algebra;
- commerce/typed bundle and normalized result carriers;
- duplicated scope, sign, coverage and binding checks into registered checks;
- commerce and typed pipelines into one plan executor.

### Redesign

- Query Spec into Bound Intent plus executable Plan;
- operator registry into a complete executable typed contract;
- semantic model to include grain, relationships/cardinality, calendars and
  typed expressions without absorbing workflows;
- result contracts so reporting does not probe incompatible field names;
- interpretation validation to detect unconsumed question clauses.

### Remove from core dispatch

- `execution_profile` parallel runtimes;
- hardcoded all-axis/dominant-axis/online-VRM/event-scan pipeline strategy;
- operation-family-to-pipeline dispatch (family may remain audit metadata);
- a separate Diagnosis Layer;
- domain-specific operator copies and free-form LLM calculations.

## 11. Architecture surviving strongest counterexamples

C4, the three-contract generic Call DAG, survived:

- five silent-intent-loss probes and paraphrase instability;
- additive, signed, ratio, balance and distinct level evaluation;
- requested and nested breakdown with typed references/guards;
- pure rate-mix shift and hidden entity migration;
- many-to-many SQL fanout and ratio pushdown;
- period-end versus daily average, missing grain and fiscal windows;
- valid-time history, privacy residual and multi-source freshness;
- deterministic versus causal counterfactual boundary;
- non-additive quantile change;
- two closed-world held-out waves totaling 60 shared queries.

E-011 resolved the C3 alternative on an integrated representative slice. C3
produced identical results and type errors, required six node classes and six
lowering cases, and compiled to the C4 wire representation. C4 is therefore the
canonical IR. C3-style typed builders may be generated from the registry for
SDK ergonomics, but are not a parallel logical architecture.

## 12. Remaining uncertainties

- real LLM planner fidelity, clause accounting and paraphrase stability;
- whether generic Call contracts yield comprehensible static errors at scale;
- integrated budget/provenance/type enforcement in the prototype DAG;
- production-grade join planning across multiple sources and dialects;
- interaction conventions for PVM/rate-mix and appearing segments;
- statistical contracts for changepoints, uncertainty and robust diagnostics;
- access control, privacy composition and policy authority;
- causal model registry and identification review process;
- external result storage, multi-source lineage and correction-vintage policy;
- performance, caching, cost planning and real-data onboarding burden.

That discriminator is now complete. The next implementation increment is
contract-only shadow mode: introduce C4 contracts and executable registry types
in production, compile existing level/delta Query Specs to non-executing shadow
plans, and require parity before routing any request through the new executor.
