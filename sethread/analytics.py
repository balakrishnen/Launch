"""Project analytics — one aggregate for the Analytics tab: status rollups and series derived from the graph and its history.

Lifecycle intelligence rather than reporting: every number here links back to the elements behind it and most carry a trend
from the patch history. Sections: headline · burndown (trend over revisions) · gates (readiness and slip risk) · departments
(open deliverables) · teams (load) · verification (test status, runs, fail rate by week) · risk (AP distribution, unassessed) ·
quality (findings, CAPA, PPM, yield) · supply (quotes, lead time, tooling) · cost (BOM vs target, top items) · maturity (TRL,
CDA margins) · change (ECO) · activity (patches by author kind and by week).
"""
from __future__ import annotations
import datetime as _dt
from collections import Counter
from . import derive as D, lifecycle as LC, pdp, indicators as IND, business as B, maturity as MAT, ops as OPS, policy


def _week(d):
    try: y, w, _ = _dt.date.fromisoformat(str(d)[:10]).isocalendar(); return f"{y}-W{w:02d}"
    except Exception: return None


def compute(m, store=None, threads=None) -> dict:
    rep = D.coverage_report(m); fm = D.fmea(m); sc = None
    try:
        from . import quality as Q
        sc = Q.scorecard(m, store)
    except Exception: sc = None
    ind = IND.compute(m, store); mx = pdp.matrix(m); stage, phase = LC.convergence(m, True) if hasattr(LC, "convergence") else (m.get("meta", {}).get("stage"), None)
    # --- gates
    gates = []
    for g, v in sorted(m["gates"].items(), key=lambda kv: kv[1].get("date", "")):
        cells = [x for team in mx["cells"].get(g, {}).values() for x in team]
        st = Counter(x.get("status") for x in cells)
        risk = next((r for r in ind["gates"] if r.get("gate") == g), {})
        gates.append({"id": g, "name": v.get("name", g), "date": v.get("date", ""), "status": v.get("status", ""), "done": st.get("done", 0), "partial": st.get("partial", 0), "missing": st.get("missing", 0), "waived": st.get("waived", 0) + st.get("n/a", 0), "total": len(cells), "risk": risk.get("level"), "days": risk.get("days")})
    # --- departments
    from . import schema
    depts = []
    for dname in schema.DEPARTMENTS:
        teams = [t for t, tv in m.get("teams", {}).items() if (tv.get("unit_path") or [None])[0] == dname or (not tv.get("unit_path") and schema.DEPARTMENT_OF.get(tv.get("focus") or tv.get("discipline") or "") == dname)]
        cells = [x for g in mx["cells"].values() for t in teams for x in g.get(t, [])]
        st = Counter(x.get("status") for x in cells)
        wi = [w for w, v in m.get("work_items", {}).items() if v.get("team") in teams and v.get("status") != "done"]
        depts.append({"name": dname, "teams": len(teams), "done": st.get("done", 0), "partial": st.get("partial", 0), "missing": st.get("missing", 0), "open_work": len(wi)})
    # --- teams
    teams = []
    for t, tv in m.get("teams", {}).items():
        wi = [w for w, v in m.get("work_items", {}).items() if v.get("team") == t and v.get("status") != "done"]
        od = [w for w in wi if m["work_items"][w].get("due") and str(m["work_items"][w]["due"]) < _dt.date.today().isoformat()]
        cells = [x for g in mx["cells"].values() for x in g.get(t, [])]
        teams.append({"id": t, "name": tv["name"], "kind": tv.get("kind", ""), "open_work": len(wi), "overdue": len(od), "deliverables_open": sum(1 for x in cells if x.get("status") not in ("done", "n/a", "waived")), "deliverables": len(cells), "members": len(set(tv.get("members", [])) | ({tv["lead"]} if tv.get("lead") else set()))})
    # --- verification
    tests = m["tests"]; tst = Counter(v.get("status", "planned") for v in tests.values())
    runs = m.get("test_runs", {}); by_week = {}
    for r in runs.values():
        w = _week(r.get("date"))
        if not w: continue
        x = by_week.setdefault(w, {"week": w, "pass": 0, "fail": 0}); x["pass" if r.get("result") == "pass" else "fail"] += 1
    by_method = Counter((v.get("method") or "test").split(",")[0].strip()[:18] for v in tests.values())
    # --- risk
    ap = Counter(x.get("AP") or "—" for x in fm)
    by_elem = Counter(x.get("element") for x in fm if x.get("AP") == "H")
    # --- quality
    findings = m.get("findings", {}); fst = Counter(v.get("status", "open") for v in findings.values()); fsev = Counter(v.get("severity", "") for v in findings.values() if v.get("status") != "closed")
    capa = B.capa_rows(m); ppm = B.supplier_ppm(m)["suppliers"]
    wo = OPS.work_orders(m)
    # --- supply & cost
    pr = B.procurement(m); cost = B.cost(m); tl = B.tooling_rows(m)
    top_cost = sorted([r for r in cost["rows"] if r["cost_usd"] not in (None, "")], key=lambda r: -float(r["cost_usd"]))[:10]
    # --- maturity
    trl = MAT.trl_rows(m); cda = MAT.cda_rows(m)
    # --- change
    eco = OPS.change_orders(m)
    # --- activity from patch history
    activity = {"by_week": [], "by_author": [], "agent_share": None}
    try:
        ps = store.list_patches("applied") if store is not None else []
        wk = Counter(); au = Counter(); agent = 0
        for p in ps:
            w = _week(getattr(p, "created", None) or getattr(p, "ts", None)); wk[w or "?"] += 1
            a = str(getattr(p, "author", "") or ""); au["agent" if a.startswith("agent") else "people"] += 1; agent += a.startswith("agent")
        activity = {"by_week": [{"week": w, "patches": n} for w, n in sorted(wk.items()) if w != "?"][-16:], "by_author": [{"who": k, "patches": n} for k, n in au.most_common()], "agent_share": round(100 * agent / len(ps), 1) if ps else None, "total": len(ps)}
    except Exception as e: activity["note"] = str(e)
    tr = policy.trend(store, 16) if store is not None else {"supported": False, "points": []}
    conv = m.get("meta", {}).get("stage")
    return {
        "headline": {"stage": conv, "elements": sum(len(m.get(k, {})) for k in schema.KINDS), "open_gaps": sum(len(v) for k, v in rep.items() if isinstance(v, list) and k != "counts"), "indicators": ind["summary"], "next_gate": ind["next_gate"], "days_to_next": ind["days_to_next"],
                     "scorecard": (sc or {}).get("score") if isinstance(sc, dict) else None, "tests_passed": tst.get("passed", 0), "tests": len(tests), "high_ap": ap.get("H", 0), "open_findings": fst.get("open", 0) + fst.get("in progress", 0), "open_work": sum(t["open_work"] for t in teams)},
        "trend": tr, "gates": gates, "departments": depts, "teams": sorted(teams, key=lambda t: -t["open_work"]),
        "verification": {"status": dict(tst), "runs_by_week": sorted(by_week.values(), key=lambda x: x["week"])[-12:], "by_method": by_method.most_common(8), "runs": len(runs)},
        "risk": {"ap": dict(ap), "assessed": len(fm), "unassessed": len(rep.get("unassessed_candidates", [])), "high_by_element": by_elem.most_common(8)},
        "quality": {"findings_status": dict(fst), "findings_severity": dict(fsev), "capa_open": sum(1 for c in capa if c["status"] != "closed"), "capa_overdue": sum(1 for c in capa if c["overdue"]), "ppm": sorted([{"supplier": k, **v} for k, v in ppm.items()], key=lambda x: -(x["ppm"] or 0)), "work_orders": [{"id": w["id"], "build": w.get("build"), "built": w["built"], "complete": w["complete"], "failed": w["failed"], "fpy": w["first_pass_yield"]} for w in wo]},
        "supply": {"quote_status": dict(Counter(r["quote_status"] for r in pr)), "late": sum(1 for r in pr if r["late"]), "lead_times": sorted([{"part": r["part"], "lead": int(r["lead_time_d"]), "order_by": r["order_by"], "late": r["late"]} for r in pr if r["lead_time_d"] not in (None, "")], key=lambda x: -x["lead"])[:10], "tooling": [{"id": t["id"], "part": t["part"], "status": t.get("status"), "ppap": t.get("ppap"), "t1": t.get("t1", ""), "late": t["late"] or t["t1_late"]} for t in tl]},
        "cost": {"bom": cost["total_usd"], "target": cost["target_usd"], "price": cost["price"], "margin": cost["gross_margin"], "capex": cost["capex_total_usd"], "top": [{"part": r["part"], "name": r["name"], "cost": float(r["cost_usd"]), "actual": (m["parts"][r["part"]].get("attrs") or {}).get("cost_actual_usd")} for r in top_cost], "missing": len(cost["parts_without_cost"])},
        "maturity": {"trl": [{"part": r["part"], "declared": r["declared"], "demonstrated": r["demonstrated"], "new": r["new_technology"]} for r in trl if r["new_technology"] or r["declared"] is not None], "cda": [{"id": r["id"], "name": r["name"], "unit": r.get("unit", ""), "current": r["current"], "target": r.get("target"), "limit": r.get("limit"), "margin_limit": r["margin_to_limit_pct"], "margin_target": r["margin_to_target_pct"], "status": r["status"], "trend": r["trend"], "series": r["series"]} for r in cda]},
        "change": {"eco_status": dict(Counter(c["status"] for c in eco)), "open": [c["id"] for c in eco if c["status"] not in ("released", "rejected")]},
        "activity": activity, "indicators": ind["themes"], "gate_risk": ind["gates"],
        "maturity_score": maturity(m, ind, mx), "maturity_history": maturity_history(m, store) if store is not None else [],
    }


