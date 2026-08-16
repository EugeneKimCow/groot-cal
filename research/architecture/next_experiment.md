# Next experiment

## E-019 — Controlled period-delta routing

Route `explain_change`'s comparison root (simple period delta plus the current
per-axis additive contribution outputs) through the C4 compiler/executor behind
the same reversible selector, preserving the public bundle boundary validated
in E-018.

1. Extend the routed selector to `explain_change` for metrics whose change
   path is additive contribution or set transition; keep rate change a refusal
   on both routes.
2. Adapt multi-output C4 results (per-axis contribution, set transition) to the
   public `contrib:<dim>` / `distinct:<dim>` result keys through one adapter,
   preserving change values, segment identities, and declared before/after
   evidence without legacy operator spelling.
3. Run the sales three-axis change, typed operating-profit/inventory/distinct
   changes, scoped changes, missing comparison month, vintage clarification,
   reporting, materialization, and provenance through both selectors.
4. Keep the H2 enforced corpus 10/10 as a routing exit gate.
5. Refuse plan comparison and drilldown on the routed selector until their own
   gates pass.

## Discriminating risks

- The current route emits one result key per axis from hardcoded decomposition
  identities; the C4 plan emits explicit Calls. Key-mapping is where silent
  reordering or dropped axes would hide.
- Reporter dominance selection (`largest_absolute_segment_contribution`) must
  select the same axis on both routes.
- Distinct change carries entity sets for set transition; the public boundary
  must not leak raw entity identifiers beyond what the current route exposes.

## Sequenced work after E-019

Additive contribution ranking/limit (E-020 target for the demo), then explicit
nested drilldown (requires the dynamic Slice decision), plan comparison, and
registered non-additive operators. After the demo increment, revisit drilldown
data-requirement transparency before any further routing.
