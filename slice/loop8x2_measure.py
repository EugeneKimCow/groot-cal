"""게이트 소비 측정 — fall_dirty 재작문 N=10 (게이트 번들 + 계약 v0.2).

비교 구도:
  처치군  out/loop8x2/fall_dirty/  — 실측 보류 번들 + v0.2 계약(R13·R14 열람)
  대조군  out/loop8x/fall_dirty/   — 실측 노출 번들 + v0.1 계약 (기존 회차)
대조군도 같은 v0.2 린트(R13·R14)로 재판정해 규칙 위반율을 나란히 놓는다
(R13·R14는 화이트리스트 비의존이라 교차 판정이 유효하다. R06은 번들이 달라
교차 판정 불가 — 처치군만 판정).

사용: python3 loop8x2_measure.py
출력: out/loop8x2/metrics.json, out/loop8x2/measurement.md
"""
import json
import re
import statistics
from pathlib import Path

from lint import lint, build_whitelist, HEDGE, REFUSAL
from loop8_measure import sentences, headline_zone, footer_split, extract_figures
from loop8x_measure import DEFENSE

HERE = Path(__file__).parent
NEW = HERE / "out" / "loop8x2" / "fall_dirty"
OLD = HERE / "out" / "loop8x" / "fall_dirty"

# 구 번들의 노출 실측치(억 표기) — 처치군 지면에 남아 있으면 보류 위반
OLD_MEASURED = ("22.5", "17.9", "4.2", "5.9", "0.6", "12.4")


class _PermitAll:
    """대조군 재판정용 — R06을 무력화해 화이트리스트 의존 규칙을 배제한다."""

    def __contains__(self, x):
        return True


def analyze(path, wl, bundle, full_lint):
    text = path.read_text()
    sents = sentences(text)
    findings = lint(text, wl if full_lint else _PermitAll(), bundle)
    if not full_lint:   # 대조군: R13·R14만 유효 (화이트리스트 비의존)
        findings = [f for f in findings if f[1] in ("R13", "R14")]
    blocks = [f for f in findings if f[0] == "BLOCK"]
    hz = headline_zone(text)
    body, _ = footer_split(text)
    return {
        "file": path.name,
        "block_n": len(blocks),
        "warn_n": len(findings) - len(blocks),
        "rules": sorted({f[1] for f in findings}),
        "r13": any(f[1] == "R13" for f in findings),
        "r14_n": sum(1 for f in findings if f[1] == "R14"),
        "block_detail": [f"{f[1]}: {f[4][:70]}" for f in blocks],
        "refusal_in_headline": bool(re.search(REFUSAL, hz)),
        "old_measured_cited": [t for t in OLD_MEASURED
                               if re.search(r"(?<![\d.])" + re.escape(t) + r"(?![\d])", text)],
        "declared_cited": bool(re.search(r"(?<![\d.])3\.9(?![\d])", text)
                               or re.search(r"(?<![\d.])5\.5(?![\d])", text)),
        "repair_requested": bool(
            re.search(r"정제|수리|보정|재적재|재실행|정합|NULL|미선언|누락", text)
            and re.search(r"요청|필요|후속|조치|확보", text)),
        "chars": len(text),
        "hedge_ratio": round(sum(1 for s in sents if re.search(HEDGE, s)) / max(1, len(sents)), 3),
        "figure_n": len(extract_figures(text)),
        "t5": bool(re.search(r"확실한 것은|여기까지", text)),
        "defense_lines": bool(re.search(DEFENSE, text)),
        "has_table": len(re.findall(r"^\s*\|.*\|", body, flags=re.M)) >= 2,
    }


def agg(rows):
    n = len(rows)

    def pct(key):
        return round(100 * sum(1 for r in rows if r[key]) / n, 0)

    def mean_sd(key):
        vals = [r[key] for r in rows]
        return f"{statistics.mean(vals):,.1f} ± {statistics.pstdev(vals):,.1f}"

    return {"n": n,
            "r13_pct": pct("r13"),
            "r14_total": sum(r["r14_n"] for r in rows),
            "refusal_hl_pct": pct("refusal_in_headline"),
            "old_measured_leak": sum(1 for r in rows if r["old_measured_cited"]),
            "declared_cited_pct": pct("declared_cited"),
            "repair_pct": pct("repair_requested"),
            "chars": mean_sd("chars"), "figure_n": mean_sd("figure_n"),
            "hedge": mean_sd("hedge_ratio"),
            "t5_pct": pct("t5"), "defense_pct": pct("defense_lines"),
            "table_pct": pct("has_table"),
            "block_rows": sum(1 for r in rows if r["block_n"] > 0),
            "blocks_total": sum(r["block_n"] for r in rows)}


