# Generality challenge 1 — signed amount와 rate

## 1. 목적

매출 사례에서 발견한 어휘가 지표 이름이 아니라 수학적 성질로 연산을 통제하는지 처음으로
반증했다. 사례는 영업이익(signed amount)과 보험 손해율(rate)이다.

## 2. 결과

### 영업이익

- `amount`, `sum`, `additive_across_dims`는 매출과 동일하게 재사용됐다.
- `sign:any` 선언에 의해 음수 사업부 값이 정상 정의역에 포함됐다.
- 같은 데이터에 `sign:nonnegative`를 선언하면 `sign_policy`가 실행을 거부했다.
- 지표 이름에 대한 kernel 조건문은 추가하지 않았다.

결과: 6월 8.0억에서 7월 2.0억으로 -6.0억이며, 리테일과 기업이 각각 -3.0억을
기여한다. 음수 원천값을 오류로 취급하지 않는다.

### 손해율

- `rate`, numerator, denominator, `denominator_weighted_mean`이 추가 실행 의미로 필요했다.
- 7월 손해율은 `(72+60)/(120+80)=0.66`이다. 지역 비율의 단순 평균 `0.675`는 거부할
  계산이다.
- `contrib_decomp`의 등록 정의역이 `amount/count`이므로 rate에 대한 호출은 계산 전에
  `out_of_domain`이 됐다.
- rate descriptor가 잘못 `aggregation_rule:sum`을 선언해도 실행이 거부됐다.

## 3. 변경 분류

| 변경 | 분류 | 해석 |
|---|---|---|
| 영업이익 descriptor·fixture | instance-only | 기존 amount 의미 재사용 |
| 손해율 descriptor·fixture | instance-only | 레지스트리 초안의 rate 어휘 재사용 |
| `bindings.value_field` | schema-extension | 기존 커널의 `sales_u` 하드코딩을 드러냄 |
| numerator/denominator binding | schema-extension | rate를 실제 필드에 연결하는 데 필수 |
| `rate_level` 등록·최소 구현 | kernel-change | rate용 첫 실행 연산자 |
| 지표명 기반 분기 | 0건 | H1에 유리한 관측 |
| domain exception | 0건 | H1에 유리한 관측 |

## 4. 발견된 경계

현재 `kernel.py`는 유통 매출의 `sales_u`, `online_orders`에 결합되어 있다. 따라서 기존
커널 자체를 범용이라고 볼 수 없다. 이번 challenge는 별도 `typed_kernel.py`에서 field
binding을 descriptor로 올렸고, 이것이 다음 kernel 일반화의 후보가 됐다.

반면 모든 연산을 하나의 함수로 통합하지 않았다. 가법 기여분과 분모 가중 rate 수준은
estimand와 post-condition이 다르므로 별도 operator로 남긴다. 범용성은 함수 수를 줄이는
것이 아니라 동일한 등록·게이트·결과 계약으로 서로 다른 연산을 다루는 데 있다.

## 5. 판정

H1은 아직 입증되지 않았지만 첫 반증은 통과했다. `amount`의 부호 정책과 `rate`의 분모
의미가 descriptor·operator contract로 표현됐고, 지표 이름이나 업종을 공통 kernel에
추가하지 않았다. 다음 반증 대상은 시간 비가산 `balance`와 차원 비가산 `distinct`다.

## 6. 후속 주 실행 승격 (2026-08-14)

- `metric_catalog.json`에 매출·영업이익·손해율 domain pack을 등록했다.
- 자연어 지표 해소 뒤 동일한 Query Spec을 만들고, catalog의 실행 profile과 metric type으로
  commerce extensions 또는 typed core를 선택한다. metric id 기반 kernel 분기는 없다.
- 영업이익은 `contrib_decomp@v1`, 손해율은 `rate_level@v1`로 runtime provenance와 예산
  기록을 남긴다.
- runtime도 registry의 `metric_types`를 검사하므로 rate에 대한 가법 분해는 invoke 전에
  거부된다.

이는 두 metric type의 실행 승격이며 vocabulary의 canonical 승격은 아니다. `balance` 또는
`distinct` 반증 전에는 canonical boundary의 서로 다른 수학적 성질 세 종류 조건을 충족하지
않는다.
