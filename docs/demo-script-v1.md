# 시연 대본 v1 — 직접 질의로 연산을 관찰하기

모든 명령은 `slice/`에서 실행한다. `--route c4`는 opt-in 시연 경로이고 기본
CLI는 기존 그대로다. 출력은 2026-08-16 실측이며 결정론적으로 재현된다.

시연의 서사: **이 시스템의 기능은 "답을 잘 하는 것"이 아니라 "답할 수 있는
것과 없는 것을 계약으로 구분하는 것"이다.** 거부·반문·보류 장면이 성공 장면과
동급의 전시물이다.

## 장면 1 — 수준 조회: 파이프라인 전체를 한 눈에

```
python3 run.py "7월 매출은?" --route c4 --show-plan
```

관찰 포인트: ① 어절 단위 바인딩(7월→time.target, 매출→metric_ref)과 조사의
명시적 비소비 ② 단일 evaluate_metric Call ③ 예산 소비 기록 ④ 값 3860과
label 상한 data_confirmed.

## 장면 2 — 어휘 일반성(H1): 수학적 성질이 다른 지표 4종

```
python3 run.py "7월 영업이익은?" --route c4      # signed amount: 20
python3 run.py "7월 보험 손해율은?" --route c4    # rate: 0.66 (Σ분자/Σ분모)
python3 run.py "7월 말 재고는?" --route c4        # balance: 190 (period-end)
python3 run.py "7월 활성 고객 수는?" --route c4   # distinct: 5
```

화법: 같은 evaluate_metric 연산자, 같은 Plan 문법. 지표별 분기는 코드가 아니라
등록된 aggregation algebra에 있다.

## 장면 3 — 변화 설명: 축별 기여 분해

```
python3 run.py "온라인 매출이 7월에 왜 빠졌어?" --route c4 --show-plan
```

관찰 포인트: "온라인"이 filter로, "왜 빠졌어"가 contribution으로 바인딩. 축별
(before, after, contribution) triplet DAG. Δ=-220의 고객유형·제품군 분해,
신규 -240 대 기존 +20. 총합 항등식은 실행 게이트가 검사한다.

## 장면 4 — 전이 의미론: distinct는 가법 산술로 축약하지 않는다

```
python3 run.py "7월 활성 고객 증가는 어느 지역에서 발생했나?" --route c4
```

관찰 포인트: Δ=2와 함께 "진입 ['c4','c5'], 이탈 [], 이동 0건" — 세그먼트
산술이 숨기는 진입/이탈/이동을 set_transition@v1이 명시한다.

## 장면 5 — 거부 1: 수학이 안 되는 요청

```
python3 run.py "7월 손해율이 왜 변했나?" --route c4
```

관찰 포인트: `[OUT_OF_DOMAIN] registered rate-change decomposition is
unavailable` — rate에 가법 기여 분해를 조용히 적용하는 대신 연산자 부재를
밝힌다. 인접한 다른 분석으로 대체하지 않는다.

## 장면 6 — 거부 2: estimand가 미정의인 요청

```
python3 run.py "7월 매출 계획 대비 어때?" --route c4
```

관찰 포인트: `[CLARIFY] plan comparison requires a pinned scenario vintage` —
"어느 계획?"이 정해지지 않으면 계산 자체가 미정의라서 반문한다.

## 장면 7 — 침묵 손실 방어: 절이 사라지지 않는다

```
python3 run.py "7월 평균 재고는?" --route c4      # '평균'이 명시적으로 거부됨
python3 run.py "2025년 7월 매출은?" --route c4    # 2025가 소비되고 suspended
```

화법: legacy 해석기는 "2025년"을 조용히 버리고 2026-07을 답했다. 시연 경로는
연도를 바인딩하고, 데이터 부재를 재개 조건과 함께 보류로 답한다. 모든 어절의
소비/보존/거부가 대장에 남는다.

## 장면 8 — 경계 고백: 검증됐지만 승격 전인 것

```
python3 run.py "7월 매출 감소 상위 3개 제품군만 보여줘" --route c4
python3 run.py "2026-06-25 계획 대비 7월 매출 어때?" --route c4
```

