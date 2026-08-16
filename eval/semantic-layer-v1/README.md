# Semantic layer agent evaluation v1

이 디렉터리는 H2 — 실행 계약이 agent 오류를 줄이는가 — 를 C0/C1/C2 조건에서 비교하기
위한 공통 사례와 채점 계약이다.

## 조건

- `raw`: 원시 데이터와 자유 계산 도구
- `advisory`: 문서·레지스트리를 읽을 수 있으나 호출 제한 없음
- `enforced`: Query Spec과 등록 연산자·gate·budget을 강제

`cases.json`은 세 조건에서 동일하게 사용한다. 현재 자동 실행기는 `enforced` 기준선을
만든다. raw/advisory는 동일한 case ID를 가진 agent trace를 수집한 뒤 단계별 필드를 같은
rubric으로 채점한다.

## 단계별 관측치

1. resolution: metric ID와 version
2. binding: scope, focal period, comparison, vintage
3. selection: selected/rejected operator
4. execution: status, 값, gate, budget
5. persistence: result kind와 provenance
6. reporting: numeric source와 label ceiling

최종 문장만으로 채점하지 않는다. 잘못된 조회가 우연히 맞는 문장을 낳거나, 올바른 조회가
작문에서 과장되는 두 오류를 구분해야 한다.

## 실행

```bash
python3 slice/eval_semantic.py
```

첫 increment의 성공 기준은 enforced 조건에서 scope·기간·vintage·등록·예산 사례가 전부
기대 상태로 닫히는 것이다. 이 결과는 C1보다 우수하다는 증거가 아니며, C0/C1 반복 실행이
채워져야 H2 비교가 완성된다.

## 비교 실험 하니스

조건별 capability와 목표 반복 수는 `conditions.json`, 공통 관측 형식은
`schemas/agent-trace-v1.schema.json`에 있다. 실행 패킷은 다음과 같이 만든다.

```bash
python3 slice/eval_h2.py packet \
  --condition raw \
  --case-id scope-online-change \
  --attempt 1
```

동일한 방식으로 `advisory`, `enforced` 패킷을 만든다. 목표 반복은 조건×사례당 5회다.
패킷의 capability manifest는 실험 runner가 실제로 격리해야 한다. scorer의 `access_log`
검사는 사후 감사이며, 거짓 access log를 방지하는 보안 경계가 아니다.

외부 runner에 넘길 전체 batch는 다음처럼 만든다. `--attempts`를 생략하면
`conditions.json`의 `target_attempts_per_case`를 사용한다.

```bash
python3 slice/eval_h2.py prepare-batch \
  --out-dir /tmp/groot-h2-packets \
  --condition raw \
  --condition advisory
```

C2의 결정론적 실행 기준 trace는 다음처럼 수집·집계한다.

```bash
python3 slice/eval_h2.py collect-enforced --out-dir /tmp/groot-h2-c2 --attempt 1
python3 slice/eval_h2.py summary --traces-dir /tmp/groot-h2-c2
```

현재 C2 기준은 resolution 10/10, 적용 가능한 binding·selection·execution·persistence
각 7/7이다. 정상 Result Envelope가 있는 5건의 reporting은 5/5 통과하며, 입력 보류·조기
반문 5건은 `not_applicable`이다. 이는 결정론적 실행 계층 기준선이며, C0/C1 trace를 격리된
독립 agent로 수집하기 전에는 H2 효과 크기나 우월성을 주장할 수 없다.

외부 agent가 남긴 trace는 다음처럼 채점한다.

```bash
python3 slice/eval_h2.py score path/to/trace.json
python3 slice/eval_h2.py summary --traces-dir path/to/traces
```

## 격리 Codex runner

`slice/run_h2_isolated.py`는 raw/advisory condition마다 허용 파일만 임시 workspace에 복사한다.
macOS Seatbelt는 원 프로젝트 디렉터리 읽기를 차단하고, 내부 Codex는 read-only sandbox에서
ephemeral session으로 실행한다. user config, project rules, web search도 비활성화한다.

```bash
python3 slice/run_h2_isolated.py prepare --condition raw
python3 slice/run_h2_isolated.py run \
  --packet /tmp/groot-h2-packets-v2/raw/level-scope-online__01.json \
  --out-dir /tmp/groot-h2-traces \
  --model gpt-5.6-terra \
  --reasoning medium
```

`run`은 허용된 ledger·plan·event fixture 또는 advisory 계약 문서를 외부 model endpoint에
전송할 수 있다. 따라서 실제 호출 전 데이터 반출과 모델 사용량에 대한 명시적 승인이 필요하다.
runner가 저장한 JSONL, 정규화 trace, score, isolation audit를 함께 보존해야 한다.

v3 전체 batch는 다음 명령으로 순차 실행한다. `--resume`은 이미 trace가 있는 packet을 건너뛰며,
`--max-runs`로 일부만 실행할 수 있다. 공통 계약과 resource payload를 prompt 앞부분에 고정해
같은 condition 반복에서 prefix cache가 재사용될 수 있게 한다.

```bash
python3 slice/run_h2_isolated.py batch \
  --packets-dir /tmp/groot-h2-packets-v4 \
  --out-dir /tmp/groot-h2-traces-v4 \
  --condition raw \
  --condition advisory \
  --model gpt-5.6-terra \
  --reasoning medium \
  --resume
```

첫 wave는 모든 사례의 첫 번째 반복만 20회 실행한다. 이상이 없으면 `--attempt`를 제거하고
같은 output directory에 `--resume`으로 나머지 80회를 채운다.

