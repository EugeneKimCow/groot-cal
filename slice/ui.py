"""질의 윈도우 — 표준 라이브러리만 사용하는 로컬 시연 서버.

입력창에 질문을 넣으면 진행 단계가 텍스트로 흐르고(SSE), 증거 한정 결과가
피드에 쌓인다. 실행 경로는 CLI의 --route c4와 동일하다: 해석 제안(규칙 또는
local LLM) → 결정론 검증·컴파일 → 라우팅된 C4 executor. 데이터는 시작 시
선택된 catalog(기본: DuckDB 저장소가 구축되어 있으면 그것)에서 적재한다.

실행: ../.venv/bin/python3 ui.py  →  http://localhost:8787
"""
import argparse
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from catalog import load_metric_catalog
from demo import demo_question_events, render_demo
from llm_intent_adapter import DEFAULT_MODEL, make_llm_proposer

HERE = Path(__file__).parent
ACCURATE_MODEL = "qwen2.5:72b-instruct-q4_K_M"


def pick_catalog():
    """DuckDB 저장소가 구축되어 있으면 그것을, 아니면 fixture catalog를 쓴다."""
    db = HERE / "store" / "groot.duckdb"
    if db.exists():
        try:
            import duckdb  # noqa: F401
            return "metric_catalog.duckdb.json", f"DuckDB · {db.name}"
        except ModuleNotFoundError:
            pass
    return None, "JSON/CSV fixture"


CATALOG_PATH, DATA_SOURCE = pick_catalog()
CONTEXTS = load_metric_catalog(CATALOG_PATH)
PROPOSERS = {"rule": None}


def get_proposer(name):
    if name not in PROPOSERS:
        PROPOSERS[name] = make_llm_proposer(model=name)
    return PROPOSERS[name]


PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>groot-cal 질의 윈도우</title>
<style>
:root {
  --surface: #fcfcfb; --card: #ffffff; --ink: #0b0b0b; --ink-2: #52514e;
  --border: #e2e1dc; --accent: #2a78d6; --ok: #1a7f4e; --warn: #b4540a;
}
@media (prefers-color-scheme: dark) {
  :root { --surface: #1a1a19; --card: #222220; --ink: #f2f1ec; --ink-2: #c3c2b7;
          --border: #3a3936; --accent: #3987e5; --ok: #35b37d; --warn: #e8823f; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface); color: var(--ink);
  font-family: -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; }
header { position: sticky; top: 0; background: var(--surface);
  border-bottom: 1px solid var(--border); padding: 12px 20px; z-index: 2;
  display: flex; align-items: baseline; gap: 12px; }
header h1 { font-size: 16px; margin: 0; }
header .src { font-size: 12px; color: var(--ink-2); }
#feed { max-width: 860px; margin: 0 auto; padding: 16px 20px 120px; }
.card { background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px; margin-bottom: 14px; }
.q { font-weight: 600; font-size: 14.5px; margin-bottom: 8px; }
.q .meta { font-weight: 400; font-size: 11.5px; color: var(--ink-2); margin-left: 8px; }
.stages { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12px;
  color: var(--ink-2); line-height: 1.7; white-space: pre-wrap; }
.stages .running::after { content: "…"; animation: dots 1.2s steps(4) infinite; }
@keyframes dots { 0% { content: ""; } 25% { content: "."; }
  50% { content: ".."; } 75% { content: "..."; } }
pre.result { font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 12.5px; line-height: 1.65; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px;
  overflow-x: auto; margin: 10px 0 0; white-space: pre-wrap; }
pre.result.ok { border-left: 3px solid var(--ok); }
pre.result.refused { border-left: 3px solid var(--warn); }
form { position: fixed; bottom: 0; left: 0; right: 0; background: var(--surface);
  border-top: 1px solid var(--border); padding: 12px 20px; }
.bar { max-width: 860px; margin: 0 auto; display: flex; gap: 8px; }
input[type=text] { flex: 1; font-size: 14px; padding: 10px 12px;
  border: 1px solid var(--border); border-radius: 8px;
  background: var(--card); color: var(--ink); }
select, button { font-size: 13px; padding: 10px 12px; border-radius: 8px;
  border: 1px solid var(--border); background: var(--card); color: var(--ink); }
button { background: var(--accent); color: #fff; border-color: var(--accent);
  cursor: pointer; font-weight: 600; }
button:disabled { opacity: 0.5; cursor: default; }
input:focus, select:focus, button:focus { outline: 2px solid var(--accent);
  outline-offset: 1px; }
.hint { max-width: 860px; margin: 6px auto 0; font-size: 11.5px;
  color: var(--ink-2); }
.hint a { color: var(--accent); cursor: pointer; text-decoration: none; }
</style>
</head>
<body>
<header><h1>groot-cal 질의 윈도우</h1>
<span class="src">데이터: __DATA_SOURCE__ · 경로: C4 (검증·연산 결정론)</span></header>
<div id="feed"></div>
<form id="ask">
  <div class="bar">
    <input id="q" type="text" autocomplete="off"
           placeholder="예: 7월 매출이 왜 변했나?" autofocus>
    <select id="llm">
      <option value="rule">규칙 해석</option>
      <option value="__DEFAULT_MODEL__" selected>LLM · __DEFAULT_MODEL__</option>
      <option value="__ACCURATE_MODEL__">LLM · __ACCURATE_MODEL__</option>
    </select>
    <button id="go" type="submit">질의</button>
  </div>
  <div class="hint">예시:
    <a data-q="7월 매출은?">수준</a> ·
    <a data-q="온라인 매출이 7월에 왜 빠졌어?">기여 분해</a> ·
    <a data-q="7월 활성 고객 증가는 어느 지역에서 발생했나?">고객 전이</a> ·
    <a data-q="7월 손해율이 왜 변했나?">거부(rate)</a> ·
    <a data-q="7월 매출 계획 대비 어때?">반문(빈티지)</a></div>
</form>
<script>
const feed = document.getElementById("feed");
const form = document.getElementById("ask");
const input = document.getElementById("q");
const model = document.getElementById("llm");
const go = document.getElementById("go");
document.querySelectorAll(".hint a").forEach(a => a.onclick = () => {
  input.value = a.dataset.q; input.focus(); });

function ask(question, llm) {
  const card = document.createElement("div");
  card.className = "card";
  const label = llm === "rule" ? "규칙 해석" : llm;
  card.innerHTML = `<div class="q"></div><div class="stages"></div>`;
  card.querySelector(".q").textContent = question;
  const meta = document.createElement("span");
  meta.className = "meta"; meta.textContent = label;
  card.querySelector(".q").appendChild(meta);
  feed.appendChild(card);
  const stages = card.querySelector(".stages");
  const running = document.createElement("div");
  running.className = "running"; running.textContent = "시작";
  stages.appendChild(running);
  card.scrollIntoView({behavior: "smooth", block: "end"});

  const source = new EventSource(
    `/events?q=${encodeURIComponent(question)}&llm=${encodeURIComponent(llm)}`);
  go.disabled = true;
  const finish = () => { source.close(); go.disabled = false; input.focus(); };
  source.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.kind === "stage") {
      const line = document.createElement("div");
      line.textContent = event.text;
      stages.insertBefore(line, running);
      running.textContent = "";
      card.scrollIntoView({block: "end"});
    }
    if (event.kind === "result") {
      stages.querySelectorAll(".running").forEach(el => el.remove());
      const pre = document.createElement("pre");
      pre.className = "result " + (event.ok ? "ok" : "refused");
      pre.textContent = event.text;
      card.appendChild(pre);
      card.scrollIntoView({behavior: "smooth", block: "end"});
      finish();
    }
    if (event.kind === "error") {
      stages.querySelectorAll(".running").forEach(el => el.remove());
      const pre = document.createElement("pre");
      pre.className = "result refused";
      pre.textContent = "서버 오류: " + event.text;
      card.appendChild(pre);
      finish();
    }
  };
  source.onerror = () => { finish(); };
}

form.onsubmit = (submit) => {
  submit.preventDefault();
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  ask(question, model.value);
};
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            body = (PAGE.replace("__DATA_SOURCE__", DATA_SOURCE)
                    .replace("__DEFAULT_MODEL__", DEFAULT_MODEL)
                    .replace("__ACCURATE_MODEL__", ACCURATE_MODEL)
                    .encode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/events":
            params = urllib.parse.parse_qs(parsed.query)
            question = (params.get("q") or [""])[0].strip()
            llm = (params.get("llm") or ["rule"])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                proposer = None if llm == "rule" else get_proposer(llm)
                for event in demo_question_events(question, CONTEXTS, proposer):
                    if event["kind"] == "stage":
                        self._emit({"kind": "stage", "text": event["text"]})
                    else:
                        outcome = event["outcome"]
                        self._emit({
                            "kind": "result",
                            "ok": (outcome["stage"] == "executed" and
                                   outcome["execution"]["status"] == "result"),
                            "text": render_demo(outcome, show_plan=True),
                        })
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as error:  # 서버는 살아남고 실패는 이름을 밝힌다
                self._emit({"kind": "error", "text": str(error)})
            return
        self.send_response(404)
        self.end_headers()

    def _emit(self, payload):
        data = json.dumps(payload, ensure_ascii=False)
        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
        self.wfile.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"질의 윈도우: http://localhost:{args.port}  (데이터: {DATA_SOURCE})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
