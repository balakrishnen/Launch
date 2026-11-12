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
        try:
            from . import pdp as _pdp; mx = _pdp.matrix(m); dl = mx["per_gate"].get(g, {"done": 0, "partial": 0, "missing": 0, "total": 0})
        except Exception: dl = {"done": 0, "partial": 0, "missing": 0, "total": 0}
        if dl["total"]: ready = ready and dl["done"] == dl["total"]
        gates.append({"gate": g, "stage": gstage, "date": gv["date"], "exit": gv["exit"], "status": gv.get("status", "planned"), "criteria": rows, "blockers": blockers, "ready": ready, "deliverables": dl, "phase": gv.get("phase"),
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


def subsystem_scope(m, tv: dict) -> dict:
    """closure of a subsystem team's scope: parts subtree, logical components, functions, requirements, interfaces (internal vs boundary),
    failure modes, tests, MoEs, and the parts' budgets (mass/cost attrs rolled up)."""
    roots = list(tv.get("parts") or []); lcs = set(tv.get("lcs") or [])
    parts = set()
    def walk(p):
        if p in parts or p not in m["parts"]: return
        parts.add(p)
        for c, cv in m["parts"].items():
            if cv.get("parent") == p: walk(c)
    for r in roots: walk(r)
    for lc in lcs:
        for p in m["logical_components"].get(lc, {}).get("parts", []): walk(p)
    for lc, v in m["logical_components"].items():
        if set(v.get("parts", [])) & parts: lcs.add(lc)
    funcs = {f for f, v in m["functions"].items() if set(v.get("alloc", [])) & parts or any(f in m["logical_components"][lc].get("funcs", []) for lc in lcs if lc in m["logical_components"])}
    reqs = sorted({r for f in funcs for r in m["functions"][f].get("reqs", [])})
    internal = [i for i, v in m["interfaces"].items() if v.get("a") in parts and v.get("b") in parts]
    boundary = [i for i, v in m["interfaces"].items() if (v.get("a") in parts) != (v.get("b") in parts)]
    fms = [x for x in D.fmea(m) if x.get("element") in parts or x.get("element") in funcs]
    tests = sorted({t for r in reqs for t in m["requirements"][r].get("tests", [])})
    needs = sorted({n for r in reqs for n in m["requirements"][r].get("from_", [])})
    moes = sorted(set(tv.get("moes") or []) | {m["needs"][n]["moe"] for n in needs if n in m["needs"] and m["needs"][n].get("moe")})
    def num(x):
        try: return float(x)
        except (TypeError, ValueError): return None
    budgets = {}
    for key in ("mass_g", "mass_kg", "cost_usd", "cost", "power_W", "power_mW"):
        vals = [num((m["parts"][p].get("attrs") or {}).get(key)) for p in parts]; vals = [v for v in vals if v is not None]
        if vals: budgets[key] = round(sum(vals), 3)
    return {"roots": roots, "parts": sorted(parts), "lcs": sorted(lcs), "functions": sorted(funcs), "requirements": reqs, "interfaces_internal": internal, "interfaces_boundary": boundary,
            "boundary": [{"id": i, **m["interfaces"][i], "outside": m["interfaces"][i]["b"] if m["interfaces"][i]["a"] in parts else m["interfaces"][i]["a"]} for i in boundary],
            "fmea": fms, "tests": tests, "needs": needs, "moes": [{"id": x, **m["moes"][x]} for x in moes if x in m["moes"]], "budgets": budgets,
            "verification": {"covered": len([r for r in reqs if m["requirements"][r].get("tests")]), "total": len(reqs), "passed": len([t for t in tests if m["tests"].get(t, {}).get("status") == "passed"]), "tests": len(tests)},
            "tree": [{"id": p, "name": m["parts"][p]["name"], "parent": m["parts"][p].get("parent") if m["parts"][p].get("parent") in parts else None, "discipline": m["parts"][p].get("discipline"), "owner_team": m["parts"][p].get("owner_team"), "make_buy": m["parts"][p].get("make_buy")} for p in sorted(parts)]}

FOCUS_VIEWS = {   # what a functional team's cross-cutting view is made of
    "reliability": lambda m, rep: {"high_ap": [x for x in D.fmea(m) if x.get("AP") == "H"], "unassessed": rep["unassessed_candidates"][:100], "field_events": list(m.get("field_events", {}).keys())},
    "quality": lambda m, rep: {"findings_open": [f for f, v in m.get("findings", {}).items() if v["status"] != "closed"], "process_steps_without_pfmea": rep["process_steps_without_pfmea"], "reviews": list(m.get("reviews", {}).keys())},
    "safety": lambda m, rep: {"hazards": [x for x in D.fmea(m) if (x.get("S") or 0) >= 9], "safety_functions": [f for f, v in m["functions"].items() if v.get("safety_decision")]},
    "compliance": lambda m, rep: {"regulations": list(m["regulations"].keys()), "regulations_without_requirements": rep["regulations_without_requirements"], "certification": [t for t, v in m["tests"].items() if v.get("kind") in ("certification", "cert")]},
    "test": lambda m, rep: {"tests": list(m["tests"].keys()), "requirements_without_tests": rep["requirements_without_tests"], "stale": []},
    "manufacturing": lambda m, rep: {"process_steps": list(m.get("process_steps", {}).keys()), "process_steps_without_pfmea": rep["process_steps_without_pfmea"]},
    "sourcing": lambda m, rep: {"suppliers": list(m.get("suppliers", {}).keys()), "buy_parts_without_supplier": rep["buy_parts_without_supplier"]},
    "program": lambda m, rep: {"gates": list(m["gates"].keys()), "pending_handoffs": rep["pending_handoffs"], "risks": list(m.get("risks", {}).keys())},
}
from . import business as _B
FOCUS_VIEWS.update(_B.FOCUS_VIEWS)   # marketing, sales, finance, hr/people, facilities, legal, service

def team_workspace(m, tid: str, store=None, threads: list | None = None) -> dict:
    """System-of-record view for one team: KPIs, every record they own by kind, what waits on them, what they wait for,
    the failure modes and tests on their parts, recent activity on their records, and conversations that touched them."""
    tv = m["teams"].get(tid)
    if not tv: return {}
    lead = tv.get("lead", ""); members = set(tv.get("members", [])) | ({lead} if lead else set())
    mine = lambda v, *keys: any(v.get(k) in (tid, lead) or v.get(k) in members for k in keys)
    recs = {
        "parts": [p for p, v in m["parts"].items() if v.get("owner_team") == tid],
        "tests": [t for t, v in m["tests"].items() if v.get("owner_team") == tid],
        "work_items": [w for w, v in m.get("work_items", {}).items() if v.get("team") == tid or mine(v, "owner")],
        "findings": [f for f, v in m.get("findings", {}).items() if mine(v, "owner")],
        "risks": [r for r, v in m.get("risks", {}).items() if v.get("team") == tid or mine(v, "owner")],
        "process_steps": [p for p, v in m.get("process_steps", {}).items() if v.get("team") == tid],
        "suppliers": [s for s, v in m.get("suppliers", {}).items() if mine(v, "owner")],
        "tables": [t for t, v in m.get("tables", {}).items() if v.get("owner_team") == tid],
        "notes": [n for n, v in m.get("notes", {}).items() if v.get("owner_team") == tid or v.get("author") in members],
        "simulations": [s for s, v in m.get("simulations", {}).items() if v.get("owner_team") == tid],
    }
    parts = set(recs["parts"])
    # elements that hang off their parts: functions allocated, interfaces, failure modes (derived), requirements realized
    funcs = [f for f, v in m["functions"].items() if set(v.get("alloc", [])) & parts]
    ifaces = [i for i, v in m["interfaces"].items() if v.get("a") in parts or v.get("b") in parts]
    reqs = sorted({r for f in funcs for r in m["functions"][f].get("reqs", [])})
    fms = [x for x in D.fmea(m) if (x.get("element") in parts or x.get("element") in funcs)]
    high = [x for x in fms if x.get("AP") == "H"]
    hand_in = [{"id": h, **v} for h, v in m.get("handoffs", {}).items() if v["to_team"] == tid and v["status"] == "pending"]
    hand_out = [{"id": h, **v} for h, v in m.get("handoffs", {}).items() if v["from_team"] == tid and v["status"] == "pending"]
    open_wi = [w for w in recs["work_items"] if m["work_items"][w]["status"] != "done"]
    overdue = [w for w in open_wi if (m["work_items"][w].get("due") or "9999") < time.strftime("%Y-%m-%d")]
    open_f = [f for f in recs["findings"] if m["findings"][f]["status"] != "closed"]
    tests_passed = [t for t in recs["tests"] if m["tests"][t].get("status") == "passed"]
    kpis = {"open_work_items": len(open_wi), "overdue": len(overdue), "open_findings": len(open_f), "critical_findings": len([f for f in open_f if m["findings"][f]["severity"] in ("critical", "major")]),
            "handoffs_waiting_on_us": len(hand_in), "handoffs_we_wait_for": len(hand_out), "tests_passed": [len(tests_passed), len(recs["tests"])], "high_ap_on_our_parts": len(high),
            "high_ap_without_test": len([x for x in high if not x.get("tests")]), "open_risks": len([r for r in recs["risks"] if m["risks"][r]["status"] == "open"])}
    # activity: applied patches touching our records
    ours = {x for xs in recs.values() for x in xs} | set(funcs) | set(ifaces)
    activity = []
    try:
        for p in sorted(store.list_patches("applied"), key=lambda p: -(getattr(p, "applied", None) or p.created))[:200]:
            hit = [o for o in p.ops if o.id in ours]
            if hit: activity.append({"patch": p.id, "ts": getattr(p, "applied", None) or p.created, "author": p.author, "rationale": p.rationale, "ids": [o.id for o in hit][:8], "n": len(hit)})
            if len(activity) >= 30: break
    except Exception: pass
    convs = [t for t in (threads or []) if any(x in (t.get("last", "") + t.get("title", "")) for x in list(ours)[:200])][:10]
    sub = subsystem_scope(m, tv) if tv.get("kind") == "subsystem" else None
    focus = None
    if tv.get("kind") != "subsystem":
        fv = FOCUS_VIEWS.get(tv.get("focus") or tv.get("discipline") or "")
        if fv:
            try: focus = {"name": tv.get("focus") or tv.get("discipline"), **fv(m, D.coverage_report(m))}
            except Exception: focus = None
    if sub:   # a subsystem team's records include everything in its scope, not only explicitly owned rows
        recs["parts"] = sorted(set(recs["parts"]) | set(sub["parts"])); recs["tests"] = sorted(set(recs["tests"]) | set(sub["tests"]))
        funcs = sub["functions"]; ifaces = sub["interfaces_internal"] + sub["interfaces_boundary"]; reqs = sub["requirements"]; fms = sub["fmea"]; high = [x for x in fms if x.get("AP") == "H"]
        kpis.update(high_ap_on_our_parts=len(high), high_ap_without_test=len([x for x in high if not x.get("tests")]), tests_passed=[sub["verification"]["passed"], sub["verification"]["tests"]], req_coverage=[sub["verification"]["covered"], sub["verification"]["total"]], boundary_interfaces=len(sub["interfaces_boundary"]))
    return {"id": tid, **tv, "members": sorted(members), "kpis": kpis, "records": recs, "subsystem": sub, "focus": focus, "functions": funcs, "interfaces": ifaces, "requirements": reqs, "high_ap": high[:50], "handoffs_in": hand_in, "handoffs_out": hand_out,
            "due_soon": sorted([{"id": w, **m["work_items"][w]} for w in open_wi if m["work_items"][w].get("due")], key=lambda w: w["due"])[:10], "activity": activity, "conversations": convs}
