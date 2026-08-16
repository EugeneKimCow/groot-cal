# groot-cal Codex Instructions

## Architecture Research

For architecture research, read these documents before starting:

- `docs/architecture/CANONICAL_ARCHITECTURE_RESEARCH.md`
- `docs/architecture/CODEX_LONG_RUNNING_ARCHITECTURE_GOAL.md`

Treat `CANONICAL_ARCHITECTURE_RESEARCH.md` as the governing research
specification.

Do not treat the current repository architecture as correct by default.

For architectural work:

- investigate before refactoring;
- generate competing hypotheses;
- actively search for counterexamples;
- prefer simplification over adding abstractions;
- prefer canonical operator composition over domain-specific implementations;
- prefer typed contracts and deterministic execution over free-form LLM logic;
- use representative analytical queries as the architecture test corpus;
- rerun regression tests after material architecture changes.

Do not stop at the first plausible architecture.

Use the cycle:

Hypothesis
→ Counterexample
→ Alternative
→ Experiment
→ Regression
→ Simplification
→ Revised Hypothesis

Maintain durable research state under:

`research/architecture/`

Record rejected hypotheses and failed experiments as well as successful ones.

For long-running research, choose the next useful experiment from the
current evidence instead of asking the user what to do next unless a
genuinely blocking decision requires user input.

Prefer small executable experiments over large speculative refactors.