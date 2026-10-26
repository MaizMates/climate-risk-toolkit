"""Run the LLM extraction over the 320 test paragraphs and cache every reply.

The model is called through the Claude Code CLI in print mode (`claude -p`) with tools, settings,
skills and session persistence switched off, so each call sees only the system prompt and one
paragraph. Replies are appended to results/llm_raw.jsonl, keyed by (model, prompt, rep, row); a
re-run skips keys already present, so the job can be resumed. Wall-clock budget per invocation is
set by BUDGET_S; run it again until it reports nothing left.

    python3 src/extract.py            # all runs in RUNS
"""
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
OUT = os.path.join(HERE, "..", "results", "llm_raw.jsonl")
BUDGET_S = 500
WORKERS = 8

SYSTEM = "You are a careful annotator of corporate climate disclosures. Answer with exactly one word."
PROMPTS = {
    # A: the dataset card's own task definition
    "A": ("The paragraph below is a climate-related paragraph from a corporate annual or sustainability report. "
          "Is it about climate commitments and actions, that is, does the company state what it commits to do or "
          "what it is doing about climate change? Answer yes or no.\n\nParagraph:\n{text}"),
    # B: terse, no definition
    "B": ("Does this paragraph from a corporate report state a climate commitment or a climate action? "
          "Answer yes or no.\n\n{text}"),
    # C: strict, requires a target or a concrete action by the company itself
    "C": ("The paragraph below is from a corporate report. Answer yes only if the company itself states a "
          "specific climate target, a pledge, or a concrete climate action it has taken or will take. Answer no "
          "for background, risk description, accounting method, governance description, or general statements of "
          "concern. Answer yes or no.\n\nParagraph:\n{text}"),
}
# (model alias, prompt, rep). A on haiku twice: test-retest. Other cells: prompt and model sweep.
RUNS = [("haiku", "A", 1), ("haiku", "A", 2), ("haiku", "B", 1), ("haiku", "C", 1), ("sonnet", "A", 1)]


def load_test():
    return [json.loads(l) for l in open(os.path.join(RAW, "test.jsonl"))]


def parse(reply):
    w = [x.strip(".,!*\"'`:;#") for x in reply.lower().replace("# answer", " ").split()]
    w = w[0] if w else ""
    # prompt B asks "commitment or action", and the model sometimes names the one it found: that is a yes
    return {"yes": 1, "no": 0, "action": 1, "commitment": 1}.get(w)


def call(model, prompt_id, text, cwd):
    cmd = ["claude", "-p", "--model", model, "--output-format", "json", "--tools", "", "--setting-sources", "",
           "--system-prompt", SYSTEM, "--no-session-persistence", "--disable-slash-commands", "--strict-mcp-config"]
    last = None
    for k in range(3):
        try:
            r = subprocess.run(cmd, input=PROMPTS[prompt_id].format(text=text), capture_output=True, text=True, cwd=cwd, timeout=180)
            d = json.loads(r.stdout)
            if d.get("is_error"):
                raise RuntimeError(d.get("result"))
            return d["result"], list(d.get("modelUsage", {})), d.get("total_cost_usd", 0.0)
        except Exception as e:
            last = repr(e)
            time.sleep(5 * (k + 1))
    return "ERROR " + str(last), [], 0.0


def main():
    rows = load_test()
    done = set()
    if os.path.exists(OUT):
        done = {(d["model"], d["prompt"], d["rep"], d["row"]) for d in map(json.loads, open(OUT))}
    todo = [(m, p, r, row) for (m, p, r) in RUNS for row in rows if (m, p, r, row["row"]) not in done]
    print(f"{len(todo)} calls left of {len(RUNS) * len(rows)}", flush=True)
    t0, cwd = time.time(), tempfile.mkdtemp()
    with open(OUT, "a") as f, cf.ThreadPoolExecutor(WORKERS) as ex:
        it = iter(todo)
        pending = set()
        n = 0
        while True:
            while len(pending) < WORKERS * 2 and time.time() - t0 < BUDGET_S:
                job = next(it, None)
                if job is None:
                    break
                m, p, r, row = job
                fut = ex.submit(call, m, p, row["text"], cwd)
                fut.meta = (m, p, r, row["row"])
                pending.add(fut)
            if not pending:
                break
            finished, pending = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
            for fut in finished:
                m, p, r, row = fut.meta
                reply, models, cost = fut.result()
                f.write(json.dumps({"model": m, "prompt": p, "rep": r, "row": row, "reply": reply[:200],
                                    "resolved_model": models, "cost_usd": cost}) + "\n")
                f.flush(); n += 1
    left = len(todo) - n
    print(f"wrote {n}, {left} left")
    sys.exit(0)


if __name__ == "__main__":
    main()
