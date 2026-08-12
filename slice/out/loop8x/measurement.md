# ⑧작문 확장 측정 — rise/flat/fall_dirty × N=10

입력: 시나리오별 bundle.json(run_sim.py) + 계약 v0.1. 기준선: fall 원 시나리오 N=20.

## rise (N=10)

- BLOCK율 0.0% (총 0건, 규칙 없음)
- 분량 3,662 ± 269자, 수치 47.1 ± 4.46개, 헤지 비율 0.1 ± 0.04
- T5 100.0%, defense 100.0%, 표 위반 0.0%, 본문 감사 용어 5건
- defense_lines: 100.0%
- has_table: 0.0%
- audit_jargon_body_n: 평균 0.5 (범위 0–5)
- hl_top_online: 100.0%
- overlap_abstained: 100.0%
- assertive_nohedge_n: 평균 0 (범위 0–0)
- vrm_rate_cited: 100.0%
- conditional_headline: 100.0%
- residual_attempt: 0.0%

| 메모 | BLOCK | 자수 | 수치수 | 헤지 | 비고 |
|---|---|---|---|---|---|
| memo_01.md | 0 | 3,358 | 43 | 0.087 | - |
| memo_02.md | 0 | 3,957 | 56 | 0.103 | - |
| memo_03.md | 0 | 3,534 | 39 | 0.108 | - |
| memo_04.md | 0 | 3,909 | 51 | 0.089 | - |
| memo_05.md | 0 | 3,346 | 51 | 0.092 | - |
| memo_06.md | 0 | 4,010 | 46 | 0.041 | - |
| memo_07.md | 0 | 3,704 | 47 | 0.117 | - |
| memo_08.md | 0 | 3,506 | 46 | 0.062 | - |
| memo_09.md | 0 | 3,982 | 45 | 0.101 | - |
| memo_10.md | 0 | 3,317 | 47 | 0.2 | - |

## flat (N=10)

- BLOCK율 0.0% (총 0건, 규칙 없음)
- 분량 2,735 ± 196자, 수치 32.5 ± 2.38개, 헤지 비율 0.05 ± 0.03
- T5 100.0%, defense 100.0%, 표 위반 0.0%, 본문 감사 용어 0건
- defense_lines: 100.0%
- has_table: 0.0%
- audit_jargon_body_n: 평균 0 (범위 0–0)
- band_cited: 100.0%
- no_event_stated: 80.0%
- sign_mix_handled: 50.0%
- smallness_stated: 100.0%

| 메모 | BLOCK | 자수 | 수치수 | 헤지 | 비고 |
|---|---|---|---|---|---|
| memo_01.md | 0 | 2,453 | 30 | 0.038 | - |
| memo_02.md | 0 | 2,617 | 31 | 0.017 | - |
| memo_03.md | 0 | 2,450 | 35 | 0.087 | - |
| memo_04.md | 0 | 2,663 | 34 | 0.093 | - |
| memo_05.md | 0 | 2,813 | 32 | 0.016 | - |
| memo_06.md | 0 | 3,110 | 38 | 0.015 | - |
| memo_07.md | 0 | 2,784 | 30 | 0.017 | - |
| memo_08.md | 0 | 2,956 | 31 | 0.029 | - |
| memo_09.md | 0 | 2,796 | 32 | 0.073 | - |
| memo_10.md | 0 | 2,709 | 32 | 0.074 | - |

## fall_dirty (N=10)

- BLOCK율 0.0% (총 0건, 규칙 없음)
- 분량 3,636 ± 248자, 수치 14.5 ± 1.28개, 헤지 비율 0.11 ± 0.03
- T5 100.0%, defense 90.0%, 표 위반 0.0%, 본문 감사 용어 0건
- defense_lines: 90.0%
- has_table: 0.0%
- audit_jargon_body_n: 평균 0 (범위 0–0)
- refusal_in_headline: 80.0%
- total_delta_cited: 100.0%
- event_figures_cited_n: 평균 5 (범위 5–5)
- repair_requested: 100.0%
- quality_caveat_on_figures: 40.0%

| 메모 | BLOCK | 자수 | 수치수 | 헤지 | 비고 |
|---|---|---|---|---|---|
| memo_01.md | 0 | 3,590 | 13 | 0.07 | - |
| memo_02.md | 0 | 3,900 | 14 | 0.125 | - |
| memo_03.md | 0 | 3,659 | 13 | 0.063 | - |
| memo_04.md | 0 | 3,181 | 17 | 0.141 | - |
| memo_05.md | 0 | 3,497 | 14 | 0.082 | - |
| memo_06.md | 0 | 3,745 | 14 | 0.139 | - |
| memo_07.md | 0 | 3,541 | 14 | 0.151 | - |
| memo_08.md | 0 | 3,925 | 16 | 0.145 | - |
| memo_09.md | 0 | 3,986 | 14 | 0.108 | - |
| memo_10.md | 0 | 3,336 | 16 | 0.101 | - |

## 교차 비교 (fall N=20 기준선)

| 지표 | fall(N=20) | rise | flat | fall_dirty |
|---|---|---|---|---|
| hedge_ratio | 0.101 | 0.1 | 0.05 | 0.11 |
| chars | 3599.2 | 3662.3 | 2735.1 | 3636 |
| figure_n | 52.0 | 47.1 | 32.5 | 14.5 |
| block_rate_pct | 0.0 | 0.0 | 0.0 | 0.0 |
| abstention_pct | 100.0 | 100.0 | - | - |
