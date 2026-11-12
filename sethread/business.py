"""Business functions on the MBSE graph — marketing, sales, finance, people (HR), facilities, legal, service.

Launch is the whole company's work OS: every function's view is derived from the same graph the engineers build, so a
marketing claim is substantiated by a requirement and its test, a sales market is open only when its regulations are
certified, the finance cost roll-up comes from the part tree, staffing comes from the teams, facilities from the process
steps and test methods, legal from regulations, claims and supplier terms, service from field events and field-replaceable
parts. Nothing here is typed twice.

Kinds added: `claims` (marketing claims with substantiation), `cost_targets` is a meta.business field, `markets` derive from
regulations. Each function has a focus view (team workspace), a derived form, agent role (roles.py) and gate checks (pdp.py).
"""
from __future__ import annotations
from . import derive as D

CERT_KINDS = ("certification", "cert")


def _business(m): return (m.get("meta") or {}).get("business") or {}


# ---------- marketing: claims substantiation ----------
def claims(m):
    """Every claim with the requirements that make it, the tests that prove it and the regulations that constrain it."""
    out = []
    for cid, c in (m.get("claims") or {}).items():
        reqs = [r for r in c.get("reqs", []) if r in m["requirements"]]
        tests = sorted({t for r in reqs for t in m["requirements"][r].get("tests", [])} | set(c.get("tests", [])))
        passed = [t for t in tests if m["tests"].get(t, {}).get("status") == "passed"]
        regs = sorted({g for r in reqs for g in m["requirements"][r].get("regs", [])} | set(c.get("regs", [])))
        if not reqs: status = "unsupported"
        elif not tests: status = "untested"
        elif len(passed) == len(tests): status = "substantiated"
        else: status = "pending"
        out.append({"id": cid, "text": c["text"], "type": c.get("type", "performance"), "markets": c.get("markets", []), "reqs": reqs, "tests": tests, "passed": passed, "regs": regs, "status": status, "owner": c.get("owner", ""), "approved": c.get("approved", "")})
    return out


def marketing_view(m, rep):
    cl = claims(m)
    return {"claims": [c["id"] for c in cl], "claims_unsubstantiated": [c["id"] for c in cl if c["status"] != "substantiated"],
            "moes": list(m.get("moes", {}).keys()), "labelling_regulations": [r for r, v in m["regulations"].items() if any(k in (v.get("name", "") + v.get("standard", "")).lower() for k in ("label", "prop 65", "energy", "ecodesign", "weee", "marking"))],
            "consumer_needs": [n for n, v in m.get("needs", {}).items() if "consumer" in (v.get("stk") or "").lower() or "customer" in (v.get("stk") or "").lower()],
            "positioning_notes": [n for n, v in m.get("notes", {}).items() if v.get("kind") in ("positioning", "messaging", "launch")]}


# ---------- sales: markets open by certification ----------
def markets(m):
    """Per market: the regulations that gate selling there, their requirement coverage and certification tests, and whether the market is open."""
    by = {}
    for rid, r in m["regulations"].items():
        for mk in [x.strip() for x in str(r.get("market", "")).replace("/", ",").split(",") if x.strip()]: by.setdefault(mk, []).append(rid)
    out = []
    for mk, regs in sorted(by.items()):
        reqs = [q for q, v in m["requirements"].items() if set(v.get("regs", [])) & set(regs)]
        tests = sorted({t for q in reqs for t in m["requirements"][q].get("tests", [])})
        cert = [t for t in tests if m["tests"][t].get("kind") in CERT_KINDS or m["tests"][t].get("gate") == "PVT"]
        passed = [t for t in tests if m["tests"][t].get("status") == "passed"]
        uncovered = [g for g in regs if not any(g in v.get("regs", []) for v in m["requirements"].values())]
        status = "open" if tests and len(passed) == len(tests) and not uncovered else ("blocked" if uncovered else "pending")
        out.append({"market": mk, "regulations": regs, "uncovered": uncovered, "requirements": len(reqs), "tests": len(tests), "passed": len(passed), "certification_tests": cert, "status": status})
    return out


def sales_view(m, rep):
    mk = markets(m); b = _business(m)
    return {"markets_open": [x["market"] for x in mk if x["status"] == "open"], "markets_blocked": [x["market"] for x in mk if x["status"] != "open"],
            "price_and_launch": [f"price {b.get('price', '—')} · target cost {b.get('target_cost', '—')} · launch {b.get('launch_date', '—')}"],
            "claims_substantiated": [c["id"] for c in claims(m) if c["status"] == "substantiated"], "gates": list(m["gates"].keys()),
            "variants": sorted({str(v.get("attrs", {}).get("variant")) for v in m["parts"].values() if v.get("attrs", {}).get("variant")})}


