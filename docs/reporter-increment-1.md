# Structured reporter increment 1

> 이 문서는 최소 안전 경계의 이력이다. Report Spec v1과 구조 슬롯 구현은
> `reporter-increment-2.md`가 이어받는다.

## 목적과 경계

이 increment는 완성된 경영진 보고서 생성기가 아니라 보고 단계의 최소 안전 경계다. reporter는
원장이나 metric fixture를 읽지 않고 호출자가 제공한 Result Envelope만 입력으로 받는다. 현재
지원 장르는 `executive_memo` 하나이며, 첫 번째 정상 operator 결과에서 요약 claim을 만든다.

기계 실행 기준은 `slice/reporter.py`다. `docs/report-contract-v0.md`의 전체 슬롯·장르·어미 규약은
목표 계약이며 아직 전부 구현되지 않았다.

## 출력 계약

각 claim은 다음을 함께 가진다.

- 사람이 읽는 `text`
- 원래 수치인 `value`
- Result Envelope 내부 경로인 `source_ref`
- 현재 허용 상한인 `데이터 확인` label

capability는 `inputs: [result_envelope]`, `raw_access: false`로 고정한다. 직전 분석 context가 없는
“이 결과를 메모로 작성해줘” 요청은 어떤 결과인지 반문한다.

## 현재 lint

- `CAP01`: Result Envelope 전용 capability 위반
- `SRC01`: claim의 수치와 `source_ref`의 실제 값 불일치 또는 경로 부재
- `LBL01`: 현재 increment에서 허용하지 않은 label
- `CAU01`: 원인·때문·초래·야기 등 인과 단정 어휘

lint를 통과한 구조화 출력만 golden set의 bounded reporting 성공으로 센다.

## 후속 범위

- `report-contract-v0.md`의 장르별 필수 슬롯과 문장 유형 예산
- 각 Result Envelope가 제공하는 실제 label ceiling의 claim별 전파
- 다축 수치의 교차 합산, 백분율 분모, 시사 근거, 후속 행동에 대한 구조 lint
- 독립 agent trace에서 reporting 단계의 반복 측정
