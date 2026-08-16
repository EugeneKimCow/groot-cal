# groot-cal pilot hypotheses v1

## 1. Pilot objective

groot-cal은 유통 매출 분석기를 제품화하기 위한 저장소가 아니라, 연산을 포함한 질의를
받은 agent를 위한 semantic layer의 경계를 검증하는 pilot이다. 검증할 전체 흐름은 다음과
같다.

```
질의 해석 → 대상 식별·조회 → admissible 연산자 선별 → 연산 → 선택적 저장 → 보고
```

semantic layer는 이 흐름의 전략을 대신 결정하지 않는다. 대신 단계 사이에서 보존되어야
하는 의미와 실행 불변조건을 제공한다.

## 2. Primary hypotheses

### H1 — vocabulary generality

현재 발견한 공통 어휘가 수학적 성질이 다른 지표에도 유지된다.

- metric identity, version, grain, scope, comparison basis
- aggregation rule과 decomposition identity
- operator precondition, post-condition, output type
- `result | out_of_domain | suspended | budget_exhausted`
- provenance, assumption ledger, evidence grade, label ceiling

반증 조건: 새 지표를 추가할 때마다 기존 필드의 의미를 바꾸거나, 지표 이름을 검사하는
kernel 분기, 도메인별 최상위 객체가 반복해서 필요하다.

### H2 — enforcement effectiveness

semantic layer를 설명문으로 제공하는 것보다 실행 계약으로 강제할 때 agent의 잘못된
조회·연산·저장·서술이 감소한다.

반증 조건: 강제형 조건에서도 오류율이 줄지 않거나, 정상 질의의 완료율이 과도하게
하락하여 순효과가 없다.

## 3. Evaluation conditions

- **C0 Raw**: 원시 조회·계산 도구만 제공
- **C1 Advisory**: semantic 문서와 레지스트리를 제공하되 호출은 자유
- **C2 Enforced**: Query Spec, admissibility, gate, budget, Result Envelope를 실행 경로에서 강제

핵심 비교는 C1 대 C2다. C0 대 C1은 어휘를 알려주는 효과, C1 대 C2는 실행 계약의
추가 효과를 측정한다.

## 4. Planned challenge metrics

| 순서 | 지표 | 수학적 성질 | 주로 흔드는 가설 |
|---|---|---|---|
| A1 | 영업이익 | signed amount | 부호, 0 통과, 기여율 |
| A2 | 보험 손해율 | rate | 분자·분모 lineage, 가중 집계 |
| A3 | 재고 잔액 | balance | 시간 비가산, 시점 의미 |
| A4 | 활성 고객 수 | distinct | 차원 비가산, entity functional |

온보딩 변경은 `instance-only`, `schema-extension`, `semantic-revision`, `kernel-change`,
`domain-exception`으로 분류한다. 공통 kernel 수정 없이 등록만으로 수용되는 비율이 H1의
주요 관측치다.

## 5. Current increment

첫 increment는 현재 매출 사례에서 H2를 시험할 최소 실행 기반을 만든다.

1. 자연어 해석 결과를 Query Spec으로 물화한다.
2. scope·metric version·comparison을 이후 호출에 자동 전파한다.
3. 캘린더 경계와 입력 가용성을 검증한다.
4. 탐색 예산을 호출 전에 강제한다.
5. operator 선택과 기계적 제외를 execution record에 분리 기록한다.

