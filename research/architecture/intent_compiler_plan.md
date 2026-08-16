# Intent compiler migration plan

Status: E-016 shadow fidelity gate complete; production routing unchanged.

## Purpose

The current interpreter reduces a question to one metric, one month, scope, a
comparison, and one of three operation families. It can therefore return a
successful but substituted analysis after dropping a requested reducer,
breakdown, ranking, limit, year, or analytical objective.

No new analytical route may be enabled until a shadow intent compiler can prove
that every material language clause was bound, preserved, clarified, or safely
refused.

```text
question
  -> clause inventory with source spans
  -> closed semantic and analytical binding
  -> fidelity verification
  -> typed Call+Ref Plan | clarify | out_of_domain
```

The intent compiler proposes bindings. Semantic and operator registries remain
the authority. The compiler never invents a metric, dimension, aggregation
rule, operator, calendar, model, or scenario reference.

## Material-clause rule

A clause is material when changing or removing it can change at least one of:

- subject metric, expression, entity, or cohort;
- estimand, reducer, comparison, model, or analytical operator;
- time window, calendar, alignment, or `as_of`;
- filter, breakdown, hierarchy, ordering, ranking, or limit;
- requested output selection or epistemic claim.

Every material clause must retain its source span and end in one explicit
state: `consumed`, `preserved`, `ambiguous`, or `unsupported`. A successful Plan
may contain only `consumed` and `preserved` material clauses. Non-semantic
discourse may be marked `non_semantic` with a reason; it is not a catch-all for
unknown analytical language. Defaults are recorded separately and never
presented as user-authored clauses.

## Competing contract hypotheses

E-015 must compare both approaches on the same corpus before adding another
permanent representation:

1. **Bound Intent Spec:** a non-executable typed object for subjects, temporal
   semantics, requested analyses, breakdown/ranking, output constraints, and a
   clause ledger; it compiles to C4 Calls.
2. **Direct Plan plus binding record:** compile directly to C4 Calls while a
   typed binding record links source clauses to Call inputs, outputs, or safe
   refusals.

The winner must preserve equal fidelity with fewer duplicated concepts. The
intent representation must not become a second Analytical IR or repeat the
operator registry.

## E-015 — Intent contract discriminator

1. Define one versioned clause/binding record shared by both hypotheses.
2. Encode representative current and adversarial questions in both forms.
3. Cover at least subject, reducer, comparison, time, filter, breakdown,
   ranking/limit, multi-metric, nested request, and output restriction.
4. Compile supported cases to byte-comparable normalized C4 Plans.
5. Compare concept count, duplicated fields, error locality, deterministic
   validation, serialization stability, and ability to account for every
   material clause.
6. Select one contract and record the rejected alternative.

No natural-language model integration or production routing occurs in E-015.

## E-016 — Shadow intent compiler and fidelity harness

1. Implement the selected contract behind a new shadow-only compiler boundary.
2. Allow deterministic rules or an LLM adapter to propose bindings, but require
   closed-vocabulary resolution and deterministic validation afterward.
3. Compile only when all material clauses are accounted for and all referenced
   contracts exist.
4. Return `clarify` for material ambiguity and `out_of_domain` for unsupported
   analytical meaning; never fall back to a neighboring operation family.
5. Normalize paraphrases against the same intent/Plan equivalence rules.
6. Keep `operation_family` as audit metadata derived from or checked against
   root Calls, never as execution dispatch.

## Required counterexample gate

The following must no longer produce a substituted successful analysis:

- `7월 평균 재고는?`
- `7월 재고 회전율은?`
- `7월 오프라인 매출 감소를 지역별로 보여줘`
- `7월 매출 감소 상위 3개 제품군만 보여줘`
- `2025년 7월 매출은?`
- `7월 매출 증가 속도가 둔화되고 있는가?`
- `7월 매출 감소가 일부 고객의 이상치 때문인가?`
- `7월 매출은 제품과 지역 중 어디에 더 집중되어 있나?`
- `7월 매출과 영업이익은 왜 엇갈렸나?`

Correct handling may be a supported Plan, `clarify`, or `out_of_domain`. A
plausible result for a different estimand is always a failure.

## Exit gate before analytical routing

- zero unaccounted material clauses in the governed intent corpus;
- zero silent substitutions in the adversarial gate;
- existing five-change paraphrases normalize 5/5, with broader groups reported
  separately rather than hidden in one aggregate;
- all successful bindings reference registered semantic and operator contracts;
- deterministic serialization and validation errors are regression-tested;
- full product, golden, semantic, and research regressions remain green;
- `engine.run_question` still uses the current route until later capability
  migration explicitly passes its own parity gate.

## Non-goals

- implementing every requested analytical operator;
- treating free-form rationale as an executable intent contract;
- embedding SQL or physical source selection in intent;
- duplicating the C4 DAG as an intent-specific workflow language;
- routing production traffic before shadow fidelity and execution parity.

## E-015 outcome — 2026-08-16

The shared twelve-case discriminator achieved seven byte-identical successful
C4 Plans and five identical refusal/clarification outcomes. A separate Bound
Intent Spec added 2,646 serialized intermediate bytes, duplicated 34 bound
values, and required a record/spec consistency check without improving fidelity
or clause-local errors.

E-016 will therefore implement **direct C4 Plan compilation plus one closed,
typed clause-binding record**. The binding record remains a first-class audit
contract; “direct” does not mean unaudited or free-form compilation. Every
successful material clause still needs a concrete target and all referenced
vocabulary remains registry-governed.

The Bound Intent Spec is rejected for the current evidence. Reconsider it only
if a stable intent object gains an independent consumer that cannot use the C4
Plan or binding record without duplicating analytical/operator semantics.

## E-016 outcome — 2026-08-16

The production shadow boundary now contains one versioned source-clause record,
a closed tagged role/value union, exact source spans, explicit outcome states,
and concrete Plan-consumer links. The Korean adapter is only a proposal
mechanism; deterministic validation and the semantic/operator registries remain
the authority. Unknown analytical text fails as `unsupported` rather than being
hidden as discourse.

The nine required adversarial questions yielded four lossless Plans and five
clause-local safe refusals, with zero silent substitution. All five existing
change paraphrases compile to the `explain_change` family. Serialization,
hashing, malformed spans, unknown references, and multiple singleton objectives
are regression-tested. Product is 148 pass plus one environment skip; golden
17/17, semantic 10/10, and research 58/58.

This closes the pre-routing fidelity gate for the governed corpus, not general
Korean language understanding. E-017 must now prove execution parity before any
capability can route through the C4 path.
