"""Model quality: deterministic checks the agent cannot talk its way around.

- requirement_quality(text, attr) : INCOSE Guide for Writing Requirements (GtWR) rules — ambiguity, escape clauses,
  vagueness, passive/unclear actor, compound ("and"/"or" multiple shalls), negatives, pronouns, missing "shall",
  missing measurable attribute, units. Returns findings with rule ids R1…R12 and a 0–100 score.
- scorecard(model) : one number per dimension and an overall grade, used by `launch eval`, the Scorecard page and the
  reviewer agent. Dimensions: trace coverage, requirement quality, FMEA completeness, architecture completeness,
  verification completeness, provenance (how much of the model came through reviewed patches).
"""
from __future__ import annotations
import re
from . import derive as D

AMBIGUOUS = ["adequate", "appropriate", "as appropriate", "as required", "as applicable", "sufficient", "user-friendly", "easy", "fast", "quick", "robust", "reliable", "efficient", "effective",
             "minimal", "minimize", "maximize", "optimal", "optimize", "approximately", "about", "roughly", "several", "some", "many", "few", "significant", "reasonable", "normal", "typical",
             "state of the art", "best practice", "seamless", "intuitive", "flexible", "scalable", "high performance", "low cost", "good", "bad", "better", "worse", "etc", "and/or", "support", "handle", "timely"]
ESCAPE = ["if possible", "where possible", "as far as possible", "when practical", "if practical", "where appropriate", "to the extent", "as necessary", "if necessary", "unless", "except"]
NEGATIVE = ["shall not", "must not", "should not", "never", "no "]
PRONOUNS = [" it ", " its ", " they ", " them ", " this ", " that ", " these ", " those ", " which "]
UNIT_RE = re.compile(r"\d\s*(%|°C|°F|K|V|mV|A|mA|µA|uA|W|mW|Wh|mAh|Ah|Ω|ohm|Hz|kHz|MHz|GHz|s|ms|µs|us|min|h|hours?|days?|years?|mm|cm|m|km|g|kg|N|Nm|Pa|kPa|bar|dB|dBA|dBm|lux|cd|lm|bit|bits|B|kB|MB|GB|bps|kbps|Mbps|rpm|cycles?|mm/s|m/s|g|Grms|J|mJ|ppm|%RH|RH|IP\d\d)(?![A-Za-z])", re.I)
NUM_RE = re.compile(r"[<>≤≥=]\s*\d|\d+(\.\d+)?")

def requirement_quality(text: str, attr: str = "", rtype: str = "") -> dict:
    t = " " + text.strip() + " "; low = t.lower(); f = []
    if " shall " not in low and " must " not in low: f.append(("R1", "no 'shall' — not a binding requirement statement"))
    if low.count(" shall ") > 1: f.append(("R2", f"{low.count(' shall ')} 'shall' — split into atomic requirements"))
    for w in AMBIGUOUS:
        if re.search(rf"\b{re.escape(w)}\b", low): f.append(("R3", f"vague term '{w}'")); break
    for w in ESCAPE:
        if w in low: f.append(("R4", f"escape clause '{w}'")); break
    if " and " in low and low.count(" shall ") <= 1 and rtype.upper() not in ("INT",) and len(re.findall(r"\b(and|or)\b", low)) >= 3: f.append(("R5", "compound statement — several 'and'/'or'; consider splitting"))
    for w in NEGATIVE:
        if w in low and rtype.upper() not in ("SAFE", "SEC"): f.append(("R6", f"negative requirement '{w.strip()}' — state what the system shall do")); break
    for w in PRONOUNS:
        if w in low: f.append(("R7", f"pronoun '{w.strip()}' — name the element")); break
    if not NUM_RE.search(t) and not NUM_RE.search(attr or ""): f.append(("R8", "no measurable quantity in text or attribute"))
    elif not UNIT_RE.search(t) and not UNIT_RE.search(attr or "") and rtype.upper() in ("PERF", "REL", "ENV", "SAFE", "PWR"): f.append(("R9", "number without a unit"))
    if re.search(r"\b(is|are|will be|was|were)\s+\w+ed\b", low) and " shall " not in low: f.append(("R10", "passive/descriptive voice — use 'The <system> shall <verb>'"))
    if len(text.split()) > 45: f.append(("R11", f"{len(text.split())} words — long; split or move rationale to attributes"))
    if re.search(r"\b(TBD|TBC|TBR|\?\?)\b", text): f.append(("R12", "contains TBD/TBC/TBR"))
    weights = {"R1": 30, "R2": 15, "R3": 15, "R4": 15, "R5": 8, "R6": 5, "R7": 8, "R8": 20, "R9": 8, "R10": 8, "R11": 5, "R12": 15}
    score = max(0, 100 - sum(weights[c] for c, _ in f))
    return {"score": score, "findings": [{"rule": c, "msg": m} for c, m in f]}

