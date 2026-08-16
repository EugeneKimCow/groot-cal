# Experiment log

## E-000 — Reproduction baseline

Date: 2026-08-16

Commands:

```bash
python3 -m unittest discover -s slice -p 'test_*.py'
python3 slice/eval_golden.py
python3 slice/eval_semantic.py
```

Result: 84 tests executed, 83 passed, one nested Seatbelt test skipped; golden
17/17; enforced semantic cases 10/10. This is the regression floor for later
minimal experiments.

## E-001 — Inventory trace

Method: trace one question through catalog, interpretation, Query Spec,
profile dispatch, pipeline, runtime, result, and reporter; compare the two
execution profiles and the machine registry.

Result: the current plan contract does not determine execution. Significant
strategy lives in Python pipeline branches, and the registry cannot invoke an
operator from its own contract. H-001 is strengthened, but no redesign has yet
been tested.

Observed executable probes:

- `7월 평균 재고는?` returns the period-end balance as a normal result.
- `7월 재고 회전율은?` binds `재고` and returns the inventory balance.
- `7월 오프라인 매출 감소를 지역별로 보여줘` omits the requested region
  breakdown and runs other fixed analyses.
- `7월 매출 감소 상위 3개 제품군만 보여줘` ignores rank, limit, and only.
- `2025년 7월 매출은?` binds 2026-07.
- Rate change is safely rejected and multi-metric input is clarified, showing
  that explicit refusal is possible but inconsistently applied.

Result refinement: the primary current-architecture failure is not only low
coverage. It is silent intent substitution with a successful envelope.

Implementation note: the first characterization assertion expected the metric
id `supply.inventory_balance`, but the registered id is
`operations.inventory_on_hand`. The probe failed for a test-fixture naming
mistake, not an architectural disagreement; the failed assertion and correction
are retained here rather than hidden.

## Planned E-002 — Corpus representation matrix

Define explicit capability manifests for C0–C4 and score every query using the
same feature requirements. Manually audit all failures to avoid equating a
manifest flag with real executability.

Discriminates: whether C3/C4 gain coverage with fewer special planner rules or
merely rename missing functionality.

### Attempt 1 result and measurement rejection

On the initial 40-query corpus the manifest ceiling was C0 10/40, C1 31/40,
C2 26/40, C3 40/40, C4 40/40. C3/C4's result is not evidence of execution;
the candidates were derived from that corpus.

More importantly, denylist manifests computed support as “all requirements in
the current corpus minus known exclusions.” A new requirement would therefore
be credited automatically. This comparison rule is rejected. The capability
universe is now closed at the attempt-1 vocabulary, and Q041–Q050 are held-out
join, calendar, cohort, reducer, alignment, estimand, scenario, null, grain, and
replay attacks. A candidate must explicitly earn any new capability.

### Attempt 2 held-out result

With a closed vocabulary, C0 scored 10/50, C1 31/50, C2 26/50, and C3/C4
40/50. Every leading-candidate miss was real: the original “thin semantic”
description omitted relationship cardinality/fanout/allocation, fiscal calendar,
cohort reference, daily grain/time reducer, unit/grain/calendar alignment,
unknown-bucket policy, scenario/reweighting, comparable attribution model, and
explicit replayability.

Consequence analysis found no new IR node form was required. These requirements
map to semantic references and validation laws, operator contracts, ordinary
Call inputs, or the serialized Plan contract. C3/C4 explicitly earned these
capabilities for the structural ceiling and return to 50/50, but none is marked
implemented. “Thin semantic layer” now means workflow-thin, not data-anemic.

## Planned E-003 — Minimal aggregate IR

Prototype only enough typed IR to express level aggregation for additive,
ratio, balance-last, and distinct metrics. Compare:

- separate level operators;
- one aggregate node with a typed semantic expression.

Measure node types, invariants, invalid-plan rejection, and fixture results.
Do not route production code through the prototype.

### First run

