# 현재 최선의 아키텍처

> 번역 주: 이 문서는 `current_best.md`의 한국어 번역본이다. 두 문서의
> 내용이 다를 경우 영문 원문을 기준으로 하며, 원문 변경 시 이 번역본도 함께
> 갱신해야 한다.

상태: E-016의 governed shadow intent gate까지 갖춘, 연구상 수렴한 후보이다.
아직 프로덕션 실행 경로로 승인되지는 않았다.

현재 가장 앞선 후보는 압축된 IR 중심 후보 C4이다.

```text
질문
  -> Agent/compiler harness
  -> 바인딩된 intent + semantic reference
  -> typed analytical DAG
       -> logical Data Requirement
       -> backend-neutral data planner -> SQL adapter -> RDBMS
       -> canonical deterministic operator
       -> 등록된 validation/invariant
  -> evidence result
  -> 결과만 소비하는 renderer/reporter
```

세 가지 주요 논리 계약은 다음과 같다.

1. Semantic contract: metric expression, grain, unit, 시간 동작,
   dimension/entity/relationship와 cardinality, calendar/cohort,
   null/allocation 정책, binding, version을 정의한다.
2. Analytical contract: 타입이 지정된 operator 입출력, parameter,
   invariant, failure variant, evidence/label ceiling을 정의한다.
3. Planning contract: 바인딩된 input, 타입이 지정된 node/edge, condition,
   budget, 선택된 output을 정의한다.

Domain pack은 alias, 도메인 semantic instance, plan idiom을 제공한다. 별도의
두 번째 runtime을 제공하지 않는다. Data backend, semantic authority, result
store, report renderer는 이 세 계약을 둘러싼 교체 가능한 port이다.

현재 이 후보가 앞서는 이유는 repository에 없던 계약을 직접 드러내면서도 기존의
가장 강한 자산을 보존하기 때문이다. 다만 다음 이유로 다른 후보에 밀릴 수 있다.
명시적 IR이 범용 workflow language로 비대해질 수 있고, typed metric
expression이 operator와 중복될 수 있으며, governed BI에서는 semantic-heavy
registration이 더 단순할 수 있다. 또한 조건부 진단에 compact DAG 이상의
표현력이 필요할 수도 있다.

이 기록은 프로덕션 실행 경로의 migration을 승인하지 않는다. E-012에서 승인한
범위는 격리된 계약과 shadow compilation뿐이다.

E-003은 현재 다섯 metric을 대상으로 aggregation algebra가 구동하는 단일
`evaluate_metric` node를 지지한다. 단, 바인딩된 단일 기간만 검증했다. E-004는
기존 contribution operator를 재사용하면서 요청된 breakdown과 nested drilldown을
generic Call+Ref 조합으로 표현할 수 있음을 지지한다. 첫 번째 held-out corpus는
semantic 및 validation contract를 확장했지만 두 번째 IR node 종류를 요구하지는
않았다.

현재 가정하는 최소 문법은 다음과 같다.

```text
Plan(version, calls, outputs, limits)
Call(id, operator_ref, inputs, parameters, optional typed guard)
Input = literal | semantic_ref | result_ref | Slice
Slice = time/calendar/cohort + predicates + grain expectation
```

이 문법은 여전히 rate/mix, set transition, distribution, SQL fanout, time
alignment, causal boundary 실험에 의해 반증될 수 있다.

E-005는 operator model을 변경했지만 문법은 변경하지 않았다. Rate/mix에는
명시적인 allocation convention을 가진 도메인 독립적 등록 계약이 필요하다.
Entity transition에는 set identity와 선택적인 functional-dimension migration이
필요하다. 어느 쪽도 도메인 전용 runtime이나 IR node class가 되어서는 안 된다.

E-006은 별도의 logical Data Requirement compiler 경계를 지지한다. Semantic
contract는 source grain과 relationship cardinality를 노출하고, analytical Call은
필요한 value/slice/group을 노출한다. Compiler는 acquisition shape을 선택하고,
backend adapter는 SQL을 생성한다. 명시적 allocation은 estimand parameter이며,
fanout과 reconciliation은 deterministic check이다.

E-007은 시간 의미를 같은 문법 안에 유지한다. Slice는 등록된
calendar/window/cohort를 참조하고 요청한 reducer를 선언하며, semantic/data
contract는 사용 가능한 grain을 명시한다. Alignment는 compilation 중 검사한다.
Period-end balance가 average-daily-balance 질문에 침묵한 채 답해서는 안 된다.

