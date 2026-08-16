# E-013 normalized metric evaluation comparison

## Scope

E-013 is a shadow execution experiment. `engine.run_question`, both current
pipelines, kernels, runtime, and public payloads remain unchanged. The new
`metric_evaluator` is invoked only by parity tests.

## Successful level parity

| Metric | Nominal type | Aggregation strategy | Legacy operator | Value |
|---|---|---|---|---:|
| commerce.net_sales | amount | sum | metric_level | 3,860 |
| commerce.net_sales, online | amount | sum | metric_level | 1,580 |
| finance.operating_profit | amount | sum | metric_level | 20 |
| insurance.loss_ratio | rate | denominator_weighted_mean | rate_level | 0.66 |
| operations.inventory_on_hand | balance | semi_additive:last | metric_level | 190 |
| growth.active_customers | distinct | entity cardinality | distinct_level | 5 |
| commerce.order_count fixture | count | sum | metric_level | 22 |

The normalized route emits one `MetricScalar` shape for all rows: metric ref,
Slice, value, unit, aggregation expression/components, checks, provenance, and
a `data_confirmed` label ceiling. Exact value, scope, unit, input snapshot,
metric ref, semantic source, and `as_of` parity passed for all six catalog query
cases. The count fixture also matched the existing typed kernel.

## Counterexamples and differences

- A duplicate numerator/denominator binding is accepted by the current rate
  path and produces `1.0`; the shadow evaluator rejects it with
  `field_binding_unique`. This is the intended canonical correction, but the
  live route remains unfixed until migration.
- Negative rate inputs, null distinct IDs, and zero denominators preserve the
  current status/check behavior.
- `type=balance` combined with `aggregation_rule=sum` is rejected by both paths.
  The current path uses a balance-specific branch; the shadow path uses the
  selected strategy's declarative type compatibility check.
- Unknown aggregation rules, unknown scope, missing periods, missing fields,
  and duplicate Slice predicates fail as tagged union variants.
- Current successful results still use incompatible `value_u`/`value` fields
  and heterogeneous label maps. E-013 does not adapt the reporter, so Increment
  2's full exit gate is not yet met.

## Branch/coupling measurement

The shadow evaluator contains zero domain metric IDs and no per-type arithmetic
branch. Four registered strategies own the arithmetic. `metric.type` appears
only in generic descriptor validation and each strategy's declared admissible
type tuple. Amount and count exercise the same `sum` implementation.

This supports the `evaluate_metric` collapse for scalar evaluation. It does not
yet prove period-end correctness over daily snapshots, multi-period reducers,
derived expressions, contribution analysis, or reporter migration.

## Historical status note

E-014 later closed the live duplicate-binding gap and moved all legacy result
shape interpretation to one read-only adapter. The comparison above records the
state at the end of E-013 and is intentionally retained as historical evidence.
