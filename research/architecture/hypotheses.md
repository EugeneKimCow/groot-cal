# Architectural hypotheses

Hypotheses are retained even when rejected.

## H-001 — Explicit operator DAG is the missing central contract

### Hypothesis

Query Spec v1 should be split into a small bound-query header and an explicit
typed analytical DAG. The current `operation_family` alone is too coarse to
represent ranking, breakdown selection, composition, or conditional analysis.

### Consequences

- Commerce and typed pipelines can consume the same plan.
- Dominant-axis drilldown becomes data in the DAG rather than Python control
  flow.
- Planning can be tested without data access; execution can be tested without
  natural language.

### Counterexamples sought

- Queries whose next operator depends on arbitrary semantic judgment rather
  than typed result predicates.
- Plans for which an explicit DAG is more complex than the current family.

### Status

Active, initially supported by missing breakdown/ranking fields and duplicated
pipeline routing. Requires corpus and executable experiment.

## H-002 — Operation family is derivable and can be removed from core IR

### Hypothesis

`inspect_level`, `explain_change`, and `compare_plan` are planner-facing idiom
labels. Once a plan contains explicit nodes, admissibility should be determined
from node input/output types, not an independent family enum.

### Counter-hypothesis

The family is a valuable user-intent invariant that prevents individually
valid operators from forming a plan that does not answer the question.

### Status

Unresolved. Test by compiling the corpus both with and without family and count
rules needed to preserve intent.

## H-003 — Metric capabilities beat closed metric-type dispatch

### Hypothesis

Operator admissibility should depend on structural capabilities such as
`aggregate=sum`, `numerator/denominator`, `entity_key`, `time_reduce=last`, and
partition constraints. The five-value metric type enum can remain descriptive
but need not dispatch execution.

### Counterexamples sought

- Two metrics with identical declared capabilities but legitimately different
  execution semantics.
- Capability combinations that permit nonsensical operations unless a nominal
  type is also checked.

### Status

Active. The current typed kernel demonstrates both the value of capabilities
and continued nominal-type branches.

## H-004 — Domain packs contain vocabulary and plan templates, not operators

### Hypothesis

Commerce VRM, inventory flow analysis, and SCM service diagnosis should compile
domain language and semantic relationships into canonical operator DAGs. A
domain pack should not introduce a parallel runtime.

### Counterexamples sought

- A domain operation with a genuinely novel estimand that cannot be expressed
  by existing operators or a registered new canonical operator.

### Status

Active. `commerce_extensions` is a current counter-design, not proof that the
separate runtime is necessary.

## H-005 — Diagnosis is not a persistent core layer

### Hypothesis

Diagnosis is a conditional plan template: compare, decompose, rank, measure
concentration, then conditionally drill or request evidence. Results and plan
provenance are persistent; “Diagnosis” is not a separate semantic authority.

### Counterexamples sought

- Reusable diagnostic state that cannot be represented as plan, result, or
  domain idiom.
- Cross-run learning that requires a stable diagnosis object.

### Status

Active but untested on nested diagnosis and counterfactual cases.

## H-006 — Data acquisition is compiled from requirements, not embedded SQL

### Hypothesis

Analytical nodes declare logical data requirements (metric expressions, grain,
dimensions, filters, time windows). A separate data planner lowers them to SQL
or another backend. SQL is not part of the core Analytical IR.

### Status

Supported by E-006 for additive and ratio-of-sums queries. A logical requirement
was lowered to SQLite while preserving source grain, cardinality, explicit
allocation, and aggregation algebra. Multi-source time/grain alignment remains
unresolved.

## H-007 — One generic aggregate primitive can replace level variants

### Hypothesis

`metric_level`, `rate_level`, and `distinct_level` can compile to one typed
aggregate node whose aggregation expression is supplied by the semantic
contract and checked by the runtime.

### Counter-hypothesis

Different estimands and invariants are clearer and safer as distinct canonical
operators even if their orchestration is shared.

### Status

High-priority falsification target. It is the clearest simplification
opportunity and the clearest risk of over-generalization.

## H-008 — Plan validation must check intent fidelity

### Hypothesis

Schema validity and operator admissibility are insufficient. The compiler must
emit a binding ledger that accounts for material question clauses—metric
modifiers, time scope, requested breakdown, rank/limit, comparison, and output
constraints—and reject or clarify unconsumed clauses.

### Counter-hypothesis

Typed plan equivalence alone may make a separate clause ledger redundant if
the interpreter is fully constrained and tested across paraphrases.

### Status

Strongly supported by executable silent-loss probes; implementation form is
unresolved.

## H-009 — Primitive status follows estimand and invariant, not code size

### Hypothesis

Rate/mix decomposition and entity transition deserve registered analytical
contracts because ordinary deltas erase their estimands and each has distinct
closure laws. They do not justify new IR node kinds or domain engines: both are
invoked as ordinary typed Calls.

### Evidence

E-005 pure-mix and zero-total-transition fixtures. Current rate change refuses;
current distinct regional deltas all equal zero while churn/migration is large.

### Status

Provisionally supported. Interaction conventions, segment appearance/disappearance,
and non-functional assignments remain counterexamples to test.