The implementation passed the rate, balance, distinct, contract, and unknown
algebra cases but failed the two commerce assertions because the research test
used stale expected values (`10450`, `5210`) rather than the fixture's current
July totals (`3860`, `1580`). Production regressions still passed. The expected
values were corrected; this is recorded as experiment-fixture error rather than
evidence against the aggregate model.

The second run exposed a representation issue: immutable tuple predicates were
returned directly instead of a JSON-native plan/result shape. Execution values
were correct. The prototype now serializes predicates as lists, preserving the
distinction between internal immutable representation and wire contract.

## E-004 — Explicit requested and nested breakdown DAG

Prototype: generic versionable calls, result references, and a deterministic
`max_abs` selector; current `contrib_decomp` is reused unchanged.

Initial run: nested region→category execution and forward-reference rejection
passed. The direct region assertion omitted the declared `호남` bucket and
failed; the plan had correctly preserved all four registered regions. The
fixture expectation was corrected and the failure retained here.

Interpretation so far: requested breakdown and a two-stage diagnostic path do
not require a new diagnosis layer or a new mathematical decomposition. They
require the planner to preserve the requested axis and an executable edge from
the deterministic selection result into the next slice. This supports H-001
and H-005, but budget/provenance/type contracts are not yet integrated into the
prototype.

## E-005 — Rate/mix and entity-transition falsification

### Rate/mix fixture

Baseline segment rates were A=0.9 and B=0.1 with equal denominator weights,
giving total 0.5. Target segment rates remained unchanged while weights moved
to 0.25/0.75, giving total 0.3. The symmetric two-factor decomposition returned
rate effect 0.0, mix effect -0.2, and closed exactly to total change -0.2.

Conclusion: two level evaluations plus raw delta cannot explain the estimand.
A registered rate/mix analytical contract with an explicit convention and
identity is justified. It is domain-independent, but it remains one Call in the
IR rather than a new node form.

### Entity transition fixture

Both periods contained four distinct customers and each region contained two,
so current `distinct_decomp` returned total and regional deltas of zero. The
same rows contained two entrants, two exits, two retained entities, and one
region migration. Set identities closed for both baseline and target.

Conclusion: period-wise distinct attribution and membership transition are
different estimands. Entry/exit/retention are set composition; dimension
migration additionally requires functional assignment. A canonical
entity-transition result contract is justified, while an “active customer
diagnosis” domain operator is not.

Regression: research 13/13; production 83 pass + one environment skip.

## E-006 — Logical data requirements and SQL fanout

SQLite fixture: two order lines total 160 and a multi-valued tag bridge. A naive
join summed to 260. A backend-neutral `DataRequirement` carrying source grain,
relationship cardinality, aggregation expression, group-by, and allocation
policy rejected the many-to-many request before SQL when policy was absent.

With explicit `equal_split`, backend lowering produced tag totals 50 and 110,
reconciling to 160. The same lowering preserved ratio-of-sums components:
allocated numerator 50 and denominator 160, overall ratio 0.3125. It did not
average row ratios.

Architectural result:

- source grain and relationship cardinality belong to semantic/data contracts;
- allocation changes the estimand and must be explicit, never a backend default;
- fanout/allocation validation belongs before or during data planning;
- aggregation algebra must survive lowering as an expression, not a field name;
- SQL is a physical backend artifact produced from Data Requirements;
- Data Requirements are compiler output from the analytical plan, not another
  free-form object for the LLM to invent.

No Analytical IR node kind was added. Research regression: 17/17.

## E-007 — Time, calendar, and grain alignment

A three-day inventory series produced period-end 300 and average daily
inventory 200 from the same metric reference. A monthly-period-end contract
rejected the average request, and a daily contract suspended when one daily
snapshot was missing. Daily actual aligned to a weekly plan only with explicit
additive `sum`, a registered window/calendar, and complete daily observations.
A registered fiscal period resolved to the same generic `TimeWindow` shape.

