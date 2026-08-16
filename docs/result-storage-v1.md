# Materialized result와 staleness v1

## 경계

저장 가능한 대상은 정상 `result`이면서 `operator_ref`가 있는 Result Envelope다. clarification,
suspended, out_of_domain 결과나 provenance 없는 임의 객체는 materialize하지 않는다.

저장 정체성은 다음 네 값으로 결정한다.

- `query_spec_hash`
- `result_key`
- `operator_ref`
- `input_snapshot_ref`

동일 정체성은 동일 `result_id`를 만들며, 기존 경로에 다른 결과를 덮어쓰지 않는다. 저장 객체의
기계 계약은 `schemas/stored-result-v1.schema.json`, 구현은 `slice/result_store.py`다.

## Staleness policies

- `recompute_on_source_change`: 현재 input snapshot hash가 같으면 fresh, 다르면 stale다. 현재
  hash가 없으면 추측하지 않고 suspended다.
- `expires_at`: 명시한 평가 시각이 만료 시각 이상이면 stale다.
- `immutable_snapshot`: 저장 당시 스냅샷에 대해 유효한 동결 결과다. `fresh`라고 부르지 않으며
  최신 상태를 주장하지 않는다.

판정은 `StalenessAssessment` Result Envelope를 반환하고 `데이터 확인` 상한을 가진다.

## 아직 없는 것

- 원천 connector에서 현재 snapshot hash를 얻는 capability
- 보존 기간, 접근 제어, 동시성 제어가 있는 외부 저장소

현재 pilot에는 in-memory `ResultCatalog`가 있어 `latest`, alias, `result_id`를 해소하며,
metric catalog의 현재 fixture snapshot과 저장 시점 snapshot을 비교한다. 따라서 golden set의
“이 분석 결과가 아직 유효한가?”는 ready다. 다만 이 경로는 프로세스 외부 영속 catalog나 실제
원천 connector를 뜻하지 않으며, 그 기능은 여전히 후속 범위다.
