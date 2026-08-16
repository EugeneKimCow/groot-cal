# E-016 shadow intent compiler result

Date: 2026-08-16

## Question

Can direct C4 compilation plus one closed source-clause binding record preserve
real governed Korean intent without silently substituting a neighboring analysis?

## Implementation

- `slice/clause_binding.py` owns the versioned record, tagged role/value union,
  exact source spans, deterministic serialization, and Plan-consumer validation.
- `schemas/source-clause-bindings-v1.schema.json` publishes the wire boundary.
- `slice/shadow_intent.py` inventories the governed Korean corpus, compiles
  successful bindings directly to C4 Calls, and returns clause-local `clarify`
  or `out_of_domain` outcomes otherwise.
- `slice/shadow_registry.py` now registers the shadow contracts required by the
  emitted contribution, ranking, alignment, and drilldown Calls. Registration
  does not provide execution or change production routing.

The adapter proposes bindings only. The binding validator and operator/semantic
registries remain authoritative. Unrecognized analytical text becomes an
`unsupported` material clause; it is not classified as discourse.

## Required adversarial gate

| Group | Result |
|---|---:|
| Required adversarial questions | 9/9 accounted |
| Supported Plans | 4 |
| Explicit safe refusals | 5 |
| Silent substitutions | 0 |

Supported Plans preserve the offline filter plus region breakdown, top-three
product-category rank plus `only`, explicit 2025 period, and two-metric
divergence composition. The compiler refuses average inventory on the registered
monthly point-in-time source, unregistered inventory turnover, acceleration,
outlier sensitivity, and cross-axis concentration.

The five existing change paraphrases all produce successful
`explain_change` Plans. Group-specific results remain separate from the nine-case
adversarial count.

## Contract evidence

- every successful material clause has an exact span and at least one concrete
  Call input, Call, or Plan metadata consumer;
- resolved roles use a closed tagged value shape;
- malformed spans, unregistered metric refs, and multiple singleton analytical
  objectives fail deterministic validation;
- Plan and binding serialization and hashes are repeatable;
- all successful operator and metric refs are registered;
- `operation_family` is derived from emitted Calls and is not execution dispatch;
- `engine.run_question` imports no E-016 module and its outputs remain unchanged.

## Regression

- product: 149 discovered, 148 passed and one environment Seatbelt skip;
- golden: 17/17;
- enforced semantic: 10/10;
- research: 58/58.

## Qualification

This proves the fidelity boundary on the governed corpus, not broad Korean NLP
coverage. The deterministic adapter is deliberately conservative. A future LLM
proposal adapter may improve recall, but it must emit the same closed record and
cannot bypass deterministic validation. Real execution parity remains E-017.

## Decision

E-016 passes its shadow intent-fidelity gate. Proceed to E-017 existing-path
shadow execution parity. Production routing remains blocked.