# ---------------- project maturity ----------------
# A composite 0–100 with eight sub-scores, each derived from the graph, and the profile a project at each gate is expected to
# show (appliance NPI defaults; an organization can tune the profile in its policy). The gap between actual and expected at the
# next gate is the maturity shortfall — the number a program manager owes the steering committee.
EXPECTED = {"G0": 20, "G1": 35, "EVT": 50, "DVT": 65, "PVT": 85, "MP": 95, "PDR": 40, "CDR": 65, "G2": 50, "G3": 65, "G4": 85}
WEIGHTS = {"requirements": 1.0, "architecture": 1.0, "risk": 1.0, "verification": 1.5, "technology": 1.0, "industrialization": 1.0, "process": 1.0, "quality_loop": 0.5}


def _pct(a, b): return round(100 * a / b, 1) if b else None


def maturity(m, ind=None, mx=None):
    rep = D.coverage_report(m); fm = D.fmea(m); mx = mx or pdp.matrix(m)
    n_req = len(m["requirements"]); n_fun = len(m["functions"]); n_parts = len([p for p, v in m["parts"].items() if not v.get("context")])
    sub = {}
    # requirements: with a test, with a need, no dangling gaps
    with_test = sum(1 for v in m["requirements"].values() if v.get("tests")); with_need = sum(1 for v in m["requirements"].values() if v.get("from_"))
    sub["requirements"] = {"score": _pct(with_test + with_need, 2 * n_req), "detail": f"{with_test}/{n_req} verified by a test · {with_need}/{n_req} traced to a need", "link": "/form/vcrm"}
    # architecture: functions allocated, interfaces with items, parts with discipline, CAD/EDA present
    alloc = sum(1 for v in m["functions"].values() if v.get("alloc")); ifc = sum(1 for v in m["interfaces"].values() if v.get("items")); disc = sum(1 for p, v in m["parts"].items() if v.get("discipline") and not v.get("context"))
    cad = len({c.get("part") for c in m.get("cad_models", {}).values()})
    sub["architecture"] = {"score": _pct(alloc / max(1, n_fun) + ifc / max(1, len(m["interfaces"])) + disc / max(1, n_parts) + min(1, cad / max(1, n_parts * 0.3)), 4), "detail": f"{alloc}/{n_fun} functions allocated · {ifc}/{len(m['interfaces'])} interfaces with items · {cad} parts modelled natively", "link": "/collection/parts"}
    # risk: assessed share, High-AP with tests
    cands = len(rep.get("unassessed_candidates", [])); hi = [x for x in fm if x.get("AP") == "H"]; hi_t = sum(1 for x in hi if x.get("tests"))
    sub["risk"] = {"score": _pct(len(fm) / max(1, len(fm) + cands) + (hi_t / len(hi) if hi else 1), 2), "detail": f"{len(fm)} assessed · {cands} candidates open · {hi_t}/{len(hi)} High-AP with a test", "link": "/form/dfmea"}
    # verification: tests passed, CDAs measured within target
    tests = m["tests"]; passed = sum(1 for v in tests.values() if v.get("status") == "passed"); cda = MAT.cda_rows(m); cda_ok = sum(1 for r in cda if r["status"] in ("ok", "tight"))
    sub["verification"] = {"score": _pct(passed / max(1, len(tests)) + (cda_ok / len(cda) if cda else 0.5), 2), "detail": f"{passed}/{len(tests)} tests passed · {cda_ok}/{len(cda)} critical design attributes within target", "link": "/form/dvpr"}
    # technology: demonstrated TRL of new technologies vs 9
    trl = [r for r in MAT.trl_rows(m) if r["new_technology"]]
    sub["technology"] = {"score": round(100 * sum(min(r["declared"] or 0, r["demonstrated"] + 1) for r in trl) / (9 * len(trl)), 1) if trl else None, "detail": f"{len(trl)} new technologies · demonstrated TRL " + (", ".join(f"{r['part']} {r['demonstrated']}" for r in trl) if trl else "none flagged"), "link": "/form/trl"}
    # industrialization: quotes, tooling kicked off, PPAP, suppliers with agreements
    pr = B.procurement(m); q = sum(1 for r in pr if r["quote_status"] in ("received", "awarded")); tl = B.tooling_rows(m); ko = sum(1 for t in tl if t.get("kickoff")); pp = sum(1 for t in tl if t.get("ppap") == "approved")
    sub["industrialization"] = {"score": _pct(q / max(1, len(pr)) + (ko / len(tl) if tl else 0) + (pp / len(tl) if tl else 0), 3), "detail": f"{q}/{len(pr)} buy parts quoted · {ko}/{len(tl)} tools kicked off · {pp}/{len(tl)} PPAP approved", "link": "/form/tooling"}
    # process: deliverables done across all gates up to the next one
    gates = sorted(((g, v) for g, v in m["gates"].items() if v.get("date")), key=lambda kv: kv[1]["date"]); today = _dt.date.today().isoformat()
    upto = [g for g, v in gates if v["date"] <= today] + [next((g for g, v in gates if v["date"] > today), None)]; upto = [g for g in upto if g]
    cells = [x for g in upto for team in mx["cells"].get(g, {}).values() for x in team]; done = sum(1 for x in cells if x.get("status") in ("done", "waived", "n/a"))
    sub["process"] = {"score": _pct(done, len(cells)), "detail": f"{done}/{len(cells)} deliverables done through {upto[-1] if upto else '—'}", "link": "/pdp"}
    # quality loop: CAPAs closed and verified, findings closed
    capa = B.capa_rows(m); cc = sum(1 for c in capa if c["status"] == "closed" and c["steps"]["verified"]); f_ = m.get("findings", {}); fc = sum(1 for v in f_.values() if v.get("status") == "closed")
    sub["quality_loop"] = {"score": _pct((cc / len(capa) if capa else 1) + (fc / len(f_) if f_ else 1), 2), "detail": f"{cc}/{len(capa)} CAPAs closed & verified · {fc}/{len(f_)} findings closed", "link": "/form/capa"}
    # composite
    num = sum(WEIGHTS[k] * v["score"] for k, v in sub.items() if v["score"] is not None); den = sum(WEIGHTS[k] for k, v in sub.items() if v["score"] is not None)
    score = round(num / den, 1) if den else None
    nxt = next(((g, v) for g, v in gates if v["date"] > today), (None, None)); expected = EXPECTED.get(nxt[0], None) if nxt[0] else None
    prev = [(g, v) for g, v in gates if v["date"] <= today]; expected_now = EXPECTED.get(prev[-1][0]) if prev else 10
    return {"score": score, "expected_now": expected_now, "expected_next": expected, "next_gate": nxt[0], "next_date": nxt[1]["date"] if nxt[1] else None, "shortfall_next": round(expected - score, 1) if expected is not None and score is not None else None,
            "level": "mass-production ready" if score and score >= 90 else "validated" if score and score >= 70 else "integrated" if score and score >= 50 else "defined" if score and score >= 30 else "conceptual",
            "sub": sub, "weights": WEIGHTS, "profile": EXPECTED}


def maturity_history(m, store, points=10):
    """The composite over revisions — is the project maturing fast enough to meet the expected profile at the next gate?"""
    out = []
    try:
        rev = store.rev(); step = max(1, rev // points)
        for r in list(range(1, rev + 1, step))[-points:] + ([rev] if rev % step else []):
            mm = store.load(r); mt = maturity(mm); out.append({"rev": r, "score": mt["score"], **{k: v["score"] for k, v in mt["sub"].items()}})
    except Exception: pass
    return out
