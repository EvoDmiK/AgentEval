#!/usr/bin/env python3
"""Build a self-contained blind scoring page from a run directory.

Usage: python3 scripts/make_score_page.py runs/full-r1 [rep]
Reads  datasets/base/1_문항표.csv and <run>/answers_blind.csv   (never mapping.csv / raw.jsonl: no agent names)
Writes <run>/score.html  (open locally; judgements are kept in the browser, export as CSV)
"""
import csv
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
run = sys.argv[1] if len(sys.argv) > 1 else "runs/full-r1"
rep = sys.argv[2] if len(sys.argv) > 2 else "1"
run_dir = run if os.path.isabs(run) else os.path.join(HERE, run)

Q = {r["문항ID"]: r for r in csv.DictReader(open(os.path.join(HERE, "datasets/base/1_문항표.csv"), encoding="utf-8-sig"))}
B = [r for r in csv.DictReader(open(os.path.join(run_dir, "answers_blind.csv"), encoding="utf-8-sig")) if r["rep"] == rep]

OPT = {
    "A": ["정확", "부분정확", "오답", "못찾음", "환각"],
    "B": ["정확", "부분정확", "오답", "못찾음", "환각"],
    "C": ["정답(없다고 답함)", "오답(지어냄=환각)", "회피"],
    "D": ["정답(전제 바로잡음)", "오답(전제 수용=환각)", "부분정답"],
}
cards = {}
for r in B:
    unit = r["unit"]
    cards.setdefault(unit, {"answers": {}})["answers"][r["label"]] = r["answer"]
out = []
for unit, c in sorted(cards.items()):
    if unit.startswith("E:"):
        members = [q for q in Q if Q[q]["유형"] == "오류 찾기" and Q[q]["제시 자료"].split()[0].split("/")[-1].startswith(unit[2:] + "_")]
        # members share the E-document file
        fn = [Q[q]["제시 자료"] for q in Q if Q[q]["문항ID"] == "E" + {"E1": "01", "E2": "06", "E3": "11"}[unit[2:]]][0]
        members = [q for q in Q if Q[q]["유형"] == "오류 찾기" and Q[q]["제시 자료"] == fn]
        out.append({"id": unit, "type": "E", "title": f"오류 찾기 · {unit[2:]} 문서 ({Q[members[0]]['출처 문서']})",
                    "question": Q[members[0]]["질문/지시"], "keys": [{"id": m, "key": Q[m]["정답"], "why": Q[m]["정답 근거(위치·원문)"]} for m in members],
                    "note": Q[members[0]]["비고"], "answers": c["answers"]})
    else:
        r = Q[unit]
        t = unit[0]
        out.append({"id": unit, "type": t, "title": f"{unit} · {r['유형']}", "question": r["질문/지시"], "key": r["정답"],
                    "why": r["정답 근거(위치·원문)"], "note": r["비고"], "options": OPT[t], "answers": c["answers"]})

data = json.dumps(out, ensure_ascii=False).replace("</", "<\\/")
page = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>블라인드 채점</title>
<style>
:root{--bg:#f6f6f4;--card:#fff;--ink:#1d1d1b;--mut:#6b6b66;--line:#d9d9d3;--acc:#2a5bd7;--ok:#1f7a45;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#212120;--ink:#ecece8;--mut:#9b9b94;--line:#3a3a37;--acc:#7da2ff;--ok:#5fcf8b;--bad:#ff8b82}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"Apple SD Gothic Neo",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
header b{font-size:16px}.pill{background:var(--card);border:1px solid var(--line);border-radius:99px;padding:2px 10px;font-size:13px}
button,select,textarea,input{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:5px 10px}
button{cursor:pointer}button.pri{background:var(--acc);color:#fff;border-color:var(--acc)}
main{max-width:1200px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:0 0 14px}
.card.done{border-color:var(--ok)}
.q{font-weight:600;margin:4px 0 8px}.key{background:rgba(42,91,215,.08);border-left:3px solid var(--acc);padding:6px 10px;border-radius:6px;margin:6px 0;font-size:14px}
.why{color:var(--mut);font-size:13px}.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}
@media (max-width:800px){.cols{grid-template-columns:1fr}}
.ans{border:1px solid var(--line);border-radius:8px;padding:8px 10px;min-width:0}.ans h4{margin:0 0 6px}
.txt{white-space:pre-wrap;word-break:break-word;font-size:14px;max-height:340px;overflow:auto;border-bottom:1px dashed var(--line);padding-bottom:8px;margin-bottom:8px}
.row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:4px 0}.small{font-size:13px;color:var(--mut)}
label.chk{display:flex;gap:6px;align-items:center;font-size:13px}textarea{width:100%;box-sizing:border-box;min-height:34px}
.hide{display:none}
</style></head><body>
<header><b>블라인드 채점</b><span class="pill" id="prog"></span>
<select id="ftype"><option value="">전체 유형</option><option>A</option><option>B</option><option>C</option><option>D</option><option>E</option></select>
<label class="chk"><input type="checkbox" id="fundone"> 미채점만</label>
<button class="pri" id="exp">CSV 내보내기</button><button id="clr">전체 초기화</button>
<span class="small">판정은 이 브라우저에 자동 저장됩니다. X/Y가 어느 에이전트인지는 이 페이지에 없습니다.</span></header>
<main id="main"></main>
<script>
const DATA=__DATA__;const REP="__REP__";const KEY="score-"+location.pathname+"-"+REP;
let S={};try{S=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(S))}catch(e){}};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const LB=["X","Y"];
function doneCount(c){ if(c.type==="E"){return LB.filter(l=>c.keys.every(k=>(S[c.id+"|"+l+"|"+k.id])!==undefined)).length}
 return LB.filter(l=>S[c.id+"|"+l+"|j"]).length }
