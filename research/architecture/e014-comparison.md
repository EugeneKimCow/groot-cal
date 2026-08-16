# E-014 normalized result boundary comparison

## Scope

E-014 changes result consumption, not analytical routing. Current commerce and
typed kernels still produce their public legacy payloads. A central read-only
adapter presents one normalized view to the reporter, CLI, and materialization
boundary.

## Normalized view

- level `value_u` and `value` become one scalar value, unit, and source ref;
- contribution/plan `delta_u`, `gap_u`, and `delta` become one change value;
- segment changes become normalized values and source refs;
- operator, provenance, and result type are required metadata;
- heterogeneous legacy label maps become role-based label capabilities.

The same adapter accepts the strict E-013 `MetricScalar` Result Envelope. It
never mutates the source payload and fails closed on ambiguous numeric shapes,
invalid numbers, or missing evidence metadata.

## Consumer result

- Reporter and CLI no longer probe legacy scalar/change field alternatives.
- Materialization uses normalized metadata but stores the original payload and
  preserves its identity.
- Report labels are selected from the result's declared evidence ceiling.
- Lint rule `LBL02` independently rejects claims that exceed that ceiling.
- Malformed successful results fail closed instead of producing a report.

## Canonical contract correction

The live typed kernel now rejects duplicate rate bindings with the explicit
`field_binding_unique` check, closing a gap previously enforced only by the
shadow evaluator.

## Remaining migration debt

Legacy Korean-keyed ceiling maps are interpreted only inside the adapter.
Strict envelopes use closed capability values. This compatibility branch can
be deleted together with the old payload producers.

E-014 added 16 regression cases. The product suite discovers 133 tests: 132
pass and one environment-dependent Seatbelt test is skipped. Golden remains
17/17 and semantic remains 10/10.
