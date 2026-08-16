# Architecture research completion audit

Date: 2026-08-16

This audit evaluates the research objective, not production migration.

| Requirement | Evidence | Assessment |
|---|---|---|
| Read governing instructions first | `AGENTS.md` and both architecture research documents were read before repository actions | Proven in session; governing constraints reflected below |
| Inspect current repository before refactoring | `inventory.md`, E-000/E-001; production files unchanged by research | Proven |
| Durable research state | README plus inventory, hypotheses, alternatives, corpus, counterexamples, experiments, decisions, metrics, unresolved, current best, next experiment, journal | Proven |
| At least 30 representative queries | `query_corpus.json` contains 60 unique questions across >30 categories | Proven by `test_research_state.py` |
| Competing architectures on same corpus | C0–C4 manifests and `compare_candidates.py`; all score the same 60 requirements | Proven structurally; not equivalent to full implementations |
| Repeated hypothesis/counterexample/experiment/regression cycles | Journal iterations 0–7 and E-000–E-010 | Proven |
| Record failures/rejected paths | stale fixture assertions, JSON tuple shape, omitted region, rejected open-world scorer, weakened/rejected hypotheses | Proven |
| Prefer minimal experiments before refactor | isolated prototypes under research; no product routing changed | Proven |
| Strong counterexamples tested | silent intent, rate/mix, migration, fanout, time reducer/grain, held-out waves, valid time/privacy/freshness, guard, causal refusal, quantile nonadditivity | Proven for representative strongest cases |
| Regression after material experiments | after E-017 research 58/58; production 164 discovered with 163 pass/1 environment skip; golden 17/17; current and shadow enforced 10/10 | Proven |
| Simplification attempted | level variants collapsed in prototype; diagnosis layer rejected; no new IR node across held-out waves; SQL excluded from IR | Proven |
| Additional cycles produce little material architecture change | last three cycles expanded contract/check details but did not change three primary contracts or Call grammar | Supported, not mathematical proof |
| Remaining uncertainty explicit | `unresolved.md` and synthesis §12 | Proven |
| Answer the twelve requested architecture questions | `synthesis.md` §§1–12 | Proven |
| Final adversarial phase | E-008 held-out wave and E-009/E-010 executable boundary attacks | Proven |
| C3/C4 implementation discriminator | E-011 integrated five-query parity, error, serialization, and concept comparison | Proven for representative slice |
| Governed intent fidelity gate | E-016 accounts for 9/9 adversarial questions, zero silent substitutions, and 5/5 change paraphrases | Proven for governed corpus; not broad Korean recall |
| Executable C4 parity | E-017 covers five level algebras, additive/distinct change, rate refusal, plan, rank, drilldown, budgets, failures, and provenance | Proven for representative analytical paths; routing remains separate |

## Scope qualification

The research objective is complete enough to select a current best logical
architecture. It does not prove C4's production implementation, broad LLM
planning accuracy, or real-world performance. Those are explicitly separate
uncertainties and the next implementation experiment, not hidden completion
claims.
