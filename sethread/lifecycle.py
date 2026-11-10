"""Lifecycle: convergence state, evidence readiness per gate, staleness, and cross-functional handoffs.

convergence(m)          -> which lifecycle stage the product is in, inferred from the model (and overridable in meta.program.stage)
gate_readiness(m, store)-> for each gate: its exit criteria (explicit in gate.criteria or defaults per stage), measured value, pass/fail,
                           and the blockers (open findings, pending handoffs, stale verification) — the "evidence readiness" panel
staleness(m, store)     -> trace links whose source changed after the target was last verified/changed (upstream evolved)
workflows(m)            -> handoffs grouped by team pair, with what is pending/accepted/rejected
team_workload(m)        -> per team: work items, findings, handoffs, parts, tests they own
"""
from __future__ import annotations
import time
from . import derive as D
from .schema import LIFECYCLE

DEFAULT_CRITERIA = {   # stage → {coverage key: max allowed} ; "tests_passed_share" is a minimum share
    "Concept": {"needs_without_requirements": 0, "regulations_without_requirements": 0, "open_findings_critical": 0},
    "Development": {"requirements_without_tests": 0, "functions_without_allocation": 0, "logical_components_without_parts": 0, "interfaces_without_functions": 0, "unassessed_candidates": 0, "high_ap_fm_without_tests": 0,
                    "fm_without_tests": 0, "tests_unreferenced": 0, "stale_verification": 0, "open_findings_critical": 0, "pending_handoffs": 0, "tests_passed_share": 0.9},
    "Production": {"process_steps_without_pfmea": 0, "unassessed_process_candidates": 0, "buy_parts_without_supplier": 0, "pending_handoffs": 0, "tests_passed_share": 1.0, "open_findings_critical": 0, "stale_verification": 0},
    "Utilization": {"open_findings_critical": 0, "pending_handoffs": 0, "field_events_without_fm": 0},
    "Support": {"field_events_without_fm": 0, "open_findings_critical": 0},
    "Retirement": {"open_findings_critical": 0},
}
# INCOSE decision gates (handbook ch. 3) and common industry equivalents, by the stage they close or open
STAGE_GATES = {"Concept": ["MCR", "MDR", "SRR", "SDR", "SFR"], "Development": ["PDR", "CDR", "TRR", "SVR", "FCA", "PCA", "EVT", "DVT", "DV"],
               "Production": ["PRR", "PV", "PVT", "MRR"], "Utilization": ["ORR", "SOP", "LAUNCH", "LRR"], "Support": ["ISR"], "Retirement": ["DRR", "DR"]}
# which technical process the model is converging on inside the stage (shown as the sub-phase)

def _last_change(store) -> dict[str, float]:
    """element id → last applied-patch time (0 for seeded elements)."""
    out: dict[str, float] = {}
    try:
        for p in store.list_patches("applied"):
            ts = getattr(p, "applied", None) or p.created
            for op in p.ops: out[op.id] = max(out.get(op.id, 0), ts)
    except Exception: pass
    return out

def staleness(m, store=None):
    """A verification link is stale when the requirement (or the function/part it realizes) changed after the test last produced a result.
    An 'upstream evolved' item is any element whose upstream neighbour changed after it did."""
    lc = _last_change(store) if store is not None else {}
    stale_ver, upstream = [], []
    for r, rv in m["requirements"].items():
        rt = lc.get(r, 0)
        for t in rv["tests"]:
            tv = m["tests"].get(t)
            if not tv: continue
            res_ts = (tv.get("attrs") or {}).get("result_ts") or lc.get(t, 0)
            if tv.get("result") and rt > res_ts: stale_ver.append({"req": r, "test": t, "req_changed": rt, "result_ts": res_ts})
    for a, rel, b in D.trace(m):
        ta, tb = lc.get(a, 0), lc.get(b, 0)
        if ta and tb and ta > tb and rel in ("derives", "imposes", "realizes", "allocated to", "partitioned into", "realized by", "contains", "constrains", "serves"):
            upstream.append({"from": a, "rel": rel, "to": b, "changed": ta, "downstream_last": tb})
    return {"stale_verification": stale_ver, "upstream_evolved": upstream}

