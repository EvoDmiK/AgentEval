#!/usr/bin/env python3
"""Publish per-agent evaluation summaries to MLflow so the two agents can be compared in the MLflow UI.

Usage:
  python3 scripts/publish_summary.py runs/full-r1                          # timing + tokens only
  python3 scripts/publish_summary.py runs/full-r1 --scores scores-rep1.csv  # also accuracy / hallucination metrics

Creates (or updates) one MLflow run per agent in experiment `compare-summary`:
  run name "<agent> · rep<N> · <run dir name>", tag compare_key "<run dir>/<agent>/rep<N>".
Per-question metrics (trace_s, input_tokens, output_tokens) use the question order as `step`,
so the two runs overlay in the UI. Accuracy metrics are added when --scores is given.
The mapping label -> agent is read from mapping.csv only when scores are supplied (after blind scoring).
Standard library plus curl; no conversation text is uploaded.
"""
import argparse
import csv
import json
import math
import os
import statistics as st
import subprocess
import sys
import time

from eval_settings import TRACKING_URI
BASE = TRACKING_URI
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS = {
    "openclaw": {"runtime": "OpenClaw eval agent (gateway)", "version": "2026.9.9", "model": "openai/gpt-6.1-sol", "fallback": "openai/gpt-6-sol"},
    "hermes": {"runtime": "Hermes profile (container per query)", "version": "0.21.5", "model": "openai-codex/gpt-6.1-sol", "fallback": "openai-codex/gpt-6-sol"},
}
COMMON = {"memory": "off (QA mode)", "mcp": "korean_law, obsidian_vault(read-only subset), grafana(read-only)", "question_set": "100 items / 88 units"}


def api(path, body=None, method="POST"):
    cmd = ["curl", "-sS", "-m", "60", "-X", method, "-H", "Content-Type: application/json"]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    out = subprocess.run(cmd + [BASE + path], capture_output=True, text=True).stdout
    try:
        return json.loads(out) if out.strip() else {}
    except json.JSONDecodeError:
        raise SystemExit(f"MLflow error on {path}: {out[:200]}")


def get_experiment(name):
    r = api(f"/api/2.0/mlflow/experiments/get-by-name?experiment_name={name}", method="GET")
    if r.get("experiment"):
        return r["experiment"]["experiment_id"]
    r = api("/api/2.0/mlflow/experiments/create", {"name": name, "tags": [{"key": "project", "value": "agent-comparison"}, {"key": "purpose", "value": "summary"}]})
    return r["experiment_id"]


def score_of(typ, judgement):
    """(points, hallucination?) for one scored item."""
    j = judgement or ""
    if typ in ("A", "B"):
        return ({"정확": 1.0, "부분정확": 0.5}.get(j, 0.0), j == "환각")
    if typ == "C":
        return (1.0 if j.startswith("정답") else 0.0, j.startswith("오답"))
    if typ == "D":
        return (1.0 if j.startswith("정답") else 0.5 if j == "부분정답" else 0.0, j.startswith("오답"))
    if typ == "E":
        return (1.0 if j == "찾음" else 0.0, False)
    return (0.0, False)


def percentile(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))]