# ---------- finance: cost roll-up vs target, capex ----------
def cost(m):
    b = _business(m); bud = D.budgets(m); rows_ = bud.get("cost") or []   # one row per root of the part tree
    total = round(sum(r["total"] for r in rows_), 2) if rows_ else None; target = b.get("target_cost"); missing = [p for r in rows_ for p in r.get("parts_without_value", [])]
    rows = [{"part": p, "name": v["name"], "cost_usd": v.get("attrs", {}).get("cost_usd"), "make_buy": v.get("make_buy", ""), "supplier": v.get("supplier"), "owner_team": v.get("owner_team")} for p, v in m["parts"].items() if not v.get("context")]
    capex = [{"step": s, "name": v["name"], "station": v.get("station", ""), "tooling_usd": v.get("tooling_usd"), "capex_usd": v.get("capex_usd")} for s, v in m.get("process_steps", {}).items()]
    cap_total = sum(float(x["tooling_usd"] or 0) + float(x["capex_usd"] or 0) for x in capex if (x["tooling_usd"] or x["capex_usd"]))
    return {"total_usd": total, "target_usd": target, "within_target": (total is not None and target is not None and float(total) <= float(target)), "parts_without_cost": missing, "rows": rows, "capex": capex, "capex_total_usd": cap_total,
            "price": b.get("price"), "gross_margin": (round(1 - float(total) / float(b["price"]), 3) if total is not None and b.get("price") else None)}


def finance_view(m, rep):
    c = cost(m)
    return {"cost_roll_up": [f"BOM {c['total_usd'] if c['total_usd'] is not None else '—'} USD vs target {c['target_usd'] or '—'} · price {c['price'] or '—'} · margin {c['gross_margin'] if c['gross_margin'] is not None else '—'}"],
            "parts_without_cost": c["parts_without_cost"], "buy_parts_without_supplier": rep.get("buy_parts_without_supplier", []), "capex_items": [x["step"] for x in c["capex"] if x["tooling_usd"] or x["capex_usd"]],
            "suppliers": list(m.get("suppliers", {}).keys()), "open_risks": [r for r, v in m.get("risks", {}).items() if v.get("status") == "open"]}


# ---------- people (HR): staffing from teams ----------
def staffing(m):
    rows = []
    for t, v in m.get("teams", {}).items():
        members = set(v.get("members", [])) | ({v["lead"]} if v.get("lead") else set())
        open_wi = [w for w, x in m.get("work_items", {}).items() if x.get("team") == t and x.get("status") != "done"]
        rows.append({"team": t, "name": v["name"], "kind": v.get("kind", "functional"), "focus": v.get("focus") or v.get("discipline", ""), "lead": v.get("lead", ""), "headcount": len(members), "open_work_items": len(open_wi), "parts": len(v.get("parts", [])), "per_head": round(len(open_wi) / len(members), 1) if members else None})
    return rows


def people_view(m, rep):
    st = staffing(m)
    return {"teams": [r["team"] for r in st], "teams_without_lead": [r["team"] for r in st if not r["lead"]], "teams_without_members": [r["team"] for r in st if r["headcount"] == 0],
            "overloaded_teams": [r["team"] for r in st if r["per_head"] is not None and r["per_head"] > 8], "roles_needed": [f"{r['name']}: {r['focus'] or r['kind']}" for r in st if r["headcount"] == 0]}


# ---------- facilities: lab and line from tests and process steps ----------
def facilities_view(m, rep):
    stations = sorted({v.get("station") for v in m.get("process_steps", {}).values() if v.get("station")})
    lab = [t for t, v in m["tests"].items() if any(k in (v.get("method", "") + v.get("name", "")).lower() for k in ("chamber", "hipot", "hi-pot", "emc", "thermal", "drop", "vibration", "salt", "humidity", "acoustic", "anechoic", "fixture"))]
    mains = [t for t, v in m["tests"].items() if any(k in (v.get("method", "") + v.get("name", "")).lower() for k in ("230 v", "120 v", "mains", "hipot", "ground bond"))]
    return {"stations": stations, "process_steps_without_station": [s for s, v in m.get("process_steps", {}).items() if not v.get("station")], "lab_tests_needing_equipment": lab, "mains_safety_tests": mains,
            "facility_notes": [n for n, v in m.get("notes", {}).items() if v.get("kind") in ("facility", "layout", "lab")]}


# ---------- legal: regulations, claims, supplier terms, IP ----------
def legal_view(m, rep):
    cl = claims(m)
    return {"regulations": list(m["regulations"].keys()), "regulations_without_requirements": rep.get("regulations_without_requirements", []), "claims_unsubstantiated": [c["id"] for c in cl if c["status"] != "substantiated"],
            "claims_unapproved": [c["id"] for c in cl if not c["approved"]], "suppliers_without_agreement": [s for s, v in m.get("suppliers", {}).items() if not v.get("agreement")],
            "ip_notes": [n for n, v in m.get("notes", {}).items() if v.get("kind") in ("ip", "patent", "trademark", "contract")]}


# ---------- service: field loop, FRUs, spares ----------
def service_view(m, rep):
    fru = [p for p, v in m["parts"].items() if str(v.get("attrs", {}).get("field_replaceable", "")).lower() in ("yes", "true", "1")]
    user_rep = [p for p, v in m["parts"].items() if str(v.get("attrs", {}).get("user_replaceable", "")).lower() in ("yes", "true", "1")]
    return {"field_events": list(m.get("field_events", {}).keys()), "field_events_open": [f for f, v in m.get("field_events", {}).items() if v.get("status", "open") != "closed"],
            "field_replaceable_parts": fru, "user_replaceable_parts": user_rep, "high_ap_without_diagnostic": [x["id"] for x in D.fmea(m) if x.get("AP") == "H" and not x.get("controls")],
            "service_notes": [n for n, v in m.get("notes", {}).items() if v.get("kind") in ("service", "repair", "spares", "warranty")]}