Architectural result: time reducers are part of the bound estimand; available
observation grain is semantic/data authority; calendar/cohort references are
Slice inputs; alignment is compiler/type-checker behavior with deterministic
checks. No time-specific execution profile, diagnosis layer, or IR node kind is
needed. Research regression: 22/22.

## E-008 — Second held-out architecture attack

Q051–Q060 reduced C3/C4 from 50/50 to 50/60 under closed-world scoring. Misses
were classified before revising the candidates:

- semantic/Slice: valid-time SCD, data vintage, conversion-rate vintage,
  business calendar, partial/comparable window;
- data planner: valid-time join and many-to-many allocation;
- analytical contracts: unit conversion, Simpson diagnostic over rate/mix,
  leave-one-out ranking stability, sampling model/uncertainty;
- evidence/governance: privacy suppression and multi-source freshness vector.

No case required a new planning node form. Each is an ordinary semantic or
result reference, Call, policy, or compiler check. C3/C4 explicitly earn these
structural capabilities and return to 60/60; execution remains unproven for the
new wave. The next experiment targets cross-boundary cases most likely to show
that “policy” was hiding a fourth core contract.

## E-009 — Valid-time, privacy, and freshness boundary

Current-row joining rewrote a June customer transaction from silver to the
customer's current gold tier. Valid-time binding preserved silver for June and
gold for July. Minimum-group suppression hid two small groups while carrying a
suppressed residual, so visible rows were not falsely presented as the total.
A two-source freshness vector marked the result stale when FX changed and
suspended when the current FX snapshot was unavailable.

Conclusion: valid time is semantic/data binding; privacy is a result disclosure
policy with reconciliation; freshness is evidence over source provenance.
These constrain the existing contracts and ports rather than requiring a
fourth primary governance contract. Research regression: 26/26.

## E-010 — Final adversarial boundaries and planning stability

A serialized typed guard deterministically skipped a false diagnostic branch.
Five intended change-analysis paraphrases produced four `explain_change` plans
and one incorrect `inspect_level`, measuring current planning stability at 4/5
and confirming that an IR does not itself solve interpretation fidelity.

Deterministic portfolio reweighting returned a noncausal scenario result. A
causal counterfactual without model and identification contracts suspended and
explicitly prohibited observed-row filtering as fallback. Finally, segment
median changes summed to 1.0 while the total median changed 0.5, falsifying
additive contribution for quantiles.

Conclusion: typed guards fit the Call grammar; causal and deterministic
counterfactuals must remain different analytical contracts; distributional
operators need their own estimands/laws. Research regression: 31/31.

## E-011 — C4 versus C3 integrated vertical slice

Five representative queries were encoded in both forms over one executable
registry/runtime/data compiler. Both produced identical normalized results,
SQL requirements, budgets, DAG traces, and provenance. Cross-input dimension
validity and reference port types were rejected before SQL.

Measured result:

- C4: one node class, zero node lowering dispatches, 2,306 serialized bytes;
- C3: six node classes, six lowering dispatches, 1,768 authoring bytes;
- compiled C3 runtime form: the same 2,306-byte C4 representation;
- tested error quality improvement from C3: none.

Two experiment corrections were retained: direct root module invocation first
failed because the research directory was not on `PYTHONPATH`, and the initial
budget assertion incorrectly expected an exhausted output to disappear rather
than remain as a normalized failure. Neither changed the architecture result.

Decision: C4 is the canonical wire/runtime IR. C3-style typed nodes may be
generated authoring helpers, not a second architecture. Integrated tests added:
9; total research regression becomes 40.

## E-012 — Production Increment 1 in shadow mode

Hypothesis: the canonical C4 contracts can be introduced beside the current
runtime, make structured intent loss observable, and validate typed edges
without changing any public execution result.

Implementation:

- added immutable `Plan`, generic `Call`, `Ref`, monthly `Slice`, binding-ledger,
  operator-port, and strict tagged Result Envelope contracts;
- added deterministic wire serialization and SHA-256 plan identity;
- added an executable shadow registry for closed ports, typed/forward refs,
  slice validity, known semantic references, and named cross-input laws;
