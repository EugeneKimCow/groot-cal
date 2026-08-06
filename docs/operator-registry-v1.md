# 연산자 레지스트리 v1 스키마 초안

> [legacy-notes.md](legacy-notes.md)의 설계 원리(P1~P8)를 적용한 초안. (2026-08 작성)
> **v1.1** — 3개 렌즈(통계 방법론 / 구현 가능성 / 계보 함정 대조)의 적대적 검증을 반영한 수정판.
> 상태: **0단계** — 4개 연산자를 목록으로 등록하며 축을 관찰하는 단계. 문법 확정(1단계)은
> 인스턴스가 쌓인 뒤로 미룬다(조기 추상화 금지).

**v1.1의 핵심 수정** (검증 패널 지적 반영):
- P2를 삼분류로 정련: 설계 사실 / **결정론적 데이터 검증** / 분포 가정 (§3.2)
- 부분함수 원칙을 산문에서 **합 타입(sum type) 반환 스키마**로 (§3.4)
- 술어는 자유 표현식이 아니라 **등록된 검사기(named check registry)** 참조로 (§3.1)
- contrib_decomp의 estimand 이원화(기술적/추론적) — 확률 모형 없는 uncertainty·shrinkage 제거 (§4.1)
- rate 타입의 3부류 분리와 **집계 규칙(aggregation_rule) 술어** 신설 (§1.1)
- VRM을 estimand 축으로 2개 연산자로 분리 (§4.2)
- execution_plan을 LLM 자기보고에서 **런타임 파생 기록**으로; 예산을 사후 계수에서 사전 상한으로 (§5)
- assumption ledger를 참조가 아니라 실재 스키마로 (§5)

---

## 1. 타입 어휘 v1

### 1.1 지표 타입 (measure types) — Mosteller–Tukey 계열

| 타입 | 정의 | 예 | 핵심 성질 |
|---|---|---|---|
| `amount` | 가산적 금액 | 매출, 비용 | 차원 간·기간 간 가산. 부호 주의(순이익은 `sign: any`) |
| `count` | 가산적 건수 | 주문 수, 클레임 건수 | 차원 간·기간 간 가산, `sign: nonnegative` |
| `rate` | 분자·분모가 선언된 비율 | 아래 3부류 참조 | 분자/분모의 지표 참조 필수; **집계는 분모 가중 평균만** |
| `balance` | 시점 스톡 (semi-additive) | 재고, 잔액, 가입자 수 | 차원 간 가산(총재고 = Σ창고별). 시간 축 **sum 금지, avg/min/max/last 허용** |
| `distinct` | 유니크 카운트 | 유니크 고객 수 | 가산성은 (지표 × 차원) 쌍의 속성 — §1.2 entity_functional 참조. `additive_across_time: false` |

**rate의 3부류.** 통계적 성질이 다르므로 술어로 구별한다 (타입 수를 늘리지 않고 술어로 —
격자 곱셈 비용 회피):

| 부류 | 예 | 성질 |
|---|---|---|
| counted fraction | 전환율, 불량률 | `is_counted_fraction: true`, bounded [0,1], 이항 구조 (로짓 변환은 이 부류에만) |
| 금액비 | 손해율 | bounded 없음(1 초과 가능) |
| 평균형 | 객단가 = amount/count | 표본평균 구조 (불확실성 정량화 시 델타법 대상) |

**속성 술어 v1.1:**

```yaml
properties:
  additive_across_dims: bool     # ※ distinct는 (지표, 차원) 쌍 수준에서 판정 (§1.2)
  additive_across_time: bool
  aggregation_rule: sum | denominator_weighted_mean | semi_additive(avg|min|max|last) | non_aggregable
                                 # rate의 차원·시간 집계는 denominator_weighted_mean으로 고정.
                                 # 단순 평균(평균의 평균) 집계는 block — Simpson's paradox 차단
  has_denominator: bool
  is_counted_fraction: bool
  bounded: {lower: number|null, upper: number|null}
  sign: nonnegative | any        # 집중도 지표(HHI/Gini)·로그 분해는 nonnegative 요구
```

