# Architecture research journal

## Iteration 0 — Observation and durable state

Date: 2026-08-16

### Hypothesis

The repository's strongest contracts—typed semantics, sum-type results,
runtime enforcement, provenance, and reporting boundaries—can survive while
the profile-specific imperative pipelines are replaced eventually by an
explicit analytical plan. This is a hypothesis, not a refactoring decision.

### Architecture change

None to production code. Durable research files and a shared query corpus were
introduced under `research/architecture/`.

### Why

The current Query Spec records metric/scope/time/family but does not record the
operators, breakdowns, ranking, conditional choices, or data requirements that
actually determine execution.

### Query coverage

Existing regression remains 17/17 golden and 10/10 enforced. Broader 40-query
architecture coverage awaits E-002.

### New counterexamples

Requested breakdown ambiguity, offsetting near-zero totals, rate change,
distinct migration, multi-metric derived analysis, hierarchy, conditional
nested diagnosis, and counterfactual identification.

### Concepts added

Research-only candidate concepts: typed analytical DAG and logical data
requirement. Neither has entered production architecture.

### Concepts removed

None. H-002 and H-007 explicitly target removals in later experiments.

### Special cases added/removed

None.

### Regression

84 discovered, 83 pass, one environment skip; golden 17/17; semantic 10/10.

### Qualitative assessment

The current system is safer and more evidence-disciplined than its planning
grammar suggests, but its generality is limited by duplicated orchestration and
fixture-backed execution. The first plausible IR-centric answer has not been
accepted; it must beat all candidates on the same corpus and survive red-team
queries.

### Next hypothesis

Test whether explicit node composition materially improves corpus coverage
without increasing concept count beyond semantic-heavy and operator-centric
alternatives.

## Iteration 1 — Intent fidelity and aggregate simplification

### Hypothesis

Current failures are dominated by missing plan fidelity, while nominal level
operator variants may collapse to aggregation algebra.

### Architecture change

Production unchanged. Added executable characterization and isolated aggregate
prototype.

### Evidence

Five silent substitutions/losses reproduced; two unsupported cases refused
safely. One evaluate node reproduced five metric-level fixtures without reading
nominal metric type and rejected duplicate bindings/unknown algebra.

### Revision

H-007 is supported only for single-period metric evaluation. Time-window
reducers, derived expressions, and decomposition laws remain open.

## Iteration 2 — DAG composition and held-out red team

### Hypothesis

Requested/nested diagnosis needs result edges and deterministic selectors, not
a diagnosis layer or new decomposition primitive.

### Evidence

Generic Call+Ref execution reused the existing contribution kernel for an
explicit offline-region breakdown and region→category nested drill. Forward
references were rejected.

The initial architecture comparison was rejected for open-world denylist
scoring. Closed-world held-out Q041–Q050 reduced C3/C4 from 100% to 80% and
forced relationship, calendar, cohort, alignment, null/allocation, scenario,
and replay contracts into the candidate. Mapping those requirements required no
new IR node form, so the Call+Ref grammar survived while “thin semantic layer”
was narrowed to mean workflow-thin, not data-anemic.

### Regression

Research 11/11; production 83 pass + 1 environment skip; golden 17/17;
enforced 10/10.

### Next hypothesis

Rate/mix and entity transitions have distinct estimands that may justify new
canonical operators, while their orchestration should remain ordinary DAG
composition.

## Iteration 3 — Non-additive estimands

### Hypothesis

New primitives are justified only when existing composition loses an estimand
or cannot state its invariant; primitive status must not imply a new IR node
kind.

### Counterexamples and experiment

A pure portfolio-mix shift changed total loss ratio by -0.2 with every segment
rate fixed. A symmetric rate/mix contract assigned 0.0 to within-rate and -0.2
to mix and closed its identity. A distinct fixture kept total and regional
counts unchanged while containing two entrants, two exits, and one migration;
current period delta hid all transitions.

### Revised hypothesis

Rate/mix and entity transition are legitimate domain-independent analytical
contracts. They remain ordinary Calls. Domain packs bind loss-ratio/customer
language and preferred idioms but do not implement either computation.

