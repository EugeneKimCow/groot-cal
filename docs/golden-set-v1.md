# Golden set v1

## 목적

이 golden set은 groot-cal이 답해야 할 대표 질문과 답의 의미 계약을 고정한다. 최종 문장
문구를 그대로 암기시키는 데이터셋이 아니라, 질문 해석·실행 결과·표현 상한을 함께 검사하는
제품 목표다. 기계 판독 정본은 `eval/golden-set-v1/cases.json`이다.

## 성숙도

- `ready`: 현재 Query Spec과 강제형 실행 경로에서 자동 회귀한다.
- `challenge`: 별도 타입 커널에서 산술 의미를 입증했지만 자연어→주 실행 경로에는 아직 없다.
- `planned`: 목표 계약만 고정했다. 구현 완료나 지원 질문으로 표시하면 안 된다.

현재 구성은 ready 17건, challenge 0건, planned 0건이다. 영업이익·손해율·재고 잔액·활성
고객 수는 `metric_catalog.json`의 domain pack과 typed core adapter를 통해 주 실행 경로로
승격됐다. 저장 결과 최신성 질문과 Result Envelope 전용 구조화 보고 질문도 자동 회귀한다.
실행은 다음과 같다.

```bash
python3 slice/eval_golden.py
```

## 답변 불변조건

1. 조회·계획 gap·항등식으로 닫힌 기여분은 `데이터 확인` 상한으로 말한다.
2. 축별 기여분은 각 축 안에서만 합산한다. 서로 다른 축의 기여분을 더하지 않는다.
3. 관측 집중과 이벤트 정합은 `데이터 시사` 상한이며 원인 판정으로 승격하지 않는다.
4. 계획은 빈티지를 고정하지 않으면 계산하지 않는다.
5. 입력 부재는 `suspended`, 정의역 위반은 `out_of_domain`으로 구분한다.
6. 보고 문장의 수치는 Result Envelope의 `source_ref`로 역검사되어야 하며 인과 단정으로
   승격할 수 없다.

## 승격 순서

1. ready 사례의 Query Spec·Result Envelope 회귀를 항상 통과시킨다.
2. C0 raw·C1 advisory에서 같은 ready 사례를 반복 실행해 C2와 비교한다.
3. C2를 reporter 포함 경로로 재수집해 reporting 단계를 관측한다.
4. 현재 `executive_memo` 구조 슬롯을 나머지 보고 장르와 최종 자연어 렌더링으로 확장한다.

네 metric type의 실행 승격으로 수학적 성질 세 종류 조건은 충족했다. 다만 C0/C1 비교로
관찰한 advisory-only 오류가 C2 enforced 경로에서 제거됨을 H2 wave v4로 확인했다. 이에 따라
type-directed metric·binding 실행 계약은 canonical로 승격했다. 현재 metric type 열거가 미래의
모든 수학적 성질을 닫는다는 주장은 여전히 provisional이다.
