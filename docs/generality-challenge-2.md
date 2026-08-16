# Generality challenge 2 — balance와 distinct

## 1. 목적

amount와 rate에서 관찰한 metric type·binding·operator contract가 시간 비가산 balance와
차원 비가산 distinct에서도 유지되는지 반증한다. 사례는 월말 재고 잔액과 활성 고객 수다.

## 2. 결과

### 재고 잔액

- `balance`, `additive_across_time:false`, `semi_additive:last`, `period_end`가 시간 의미를
  실행 전에 구속한다.
- 6월 말 180개에서 7월 말 190개로 10개 증가했다. 창고별 기여는 서울 +20개,
  부산 -10개다.
- `aggregation_rule:sum`으로 바꾸면 `balance_time_semantics`가 실행을 거부한다.
- 기존 `contrib_decomp`를 재사용하되 balance의 시점 의미 gate를 추가했다.

### 활성 고객 수

- 원천 행 수가 아니라 `bindings.entity_id_field`의 distinct set을 센다. 중복 관측은 한 번만
  포함된다.
- 6월 3명에서 7월 5명으로 2명 증가했고 서울·부산 기여는 각각 +1명이다.
- 분해 차원은 `(dimension.entity_functional[entity_type] == true)`일 때만 허용된다.
- 선언과 달리 같은 월·entity가 복수 차원값을 가지면 `entity_functional_runtime`이 거부한다.
- distinct는 가법 amount와 estimand가 다르므로 별도 `distinct_decomp`로 등록했다.

## 3. 공통성 판정

- metric id 기반 kernel 분기: 0건
- domain exception: 0건
- 공통 재사용: Query Spec, Result Envelope, runtime budget, registry admissibility,
  provenance, field binding, 합 타입 실패
- 신규 의미: balance 시간 gate, distinct entity binding과 functional-dimension gate

네 metric type(amount, rate, balance, distinct)이 실행 경로에 올랐으므로 canonical boundary의
“서로 다른 수학적 성질 세 종류” 조건은 충족한다. 후속 H2 wave v4에서 advisory-only의
binding·산술·provenance 오류가 enforced 실행 경로에서 제거된 것도 확인했다. 따라서
type-directed admissibility와 명시적 field binding 계약은 canonical로 승격한다. 현재 type
enum이 완전한 닫힌 집합이라는 주장은 계속 provisional이다.

## 4. 발견된 다음 경계

“어느 지역에서”처럼 사용자가 요청한 분해 축을 Query Spec에 물화하는 필드가 아직 없다.
현재 distinct fixture에는 admissible 차원이 하나뿐이라 결과가 결정되지만, 복수 admissible 차원이
생기면 question signature와 별도로 `breakdown_dimensions` 또는 동등한 binding이 필요하다.

또한 distinct 지역 기여는 두 시점의 지역별 distinct count 차이다. 고객 이동 자체를 별도 항으로
분리하는 migration decomposition은 다른 estimand이며 자동으로 같은 연산자에 넣지 않는다.
