# Structured reporter increment 2

## 목적과 경계

이 increment는 Result Envelope 전용 안전 경계를 유지하면서 `executive_memo` 장르의 핵심
보고 슬롯을 구조화한다. Report Spec과 출력 schema를 추가하고, 결과 선택·claim 참조·근거·
분모·분해 축을 코드가 검사한다. 다른 장르와 완성된 자연어 1페이지 렌더링은 후속 범위다.

기계 실행 기준은 다음과 같다.

- `schemas/report-spec-v1.schema.json`
- `schemas/structured-report-v1.schema.json`
- `slice/reporter.py`

## Report Spec v1

Report Spec은 다음을 고정한다.

- `genre: executive_memo`
- `audience: executive`
- `language: ko`
- `input_capability: result_envelope_only`
- `result_selector: primary | explicit`
- 장르별 필수 슬롯 집합

`primary`는 질의의 `operation_family`로 level·plan 결과를 선택하고, 변화 설명에서는 최상위
분해 결과 중 절대 기여분이 가장 큰 축을 결정적으로 선택한다. `explicit`은 호출자가 지정한
`result_key`만 사용하며, 찾지 못하면 다른 결과로 fallback하지 않고 `suspended`한다.

## 구조화 출력

현재 executive memo 필수 슬롯은 다음 9개다.

1. `header_meta`
2. `headline_verdict`
3. `reassurance_signal`
4. `decomposition_where`
5. `cause_mapping_why`
6. `ambiguity_block`
7. `watchpoints_validation`
8. `followup_actions`
9. `source_basis_footer`

모든 슬롯은 `populated | not_applicable | suspended` 상태를 가진다. 입력에 없는 정보는 만들지
않는다. 보류 슬롯은 `missing_inputs`와 `pass_conditions`를 남기며, 후속 행동의 담당자·기한이
없으면 `needs_assignment`와 `ACT01` 경고를 기록한다.

각 claim은 다음 구조를 가진다.

```text
claim_id + slot + statement_type + text + label
         + [value + unit + source_ref]
         + [evidence_refs + evidence_grade]
```

수치 claim은 Result Envelope 내부 경로로 역검사한다. 시사·판단 claim은 근거 참조가 필수다.
인과 연결은 `데이터 시사` 상한으로 렌더링하며, 확정 불가 문장을 함께 보존한다.

## 구조 lint

차단 규칙은 다음과 같다.

- `CAP01`: Result Envelope 전용 capability 위반
- `SPEC01`: Report Spec v1 불일치
- `SLOT01`: 필수 슬롯 또는 보류 계약 누락
- `REF01`: claim ID 중복·슬롯 참조 불일치
- `SRC01`: 수치와 source 경로 값 불일치
- `PCT01`: 백분율 분모 참조 누락
- `EVD01`: 시사·판단 근거 누락 또는 잘못된 경로
- `LBL01`: 미등록 label
- `CAU01`: 상한 선언 없는 인과 단정
- `AXIS01`: 서로 다른 분해 축의 수치 혼합

`ACT01`은 담당자·기한 미지정을 알리는 경고다. 이를 채우기 위해 값을 추측하지 않는다.

## 현재 완료와 후속

Golden set은 기본 지배 축 선택과 명시적 `result_key` 선택을 모두 검사한다. 현재 후속 범위는
주간 브리핑·경영진 1페이지·분석가 노트·S&OP 장르, 장르별 문장 유형 예산, 표 규약과 최종
자연어 렌더링이다.
