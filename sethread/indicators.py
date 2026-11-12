"""Leading indicators — the early-warning layer on the graph, so control is anticipatory rather than reactive.

Each indicator is computed from the current model and, where it is a rate, from the model at an earlier revision (the patch
history). Each carries: value, unit, threshold (amber / red), direction (higher is worse), trend over the window, the elements
behind it, and which upcoming gate it threatens. Gate-slip risk per gate = the red/amber indicators that bear on its
deliverables, weighted by days to the gate.

The set is the one that, in practice, predicts cost and schedule surprises before the gate review does:
  requirement churn · late requirements · unassessed failure-mode candidates · High-AP without a test · test fail rate ·
  test freshness · ECO rate · open CAPA age · supplier PPM · parts late to order · tooling T1 vs build · BOM vs target ·
  staffing (teams without lead) · handoffs waiting · deliverable burn (open deliverables vs days to gate)
"""
from __future__ import annotations
import datetime as _dt
from . import derive as D


# GAO evidence themes (NASA project reports): TRL technology readiness · PA project assessment · CDA critical design attributes ·
# C&SP cost & schedule performance · RA&CNTRL risk assessment & control · KM knowledge management
THEMES = {"TRL": "Technology readiness", "PA": "Project assessment", "CDA": "Critical design attributes", "C&SP": "Cost & schedule performance", "RA&CNTRL": "Risk assessment & control", "KM": "Knowledge management"}
THEME_OF = {"trl_below_gate": "TRL", "trl_overstated": "TRL", "req_churn": "PA", "req_unverified": "PA", "teams_without_lead": "PA", "handoffs_waiting": "PA", "parts_unquoted": "PA",
            "cda_violating": "CDA", "cda_tight": "CDA", "cda_worsening": "CDA", "cda_unmeasured": "CDA",
            "bom_vs_target": "C&SP", "parts_late_to_order": "C&SP", "tooling_risk": "C&SP", "work_overdue": "C&SP", "eco_rate": "C&SP",
            "fm_unassessed": "RA&CNTRL", "high_ap_untested": "RA&CNTRL", "test_fail_rate": "RA&CNTRL", "capa_overdue": "RA&CNTRL", "supplier_ppm": "RA&CNTRL",
            "test_stale": "KM", "eco_open": "KM"}


def _days(date):
    try: return (_dt.date.fromisoformat(str(date)[:10]) - _dt.date.today()).days
    except Exception: return None


def _level(v, amber, red, higher_worse=True):
    if v is None: return "unknown"
    if higher_worse: return "red" if v >= red else ("amber" if v >= amber else "green")
    return "red" if v <= red else ("amber" if v <= amber else "green")