FOCUS_VIEWS = {"marketing": marketing_view, "sales": sales_view, "finance": finance_view, "hr": people_view, "people": people_view, "facilities": facilities_view, "legal": legal_view, "service": service_view}


# ---------- derived forms ----------
def claims_form(m):
    rows = []
    for c in claims(m):
        rows.append([c["id"], c["text"], c["type"], ", ".join(c["markets"]), ", ".join(c["reqs"]), ", ".join(c["tests"]), f"{len(c['passed'])}/{len(c['tests'])}", ", ".join(c["regs"]), c["status"], c["owner"], c["approved"]])
    headers = ["Claim", "Claim text (as it will appear)", "Type", "Markets", "Substantiating requirements", "Tests", "Passed", "Regulations constraining the claim", "Status", "Owner", "Legal approval"]
    return [("CLAIMS SUBSTANTIATION MATRIX (FTC 16 CFR 260 / EU 2005/29/EC — every claim traces to a requirement and a passed test)", len(headers))], headers, [8, 36, 10, 10, 18, 18, 7, 20, 11, 10, 10], rows


def cost_form(m):
    c = cost(m); rows = []
    for r in sorted(c["rows"], key=lambda r: -(float(r["cost_usd"]) if r["cost_usd"] not in (None, "") else 0)):
        rows.append([r["part"], r["name"], r["make_buy"], r["supplier"] or "", r["owner_team"] or "", r["cost_usd"] if r["cost_usd"] not in (None, "") else "— missing"])
    rows.append(["Σ", "BOM cost roll-up", "", "", "", c["total_usd"] if c["total_usd"] is not None else ""]); rows.append(["", "Target cost", "", "", "", c["target_usd"] or ""]); rows.append(["", "Price", "", "", "", c["price"] or ""]); rows.append(["", "Gross margin", "", "", "", c["gross_margin"] if c["gross_margin"] is not None else ""])
    for x in c["capex"]:
        if x["tooling_usd"] or x["capex_usd"]: rows.append([x["step"], "capex: " + x["name"], x["station"], "", "", float(x["tooling_usd"] or 0) + float(x["capex_usd"] or 0)])
    rows.append(["Σ", "Tooling + capex", "", "", "", c["capex_total_usd"]])
    headers = ["Part / step", "Name", "Make/buy", "Supplier", "Owner team", "Cost (USD)"]
    return [("PRODUCT COST ROLL-UP (BOM from the part tree; capex from process steps)", len(headers))], headers, [10, 34, 9, 12, 12, 12], rows


def markets_form(m):
    rows = [[x["market"], ", ".join(x["regulations"]), ", ".join(x["uncovered"]), x["requirements"], f"{x['passed']}/{x['tests']}", ", ".join(x["certification_tests"]), x["status"]] for x in markets(m)]
    headers = ["Market", "Regulations gating sale", "Not yet covered by a requirement", "Requirements", "Tests passed", "Certification tests", "Market status"]
    return [("MARKET READINESS (a market is open when every gating regulation is covered and its tests pass)", len(headers))], headers, [8, 30, 24, 10, 10, 22, 10], rows


def staffing_form(m):
    rows = [[r["team"], r["name"], r["kind"], r["focus"], r["lead"] or "— none", r["headcount"], r["open_work_items"], r["per_head"] if r["per_head"] is not None else "", r["parts"]] for r in staffing(m)]
    headers = ["Team", "Name", "Kind", "Focus / discipline", "Lead", "Headcount", "Open work items", "Per head", "Parts owned"]
    return [("STAFFING PLAN (teams, leads, load)", len(headers))], headers, [8, 24, 10, 16, 18, 8, 10, 8, 8], rows


FORMS = {
    "claims": ("Claims substantiation", "Marketing claims traced to requirements, tests and regulations (FTC / UCPD)", claims_form),
    "cost": ("Product cost roll-up", "BOM cost from the part tree vs target and price; tooling and capex from process steps", cost_form),
    "markets": ("Market readiness", "Which markets are open to sell in: regulations covered and certified", markets_form),
    "staffing": ("Staffing plan", "Teams, leads, headcount and load from the model", staffing_form),
}