def complete_trace(row):
    """Only unambiguous measured rows contribute to efficiency summaries."""
    try:
        values = [float(row[k]) for k in ("trace_s", "input_tokens", "output_tokens")]
        return int(row["n_traces"]) == 1 and all(math.isfinite(v) and v >= 0 for v in values)
    except (KeyError, ValueError, TypeError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--scores", default="")
    ap.add_argument("--rep", default="1")
    ap.add_argument("--experiment", default="compare-summary")
    a = ap.parse_args()
    run_dir = a.run_dir if os.path.isabs(a.run_dir) else os.path.join(HERE, a.run_dir)
    tag_dir = os.path.basename(run_dir.rstrip("/"))

    metrics = [r for r in csv.DictReader(open(os.path.join(run_dir, "metrics.csv"), encoding="utf-8-sig")) if r["rep"] == a.rep]
    if not metrics:
        sys.exit("metrics.csv has no rows for rep " + a.rep + " (run join_traces.py first)")
    order = sorted({r["unit"] for r in metrics})
    raw_path = os.path.join(run_dir, "raw.jsonl")
    successful = None
    if os.path.exists(raw_path):
        with open(raw_path, encoding="utf-8") as f:
            raw = [json.loads(line) for line in f if line.strip()]
        successful = {(r["unit"], str(r["rep"]), r["agent"]) for r in raw
                      if r["exit"] == 0 and r["answer"].strip()}
    acc = {}
    if a.scores:
        mapping = {(r["unit"], r["rep"], r["label"]): r["agent"] for r in csv.DictReader(open(os.path.join(run_dir, "mapping.csv"), encoding="utf-8-sig"))}
        for r in csv.DictReader(open(a.scores, encoding="utf-8-sig")):
            if r["rep"] != a.rep or not r["judgement"] or r["judgement"] == "무효":
                continue
            unit = r["unit"]
            ag = mapping.get((unit, a.rep, r["label"]))
            if not ag:
                continue
            typ = unit[0] if not unit.startswith("E:") else "E"
            pts, hall = score_of(typ, r["judgement"])
            d = acc.setdefault(ag, {"items": {}, "fp": 0, "cite_y": 0, "cite_n": 0})
            d["items"][(typ, r["item"])] = (pts, hall)
            if typ == "E" and r["false_positives"].strip().isdigit() and r["item"].endswith(("01", "06", "11")):
                d["fp"] += int(r["false_positives"])
            if typ in ("A", "B") and r["cited_verified"]:
                d["cite_y"] += 1

    exp_id = get_experiment(a.experiment)
    now = int(time.time() * 1000)
    for ag in ("openclaw", "hermes"):
        allrows = [r for r in metrics if r["agent"] == ag]
        if not allrows:
            continue
        rows = [r for r in allrows if complete_trace(r) and
                (successful is None or (r["unit"], r["rep"], ag) in successful)]
        rows.sort(key=lambda r: order.index(r["unit"]))
        ts = [float(r["trace_s"]) for r in rows]
        it = [int(r["input_tokens"]) for r in rows]
        ot = [int(r["output_tokens"]) for r in rows]
        key = f"{tag_dir}/{ag}/rep{a.rep}"
        found = api("/api/2.0/mlflow/runs/search", {"experiment_ids": [exp_id], "filter": f"tags.compare_key = '{key}'", "max_results": 1}).get("runs", [])
        created = not found
        if created:
            run = api("/api/2.0/mlflow/runs/create", {"experiment_id": exp_id, "start_time": now, "tags": [
                {"key": "mlflow.runName", "value": f"{ag} · rep{a.rep} · {tag_dir}"}, {"key": "compare_key", "value": key},
                {"key": "agent", "value": ag}, {"key": "rep", "value": a.rep}]})["run"]["info"]["run_id"]
        else:
            run = found[0]["info"]["run_id"]
        params = {**PARAMS[ag], **COMMON, "agent": ag, "rep": a.rep, "source_run": tag_dir}
        batch_metrics = []

        def m(k, v, step=0):
            batch_metrics.append({"key": k, "value": float(v), "timestamp": now, "step": step})

        m("units", len(allrows)); m("telemetry_units", len(rows)); m("telemetry_coverage", len(rows) / len(allrows))
        m("telemetry_excluded_units", len(allrows) - len(rows))
        if rows:
            m("trace_s_median", st.median(ts)); m("trace_s_mean", st.mean(ts)); m("trace_s_p90", percentile(ts, 0.9)); m("trace_s_total_min", sum(ts) / 60)
            m("input_tokens_total", sum(it)); m("output_tokens_total", sum(ot)); m("input_tokens_mean", st.mean(it)); m("output_tokens_mean", st.mean(ot))
        for t in "ABCDE":
            sub = [r for r in rows if (r["unit"][0] if not r["unit"].startswith("E:") else "E") == t]
            if sub:
                m(f"trace_s_median_{t}", st.median(float(r["trace_s"]) for r in sub)); m(f"input_tokens_mean_{t}", st.mean(int(r["input_tokens"]) for r in sub))
        if created:  # per-question series, once
            for r in rows:
                i = order.index(r["unit"])
                m("q_trace_s", r["trace_s"], i); m("q_input_tokens", r["input_tokens"], i); m("q_output_tokens", r["output_tokens"], i)
        if ag in acc and acc[ag]["items"]:
            items = acc[ag]["items"]
            pts = [v[0] for v in items.values()]; hall = [v[1] for v in items.values()]
            m("accuracy", sum(pts) / len(pts)); m("scored_items", len(pts))
            qa = [(k, v) for k, v in items.items() if k[0] in "ABCD"]
            if qa:
                m("hallucination_rate", sum(1 for k, v in qa if v[1]) / len(qa))
            for t in "ABCDE":
                s = [v[0] for k, v in items.items() if k[0] == t]
                if s:
                    m(f"accuracy_{t}", sum(s) / len(s))
            if any(k[0] == "E" for k in items):
                m("e_false_positives", acc[ag]["fp"])
            if acc[ag]["cite_y"]:
                m("citation_verified_items", acc[ag]["cite_y"])
        # MLflow limits: 1000 metrics, 100 params per batch
        for i in range(0, len(batch_metrics), 900):
            body = {"run_id": run, "metrics": batch_metrics[i:i + 900]}
            if i == 0:
                body["params"] = [{"key": k, "value": str(v)} for k, v in params.items()] if created else []
            api("/api/2.0/mlflow/runs/log-batch", body)
        api("/api/2.0/mlflow/runs/update", {"run_id": run, "status": "FINISHED", "end_time": now})
        print(f"{ag}: {'created' if created else 'updated'} run {run[:8]}  metrics={len(batch_metrics)}  telemetry={len(rows)}/{len(allrows)}  accuracy={'yes' if ag in acc else 'not yet'}")
    print(f"MLflow: {BASE}/#/experiments/{exp_id}")


if __name__ == "__main__":
    main()
