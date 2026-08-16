# Canonical boundary v1

이 문서는 pilot에서 무엇을 정본 후보로 다루고 무엇을 아직 고정하지 않는지 기록한다.
`canonical`은 널리 쓰인다는 뜻이 아니라, 실행 단계가 참조해야 하는 단일 의미 계약이라는
뜻이다.

## 1. Status classes

| 상태 | 의미 | 변경 규칙 |
|---|---|---|
| canonical | 실행이 의존하는 의미 불변조건 | 변경 시 schema version과 ADR 필요 |
| provisional | 이종 지표로 일반성 검증 중 | 반례에 따라 확장·축소 가능 |
| domain pack | 특정 업무 영역의 등록 자료 | 공통 kernel 의미를 변경할 수 없음 |
| exemplar | 실험·교육용 전략과 사례 | 실행의 단일 기준점으로 사용 금지 |
| deprecated | 대체됐으나 계보 보존 | 신규 실행에서 참조 금지 |

## 2. Current classification

### Canonical execution contracts

- Query Spec에서 확정된 metric, version, scope, comparison, `as_of`는 전 실행에 구속된다.
- operator는 합 타입 Result Envelope를 반환한다.
- design fact 위반은 `out_of_domain`, 입력 부재는 `suspended`로 구분한다.
- post-condition 실패 결과는 정상 결과로 승격할 수 없다.
- 보고 수치와 주장은 provenance와 label ceiling을 넘어설 수 없다.
- 실행 예산은 사후 자기보고가 아니라 호출 전 상한이다.
- metric의 연산 의미는 metric ID 분기가 아니라 descriptor의 `type`, `properties`,
  `bindings`와 operator admissibility로 결정한다.
- 원천 필드명은 `bindings`로 명시하며, 실행 전에 존재성과 중복 binding을 검사한다.

### Provisional vocabulary

- metric type 열거의 완전성(새 수학적 성질을 닫힌 집합 밖에 추가할 가능성)
- question signature의 축
- design fact / deterministic data check / distributional assumption 삼분류
- evidence grade 세분화와 exploration budget 축
- 저장 결과의 승격·staleness 규칙

metric type 기반 dispatch와 명시적 field binding 계약은 amount·rate·balance·distinct 네
성질에서 재사용됐고 H2 실행 강제 비교도 통과해 canonical execution contract로 승격했다.
다만 현재 type enum 자체가 모든 미래 지표를 포괄한다는 닫힌 집합 주장은 하지 않는다.

### Domain pack

- 유통 매출 metric과 channel/category/customer_type/region
- 영업이익 signed amount descriptor와 business_unit fixture
- 보험 손해율 rate descriptor와 numerator/denominator binding
- 월말 재고 balance descriptor와 warehouse fixture
- 활성 고객 distinct descriptor와 entity-functional region fixture
- 온라인 주문 건수와 VRM 구현
- 계획 vintage 저장소와 이벤트 레지스트리
- 유통 데이터 품질 검사기의 구체적 설정

### Exemplar

- 최대 기여 축부터 보는 드릴다운 전략
- 오프라인×권역, 온라인 신규×카테고리 같은 고정 경로
- CFO 메모 및 가상 이벤트 시나리오
- `exemplars-v0.md`의 기대 수치

## 3. Source-of-truth rule

- 아키텍처 경계는 `archi-2.md`가 정본이다.
- 기계 실행 객체의 필드와 불변조건은 `schemas/`와 실행 코드가 정본이다.
- 실행 가능한 지표 목록과 domain pack profile은 `slice/metric_catalog.json`이 기준이다.
- materialized result 필드와 판정 불변조건은 `schemas/stored-result-v1.schema.json`과
  `slice/result_store.py`가 기준이다. 외부 저장소·보존 정책은 아직 provisional이다.
- Report Spec v1, `executive_memo` 구조화 출력과 lint 불변조건은 `schemas/report-spec-v1.schema.json`,
  `schemas/structured-report-v1.schema.json`, `slice/reporter.py`가 실행 기준이다. 다른 장르와
  최종 자연어 렌더링은 아직 `report-contract-v0.md`의 후속 범위다.
- `operator-registry-v1.md`는 현재 provisional registry 설계다. 실행 가능한 registry가
  도입되면 문서는 그것에서 생성하거나 일치 검사를 받아야 한다.
- 과거 측정 bundle은 동결 산출물이며 최신 schema의 정본이 아니다.

## 4. Promotion rule

provisional 개념은 다음 조건을 모두 만족할 때 canonical 후보가 된다.

1. 수학적 성질이 다른 지표 세 종류 이상에서 재사용된다.
2. agent 오류를 줄이거나 필수 provenance를 제공한다.
3. 실행 가능한 불변조건 또는 명확한 정보 계약으로 표현된다.
4. 특정 도메인 이름에 의존하지 않는다.
5. 실패 상태와 반례가 테스트로 고정된다.

## 5. Promotion record — H2 wave v4

2026-08-14의 H2 정식 wave는 C0 raw와 C1 advisory를 같은 10개 사례에서 각 5회 실행했다.
C1은 C0보다 resolution·binding·selection·execution을 개선했지만, 적용 가능한 persistence는
0/35에 머물렀다. C2 enforced는 10개 결정론적 사례에서 resolution 10/10, 적용 가능한
binding·selection·execution·persistence 7/7, reporting 5/5를 통과했다.

따라서 설명문만으로는 남은 binding·산술·provenance 오류가 실행 계약에서 제거된다는 H2를
이 pilot 범위에서 지지한다. 이 근거로 type-directed admissibility와 field binding의 존재성·
구속 규칙을 canonical로 승격한다. 모델 일반 효과나 현재 type enum의 완전성은 이 결과가
보장하지 않는다. 기계 판독 집계는 `eval/semantic-layer-v1/wave-v4-final.json`에 고정한다.
