#!/usr/bin/env python3
"""Join evaluation runs (runs/<dir>/raw.jsonl) to MLflow traces by time window.
Usage: python3 scripts/join_traces.py runs/pilot
OpenClaw traces: only those carrying mlflow.trace.tokenUsage (model-call traces); Hermes: all traces in the window.
"""
import datetime as dt, json, statistics as st, subprocess, sys

from eval_settings import TRACKING_URI
URL = TRACKING_URI.rstrip("/") + "/api/3.0/mlflow/traces/search"
EXP = {"openclaw": 45, "hermes": 45}


def traces(exp):
    """All traces of an experiment, following next_page_token."""
    out, token = [], None
    while True:
        req = {"locations": [{"type": "MLFLOW_EXPERIMENT", "mlflow_experiment": {"experiment_id": str(exp)}}],
               "max_results": 500, "order_by": ["timestamp_ms DESC"]}
        if token:
            req["page_token"] = token
        response = subprocess.run(["curl", "-f", "-sS", "-m", "60", "-X", "POST", "-H", "Content-Type: application/json",
                                   "-d", json.dumps(req), URL], capture_output=True, text=True)
        if response.returncode:
            raise RuntimeError(f"trace search failed for experiment {exp}: curl exit {response.returncode}")
        res = json.loads(response.stdout)
        if "error_code" in res or "traces" not in res:
            raise RuntimeError(f"invalid trace search response for experiment {exp}")
        out += res.get("traces", [])
        token = res.get("next_page_token")
        if not token or not res.get("traces"):
            return out


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def main(run_dir):
    # Evaluation trace history and future traces now share experiment 45.
    unified = traces(45)
    T = {agent: [t for t in unified
                 if (t.get("tags") or {}).get("trace_scope") != "instrumentation_check"
                 and ((t.get("tags") or {}).get("trace_scope") == "native"
                      or (t.get("tags") or {}).get("service.name") == agent)
                 and (t.get("tags") or {}).get("agent", (t.get("tags") or {}).get("service.name")) == agent]
         for agent in EXP}
    rows = [json.loads(l) for l in open(f"{run_dir}/raw.jsonl", encoding="utf-8")]
    import csv
    mf = open(f"{run_dir}/metrics.csv", "w", encoding="utf-8-sig", newline="")
    mw = csv.writer(mf)
    mw.writerow(["unit", "rep", "agent", "label", "wall_s", "trace_s", "input_tokens", "output_tokens", "n_traces"])
    print(f'{"unit":6} {"agent":9} {"wall_s":>7} {"trace_s":>8} {"in_tok":>8} {"out_tok":>8} {"traces":>6}')
    agg = {"openclaw": [], "hermes": []}
    for r in rows:
        s, e = ts(r["start"]), ts(r["end"])
        c = [x for x in T[r["agent"]] if s <= ts(x["request_time"]) <= e]
        if r["agent"] == "openclaw":
            c = [x for x in c if (x.get("trace_metadata") or {}).get("mlflow.trace.tokenUsage")]
        tk = [json.loads((x.get("trace_metadata") or {}).get("mlflow.trace.tokenUsage") or "{}") for x in c]
        i = sum(t.get("input_tokens", 0) for t in tk)
        o = sum(t.get("output_tokens", 0) for t in tk)
        d = sum(float(x.get("execution_duration", "0s").rstrip("s")) for x in c)
        # Missing telemetry is unknown, not a zero-cost/zero-duration run.
        tokens_complete = bool(c) and all("input_tokens" in t and "output_tokens" in t for t in tk)
        duration_complete = bool(c) and all("execution_duration" in x for x in c)
        measured = (round(d, 2) if duration_complete else "",
                    i if tokens_complete else "", o if tokens_complete else "")
        if len(c) == 1 and tokens_complete and duration_complete and r["exit"] == 0 and r["answer"].strip():
            agg[r["agent"]].append((r["wall_s"], d, i, o))
        mw.writerow([r["unit"], r["rep"], r["agent"], r["label"], r["wall_s"], *measured, len(c)])
        print(r["unit"], r["agent"], "wall_s", r["wall_s"], "trace_s/tokens", measured, "traces", len(c))
    for a, v in agg.items():
        if v:
            print(a, "| complete successful single-trace coverage", len(v), "/", sum(r["agent"] == a for r in rows),
                  "| median wall", st.median(x[0] for x in v), "| median trace_s", round(st.median(x[1] for x in v), 1),
                  "| median in_tok", st.median(x[2] for x in v), "| median out_tok", st.median(x[3] for x in v))
        else:
            print(a, "| complete successful single-trace coverage 0 /", sum(r["agent"] == a for r in rows))
    mf.close()


if __name__ == "__main__":
    main(sys.argv[1])
