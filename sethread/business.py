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
    if typ == "fru":
        fru = [p for p, v in m["parts"].items() if str(v.get("attrs", {}).get("field_replaceable", "")).lower() in ("yes", "true", "1")]
        return {"status": "done" if len(fru) >= c.get("n", 1) else "missing", "measured": f"{len(fru)} field-replaceable parts", "link": "/collection/parts"}
    return None