### 1.2 차원 타입 (dimension types)

`nominal` / `hierarchical`(카테고리>브랜드>SKU) / `ordinal`(연령대) / `time`(+ `cyclic` 플래그).

**차원별 추가 선언:**

```yaml
dimension:
  name: 거주지역
  type: nominal
  entity_functional:             # 개체 수준 함수적 종속: 고객 1인 = 정확히 한 값
    고객: true                   #   → distinct(유니크 고객 수)의 기여도 분해가 이 차원에서 유효
  # 다치(multi-valued) 차원(예: 구매 카테고리)은 entity_functional: false
  #   → distinct 분해는 out_of_domain
```

**재캐스팅(CLASS 문 원리).** 스키마의 타입은 디폴트. C1 게이트에서 질문 맥락에 따라 재선언
가능(연령: 연속 ↔ '30대' 순서 구간). 재캐스팅 이력은 semantic layer의 일급 기록.

### 1.3 지표 부가 메타데이터 (semantic layer 필수 필드)

```yaml
metric:
  name: 매출
  type: amount
  version: 3                     # 정의 변경 이력 — '지표 정의 동일성' 게이트의 판정 근거
  definition_history: [...]
  decomposition_identities:
    - identity: "매출 = Σ_seg 매출[seg]"
      kind: additive_partition   # ← 항등식 유형이 담당 연산자를 결정
    - identity: "매출 = 고객수 × 구매빈도 × 객단가"
      kind: multiplicative       # v1 정의역 밖 — §4.6 공백 등록부 참조
    - identity: "Δ재고 = 입고 − 출고"
      kind: flow_stock           # balance 변화 진단의 자연스러운 estimand
  generation:                    # データの科学: 생성 과정 메타데이터
    source: 주문 원장
    grain: 주문 라인
    known_biases: [환불 반영 지연 D+3]
  assignment_mechanism: null     # 그룹 비교 시: randomized | targeting_rule
                                 #   | self_selected | policy_cutoff (인과 전통)
```

## 2. 질문 서명 (question signature)

```yaml
question_signature:              # 질문의 속성 (연산자의 요구와 분리)
  external_criterion: present | absent   # 하야시의 제1분류자
  question_type: level | change | composition | distribution
  # enum 확장 규약: 새 값은 기존 값으로 서술 불가능함을 보인 뒤에만 추가 (I~IV 번호 경직화 방지)
```

연산자 쪽 요구는 input_contract의 술어로 표현: `requires_external_criterion: bool`.

**서명은 디스패처가 아니다.** 서명은 admissible 후보 집합을 좁힐 뿐 단일 선택을 결정하지
않는다(예: contrib_decomp와 trend_changepoint 확인형은 같은 서명을 가진다). 후보 중 선택은
LLM 판단이며, 반드시 §5의 `operators_considered`에 기록된다. 비교 기저 축(전기 대비/추세선
대비)이 이 둘을 구분하는 축임 → 1단계 인수분해 재료.

## 3. 연산자 등록 스키마

### 3.1 술어와 검사기 — named check registry

v1에서는 표현식 언어를 만들지 않는다(YAGNI). 모든 술어는 **등록된 검사기의 id 참조**다:

```yaml
check:
  id: mutually_exclusive_exhaustive_partition
  checker: machine               # machine | human | llm_judgment — 기계 판정 아님을 데이터로 노출
  impl: "SQL: Σ세그먼트 지표 == 전체 지표, NULL/미분류 행 검출"
```

- 검사기 없는 자유 문자열 술어는 **등록 단계에서 거부**된다.
- `checker: llm_judgment`는 허용되지만 그 사실이 기록되고, 해당 검사에 근거한 출력은
  '컨설턴트 판단' 라벨 상한을 받는다. (admissibility가 LLM의 자기 판단으로 퇴행하는 것을
  구조적으로 방지 — 1980년대 전문가 시스템의 교훈.)

