# Bosch Production Line Performance — 데이터 설명

작성 2026-08-18. 원본: Kaggle 대회 [Bosch Production Line Performance]
(bosch-production-line-performance). 부품이 Bosch 생산 라인을 통과하며 측정된
값들로, 품질 검사 불합격(`Response = 1`) 부품의 예측이 원 대회의 과제였다.

> **라이선스 주의**: Kaggle 대회 규정상 데이터 재배포가 금지된다. 이 저장소는
> `data/` 전체와 `*.duckdb`를 gitignore하며, 적재 스크립트
> ([slice/load_bosch.py](../slice/load_bosch.py))와 이 설명 문서만 커밋한다.

## 1. 파일 구성 (실측)

`data/bosch-production-line-performance/`에 zip 7개(총 696MB, 해제 시 약
14.4GB). 파일은 feature 종류별로 분리되어 있다:

| 파일 | 행 × 열 (실측) | 내용 |
|---|---|---|
| train_numeric.csv | 1,183,747 × 970 | 수치 측정값 + **Response**(정답) |
| train_date.csv | 1,183,747 × 1,157 | 각 측정의 시각 (익명 단위) |
| train_categorical.csv | 1,183,747 × 2,141 | 범주 측정값 (예: `T1`) |
| test_numeric.csv | 1,183,748 × 969 | 평가용 — Response 없음 |
| test_date.csv | 1,183,748 × 1,157 | 〃 |
| test_categorical.csv | 1,183,748 × 2,141 | 〃 |
| sample_submission.csv | — | 제출 형식 예시 |

## 2. 열 이름 규약

`L{라인}_S{스테이션}_{F|D}{번호}` — 예: `L3_S36_F3939`는 라인 3, 스테이션
36의 feature 3939. date 열의 끝 번호는 **직전 feature 번호에 대응**한다:
`L0_S0_D1`은 `L0_S0_F0`이 측정된 시각이다.

> **시간 단위 주의**: date 값은 실제 달력 시각이 아니라 **익명화된 시간
> 단위**다(실측 범위 0 ~ 1718.48). 절대 시점·요일·월을 알 수 없고, 순서와
> 간격만 의미가 있다.

## 3. 실측 구조

### 라인·스테이션 (train 기준, 전체 스테이션 52개)

| 라인 | 스테이션 수 | 통과 부품 | 불량 부품 |
|---|---:|---:|---:|
| L0 | 24 | 916,029 | 4,924 |
| L1 | 2 | 79,318 | 413 |
| L2 | 3 | 357,019 | 2,575 |
| L3 | 23 | 1,183,158 | 6,875 |

L3는 사실상 전 부품(99.95%)이 통과하는 공통 후공정이다.

### 정답 불균형

전체 1,183,747개 중 불량 6,879개 — **불량률 0.581%**. 원 대회가 어려웠던
두 축(초고차원 feature + 극단 불균형) 중 하나다.

### 경로·시간 (part_summary_train 실측)

- 부품당 평균 12.0개 스테이션 통과 (최소 1, 최대 23)
- 통과 소요(익명 단위) 평균 6.91
- 주요 라인 경로: `[L0→L3]` 802,045개(불량률 0.508%) ·
  `[L2→L3]` 173,922개(0.795%) · `[L0→L2→L3]` 112,867개(0.747%) ·
  `[L1→L2→L3]` 69,283개(0.498%) · `[L3]` 단독 15,008개(**1.099%**)

### 주목할 실측 관찰

- **L3_S32가 압도적 핫스팟**: 24,543개 통과 중 1,106개 불량(**4.506%** —
  기저율의 7.8배). 이어서 L3_S38(0.781%), L2_S26(0.747%).
- L3 단독 경로(전공정 기록 없음)의 불량률이 두 배 가까이 높다 — 기록
  누락과 품질의 상관이라는 가설 후보.

## 4. DuckDB 적재 결과

`data/bosch-production-line-performance/bosch.duckdb` (5.6GB, 적재 118초).

**원본 테이블 6종** — CSV와 동일 스키마 (`Id` BIGINT, 수치/date DOUBLE,
범주 VARCHAR, `Response` INTEGER).

**파생 테이블 5종** (열 이름 규약을 이용해 생성):

| 테이블 | 정의 |
|---|---|
| `part_station_{train,test}` | 부품 × 방문 스테이션 long 형식: `Id, line, station, station_time`. 각 스테이션의 **첫 date 열**을 방문·시각의 대표로 사용(원 대회의 표준 기법) |
| `part_summary_{train,test}` | 부품별 요약: `start_time, end_time, duration, n_stations, lines_visited` (+train은 `response`) |
| `station_stats_train` | 스테이션별 `parts, failures, failure_rate` |
| `line_stats_train` | 라인별 통과·불량 집계 |

재현:

```bash
cd data/bosch-production-line-performance && for f in *.zip; do unzip -o "$f"; done
cd ../../slice && ../.venv/bin/python3 load_bosch.py
```

## 5. groot-cal 온보딩 관점

이 데이터는 지금까지의 fixture·날씨 데이터와 **질적으로 다른 온보딩 시험**이다:

- **지표 후보**: 불량률 = rate(Σ`Response` / Σ부품 수 — 분모 가중 집계가
  강제되는 정확히 그 유형), 검사 부품 수 = count, 통과 소요 = duration
  분포(현재 미등록 수학).
- **차원 후보**: line·station(52값 — 현 차원 열거 상한을 시험),
  lines_visited 경로(합성 차원 — 미등록 개념).
- **시간축 충돌**: date가 달력이 아닌 익명 단위이므로 **month/iso_week
  window를 등록할 수 없다**. 등록 calendar 계약(E-007/E-023)의 첫 반례 —
  선택지는 (a) 익명 단위 구간(예: 100단위 버킷)의 window 등록 확장,
  (b) 시간축 없는 수준·스테이션 비교만 온보딩. 결정이 필요한 지점이다.
- 원본 970~2,141열의 익명 feature 자체는 semantic layer의 등록 대상이
  아니다 — 등록 가능한 것은 파생 수준(라인·스테이션·불량·경로)의 의미다.

## 6. 온보딩 결과 (E-027, 2026-08-18)

(a) 방향 — **익명 단위 구간 window(`unit_bucket`, 폭 100)** 를 계약에
등록하고, 두 지표를 (구간 × 라인 경로) 집계 grain(119행)으로 온보딩했다.
집계 grain에서도 rate의 Σ분자/Σ분모와 count의 Σ는 정확하다.

- **불량률** `quality.failure_rate` (rate, 분모 가중): "U0300 구간 불량률은?"
  → 1.0348% (591/57,110). 변화 분해는 rate 계약이 거부.
- **검사 부품 수** `quality.inspected_parts` (count): "U0300 대비 U0400
  검사수가 왜 변했나?" → Δ−11,400의 경로 축 분해.
- **달력 질의는 이름을 밝혀 거부**: "3월 불량률은?" → month is not
  registered for this source — E-027부터 month는 특권이 아니라 등록 대상이다.

온보딩이 적발한 시스템 공백 2건(수리·테스트 고정): ① 차원 값이 다른 값의
부분 문자열일 때("L0" ⊂ "L0-L3") 중복 filter 바인딩 → 전역 최장 우선·비중복
매칭, ② 같은 차원의 상충 filter가 침묵 last-wins로 실행되던 projection →
명시 거부. 스테이션(52값) 차원의 부품 grain 온보딩은 다중 grain 설계가 필요해
다음 증분으로 남긴다.
