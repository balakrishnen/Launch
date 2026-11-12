"""Operations modules — the small native beginnings of PLM, MES and ERP on the Launch graph.

Each is one kind plus derivations; because the records live in the same graph as parts, process steps, quotes and tests,
"bidirectional" is automatic: a change order carries the parts it affects and the baseline it creates; a work order builds
units whose station results are inspections and test runs; a purchase order is cut from an awarded quote and its actual
cost writes back to the part. When any of these grows into its own product, the kind becomes its API.

PLM  — change_orders: ECO with affected items, impact (derived), approvals, effectivity, baseline on release
MES  — work_orders: a build (gate) of N units at a line; units: serial numbers with genealogy (child serials/lots per part),
        station results (pass/fail per process step), and the inspections/test runs that reference them
ERP  — purchase_orders: from an awarded quote; lines (part, qty, unit cost), receipts write actual cost and lot to the graph
"""
from __future__ import annotations
import datetime as _dt
from . import derive as D


def _today(): return _dt.date.today().isoformat()


# ---------------- PLM: change orders ----------------
def change_order_impact(m, co):
    """Everything downstream of the affected items, from the graph: functions, requirements, interfaces, tests to re-run,
    failure modes, tooling, quotes and open purchase orders touching those parts."""
    items = set(co.get("affected", []))
    parts = {i for i in items if i in m["parts"]}; reqs = {i for i in items if i in m["requirements"]}
    funcs = {f for f, v in m["functions"].items() if set(v.get("alloc", [])) & parts or set(v.get("reqs", [])) & reqs}
    reqs |= {r for f in funcs for r in m["functions"][f].get("reqs", [])}
    ifaces = [i for i, v in m["interfaces"].items() if v.get("a") in parts or v.get("b") in parts]
    tests = sorted({t for r in reqs for t in m["requirements"][r].get("tests", [])} | {t for t, v in m["tests"].items() if v.get("element") in parts})
    fms = [x["id"] for x in D.fmea(m) if x.get("element") in parts or x.get("element") in funcs]
    tooling = [t for t, v in m.get("tooling", {}).items() if v.get("part") in parts]
    quotes = [q for q, v in m.get("quotes", {}).items() if v.get("part") in parts and v.get("status") == "awarded"]
    pos = [p for p, v in m.get("purchase_orders", {}).items() if v.get("status") in ("open", "issued") and any(l.get("part") in parts for l in v.get("lines", []))]
    teams = sorted({m["parts"][p].get("owner_team") for p in parts if m["parts"][p].get("owner_team")})
    return {"parts": sorted(parts), "functions": sorted(funcs), "requirements": sorted(reqs), "interfaces": ifaces, "tests_to_rerun": tests, "failure_modes": fms, "tooling": tooling, "awarded_quotes": quotes, "open_purchase_orders": pos, "owning_teams": teams}


def change_orders(m):
    out = []
    for c, v in m.get("change_orders", {}).items():
        imp = change_order_impact(m, v); appr = v.get("approvals") or {}
        need = set(v.get("approvers") or imp["owning_teams"]); got = {k for k, a in appr.items() if a.get("decision") == "approved"}
        out.append({"id": c, **v, "impact": imp, "approvals_needed": sorted(need), "approvals_got": sorted(got), "approved": bool(need) and need <= got, "ready_to_release": v.get("status") == "approved" or (bool(need) and need <= got)})
    return out


def release_ops(m, cid, by):
    """Patch ops that release a change order: status released, effectivity date, and a note on every affected part's rev."""
    co = m["change_orders"][cid]; ops = [{"op": "update", "kind": "change_orders", "id": cid, "value": {"status": "released", "released": _today(), "released_by": by}}]
    for p in co.get("affected", []):
        if p in m["parts"]:
            a = dict(m["parts"][p].get("attrs", {})); rev = a.get("rev", "A"); a["rev"] = _bump(rev); a["last_eco"] = cid
            ops.append({"op": "update", "kind": "parts", "id": p, "value": {"attrs": a}})
    return ops


