# Architecture decisions

## D-001 — Preserve the production slice during discovery

Status: accepted for research phase.

Reason: current regressions are valuable evidence, while the missing IR and SQL
contracts are not sufficiently understood to justify a refactor. Experiments
will live under `research/architecture/` until a candidate survives shared
corpus and adversarial comparison.

## D-002 — Use one shared query corpus for all candidates

Status: accepted.

Reason: comparing candidates on different examples would reward architecture-
specific anecdotes. Coverage claims must identify fully represented, refused,
and incorrectly accepted queries on the same corpus.

## D-003 — Treat current canonical labels as evidence, not immunity

Status: accepted.

Reason: existing documents canonized type-directed admissibility and bindings
for the pilot. The new governing specification explicitly requires attempting
to falsify current abstractions. Existing evidence raises the burden for a
change but does not forbid it.

## D-004 — No architecture winner yet

Status: active constraint.

Reason: inventory alone supports C3/C4 but has not tested semantic-heavy or
operator-centric candidates against the corpus.

## D-005 — SQL is not an Analytical IR primitive

Status: provisionally accepted after E-006.

The Analytical Plan references semantic metrics and slices. Compilation derives
logical Data Requirements; backend adapters lower those requirements to SQL or
another acquisition mechanism. Grain, relationship cardinality, allocation,
and aggregation expressions are logical contracts and cannot be delegated to
an unconstrained SQL generator.

This decision remains provisional until multi-source alignment and at least one
non-SQL lowering or equivalent mock are tested.

## D-006 — C4 is the research winner, not a migration approval

Status: accepted as the current best research architecture.

C4's three contracts and generic typed Call+Ref DAG retained 60-query
structural coverage through two held-out waves without adding an IR node form.
Executable prototypes covered aggregation algebra, references, guards,
non-additive estimands, SQL lowering, temporal alignment, valid time, privacy,
freshness, and causal refusal. C3 remains a viable implementation alternative
if explicit node classes materially improve type errors or developer clarity.

Production migration is a separate decision requiring an integrated vertical
slice and parity tests; this research did not authorize or perform it.

## D-007 — No separate Diagnosis Layer

Status: accepted for the logical architecture.

Observed diagnostic behavior was expressible as Calls, result references,
deterministic selectors, and typed guards. Domain packs may name reusable
diagnostic idioms, but diagnosis is not a semantic authority or runtime.

## D-008 — Operation family is audit metadata, not execution dispatch

Status: provisional.

Explicit root Calls determine execution. A normalized user-intent family may
remain useful for fidelity checking, policy, and explanation, but the current
comparison→family→hardcoded-pipeline dispatch should not define the runtime.

## D-009 — C4 canonical IR with generated typed builders

Status: accepted after E-011.

C4 and C3 had exact execution parity. C3 saved authoring bytes and can improve
IDE ergonomics, but added six node classes and six lowering dispatches and
compiled to the same C4 representation. Tested type errors were identical
because meaningful laws reside in the executable operator registry.

Therefore C4 is the only canonical serialized/runtime IR. Typed C3-style
builders are optional generated interfaces over registry contracts. Manually
maintaining both would duplicate the architecture.

## D-010 — Accept Increment 1 as a migration scaffold, not an execution route

Status: accepted after E-012.

The generic Plan/Call/Ref/Slice wire contract, executable shadow port registry,
strict result union, and binding ledger entered production code without any
import from the current engine or execution paths. Full regressions remained
green, and malformed refs, cross-metric delta, malformed slices, and structured
unconsumed clauses failed closed.

This decision does not approve routing traffic through the new plan. It also
does not claim intent fidelity: clauses lost by the current natural-language
interpreter never reach the ledger. Routing remains gated on normalized metric
evaluation and parity in later increments.

## D-011 — Aggregation rule selects math; metric type gates admissibility

Status: provisionally accepted after E-013.

Four registered strategies reproduced scalar levels for amount, rate, balance,
distinct, and count. Amount and count share `sum`; no domain metric ID or
per-type arithmetic branch is needed. Removing metric type entirely was too
weak, however: it allowed a contradictory balance-plus-sum descriptor. Each
strategy therefore declares compatible nominal types, while its aggregation
rule remains the dispatch key.

