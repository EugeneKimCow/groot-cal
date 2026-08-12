"""⑧작문 확장 측정 — rise/flat/fall_dirty × N=10, 시나리오별 + 교차 비교.

사용: python3 loop8x_measure.py

공통 지표는 loop8_measure의 도구를 재사용하고, 시나리오별 검사를 얹는다:
  rise      계약 §12-1 시험 — 상승에서 인과 단정이 관대해지는가
            (R01~R03 발화, 무헤지 단정 어구, 중첩 3쌍 기권, VRM 단가 인용)
  flat      무변화 보고 — 대역 인용, 이벤트 부재 명시, 원인 날조 신호, 분량
  fall_dirty 게이트 거부 보고 — 거부의 헤드라인 전달, 오염 실측치 인용 폭,
            데이터 수리 요청 변환

교차 비교 기준선: out/loop8/metrics.json (fall 원 시나리오 N=20).
출력: out/loop8x/metrics.json, out/loop8x/measurement.md
"""
import json
import re
import statistics
from pathlib import Path

from lint import lint, build_whitelist, HEDGE
from loop8_measure import sentences, extract_figures, headline_zone, footer_split

HERE = Path(__file__).parent
BASE = HERE / "out" / "loop8x"
SCENARIOS = ["rise", "flat", "fall_dirty"]

ABSTAIN = (r"분리(가|는|를)?\s*(안 |불가|어렵|되지 않)|특정할\s*수 없|특정하지 못"
           r"|나눌 수 없|(나누|나눠|배분|분리)[^.]{0,60}(할 수 없|불가|무리|않|근거 없)")
DEFENSE = (r"답하(십시오|시면|시기|시길)|답변하(십시오|시)|방어 대사|이렇게 답|답변용|문안"
           r"|다음과 같이 (답|말씀)")


def common(path, wl):
    text = path.read_text()
    sents = sentences(text)
    findings = lint(text, wl)
    blocks = [f for f in findings if f[0] == "BLOCK"]
    body, _ = footer_split(text)
    return text, {
        "file": path.name,
        "block_n": len(blocks),
        "warn_n": len(findings) - len(blocks),
        "rules_block": sorted(f[1] for f in blocks),
        "block_detail": [f"{f[1]}: {f[4][:70]}" for f in blocks],
        "chars": len(text),
        "hedge_ratio": round(sum(1 for s in sents if re.search(HEDGE, s)) / max(1, len(sents)), 3),
        "figure_n": len(extract_figures(text)),
        "_figures": sorted(extract_figures(text)),
        "t5": bool(re.search(r"확실한 것은|여기까지", text)),
        "defense_lines": bool(re.search(DEFENSE, text)),
        "has_table": len(re.findall(r"^\s*\|.*\|", body, flags=re.M)) >= 2,
        "audit_jargon_body_n": len(re.findall(r"항등식|증거 번들|검산|번들", body)),
    }


def extra_rise(text):
    hz = headline_zone(text)
    # 무헤지 인과 단정 어구(상승 관대화 신호): '덕분/견인/이끌' + 헤지 부재 문장
    assertive = sum(1 for s in sentences(text)
                    if re.search(r"덕분|견인했|이끌었|성과(다|입니다)[.\s]", s)
                    and not re.search(HEDGE, s))
    return {
        "hl_top_online": bool(re.search(r"온라인", hz)),
        "overlap_abstained": bool(re.search(ABSTAIN, text)),
        "assertive_nohedge_n": assertive,
        "vrm_rate_cited": "10.5" in text,
        "conditional_headline": bool(re.search(
            r"(판별|확인|해소|특정)[^.]{0,8}(전까지|되기까지)|전까지는", hz)),
    }


def extra_flat(text):
    return {
        "band_cited": bool(re.search(r"통상|변동 (범위|대역)|대역", text)),
        "no_event_stated": bool(re.search(
            r"이벤트(가|는)?\s*(없|0건|등록되지 않|부재)|등록된 이벤트가 없|원인 후보가 없", text)),
        "sign_mix_handled": bool(re.search(r"부호|혼재|상쇄|절대값|절댓값", text)),
        "cause_invented_tokens": len(re.findall(
            r"프로모션|쿠폰|행사|폐점|경쟁사|발주|입점", text)),
        "smallness_stated": bool(re.search(r"미소|소폭|보합|크지 않|이례적이지 않|통상", text)),
    }