def requirements_report(m):
    out = []
    for rid, r in m["requirements"].items():
        q = requirement_quality(r["text"], r.get("attr", ""), r.get("type", ""))
        out.append({"id": rid, "type": r.get("type", ""), "text": r["text"], "attr": r.get("attr", ""), **q})
    return out

def scorecard(m, store=None) -> dict:
    rep = D.coverage_report(m); c = rep["counts"]
    n_req = len(m["requirements"]) or 1; n_fun = len(m["functions"]) or 1; n_test = len(m["tests"]) or 1
    gaps = sum(len(v) for k, v in rep.items() if k not in ("counts", "clean"))
    trace = max(0, 100 - 100 * gaps / max(1, n_req + n_fun + n_test))
    rq = requirements_report(m); req_quality = sum(r["score"] for r in rq) / max(1, len(rq)) if rq else 0
    fmea = 100 * (c["assessed"] + c["screened"]) / max(1, c["candidates"]) if c["candidates"] else 0
    high_cov = 100 * (1 - len(rep["high_ap_fm_without_tests"]) / max(1, c["high_ap"])) if c["high_ap"] else 100
    arch_items = [bool(m["logical_components"]), bool(m["logical_interfaces"]), bool(m["parts"]), bool(m["interfaces"]), bool(m["states"]), bool(m["arch_decisions"]), bool(m["nodes"]),
                  all(p.get("discipline") for p in m["parts"].values()) if m["parts"] else False]
    arch = 100 * sum(arch_items) / len(arch_items)
    tests = list(m["tests"].values())
    ver_items = [sum(1 for t in tests if t.get("method")) , sum(1 for t in tests if t.get("passfail")), sum(1 for t in tests if t.get("gate")), sum(1 for t in tests if t.get("units"))]
    verification = 100 * sum(ver_items) / max(1, 4 * len(tests)) if tests else 0
    prov = 0
    if store is not None:
        try:
            touched = set(); import json
            if getattr(store, "log_path", None):
                for line in open(store.log_path):
                    ev = json.loads(line)
                    for op in ev.get("ops", []): touched.add(op.get("id"))
            else:
                for p in store.list_patches("applied"):
                    if not p.author.startswith("system:"):
                        for op in p.ops: touched.add(op.id)
            total = sum(len(m[k]) for k in m if isinstance(m[k], dict) and k not in ("meta", "program"))
            prov = 100 * len([x for x in touched if x]) / max(1, total)
        except Exception: prov = 0
    dims = {"trace_coverage": round(trace), "requirement_quality": round(req_quality), "fmea_completeness": round(fmea), "high_ap_test_coverage": round(high_cov),
            "architecture_completeness": round(arch), "verification_completeness": round(verification), "provenance": round(min(100, prov))}
    w = {"trace_coverage": 3, "requirement_quality": 2, "fmea_completeness": 2, "high_ap_test_coverage": 2, "architecture_completeness": 1, "verification_completeness": 1, "provenance": 0.5}
    overall = sum(dims[k] * w[k] for k in dims) / sum(w.values())
    grade = "A" if overall >= 90 else "B" if overall >= 80 else "C" if overall >= 65 else "D" if overall >= 50 else "F"
    worst = sorted(rq, key=lambda r: r["score"])[:10]
    return {"overall": round(overall), "grade": grade, "dimensions": dims, "gaps": gaps, "counts": c,
            "worst_requirements": [{"id": r["id"], "score": r["score"], "findings": [f["msg"] for f in r["findings"]]} for r in worst if r["score"] < 100]}