def _bump(rev):
    rev = str(rev or "A")
    if rev.isalpha() and len(rev) == 1 and rev != "Z": return chr(ord(rev) + 1)
    try: return str(int(rev) + 1)
    except ValueError: return rev + "1"


# ---------------- MES: work orders and serialized units ----------------
def work_orders(m):
    out = []
    for w, v in m.get("work_orders", {}).items():
        units = {u: uv for u, uv in m.get("units", {}).items() if uv.get("work_order") == w}
        steps = v.get("routing") or sorted(m.get("process_steps", {}), key=lambda s: m["process_steps"][s].get("order", 0))
        done = [u for u, uv in units.items() if all((uv.get("stations") or {}).get(s, {}).get("result") == "pass" for s in steps)]
        failed = [u for u, uv in units.items() if any((uv.get("stations") or {}).get(s, {}).get("result") == "fail" for s in steps)]
        per_step = {s: {"pass": sum(1 for uv in units.values() if (uv.get("stations") or {}).get(s, {}).get("result") == "pass"), "fail": sum(1 for uv in units.values() if (uv.get("stations") or {}).get(s, {}).get("result") == "fail")} for s in steps}
        fpy = None
        if units:
            first_fail = sum(1 for uv in units.values() if any((uv.get("stations") or {}).get(s, {}).get("result") == "fail" for s in steps)); fpy = round(100 * (1 - first_fail / len(units)), 1)
        out.append({"id": w, **v, "routing": steps, "built": len(units), "complete": len(done), "failed": len(failed), "per_step": per_step, "first_pass_yield": fpy, "units": sorted(units)})
    return out


def unit_genealogy(m, uid):
    u = m.get("units", {}).get(uid)
    if not u: return None
    wo = m.get("work_orders", {}).get(u.get("work_order"), {})
    comp = []
    for p, src in (u.get("components") or {}).items():
        pv = m["parts"].get(p, {}); comp.append({"part": p, "name": pv.get("name", ""), "serial_or_lot": src, "supplier": pv.get("supplier"), "rev": pv.get("attrs", {}).get("rev", "")})
    runs = [r for r, v in m.get("test_runs", {}).items() if v.get("unit") == uid]
    ins = [i for i, v in m.get("inspections", {}).items() if v.get("unit") == uid or (v.get("lot") and v["lot"] in (u.get("components") or {}).values())]
    fe = [f for f, v in m.get("field_events", {}).items() if v.get("unit") == uid]
    return {"id": uid, **u, "work_order": wo and {"id": u.get("work_order"), **wo}, "components": comp, "test_runs": runs, "inspections": ins, "field_events": fe}


# ---------------- ERP: purchase orders ----------------
def po_from_quote(m, qid, qty, by):
    q = m["quotes"][qid]; n = len(m.get("purchase_orders", {})) + 1
    pid = f"PO-{n:04d}"
    val = {"supplier": q["supplier"], "status": "issued", "date": _today(), "lines": [{"part": q["part"], "qty": qty, "unit_cost_usd": q.get("unit_cost_usd"), "quote": qid}], "incoterm": q.get("incoterm", ""), "currency": "USD", "by": by, "receipts": []}
    return pid, val


def purchase_orders(m):
    out = []
    for p, v in m.get("purchase_orders", {}).items():
        total = sum(float(l.get("qty") or 0) * float(l.get("unit_cost_usd") or 0) for l in v.get("lines", []))
        recd = sum(float(r.get("qty") or 0) for r in v.get("receipts", []))
        ordered = sum(float(l.get("qty") or 0) for l in v.get("lines", []))
        out.append({"id": p, **v, "total_usd": round(total, 2), "received": recd, "ordered": ordered, "open_qty": ordered - recd})
    return out