### Regression

Research 13/13; production 83 pass + 1 environment skip.

### Next hypothesis

Logical data requirements can preserve grain/cardinality/aggregation algebra
through SQL lowering without placing SQL or joins in Analytical IR.

## Iteration 4 — Data requirements and SQL boundary

### Hypothesis

Logical data requirements can make fanout errors rejectable while keeping SQL
out of Analytical IR.

### Counterexample and experiment

A many-to-many tag join inflated additive sales from 160 to 260. The prototype
refused missing allocation before SQL; explicit equal split reconciled grouped
sales and preserved ratio-of-sums numerator/denominator under SQLite lowering.

### Revised hypothesis

Source grain and relationship cardinality are semantic/data contracts;
allocation is an explicit estimand policy; fanout is a data-planner check;
aggregation algebra is compiled intact. Data Requirement is compiler output,
not planner-authored SQL or a fourth primary architecture contract.

### Regression

Research 17/17. Production code unchanged.

### Next hypothesis

Calendar/grain alignment can be typed compiler behavior over Slice and semantic
references rather than a time-specific operator hierarchy.

## Iteration 5 — Temporal estimands and alignment

### Hypothesis

Calendar/grain alignment is typed compiler behavior over Slice and semantic
references rather than a time-specific operator hierarchy.

### Evidence

Period-end and daily-average inventory diverged on the same series. Missing
daily grain was refused. Complete daily actual rolled to a registered weekly
window and compared with plan; incomplete actual suspended. A named fiscal
period resolved to the generic window representation.

### Revision

Time reducer belongs to the bound metric evaluation; observation grain belongs
to semantic/data authority; calendar/cohort belongs to Slice; alignment checks
belong to compilation. The Call+Ref grammar did not change.

### Regression

Research 22/22. Production code unchanged.

### Next hypothesis

A second unseen query wave will primarily expand semantic/check policies, not
the analytical grammar. A new core node kind would materially weaken the
current convergence claim.

## Iteration 6 — Second held-out wave

### Result

Ten unseen questions reduced C3/C4 structural coverage from 100% to 83.3%.
Every miss mapped to a field/reference, analytical Call, compiler/data check,
or evidence policy inside the existing three contracts and adjacent ports.
After explicit revision the ceiling is 60/60. No new IR node form was added.

### Skeptical qualification

The candidate was again revised after seeing failures. Stability is supported
only by the kind of change required—contract detail rather than grammar—not by
the restored percentage. New capabilities are not implementation claims.

### Next hypothesis

Valid-time truth, privacy suppression, and multi-source freshness can remain
constraints on semantic binding/data acquisition/result consumption rather
than becoming a fourth primary logical contract.

## Iteration 7 — Governance boundary and final adversarial phase

Valid-time joining preserved historical truth, suppression preserved a hidden
residual, and multi-source freshness refused scalar freshness when one source
was stale or unknown. These were constraints on existing boundaries, not a new
primary contract.

Typed guards made conditional plans replayable. Current paraphrase planning was
only 4/5 stable, leaving intent fidelity as an explicit compiler responsibility.
Deterministic scenario reweighting stayed noncausal; causal counterfactual
suspended without identification; quantile change violated the additive
identity. No case required a new IR node form.

Research reached 31/31 tests. Across the last three cycles, material changes
were additions to semantic/operator/check detail, while the three-contract and
Call+Ref grammar remained unchanged. This is the convergence signal required
for a completion audit, not proof that the architecture is universally final.

## Iteration 8 — Integrated C3/C4 discriminator

### Hypothesis

Explicit C3 node classes might justify their larger taxonomy through better
type errors or materially clearer execution contracts.

### Experiment

Five representative plans shared semantic and operator registries, SQL
lowering, normalized results, budget, provenance, and runtime. C3 nodes lowered
to C4 Calls. Valid results and invalid reference/dimension errors were compared.

### Result

Execution and errors were identical. C3 was shorter to author but introduced
six classes and six lowering cases; its runtime serialization became identical
to C4. The hypothesis that C3 should be a separate core IR is rejected.