def checks_for_pdp(m, typ, c):
    """Gate deliverable checks for the business functions (called from pdp.evaluate)."""
    if typ == "claims":
        cl = claims(m); ok = [x for x in cl if x["status"] == "substantiated" and (x["approved"] or not c.get("approved"))]
        if not cl: return {"status": "missing", "measured": "no claims", "link": "/form/claims"}
        return {"status": "done" if len(ok) == len(cl) else ("partial" if ok else "missing"), "measured": f"{len(ok)}/{len(cl)} substantiated" + (" & approved" if c.get("approved") else ""), "link": "/form/claims"}
    if typ == "cost":
        k = cost(m)
        if k["total_usd"] is None: return {"status": "missing", "measured": "no part costs", "link": "/form/cost"}
        if k["target_usd"] is None: return {"status": "partial", "measured": f"BOM {k['total_usd']} — no target cost set (meta.business.target_cost)", "link": "/form/cost"}
        if not c.get("coverage"): return {"status": "done" if k["price"] else "partial", "measured": f"target {k['target_usd']} · price {k['price'] or '— not set'}", "link": "/form/cost"}
        cov = 1 - len(k["parts_without_cost"]) / max(1, len(k["rows"]))
        return {"status": "done" if k["within_target"] and cov >= c.get("coverage", 0.9) else "partial", "measured": f"BOM {k['total_usd']} vs target {k['target_usd']} · {len(k['parts_without_cost'])} parts without cost", "link": "/form/cost"}
    if typ == "markets":
        mk = markets(m); want = c.get("markets") or [x["market"] for x in mk]; got = [x for x in mk if x["market"] in want]
        op = [x for x in got if x["status"] == "open"]
        if not got: return {"status": "missing", "measured": "no regulations by market", "link": "/form/markets"}
        return {"status": "done" if len(op) == len(got) else ("partial" if any(x["status"] != "blocked" for x in got) else "missing"), "measured": f"{len(op)}/{len(got)} markets open", "link": "/form/markets"}
    if typ == "staffing":
        st = staffing(m); bad = [r for r in st if not r["lead"] or r["headcount"] == 0]
        return {"status": "done" if st and not bad else ("partial" if st else "missing"), "measured": f"{len(st) - len(bad)}/{len(st)} teams staffed with a lead", "link": "/form/staffing"}
    if typ == "procurement": return procurement_check(m, c)
    if typ in ("tooling", "capa", "ppm", "field_loop"): return quality_supply_check(m, typ, c)
    if typ == "fru":
        fru = [p for p, v in m["parts"].items() if str(v.get("attrs", {}).get("field_replaceable", "")).lower() in ("yes", "true", "1")]
        return {"status": "done" if len(fru) >= c.get("n", 1) else "missing", "measured": f"{len(fru)} field-replaceable parts", "link": "/collection/parts"}
    return None


# ---------- procurement: quotes, lead times vs gates, MOQ vs builds, single source ----------
import datetime as _dt


def _days_to(date):
    try: return (_dt.date.fromisoformat(str(date)[:10]) - _dt.date.today()).days
    except Exception: return None


def procurement(m):
    """Per buy part: supplier, best quote, lead time, the earliest gate whose build needs it, whether the order date has passed,
    MOQ against the build quantity, second source, and the quote-vs-BOM variance."""
    b = _business(m); builds = b.get("builds") or {}   # {gate_id: units}
    gates = sorted(((g, v.get("date", "")) for g, v in m["gates"].items() if v.get("date")), key=lambda kv: kv[1])
    quotes = m.get("quotes", {})
    rows = []
    for p, v in m["parts"].items():
        if v.get("context") or (v.get("make_buy") or "buy") != "buy": continue
        qs = [(q, x) for q, x in quotes.items() if x.get("part") == p]
        awarded = [x for _, x in qs if x.get("status") == "awarded"]; received = [x for _, x in qs if x.get("status") in ("received", "awarded")]
        best = awarded[0] if awarded else (min(received, key=lambda x: float(x.get("unit_cost_usd") or 1e12)) if received else None)   # the awarded quote is the price; else the cheapest received
        lead = (awarded[0] if awarded else best or {}).get("lead_time_d")
        if lead in (None, ""): lead = (m.get("suppliers", {}).get(v.get("supplier") or "", {}) or {}).get("lead_time_d")
        first_gate = next(((g, d) for g, d in gates if builds.get(g)), gates[0] if gates else (None, None))
        need_by = first_gate[1]; days = _days_to(need_by) if need_by else None
        order_by = None; late = None
        if days is not None and lead not in (None, ""):
            order_by = (_dt.date.fromisoformat(str(need_by)[:10]) - _dt.timedelta(days=int(lead))).isoformat(); late = _days_to(order_by) is not None and _days_to(order_by) < 0 and not awarded
        qty = builds.get(first_gate[0]) if first_gate[0] else None
        moq = (awarded[0] if awarded else best or {}).get("moq")
        sup = v.get("supplier") or (best or {}).get("supplier") or (qs[0][1].get("supplier") if qs else None); second = (m.get("suppliers", {}).get(sup or "", {}) or {}).get("second_source") or any(x.get("supplier") != sup for x in received)
        bom = (v.get("attrs") or {}).get("cost_usd")
        try: var = round(float(best["unit_cost_usd"]) - float(bom), 2) if best and bom not in (None, "") else None
        except (TypeError, ValueError): var = None
        crit = any(x.get("AP") == "H" for x in D.fmea(m) if x.get("element") == p) or (v.get("discipline") in ("electrical",) and (v.get("attrs") or {}).get("lifecycle") in ("nrnd", "eol"))
        rows.append({"part": p, "name": v["name"], "supplier": sup, "quotes": len(qs), "quote_status": "awarded" if awarded else ("received" if received else ("requested" if qs else "none")),
                     "unit_cost_quote": best.get("unit_cost_usd") if best else None, "bom_cost": bom, "variance_usd": var, "lead_time_d": lead, "need_by": need_by, "need_for": first_gate[0], "order_by": order_by, "late": bool(late),
                     "qty_first_build": qty, "moq": moq, "moq_exceeds_build": (moq not in (None, "") and qty is not None and float(moq) > float(qty)), "second_source": bool(second), "critical": crit, "owner_team": v.get("owner_team")})
    return rows