def compute(m, store=None, window_revs: int = 25) -> dict:
    prev = None
    try:
        if store is not None:
            rev = store.rev(); prev = store.load(max(1, rev - window_revs)) if rev > 1 else None
    except Exception: prev = None
    rep = D.coverage_report(m); fm = D.fmea(m)
    gates = sorted(((g, v) for g, v in m["gates"].items() if v.get("date")), key=lambda kv: kv[1]["date"])
    nxt = next(((g, v) for g, v in gates if (_days(v["date"]) or -1) >= 0), (None, None))
    days_to_next = _days(nxt[1]["date"]) if nxt[1] else None
    ind = []

    def add(key, name, value, unit, amber, red, higher_worse=True, ids=None, gate_scope="all", note=""):
        ind.append({"key": key, "name": name, "value": value, "unit": unit, "amber": amber, "red": red, "higher_worse": higher_worse, "level": _level(value, amber, red, higher_worse), "ids": (ids or [])[:12], "n": len(ids or []), "gate_scope": gate_scope, "note": note, "theme": THEME_OF.get(key, "PA")})

    # --- TRL and critical design attributes (GAO themes TRL, CDA)
    try:
        from . import maturity as MAT
        tr = [r for r in MAT.trl_rows(m) if r["new_technology"]]
        need = MAT.TRL_MIN.get(nxt[0], 5) if nxt[0] else 5
        below = [r["part"] for r in tr if (r["declared"] if r["declared"] is not None else r["demonstrated"]) < need]
        over = [r["part"] for r in tr if r["gap"] is not None and r["gap"] >= 2]
        add("trl_below_gate", f"New technologies below TRL {need} for {nxt[0] or 'the next gate'}", len(below), "parts", 1, 2, ids=below)
        add("trl_overstated", "Declared TRL ≥ 2 above what the evidence shows", len(over), "parts", 1, 2, ids=over, note="declared maturity without tests, units or qualification behind it")
        cd = MAT.cda_rows(m)
        viol = [r["id"] for r in cd if r["status"] == "violating limit"]; tight = [r["id"] for r in cd if r["status"] in ("tight", "below target")]; wors = [r["id"] for r in cd if r["trend"] == "worsening"]; unm = [r["id"] for r in cd if r["current"] is None]
        add("cda_violating", "Critical design attributes over their limit", len(viol), "CDAs", 1, 1, ids=viol)
        add("cda_tight", "Critical design attributes below target or within 10 % of limit", len(tight), "CDAs", 1, 3, ids=tight)
        add("cda_worsening", "Critical design attributes trending the wrong way", len(wors), "CDAs", 1, 2, ids=wors)
        add("cda_unmeasured", "Critical design attributes never measured", len(unm), "CDAs", 1, 3, ids=unm)
    except Exception as e:
        ind.append({"key": "maturity", "name": "TRL / CDA indicators", "level": "unknown", "note": str(e), "theme": "TRL"})

    # --- requirements stability
    n_req = max(1, len(m["requirements"]))
    if prev is not None:
        changed = [r for r, v in m["requirements"].items() if prev["requirements"].get(r) and prev["requirements"][r].get("text") != v.get("text")]
        new = [r for r in m["requirements"] if r not in prev["requirements"]]
        add("req_churn", "Requirement churn (changed or added over the window)", round(100 * (len(changed) + len(new)) / n_req, 1), "%", 10, 25, ids=changed + new, note="late churn is the strongest predictor of integration surprises")
    unverified = [r for r, v in m["requirements"].items() if not v.get("tests")]
    add("req_unverified", "Requirements without a test", round(100 * len(unverified) / n_req, 1), "%", 10, 30, ids=unverified)
    # --- risk maturity
    cands = rep.get("unassessed_candidates", []); add("fm_unassessed", "Failure-mode candidates not yet assessed", len(cands), "items", 5, 15, ids=sorted({(c.get("element") if isinstance(c, dict) else c) for c in cands}))
    hi_untested = [x["id"] for x in fm if x.get("AP") == "H" and not x.get("tests")]
    add("high_ap_untested", "High-AP failure modes without a test", len(hi_untested), "items", 1, 3, ids=hi_untested)
    # --- verification health
    tests = m["tests"]; runs = m.get("test_runs", {})
    recent = [r for r in runs.values() if (_days(r.get("date")) or -999) >= -30]
    fails = [r for r in recent if r.get("result") == "fail"]
    add("test_fail_rate", "Test fail rate, last 30 days of runs", round(100 * len(fails) / len(recent), 1) if recent else None, "%", 15, 30, ids=[r.get("test") for r in fails])
    stale = [t for t, v in tests.items() if v.get("status") == "passed" and v.get("last_run") and (_days(v["last_run"]) or 0) < -60]
    add("test_stale", "Passed tests older than 60 days (evidence going stale)", len(stale), "tests", 3, 8, ids=stale)
    # --- change pressure
    ecos = m.get("change_orders", {}); open_eco = [c for c, v in ecos.items() if v.get("status") not in ("released", "rejected")]
    add("eco_open", "Change orders open", len(open_eco), "ECOs", 3, 6, ids=open_eco)
    if prev is not None:
        add("eco_rate", "Change orders raised over the window", len([c for c in ecos if c not in prev.get("change_orders", {})]), "ECOs", 2, 5, ids=[c for c in ecos if c not in prev.get("change_orders", {})])
    # --- quality loop
    capa = m.get("capa", {}); aged = [c for c, v in capa.items() if v.get("status") != "closed" and v.get("due") and (_days(v["due"]) or 0) < 0]
    add("capa_overdue", "CAPAs past due", len(aged), "CAPAs", 1, 3, ids=aged)
    try:
        from . import business as B
        ppm = B.supplier_ppm(m)["suppliers"]; target = (m.get("meta") or {}).get("business", {}).get("ppm_target", 500)
        over = [s for s, v in ppm.items() if v["ppm"] is not None and v["ppm"] > target]
        add("supplier_ppm", "Suppliers over PPM target", len(over), "suppliers", 1, 2, ids=over)
        pr = B.procurement(m); late = [r["part"] for r in pr if r["late"]]; noq = [r["part"] for r in pr if r["quote_status"] == "none"]
        add("parts_late_to_order", "Buy parts past their order-by date", len(late), "parts", 1, 3, ids=late)
        add("parts_unquoted", "Buy parts without a quote", round(100 * len(noq) / max(1, len(pr)), 1), "%", 30, 60, ids=noq)
        tr = B.tooling_rows(m); t1late = [t["id"] for t in tr if t["t1_late"]]; ko = [t["id"] for t in tr if t["late"]]
        add("tooling_risk", "Tools late to kick-off or T1 after the build", len(t1late) + len(ko), "tools", 1, 2, ids=t1late + ko)
        k = B.cost(m)
        if k["total_usd"] is not None and k["target_usd"]:
            add("bom_vs_target", "BOM cost over target", round(100 * (float(k["total_usd"]) / float(k["target_usd"]) - 1), 1), "%", 0, 10, note=f"BOM {k['total_usd']} vs target {k['target_usd']}")
        st = B.staffing(m); nolead = [r["team"] for r in st if not r["lead"]]
        add("teams_without_lead", "Teams without a lead", round(100 * len(nolead) / max(1, len(st)), 1), "%", 20, 50, ids=nolead)
    except Exception as e:
        ind.append({"key": "business", "name": "business indicators", "level": "unknown", "note": str(e)})
    # --- flow
    pend = rep.get("pending_handoffs", []); add("handoffs_waiting", "Handoffs waiting", len(pend), "handoffs", 3, 8, ids=[(h.get("id") or h.get("handoff") or str(h)) if isinstance(h, dict) else h for h in pend])
    overdue_wi = [w for w, v in m.get("work_items", {}).items() if v.get("status") != "done" and v.get("due") and (_days(v["due"]) or 0) < 0]
    add("work_overdue", "Work items overdue", len(overdue_wi), "items", 3, 10, ids=overdue_wi)
    # --- deliverable burn toward the next gate
    gate_risk = []
    try:
        from . import pdp
        mx = pdp.matrix(m)
        for g, v in gates:
            d = _days(v["date"])
            if d is None or d < -1: continue
            cells = [x for team in mx["cells"].get(g, {}).values() for x in team]
            openc = [x for x in cells if x.get("status") not in ("done", "n/a", "waived")]
            share = round(100 * len(openc) / len(cells), 1) if cells else None
            # burn needed: open deliverables per remaining week
            per_week = round(len(openc) / max(1, d / 7), 1) if d is not None and d > 0 else (len(openc) if openc else 0)
            bearing = [i for i in ind if i["level"] in ("red", "amber")]
            score = (len(openc) * 2 + sum(3 if i["level"] == "red" else 1 for i in bearing)) / max(1, (d or 0) / 7 + 1)
            level = "red" if (share or 0) >= 60 and (d or 0) < 42 or score >= 6 else ("amber" if (share or 0) >= 30 or score >= 2.5 else "green")
            gate_risk.append({"gate": g, "name": v.get("name", g), "date": v["date"], "days": d, "open_deliverables": len(openc), "deliverables": len(cells), "open_share": share, "burn_per_week": per_week, "level": level, "drivers": [i["key"] for i in bearing][:8]})
    except Exception as e:
        gate_risk.append({"gate": "?", "note": str(e)})
    summary = {"red": sum(1 for i in ind if i.get("level") == "red"), "amber": sum(1 for i in ind if i.get("level") == "amber"), "green": sum(1 for i in ind if i.get("level") == "green"), "unknown": sum(1 for i in ind if i.get("level") == "unknown")}
    themes = {k: {"name": v, "red": sum(1 for i in ind if i.get("theme") == k and i.get("level") == "red"), "amber": sum(1 for i in ind if i.get("theme") == k and i.get("level") == "amber"), "n": sum(1 for i in ind if i.get("theme") == k)} for k, v in THEMES.items()}
    return {"indicators": ind, "gates": gate_risk, "themes": themes, "next_gate": nxt[0], "days_to_next": days_to_next, "summary": summary, "window_revs": window_revs if prev is not None else 0}


