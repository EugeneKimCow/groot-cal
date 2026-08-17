# E-025 rank + drilldown demo routing

Date: 2026-08-17

## Question

Can ranking and explicit nested drilldown leave shadow — executing on the
demo/UI path — once their two recorded debts are resolved: the #19 failure-
isolation question and drilldown's hidden child data acquisition?

## Decisions on the two debts

1. **#19 does not block these capabilities.** Rank and drilldown plans are
   sequential dependency chains (evaluate → contribution → rank → drilldown);
   stop-on-first-failure is the *correct* semantics for a chain. #19 remains
   open where it always was: independent sibling branches (multi-axis change),
   still indiscriminable on current fixtures.
2. **Drilldown's hidden children are now confessed, not redesigned.** The
   provisional operator keeps performing child evaluations, but each child now
   consumes `operator_calls` budget *with a pre-charge check* and appears in
   the execution record as `<call_id>.before/.after`. Starving the budget by
   exactly the child count closes the whole plan as `budget_exhausted`. The
   target state — explicit Ref-capable dynamic Slice Calls — remains the
   registered design debt; what E-025 removes is the *unaccounted* part.

## Evidence

- rank: "상위 3개 제품군" executes on the demo path; ranked order equals the
  legacy contribution order (가전 −200, 생활용품 −140, 식품 −80).
- drilldown: dominant-category selection then customer-type decomposition
  executes with `parent_scope` displayed; totals and segment maps equal the
  legacy kernel's scoped decomposition (−200; 기존 −119, 신규 −81).
- budget confession: top-level calls + 2 children accounted (7/10 on the
  drilldown plan); starved budget → `budget_exhausted`, child call recorded.
- invalid region drilldown still fails closed at the semantic scope gate.
- unrouted remainder: `plan_gap@v1`, `align_metrics@v1` — still refused by
  name (E-020 gates updated to pin the new boundary).

## Regression

E-025 tests 5/5; production 229 on both interpreters; golden 17/17; semantic
10/10; C2′ rule baseline 10/10.

## Decision

Rank and drilldown are demo-routed. The demo now answers "상위 N"과 "그 안에서
다시 분해" 요청을 실행하고, 여전히 plan 비교·다지표 정렬은 이름을 밝혀
거부한다.