def convergence(m, detail=False):
    """Life-cycle stage (INCOSE/ISO 15288) the product is in, inferred from the model, and the technical process it is converging on.
    meta/program.stage overrides the stage; the process is always inferred."""
    prog = m.get("program") or {}
    rep = D.coverage_report(m)
    tests = list(m["tests"].values()); passed = sum(1 for t in tests if t.get("status") == "passed")
    if not m["requirements"] or rep["needs_without_requirements"]: stage, proc = "Concept", "Stakeholder needs and requirements definition" if m["needs"] else "Business or mission analysis"
    elif rep["requirements_without_tests"] and not m["functions"]: stage, proc = "Development", "System requirements definition"
    elif rep["functions_without_allocation"] or not m["parts"]: stage, proc = "Development", "System architecture definition" if not m["logical_components"] else "Design definition"
    elif rep["unassessed_candidates"] or rep["high_ap_fm_without_tests"]: stage, proc = "Development", "System analysis"
    elif rep.get("buy_parts_without_supplier"): stage, proc = "Development", "Implementation"
    elif tests and passed < len(tests): stage, proc = "Development", "Verification"
    elif m.get("process_steps") and (rep["process_steps_without_pfmea"] or rep.get("unassessed_process_candidates")): stage, proc = "Production", "Transition"
    elif m.get("field_events"): stage, proc = ("Support", "Maintenance") if rep["field_events_without_fm"] else ("Utilization", "Operation")
    else: stage, proc = "Production", "Validation"
    if prog.get("stage") in LIFECYCLE: stage = prog["stage"]
    return (stage, proc) if detail else stage

def gate_readiness(m, store=None):
    rep = D.coverage_report(m); st = staleness(m, store); stage, phase = convergence(m, detail=True)
    tests = list(m["tests"].values()); passed = sum(1 for t in tests if t.get("status") == "passed"); share = passed / len(tests) if tests else 0.0
    measured = {k: (len(v) if hasattr(v, "__len__") and not isinstance(v, dict) else v) for k, v in rep.items() if k not in ("counts", "clean")}
    measured["stale_verification"] = len(st["stale_verification"]); measured["upstream_evolved"] = len(st["upstream_evolved"]); measured["tests_passed_share"] = round(share, 3)
    gates = []
    for g, gv in m["gates"].items():
        gstage = (gv.get("stage") if gv.get("stage") in LIFECYCLE else None) or next((s for s, names in STAGE_GATES.items() if g.upper() in names), stage)
        crit = gv.get("criteria") or DEFAULT_CRITERIA.get(gstage, {})
        rows = []
        for k, limit in crit.items():
            v = measured.get(k, 0)
            ok = (v >= limit) if k == "tests_passed_share" else (v <= limit)
            rows.append({"criterion": k.replace("_", " "), "key": k, "value": v, "limit": limit, "ok": ok})
        blockers = {"open_findings": rep["open_findings_critical"], "pending_handoffs": [h for h in rep["pending_handoffs"] if not m["handoffs"][h].get("gate") or m["handoffs"][h]["gate"] == g],
                    "stale_verification": [f"{x['req']}→{x['test']}" for x in st["stale_verification"]], "upstream_evolved": len(st["upstream_evolved"])}
        ready = all(r["ok"] for r in rows) and not blockers["open_findings"] and not blockers["pending_handoffs"]
        gates.append({"gate": g, "stage": gstage, "date": gv["date"], "exit": gv["exit"], "status": gv.get("status", "planned"), "criteria": rows, "blockers": blockers, "ready": ready,
                      "score": round(100 * sum(1 for r in rows if r["ok"]) / max(1, len(rows)))})
    gates.sort(key=lambda g: g["date"])
    nxt = next((g for g in gates if g["status"] != "passed"), gates[-1] if gates else None)
    return {"stage": stage, "phase": phase, "stages": LIFECYCLE, "stage_index": LIFECYCLE.index(stage), "gates": gates, "next_gate": nxt, "measured": measured,
            "alerts": _alerts(m, rep, st), "verification": {"coverage": [len(m["requirements"]) - len(rep["requirements_without_tests"]), len(m["requirements"])], "passed": [passed, len(tests)], "fresh": [len(tests) - len(st["stale_verification"]), len(tests)]}}