- compiled current level Query Specs to one `evaluate_metric@v1` Call and simple
  comparison roots to two evaluations plus `delta@v1`;
- refused plan comparison because its operator is outside Increment 1;
- refused injected top-level `rank` and nested `intent.breakdown` clauses as
  unconsumed rather than silently dropping them;
- left `engine`, both pipelines, kernels, runtime, and reporter untouched.

Counterexample result: the binding ledger catches clauses once they exist in a
structured Query Spec. It cannot recover ranking, breakdown, average-vs-end,
or other language intent that the current interpreter already discarded before
producing that spec. The shadow compiler therefore reduces downstream silent
loss but does not solve the known interpretation-fidelity defect.

One test expectation was corrected during the cycle: 1,580 is scoped online
July sales, while unscoped July sales is 3,860. This was a test error, not a
runtime behavior change.

Regression: 18 shadow/contract tests pass; production discovery is 102 tests,
101 pass and one environment skip; golden 17/17; semantic 10/10; research
40/40. Increment 1 exit gate is satisfied.

## E-013 — Normalized metric evaluation shadow parity

Hypothesis: one aggregation-rule registry can evaluate all current scalar
metrics without domain IDs or per-type arithmetic branches, while a normalized
carrier removes the `value_u`/`value` distinction.

Implementation added four strategies: sum, ratio-of-sums, period-end sum, and
entity cardinality. Strategies declare required bindings and admissible nominal
types; the aggregation rule selects the implementation. The result is a strict
`MetricScalar` inside the E-012 tagged Result Envelope, carrying Slice, unit,
expression/components, checks, provenance, and a canonical label ceiling.

The shared level comparison covered five catalog metrics plus scoped sales and
a new count fixture. Values, units, scopes, metric/source/input/as-of provenance,
and evidence ceiling all matched or normalized as intended. Amount and count
used the identical sum strategy. No current execution file imports the new
evaluator.

Counterexamples:

- duplicate rate bindings are accepted by the legacy path but rejected by the
  candidate with `field_binding_unique`;
- negative rate inputs, null distinct IDs, and zero denominator behavior match;
- inconsistent balance type plus sum rule is rejected by both, with the new
  path using generic strategy admissibility rather than a balance arithmetic
  branch;
- unknown algebra/scope, missing fields/period, and duplicate Slice predicates
  fail closed.

Conclusion: scalar `evaluate_metric` remains viable. The type vocabulary is an
admissibility contract, while aggregation rule selects mathematics. Increment
2 is not complete because live payloads and reporter probes are unchanged, and
duplicate-binding enforcement is not live. Production discovery after E-013 is
117 tests, 116 pass and one environment skip; golden 17/17; semantic 10/10;
research 40/40.

## E-014 — Normalized result consumption boundary

Hypothesis: one read-only adapter can normalize the current result families for
all downstream consumers without changing public payloads or analytical
routing.

The adapter exposes one scalar or total-change view, normalized segments,
source/operator/provenance references, and role-based label capabilities.
Reporter, CLI, and materialization now use this boundary; their legacy numeric
shape probes were removed. Materialization still stores the exact original
payload and preserves its identity.

Malformed and ambiguous numeric shapes fail closed. Reporter labels now derive
from the declared ceiling, and independent lint rule `LBL02` rejected both an
arithmetic-label escalation and promotion of suggestive event evidence to data
confirmation. The live typed kernel also gained the canonical duplicate
binding check that E-013 had enforced only in shadow mode.

Conclusion: Increment 2 is complete. The remaining compatibility debt is one
adapter branch for legacy Korean-keyed label maps; it can disappear with the
old producers. Production discovery is 133 tests, 132 pass and one environment
skip; golden 17/17; semantic 10/10; research 40/40.

## E-015 — Intent contract discriminator

