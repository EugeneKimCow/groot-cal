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
            # 건수 → 만 단위
            if abs(f) >= 1000:
                nums.add(round(f / 10000, 2))

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
    # 항등식 파생 허용치: 번들 내 u값들의 합·차는 이미 대부분 번들에 존재. 날짜·서수 등 문맥 토큰:
    nums |= {float(x) for x in range(0, 32)}  # 일·월·소절 번호
    nums |= {2026.0, 2025.0}
    return nums


DATE_CTX = re.compile(r"(\d+)\s*(년|월|일|주차|장|절|번|개|건|회|명|호|페이지|p|%p)")


def lint(text, whitelist):
    findings = []
    sents = [s.strip() for s in re.split(r"(?<=[.!?다])\s+|\n", text) if s.strip()]

    for i, s in enumerate(sents):
        # R01 인과 단정
        if re.search(r"(때문이|기인하|의 결과다|이 원인이다)", s) and not re.search(HEDGE, s):
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
        # R09 수치 없는 기각
        if re.search(r"(아님|해당 없음|설명력 약|아니다)[.,)\s]", s + " ") \
           and re.search(r"^[-*•]|—", s) and not re.search(r"\d", s):
            findings.append(("BLOCK", "R09", i, "수치 없는 기각", s[:60]))
        # R11 미래 단정
        if re.search(r"(회복된다|돌아온다|환입된다)[.\s]", s) \
           and not re.search(r"(되면|경우|전제|시\b|예정)", s):
            findings.append(("WARN", "R11", i, "조건절 없는 미래 단정", s[:60]))

    # R06 수치 출처 (문서 전체)
    for m in re.finditer(r"[+\-]?\d+(?:\.\d+)?", text):
        tok = m.group()
        span = text[max(0, m.start() - 8):m.end() + 8]
        if DATE_CTX.search(span) or re.search(r"\d{4}-\d{2}", span) or "/" in span:
            continue  # 날짜·서수 문맥 제외
        val = round(abs(float(tok)), 2)
        if val not in whitelist:
            findings.append(("BLOCK", "R06", -1, "번들 미등재 수치", f"{tok} (문맥: …{span}…)"))

    # R10 분리불가 → 해소경로 (문서 수준)
    if re.search(r"(분리(가|는)?\s*(안|불가|어렵)|특정할\s*(수 없|근거)|배분\S{0,10}(미확정|어렵))", text):
        if not re.search(r"(요청|필요 데이터|필요한 데이터|확인 사항|후속)", text):
            findings.append(("BLOCK", "R10", -1, "분리불가 선언에 해소경로 부재", "-"))

    # R08 시사 근거 동반 (완화: 헤지 문장에 수치·이벤트·기간 토큰 없으면 경고)
    for i, s in enumerate(sents):
        if re.search(r"(로 보인다|로 보입니다|가능성이|것으로 보)", s):
            if not re.search(r"\d|프로모션|쿠폰|폐점|발주|행사|페스타|브랜드|라이브", s):
                findings.append(("WARN", "R08", i, "근거 토큰 없는 시사 문장", s[:60]))

    return findings


def main():
    path = Path(sys.argv[1])
    text = path.read_text()
    bundle = json.loads((HERE / "out" / "bundle.json").read_text())
    findings = lint(text, build_whitelist(bundle))
    blocks = [f for f in findings if f[0] == "BLOCK"]
    for sev, rule, i, why, ctx in findings:
        print(f"[{sev}] {rule} (문장 {i}): {why} — {ctx}")
    print(f"\n요약: BLOCK {len(blocks)}건, WARN {len(findings) - len(blocks)}건")
    sys.exit(1 if blocks else 0)


if __name__ == "__main__":
    main()