E-011은 검증 대상 slice에서 남아 있던 C3/C4 구현 선택 문제를 해결했다. C4는
wire/runtime 경계의 canonical 형식이다. C3의 명시적 node class는 C4로 즉시
lowering되는 생성형 authoring builder로만 유용하다. 별도의 병렬 논리 아키텍처가
아니다.

E-012는 routing을 변경하지 않고 canonical value contract, 실행 가능한 shadow
registry, Query Spec shadow compiler를 도입했다. 이는 migration seam을 검증한
것이지 execution parity를 검증한 것은 아니다. Binding ledger는 어떤 Call도
소비하지 않은 구조화 clause를 발견할 수 있지만, Query Spec 생성 전에 버려진
자연어 intent는 볼 수 없다. 다음 프로덕션 판별 대상은 현재 다섯 metric type
전체를 처리하는 정규화된 aggregation-algebra 기반 metric evaluator이다.

E-013은 shadow mode에서 이 scalar 판별 실험을 통과했다. 네 aggregation
strategy가 다섯 nominal type을 처리하며, amount와 count는 sum을 공유한다.
Metric type은 선언적 admissibility constraint로 남고 aggregation rule이 산술을
선택한다. 새 후보는 legacy rate 경로가 받아들이는 중복 binding을 거부한다.
다만 reporter/result adaptation, live binding enforcement, finer-grain source의
period-end 동작이 완료되지 않았으므로 routing은 계속 차단되어 있다.

Migration 순서에는 이제 shadow analytical path 확장이나 routing보다 먼저 수행할
명시적인 intent compiler gate가 포함된다. E-015는 별도의 Bound Intent Spec과,
typed clause-binding record를 포함한 direct C4 Plan compilation을 비교했고 E-016은
선택된 계약을 shadow mode로 구현했다. 성공한 Plan은 모든 중요한 자연어 clause의
처리 상태를 설명해야 하며, 지원하지 않는 intent는 인접한 다른 분석으로 대체하지
말고 clarification 또는 fail-closed로 끝나야 한다.

E-014로 Increment 2의 result-consumption 단계가 완료되었다. 삭제 예정인 하나의
read-only adapter가 legacy scalar/change field, segment, provenance, operator
identity, evidence ceiling을 정규화하여 reporter, CLI, materialization에 제공한다.
Public payload와 analytical routing은 바뀌지 않았다. Report label은 이제 result가
선언한 capability에서 선택되며 lint가 ceiling을 넘는 승격을 거부한다. Live typed
operator도 binding uniqueness를 강제한다. 남은 호환 로직은 adapter 한 곳에만
격리되어 있으며 목표 아키텍처의 일부가 아니다. Increment 3은 완료됐으며
Increment 4 / E-017이 활성화된다.

E-015는 이 increment의 최소 intent 경계를 선택했다. 폐쇄형이며 versioned인
source-clause binding record를 C4로 직접 compile하고, 별도의 Bound Intent Spec은
두지 않는다. 12개 공통 사례에서 추가 spec은 fidelity나 error locality를 개선하지
않으면서 34개 값을 중복하고 새로운 consistency 경계를 만들었다. Binding record는
free-form metadata가 아니다. Source span, materiality, 명시적 outcome state,
role-validated value, Plan consumer link를 유지한다. E-016은 governed Korean
corpus에서 이 경계를 검증했다. Routing은 바뀌지 않았고 E-017 execution parity까지
계속 차단되어 있다.

E-016은 governed Korean corpus에서 이 경계를 구현하고 통과했다. 필수 적대 질문
9개는 손실 없는 Plan 4개와 clause-local safe refusal 5개로 모두 처리됐고, 기존 변화
질문 paraphrase는 5/5로 정규화됐다. Exact span, tagged role/value validation, 등록
reference, Plan consumer link, deterministic hash는 proposal adapter 밖에서 강제된다.
`operation_family`는 생성된 Call에서 파생된다. 이는 governed intent fidelity gate를
닫지만 그 자체로 광범위한 한국어 parser recall을 입증하지는 않는다. E-017도
완료됐으며 현재 판별 대상은 E-018 controlled metric-level routing이다.