### Simplification

Keep C4 as the only canonical wire/runtime IR. Generate typed C3-style builders
from the registry when SDK ergonomics justify them. This retains one source of
truth and removes the last competing logical architecture.

### Next action

Begin production refactoring only with contract definitions and shadow-plan
parity. Do not replace routing or delete current paths in the first increment.

## Iteration 9 — Production contracts in shadow mode

### Hypothesis

C4 contracts and executable port validation can enter production code as a
zero-routing-change scaffold, while a binding ledger can make structured clause
loss fail closed.

### Experiment

Added isolated production modules for Plan/Call/Ref/Slice, a tagged Result
Envelope, executable shadow operator contracts, and Query Spec shadow
compilation. Tested level, rate level, scoped level, calendar boundary, period
delta, deterministic hashes, plan-comparison refusal, malformed references,
cross-metric delta, malformed slices, and unknown intent clauses.

### Result

All 18 new tests pass. Current engine outputs remain unchanged. The complete
gate remains green: 101 production tests pass with one Seatbelt skip, golden
17/17, semantic 10/10, and research 40/40.

### Skeptical qualification

The ledger audits the Query Spec/compiler boundary, not the natural-language
interpreter boundary. It caught injected `rank` and `intent.breakdown` fields,
but the current interpreter still never emits those fields for real ranking or
breakdown requests. The period-delta shadow plan is consequently labeled a
partial comparison root, not a complete `explain_change` answer.

### Next hypothesis

One aggregation-algebra-driven evaluator can normalize all five current metric
types without branching outside registered metric strategy and without forcing
the reporter to probe incompatible field names.

## Iteration 10 — Normalized metric scalar evaluation

### Hypothesis

The four observed aggregation algebras, not metric IDs or separate level
operators, are sufficient for all five current metric types and count.

### Experiment

Added a shadow evaluator with registered sum, ratio-of-sums, period-end sum, and
entity-cardinality strategies. Compared five catalog metrics, scoped sales, and
a count fixture with current kernels. Attacked duplicate bindings, negative
rate inputs, zero denominators, null distinct IDs, inconsistent balance
semantics, unknown algebra/scope, missing data, and duplicate predicates.

### Result

All normal values, scopes, units, and provenance match. Amount and count reuse
one sum implementation. The new carrier removes value-field variation and
provides one evidence ceiling. The candidate closes duplicate binding, while
the live rate path demonstrably still accepts it.

### Revision

Pure rule dispatch initially accepted the contradictory descriptor
`type=balance, rule=sum`. The corrected model keeps arithmetic selected by rule
but makes each strategy declare compatible nominal types. This is an
admissibility check, not a per-type arithmetic branch.

### Regression and remaining gate

Fifteen E-013 tests pass. The full suite is 116 pass plus one environment skip;
golden 17/17, semantic 10/10, research 40/40. Increment 2 remains open because
reporter consumption and live payloads are not normalized.

## Iteration 11 — Migration sequence correction for intent fidelity

### Observation

The refactoring sequence placed shadow analytical-path expansion immediately
after result normalization even though the current Query Spec had already been
shown to erase reducer, breakdown, ranking, year, and analytical-objective
clauses. A typed executor could therefore make substituted intent more
reproducible without making it correct.

### Revision

Added a mandatory intent compiler increment before shadow-path expansion and
routing. E-015 compares a Bound Intent Spec with direct Plan plus a typed source
binding record; E-016 implements the winner in shadow mode. The contract must
account for every material clause and fail closed on unsupported meaning.

### Gate

No production capability may route through the new DAG until both intent
fidelity and execution parity pass. Immediate work remains E-014 result-boundary
normalization, followed by E-015 and E-016.

## Iteration 12 — Normalized result consumption boundary

### Hypothesis

One read-only compatibility boundary can remove legacy result-shape knowledge
from all downstream consumers without changing public payloads or analytical
routing.

### Experiment and result