Hypothesis A inserted a serialized Bound Intent Spec between a versioned source
binding record and C4. Hypothesis B compiled the same record directly to C4.
Both shared closed role/value validation and the same emitter so the experiment
isolated the value of the intermediate representation.

Twelve cases covered reducer, explicit time/comparison, filter, breakdown,
ranking/limit, output restriction, multi-metric, nested diagnosis, ambiguity,
and all nine required silent-substitution attacks. Seven supported cases emitted
byte-identical Plans under both hypotheses; five unsupported/ambiguous cases had
identical clause-local outcomes.

The Bound Intent Spec added 2,646 intermediate bytes, duplicated 34 bound
values, one contract type, and one cross-representation consistency check. It
improved neither fidelity nor error locality. A red-team case also found that
the first shared emitter would choose the first of multiple objective bindings;
the corrected validator refuses them unless explicit composition is registered.

Conclusion: Hypothesis B wins. E-016 will implement direct C4 Plan compilation
plus the typed binding record in production shadow mode. This is a contract
simplification, not permission for untyped/free-form planning.

Regression: E-015 18/18, full research 58/58, product 132 pass plus one
environment skip, golden 17/17, and semantic 10/10. Routing changes: zero.

## E-016 — Shadow intent compiler and fidelity harness

Hypothesis: a governed Korean proposal adapter plus the E-015 closed binding
record can account for every material clause and compile directly to C4 without
a second intent representation or a neighboring-analysis fallback.

Implementation added the versioned record and schema, a closed tagged
role/value validator, a conservative Korean inventory adapter, direct C4
emission, and registered shadow contracts for contribution, ranking, metric
alignment, and drilldown. `operation_family` is derived from emitted Calls.
The current engine does not import the new boundary.

The nine required attacks produced four supported Plans and five explicit
refusals. The supported cases retained filter/breakdown, rank/limit/only,
explicit year, and multi-metric composition. Average inventory was refused
because the monthly point-in-time source cannot satisfy `time_average`; inventory
turnover and the acceleration, outlier, and concentration objectives were not
substituted. The five change paraphrases normalized 5/5 to `explain_change`.

Red-team checks rejected malformed spans, unregistered semantic refs, multiple
singleton objectives, and unrecognized analytical language. All successful
material clauses link to a concrete Plan consumer, and both Plan and binding
hashes are deterministic.

Conclusion: E-016 passes for the governed corpus. It does not prove broad Korean
parsing recall or execution parity. The validator remains reusable if a later
LLM replaces the rule proposal adapter. E-017 is the next discriminator.

Regression: E-016 16/16, product 148 pass plus one environment skip, golden
17/17, semantic 10/10, research 58/58. Routing changes: zero.

## E-017 — Existing analytical-path shadow parity

Hypothesis: executable C4 Calls can match the current analytical paths using the
normalized metric evaluator and explicit operator composition, without importing
the new executor from the current engine.

The shadow executor matched level results across all five catalog algebras,
sales change on three axes, operating-profit and period-end inventory change,
distinct regional change, pinned/scoped plan gap, Top-N selection, and explicit
nested drilldown. Rate change remains a safe refusal. The enforced semantic
corpus normalized 10/10 through the shadow compiler/executor.

The first Top-N comparison found a real parity defect: equal absolute changes
were reordered by label, changing the third selected segment. Preserving the
registered dimension order fixed the tie deterministically. A product-to-region
drilldown also failed correctly because region requires offline scope.

Distinct change falsified use of ordinary additive contribution. A provisional
`set_transition@v1` now exposes entrants, exits, and migrations while matching
the current segment/total arithmetic. This is a stronger estimand contract, but
whether it is primitive or lowers to set operations remains unresolved.

Conclusion: representative execution parity is sufficient for metric-level
controlled routing. Drilldown remains shadow because its current provisional
operator performs dynamic child evaluation internally; Ref-capable data
requirements may be needed before that capability routes.

Regression: E-017 15/15, product 163 pass plus one environment skip, current
golden 17/17, current and shadow semantic 10/10, research 58/58. Routing changes:
zero.
