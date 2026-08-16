# Codex Long-Running Architecture Research Goal

```text
/goal Treat docs/architecture/CANONICAL_ARCHITECTURE_RESEARCH.md as the governing research specification for this task.

Your objective is NOT to quickly produce one architecture proposal.

Your objective is to investigate the current groot-cal repository and progressively discover a simpler, more logical, more canonical architecture for translating BI-style natural-language analytical questions into:

Question
→ Intent
→ Semantic Binding
→ Analytical Plan / IR
→ Data Requirements
→ RDBMS Query
→ Canonical Mathematical Operators
→ Validation
→ Evidence
→ Answer

Work autonomously for as long as useful. Do not stop after producing an initial recommendation, architecture diagram, or implementation.

The path to the answer is intentionally uncertain. Treat this as an architecture research problem rather than a normal feature implementation task.

First, read the entire research specification and inspect the existing repository deeply enough to understand the current implementation before proposing changes.

Then establish persistent research artifacts inside the repository, including at minimum:

- current architecture inventory
- hypotheses
- alternative architecture candidates
- query corpus
- counterexamples
- experiments
- decisions
- proxy metrics
- unresolved questions
- current best architecture
- next experiment

Use these files as durable working memory. Re-read and update them throughout the run so that progress does not depend only on conversation context.

Operate in repeated research cycles:

OBSERVE
→ FORM HYPOTHESIS
→ DERIVE CONSEQUENCES
→ GENERATE ALTERNATIVES
→ RED TEAM
→ FIND COUNTEREXAMPLES
→ BUILD MINIMAL EXPERIMENT
→ TEST
→ COMPARE
→ SIMPLIFY
→ RECORD EVIDENCE
→ SELECT NEXT EXPERIMENT
→ REPEAT

Important operating rule:

Do not interpret “having a plausible architecture” as completion.

Whenever you reach a seemingly good architecture, actively try to falsify it.

Ask:

- Which realistic BI or SCM query cannot be represented?
- Which abstraction exists only because of the current implementation?
- Can two concepts be collapsed into one?
- Can a domain-specific operation be expressed as a composition of canonical operators?
- Can free-form LLM reasoning be replaced by a typed contract or deterministic execution?
- Is Diagnosis really a persistent layer, or can it be generated as a conditional analytical DAG?
- Is a proposed primitive genuinely primitive?
- Can the same capability be achieved with fewer concepts?
- Does this architecture survive when SCM-specific terminology is removed?
- Does it survive when PostgreSQL, TypeDB, YAML, or any particular implementation technology is replaced?

Do not add abstractions merely because they make one difficult case easier.

Before adding any new primitive or subsystem:

1. identify the concrete counterexample that requires it,
2. prove that existing composition is insufficient,
3. determine whether the requirement belongs to core or a domain pack,
4. evaluate how many exceptions the new concept removes,
5. rerun the query corpus.

Build or extend a representative query corpus and use it as an architectural test suite.

Include simple and difficult cases such as:

- aggregation
- comparison
- ranking
- contribution decomposition
- offsetting drivers
- mix vs rate
- price / volume / mix
- trends
- acceleration / deceleration
- change points
- robust outlier detection
- concentration
- non-additive metrics
- derived metrics
- weighted metrics
- multi-dimensional driver analysis
- nested diagnosis
- counterfactual analysis
- combinations of the above

Prefer discovering the minimum Analytical IR grammar by working backward from these questions rather than designing a large ontology or class hierarchy first.

Continuously compare at least these architecture families:

A. semantic-heavy architecture
B. operator-centric architecture
C. IR-centric architecture with a thin semantic layer
D. the current groot-cal architecture

Create additional candidates if evidence warrants them.

Do not prematurely commit to one.

Use quantitative proxy metrics where useful, including:

- query coverage
- concept count
- IR node/type count
- canonical operator count
- operator reuse ratio
- domain-specific exception count
- special planner rule count
- deterministic execution ratio
- planning stability across paraphrases
- regression failures

These metrics are indicators, not the objective function.

Architectural judgment remains qualitative.

Favor architectures that simultaneously tend toward:

coverage ↑
composability ↑
operator reuse ↑
planning stability ↑
determinism ↑
explainability ↑
testability ↑

while tending toward:

concept count ↓
special cases ↓
domain duplication ↓
free-form LLM logic ↓
framework coupling ↓

Use subagents when independent investigation would materially improve the research.

Good subagent tasks include:

- inspect the existing semantic model
- independently derive a minimal IR
- design adversarial BI questions
- challenge the current best architecture
- inspect operator taxonomy
- test domain portability
- act as an architecture minimalist
- act as a compiler/IR designer

Prefer parallel subagents for read-heavy exploration and criticism. Avoid uncontrolled parallel edits to the same architecture files.

After collecting subagent results, synthesize and judge them in the main thread rather than accepting them independently.

When ambiguity exists, do not immediately stop to ask me.

If the ambiguity can be explored safely:
- state the assumption,
- test more than one interpretation where useful,
- record the uncertainty,
- continue the research.

Only stop for user input when a genuinely blocking decision cannot be investigated from repository evidence or experiments.

Do not optimize for code volume.

Deleting a concept, rejecting a hypothesis, finding a counterexample, or proving that an existing layer is unnecessary counts as meaningful progress.

Prefer small executable experiments over large speculative refactors.

For every material architectural hypothesis, try to produce evidence using one or more of:

- query corpus results
- typed IR examples
- executable prototypes
- unit tests
- invariant checks
- comparison against alternative architectures
- counterexamples
- code complexity changes
- removal of special cases

If an experiment fails, record why. Do not erase failed reasoning paths.

Periodically re-read the governing research document and current research journal to guard against drift.

Do not repeatedly ask me what to do next.

Choose the next experiment based on the current evidence.

Continue while there is a meaningful unresolved hypothesis, counterexample, simplification opportunity, or architecture comparison that could materially change the conclusion.

A candidate architecture should not be considered mature merely because all current tests pass. Before considering completion, perform a final adversarial phase specifically designed to break the current best model.

The final result should be evidence-backed rather than merely persuasive.

The eventual output should clearly answer:

1. What is the minimum semantic contract groot-cal needs?
2. What is the minimum analytical operator model?
3. What is the minimum Analytical IR grammar?
4. What belongs in Domain Packs rather than Core?
5. Is a separate Diagnosis Layer necessary?
6. What exactly should the LLM decide?
7. What should be deterministic?
8. Where should SQL generation sit?
9. What should remain storage- and vendor-neutral?
10. Which current groot-cal abstractions should be retained, merged, redesigned, or removed?
11. What architecture survived the strongest counterexamples?
12. What important uncertainties remain?

Do not stop simply because you have written an answer to these questions.

Stop only when additional iterations are producing little material architectural change, the strongest known counterexamples have been addressed or explicitly documented, the alternatives have been compared against the same corpus, and you can explain why the current architecture is preferable with evidence.

If convergence remains uncertain, report the competing candidates and the experiment that would best discriminate between them rather than pretending certainty.

Start now by reading the governing document and inspecting the repository. Create the research state needed for a long-running investigation, formulate the first competing hypotheses, and begin the first research cycle without waiting for further instructions.
```