Added a central adapter for scalar/change values, segments, source/operator/
provenance refs, and evidence ceilings. Reporter, CLI, and materialization now
consume the normalized view. Source payloads remain unchanged and
materialization preserves their identity. Ambiguous or malformed successful
results fail closed. Reporter labels derive from declared capabilities, and
lint rule `LBL02` independently prevents escalation beyond them.

### Contract correction

The live typed kernel now enforces `field_binding_unique`, closing the duplicate
rate-binding drift documented in E-013. The only remaining legacy interpretation
is the adapter's deletion-bound conversion of Korean-keyed label maps.

### Regression and next hypothesis

Production discovery is 133 tests: 132 pass and one environment skip. Golden is
17/17, semantic 10/10, and research 40/40. Increment 2 is complete. E-015 now
compares the two minimum typed intent contracts before any intent compiler or
routing implementation is selected.

## Iteration 13 — Intent contract discriminator

### Competing hypotheses

A serialized Bound Intent Spec might give the compiler a clearer stable target
before C4. The smaller alternative is one typed clause-binding record compiled
directly to C4, avoiding a second representation of the same analytical intent.

### Minimal experiment

Implemented both over one closed, versioned record and one shared emitter.
Twelve annotated cases covered subject, reducer, explicit comparison/time,
filter, breakdown, rank/limit, multi-metric intent, nested diagnosis, output
restriction, ambiguity, and every required silent-substitution counterexample.

### Red-team revision

The initial emitter could accept multiple analytical-objective bindings and use
the first. Typed structures alone did not prevent intent loss. The common
validator now rejects multiple singleton objectives unless an explicit
registered composition consumes all of them.

### Result and decision

Both candidates produced seven byte-identical successful C4 Plans and five
identical refusal/clarification outcomes. Bound Intent added 2,646 intermediate
bytes, 34 duplicated values, one contract type, and an inconsistent record/spec
state without improving error locality. Direct C4 Plan plus the typed binding
record wins E-015. No production route changed.

### Next hypothesis

E-016 must show that the selected contract can bind real governed Korean
questions with zero silent substitution. The likely failure mode is incomplete
clause inventory, not Plan emission; a deterministic validator must remain the
authority even if a proposal adapter later uses an LLM.

## Iteration 14 — Governed shadow intent compiler

### Hypothesis

The E-015 direct C4 boundary can preserve real governed Korean clauses with one
typed source record, provided proposal and deterministic authority remain
separate.

### Minimal implementation

Added a versioned source-clause record and wire schema, closed tagged role/value
validation, a conservative Korean proposal adapter, direct C4 emission, and the
shadow operator contracts needed by contribution, rank, metric alignment, and
drilldown Plans. Every successful material clause links to a concrete Call or
Plan consumer. `operation_family` is derived from Calls.

### Counterexample result

The nine required attacks produced four supported Plans and five safe refusals,
with no neighboring-analysis fallback. Filter plus region breakdown,
rank/limit/only, explicit 2025 time, and multi-metric divergence survive.
Average inventory is refused against the monthly point-in-time source; inventory
turnover, acceleration, outlier sensitivity, and cross-axis concentration remain
explicitly unsupported. Unknown analytical language also fails closed.

### Stability and regression

The five existing change paraphrases normalize 5/5 to `explain_change`.
Malformed spans, unregistered refs, multiple singleton objectives, deterministic
serialization, and unchanged engine output are tested. Product discovery is 149
tests: 148 pass and one environment skip. Golden is 17/17, semantic 10/10, and
research 58/58. Routing changes remain zero.

### Skeptical qualification and next hypothesis

This proves governed-corpus fidelity, not broad Korean parsing recall. The rule
adapter is replaceable; the deterministic binding validator is not. E-017 must
now discriminate whether executable C4 Calls can match current level, change,
plan, and drilldown behavior without restoring hidden orchestration.

## Iteration 15 — Executable C4 parity

### Hypothesis

The normalized metric evaluator plus registered C4 Calls can reproduce existing
analytical behavior without operation-family dispatch or production routing.

### Experiment

