"""⑧작문 루프 N=20 측정 하네스 — 생성 분산·BLOCK율.

사용: python3 loop8_measure.py [memo_dir]   (기본: out/loop8)

측정 축:
  A. 린트 1회차 — BLOCK율(메모 단위), 규칙별 발화 빈도 (lint.py 재사용)
  B. 결론 안정성 — 몸통 귀속(신규), 중첩 기권, 잔차 논법 시도, 헤드라인 조건부 어법
  C. 계약 v0.1 준수(린트 미구현 조항의 수동 검사) — defense_lines, 계획 대비,
     감사 용어 본문 침입, 표 상한(CFO=0), T5, 분모 구문
  D. 형태·수치 분산 — 분량, 헤지 비율, 수치 집합(핵심/주변 수치, 쌍별 Jaccard)

출력: <memo_dir>/metrics.json, <memo_dir>/measurement.md
"""
import json
import re
import statistics
import sys
from itertools import combinations
from pathlib import Path

from lint import lint, build_whitelist, HEDGE, DATE_CTX

HERE = Path(__file__).parent


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?다])\s+|\n", text) if s.strip()]


def extract_figures(text):
    """R06과 같은 필터로 수치 토큰 추출 — 단, 트리비얼 정수(0~31, 연도)는 제외."""
    figs = set()
    for m in re.finditer(r"[+\-]?\d+(?:\.\d+)?", text):
        span = text[max(0, m.start() - 8):m.end() + 8]
        # 날짜 단위 검사는 토큰 자신의 접미(뒤 8자)에만 — 앞 이웃("7월 매출은
        # 386.0억")의 날짜가 토큰을 오염시키지 않게 한다. yyyy-mm·'/'는 전체 span.
        own = text[m.start():m.end() + 8]
        if DATE_CTX.search(own) or re.search(r"\d{4}-\d{2}", span) or "/" in span:
            continue
        tok = m.group()
        val = round(abs(float(tok)), 2)
        # 소수점 없는 0~31은 서수·개수(트리비얼)로 간주 — "28.0억"처럼 소수점이
        # 찍힌 정수값 금액은 유지한다.
        if val in {2025.0, 2026.0} or ("." not in tok and 0 <= val <= 31):
            continue
        figs.add(val)
    return figs


def headline_zone(text):
    """첫 번째 '##' 섹션(요약)의 본문. 헤딩이 없으면 앞 800자."""
    parts = re.split(r"^## ", text, flags=re.M)
    if len(parts) >= 2:
        return parts[1]
    return text[:800]


def footer_split(text):
    """말미 각주(마지막 '---' 이후, 문서 말미 30% 내에 있을 때)와 본문 분리."""
    idx = text.rfind("\n---")
    if idx > len(text) * 0.7:
        return text[:idx], text[idx:]
    return text, ""


def analyze(path, whitelist):
    text = path.read_text()
    sents = sentences(text)
    findings = lint(text, whitelist)
    blocks = [f for f in findings if f[0] == "BLOCK"]
    warns = [f for f in findings if f[0] == "WARN"]
    hz = headline_zone(text)
    body, footer = footer_split(text)

    conditional_hl = bool(re.search(r"(판별|확인|해소|특정)[^.]{0,8}(전까지|되기까지)|전까지는", hz))
    transient_hl = bool(re.search(r"일시[^.]{0,14}(성격|요인)[^.]{0,12}보(입니다|인다|이며)", hz))

    m714 = [text[max(0, m.start() - 45):m.end() + 8] for m in re.finditer(r"71\.4", text)]

    return {
        "file": path.name,
        # A. 린트
        "block_n": len(blocks),
        "warn_n": len(warns),
        "rules_block": sorted(f[1] for f in blocks),
        "rules_warn": sorted(f[1] for f in warns),
        "block_detail": [f"{f[1]}: {f[4][:70]}" for f in blocks],
        # B. 결론 안정성
        "attrib_sinkyu_hl": bool(re.search(r"신규", hz)),
        "cites_body_280": "28.0" in text,       # 신규 Δ
        "cites_online_sinkyu_240": "24.0" in text,  # 온라인×신규 Δ
        "overlap_abstained": bool(re.search(
            r"분리(가|는|를)?\s*(안 |불가|어렵|되지 않)|특정할\s*수 없|특정하지 못|나눌 수 없"
            r"|(나누|나눠|배분|분리)[^.]{0,60}(할 수 없|불가|무리|않|근거 없)", text)),
        "residual_attempt": any(f[1] == "R04" for f in blocks),
        "conditional_headline": conditional_hl,
        "bare_transient_headline": transient_hl and not conditional_hl,
        # C. 계약 v0.1 수동 검사
        "defense_lines": bool(re.search(
            r"답하(십시오|시면|시기|시길)|답변하(십시오|시)|방어 대사|이렇게 답|답변용|문안"
            r"|다음과 같이 (답|말씀)", text)),
        "plan_ref": bool(re.search(r"계획\s*(대비|과의)|달성률", text)),
        "audit_jargon_body_n": len(re.findall(r"항등식|증거 번들|검산|번들", body)),
        "has_table": len(re.findall(r"^\s*\|.*\|", body, flags=re.M)) >= 2,
        "t5_upper_bound": bool(re.search(r"확실한 것은|여기까지", text)),
        "denominator_x_of_y": len(re.findall(r"중\s*\d+(?:\.\d+)?\s*%", text)),
        "ctx_714": m714,
        # D. 형태
        "chars": len(text),
        "sent_n": len(sents),
        "hedge_ratio": round(sum(1 for s in sents if re.search(HEDGE, s)) / max(1, len(sents)), 3),
        "figure_n": len(extract_figures(text)),
        "_figures": sorted(extract_figures(text)),
    }