def main():
    bundle = json.loads((NEW / "bundle.json").read_text())
    wl = build_whitelist(bundle)
    new_rows = [analyze(p, wl, bundle, True) for p in sorted(NEW.glob("memo_*.md"))]
    old_rows = [analyze(p, None, bundle, False) for p in sorted(OLD.glob("memo_*.md"))]
    a_new, a_old = agg(new_rows), agg(old_rows)

    md = ["# 게이트 소비 측정 — fall_dirty 재작문 N=10 (게이트 번들 + 계약 v0.2)\n",
          "처치군: 실측 보류 번들 + v0.2 계약. 대조군: v0.1 회차를 같은 R13·R14로 재판정.\n",
          "| 지표 | v0.1 회차(대조) | v0.2 회차(처치) |", "|---|---|---|",
          f"| R13 위반(거부 요약 누락) | {a_old['r13_pct']}% | {a_new['r13_pct']}% |",
          f"| R14 경고(선언 출처 부기 부재, 총건) | {a_old['r14_total']} | {a_new['r14_total']} |",
          f"| 거부의 요약 전달 | {a_old['refusal_hl_pct']}% | {a_new['refusal_hl_pct']}% |",
          f"| 구 실측치 인용(보류 위반) | (노출 번들이라 해당 없음) | {a_new['old_measured_leak']}건 |",
          f"| 선언치 인용 | {a_old['declared_cited_pct']}% | {a_new['declared_cited_pct']}% |",
          f"| 수리 요청 | {a_old['repair_pct']}% | {a_new['repair_pct']}% |",
          f"| 분량(자) | {a_old['chars']} | {a_new['chars']} |",
          f"| 인용 수치(개) | {a_old['figure_n']} | {a_new['figure_n']} |",
          f"| 헤지 비율 | {a_old['hedge']} | {a_new['hedge']} |",
          f"| T5 / defense / 표위반 | {a_old['t5_pct']}/{a_old['defense_pct']}/{a_old['table_pct']}% "
          f"| {a_new['t5_pct']}/{a_new['defense_pct']}/{a_new['table_pct']}% |",
          f"| 전체 린트 BLOCK (처치군만 전 규칙) | — | {a_new['block_rows']}개 메모 "
          f"/ {a_new['blocks_total']}건 |",
          "\n## 처치군 메모별\n",
          "| 메모 | BLOCK | R13 | R14 | 거부HL | 구실측누출 | 자수 | 수치수 |",
          "|---|---|---|---|---|---|---|---|"]
    for r in new_rows:
        md.append(f"| {r['file']} | {r['block_n']} | {'✗' if r['r13'] else '-'} "
                  f"| {r['r14_n']} | {'○' if r['refusal_in_headline'] else '×'} "
                  f"| {','.join(r['old_measured_cited']) or '-'} "
                  f"| {r['chars']:,} | {r['figure_n']} |")
    details = [(r["file"], d) for r in new_rows for d in r["block_detail"]]
    if details:
        md.append("")
        for f, d in details:
            md.append(f"- BLOCK {f} — {d}")

    (NEW.parent / "metrics.json").write_text(json.dumps(
        {"treated": {"aggregate": a_new, "memos": new_rows},
         "control_v01_reJudged": {"aggregate": a_old, "memos": old_rows}},
        ensure_ascii=False, indent=1))
    (NEW.parent / "measurement.md").write_text("\n".join(md) + "\n")
    print(f"처치군 N={a_new['n']}: R13 위반 {a_new['r13_pct']}% (대조 {a_old['r13_pct']}%), "
          f"거부HL {a_new['refusal_hl_pct']}% (대조 {a_old['refusal_hl_pct']}%), "
          f"R14 {a_new['r14_total']}건 (대조 {a_old['r14_total']}건), "
          f"구실측 누출 {a_new['old_measured_leak']}건, BLOCK {a_new['blocks_total']}건")
    print(f"→ {NEW.parent/'measurement.md'}")


if __name__ == "__main__":
    main()
