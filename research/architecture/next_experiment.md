# Next experiment

## E-020 — Demo entry point: intent compiler → routed executor

Connect the E-016 clause-binding intent compiler to the routed C4 executor
behind an explicit CLI mode, so a Korean question can be observed end to end:
clause binding ledger → compiled Plan → execution record → evidence-bounded
result → rendered report. This is the closeout increment for the demo, not a
new capability routing gate.

1. Add an opt-in `--route c4` / `--show-plan` mode to the CLI. The default
   invocation stays byte-identical to the current route.
2. In demo mode, compile the question with `compile_shadow_intent`; execute
   only plans whose capability is routed (level, period change); answer
   clarify / out_of_domain fail-closed for everything else, naming the
   unrouted capability instead of substituting a neighbor.
3. Render the binding ledger (which clause bound to which reference, what was
   not consumed), the Call DAG, budgets/gates/provenance, the normalized
   result view, and the report labels in that order.
4. Gate: the governed corpus adversarial 9/9 (4 lossless, 5 fail-closed) and
   change paraphrases 5/5 reproduce through the demo CLI; current-route
   defaults unchanged; all standing gates stay green.

## Discriminating risks

- The intent compiler emits plans the Query Spec route never produces
  (ranking, drilldown, multi-metric). The demo must refuse or clarify these
  without executing shadow-only capabilities.
- Intent-compiled change plans and Query-Spec-compiled change plans must agree
  on routed capabilities — any divergence is a compiler fidelity finding.

## Sequenced work after E-020

Broader Korean recall with an LLM proposal adapter over the clause-binding
contract (the C2′ experiment), then drilldown's dynamic Slice decision with
failure-isolation semantics (unresolved #19), then plan comparison routing.