def procurement_view(m, rep):
    pr = procurement(m)
    return {"buy_parts": [r["part"] for r in pr], "buy_parts_without_supplier": [r["part"] for r in pr if not r["supplier"]], "parts_without_quote": [r["part"] for r in pr if r["quote_status"] == "none"],
            "late_to_order": [r["part"] for r in pr if r["late"]], "long_lead_parts": [r["part"] for r in pr if r["lead_time_d"] not in (None, "") and int(r["lead_time_d"]) >= 56],
            "single_source_critical": [r["part"] for r in pr if r["critical"] and not r["second_source"]], "moq_exceeds_first_build": [r["part"] for r in pr if r["moq_exceeds_build"]],
            "quote_over_bom": [r["part"] for r in pr if r["variance_usd"] is not None and r["variance_usd"] > 0], "quotes": list(m.get("quotes", {}).keys())}


FOCUS_VIEWS["procurement"] = procurement_view


def rfq_package(m, part):
    """What a supplier needs to quote, derived from the graph: the part, its attributes and bounds, the interfaces it must mate,
    drawings/CAD attached, requirements and regulations that apply (food contact, RoHS, UL recognition), quantities per build, quality asks."""
    v = m["parts"].get(part)
    if not v: return None
    b = _business(m); builds = b.get("builds") or {}
    ifaces = {i: iv for i, iv in m["interfaces"].items() if iv.get("a") == part or iv.get("b") == part}
    funcs = [f for f, fv in m["functions"].items() if part in fv.get("alloc", [])]
    reqs = sorted({r for f in funcs for r in m["functions"][f].get("reqs", [])})
    regs = sorted({g for r in reqs for g in m["requirements"][r].get("regs", [])})
    att = [a for a in m.get("attachments", {}).values() if a.get("element") == part]
    cad = [c for c in m.get("cad_models", {}).values() if c.get("part") == part]
    fms = [x for x in D.fmea(m) if x.get("element") == part and x.get("AP") == "H"]
    return {"part": part, "name": v["name"], "type": v.get("type", ""), "discipline": v.get("discipline", ""), "attrs": v.get("attrs", {}), "parent": v.get("parent"),
            "interfaces": [{"id": i, "name": iv["name"], "with": iv["b"] if iv["a"] == part else iv["a"], "items": iv.get("items", []), "kind": iv.get("kind", "")} for i, iv in ifaces.items()],
            "requirements": [{"id": r, "text": m["requirements"][r]["text"], "attr": m["requirements"][r].get("attr", "")} for r in reqs],
            "regulations": [{"id": g, "name": m["regulations"][g]["name"], "standard": m["regulations"][g].get("standard", "")} for g in regs if g in m["regulations"]],
            "drawings": [{"file": a["file"], "role": a["role"], "rev": a.get("rev", "")} for a in att] + [{"file": (c.get("files") or {}).get("step", ""), "role": "cad", "rev": c.get("built", "")} for c in cad if (c.get("files") or {}).get("step")],
            "quantities": [{"build": g, "units": n, "date": m["gates"].get(g, {}).get("date", "")} for g, n in builds.items()], "annual_volume": b.get("annual_volume"),
            "quality": {"high_ap_failure_modes": [{"id": x["id"], "mode": x["mode"], "controls": x.get("controls", "")} for x in fms], "asks": ["PPAP level 3 or equivalent FAI", "CoC per lot", "RoHS/REACH declaration" if any("rohs" in (g["name"] + g["standard"]).lower() for g in [{"name": m["regulations"][g]["name"], "standard": m["regulations"][g].get("standard", "")} for g in regs if g in m["regulations"]]) else "", "food-contact DoC" if any("food" in m["regulations"][g]["name"].lower() for g in regs if g in m["regulations"]) else ""]},
            "commercial": {"incoterm": b.get("incoterm", "FCA"), "currency": b.get("currency", "USD"), "ask": ["unit price at each build quantity and annual volume", "MOQ and lead time", "tooling cost and ownership", "second-source availability", "lifecycle status / EOL notice terms"]}}


def procurement_form(m):
    rows = [[r["part"], r["name"], r["supplier"] or "— none", r["quote_status"], r["unit_cost_quote"] if r["unit_cost_quote"] is not None else "", r["bom_cost"] if r["bom_cost"] not in (None, "") else "", r["variance_usd"] if r["variance_usd"] is not None else "", r["lead_time_d"] or "", r["need_for"] or "", r["need_by"] or "", r["order_by"] or "", "LATE" if r["late"] else "", r["qty_first_build"] or "", r["moq"] or "", "yes" if r["second_source"] else "no", "critical" if r["critical"] else ""] for r in procurement(m)]
    rows.sort(key=lambda r: (r[11] != "LATE", r[10] or "9999"))
    headers = ["Part", "Name", "Supplier", "Quote", "Quote unit cost", "BOM cost", "Variance", "Lead time (d)", "First build", "Need by", "Order by", "Status", "Build qty", "MOQ", "2nd source", "Critical"]
    return [("PROCUREMENT PLAN (buy parts: quotes, lead time against the first build that needs them, MOQ, second source)", len(headers))], headers, [8, 24, 12, 9, 9, 8, 8, 8, 8, 10, 10, 6, 8, 7, 8, 8], rows


FORMS["procurement"] = ("Procurement plan", "Quotes, lead times vs gates, MOQ vs build quantities, second sources", procurement_form)