def agg(rows):
    n = len(rows)
    figs = [set(r["_figures"]) for r in rows]
    jac = [len(a & b) / len(a | b) for a, b in combinations(figs, 2)] if n >= 2 else []
    freq = {}
    for fs in figs:
        for v in fs:
            freq[v] = freq.get(v, 0) + 1
    core = sorted(v for v, c in freq.items() if c >= 0.9 * n)
    fringe = sorted((v for v, c in freq.items() if c <= 0.2 * n))
    rule_hist = {}
    for r in rows:
        for rule in r["rules_block"]:
            rule_hist[rule] = rule_hist.get(rule, {"BLOCK": 0, "WARN": 0})
            rule_hist[rule]["BLOCK"] += 1
        for rule in r["rules_warn"]:
            rule_hist[rule] = rule_hist.get(rule, {"BLOCK": 0, "WARN": 0})
            rule_hist[rule]["WARN"] += 1

    def pct(key):
        return round(100 * sum(1 for r in rows if r[key]) / n, 1)

    def stats_of(key):
        vals = [r[key] for r in rows]
        return {"mean": round(statistics.mean(vals), 1),
                "sd": round(statistics.pstdev(vals), 1),
                "min": min(vals), "max": max(vals)}

    return {
        "n": n,
        "lint": {
            "memo_block_rate_pct": pct("residual_attempt") if False else round(
                100 * sum(1 for r in rows if r["block_n"] > 0) / n, 1),
            "blocks": stats_of("block_n"),
            "warns": stats_of("warn_n"),
            "rule_hist_memos": rule_hist,  # 규칙별: 그 규칙이 발화한 메모 수(건수 아님)
        },
        "conclusion": {
            "attrib_sinkyu_hl_pct": pct("attrib_sinkyu_hl"),
            "overlap_abstained_pct": pct("overlap_abstained"),
            "residual_attempt_pct": pct("residual_attempt"),
            "conditional_headline_pct": pct("conditional_headline"),
            "bare_transient_headline_pct": pct("bare_transient_headline"),
        },
        "contract_v01": {
            "defense_lines_pct": pct("defense_lines"),
            "plan_ref_pct": pct("plan_ref"),
            "audit_jargon_body": stats_of("audit_jargon_body_n"),
            "table_violation_pct": pct("has_table"),
            "t5_pct": pct("t5_upper_bound"),
        },
        "form": {
            "chars": stats_of("chars"),
            "hedge_ratio": {"mean": round(statistics.mean(r["hedge_ratio"] for r in rows), 3),
                            "sd": round(statistics.pstdev(r["hedge_ratio"] for r in rows), 3)},
            "figure_n": stats_of("figure_n"),
            "figure_jaccard": {"mean": round(statistics.mean(jac), 3) if jac else None,
                               "min": round(min(jac), 3) if jac else None},
            "core_figures_ge90pct": core,
            "fringe_figures_le20pct_n": len(fringe),
        },
    }


