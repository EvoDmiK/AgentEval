#!/usr/bin/env python3
"""Send the same evaluation prompts to the OpenClaw `eval` agent and the Hermes eval profile.

Usage:
  python3 scripts/run_eval.py --ids A01,B10,E01 --reps 1 [--agents openclaw,hermes] [--seed 7]
  python3 scripts/run_eval.py --all --reps 3

Writes under runs/<timestamp>/:
  raw.jsonl          one line per run: question, repetition, agent, label, times, answer (agent names visible)
  answers_blind.csv  question, repetition, label (X/Y), answer   <- score this one
  mapping.csv        question, repetition, label -> agent         <- open only after scoring

Each prompt runs in a fresh session. Prompts follow 0_프롬프트_템플릿.md.
Standard library only.
"""
import argparse
import csv
import datetime as dt
import json
import os
import random
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_HERMES = os.path.join(HERE, "hermes-docker", "run-hermes.sh")
TIMEOUT_S = 900

from eval_settings import VAULT_NAME

QA_PROMPT = """obsidian_vault 도구로 CONFIGURED_VAULT 보관함에서 찾아 답하라.
- 읽어도 되는 폴더: Work/, Dev/, Learning/. Private/ 와 resume/ 는 읽지 마라.
- 답과 함께 근거 문서 경로와 해당 문장을 그대로 인용하라.
- 문서에서 확인할 수 없으면 추측하지 말고 "문서에서 확인할 수 없음"이라고 답하라.
- 질문에 틀린 전제가 있으면 먼저 바로잡아라.

질문: {q}""".replace("CONFIGURED_VAULT", VAULT_NAME)

ERR_PROMPT = """아래 문서에는 사실 또는 논리 오류가 여러 개 들어 있다. 도구를 쓰지 말고 문서 안의 내용만으로 오류를 모두 찾아라.
각 오류마다 (1) 위치(줄 또는 문장), (2) 틀린 내용, (3) 올바른 내용 또는 모순되는 근거를 적어라.
오류가 아닌 것을 오류로 지적하지 마라. 확실하지 않으면 "불확실"로 표시하라.

--- 문서 시작 ---
{doc}
--- 문서 끝 ---"""

S6 = re.compile(r"^(s6-rc|cont-init|\[supervise|reconcile|\[stage2|/package/admin|Syncing bundled|Done: )")


