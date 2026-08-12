"""서사 린트 v0 — report-contract-v0.md §10의 R01~R11 (정규식 수준).

사용: python3 lint.py <report.md>
- 수치 출처(R06)는 slice/out/bundle.json에서 화이트리스트를 구축해 대조.
- 출력: 위반 목록(BLOCK/WARN) + 종료 코드(BLOCK 있으면 1).
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
U = 0.1

HEDGE = r"(보인다|보입니다|보이며|가능성|수 있|것으로|추정|시사|정합|판단됨|개연)"


def build_whitelist(bundle):
    """번들의 모든 수치 → 허용 표기 집합(float, round 2)."""
    nums = set()

    def add(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            f = float(v)
            nums.add(round(f, 2))
            nums.add(round(abs(f), 2))
            # u 단위 → 억 표기
            nums.add(round(f * U, 2))
            nums.add(round(abs(f) * U, 2))
            # 건수 → 만 단위. 원시 건수는 반올림 인용("약 42.0만 건")이 관행이므로
            # 소수 1자리 반올림 변형까지 허용 — 억 단위 값은 이미 1자리라 불필요.
            if abs(f) >= 1000:
                q = f / 10000
                nums.update({round(q, 2), round(abs(q), 2),
                             round(q, 1), round(abs(q), 1)})

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        else:
            add(x)

    walk(bundle)
    # 항등식 파생치 1단계 (계약 R06 "Bundle 수치 + 등록 항등식 파생치"):
    # 같은 결과 블록 안의 형제 수치만 — ① 세그먼트 delta_u 2개의 합(부분합 인용,
    # 예: E1∩E2 타깃 가전+생활 -12.8억), ② 기간 딕셔너리(orders 등) 두 값의 차
    # (예: 주문 -4.4만 건). 블록 경계를 넘는 합산은 계약 §2가 금지하므로 넣지 않는다.
    from itertools import combinations
    for r in bundle.get("results", {}).values():
        if not isinstance(r, dict):
            continue
        deltas = [s["delta_u"] for s in r.get("segments", [])
                  if isinstance(s, dict) and isinstance(s.get("delta_u"), (int, float))]
        for a, b in combinations(deltas, 2):
            add(a + b)
        for v in r.values():
            if isinstance(v, dict):
                pv = [x for x in v.values()
                      if isinstance(x, (int, float)) and not isinstance(x, bool)]
                for a, b in combinations(pv, 2):
                    add(a - b)
        # 이벤트 행 내부의 선언-실측-참조 대조 차("산술 대조" 등급의 산출물)와
        # 중첩 플래그의 공유 슬라이스 기간 간 Δ — 계약이 장려하는 파생치.
        for e in r.get("events", []):
            trio = [e.get(k) for k in ("measured_slice_delta_u",
                                       "declared_magnitude_u", "reference_scale_u")]
            trio = [x for x in trio if isinstance(x, (int, float))]
            for a, b in combinations(trio, 2):
                add(a - b)
        for o in r.get("overlap_flags", []):
            tv = [x for x in (o.get("shared_slice_totals_u") or {}).values()
                  if isinstance(x, (int, float))]
            for a, b in combinations(tv, 2):
                add(a - b)
    # 날짜·서수 등 문맥 토큰:
    nums |= {float(x) for x in range(0, 32)}  # 일·월·소절 번호
    nums |= {2026.0, 2025.0}
    return nums


DATE_CTX = re.compile(r"(\d+)\s*(년|월|일|주차|장|절|번|개|건|회|명|호|페이지|p|%p)")


REFUSAL = (r"거부|차단|불가|보류|중단|기각|제공하지 못|(산출|제시|제공)할 수\s*없"
           r"|산출되지\s*않|판정.{0,6}(불가|유보)|오염|품질")
SOURCE_ATTR = r"신고|집계|확인|외부|영업|마케팅|팀"


def _headline_zone(text):
    parts = re.split(r"^## ", text, flags=re.M)
    return parts[1] if len(parts) >= 2 else text[:800]


def lint(text, whitelist, bundle=None):
    findings = []
    sents = [s.strip() for s in re.split(r"(?<=[.!?다])\s+|\n", text) if s.strip()]

    for i, s in enumerate(sents):
        # R01 인과 단정 — 단, 인프라 부재의 과정 설명("계획 기준선이 없기 때문")은
        # 지표 변화에 대한 인과 주장이 아니므로 제외. 명사 목록으로 좁게 한정한다.
        if re.search(r"(때문이|기인하|의 결과다|이 원인이다)", s) and not re.search(HEDGE, s) \
           and not re.search(r"(데이터|등록|기준선|빈티지|저장소|원장|집계|산출|필드)"
                             r"[^.]{0,20}없기 때문", s):
            findings.append(("BLOCK", "R01", i, "인과 단정(헤지 부재)", s[:60]))
        # R02 인과어+확인동사
        if re.search(r"(영향|원인|효과|탓)[이가은는의]?\s*\S{0,8}(확인|입증|규명|검증)(됐|되었|됨|된)", s):
            findings.append(("BLOCK", "R02", i, "인과어+확인동사 결합", s[:60]))
        # R03 배타적 단일원인
        if re.search(r"(전부|전적으로|만으로).{0,12}설명(한다|했다|된다)", s) \
           and not re.search(r"(가능|수 있)", s):
            findings.append(("BLOCK", "R03", i, "배타적 단일원인 단정", s[:60]))
        # R04 잔차 귀속
        if re.search(r"(나머지|잔여|남는|잔차).{0,20}(전부|모두|전액|곧).{0,20}(영향|귀속|때문|분)", s):
            findings.append(("BLOCK", "R04", i, "잔차 귀속", s[:60]))
        # R05 반사실 신수치
        if re.search(r"(없었다면|없었더라면|아니었다면)", s) and re.search(r"\d", s):
            findings.append(("WARN", "R05", i, "반사실 절 내 수치", s[:60]))
# R09는 계약 §10이 "불릿" 단위로 규정 — 문장 분할이 반증 수치를 다음 문장으로
# 떼어내면 오탐이므로 행 단위로 검사한다 (lint() 본문 하단).
        # R11 미래 단정
        if re.search(r"(회복된다|돌아온다|환입된다)[.\s]", s) \
           and not re.search(r"(되면|경우|전제|시\b|예정)", s):
            findings.append(("WARN", "R11", i, "조건절 없는 미래 단정", s[:60]))
        # R12 분모 명시 (계약 v0.1-5): 'X 감소분의 Y%' 형태는 분모 오라벨 위험
        if re.search(r"(감소분의|증가분의|하락분의)\s*\d", s):
            findings.append(("WARN", "R12", i, "분모 명시 검토 — 'X 중 Y%' 구문 권장", s[:60]))

    # R06 수치 출처 (문서 전체) — 콤마 자릿수 표기("364,800")를 한 토큰으로 잡는다
    for m in re.finditer(r"[+\-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[+\-]?\d+(?:\.\d+)?", text):
        tok = m.group().replace(",", "")
        span = text[max(0, m.start() - 8):m.end() + 8]
        if DATE_CTX.search(span) or re.search(r"\d{4}-\d{2}", span) or "/" in span:
            continue  # 날짜·서수 문맥 제외
        val = round(abs(float(tok)), 2)
        if val not in whitelist:
            findings.append(("BLOCK", "R06", -1, "번들 미등재 수치", f"{tok} (문맥: …{span}…)"))

    # R09 수치 없는 기각 (불릿=행 단위 — 계약 §10)
    for ln in text.splitlines():
        ls = ln.strip()
        if not ls:
            continue
        if re.search(r"(아님|해당 없음|설명력 약|아니다)[.,)\s]", ls + " ") \
           and re.search(r"^[-*•]|—", ls) and not re.search(r"\d", ls):
            findings.append(("BLOCK", "R09", -1, "수치 없는 기각", ls[:60]))

    # R10 분리불가 → 해소경로 (문서 수준)
    if re.search(r"(분리(가|는)?\s*(안|불가|어렵)|특정할\s*(수 없|근거)|배분\S{0,10}(미확정|어렵))", text):
        if not re.search(r"(요청|필요 데이터|필요한 데이터|확인 사항|후속)", text):
            findings.append(("BLOCK", "R10", -1, "분리불가 선언에 해소경로 부재", "-"))

    # R08 시사 근거 동반 (완화: 헤지 문장에 수치·이벤트·기간 토큰 없으면 경고)
    for i, s in enumerate(sents):
        if re.search(r"(로 보인다|로 보입니다|가능성이|것으로 보)", s):
            if not re.search(r"\d|프로모션|쿠폰|폐점|발주|행사|페스타|브랜드|라이브", s):
                findings.append(("WARN", "R08", i, "근거 토큰 없는 시사 문장", s[:60]))

    # ── v0.2 조항 (번들 문맥 필요 — bundle 미전달 시 생략) ────────────────
    if bundle is not None:
        results = bundle.get("results", {})
        # R13 게이트 거부의 요약 의무 (계약 §12-1): 핵심 연산(분해 축) 거부 회차에는
        # 요약(첫 섹션)이 거부 사실을 명시해야 한다.
        refused = [k for k, v in results.items()
                   if k.startswith("contrib:") and isinstance(v, dict)
                   and v.get("status") != "result"]
        if refused and not re.search(REFUSAL, _headline_zone(text)):
            findings.append(("BLOCK", "R13", -1,
                             "게이트 거부 회차의 요약에 거부 명시 부재",
                             f"거부된 연산: {', '.join(refused)}"))
        # R14 보류 회차의 선언치 출처 부기 (계약 §12-2): 실측이 보류된 이벤트의
        # 선언치·참조치를 인용하는 문장에는 외부 신고 출처가 동반돼야 한다.
        ev = results.get("events", {})
        for e in (ev.get("events", []) if isinstance(ev, dict) else []):
            if e.get("measurement_status") != "suspended":
                continue
            for key in ("declared_magnitude_u", "reference_scale_u"):
                v = e.get(key)
                if not isinstance(v, (int, float)):
                    continue
                # 숫자 경계 강제 — "45.5억" 속의 "5.5" 같은 부분 문자열 오폭 방지
                pat = re.compile(r"(?<![\d.])" + re.escape(f"{abs(v) * U:.1f}") + r"(?![\d])")
                for i, s in enumerate(sents):
                    if pat.search(s) and not re.search(SOURCE_ATTR, s):
                        findings.append(("WARN", "R14", i,
                                         f"{e['id']} 선언치 인용에 출처 부기 부재", s[:60]))

    return findings


def main():
    path = Path(sys.argv[1])
    text = path.read_text()
    bundle = json.loads((HERE / "out" / "bundle.json").read_text())
    findings = lint(text, build_whitelist(bundle), bundle)
    blocks = [f for f in findings if f[0] == "BLOCK"]
    for sev, rule, i, why, ctx in findings:
        print(f"[{sev}] {rule} (문장 {i}): {why} — {ctx}")
    print(f"\n요약: BLOCK {len(blocks)}건, WARN {len(findings) - len(blocks)}건")
    sys.exit(1 if blocks else 0)


if __name__ == "__main__":
    main()