function render(){
 const ft=document.getElementById("ftype").value, fu=document.getElementById("fundone").checked;
 const m=document.getElementById("main");m.innerHTML="";let tot=0,dn=0;
 DATA.forEach(c=>{const d=doneCount(c);tot+=2;dn+=d;
  if(ft&&c.type!==ft)return; if(fu&&d===2)return;
  const el=document.createElement("div");el.className="card"+(d===2?" done":"");
  let h=`<div class="small">${esc(c.title)}</div><div class="q">${esc(c.question)}</div>`;
  if(c.type==="E"){h+=`<div class="key"><b>심은 오류 5개 (정답)</b><ol>`+c.keys.map(k=>`<li>${esc(k.key)}<div class="why">${esc(k.why)}</div></li>`).join("")+`</ol></div>`}
  else{h+=`<div class="key"><b>정답:</b> ${esc(c.key)}<div class="why">${esc(c.why)}</div></div>`}
  if(c.note)h+=`<div class="small">비고: ${esc(c.note)}</div>`;
  h+=`<div class="cols">`+LB.map(l=>{
    const a=c.answers[l]||"(답변 없음)";let ctl="";
    if(c.type==="E"){ctl=c.keys.map((k,i)=>`<div class="row"><span class="small" style="min-width:56px">오류 ${i+1}</span>`+["찾음","놓침"].map(v=>`<label class="chk"><input type="radio" name="${c.id}|${l}|${k.id}" value="${v}" ${S[c.id+"|"+l+"|"+k.id]===v?"checked":""} data-k="${c.id}|${l}|${k.id}">${v}</label>`).join("")+`</div>`).join("")+
      `<div class="row"><span class="small">오탐(원문에 이미 있는 사항 제외)</span><input type="number" min="0" style="width:64px" value="${S[c.id+"|"+l+"|fp"]??""}" data-k="${c.id}|${l}|fp"></div>`}
    else{ctl=`<div class="row"><select data-k="${c.id}|${l}|j"><option value="">판정 선택</option>`+c.options.map(o=>`<option ${S[c.id+"|"+l+"|j"]===o?"selected":""}>${o}</option>`).join("")+`</select>`+
      `<label class="chk"><input type="checkbox" data-k="${c.id}|${l}|cite" ${S[c.id+"|"+l+"|cite"]?"checked":""}>인용 실제 확인</label></div>`}
    return `<div class="ans"><h4>답변 ${l}</h4><div class="txt">${esc(a)}</div>${ctl}<textarea placeholder="메모" data-k="${c.id}|${l}|memo">${esc(S[c.id+"|"+l+"|memo"]||"")}</textarea></div>`}).join("")+`</div>`;
  el.innerHTML=h;m.appendChild(el)});
 document.getElementById("prog").textContent=`채점 ${dn}/${tot}`;
 m.querySelectorAll("[data-k]").forEach(x=>{const f=()=>{const k=x.dataset.k;
   S[k]=x.type==="checkbox"?x.checked:(x.type==="radio"?x.value:x.value);if(x.type==="radio"&&!x.checked)return;save();
   if(x.tagName!=="TEXTAREA"&&!(x.type==="number")){const y=window.scrollY;render();window.scrollTo(0,y)} };
   x.addEventListener(x.tagName==="TEXTAREA"||x.type==="number"?"change":"input",f)})}
document.getElementById("ftype").onchange=render;document.getElementById("fundone").onchange=render;
document.getElementById("clr").onclick=()=>{if(confirm("모든 판정을 지울까요?")){S={};save();render()}};
document.getElementById("exp").onclick=()=>{
 const rows=[["unit","rep","label","item","judgement","cited_verified","false_positives","memo"]];
 DATA.forEach(c=>LB.forEach(l=>{
  if(c.type==="E"){const fp=S[c.id+"|"+l+"|fp"]??"";c.keys.forEach(k=>rows.push([c.id,REP,l,k.id,S[c.id+"|"+l+"|"+k.id]||"","",fp,S[c.id+"|"+l+"|memo"]||""]))}
  else rows.push([c.id,REP,l,c.id,S[c.id+"|"+l+"|j"]||"",S[c.id+"|"+l+"|cite"]?"Y":"",""  ,S[c.id+"|"+l+"|memo"]||""])}));
 const csv="\\ufeff"+rows.map(r=>r.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(",")).join("\\n");
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"}));a.download="scores-rep"+REP+".csv";a.click()};
render();
</script></body></html>"""
page = page.replace("__DATA__", data).replace("__REP__", rep)
out_path = os.path.join(run_dir, "score.html")
open(out_path, "w", encoding="utf-8").write(page)
print(out_path, len(out), "cards;", round(len(page) / 1024), "KB")