### 3.2 전제조건 — P2의 삼분류 (P2′)

| 부류 | 정의 | 처리 |
|---|---|---|
| `design_facts` | 데이터를 보기 전에 스키마·선언에서 판정 | 하드 게이트 (위반 = 실행 불가, 일급 실패 출력) |
| `deterministic_data_checks` | 결정론적으로 검사 가능한 데이터 사실. 위반 시 **estimand 자체가 달라짐** (예: 개방 코호트, MECE 실데이터 검증) | 게이트 또는 estimand 전환 요구. 산술 검증이므로 사전검정 함정에 해당 없음. **자동 폴백은 금지** — 대안 estimand를 제시하고 선택을 기록 |
| `distributional_assumptions` | 잡음 있는 분포 가정 (정규성, 자기상관 정도 등) | **ledger 전용.** 조건부 폴백 금지 — robust 짝을 조건 없이 항상 병기 |

각 항목은 §3.1의 check id를 참조하고, **항목별로** `on_violation: block | warn_override |
allow`를 지정한다(연산자 수준 값은 기본값일 뿐). warn_override의 오버라이드는 '컨설턴트 판단'
라벨로 영구 기록된다. 절대 금지의 남발은 기록 없는 우회를 낳는다 — Stevens 계보의 교훈.

data_dependent 검사는 ledger 엔트리를 생산하는 **결정론적 진단의 id**를 필수로 연결한다
(예: 코호트 안정성 → `segment_churn_rate` 진단). 진단이 없으면 `ledger_entry:
not_computable_v1`을 명시 — '기록 안 됨'과 '기록할 수단 없음'을 구분해야 v2 우선순위가
데이터에서 나온다.

### 3.3 등록 스키마 본체

```yaml
operator:
  id: string
  canonical_equivalents: [{name, refs}]    # P7: 학술 표준 동치

  provisional_axes:              # 0단계 축 관찰용 — admissibility에 미사용 (P1)
    metric_form: ...             # 지표 함수형
    partition: ...               # 분할 구조
    comparison_basis: ...        # 비교 기저
    decomposition_rule: ...      # 분해 규칙

  question_signature: {...}      # §2 (질문 쪽 서명과의 매칭 조건)

  parameters:                    # PROC의 시그니처 원리 — 시그니처 변경 = 신규 연산자 등록
    - {name, type, default, range, override_recorded: bool}

  input_contract:
    measure_checks: [check_id]   # §3.1의 등록된 검사기 참조
    dimension_checks: [check_id]
    minimum_data: {...}

  preconditions:                 # §3.2의 삼분류, 항목별 on_violation
    design_facts: [{check: id, on_violation: ...}]
    deterministic_data_checks: [{check: id, on_violation: ..., ledger_diagnostic: id}]
    distributional_assumptions: [{assumption, ledger_diagnostic: id | not_computable_v1}]

  output_contract:               # §3.4의 합 타입
    estimand: string
    output_type: Description | Attribution | Sensitivity | RobustnessDiagnostic
                                 # Cause는 output_type에 존재하지 않는다 (P3)
    fields: [...]
    uncertainty_model: string | none
                                 # '필드 존재 = 계산 절차 존재' 불변 조건:
                                 #   uncertainty_model: none이면 uncertainty 필드 자체가 없다
    label_ceiling: {...}         # 필드 단위 승격 조건 (§3.5)

  threat_coverage: [...]         # 이 연산자가 소거·판별할 수 있는 대안 설명 (기각 어법 지양)
  robust_companions:             # 런타임 의무 — 연산자 래퍼가 자동 실행해 번들로 묶는다
    - {id: operator_id, output_contract_ref}   # companion도 자체 등록 필수 (봉인 우회 방지)

  lifecycle: {introduced, evidence_refs, deprecation_condition, replacement}
```

