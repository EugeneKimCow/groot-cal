# 연구 마무리·시연 계획 v1

작성: 2026-08-16. 목적: 아키텍처 연구(E-000~E-017)와 pilot(H1·H2) 결과를 봉합해
커밋하고, C4 경로를 시연에 필요한 최소 capability까지 정식 라우팅한 뒤, 한국어
질의 → 절 바인딩 → Plan → 실행 → 증거 한정 결과 → 보고를 한 번에 관찰하는 시연
진입점을 만든다. 이 문서는 `research/architecture/refactoring_plan.md`의
increment 5를 시연 목표에 맞춰 구체화한 실행 계획이며, 연구 교리(증거 게이트,
가역 selector, fail-closed)를 그대로 따른다.

## 완료 정의

1. 전 증거 사슬(H2 v4 final, 연구 기록, shadow 구현)이 논리 커밋으로 보존된다.
2. metric level·period delta·additive contribution이 가역 selector 뒤에서 C4
   경로로 라우팅되고, golden 17/17·semantic 10/10·H2 enforced corpus가 C4
   경로에서도 통과한다.
3. 시연 CLI 한 번의 호출로 질의 1건의 전체 파이프라인 산출물(절 바인딩 대장,
   컴파일된 Plan, 실행 기록, 결과, 보고 문장)을 관찰할 수 있다.
4. 시연 대본(질문 10선 내외)과 상태 문서 v2가 정본화된다.

## Phase 0 — 상태 봉합 (커밋, 선행 필수)

미커밋 산출물 전체를 논리 단위로 나눠 커밋한다.

1. pilot 완결: challenge 2, golden set v1, materialized result increment 1,
   reporter increment 2, H2 v4 final 증거(eval/, 해당 slice/ 모듈·테스트,
   docs/pilot-*·generality-challenge-2·golden-set-v1·result-storage-v1·
   reporter-increment-*·canonical-boundary-v1)
2. 아키텍처 연구 상태: `AGENTS.md`, `docs/architecture/`,
   `research/architecture/` 전체(E-000~E-017, corpus, 판정 기록)
3. shadow 구현 increment 1~4: `analytical_ir`, `shadow_registry`,
   `shadow_plan`, `shadow_intent`, `shadow_executor`, `clause_binding`,
   `metric_evaluator`, `result_adapter`와 신규 schemas·테스트

제외: `docs/Untitled-1.mmd`, `docs/operator-registry-v1.pdf`(사용자 개인 파일),
`.DS_Store`(`.gitignore` 추가). push는 사용자 확인 후.

게이트: 커밋 후 production 164·research 58·golden 17/17·semantic 10/10 재확인.

## Phase 1 — E-018 metric-level routing

설계는 `research/architecture/next_experiment.md`를 그대로 따른다: 기본값이
현행 경로인 가역 selector, 성공·정규화 실패 C4 결과만 기존 public bundle
경계로 adapt, 5개 algebra × scoped/missing/bad-binding/bad-scope/label-ceiling/
materialization/reporting/provenance를 양 selector로 비교, non-level Plan은
명시적 caller 선택 없이 fallback하지 않고 거부.

이 계획의 신규 결정: **H2 enforced corpus(C2 기준 사례 10건)를 C4 selector로도
실행해 exit gate에 편입한다.** 이후 모든 라우팅 증분에 동일 적용한다. H2의
canonical 승격이 legacy 경로에 대한 증거로 퇴화하지 않게 하는 봉합 장치다.

산출: `e018-comparison.md`, `metrics.md` 갱신.

## Phase 2 — 시연 최소 집합 라우팅 (E-019·E-020)

시연 서사가 요구하는 최소 capability만 순서대로 라우팅한다.

- E-019 period delta: "왜 변했나"의 비교 루트
- E-020 additive contribution: 축별 기여 분해 — 시연의 핵심 장면

각각 Phase 1과 동일한 게이트 형식(양 selector 비교, golden·semantic·H2,
가역성)을 적용한다.

