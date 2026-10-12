import csv, sys, os
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Q = {r["문항ID"]: r for r in csv.DictReader(open(os.path.join(H, "datasets/base/1_문항표.csv"), encoding="utf-8-sig"))}
ans = {}
for r in csv.DictReader(open(os.path.join(H, "runs/full-r1/answers_blind.csv"), encoding="utf-8-sig")):
    ans.setdefault(r["unit"], {})[r["label"]] = r["answer"]
lim = int(sys.argv[3]) if len(sys.argv) > 3 else 750
for qid in [q for q in Q if sys.argv[1] <= q <= sys.argv[2] and not q.startswith("E")]:
    r = Q[qid]
    print("=" * 90); print(f"{qid} [{r['유형']}] {r['질문/지시'].split('질문이다. ')[-1]}")
    print("KEY:", r["정답"]);
    for l in "XY":
        a = ans[qid][l].replace("\n", " / ")
        print(f"  [{l}] {a[:lim]}")
