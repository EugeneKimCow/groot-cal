# Current best architecture

Status: converged research candidate with the E-016 governed shadow intent gate;
not yet a production execution-route approval.

The current leader is the compressed IR-centric candidate C4:

```text
Question
  -> Agent/compiler harness
  -> bound intent + semantic references
  -> typed analytical DAG
       -> logical data requirements
       -> backend-neutral data planner -> SQL adapter -> RDBMS
       -> canonical deterministic operators
       -> registered validation/invariants
  -> evidence results
  -> result-only renderer/reporter
```

Three primary logical contracts:

1. Semantic contract: metric expressions, grain, unit, time behavior,
   dimensions/entities/relationships and cardinality, calendars/cohorts,
   null/allocation policies, bindings, versions.
2. Analytical contract: typed operator input/output, parameters, invariants,
   failure variants, evidence/label ceiling.
3. Planning contract: bound inputs, typed nodes/edges, conditions, budgets, and
   selected outputs.

Domain packs provide aliases, domain semantic instances, and plan idioms. They
do not provide a second runtime. Data backends, semantic authorities, result
stores, and report renderers are replaceable ports around the three contracts.

Why it currently leads: it directly exposes the contract absent from the
repository while retaining the strongest existing assets. Why it may lose: an
explicit IR could grow into a general workflow language; typed metric
expressions could duplicate operators; semantic-heavy registration may prove
simpler for governed BI; conditional diagnosis may require more than a compact
DAG.

No production execution-route migration is approved by this record. E-012 only
approved isolated contracts and shadow compilation.

E-003 supports one `evaluate_metric` node driven by aggregation algebra for the
five current metrics, but only for a bound single period. E-004 supports generic
Call+Ref composition for requested breakdown and nested drilldown while reusing
the existing contribution operator. The first held-out corpus expanded the
semantic and validation contract but did not require a second IR node kind.

The minimum current grammar hypothesis is:

```text
Plan(version, calls, outputs, limits)
Call(id, operator_ref, inputs, parameters, optional typed guard)
Input = literal | semantic_ref | result_ref | Slice
Slice = time/calendar/cohort + predicates + grain expectation
```

This remains vulnerable to rate/mix, set transition, distribution, SQL fanout,
time alignment, and causal-boundary experiments.

E-005 changed the operator model but not the grammar. Rate/mix needs a
domain-independent registered contract with an explicit allocation convention;
entity transition needs set identities and optional functional-dimension
migration. Neither should become a domain-specific runtime or an IR node class.

E-006 supports a separate logical Data Requirement compiler boundary. Semantic
contracts expose source grain and relationship cardinality; analytical calls
expose required values/slices/groups; the compiler chooses acquisition shape;
backend adapters emit SQL. Explicit allocation is an estimand parameter, while
fanout and reconciliation are deterministic checks.

E-007 keeps time inside the same grammar: a Slice references a registered
calendar/window/cohort and declares the requested reducer, while semantic/data
contracts state available grain. Alignment is checked during compilation. A
period-end balance cannot silently answer an average-daily-balance question.

E-011 resolves the remaining C3/C4 implementation question for the tested
slice. C4 is canonical at the wire/runtime boundary. C3's explicit node classes
are useful only as generated authoring builders that lower immediately to C4;
they are not a parallel logical architecture.

E-012 introduced that canonical value contract, an executable shadow registry,
and a Query Spec shadow compiler without changing routing. This validates the
migration seam, not execution parity. The binding ledger catches structured
clauses that no Call consumes, but cannot see language intent discarded before
Query Spec creation. The next production discriminator is a normalized,
aggregation-algebra-driven metric evaluator across all five current metric
types.

E-013 passed that scalar discriminator in shadow mode. Four aggregation
strategies cover five nominal types, with amount and count sharing sum. Metric
type remains a declarative admissibility constraint; aggregation rule selects
the arithmetic. The candidate now rejects duplicate bindings that the legacy
rate path accepts. Routing is still gated because reporter/result adaptation,
live binding enforcement, and period-end behavior over finer-grain sources are
not complete.

The migration sequence now includes an explicit intent compiler gate before
shadow analytical-path expansion or routing. E-015 compared a separate Bound
Intent Spec with direct C4 Plan compilation plus a typed clause-binding record;
E-016 implemented the selected contract in shadow mode. Successful Plans must
account for every material language clause, and unsupported intent must clarify
or fail closed rather than substitute a neighboring analysis.

E-014 completed the result-consumption half of Increment 2. One deletion-bound,
read-only adapter now normalizes legacy scalar/change fields, segments,
provenance, operator identity, and evidence ceilings for reporter, CLI, and
materialization. Public payloads and analytical routing did not change. Report
labels now derive from result capabilities and lint rejects escalation beyond
them; the live typed operator also enforces duplicate-binding uniqueness. The
remaining compatibility logic is isolated to the adapter and is not part of
the target architecture. Increment 3 is complete; Increment 4 / E-017 is active.

E-015 selected the minimum intent boundary for that increment. A closed,
versioned source-clause binding record compiles directly to C4; there is no
separate Bound Intent Spec. On twelve shared cases the extra spec produced no
fidelity or error-locality gain but duplicated 34 values and introduced a new
consistency boundary. The binding record is not free-form metadata: it retains
source spans, materiality, explicit outcome states, role-validated values, and
Plan consumer links. E-016 has now proven this boundary on the governed Korean
corpus; routing remains unchanged and blocked pending E-017 execution parity.

E-016 implemented and passed that boundary on the governed Korean corpus. All
nine required adversarial questions are accounted for as four lossless Plans or
five clause-local safe refusals, and the existing change paraphrases normalize
5/5. Exact spans, tagged role/value validation, registered references, Plan
consumer links, and deterministic hashes are enforced outside the proposal
adapter. `operation_family` is derived from emitted Calls. This closes the
governed intent-fidelity gate but does not establish broad parser recall by
itself. E-017 has since completed; E-018 controlled metric-level routing is the
active discriminator.

E-017 added an isolated C4 executor and established parity across all five metric
level algebras plus representative change, plan, rank, and explicit drilldown
paths. A tie-order counterexample now preserves registered dimension order.
Distinct change uses provisional `set_transition@v1` so entrants, exits, and
migrations are not collapsed into additive arithmetic. The enforced semantic
shadow corpus is 10/10. This supports E-018 controlled metric-level routing, but
other capabilities remain shadow; drilldown still has unresolved dynamic data-
requirement transparency.

E-018 completed controlled metric-level routing. `engine.run_question` now has a
reversible route selector whose default preserves the current route; `c4_level`
executes only metric level through the C4 compiler/executor, refuses every other
family explicitly, and exposes canonical Result Envelope payloads at the public
bundle boundary with declared — never legacy-spelled — operator identity. Parity
held for values, units, labels, failure locations, reporting, materialization,
and provenance; the H2 enforced corpus is 10/10 on the routed selector and is
now a standing exit gate for every subsequent capability. The one counterexample
was at the public boundary, as predicted: dropped domain-pack assumption ledger
entries silently weakened declared uncertainty, and are now preserved by every
route. Period delta plus additive contribution routing (E-019) is the active
discriminator.