def receive_ops(m, pid, part, qty, lot, actual_unit_cost, by):
    """Receiving a PO line: receipt on the PO, actual cost on the part (beside the quoted), and an incoming-inspection stub."""
    po = m["purchase_orders"][pid]; receipts = list(po.get("receipts", [])) + [{"part": part, "qty": qty, "lot": lot, "date": _today(), "unit_cost_usd": actual_unit_cost, "by": by}]
    ordered = sum(float(l.get("qty") or 0) for l in po.get("lines", [])); recd = sum(float(r.get("qty") or 0) for r in receipts)
    ops = [{"op": "update", "kind": "purchase_orders", "id": pid, "value": {"receipts": receipts, "status": "received" if recd >= ordered else "partial"}}]
    if part in m["parts"] and actual_unit_cost not in (None, ""):
        a = dict(m["parts"][part].get("attrs", {})); a["cost_actual_usd"] = actual_unit_cost; ops.append({"op": "update", "kind": "parts", "id": part, "value": {"attrs": a}})
    n = len(m.get("inspections", {})) + 1
    ops.append({"op": "add", "kind": "inspections", "id": f"INS-{n:02d}", "value": {"date": _today(), "part": part, "stage": "incoming", "qty": qty, "defects": 0, "supplier": po["supplier"], "lot": lot, "disposition": "pending inspection", "by": by, "notes": f"auto from {pid} receipt"}})
    return ops


# ---------------- forms ----------------
def eco_form(m):
    rows = []
    for c in change_orders(m):
        i = c["impact"]; rows.append([c["id"], c["title"], c.get("reason", ""), c["status"], ", ".join(c.get("affected", [])), len(i["requirements"]), len(i["tests_to_rerun"]), ", ".join(i["tooling"]), ", ".join(i["open_purchase_orders"]), ", ".join(c["approvals_needed"]), ", ".join(c["approvals_got"]), c.get("effectivity", ""), c.get("released", "")])
    headers = ["ECO", "Title", "Reason", "Status", "Affected items", "Reqs impacted", "Tests to re-run", "Tooling", "Open POs", "Approvers", "Approved by", "Effectivity", "Released"]
    return [("ENGINEERING CHANGE ORDERS (impact derived from the graph)", len(headers))], headers, [8, 26, 18, 9, 20, 7, 7, 10, 10, 14, 14, 10, 10], rows


def wo_form(m):
    rows = []
    for w in work_orders(m):
        rows.append([w["id"], w.get("build", ""), w.get("qty", ""), w["built"], w["complete"], w["failed"], w["first_pass_yield"] if w["first_pass_yield"] is not None else "", w.get("line", ""), w.get("status", ""), "; ".join(f"{s}: {v['pass']}/{v['pass'] + v['fail']}" for s, v in w["per_step"].items() if v["pass"] + v["fail"])])
    headers = ["Work order", "Build", "Qty", "Started", "Complete", "Failed", "FPY %", "Line", "Status", "Per station pass/total"]
    return [("WORK ORDERS & STATION YIELD", len(headers))], headers, [10, 8, 6, 7, 8, 7, 7, 10, 9, 40], rows


def po_form(m):
    rows = []
    for p in purchase_orders(m):
        for l in p.get("lines", []): rows.append([p["id"], p.get("date", ""), p["supplier"], l["part"], l.get("qty"), l.get("unit_cost_usd"), l.get("quote", ""), p["received"], p["status"], p.get("incoterm", "")])
    headers = ["PO", "Date", "Supplier", "Part", "Qty", "Unit cost (USD)", "From quote", "Received", "Status", "Incoterm"]
    return [("PURCHASE ORDERS (cut from awarded quotes; receipts write actual cost back to the part)", len(headers))], headers, [8, 10, 12, 8, 6, 10, 8, 8, 9, 10], rows


FORMS = {"eco": ("Change orders (ECO)", "Engineering change orders with graph-derived impact and approvals", eco_form), "work_orders": ("Work orders", "Builds, serialized units and station yield", wo_form), "purchase_orders": ("Purchase orders", "POs from awarded quotes with receipts", po_form)}