E-017은 격리된 C4 executor를 추가하고 다섯 metric level algebra 및 대표적인
change, plan, rank, 명시적 drilldown 경로에서 parity를 확보했다. 동률 순위 반례는
등록 dimension 순서를 보존하도록 수정됐다. Distinct change는 entrant, exit,
migration을 가법 산술로 축약하지 않도록 잠정 `set_transition@v1`을 사용한다.
Shadow semantic corpus는 10/10이다. 이 결과는 E-018의 controlled metric-level
routing만 지지한다. 다른 capability는 shadow에 남으며 drilldown의 dynamic data
requirement 투명성은 아직 해결되지 않았다.

E-018은 controlled metric-level routing을 완료했다. `engine.run_question`에
기본값이 현행 경로를 보존하는 가역 route selector가 추가됐다. `c4_level`은
metric level만 C4 compiler/executor로 실행하고 다른 family는 전부 명시적으로
거부하며, public bundle 경계에는 legacy 철자를 사칭하지 않는 선언된 identity의
canonical Result Envelope를 노출한다. 값·단위·label·실패 위치·보고·
materialization·provenance parity가 성립했고, H2 enforced corpus는 라우팅된
selector에서 10/10로 이후 모든 capability의 상설 exit gate가 됐다. 유일한
반례는 예측대로 public 경계에서 나왔다: domain pack의 미검증 가정 ledger가
누락되어 선언된 불확실성이 조용히 약해지는 문제였고, 이제 모든 경로가 보존한다.
다음 판별 대상은 period delta + additive contribution routing(E-019)이다.

E-019는 controlled routing을 period change로 확장했다. `explain_change`는 현행
공개 경계와 동형인 축별 contribution/set-transition DAG로 컴파일되고, commerce
이벤트 idiom은 명시적 등록 Call(`event_overlap_scan@v1`)이 됐으며, adapter는
canonical Attribution change view를 배웠다. 값·세그먼트·백분율·이벤트 증거·
보고서·materialization parity가 성립했다. 지배축 자동 드릴다운과 온라인 VRM
산출물은 라우팅된 경계에서 의도적으로 부재하다 — synthesis §10이 제거한 숨은
전략이며, 테스트가 이를 선언된 차이로 고정한다. 추가 라우팅 전 미해결: DAG
실패 격리 의미론, share 억제 규범의 소유권, label capability의 소유권. 시연
increment는 라우팅된 level + change 위에서 진행하고, plan comparison·drilldown·
비가법 연산자는 게이트 뒤에 남는다.

E-020은 시연 increment를 닫았다: 한국어 질의가 opt-in CLI 모드 뒤에서
clause-binding compiler와 라우팅된 executor를 거쳐 끝까지 실행되고, 바인딩
대장·Call DAG·실행 기록·증거 한정 결과가 계층 렌더링된다. 미라우팅
capability는 이름을 밝혀 거부되며 결코 대체되지 않는다. 두 compiler(intent와
Query Spec)는 같은 executor에서 같은 수치로 만난다. 다음 판별 대상은
clause-binding 계약 위의 LLM proposal adapter(C2′)이고, rank/drilldown
라우팅은 미해결 #19 뒤에 있다.

E-021은 같은 계약 뒤에서 proposal 슬롯에 local LLM을 넣었다. 마무리
seam(finalize_clause_record)은 이제 제안자 독립이며, 결정론 가드 3종(원문
그대로의 span 복원, 상대 월 재계산, 겹침 선착순)이 해석 권위를 모델 밖에
둔다. 두 local 모델 실측에서 침묵 치환 0·오답 수치 0 — 모든 제안 오류는
거부 또는 검증된 거친 답이 됐고, 모델 크기는 recall만 샀다. 다음 판별 대상은
C2′ 증분 2(advisory 대 계약-아래-LLM 비교)다.

E-024는 H2의 원 비교를 닫았다: C2′(계약 아래서 해석하는 LLM)가 고정 H2
corpus의 분석 구간에서 로컬 14B 모델로 50/50 — 결정론 enforced 상한 — 에
도달했고, frontier advisory agent는 58% 이하였다. 측정 자체가 시스템을 두 번
수리했다: 채점기 오탐(plan_gap의 subject 소비)과 진짜 별칭 충실성 공백(증거
없는 subject 바인딩은 이제 결정론적으로 반문 강등). 효과를 나르는 것은 모델
크기가 아니라 강제다. 다음 판별 대상: 광역 recall(#16), pushdown 권위(#24),
rank/drilldown 라우팅(#19).
