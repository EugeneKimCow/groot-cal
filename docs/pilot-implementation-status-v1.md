# Pilot implementation status v1

## 완료된 범위

### 실행 계약 increment 1

- Query Spec v1과 semantic validation
- scope·기간·비교 기준·metric version의 실행 전파
- 1월 연도 경계를 포함한 달력 계산
- 계획 vintage 미지정 반문과 plan-only routing
- 실행 가능한 operator registry v1
- 호출 전 depth·segment·hypothesis·operator-call 예산 강제
- 자동 call provenance, spec hash, input snapshot hash, gate 기록
- 기존 동결 bundle과 분리된 `bundle-v1.json` 출력

### 일반성 challenge 1

- signed amount: 영업이익
- rate: 보험 손해율
- 지표 이름이 아닌 type, sign policy, aggregation rule, field binding으로 실행 통제
- rate에 대한 가법 기여도 호출 및 단순 평균 경로 차단

### H2 평가 기반

- raw/advisory/enforced 공통 사례 형식
- enforced 조건 자동 실행기
- scope, 기간, vintage, level/change routing, unknown metric을 포함한 기준 사례 10개
- raw/advisory/enforced capability manifest와 조건별 실행 패킷
- normalized agent trace v1 schema, 단계별 scorer와 조건별 집계기
- C2 결정론적 실행 trace collector
- raw/advisory allowlist workspace와 원 프로젝트 read-deny Seatbelt runner
- ephemeral·read-only·설정 비상속 Codex CLI 실행 및 JSONL/trace/score/audit 보존

### Golden set v1

- 현재 실행 가능한 질문 16건을 `ready`로 자동 회귀
- 영업이익·손해율·재고 잔액·활성 고객 수를 metric catalog + typed core 주 실행 경로로 승격
- materialized result staleness와 bounded reporting을 주 실행 경로에 연결
- 수치 기대값과 함께 축간 합산 금지·인과 판정 금지·label ceiling을 answer contract로 고정
- 잘못된 기간의 합 타입 회복, 실제 hypothesis 예산 초과 차단, 제한 차원 scope 침묵 축소 차단

### Materialized result increment 1

- 정상 operator result만 materialize
- query spec·operator·input snapshot 기반 결정적 result ID
- source change, expires_at, immutable snapshot staleness policy
- 현재 source hash 부재 시 suspended
- 기존 경로의 다른 결과 덮어쓰기 차단
- in-memory result catalog의 latest·alias·result_id 해소
- 자연어의 최신성 질문을 현재 metric source snapshot과 비교

### Reporter increment 2

- 입력 capability를 Result Envelope로 한정하고 raw access를 명시적으로 차단
- 보고 문장마다 수치 값과 `source_ref`를 함께 보존
- source 역검사, label, 인과 단정, capability lint
- 직전 분석 context가 없으면 보고 질문을 실행하지 않고 반문
- Report Spec v1과 Structured Report v1 schema
- `executive_memo`의 header·headline·reassurance·decomposition·cause·ambiguity·watchpoint·
  follow-up·source footer 구조 슬롯
- operation family와 지배 기여도에 따른 결정적 결과 선택, 호출자 `result_key` 명시 선택
- claim–slot 참조, 백분율 분모, 단일 분해 축, 시사·판단 근거의 구조 lint
- 번들에 없는 담당자·기한을 만들지 않고 `needs_assignment`·`ACT01` 경고로 보존

## 현재 측정 결과

- 실행 계약 단위 테스트: 14개 통과
- 다중 metric catalog·typed 실행 테스트: 9개 통과
- 일반성 challenge 테스트: 5개 통과
- 일반성 challenge 2 테스트: 6개 통과
- H2 평가 하니스 테스트: 17개 통과
- H2 격리 runner 테스트: 7개 통과(외부 Seatbelt 검증 포함)
- materialized result·staleness 테스트: 7개 통과
- result catalog·자연어 최신성 context 테스트: 3개 통과
- reporter·lint 테스트: 16개 통과
- 전체 단위 테스트: 일반 sandbox에서 84개 실행·83개 통과·중첩 Seatbelt 1개 skip,
  외부 Seatbelt 실행에서 격리 runner 검증 별도 통과
- enforced 기준 사례: 10/10 통과
- H2 C2 실행 trace: resolution 10/10, 적용 가능한 binding·selection·execution·persistence 7/7
- H2 C2 reporting: 적용 가능한 정상 결과 5/5 통과, 비대상 5건
- H2 C0/C1 정식 trace: attempt 1–5 raw 50건·advisory 50건, batch error·capability 위반 0건
- C0/C1 smoke: 동일 사례 각 1회에서 양쪽 모두 수치·source reporting 통과, advisory는 metric
  ID/version·operator 선택도 일치. v2 trace 정규화 결함으로 비교 표본에서는 제외
- C0/C1 v3 형식 smoke: advisory resolution·binding·selection·reporting 통과. C2 내부 result
  key를 공통 rubric이 요구한 결함을 발견해 v4 `primary_value` 계약으로 교정; 비교 표본 제외
- C0/C1 v4 최종 smoke: raw primary value·reporting 통과, advisory는 persistence 외 전 단계
  통과. capability 위반 0건; v4를 정식 반복 측정 형식으로 확정
- C0/C1 v4 final: raw→advisory pass가 resolution 7→40/50, binding 0→14/35,
  selection 10→25/35, execution 11→23/35. persistence 0→0/35, reporting 12→14/25
- matched 50쌍 전체 통과는 7→14건(개선 8, 퇴행 1, 탐색적 exact McNemar p=0.0391)
- C2 enforced는 resolution 10/10, 적용 가능한 binding·selection·execution·persistence 7/7,
  reporting 5/5. pilot 범위에서 H2를 지지하며 상세 집계는 `wave-v4-final.json`
- golden set ready 사례: 17/17 통과 (`planned` 0건)
- 기존 gate 적대 프로브: 전부 통과
- 기존 rise/flat/fall_dirty 시뮬레이션: 회귀 없음

H1은 네 metric type의 실행 반례를 통과했고, H2는 고정 매출 corpus에서 C0/C1 5회 반복과
C2 기준선 비교를 완료했다. 이에 따라 type-directed metric·binding 실행 계약은 canonical로
승격한다. 다만 이 결과는 현재 model·fixture 밖의 보편 효과나 metric type 열거의 완전성을
입증하지 않는다.

## 다음 실행 순서

1. H2의 반복 측정과 scorer 계약을 회귀로 유지하고, 새 model·domain에서 재현 범위를 넓힌다.
2. 외부 영속 result catalog와 source connector를 별도 capability로 구현한다.
3. reporter를 주간 브리핑·경영진 1페이지·분석가 노트·S&OP 장르와 최종 자연어 렌더링으로
   확장한다.

## 보류한 정본 승격

- metric type 열거의 완전성
- rate 변화 분해 operator
- 저장 결과 승격 기준
- question signature의 최종 축

type-directed admissibility와 `bindings`의 존재성·구속 규칙은 canonical로 승격했다. 새로운
수학적 성질이 현재 enum 밖에 있을 가능성과 domain별 binding key 확장은 열어 둔다. 나머지
항목은 해당 실패 반례와 실행 계약이 추가될 때 재평가한다.