> v1.0의 `degraded_mode` 필드는 **삭제**되었다. 데이터 의존 검사 결과로 강등이 발동되면
> 그것이 정확히 사전검정 후 조건부 분기(순서도의 오류)의 재현이기 때문이다. 대안 제시는
> §3.4 실패 반환의 `alternatives` 필드로 흡수한다 — **라우팅 힌트이지 자동 전환이 아니다.**

### 3.4 반환 타입 — 부분함수의 합 타입 (전사함수 금지)

모든 연산자의 반환은 다음 세 변종 중 하나다. 세 변종 모두 v1 스키마의 필수 구성원이며,
성공/실패 모두 파싱 가능해야 파이프라인 합성(P8 폐쇄성)이 실패 경로에서도 유지된다:

```yaml
result:      {fields..., assumptions_used: [ledger_entry_id], witness_refs}
out_of_domain: {violated: [check_id], reason, alternatives: [operator_id]}
suspended:   {missing_inputs, pass_conditions}   # GLIMPSE suspension:
                                                 # "무엇이 있으면 통과 가능한가"의 구조화 출력
```

### 3.5 라벨 승격 규칙

- 승격 조건은 **필드 단위**로 선언한다.
- **검증기가 등록되지 않은 승격 조건은 무효** — 해당 필드의 상한은 무조건 '데이터 시사'.
- 항등식 재계산 검증기(Σ기여분 == Δ전체 등)는 전체 시스템에서 가장 싼 결정론적 검사이므로
  **v1 배포 범위에 포함**하고, 승격 조건이 아니라 연산자의 필수 post-condition으로 둔다:
  재계산 불일치 시 출력 자체가 실패 처리된다.
- 모형 의존 필드(uncertainty, shrunk_estimate류)는 **어떤 조건에서도 '확인' 불가**.

### 3.6 서사 계층 구속 (2층 분리의 강제)

최종 서사의 모든 수치 주장은 연산자 호출 id를 참조해야 한다. 하니스가 이를 린트하여,
참조 없는 숫자(LLM이 즉석에서 나눠 만든 비율 등)는 '컨설턴트 판단' 라벨을 강제받거나
차단된다. 이것이 없으면 2층 분리는 선언에 그친다.

## 4. v1 연산자 등록

### 4.1 세그먼트 기여도 분해 `contrib_decomp` — fully worked