def _alerts(m, rep, st):
    a = []
    if st["upstream_evolved"]: a.append({"level": "warn", "text": f"{len(st['upstream_evolved'])} stale items — upstream evolved", "to": "stale"})
    if st["stale_verification"]: a.append({"level": "bad", "text": f"{len(st['stale_verification'])} stale verification links", "to": "stale"})
    if rep["open_findings_critical"]: a.append({"level": "bad", "text": f"{len(rep['open_findings_critical'])} critical/major findings open", "to": "findings"})
    if rep["pending_handoffs"]: a.append({"level": "bad", "text": f"{len(rep['pending_handoffs'])} team handoffs not accepted", "to": "handoffs"})
    if rep["high_ap_fm_without_tests"]: a.append({"level": "bad", "text": f"{len(rep['high_ap_fm_without_tests'])} High-AP failure modes without a test", "to": "dfmea"})
    if rep["unassessed_candidates"]: a.append({"level": "warn", "text": f"{len(rep['unassessed_candidates'])} failure-mode candidates unassessed", "to": "dfmea"})
    if rep["process_steps_without_pfmea"]: a.append({"level": "warn", "text": f"{len(rep['process_steps_without_pfmea'])} process steps without PFMEA", "to": "pfmea"})
    if rep.get("unassessed_process_candidates"): a.append({"level": "warn", "text": f"{len(rep['unassessed_process_candidates'])} PFMEA candidates unassessed", "to": "pfmea"})
    if rep["buy_parts_without_supplier"]: a.append({"level": "warn", "text": f"{len(rep['buy_parts_without_supplier'])} buy parts without a supplier", "to": "suppliers"})
    if rep["field_events_without_fm"]: a.append({"level": "warn", "text": f"{len(rep['field_events_without_fm'])} field events not tied to a failure mode", "to": "fracas"})
    return a

def workflows(m):
    teams = m.get("teams", {}); out = {}
    for h, hv in m.get("handoffs", {}).items():
        key = (hv["from_team"], hv["to_team"]); out.setdefault(key, {"from": teams.get(hv["from_team"], {}).get("name", hv["from_team"]), "to": teams.get(hv["to_team"], {}).get("name", hv["to_team"]), "pending": [], "accepted": [], "rejected": []})
        out[key][{"pending": "pending", "accepted": "accepted"}.get(hv["status"], "rejected")].append({"id": h, **hv})
    groups = sorted({t for k in out for t in k})
    return {"pairs": list(out.values()), "groups": [teams.get(g, {}).get("name", g) for g in groups], "pending_total": sum(len(p["pending"]) for p in out.values())}

def team_workload(m):
    out = {}
    for t, tv in m.get("teams", {}).items():
        out[t] = {"name": tv["name"], "discipline": tv.get("discipline", ""), "lead": tv.get("lead", ""),
                  "work_items": [w for w, wv in m.get("work_items", {}).items() if wv.get("team") == t and wv["status"] != "done"],
                  "findings": [f for f, fv in m.get("findings", {}).items() if fv.get("owner") in (tv.get("lead"), t) and fv["status"] != "closed"],
                  "handoffs_in": [h for h, hv in m.get("handoffs", {}).items() if hv["to_team"] == t and hv["status"] == "pending"],
                  "handoffs_out": [h for h, hv in m.get("handoffs", {}).items() if hv["from_team"] == t and hv["status"] == "pending"],
                  "parts": [p for p, pv in m["parts"].items() if pv.get("owner_team") == t], "tests": [x for x, xv in m["tests"].items() if xv.get("owner_team") == t],
                  "process_steps": [p for p, pv in m.get("process_steps", {}).items() if pv.get("team") == t]}
    return out