def extra_dirty(text):
    hz = headline_zone(text)
    ev_figs = sum(1 for tok in ("22.5", "17.9", "4.2", "5.9", "0.6") if tok in text)
    return {
        "refusal_in_headline": bool(re.search(
            r"거부|차단|불가|보류|산출(할 수|되지) (없|않)|신뢰할 수 없|품질|오염"
            r"|판정.{0,6}(불가|유보)|제공하지 못|중단", hz)),
        "total_delta_cited": "37.4" in text,
        "event_figures_cited_n": ev_figs,
        "repair_requested": bool(
            re.search(r"정제|수리|보정|재적재|재실행|정합|NULL|미선언|누락", text)
            and re.search(r"요청|필요|후속|조치|확보", text)),
        "quality_caveat_on_figures": bool(re.search(
            r"(오염|품질|정합|미선언|NULL)[^.]{0,40}(전제|유의|주의|한계|잠정)"
            r"|(잠정|참고)[^.]{0,20}(실측|수치)", text)),
    }


EXTRA = {"rise": extra_rise, "flat": extra_flat, "fall_dirty": extra_dirty}


def stats_of(rows, key):
    vals = [r[key] for r in rows]
    return {"mean": round(statistics.mean(vals), 2), "sd": round(statistics.pstdev(vals), 2),
            "min": min(vals), "max": max(vals)}


def pct(rows, key):
    return round(100 * sum(1 for r in rows if r[key]) / len(rows), 0)


def measure_scenario(sc):
    d = BASE / sc
    bundle = json.loads((d / "bundle.json").read_text())
    wl = build_whitelist(bundle)
    rows = []
    for p in sorted(d.glob("memo_*.md")):
        text, row = common(p, wl)
        row.update(EXTRA[sc](text))
        if sc == "rise":
            row["residual_attempt"] = "R04" in row["rules_block"]
        rows.append(row)
    return rows


