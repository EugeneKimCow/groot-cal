# Counterexample register

## CE-001 — Requested breakdown is absent from Query Spec

“Which warehouse drove the inventory increase?” and “which region drove active
customer growth?” happen to work only because their fixtures expose one useful
dimension. With two admissible dimensions, current planning cannot preserve the
requested breakdown.

Targets: C0 and any IR without explicit breakdown binding.

## CE-002 — Offset with near-zero total

“Total sales were flat; which rising and falling segments offset?” must not be
stopped by a total-change threshold or ranked only by share of net change.

Targets: contribution result contracts and diagnosis templates.

## CE-003 — Rate change attribution

Loss ratio rises because claim severity, claim frequency, and portfolio mix
change. Current typed path returns out-of-domain for all rate change analysis.

Targets: nominal type dispatch and primitive taxonomy.

## CE-004 — Migrating distinct entities

Active customers move between regions while total distinct count is unchanged.
Period-wise distinct deltas by region do not identify entrants, exits, or
migrations and may be misread as additive contributions.

Targets: `distinct_decomp` estimand and generic decomposition claims.

## CE-005 — Multi-metric derived question

“Did revenue rise because units increased or average selling price increased?”
requires relationships among revenue, quantity, and price. Current resolver
rejects multiple metrics and Query Spec has one subject.

Targets: one-subject semantics and domain-specific VRM.

## CE-006 — Hierarchical breakdown and double counting

“Drill category → brand → SKU” must preserve hierarchy and avoid treating
levels as independent MECE axes. Current dimensions are flat closed lists.

Targets: thin semantics that omit relationships/grain.

## CE-007 — Conditional nested diagnosis

“If delay is concentrated in one supplier, drill by lane; otherwise test plant
trend.” requires typed predicates and branches based on prior results.

Targets: flat operator lists and over-static DAGs.

## CE-008 — Counterfactual identification

“Without supplier delay, would service level still have fallen?” cannot be
answered by arithmetic decomposition alone. The architecture must represent
required identification assumptions or refuse without inventing a cause layer.

Targets: diagnosis-as-arithmetic and unrestricted counterfactual operators.

## CE-009 — Same measure, two time semantics

Inventory may ask for period-end balance or average daily inventory. A nominal
`balance` type alone cannot choose the time reducer; the query and metric
expression must bind the estimand.

Targets: type-only dispatch.

## CE-010 — Backend-neutral ratio pushdown

Computing `SUM(numerator)/SUM(denominator)` can be pushed to SQL, while taking
the average of row ratios is wrong. A data planner must preserve the semantic
aggregation expression across backend lowering.

Targets: any SQL generator that receives only field names.

## CE-011 — Report and staleness are not analytical math

Forcing “write a memo” or “is this result stale?” into the same operator grammar
may inflate the analytical IR. Excluding them entirely may fragment the agent
harness.

Targets: boundaries around planning, reporting, and result management.

## CE-012 — Metric capability collision

Two metrics can both be nonnegative, dimension-additive, and time-last, yet one
may represent a snapshot and another a slowly changing derived state with a
different valid comparison. Structural capabilities may be insufficient unless
the estimand expression remains explicit.

Targets: H-003 and H-007.

## CE-013 — Many-to-many join fanout

Joining orders to multi-valued product tags can duplicate revenue. Metric grain
and dimension names are insufficient without relationship cardinality,
allocation semantics, and a fanout check.

Targets: an overly thin semantic contract and backend lowering.

## CE-014 — Fiscal, rolling, and cohort time scopes

“Fiscal Q2,” “rolling 28 days,” and “same-customer cohort” cannot be reduced to
one `YYYY-MM` focal period. Time windows, calendars, and entity-set references
must remain distinct enough to preserve estimands.

Targets: scalar comparison grammar and generic slice proposals.

## CE-015 — Cross-axis scores are not automatically comparable

The current largest-driver rule compares the largest absolute segment delta
from dimensions with different cardinalities and overlapping projections.
That is a deterministic heuristic, not a canonical independent-effect score.

Targets: hardcoded dominant-axis diagnosis and generic multi-dimensional claims.

## CE-016 — Silent metric-modifier loss

“Average inventory” currently returns period-end inventory, and “inventory
turnover” can bind the inventory alias and return a balance. A plan validator
must prove that modifiers and derived metric expressions were preserved, not
merely that some registered metric was found.

Targets: substring resolution and intent-to-plan fidelity.
