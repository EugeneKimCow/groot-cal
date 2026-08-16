# Evidence-gated production refactoring plan

The E-011 decision permits staged refactoring, not a rewrite.

## Increment 1 — Introduce contracts in shadow mode (complete 2026-08-16)

- Add canonical `Plan`, `Call`, `Ref`, `Slice`, operator port, and normalized
  Result Envelope contracts under the production package.
- Make the operator registry executable for type checks and cross-input named
  validators.
- Do not change `engine.run_question` routing.
- Compile fixed existing Query Specs into plans and compare them in tests only.

Exit gate: no production output changes; all existing regressions plus plan
serialization/type-error tests pass.

Implemented as isolated `analytical_ir`, `shadow_registry`, and `shadow_plan`
modules. No current engine, pipeline, kernel, runtime, or reporter imports the
new path. Level and period-delta Query Specs compile to validated shadow plans;
plan comparison fails closed. Structured unknown clauses fail the binding
ledger instead of disappearing. The period-delta plan is explicitly marked as
only the comparison root of `explain_change`, not a completed explanation.

Exit evidence: 18 new contract/shadow tests; 102 production tests discovered
(101 pass, one environment skip); golden 17/17; semantic 10/10; research 40/40.

## Increment 2 — Normalize metric evaluation (complete 2026-08-16)

- Introduce aggregation-algebra-driven metric evaluation for sum,
  ratio-of-sums, distinct, and period-end balance.
- Adapt current commerce and typed results to one normalized carrier.
- Enforce duplicate binding and label-ceiling contracts discovered during
  inventory.

Exit gate: parity on all five current metrics and reporter tests without field
shape probing.

E-013 phase A added a shadow-only aggregation strategy registry and one
`MetricScalar` carrier. Sum, ratio-of-sums, entity cardinality, and period-end
sum match the five catalog metrics; amount and count share the sum strategy.
Duplicate bindings now fail in the candidate route, and type/rule contradictions
are rejected by declarative strategy admissibility rather than arithmetic
branches. Exact level value/scope/unit/provenance parity passed.

E-014 added one central read-only adapter for scalar values, total changes,
segments, operator/provenance references, and evidence ceilings. Reporter, CLI,
and materialization now consume that normalized view while current public
payloads and routing remain unchanged. Reporter labels derive from the declared
ceiling, and lint rule `LBL02` independently rejects label promotion beyond it.
The live typed kernel now rejects duplicate rate bindings as well as the shadow
candidate.

Exit evidence: 133 production tests discovered (132 pass, one environment
skip); golden 17/17; semantic 10/10; research 40/40. Remaining deletion debt is
confined to the adapter's interpretation of legacy Korean-keyed ceiling maps.

## Increment 3 — Intent compiler fidelity gate (complete 2026-08-16)

This increment is mandatory before expanding shadow execution or routing any
capability. Detailed experiment design is in `intent_compiler_plan.md`.

### E-015 — Select the minimum typed intent contract (complete 2026-08-16)

- Compare a Bound Intent Spec with direct C4 Plan compilation plus a typed
  source-clause binding record.
- Preserve subjects, reducer, comparison/time, filters, requested breakdown,
  ranking/limit, multi-metric intent, nested requests, and output restrictions.
- Require source spans and an explicit state for every material clause.
- Reject any representation that duplicates Analytical IR or operator
  contracts without improving fidelity or validation.

Twelve shared cases produced seven byte-identical successful C4 Plans and five
identical refusal/clarification outcomes. The Bound Intent Spec added one
serialized contract, 2,646 intermediate bytes, 34 duplicated binding values,
and a new cross-representation consistency state without improving fidelity or
error locality. E-015 therefore selected direct C4 Plan compilation plus the
typed source-clause binding record. The rejected representation is revisitable
only with an independently consumed intent-object counterexample.

### E-016 — Implement the selected compiler in shadow mode (complete 2026-08-16)