```bash
python3 slice/run_h2_isolated.py batch \
  --packets-dir /tmp/groot-h2-packets-v4 \
  --out-dir /tmp/groot-h2-traces-v4 \
  --condition raw \
  --condition advisory \
  --attempt 1 \
  --model gpt-5.6-terra \
  --reasoning medium
```

### Smoke v1 결과

`level-scope-online`을 `gpt-5.6-terra`, reasoning medium으로 raw/advisory 각 1회 실행했다.
두 조건 모두 1580u와 원장 source를 맞췄고 인과 claim을 만들지 않아 reporting의 공통 rubric은
통과했다. advisory는 metric ID/version과 `metric_level` 선택까지 맞췄다.

그러나 v2 packet의 binding·execution template가 빈 객체 형태를 충분히 지정하지 않아 agent가
Query Spec 전체와 자체 execution 필드명을 기록했다. 이 때문에 의미상 맞은 일부 관측도 구조
불일치로 실패 처리됐다. v3 packet은 모든 단계의 정규화 필드와 status 의미를 명시하고,
raw/advisory reporting에서 C2 전용 report wrapper를 요구하지 않는다. 따라서 smoke v1은 runner
검증 자료이지 H2 조건 효과 표본에는 포함하지 않는다.

v3 형식 smoke에서도 같은 사례를 조건별 1회 실행했다. raw는 공통 구조와 reporting을 통과했고,
advisory는 resolution·binding·selection·reporting을 통과했다. 두 조건 모두 1580u를 맞췄지만
execution rubric이 C2 내부 bundle key와 value path를 요구해 실패했다. v4는 조건 공통
`primary_value`를 추가하고, 내부 `result_key`·`values` 검사는 enforced 조건에만 적용한다.
따라서 v3 smoke도 형식 개발 자료이며 비교 표본에서 제외한다.

v4 최종 smoke에서 raw는 `primary_value=1580`과 reporting을 통과했고, advisory는
resolution·binding·selection·execution·reporting을 모두 통과했다. advisory persistence는
강제 hash·snapshot·result provenance가 없어 실패했으며 이는 H2가 측정하려는 C1과 C2의 실제
차이다. raw가 일반 성공 표현 `success`를 쓴 경우는 공통 상태 `result`로 정규화한다. v4부터
정식 비교 표본을 수집한다.

### v4 attempt-1 wave

10개 사례를 raw/advisory에서 각 1회 실행한 첫 정식 wave는 20/20 trace 생성, batch error 0,
capability violation 0이었다. raw 대비 advisory의 pass 수는 resolution 1→8, binding 0→4,
selection 2→5, execution 3→5였고 persistence는 양쪽 모두 0/7이었다. reporting은 양쪽 3/5다.

실제 오산도 보존됐다. plan vintage 사례와 category scope 변화 사례에서 양 조건 모두 기대값과
다른 값을 계산했다. 집계와 usage는 `wave-v4-attempt1.json`에 고정했다. 이는 attempt 1의 중간
결과이며 나머지 4회 반복 전에는 H2 효과 크기나 우월성을 주장하지 않는다.

### v4 final wave

attempt 1–5의 정식 표본은 raw 50건과 advisory 50건이다. runner error와 capability violation은
0건이며, 조건별 1건씩은 완성 trace를 `trace_template` 아래 감싸 반환해 출력 계약 실패로
채점했다. invalid trace는 전체 실패이자 해당 사례의 적용 가능한 모든 단계 실패로 분모에
포함한다.

| 단계 | raw | advisory | enforced 기준선 |
|---|---:|---:|---:|
| resolution | 7/50 (14.0%) | 40/50 (80.0%) | 10/10 |
| binding | 0/35 (0.0%) | 14/35 (40.0%) | 7/7 |
| selection | 10/35 (28.6%) | 25/35 (71.4%) | 7/7 |
| execution | 11/35 (31.4%) | 23/35 (65.7%) | 7/7 |
| persistence | 0/35 (0.0%) | 0/35 (0.0%) | 7/7 |
| reporting | 12/25 (48.0%) | 14/25 (56.0%) | 5/5 |

raw→advisory의 50개 matched pair에서 전체 통과는 7→14건이었다(개선 8, 퇴행 1,
exact McNemar 양측 p=0.0391). 단계별 개선은 resolution·binding·selection·execution에서
뚜렷했지만 persistence에는 효과가 없고 reporting 차이도 작았다. 반복 5회가 같은 10개
case prompt에 묶여 있으므로 p-value는 탐색적 지표이며 독립 모집단 추론으로 해석하지 않는다.

핵심 H2 비교인 advisory→enforced는 전체 통과율 28%→100%, 적용 가능한 persistence
0%→100%였다. C2는 10개 고유 사례의 결정론적 실행 기준선이므로 C1과의 추론 통계는 계산하지
않는다. 결론은 이 고정 매출 corpus에서 실행 계약이 advisory-only에 남은 binding·산술·저장·
보고 오류를 제거했다는 범위로 한정한다. 전체 집계·사용량·해석은
`wave-v4-final.json`에 고정했다.

현재 scorer로 파생 score를 재생성하고 paired 비교를 확인하는 명령은 다음과 같다.

```bash
python3 slice/eval_h2.py rescore --traces-dir /tmp/groot-h2-traces-v4
python3 slice/eval_h2.py compare --traces-dir /tmp/groot-h2-traces-v4
```

사용자가 기대하는 대표 질문·수치·답변 상한의 제품 회귀는 별도 golden set으로 관리한다.

```bash
python3 slice/eval_golden.py
```

`eval/golden-set-v1/cases.json`의 `ready`만 현재 통과 수치에 포함하며, `challenge`와
`planned`는 구현 완료로 간주하지 않는다.
