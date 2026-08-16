# Pilot implementation status v2

2026-08-16 기준. v1 이후의 변화: 아키텍처 연구 루프(E-000~E-017)가 C4 3계약
generic Call DAG를 현재 최선으로 선정했고, increment 5 라우팅이 E-018~E-020으로
시연 가능한 범위까지 진행됐다. v1의 pilot 완료 범위(H1·H2·golden set·
materialized result·reporter)는 그대로 유효하다.

## v1 이후 완료된 범위

### 아키텍처 연구 (research/architecture/)

- 후보 C0~C4를 60질문 corpus에서 비교, C4(3계약 generic Call DAG) 선정
- shadow increment 1~4: canonical 계약·algebra 평가기·intent compiler
  fidelity gate(governed 한국어 9/9·침묵 치환 0)·실행 parity — 전부 라우팅
  무변경 상태에서 검증

### E-018 — metric-level routing

- `engine.run_question`에 가역 route selector(기본값 현행 경로 보존)
- 5개 metric algebra의 값·단위·label·실패 위치·보고·materialization·
  provenance parity, 침묵 fallback 0
- **H2 enforced corpus 10/10을 모든 라우팅 증분의 상설 exit gate로 편입**
- 반례 실증 1건: public 경계의 domain pack 가정 ledger 누락 → 공유 상수로 수리
  (예측대로 마이그레이션 제약은 산술이 아니라 bundle 경계였다)

### E-019 — period-change routing

- explain_change를 축별 (before, after, contribution|set_transition) DAG로
  컴파일 — 현행 공개 경계와 동형, rate 변화는 동일 payload로 거부
- commerce 이벤트 대조를 명시적 등록 Call(event_overlap_scan@v1)로 편입
- 변화 메모 보고서 claims 14건 바이트 동일·lint 청정
- 선언된 경계 축소: 지배축 자동 드릴다운(drill:*)·vrm:online은 라우팅 경계에서
  의도적 부재(synthesis §10의 숨은 전략 제거, 소비자·golden 참조 0건)

### E-020 — 시연 진입점

- `run.py --route c4 [--show-plan]`: 한국어 질의 → 절 바인딩 대장 → Call DAG
  → 실행 기록(예산·게이트·provenance) → 증거 한정 결과의 계층 관찰
- 적대 질문 9/9 처리(실행 2·intent 거부 5·미라우팅 거부 2), 치환 0
- intent compiler와 Query Spec compiler가 같은 executor에서 동일 수치로 수렴
- 미라우팅 capability(rank·drilldown·plan_gap·align)는 이름을 밝혀 거부

## 현재 측정 결과

- production 테스트: 197 (표준 sandbox 전부 통과, Seatbelt 1건 외부 검증)
- golden set ready: 17/17, enforced semantic: 10/10 (양 selector), research: 58/58
- E-018 14 + E-019 11 + E-020 8 = 라우팅·시연 게이트 33개
- 기본 경로 동작 변화: 0 (가드 테스트로 고정)

## 다음 실행 순서

1. LLM proposal adapter over clause-binding 계약(C2′) — H2의 원 비교(C1 vs
   "계약 아래의 LLM")를 완성하는 최대 판별 실험이자 광역 한국어 recall 시험
2. rank·drilldown 라우팅 — 동적 Slice 설계와 DAG 실패 격리(미해결 #19) 선결
3. H2 재현(새 model·domain)은 C4 라우팅 경로 위에서 수행
4. increment 6(legacy 제거)은 capability 라우팅 완주 후

## 보류·미해결 (research/architecture/unresolved.md)

- DAG 실패 격리 의미론(#19), share 억제 규범 소유권(#20), label capability
  소유권(#21), LLM planner fidelity·광역 recall(#14·#16), 실 RDBMS pushdown(#12)