명시적 보류: drilldown(동적 Slice 설계 부채 미해결), plan comparison,
set_transition, rate 변화 분해는 shadow에 남긴다. 시연에서 이들 질문은 정직한
거부·clarify로 나타나며, 그것 자체가 시연 포인트다(침묵 치환 없음).

## Phase 3 — 질의 진입점: E-016 compiler의 시연 경로 연결

현행 `engine.run_question`은 regex+interpret 경로다. 시연 모드는 opt-in으로
추가하고 기본 경로는 바꾸지 않는다.

- `--route c4` 지정 시: E-016 intent compiler로 질의를 절 바인딩 →
  Plan 컴파일하고, 라우팅 승격된 capability면 C4 executor로 실행, 아니면
  clarify / out_of_domain로 fail-closed.
- `--show-plan` 출력 계층: ① 절 바인딩 대장(어느 어절이 어떤 semantic
  reference에 바인딩됐고 소비되지 않은 절은 무엇인지) ② 컴파일된
  Plan(Call DAG) ③ 실행 기록(예산·게이트·provenance) ④ 증거 한정 결과
  ⑤ 보고 문장(label ceiling 표기).

게이트: governed corpus 필수 적대 질문 9/9(무손실 4 + fail-closed 5)와 변화
paraphrase 5/5가 시연 CLI에서 재현된다.

## Phase 4 — 문서 정본화·연구 종결 기록

- `pilot-implementation-status` v2: 라우팅 상태와 H2 게이트 편입 반영
- research journal·`current_best`·`refactoring_plan` 갱신(E-018~E-020 기록)
- `docs/demo-script-v1.md`: 시연 질문·기대 출력·거부가 기능임을 설명하는 화법
- 최종 커밋

## 시연 질문 초안

구체 문안은 golden set과 governed corpus에서 선별한다.

1. 수준 조회: "6월 온라인 매출 얼마였어?" — metric level, C4 경로
2. metric type 횡단: 영업이익(signed)·손해율(rate)·재고 잔액(balance)·활성
   고객 수(distinct) 수준 조회 — H1을 한 화면에
3. 변화 설명: "7월 매출이 왜 변했나?" — delta + contribution
4. 거부 1: 손해율 기여 분해 요청 → out_of_domain(가법 분해 부적합)
5. 거부 2: 계획 대비인데 vintage 미지정 → clarify 반문
6. 침묵 손실 방어: 소비되지 않는 절을 포함한 질의 → binding ledger가 잡아
   fail-closed
7. 최신성: "이 결과 아직 유효해?" — staleness
8. 보고: "경영진 메모로 작성해줘" — label ceiling·lint

## 범위 제외

- increment 6 legacy 제거(시연 후)
- LLM proposal adapter — 시연 후 최대 판별 실험으로 예약. H2의 핵심 비교를
  완성하는 C2′(LLM이 계약 아래서 계획) 설계가 여기에 걸린다.
- 외부 result store, 실 RDBMS pushdown, reporter 장르 확장, H2의 새 model·
  domain 재현(라우팅 완료 후 C4 경로에서 수행)

## 리스크와 대응

- public bundle 경계가 산술보다 큰 마이그레이션 제약으로 판명(E-018 명시
  리스크) → parity 기준을 byte가 아닌 normalized-field로 시작하고, 경계 차이는
  E-014 adapter 한 곳에만 수용한다.
- E-016 recall은 governed corpus 한정 → 시연 질문은 등록 어휘 안에서 선별하고,
  벗어난 질의의 clarify를 시연 서사에 편입한다(약점을 숨기지 않고 기능으로
  제시).
- contribution 라우팅의 reporter 경계 회귀 → reporter 테스트와 기존 loop8 판정
  불변을 게이트에 포함한다.

## 순서 요약

Phase 0(커밋) → 1(E-018) → 2(E-019·E-020) → 3(시연 진입점) → 4(문서·대본).
각 phase는 독립 게이트를 가지며, 어느 단계에서 멈춰도 저장소는 회귀 없이
일관된 상태를 유지한다.