- Bind only to registered semantic and analytical vocabulary.
- Compile to explicit root Calls; derive or audit `operation_family` rather than
  dispatching on it.
- Return `clarify` for ambiguity and `out_of_domain` for unsupported meaning.
- Never substitute a neighboring supported operation for an unsupported one.
- Measure paraphrase normalization and silent-substitution failures on the
  governed corpus.

Exit gate: every material clause is consumed or preserved for successful Plans;
zero silent substitutions in the adversarial intent corpus; the existing
change paraphrases normalize 5/5; all current regression gates remain green.

Implemented as isolated `clause_binding` and `shadow_intent` modules plus one
versioned wire schema. The governed Korean adapter proposes clauses, while the
deterministic contract validates exact spans, closed tagged role/value shapes,
registered references, and concrete Plan-consumer links. Four of nine required
adversarial questions compile without loss; five fail closed with clause-local
reasons. The five change paraphrases normalize 5/5 to `explain_change`.
`operation_family` is derived from emitted Calls. No current engine import or
routing changed.

Exit evidence: 16 new E-016 tests; 149 product tests discovered (148 pass, one
environment skip); golden 17/17; semantic 10/10; research 58/58.

## Increment 4 — Shadow-plan existing analytical paths (complete 2026-08-16)

- Compile level, prior-period change, plan comparison, and current drilldown
  behavior to explicit Calls.
- Run current imperative and shadow DAG paths on the golden corpus; compare
  numeric results, failures, budgets, provenance, and selected outputs.
- Keep domain event/VRM behavior as explicit provisional Calls, not automatic
  hidden pipeline branches.

Exit gate: full golden and semantic parity with zero silent dropped clauses in
the new plan contract.

E-017 added an isolated C4 executor and established representative parity for
all five metric level algebras; sales, operating-profit, inventory, and distinct
change; rate-change refusal; plan comparison; ranking; and explicit drilldown.
The shadow enforced semantic corpus is 10/10. Distinct change uses provisional
`set_transition@v1`, not additive contribution. A tie-order counterexample was
fixed by preserving registered dimension order. The current engine route and
public payloads remain unchanged.

Exit evidence: 15 E-017 tests; 164 product tests discovered (163 pass, one
environment skip); current-route golden 17/17; semantic 10/10; research 58/58.
Drilldown's dynamic child acquisition remains a pre-routing design debt for that
capability, but does not block metric-level controlled routing.

## Increment 5 — Route one capability at a time

1. Metric level (complete 2026-08-16, E-018)
2. Period delta
3. Additive contribution
4. Explicit nested drilldown
5. Plan comparison
6. Non-additive registered operators

Use reversible feature selection during migration. Do not remove the old path
until each capability's golden, adversarial, reporter, and provenance tests
pass through the new executor.

E-018 added the `route` selector to `engine.run_question` (default preserves
the current route) and `slice/c4_route.py` as the single public-boundary
adapter. Metric level passes value/unit/label, failure-location, reporting,
materialization, and provenance parity on both selectors; non-level plans are
refused explicitly, with fallback only by caller choice. The H2 enforced corpus
is now part of every routing exit gate (10/10 routed parity). One
public-boundary counterexample was found and fixed: the commerce domain pack's
unchecked assumption ledger must be preserved by every route.

## Increment 6 — Remove historical architecture

Only after full parity:

- remove `execution_profile` dispatch;
- merge commerce and typed pipelines/kernels;
- remove hardcoded all-axis/dominant-axis/VRM/event orchestration;
- retain normalized intent family only as audit/fidelity metadata;
- generate optional typed builders from the registry rather than maintaining a
  parallel explicit-node IR.

## Current implementation target

Increments 3 and 4 are complete. E-016 passed governed intent fidelity and E-017
passed representative execution parity without changing production routing.
Increment 5 is active, beginning with a reversible metric-level route only.
Contribution, set transition, plan comparison, and drilldown remain shadow.