관찰 포인트: rank@v1·plan_gap@v1은 shadow parity까지 검증됐지만 라우팅 승격
전 — 시스템이 자기 경계를 이름으로 밝힌다. 같은 질문을 기본 CLI로 다시 실행해
현행 경로의 답을 보여줄 수 있다:

```
python3 run.py "2026-06-25 계획 대비 7월 매출 어때?"
```

## 장면 9 — 저장·최신성·보고 (현행 경로, engine 수준)

```
python3 - <<'EOF'
from engine import run_question
from result_store import materialize_result, assess_staleness
from result_catalog import ResultCatalog

_, bundle = run_question("7월 매출은?", route="c4")
stored = materialize_result(bundle, "level", created_at="2026-08-16T00:00:00Z")
print("result_id:", stored["result_id"], "| operator:", stored["operator_ref"])
catalog = ResultCatalog(); catalog.add(stored, aliases=["latest"])
_, staleness = run_question("이 분석 결과가 아직 유효한가?", result_catalog=catalog)
print("staleness:", staleness["results"]["staleness"]["staleness_status"])

_, change = run_question("온라인 매출이 7월에 왜 빠졌어?", route="c4_or_current")
_, memo = run_question("이 결과를 경영진 메모로 작성해줘", report_context=change)
print("memo:", memo["results"]["report"]["status"],
      "| lint:", memo["results"]["lint"]["passed"])
EOF
```

관찰 포인트: C4 경로 결과가 결정적 result ID로 저장되고(선언된 operator
identity), 최신성 판정과 경영진 메모·lint까지 같은 Result Envelope 경계 위에서
작동한다.

## 장면 10 — local LLM 해석: 제안은 모델이, 권위는 계약이

```
python3 run.py "7월 매출은?" --route c4 --llm gemma3:12b --show-plan
python3 run.py "7월 매출은?" --route c4 --llm qwen2.5:72b-instruct-q4_K_M --show-plan
```

관찰 포인트: 절 바인딩 *제안*만 local LLM(Ollama)이 하고, 검증·컴파일·산술은
전부 동일한 결정론 계약이 수행한다 — 결과 3860은 해석기와 무관하게 같다.
LLM이 등록 어휘 밖 지표·차원 값을 지어내면 검증기가 거부하고, 원문에 없는
텍스트를 제안하면 span 복원이 실패해 해당 구간이 미소비로 실토되며, "전월
대비"의 산술은 LLM 답을 버리고 계약이 재계산한다. 작은 모델이 "원인"을
delta로 잘못 바인딩하면 — 수치는 여전히 정확한 거친 답이 되거나, rank 입력
타입 불일치(`Delta != Attribution`)로 계약이 plan 자체를 거부한다. **모델
교체는 recall을 바꿀 뿐, 침묵 치환은 어느 모델에서도 0건**이라는 것이 이
장면의 주장이다.

## 자주 나올 질문에 대한 답

- **"왜 이렇게 거부가 많나?"** — 거부는 실패가 아니라 계약의 발화다. H2 측정
  에서 자유 실행 대비 강제 조건의 개선(matched 50쌍 7→14, McNemar p=0.039)은
  정확히 이 거부들이 만든 차이다.
- **"말을 조금 바꾸면?"** — 변화 질문 paraphrase 5종은 전부 같은 plan으로
  정규화된다. 등록 어휘 밖 표현은 clarify로 끝난다. 광역 recall은 다음 실험
  (LLM proposal adapter)의 몫이다.
- **"실데이터는?"** — 현재는 고정 fixture다. 계약·연산·거부의 형태는 데이터
  소스와 독립이며, RDBMS pushdown은 unresolved #12로 등재되어 있다.

## 장면 0 — 질의 윈도우 (권장 시작점)

```
cd slice && ../.venv/bin/python3 ui.py     # http://localhost:8787
```

브라우저에서 질문을 입력하면 진행 단계(해석→검증·컴파일→실행→결과)가 텍스트로
흐르고, 증거 한정 결과가 피드에 쌓인다. 해석기는 규칙/local LLM을 카드마다
선택할 수 있고, 헤더에 데이터 소스(DuckDB 저장소)가 표시된다. 장면 1~10의 모든
질문을 이 창에서 실행할 수 있다. 저장소 구축은 최초 1회:
`../.venv/bin/python3 build_duckdb.py`.