Added an isolated shadow executor for evaluation, delta, contribution, rank,
metric alignment, plan gap, set transition, and provisional drilldown. Compared
all five level algebras; additive sales/profit/balance change; distinct change;
rate refusal; plan gap; Top-N; explicit drilldown; budgets; failures;
provenance; and the ten-case semantic corpus.

### Counterexamples and revision

Equal-magnitude category changes were initially reordered by label, changing
Top-N membership. Registered dimension order is now the deterministic tie-break.
Distinct change also falsified ordinary additive contribution, so a provisional
set-transition contract now carries entrants, exits, and migrations. A
product-to-region drilldown correctly fails because region is offline-only.

### Result

Representative numeric/segment parity passed, including semantic 10/10. E-017
has 15 tests. Full product discovery is 164: 163 pass and one environment skip;
current golden 17/17 and research 58/58. Routing remains unchanged.

### Qualification and next hypothesis

The provisional drilldown operator hides dynamic child evaluations; this is a
data-requirement transparency debt, not approval to route it. E-018 should route
metric level only behind an explicit selector and test the public bundle,
reporting, materialization, provenance, and failure boundary.

## Iteration 9 — E-018 controlled metric-level routing

### Hypothesis

Metric level can route through the C4 compiler/executor behind a reversible
selector with full public-boundary parity, and the real migration constraint
will be the bundle boundary rather than arithmetic.

### Experiment

Added a `route` selector to `engine.run_question` (default: current route) and
`slice/c4_route.py` as the single adapter from C4 execution to the public
bundle. Ran five level algebras, scoped level, missing month, bad scope,
duplicate binding, reporting, materialization, staleness, provenance, non-level
refusal/fallback, the H2 enforced corpus, and golden level cases through both
selectors.

### Counterexample and revision

Reporting parity failed first: the routed bundle dropped the commerce domain
pack's unchecked open-cohort assumption, silently weakening the report's
declared uncertainty. The assumption belongs to the domain pack, not the
execution path; both routes now share one `COMMERCE_ASSUMPTION_LEDGER`
constant. Arithmetic, unit, and label parity never failed — the predicted
boundary constraint, confirmed.

### Result

E-018 tests 14/14; product discovery 178 all passing in the standard sandbox;
current golden 17/17; enforced semantic 10/10 on both selectors; research
58/58. Non-level plans refuse explicitly; fallback exists only as a caller
choice. Plan hashes and materialized result IDs are deterministic, with
declared operator identity (`evaluate_metric@v1`).

### Qualification and next hypothesis

Golden's legacy field assertions (`value_u`) stay tied to the current route;
the C4 route holds the same facts under normalized names. Legacy interpret
still drops unconsumed year clauses on both routes — an intent-compiler concern
for the demo entry point. E-019 routes period delta plus additive contribution,
where per-axis result-key mapping and reporter dominance selection are the
discriminating risks.

## Iteration 10 — E-019 controlled period-change routing

### Hypothesis

Period change can route with parity for everything consumers depend on, while
the rejected hidden exploration strategy (auto-drilldown, VRM) stays out of the
routed boundary.

### Experiment

Extended the Query Spec compiler to per-axis contribution/set-transition DAGs,
registered the commerce event scan as an explicit Call, taught the adapter the
canonical Attribution view, and generalized the selector to c4/c4_or_current.
Compared sales three-axis change, scoped change, typed and distinct changes,
rate refusal, events, reports, and materialization across both selectors.

### Result

All parity gates passed: golden change expectations on canonical paths, 14
report claims byte-identical with clean lint, identical event evidence and
hypothesis budgets, deterministic materialization under declared
contribution@v1 identity. drill:*/vrm:* absence is pinned as a declared
difference. E-019 tests 11/11; product 189; golden 17/17; semantic 10/10;
research 58/58.

### Qualification and next hypothesis

Executor failure isolation (break vs per-branch) is indiscriminable on current
fixtures and recorded as unresolved #19; share-suppression and label-capability
ownership as #20–21. Routed capabilities now cover the demo scenario; the next
increment is the demo entry point (intent compiler → routed executor behind an
explicit CLI mode), not further capability routing.