```yaml
operator:
  id: contrib_decomp
  canonical_equivalents:
    - {name: multi-dimensional root cause analysis, refs: [Adtributor (NSDI 2014), HotSpot 계열]}
    - {name: contribution/variance analysis, refs: [관리회계 variance analysis 전통]}
  provisional_axes: {metric_form: additive, partition: 단일 차원 MECE,
                     comparison_basis: 전기 대비, decomposition_rule: 가산 항등식}
  question_signature: {external_criterion: present, question_type: change}
  parameters:
    - {name: min_segment_share, type: float, default: 0.01, range: [0, 0.2], override_recorded: true}
    - {name: unknown_bucket, type: bool, default: true}   # 미분류 값의 명시적 'unknown' 세그먼트 편입

  input_contract:
    measure_checks: [additive_across_dims_for_dim]   # (지표, 차원) 쌍 판정 — distinct는
                                                     # entity_functional 차원에서만 통과
    dimension_checks: [mece_declared]
    minimum_data: {periods: 2}

  preconditions:
    design_facts:
      - {check: mece_declared, on_violation: block}            # 스키마 선언 수준의 MECE
      - {check: metric_version_identical, on_violation: block} # §1.3 version 필드로 판정
    deterministic_data_checks:
      - {check: mece_runtime_coverage,                         # Σ세그먼트 == 전체, NULL/미분류 검출
         on_violation: warn_override,                          # unknown 버킷 편입으로 해소 가능
         ledger_diagnostic: coverage_residual}
      - {check: cohort_stability,                              # 개방 코호트 검출 (멤버십 이동률)
         on_violation: warn_override,
         ledger_diagnostic: segment_churn_rate}
         # 위반 시 자동 폴백이 아니라 estimand 재선언을 제시:
         #   "고정 코호트 기여 + migration 항"의 분해 (alternatives로 노출, 선택은 기록)
    distributional_assumptions: []                             # v1 estimand는 산술적 — 해당 없음

  output_contract:
    estimand: "관측 기간의 산술 기여분 — Δ지표에 대한 세그먼트 s의 기여
               (선언된 additive_partition 항등식 기준). 결정론적 회계 수치."
    output_type: Attribution
    uncertainty_model: none        # 산술 estimand에는 표본이 없다 — uncertainty 필드 자체가 없음
    fields: [contribution, share_of_change, assumptions_used, witness_refs]
    share_of_change_rules:         # 순수 산술도 오도 가능 — 산출 억제 규칙
      suppress_if: "|Δ전체| < δ_min 또는 세그먼트 기여 부호 혼재"
      fallback: "Σ|기여분| 대비 비중 또는 절대 기여분만 보고"
    label_ceiling:                 # 필드 단위
      contribution: {ceiling: 데이터 확인, condition: identity_recheck (post-condition, v1 검증기 포함)}
      share_of_change: {ceiling: 데이터 확인, condition: 부호 동질 AND |Δ전체| ≥ δ_min}
      기타: {ceiling: 데이터 시사}

  threat_coverage:
    - "변화의 세그먼트 간 분포(집중 vs 광범위)를 정량 기술 — 전사적 요인과 국지적 요인을
       구별하는 증거 제공"
  robust_companions:
    - {id: winsorized_contrib_stability, output_contract_ref: 4.5}
  lifecycle: {introduced: v1}
```

**추론적 estimand는 v2로.** "체계적(재현 기대) 기여분" — 상위 세그먼트의 winner's curse
보정(shrinkage)과 불확실성 — 은 확률 모형(세그먼트 간 교환가능성 하의 경험적 베이즈, 또는
기간 간 변동 기반 잡음 추정)의 명시를 전제하며, `periods: 2`로는 성립하지 않는다.
v2에서 `contrib_decomp_inferential`로 별도 등록(minimum periods ≥ 8, label 상한 '시사' 고정).
확률 모형 없는 shrinkage는 임의의 수치 변형이다.

### 4.2 Volume–Rate–Mix — estimand 축으로 2개 연산자

v1.0에서 하나였던 vrm_decomp는 서로 다른 두 estimand를 뭉친 것이었다. 분리:

**`vrm_decomp_amount`** — 대상: `amount`. 항등식 `amount = Σ_s rate_s × denom_s`에 대한
ΔAmount의 volume/rate/mix 분해.
- canonical_equivalents: price-volume-mix variance(관리회계), 지수 문제(Laspeyres/Paasche)
- 교호작용항 배분 관례를 `parameters`로 선언(단일 정답처럼 제시 금지)

**`vrm_decomp_rate`** — 대상: `rate`. 전체율 차이 Δrate = rate 효과 + 구성(mix) 효과.
- canonical_equivalents: Kitagawa decomposition(1955), Oaxaca–Blinder
- input_contract: has_denominator == true, aggregation_rule == denominator_weighted_mean

두 연산자는 같은 축(분해 규칙)의 다른 점 — 1단계 인수분해의 재료로 provisional_axes에 기록.

### 4.3 추세·변곡점 — 확인형/스캔형 분리

**`trend_changepoint_confirm`** (v1) — 사용자가 지정한 타깃 지표+기간의 변화 검사.
- question_signature: {external_criterion: present, question_type: change}
- canonical_equivalents: changepoint detection(CUSUM 계열), SPC(Shewhart)
- preconditions:
  - design_facts: `{check: seasonal_adjustment_applied, on_violation: block}` — 시간 차원에
    cyclic 플래그가 있으면 계절 조정/차분을 **무조건** 적용(조건부 아님)
  - distributional_assumptions: 잔차 자기상관 → `ledger_diagnostic: residual_autocorr`
    (SPC의 독립 가정 — 자기상관 시 오경보율 상승을 ledger에 수치로)