def procurement_check(m, c):
    pr = procurement(m)
    if c.get("key") == "long_lead_ordered":
        ll = [r for r in pr if r["lead_time_d"] not in (None, "") and r["need_for"] == c.get("gate_ref", r["need_for"])]
        ok = [r for r in ll if r["quote_status"] == "awarded"]
        if not ll: return {"status": "partial", "measured": "no lead times known", "link": "/form/procurement"}
        return {"status": "done" if len(ok) == len(ll) else ("partial" if ok else "missing"), "measured": f"{len(ok)}/{len(ll)} ordered · {len([r for r in ll if r['late']])} late", "link": "/form/procurement"}
    if c.get("key") == "quotes":
        q = [r for r in pr if r["quote_status"] in ("received", "awarded")]
        return {"status": "done" if pr and len(q) == len(pr) else ("partial" if q else "missing"), "measured": f"{len(q)}/{len(pr)} buy parts quoted", "link": "/form/procurement"}
    if c.get("key") == "second_source":
        cr = [r for r in pr if r["critical"]]; ok = [r for r in cr if r["second_source"]]
        return {"status": "done" if len(ok) == len(cr) else ("partial" if ok else "missing"), "measured": f"{len(ok)}/{len(cr)} critical parts dual-sourced", "link": "/form/procurement"}
    return {"status": "missing", "measured": "unknown procurement check", "link": "/form/procurement"}


# =====================================================================================================================
# QUALITY department — supplier / launch / field / design quality, each a closed loop on the graph
# =====================================================================================================================
def supplier_ppm(m):
    """Incoming-inspection PPM per supplier and per part from inspections (stage incoming)."""
    by_sup = {}; by_part = {}
    for i, v in m.get("inspections", {}).items():
        if v.get("stage") != "incoming": continue
        sup = v.get("supplier") or m["parts"].get(v["part"], {}).get("supplier")
        q = float(v.get("qty") or 0); d = float(v.get("defects") or 0)
        for key, store in ((sup, by_sup), (v["part"], by_part)):
            if not key: continue
            x = store.setdefault(key, {"qty": 0.0, "defects": 0.0, "lots": 0}); x["qty"] += q; x["defects"] += d; x["lots"] += 1
    f = lambda x: round(1e6 * x["defects"] / x["qty"]) if x["qty"] else None
    return {"suppliers": {k: {**v, "ppm": f(v)} for k, v in by_sup.items()}, "parts": {k: {**v, "ppm": f(v)} for k, v in by_part.items()}}


def capa_rows(m):
    out = []
    for c, v in m.get("capa", {}).items():
        t = v.get("verification_test"); tv = m["tests"].get(t, {}) if t else {}
        steps = {"containment": bool(v.get("containment")), "root_cause": bool(v.get("root_cause")), "corrective": bool(v.get("corrective")), "preventive": bool(v.get("preventive")), "verified": bool(v.get("verified")) or tv.get("status") == "passed"}
        out.append({"id": c, **v, "steps": steps, "done": sum(steps.values()), "overdue": bool(v.get("due")) and v.get("status") != "closed" and str(v["due"]) < _dt.date.today().isoformat()})
    return out


def supplier_quality_view(m, rep):
    ppm = supplier_ppm(m); t = (m.get("meta") or {}).get("business", {}).get("ppm_target", 500)
    tl = m.get("tooling", {})
    return {"suppliers": list(m.get("suppliers", {}).keys()), "suppliers_over_ppm_target": [k for k, v in ppm["suppliers"].items() if v["ppm"] is not None and v["ppm"] > t],
            "parts_without_incoming_inspection": [p for p, v in m["parts"].items() if (v.get("make_buy") or "buy") == "buy" and not v.get("context") and p not in ppm["parts"]],
            "ppap_open": [k for k, v in tl.items() if v.get("ppap") not in ("approved",)], "supplier_capa_open": [c["id"] for c in capa_rows(m) if c["source"] in ("inspection", "supplier") and c["status"] != "closed"],
            "suppliers_without_agreement": [s for s, v in m.get("suppliers", {}).items() if not v.get("agreement")]}


def launch_quality_view(m, rep):
    ins = [i for i, v in m.get("inspections", {}).items() if v.get("stage") in ("in-process", "eol", "end-of-line")]
    ppm = supplier_ppm(m)
    return {"build_inspections": ins, "eol_yield": [_yield(m)], "process_steps_without_pfmea": rep.get("process_steps_without_pfmea", []), "open_findings": [f for f, v in m.get("findings", {}).items() if v["status"] != "closed"],
            "capa_open_before_build": [c["id"] for c in capa_rows(m) if c["status"] != "closed"], "ppap_not_approved": [k for k, v in m.get("tooling", {}).items() if v.get("ppap") != "approved"], "parts_over_ppm": [k for k, v in ppm["parts"].items() if v["ppm"] and v["ppm"] > 1000]}


def _yield(m):
    q = d = 0.0
    for v in m.get("inspections", {}).values():
        if v.get("stage") in ("eol", "end-of-line"): q += float(v.get("qty") or 0); d += float(v.get("defects") or 0)
    return f"EoL first-pass yield {round(100 * (1 - d / q), 1)} % over {int(q)} units" if q else "no end-of-line inspections yet"