def main():
    fall = json.loads((HERE / "out" / "loop8" / "metrics.json").read_text())["aggregate"]
    out = {"scenarios": {}, "cross": {}}
    md = ["# ⑧작문 확장 측정 — rise/flat/fall_dirty × N=10\n",
          "입력: 시나리오별 bundle.json(run_sim.py) + 계약 v0.1. 기준선: fall 원 시나리오 N=20.\n"]

    for sc in SCENARIOS:
        rows = measure_scenario(sc)
        n = len(rows)
        agg = {
            "n": n,
            "block_rate_pct": round(100 * sum(1 for r in rows if r["block_n"] > 0) / n, 0),
            "blocks_total": sum(r["block_n"] for r in rows),
            "rules_block_memos": sorted({rl for r in rows for rl in r["rules_block"]}),
            "chars": stats_of(rows, "chars"),
            "hedge_ratio": stats_of(rows, "hedge_ratio"),
            "figure_n": stats_of(rows, "figure_n"),
            "t5_pct": pct(rows, "t5"),
            "defense_pct": pct(rows, "defense_lines"),
            "table_pct": pct(rows, "has_table"),
            "audit_jargon_total": sum(r["audit_jargon_body_n"] for r in rows),
        }
        for k in rows[0]:
            if k.startswith("_") or k in ("file", "block_detail", "rules_block"):
                continue
            if isinstance(rows[0][k], bool):
                agg[f"{k}_pct"] = pct(rows, k)
            elif k.endswith("_n") and k not in ("block_n", "warn_n", "figure_n"):
                agg[k] = stats_of(rows, k)
        out["scenarios"][sc] = {"aggregate": agg, "memos": rows}

        md.append(f"## {sc} (N={n})\n")
        md.append(f"- BLOCK율 {agg['block_rate_pct']}% (총 {agg['blocks_total']}건, "
                  f"규칙 {agg['rules_block_memos'] or '없음'})")
        md.append(f"- 분량 {agg['chars']['mean']:,.0f} ± {agg['chars']['sd']:,.0f}자, "
                  f"수치 {agg['figure_n']['mean']} ± {agg['figure_n']['sd']}개, "
                  f"헤지 비율 {agg['hedge_ratio']['mean']} ± {agg['hedge_ratio']['sd']}")
        md.append(f"- T5 {agg['t5_pct']}%, defense {agg['defense_pct']}%, "
                  f"표 위반 {agg['table_pct']}%, 본문 감사 용어 {agg['audit_jargon_total']}건")
        for k, v in agg.items():
            if k.endswith("_pct") and k not in ("block_rate_pct", "t5_pct", "defense_pct", "table_pct"):
                md.append(f"- {k[:-4]}: {v}%")
            elif isinstance(v, dict) and k not in ("chars", "hedge_ratio", "figure_n"):
                md.append(f"- {k}: 평균 {v['mean']} (범위 {v['min']}–{v['max']})")
        md.append("")
        md.append("| 메모 | BLOCK | 자수 | 수치수 | 헤지 | 비고 |")
        md.append("|---|---|---|---|---|---|")
        for r in rows:
            note = ", ".join(r["rules_block"]) or "-"
            md.append(f"| {r['file']} | {r['block_n']} | {r['chars']:,} "
                      f"| {r['figure_n']} | {r['hedge_ratio']} | {note} |")
        blocks = [(r["file"], d_) for r in rows for d_ in r["block_detail"]]
        if blocks:
            md.append("")
            for f, d_ in blocks:
                md.append(f"- BLOCK {f} — {d_}")
        md.append("")

    # 교차 비교
    rise_a = out["scenarios"]["rise"]["aggregate"]
    flat_a = out["scenarios"]["flat"]["aggregate"]
    dirty_a = out["scenarios"]["fall_dirty"]["aggregate"]
    cross = {
        "hedge_ratio": {"fall_N20": fall["form"]["hedge_ratio"]["mean"],
                        "rise": rise_a["hedge_ratio"]["mean"],
                        "flat": flat_a["hedge_ratio"]["mean"],
                        "fall_dirty": dirty_a["hedge_ratio"]["mean"]},
        "chars": {"fall_N20": fall["form"]["chars"]["mean"],
                  "rise": rise_a["chars"]["mean"], "flat": flat_a["chars"]["mean"],
                  "fall_dirty": dirty_a["chars"]["mean"]},
        "figure_n": {"fall_N20": fall["form"]["figure_n"]["mean"],
                     "rise": rise_a["figure_n"]["mean"], "flat": flat_a["figure_n"]["mean"],
                     "fall_dirty": dirty_a["figure_n"]["mean"]},
        "block_rate_pct": {"fall_N20": fall["lint"]["memo_block_rate_pct"],
                           "rise": rise_a["block_rate_pct"], "flat": flat_a["block_rate_pct"],
                           "fall_dirty": dirty_a["block_rate_pct"]},
        "abstention_pct": {"fall_N20": fall["conclusion"]["overlap_abstained_pct"],
                           "rise": rise_a.get("overlap_abstained_pct")},
    }
    out["cross"] = cross
    md.append("## 교차 비교 (fall N=20 기준선)\n")
    md.append("| 지표 | fall(N=20) | rise | flat | fall_dirty |")
    md.append("|---|---|---|---|---|")
    for k, v in cross.items():
        md.append(f"| {k} | {v.get('fall_N20', '-')} | {v.get('rise', '-')} "
                  f"| {v.get('flat', '-')} | {v.get('fall_dirty', '-')} |")

    (BASE / "metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    (BASE / "measurement.md").write_text("\n".join(md) + "\n")
    for sc in SCENARIOS:
        a = out["scenarios"][sc]["aggregate"]
        print(f"{sc}: BLOCK율 {a['block_rate_pct']}% 헤지 {a['hedge_ratio']['mean']} "
              f"수치 {a['figure_n']['mean']}개")
    print(f"→ {BASE/'metrics.json'}, {BASE/'measurement.md'}")


if __name__ == "__main__":
    main()