- output_contract 필수 필드: 변곡점 위치의 불확실성, **스캔된 후보 시점 수**(연산자 내부
  다중성의 노출), 탐지 임계의 다중성 보정 방식(파라미터)

**`trend_changepoint_scan`** (봉인) — 여러 지표·전 구간을 훑는 탐색형.
external_criterion: absent이므로 §4.4와 동일한 봉인 논리 적용: v1 미개방.
개방 조건: exploration_budget에 스캔 지표 수·오경보율 통제의 필수 선언 + 해석 규율 성숙.

### 4.4 이상치·집중도 `outlier_concentration` — 봉인 (채널 무관)

- canonical_equivalents: robust statistics(median/MAD, Tukey), 집중도 지표(HHI, Gini/Pareto)
- question_signature: {external_criterion: absent, question_type: distribution}
- input_contract: 집중도 지표 경로에 `sign == nonnegative` (음수 가능 지표에서 HHI/Gini는
  미정의/오도적)
- **봉인 규칙(v1.1 강화)**: 단독 개방은 라벨·C5 규율 성숙 후. companion 채널로 노출될 때도
  **label_ceiling은 채널 무관하게 '참고치'(시사 미만)로 고정** — 봉인이 companion 경로로
  우회되지 않게. companion 출력도 자체 output_contract 등록 필수(§3.3).

### 4.5 `winsorized_contrib_stability` — robust 짝의 재정의

v1.0의 `median_contrib`("중앙값 기반 기여도 분해")는 **정의 불가능하여 삭제** —
중앙값은 가산 항등식을 만족하지 않는다(Σ median기여 ≠ Δmedian). 대체:

- estimand: "윈저화/트림된 원천 데이터로 가산 분해를 재실행했을 때 상위 기여 순위의 안정성
  (이상 거래 몇 건이 결론을 만들었는가 — leave-out 민감도)"
- output_type: **RobustnessDiagnostic** — 항등식을 보존하는 분해가 아니라 결론의 강건성
  진단임을 타입으로 명시
- label_ceiling: 데이터 시사

### 4.6 공백 등록부 — 명시적 Unknown (침묵 금지)