def load_questions():
    with open(os.path.join(HERE, "datasets/base/1_문항표.csv"), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_units(rows, ids):
    """Return units to run. Questions of the same error-injected document form one unit."""
    units, seen_files = [], set()
    for r in rows:
        if ids and r["문항ID"] not in ids and not (r["문항ID"].startswith("E") and any(i.startswith("E") and unit_of_e(i) == unit_of_e(r["문항ID"]) for i in ids)):
            continue
        if r["문항ID"].startswith("E"):
            m = re.search(r"materials/(.+?\.md)", r["제시 자료"])
            fn = m.group(1)
            if fn in seen_files:
                continue
            seen_files.add(fn)
            with open(os.path.join(HERE, "materials", fn), encoding="utf-8") as f:
                doc = f.read()
            members = [x["문항ID"] for x in rows if fn in x["제시 자료"]]
            units.append({"unit": "E:" + fn.split("_")[0], "members": members, "prompt": ERR_PROMPT.format(doc=doc)})
        else:
            units.append({"unit": r["문항ID"], "members": [r["문항ID"]], "prompt": QA_PROMPT.format(q=r["질문/지시"])})
    return units


def unit_of_e(qid):
    n = int(qid[1:])
    return (n - 1) // 5


def run_openclaw(prompt, sid):
    cmd = ["docker", "exec", "openclaw-cli", "node", "dist/index.js", "agent", "--agent", "eval",
           "--session-id", sid, "--message", prompt]
    return run(cmd)


def run_hermes(prompt, sid):
    return run(["sh", RUN_HERMES, "chat", "-Q", "-q", prompt])


def run(cmd):
    t0 = time.time()
    start = dt.datetime.now(dt.timezone.utc)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
        out, err, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out, err, code = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout", 124
    end = dt.datetime.now(dt.timezone.utc)
    return {"start": start.isoformat(), "end": end.isoformat(), "wall_s": round(time.time() - t0, 2),
            "stdout": out, "stderr": err, "exit": code}


def clean_answer(agent, out):
    lines = [l for l in out.splitlines() if not S6.match(l)]
    return "\n".join(lines).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--agents", default="openclaw,hermes")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--outdir", default="")
    a = ap.parse_args()
    ids = set(x for x in a.ids.split(",") if x)
    if not ids and not a.all:
        sys.exit("give --ids or --all")
    agents = a.agents.split(",")
    rng = random.Random(a.seed)
    units = build_units(load_questions(), None if a.all else ids)
    out = a.outdir or os.path.join(HERE, "runs", dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out, exist_ok=True)
    raw_path = os.path.join(out, "raw.jsonl")
    prior = []
    if os.path.exists(raw_path):  # resume: keep finished runs, reuse their labels
        prior = [json.loads(l) for l in open(raw_path, encoding="utf-8") if l.strip()]
    done = {(r["unit"], r["rep"], r["agent"]) for r in prior if r["exit"] == 0 and r["answer"].strip()}
    prior = [r for r in prior if (r["unit"], r["rep"], r["agent"]) in done]
    open(raw_path, "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in prior))
    labels_by = {}
    for r in prior:
        labels_by.setdefault((r["unit"], r["rep"]), {})[r["agent"]] = r["label"]
    raw = open(raw_path, "a", encoding="utf-8")
    total = len(units) * a.reps * len(agents)
    n = len(prior)
    print(f"resuming: {len(prior)} of {total} runs already done", flush=True) if prior else None
    for rep in range(1, a.reps + 1):
        for u in units:
            order = list(agents)
            rng.shuffle(order)  # random label assignment and run order
            known = labels_by.get((u["unit"], rep), {})
            labels = dict(zip(order, ["X", "Y", "Z"][: len(order)]))
            labels.update(known)
            if len(set(labels.values())) < len(labels):  # keep labels unique after reuse
                free = [l for l in ["X", "Y", "Z"] if l not in known.values()]
                for ag in order:
                    if ag not in known:
                        labels[ag] = free.pop(0)
            for ag in order:
                if (u["unit"], rep, ag) in done:
                    continue
                n += 1
                sid = f"eval-{u['unit'].replace(':', '')}-r{rep}-{int(time.time())}"
                print(f"[{n}/{total}] {u['unit']} rep{rep} {ag} ...", flush=True)
                res = (run_openclaw if ag == "openclaw" else run_hermes)(u["prompt"], sid)
                ans = clean_answer(ag, res["stdout"])
                row = {"unit": u["unit"], "members": u["members"], "rep": rep, "agent": ag, "label": labels[ag],
                       "session": sid, **{k: res[k] for k in ("start", "end", "wall_s", "exit")}, "answer": ans,
                       "stderr_tail": res["stderr"][-400:]}
                raw.write(json.dumps(row, ensure_ascii=False) + "\n")
                raw.flush()
                print(f"    exit={res['exit']} {res['wall_s']}s answer_chars={len(ans)}", flush=True)
    allrows = [json.loads(l) for l in open(raw_path, encoding="utf-8") if l.strip()]
    blind = sorted(([r["unit"], r["rep"], r["label"], r["answer"]] for r in allrows), key=lambda r: (r[0], r[1], r[2]))
    mapping = [[r["unit"], r["rep"], r["label"], r["agent"]] for r in allrows]
    with open(os.path.join(out, "answers_blind.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["unit", "rep", "label", "answer"])
        w.writerows(blind)
    with open(os.path.join(out, "mapping.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["unit", "rep", "label", "agent"])
        w.writerows(mapping)
    print("done ->", out)


if __name__ == "__main__":
    main()