def field_quality_view(m, rep):
    fe = m.get("field_events", {}); units = (m.get("meta") or {}).get("business", {}).get("units_in_field")
    by_fm = {}
    for f, v in fe.items():
        by_fm.setdefault(v.get("fm") or "unlinked", 0); by_fm[v.get("fm") or "unlinked"] += int(v.get("count") or 1)
    pareto = sorted(by_fm.items(), key=lambda kv: -kv[1])
    total = sum(by_fm.values())
    return {"field_events_open": [f for f, v in fe.items() if v.get("status", "open") != "closed"], "events_without_failure_mode": [f for f, v in fe.items() if not v.get("fm")],
            "pareto": [f"{k}: {n}" for k, n in pareto[:8]], "field_rate": [f"{total} events" + (f" over {units} units = {round(1000 * total / units, 2)} per 1,000" if units else " — set meta.business.units_in_field for a rate")],
            "capa_open": [c["id"] for c in capa_rows(m) if c["source"] == "field" and c["status"] != "closed"], "capa_unverified": [c["id"] for c in capa_rows(m) if c["status"] == "closed" and not c["steps"]["verified"]],
            "high_ap_without_diagnostic": [x["id"] for x in D.fmea(m) if x.get("AP") == "H" and not x.get("controls")]}


def design_quality_view(m, rep):
    cmf = [p for p, v in m["parts"].items() if str(v.get("attrs", {}).get("visible", "")).lower() in ("yes", "true", "1")]
    return {"visible_parts": cmf, "visible_parts_without_cmf": [p for p in cmf if not m["parts"][p].get("attrs", {}).get("cmf")], "design_reviews": [r for r, v in m.get("reviews", {}).items() if "design" in v.get("name", "").lower()],
            "open_findings_design": [f for f, v in m.get("findings", {}).items() if v.get("source") == "design" and v["status"] != "closed"], "perceived_quality_notes": [n for n, v in m.get("notes", {}).items() if v.get("kind") in ("design_quality", "perceived_quality", "cmf")]}


# =====================================================================================================================
# SUPPLY CHAIN department — sourcing (AVL, exists) / procurement (exists) / industrialization / logistics
# =====================================================================================================================
def tooling_rows(m):
    out = []
    for t, v in m.get("tooling", {}).items():
        p = m["parts"].get(v["part"], {}); gates = m["gates"]
        need = next((g for g, gv in sorted(gates.items(), key=lambda kv: kv[1]["date"]) if (m.get("meta") or {}).get("business", {}).get("builds", {}).get(g)), None)
        out.append({"id": t, **v, "part_name": p.get("name", ""), "first_build": need, "first_build_date": gates.get(need, {}).get("date", "") if need else "",
                    "t1_late": bool(v.get("t1")) and need and str(v["t1"]) > str(gates.get(need, {}).get("date", "9999")), "late": not v.get("kickoff") and need and _days_to(gates[need]["date"]) is not None and _days_to(gates[need]["date"]) < 120})
    return out


def industrialization_view(m, rep):
    tr = tooling_rows(m)
    tooled = {t["part"] for t in tr}
    need_tool = [p for p, v in m["parts"].items() if not v.get("context") and (v.get("make_buy") or "buy") in ("make", "buy") and any(k in (v.get("attrs", {}).get("material", "") + v.get("type", "") + v["name"]).lower() for k in ("pp", "abs", "polycarbonate", "tritan", "injection", "housing", "basket", "molded", "mold", "stamp", "cast", "die"))]
    dfx = None
    try:
        from . import dfx as DFX
        dfx = DFX.evaluate(m, "manufacturing")
    except Exception: pass
    return {"tooling": [t["id"] for t in tr], "parts_needing_tooling_without_tool": [p for p in need_tool if p not in tooled], "tooling_not_kicked_off": [t["id"] for t in tr if not t.get("kickoff")],
            "t1_after_first_build": [t["id"] for t in tr if t["t1_late"]], "ppap_open": [t["id"] for t in tr if t.get("ppap") != "approved"], "fai_missing": [t["id"] for t in tr if t.get("t1") and not t.get("fai")],
            "dfm_score": [f"Design for manufacturing {dfx['score']} %" if dfx and dfx.get("score") is not None else "DfM not evaluated"], "capacity_short": [t["id"] for t in tr if t.get("capacity_per_week") and (m.get("meta") or {}).get("business", {}).get("annual_volume") and float(t["capacity_per_week"]) * 50 < float(m["meta"]["business"]["annual_volume"])]}


def logistics_view(m, rep):
    b = _business(m); q = m.get("quotes", {})
    pkg = [p for p, v in m["parts"].items() if "pack" in (v.get("type", "") + v["name"]).lower() and "pack" in v["name"].lower() and "battery" not in v["name"].lower()]
    return {"incoterm": [b.get("incoterm") or "— set meta.business.incoterm"], "quotes_without_incoterm": [k for k, v in q.items() if not v.get("incoterm")], "packaging_parts": pkg,
            "transport_tests": [t for t, v in m["tests"].items() if any(k in (v.get("method", "") + v["name"]).lower() for k in ("ista", "drop", "transport", "vibration", "shipping"))],
            "long_lead_imports": [r["part"] for r in procurement(m) if r["lead_time_d"] not in (None, "") and int(r["lead_time_d"]) >= 56], "freight_notes": [n for n, v in m.get("notes", {}).items() if v.get("kind") in ("logistics", "freight", "packaging")]}


FOCUS_VIEWS.update({"supplier_quality": supplier_quality_view, "launch_quality": launch_quality_view, "field_quality": field_quality_view, "design_quality": design_quality_view,
                    "industrialization": industrialization_view, "logistics": logistics_view})