The normalized evaluator and `MetricScalar` carrier are accepted as the shadow
migration target. This is not live-route approval. Current kernels still have
different result fields, current reporting still probes them, and the legacy
rate path still violates the canonical duplicate-binding rule.

## D-012 — Intent fidelity is a mandatory pre-routing gate

Status: accepted as a sequencing constraint.

The current Query Spec cannot represent reducer, requested breakdown,
ranking/limit, multi-metric operations, or most analytical objectives. Moving
that lossy object into a typed DAG would preserve the wrong intent more
reliably, not solve the defect.

Before shadow analytical-path expansion and production routing, E-015 must
select the minimum typed intent/binding contract and E-016 must implement a
shadow compiler. Every material source clause must be linked to a Plan input,
Call, output, preserved constraint, clarification, or safe refusal. A successful
neighboring analysis is not an acceptable fallback for unsupported intent.

`operation_family` remains audit/fidelity metadata. Explicit root Calls define
execution. The intent contract must not become a parallel Analytical IR.

E-015 and E-016 have now satisfied this sequencing gate for the governed corpus.
Execution parity and production routing remain separate gates.

## D-013 — One deletion-bound result adapter owns legacy interpretation

Status: accepted after E-014.

Reporter, CLI, and materialization consume one normalized scalar/change,
segment, evidence, and label-capability view. Current producers and their
public payloads remain unchanged during migration. The adapter is the only
place allowed to interpret legacy field alternatives and Korean-keyed ceiling
maps; new producers must emit the strict Result Envelope and must not add new
adapter variants.

The live typed operator boundary now rejects duplicate field bindings with the
same `field_binding_unique` contract as the shadow evaluator. This closes the
known canonical-boundary drift without approving new analytical routing.

## D-014 — Compile typed clause bindings directly to C4

Status: accepted after E-015 for E-016 shadow implementation.

Use one closed, versioned source-clause binding record beside the canonical C4
Plan. Do not introduce a permanent Bound Intent Spec. On twelve shared cases the
extra spec produced the same seven successful Plans and five failure outcomes,
while adding 2,646 intermediate bytes, 34 duplicated values, and a new
record/spec consistency failure state.

“Direct” does not remove the intent boundary. The record must retain exact
spans, materiality, explicit outcome state, closed role/value validation, and
links to concrete Plan consumers. Ambiguity clarifies and unsupported meaning
fails closed. Multiple objectives must have registered composition or be
refused rather than ordered implicitly.

Reopen this decision only if a stable intent object acquires an independent
consumer that cannot use the binding record or C4 Plan without duplicating
analytical semantics.

## D-015 — Accept the governed shadow intent boundary

Status: accepted after E-016; production routing remains blocked.

Use the versioned source-clause binding record and direct C4 compiler as the
pre-routing fidelity boundary. The proposal adapter may change, including to an
LLM, but exact source spans, closed tagged role/value validation, registered
references, explicit outcome states, and concrete Plan-consumer links remain
deterministic requirements.

On the governed corpus the boundary accounts for all nine required adversarial
questions with four supported Plans, five safe refusals, and zero silent
substitution. The five existing change paraphrases normalize 5/5. Unknown
analytical text is unsupported, not discourse. `operation_family` is derived
from Calls and remains audit metadata.

This decision approves E-017 execution-parity work only. It does not approve
production routing or claim broad Korean parser coverage.

## D-016 — Permit controlled metric-level routing after E-017

Status: accepted for E-018; all other capabilities remain shadow.

The C4 executor matches the five metric level algebras and representative
change, plan, ranking, and drilldown paths while preserving normalized failures,
budgets, provenance, and evidence ceilings. The enforced semantic shadow corpus
is 10/10 and current routing remains regression-green.

Begin routing only metric level behind an explicit reversible selector. Do not
silently fall back when that selector receives a non-level Plan. Preserve the
public bundle contract and test reporting/materialization before changing the
default selector.

`set_transition@v1` is accepted provisionally for distinct change because an
additive contribution contract loses entrants, exits, and migrations. Revisit
whether it lowers to canonical set operations before treating it as irreducible.
Do not route drilldown until its dynamic child data requirements are explicit or
the provisional compound operator is justified by a stronger counterexample.
