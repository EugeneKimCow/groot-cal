# E-024 C2′ increment 2 — advisory vs LLM-under-contract on the H2 corpus

Date: 2026-08-17

## Question

H2's original design compared C1 (advisory: semantic docs provided, execution
free) against C2 (enforced) — but v4's C2 was fully deterministic, so the
"enforcement effect on an *agent*" remained partially confounded. E-024 runs
the missing condition: **C2′ = an LLM interprets the question, but every
downstream authority (validation, compilation, arithmetic) is the contract's.**
Does contract-constrained LLM interpretation beat advisory free execution on
the same fixed 10-case corpus — and does it do so with a *local 14B model*
against v4's frontier agent (gpt-5.6-terra)?

## Setup

- Corpus: the frozen H2 case corpus (10 cases: 3 result cases with expected
  values, 2 plan cases, 2 suspensions, 2 clarifications, 1 unknown metric).
- C2′ pipeline: `compile_shadow_intent` with the E-021 LLM proposer →
  deterministic clause validation → C4 compile → shadow executor. Unrouted
  capabilities (plan comparison) execute in measurement mode via the shadow
  executor — E-017's parity scope; this is measurement, not routing promotion.
- Scoring: analytical span (resolution→execution equivalents) — expected
  envelope/result statuses, expected values, plus two hard counters: silent
  substitutions and wrong values. Persistence/reporting are excluded and the
  exclusion is declared: on the contract path they are deterministic
  (E-018/E-019 parity), so they carry no information about the LLM.
- Attempts: 5 per case (v4 form), model qwen2.5-coder:14b, temperature 0.
- Baseline sanity: the rule proposer scores 10/10 through the same harness.

## Comparison frame (from wave-v4-final, gpt-5.6-terra)

| condition | full-task pass | resolution | binding | selection | execution |
|---|---|---|---|---|---|
| C0 raw | 7/50 (14%) | 14% | 0% | 29% | 31% |
| C1 advisory | 14/50 (28%) | 80% | 40% | 71% | 66% |
| C2 enforced (deterministic) | 100% | 100% | 100% | 100% | 100% |

Advisory's *analytical-span* joint pass cannot be recomputed exactly (per-trace
stage rows were not preserved in the committed evidence); it is bounded to
**[14, 29]/50 (28–58%)**. E-024 therefore compares against the generous upper
bound, not the flattering lower one.

## Scorer defect found by the baseline run

The rule-proposer baseline first scored 8/10: `_has_silent_substitution`'s
subject check accepted only `evaluate_metric` consumption, flagging legitimate
`plan_gap@v1` plans (which consume the metric directly) as substitutions — a
false positive latent since E-016, exposed by the first successful plan compile
in a fidelity measurement. Fixed to accept any Call consuming the subject's
metric ref; a regression test pins both the fix and the preserved detection
power (a gutted subject is still flagged).

## Results

### Initial run — qwen2.5-coder:14b, 5×10 = 50 runs (avg 5.6s/run)

- analytical pass **40/50 (80%)**; silent substitutions 0; wrong values 0;
  unstable cases 0 (every case produced one outcome across five attempts).
- Both failing cases failed identically 5/5 — deterministic, diagnosable:
  1. **unknown-metric ("7월 이익이 왜 줄었지?")**: the model bound "이익" to
     `finance.operating_profit@v1` and *answered* with the operating-profit
     decomposition where gold demands clarification. The contract validated
     the *ref* but never demanded the clause *text witness a registered
     alias* of it — an **alias-fidelity gap**, substitution-class, invisible
     to `_has_silent_substitution` because the subject is consumed
     consistently. The E-021 governed corpus never exposed it; this corpus
     did.
  2. **invalid-month ("13월…")**: refused as `out_of_domain` where gold wants
     `clarify` — safe, but the wrong refusal shape.

### Deterministic guards (no new LLM authority)

Two adapter guards align LLM proposals with the rule proposer's discipline:
a consumed subject whose text does not contain any registered alias of its
bound (registered) ref downgrades to *ambiguous*; out-of-range months
normalize from refusal to *clarification*. Unregistered refs still flow to
the validator's `out_of_domain`. Both guards are pinned by fake-transport
tests; detection power is regression-tested (a gutted subject still flags).

### Guarded run — same model, same 50 runs

- analytical pass **50/50 (100%)**; silent substitutions 0; wrong values 0;
  unstable cases 0.

### The comparison

| condition | model | analytical outcome |
|---|---|---|
| C1 advisory (v4) | gpt-5.6-terra (frontier), free execution | ≤ 29/50 (≤58%, generous bound); full task 14/50 (28%) |
| **C2′ (this experiment)** | **qwen2.5-coder:14b (local), under contract** | **50/50 (100%)**, substitutions 0, wrong values 0 |
| C2 enforced (v4) | deterministic | 50/50 (100%) |

## Qualification

- Scope: analytical span on the fixed corpus; not broad Korean recall
  (unresolved #16), not a population claim. The v4 agent did the full task
  including persistence/reporting in an isolated workspace; C2′'s excluded
  stages are deterministic on this path, but the reader should weigh the scope
  difference, which is why the bound comparison is reported.
- Model asymmetry cuts *against* C2′: v4's agent was a frontier model; C2′
  uses a local 14B. Any C2′ advantage is therefore conservative.

## Decision

C2′ closes H2's original comparison on this corpus: with the contract holding
every non-interpretive authority, a **local 14B model reaches the
deterministic enforced ceiling (100%)** on the analytical span, while a
frontier model with advisory documents and free execution stayed at or below
58%. The enforcement effect is not explained by model capability — the model
asymmetry ran the other way. The corpus also earned its keep twice over,
exposing one scorer false positive (plan_gap subject consumption) and one
genuine contract gap (alias fidelity), both now fixed deterministically and
pinned by tests. Remaining honest limits: fixed 10-case corpus, one local
model family measured to completion, analytical span only.