def interventions(res: dict) -> list[dict]:
    """What to do about each red/amber indicator — the agent role or team that acts, and the prompt to send."""
    ACT = {
        "req_churn": ("requirements", "Freeze the requirement set for the next gate: list the changed/added requirements, their downstream tests and parts, and raise a change order for each change still worth making"),
        "req_unverified": ("verification", "Write the missing tests for every requirement without one, with method and gate"),
        "fm_unassessed": ("risk", "Assess every unassessed failure-mode candidate from the architecture"),
        "high_ap_untested": ("verification", "Add a test for every High-AP failure mode and link it"),
        "test_fail_rate": ("verification", "Analyse the failed runs of the last 30 days, link each to a failure mode or finding, and propose corrective work items"),
        "test_stale": ("verification", "Plan re-runs for the passed tests older than 60 days before the next gate"),
        "eco_open": ("design_quality", "Drive the open change orders to decision: who is missing, what is the impact, which can be deferred past the gate"),
        "eco_rate": ("program", "Review the change-order rate: which subsystem is unstable and why; propose a design freeze date"),
        "capa_overdue": ("launch_quality", "Close or re-plan every overdue CAPA with a verification test"),
        "supplier_ppm": ("supplier_quality", "Open a CAPA for every supplier over the PPM target and plan containment for the next build"),
        "parts_late_to_order": ("procurement", "Place or expedite orders for every part past its order-by date; raise a program risk per part"),
        "parts_unquoted": ("procurement", "Build RFQ packages and request quotes for every unquoted buy part"),
        "tooling_risk": ("industrialization", "Kick off late tools and re-plan T1 against the build; raise risks"),
        "bom_vs_target": ("finance", "Propose should-cost actions for the largest cost items to bring BOM under target"),
        "teams_without_lead": ("people", "Propose leads for every team without one and the hiring/reassignment work items"),
        "handoffs_waiting": ("program", "Chase every waiting handoff: owner, due, blocker"),
        "work_overdue": ("program", "Re-plan or close every overdue work item with the owning team"),
        "trl_below_gate": ("analysis", "For every new technology below the gate's TRL: name the test, build or qualification that raises it, plan it before the gate, or raise a program risk"),
        "trl_overstated": ("reviewer", "Challenge the declared TRL of these parts: list the evidence the model holds, and lower the declared level or add the missing evidence"),
        "cda_violating": ("analysis", "For every critical design attribute over its limit: root cause from the architecture, the design change or trade study that recovers it, and the test that proves it"),
        "cda_tight": ("analysis", "For every critical design attribute below target or inside 10 % of its limit: margin recovery options with evidence"),
        "cda_worsening": ("verification", "Explain the worsening trend from the runs (scale, drift, fixture) and plan the next measurement"),
        "cda_unmeasured": ("verification", "Plan the test run or station that measures every unmeasured critical design attribute before the next gate"),
    }
    out = []
    for i in res["indicators"]:
        if i.get("level") in ("red", "amber") and i["key"] in ACT:
            role, prompt = ACT[i["key"]]; out.append({"key": i["key"], "level": i["level"], "role": role, "prompt": prompt, "ids": i.get("ids", [])})
    return sorted(out, key=lambda x: 0 if x["level"] == "red" else 1)
