# E-015 intent contract discriminator

## Question

Does groot-cal need a serialized Bound Intent Spec between source-clause
binding and the canonical C4 Plan, or can it compile directly to C4 while
retaining one typed clause-binding record?

Both candidates shared the same closed role/value validation and the same C4
emitter. This intentionally isolated the representation boundary; E-015 did
not test natural-language extraction or production routing.

## Shared record

One versioned `ClauseBindingRecord` contains:

- exact source text and `[start, end]` span;
- whether the clause is material;
- one of `consumed`, `preserved`, `ambiguous`, `unsupported`, or
  `non_semantic`;
- a closed role, role-validated value, and Plan target refs;
- a reason for ambiguity, unsupported meaning, or non-semantic text.

Successful compilation permits no unresolved material clause. Ambiguity returns
`clarify`; unsupported meaning returns `out_of_domain`. Unknown semantic refs,
dimensions, reducers, objectives, target links, malformed spans, invalid rank
parameters, and implicit selection among multiple objectives fail closed.

## Same corpus

Twelve annotated cases cover subject, reducer, explicit comparison and year,
filter, breakdown, ranking/limit, output restriction, multi-metric divergence,
nested diagnosis, ambiguity, and unsupported objectives. They include all nine
counterexamples required by `intent_compiler_plan.md`.

| Measure | Bound Intent Spec | Direct C4 Plan + record |
|---|---:|---:|
| Successful cases | 7 | 7 |
| Byte-identical C4 Plans | 7/7 | 7/7 |
| Identical refusal/clarify outcomes | 5/5 | 5/5 |
| Additional serialized contract types | 1 | 0 |
| Additional intermediate bytes | 2,646 | 0 |
| Bound values duplicated outside the record | 34 | 0 |
| Additional cross-representation consistency checks | 1 | 0 |
| Conceptual source-to-Plan hops | 3 | 2 |

The shared emitter makes Plan parity expected, not an independent executor
proof. The material result is that the extra representation improved neither
fidelity nor clause-local validation on this corpus while introducing a new
inconsistent-state attack (`record.reducer != BoundIntent.reducer`).

## Counterexample discovered during the experiment

The first emitter draft allowed multiple analytical-objective bindings and
used the first. That would reproduce the silent-substitution defect inside a
typed compiler. The corrected shared validator rejects multiple singleton
objectives unless an explicit registered composition consumes all of them.

## Decision

Select **direct C4 Plan plus the typed clause-binding record** for E-016. Reject
a permanent Bound Intent Spec because it duplicates Plan-relevant values and
creates a consistency boundary without demonstrated fidelity or error-quality
benefit.

This does not permit a free-form record. E-016 must productionize the record as
a closed tagged contract, resolve values only through semantic/operator
registries, and link successful clauses to concrete Call inputs, Calls,
outputs, or preserved constraints.

Revisit the rejected representation only if E-016 finds a concrete operation
that must consume a stable intent object independently of C4 and cannot use the
binding record or Plan without duplicating operator semantics.

Regression after the decision: E-015 18/18, full research 58/58, product 133
discovered with 132 pass and one environment skip, golden 17/17, and semantic
10/10. Production analytical routing remains unchanged.