def render_md(rows, a):
    L = []
    L.append("# ⑧작문 루프 N=%d 측정 — 생성 분산·BLOCK율\n" % a["n"])
    L.append("입력 고정: bundle.json(as_of 2026-08-06) + report-contract-v0.md(v0.1). "
             "표본·과거 보고서·린트 차단. 1회 작성(수정 루프 없음).\n")
    L.append("## A. 린트 1회차\n")
    L.append(f"- **메모 단위 BLOCK율: {a['lint']['memo_block_rate_pct']}%** "
             f"(BLOCK ≥1건인 메모 / 전체)")
    L.append(f"- BLOCK 건수: 평균 {a['lint']['blocks']['mean']} ± {a['lint']['blocks']['sd']} "
             f"(범위 {a['lint']['blocks']['min']}–{a['lint']['blocks']['max']})")
    L.append(f"- WARN 건수: 평균 {a['lint']['warns']['mean']} ± {a['lint']['warns']['sd']} "
             f"(범위 {a['lint']['warns']['min']}–{a['lint']['warns']['max']})")
    L.append("- 규칙별 발화 메모 수:")
    for rule in sorted(a["lint"]["rule_hist_memos"]):
        h = a["lint"]["rule_hist_memos"][rule]
        L.append(f"  - {rule}: BLOCK {h['BLOCK']}개 메모, WARN {h['WARN']}개 메모")
    L.append("\n## B. 결론 안정성\n")
    c = a["conclusion"]
    L.append(f"- 헤드라인이 신규 고객을 몸통으로 지목: {c['attrib_sinkyu_hl_pct']}%")
    L.append(f"- E1·E2 중첩에서 분리 불가 기권 선언: {c['overlap_abstained_pct']}%")
    L.append(f"- 잔차 귀속 시도(R04 발화): {c['residual_attempt_pct']}%")
    L.append(f"- 헤드라인 조건부 어법(v0.1-1 준수): {c['conditional_headline_pct']}%")
    L.append(f"- 무조건부 '일시 요인' 헤드라인(v0.1-1 위반): {c['bare_transient_headline_pct']}%")
    L.append("\n## C. 계약 v0.1 준수 (린트 미구현 조항 — 수동 검사)\n")
    v = a["contract_v01"]
    L.append(f"- defense_lines 슬롯 존재(v0.1-2): {v['defense_lines_pct']}%")
    L.append(f"- 계획 대비 인용(번들 plan_gap 소비): {v['plan_ref_pct']}%")
    L.append(f"- 본문 감사 용어(v0.1-4, 건/메모): 평균 {v['audit_jargon_body']['mean']} "
             f"(범위 {v['audit_jargon_body']['min']}–{v['audit_jargon_body']['max']})")
    L.append(f"- 표 사용(CFO 상한 0개 위반): {v['table_violation_pct']}%")
    L.append(f"- T5 상한 선언문 존재: {v['t5_pct']}%")
    L.append("\n## D. 형태·수치 분산\n")
    f = a["form"]
    L.append(f"- 분량: {f['chars']['mean']:,.0f} ± {f['chars']['sd']:,.0f}자 "
             f"(범위 {f['chars']['min']:,}–{f['chars']['max']:,})")
    L.append(f"- 헤지 문장 비율: {f['hedge_ratio']['mean']} ± {f['hedge_ratio']['sd']}")
    L.append(f"- 인용 수치 개수: {f['figure_n']['mean']} ± {f['figure_n']['sd']} "
             f"(범위 {f['figure_n']['min']}–{f['figure_n']['max']})")
    L.append(f"- 수치 집합 쌍별 Jaccard: 평균 {f['figure_jaccard']['mean']} "
             f"(최소 {f['figure_jaccard']['min']})")
    L.append(f"- 핵심 수치(≥90% 메모가 인용) {len(f['core_figures_ge90pct'])}개: "
             f"{f['core_figures_ge90pct']}")
    L.append(f"- 주변 수치(≤20% 메모만 인용): {f['fringe_figures_le20pct_n']}개")
    L.append("\n## 메모별 상세\n")
    L.append("| 메모 | BLOCK | WARN | 기권 | 조건부HL | 방어대사 | 계획 | 표 | 자수 | 수치수 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        L.append(f"| {r['file']} | {r['block_n']} | {r['warn_n']} "
                 f"| {'○' if r['overlap_abstained'] else '×'} "
                 f"| {'○' if r['conditional_headline'] else '×'} "
                 f"| {'○' if r['defense_lines'] else '×'} "
                 f"| {'○' if r['plan_ref'] else '×'} "
                 f"| {'!' if r['has_table'] else '-'} "
                 f"| {r['chars']:,} | {r['figure_n']} |")
    L.append("\n### BLOCK 상세 (전 메모)\n")
    for r in rows:
        for d in r["block_detail"]:
            L.append(f"- {r['file']} — {d}")
    if not any(r["block_detail"] for r in rows):
        L.append("- (없음)")
    return "\n".join(L) + "\n"


def main():
    memo_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out" / "loop8"
    bundle = json.loads((HERE / "out" / "bundle.json").read_text())
    wl = build_whitelist(bundle)
    paths = sorted(memo_dir.glob("memo_*.md"))
    if not paths:
        print(f"메모 없음: {memo_dir}")
        sys.exit(1)
    rows = [analyze(p, wl) for p in paths]
    a = agg(rows)
    (memo_dir / "metrics.json").write_text(
        json.dumps({"aggregate": a, "memos": rows}, ensure_ascii=False, indent=1))
    (memo_dir / "measurement.md").write_text(render_md(rows, a))
    print(f"측정 완료: {len(rows)}개 메모")
    print(f"  BLOCK율 {a['lint']['memo_block_rate_pct']}%  "
          f"기권 {a['conclusion']['overlap_abstained_pct']}%  "
          f"방어대사 {a['contract_v01']['defense_lines_pct']}%")
    print(f"  → {memo_dir/'metrics.json'}, {memo_dir/'measurement.md'}")


if __name__ == "__main__":
    main()