| 공백 | 상태 |
|---|---|
| 곱셈형 항등식 분해 (매출 = 고객수 × 빈도 × 객단가) | **Unknown.** v1 정의역 밖 — LLM의 즉석 곱셈 분해 우회 금지. v2 후보: `multiplicative_decomp`(LMDI/Shapley 배분, 관례는 파라미터) |
| flow_stock 항등식 분해 (Δ재고 = 입고 − 출고) | **Unknown.** v2 후보 |
| 추론적 기여분 (winner's curse 보정) | v2: `contrib_decomp_inferential` (확률 모형 명시 전제) |
| 탐색형 스캔 (§4.3 scan, §4.4 단독) | 봉인 — 개방 조건 명시됨 |

### v2+ 백로그 (가정 부하 오름차순)

1. `sensitivity_bound` — Cornfield/E-value 계열 민감도 정량화 (식별 가정 불요, 조기 투입 가능)
2. `negative_control` — 음성 대조 검사 (저비용, C2·C5 동시 강화)
3. `implication_check` — 가설의 검증 가능 함의 검사 (elaborate theories; C4 재정의의 기반)
4. `natural_experiment_scan` — 변곡점 × 외생 이벤트 메타데이터 교차
5. `contrib_decomp_inferential`, `multiplicative_decomp`, flow_stock 분해
6. 설계 기반 비교(이벤트 스터디류) — `assignment_mechanism` 메타데이터가 존재할 때만 개방
7. ~~인과성 연산자~~ — **로드맵에 없음.** 최종 산출물은 증거 패키지.

## 5. 실행 기록 (Evidence Bundle의 구조 필드)

**생산 주체가 원칙이다**: 아래 기록은 LLM이 사후에 작성하는 자기보고 문서가 아니라,
**런타임이 도구 호출 로그에서 파생하는 기록**이다(1980년대 시스템이 규칙 추적으로 why를
공짜로 얻었듯, 하니스가 호출을 추적해 공짜로 얻는다). LLM 자기보고가 섞이는 필드는 그 사실을
표기한다.

```yaml
execution_record:
  dag: [...]                     # 런타임이 연산자 호출에서 자동 append
  gates_passed: [...]            # 게이트별 판정과 check id·결과 (런타임)
  operators_considered:
    runtime_rejected: [...]      # admissibility 검사 실행 → 탈락 (기계 사실)
    llm_reported: [...]          # "고려했으나 선택 안 함" (자기보고임을 표기)
  exploration_budget:
    limits: {max_depth, max_segments, max_hypotheses}    # 사전 상한 — 상한 없는 실행 불가
    consumed: {...}                                      # 런타임 계수
    on_exhaustion: stop_and_report                       # 소진 시 중단 + Bundle에 소진 라벨
  assumption_ledger:             # P2′ 우변의 실재 스키마 (참조만 있던 v1.0 결함 해소)
    - {assumption: string,
       status: checked | unchecked | uncheckable,        # 검사 불가능도 일급 출력
       evidence_ref: diagnostic_id | not_computable_v1,
       operator_id}
  overrides: [...]               # warn_override 행사 기록 → admissibility 규칙 개정의 입력
```

- output_contract의 `assumptions_used`는 이 ledger의 엔트리 id를 참조한다.
- "이 결론은 N개 경로 중 선택된 것" 라벨은 `consumed`에서 파생된다.
- 전략 자체는 정본화하지 않는다(P4) — 이 기록은 검증용이지 표준 순서의 강제가 아니다.

## 6. 게이트 × 레지스트리 실행 매핑 (부록)

게이트 본문 정의는 아키텍처 문서 소관이나, 레지스트리 필드의 실행 지점은 여기 명시한다:

| 게이트 | 이 문서의 실행 대상 |
|---|---|
| C1 (의미 확정) | 지표·차원 타입 확정, 재캐스팅(§1.2), decomposition_identities 선택, question_signature 결정 |
| C1 직후 | input_contract 검사, preconditions.design_facts 평가 (하드 게이트) |
| C2 (품질) | preconditions.deterministic_data_checks 실행 → 게이트/estimand 전환/ledger, generation 메타데이터 참조 |
| C3 (유의미성) | output_contract의 δ_min·suppress 규칙 (종료가 아니라 라우팅 힌트 — legacy-notes 함정 3) |
| C4 (수렴) | exploration_budget.limits 검사; (v2) implication_check |
| C5 (근거 정합) | witness_refs 검증, 서사 린트(§3.6) |

## 7. 미해결 질문 (open questions)

1. 축 확정 시점 — 0단계 종료 기준. **v1.1 보강**: provisional_axes 필드가 관찰 데이터를
   축적하므로, "provisional_axes가 안정된 연산자 수 ≥ N"을 후보 기준으로.
2. `rate` 교호작용항 배분 관례 목록(v1에 선언 가능하게 둘 관례들).
3. ~~항등식 재계산 검증기~~ — **해소**: v1 배포 범위 + post-condition으로 확정 (§3.5).
4. `contrib_decomp_inferential`의 확률 모형 선택(경험적 베이즈 vs 기간 간 변동 기반) 및
   uncertainty_model의 표준 어휘.
5. 게이트(C1~C5)를 버전된 설정으로 두는 형식.
6. **신규**: named check registry의 v1 검사기 목록 확정(§3.1) — mece_runtime_coverage,
   segment_churn_rate, identity_recheck, residual_autocorr이 최소 집합.
7. **신규**: 서사 린트(§3.6)의 구현 — 수치 주장 ↔ 호출 id 참조의 강제 방식.