def ppm_form(m):
    ppm = supplier_ppm(m); rows = []
    for s, v in sorted(ppm["suppliers"].items(), key=lambda kv: -(kv[1]["ppm"] or 0)):
        rows.append([s, m.get("suppliers", {}).get(s, {}).get("name", ""), int(v["qty"]), int(v["defects"]), v["ppm"], v["lots"], ", ".join(p for p, pv in m["parts"].items() if pv.get("supplier") == s)])
    headers = ["Supplier", "Name", "Units inspected", "Defects", "PPM", "Lots", "Parts"]
    return [("SUPPLIER QUALITY — INCOMING PPM", len(headers))], headers, [10, 26, 12, 10, 8, 6, 30], rows


def capa_form(m):
    rows = [[c["id"], c["title"], c["source"], c.get("source_id", ""), ", ".join(c.get("parts", [])), c.get("fm", ""), "✓" if c["steps"]["containment"] else "", "✓" if c["steps"]["root_cause"] else "", "✓" if c["steps"]["corrective"] else "", "✓" if c["steps"]["preventive"] else "", c.get("verification_test") or "", "✓" if c["steps"]["verified"] else "", c.get("owner", ""), c.get("due", ""), c["status"] + (" OVERDUE" if c["overdue"] else "")] for c in capa_rows(m)]
    headers = ["CAPA", "Title", "Source", "Source id", "Parts", "Failure mode", "D3 contain", "D4 root cause", "D5 corrective", "D7 preventive", "Verification test", "D6 verified", "Owner", "Due", "Status"]
    return [("CAPA / 8D LOG (every quality loop closed with a verified corrective action)", len(headers))], headers, [8, 28, 9, 9, 14, 8, 6, 6, 6, 6, 10, 6, 10, 9, 10], rows


def tooling_form(m):
    rows = [[t["id"], t["part"], t["part_name"], t.get("supplier", ""), t.get("type", ""), t.get("cavities") or "", t.get("cost_usd") or "", t.get("owner", ""), t.get("kickoff", ""), t.get("t0", ""), t.get("t1", ""), t.get("t2", ""), t["first_build"] or "", t["first_build_date"], t.get("status", ""), t.get("ppap", ""), t.get("fai", ""), "T1 LATE" if t["t1_late"] else ("KICK OFF" if t["late"] else "")] for t in tooling_rows(m)]
    headers = ["Tool", "Part", "Name", "Supplier", "Type", "Cav.", "Cost (USD)", "Owner", "Kick-off", "T0", "T1", "T2", "First build", "Build date", "Status", "PPAP", "FAI", "Flag"]
    return [("TOOLING & PPAP — LAUNCH READINESS", len(headers))], headers, [7, 8, 22, 10, 12, 5, 9, 8, 9, 9, 9, 9, 7, 9, 9, 10, 8, 8], rows


FORMS.update({"ppm": ("Supplier PPM", "Incoming-inspection PPM per supplier and part", ppm_form), "capa": ("CAPA / 8D log", "Closed-loop corrective actions from findings, field events and inspections", capa_form),
              "tooling": ("Tooling & PPAP", "Tools per part with T-samples, PPAP and FAI against the first build", tooling_form)})


def quality_supply_check(m, typ, c):
    key = c.get("key")
    if typ == "tooling":
        tr = tooling_rows(m)
        if not tr: return {"status": "missing", "measured": "no tooling records", "link": "/form/tooling"}
        if key == "kicked_off": ok = [t for t in tr if t.get("kickoff")]; lab = "kicked off"
        elif key == "t1": ok = [t for t in tr if t.get("t1") and not t["t1_late"]]; lab = "T1 before first build"
        elif key == "ppap": ok = [t for t in tr if t.get("ppap") == "approved"]; lab = "PPAP approved"
        else: ok = []; lab = key
        return {"status": "done" if len(ok) == len(tr) else ("partial" if ok else "missing"), "measured": f"{len(ok)}/{len(tr)} {lab}", "link": "/form/tooling"}
    if typ == "capa":
        rows = [x for x in capa_rows(m) if not c.get("source") or x["source"] == c["source"]]
        op = [x for x in rows if x["status"] != "closed"]; unver = [x for x in rows if x["status"] == "closed" and not x["steps"]["verified"]]
        return {"status": "done" if not op and not unver else ("partial" if rows else "missing" if c.get("n", 0) else "done"), "measured": f"{len(op)} open · {len(unver)} closed without verification · {len(rows)} total", "link": "/form/capa"}
    if typ == "ppm":
        ppm = supplier_ppm(m); t = c.get("max", 500); over = [k for k, v in ppm["suppliers"].items() if v["ppm"] is not None and v["ppm"] > t]
        if not ppm["suppliers"]: return {"status": "missing", "measured": "no incoming inspections", "link": "/form/ppm"}
        return {"status": "done" if not over else "partial", "measured": f"{len(over)} suppliers over {t} PPM", "link": "/form/ppm"}
    if typ == "field_loop":
        fe = m.get("field_events", {}); unl = [f for f, v in fe.items() if not v.get("fm")]; op = [x for x in capa_rows(m) if x["source"] == "field" and x["status"] != "closed"]
        return {"status": "done" if not unl and not op else "partial", "measured": f"{len(fe)} events · {len(unl)} without failure mode · {len(op)} CAPA open", "link": "/form/fracas"}
    return None
