# E-021 local LLM proposal adapter (C2′ increment 1)

Date: 2026-08-17

## Question

Can a local LLM take over clause-binding *proposal* while the deterministic
contract keeps every authority it had — validation, semantic downgrades,
unaccounted-text confession, compilation, arithmetic — so that model errors can
only become refusals or verifiably coarser answers, never silent substitutions
or wrong numbers?

## Implementation

- `shadow_intent` gained one explicit seam: `finalize_clause_record` (semantic
  compatibility → unaccounted confession → clause ids → defaults) is now shared
  by every proposer, and `compile_shadow_intent(proposer=...)` injects the
  proposal function. The rule-based proposer is unchanged and remains the
  default.
- `slice/llm_intent_adapter.py` builds a closed-vocabulary Korean prompt
  (registered metric aliases, dimension values, role/kind/state contract, two
  examples), calls Ollama (`format: json`, temperature 0, stdlib urllib only),
  and converts proposals into `ClauseBinding` rows.
- Three adapter guards keep the LLM out of authority it must not have:
  1. **span recovery is deterministic** — proposed text is located verbatim in
     the question; hallucinated text cannot bind, and the uncovered region is
     confessed by `_unaccounted_clauses` as unsupported/non_semantic;
  2. **relative-period arithmetic is recomputed** — "전월/작년 대비" baselines
     are overwritten with `shift_month` from the bound target, because the
     validator checks month *format*, not month *arithmetic*;
  3. **overlapping proposals resolve first-wins**, and malformed model output
     raises instead of guessing.
- Demo wiring: `run.py --route c4 --llm [MODEL]`; the interpreter is shown in
  the rendered output. Default route and rule-based demo are unchanged.

## Fail-closed evidence (fake-transport contract tests, no network)

- valid proposal compiles to byte-identical Calls as the rule proposer;
- hallucinated metric ref / predicate value → `clause_binding_valid` refusal;
- text absent from the question is dropped and the residual real clause is
  confessed — no silent loss;
- wrong "전월" arithmetic from the model is corrected to target−1;
- duplicate-span proposals converge to the first binding;
- non-JSON model output raises.

## Live measurement — governed corpus (5 paraphrases + 9 adversarial)

### gemma3:12b (14/14 answered, 2.9–5.6s each)

- full agreement with the rule proposer: 8/14 (identical statuses; identical
  Calls where both compiled);
- **silent substitutions: 0/14; wrong numbers: 0/14**;
- all 6 divergences trace to ONE proposal error: binding
  "원인/동인/달라졌어/기여로" to `delta` instead of `contribution`. The
  contract converted every instance into a safe outcome:
  - 3× coarser-but-correct executed answers (single Δ −340, no axis
    decomposition);
  - 1× registry type check rejected the incoherent plan
    (`rank input: Delta != Attribution`);
  - 1× singleton-analysis rule rejected a double binding;
  - 1× region-scoped delta whose value equals the contribution total — equal
    numbers, coarser shape.

### qwen2.5:72b-instruct-q4_K_M (re-run of the 6 divergent questions)

Re-run of the 6 gemma-divergent questions only (19–66s each):

- 4/6 converged to the rule proposer's byte-identical Call DAGs, including
  both "원인/동인" contribution plans, the ranked Top-3 plan (now correctly
  refused at the *route* stage as unrouted `rank@v1`, matching the rule path),
  and the offline-region contribution;
- "전월 대비 어떻게 달라졌어?" still compiles to `delta` — and produced
  Delta −340, the correct number. This reading is defensible ("how much did it
  change"), so the divergence is recorded as gold-label ambiguity in the
  paraphrase corpus, not a model error;
- "변동을 제품군별 기여로" fails closed on both models the same way: the
  phrase splits into two analysis clauses and the singleton rule refuses.
  A composite-phrase example in the prompt is the obvious next lever.

Model scale bought recall (4 of 6 divergences resolved); it changed nothing
about safety, which was already absolute at 12B.

## Qualification

This is C2′ increment 1: proposal-slot substitution on the governed corpus,
one small and one large local model. It does not yet measure broad Korean
recall (unresolved #16), does not touch C0/C1-style free execution, and the
prompt's cue list is itself a registered-vocabulary artifact. The H2-completing
comparison (C1 advisory vs LLM-under-contract on the fixed case corpus) is the
natural increment 2.

## Decision

The contract holds against a live LLM proposer: interpretation errors degrade
to refusals or verifiably coarser answers, never silent substitutions or wrong
numbers. Model scale buys recall, not safety — safety lives in the contract.
