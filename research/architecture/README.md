# Architecture research state

This directory is the durable working memory for the long-running groot-cal
architecture investigation. The governing specification is
`docs/architecture/CANONICAL_ARCHITECTURE_RESEARCH.md`.

The files are deliberately separated so failed ideas remain visible:

- `inventory.md` — observed current architecture and coupling
- `hypotheses.md` — competing, falsifiable hypotheses
- `alternatives.md` — architecture families evaluated on one corpus
- `query_corpus.json` — shared architecture test corpus
- `counterexamples.md` — strongest known attacks
- `experiments.md` — executable and paper experiments, including failures
- `decisions.md` — provisional and final decisions with evidence
- `metrics.md` — proxy definitions and iteration measurements
- `unresolved.md` — uncertainties that must not be hidden
- `current_best.md` — current leading architecture, never assumed final
- `current_best.ko.md` — Korean translation of the current leading architecture
- `next_experiment.md` — one evidence-selected next step
- `journal.md` — chronological research cycles
- `synthesis.md` — evidence-backed answers to the twelve target questions
- `completion_audit.md` — requirement-by-requirement research audit
- `e011-comparison.md` — integrated C4/C3 parity and cost comparison
- `e014-comparison.md` — normalized result boundary and ceiling enforcement
- `e015-comparison.md` — Bound Intent versus direct C4 contract discriminator
- `e016-comparison.md` — governed Korean shadow intent compiler fidelity gate
- `e017-comparison.md` — executable C4 parity across current analytical paths
- `refactoring_plan.md` — evidence-gated production migration sequence
- `intent_compiler_plan.md` — explicit pre-routing intent fidelity gate

## Reproduction baseline

```bash
python3 -m unittest discover -s slice -p 'test_*.py'
python3 slice/eval_golden.py
python3 slice/eval_semantic.py
```

Baseline observed 2026-08-16: 84 unit tests, 83 passed and one nested
Seatbelt test skipped; golden set 17/17; enforced semantic baseline 10/10.

After E-012 shadow contracts: 102 unit tests discovered, 101 passed and one
nested Seatbelt test skipped; golden 17/17; semantic 10/10; research 40/40.

After E-013 normalized evaluator: 117 unit tests discovered, 116 passed and one
nested Seatbelt test skipped; golden 17/17; semantic 10/10; research 40/40.

After E-014 normalized result boundary: 133 unit tests discovered, 132 passed
and one nested Seatbelt test skipped; golden 17/17; semantic 10/10; research
40/40.

After E-015 intent contract discriminator: product remains 133 discovered, 132
passed and one nested Seatbelt test skipped; golden 17/17; semantic 10/10;
research 58/58.

After E-016 shadow intent compiler: 149 product tests discovered, 148 passed and
one nested Seatbelt test skipped; golden 17/17; semantic 10/10; research 58/58.

After E-017 shadow executor parity: 164 product tests discovered, 163 passed and
one nested Seatbelt test skipped; current-route golden 17/17; current-route and
shadow semantic 10/10; research 58/58.
