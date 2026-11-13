"""Launch as an MCP server — the graph as a connector any Claude (Claude.ai plugins such as Claude for Manufacturing, Claude Code,
Cowork, other agents) can read from and propose to.

Two transports:
  * stdio:  `launch mcp --data <root> --tenant <t> --user <email>`  (for Claude Code / desktop configs)
  * HTTP:   mounted at /mcp on the web server; HTTP Basic `email:token` (token from /api/token), streamable-HTTP transport

Reads are the same derivations the UI uses (forms in standard shape, procurement, quality, trades, indicators, analytics, maturity).
Writes never bypass the kernel: `propose_patch` stages a patch for human review in the project's inbox; `record_*` tools apply
small factual records (an inspection lot, a test run, a station result) with provenance `mcp:<user>`, exactly like a person typing them.
"""
from __future__ import annotations
import json, os, time, base64
from typing import Any
from mcp.server.mcpserver import MCPServer

from . import derive, forms as FORMS, business as B, trades as TRADES, indicators as IND, analytics as AN, maturity as MAT, ops as OPS, pdp, schema, skills as SK
from .store import Patch, Op


def _j(x): return json.dumps(x, ensure_ascii=False, default=str)


def build(W, user_of=lambda: os.environ.get("USER", "mcp")) -> MCPServer:
    srv = MCPServer("launch", instructions="Launch: the MBSE graph of hardware products as a system of record. Every tool takes a project id (pid); list_projects gives them. "
                    "Reads return the same derived artifacts the app shows (requirements, DFMEA, DVP&R, procurement plan, supplier PPM, CAPA, trade studies, leading indicators, analytics, maturity). "
                    "Writes are proposals: propose_patch stages a change for a person to review in the project's inbox; record_inspection / record_test_run / record_station_result apply factual records with your name as provenance. Never invent ids — search first.")

    def S(pid): return W.get(pid)
    def M(pid): return S(pid).store.load()
    def who(): return f"mcp:{user_of()}"

    @srv.tool(description="Projects in this organization with counts, status and the stage.")
    def list_projects() -> str: return _j([W.summary(p) for p in W.ids()])

    @srv.tool(description="Full-text search across every element kind of a project: id, name, text, attributes. Returns id, kind, title, snippet.")
    def search(pid: str, q: str, limit: int = 25) -> str:
        m = M(pid); ql = q.lower(); out = []
        for kind in schema.KINDS:
            for eid, v in (m.get(kind) or {}).items():
                blob = f"{eid} {json.dumps(v, ensure_ascii=False)}".lower()
                if ql in blob: out.append({"id": eid, "kind": kind, "title": v.get("name") or v.get("title") or v.get("text", "")[:80]})
                if len(out) >= limit: return _j(out)
        return _j(out)

    @srv.tool(description="One element with its kind, data, and the elements it links to (where-used).")
    def element(pid: str, eid: str) -> str:
        m = M(pid); kind = next((k for k in schema.KINDS if eid in (m.get(k) or {})), None)
        if not kind: return _j({"error": "no such element"})
        return _j({"id": eid, "kind": kind, "data": m[kind][eid], "where_used": derive.where_used(m, eid) if hasattr(derive, "where_used") else None})

    @srv.tool(description="A whole collection (kind) of a project, e.g. requirements, parts, tests, suppliers, quotes, inspections, capa, tooling, change_orders, work_orders, units, cdas, claims, trades. Optional filter: key=value on the element data.")
    def collection(pid: str, kind: str, key: str = "", value: str = "") -> str:
        m = M(pid); rows = {k: v for k, v in (m.get(kind) or {}).items() if not key or str(v.get(key)) == value}
        return _j(rows)

    @srv.tool(description="A derived artifact in its standard shape (headers + rows): dfmea, pfmea, dvpr, vcrm, reqspec, icd, risks, findings, fracas, avl, procurement, ppm, capa, tooling, eco, work_orders, purchase_orders, claims, cost, markets, staffing, trl, cda, certification, control_plan, hazards, fta.")
    def form(pid: str, name: str) -> str:
        if name not in FORMS.FORMS: return _j({"error": "unknown form", "available": sorted(FORMS.FORMS)})
        title, desc, fn = FORMS.FORMS[name]; groups, headers, widths, rows = fn(M(pid))
        return _j({"title": title, "description": desc, "headers": headers, "rows": rows})

    @srv.tool(description="Trace health: coverage report with every gap list (requirements without tests, regulations without requirements, unassessed failure modes, buy parts without supplier, pending handoffs...).")
    def coverage(pid: str) -> str: return _j(derive.coverage_report(M(pid)))

    @srv.tool(description="Procurement plan: every buy part with quote status, awarded/best unit cost vs BOM cost, lead time against the first build (order-by date, LATE), MOQ vs build qty, second source, critical flag.")
    def procurement_plan(pid: str) -> str: return _j(B.procurement(M(pid)))

    @srv.tool(description="RFQ package for a buy part derived from the graph: attributes, interfaces to mate, requirements, regulations/declarations, drawings/CAD, quantities per build, quality and commercial asks.")
    def rfq_package(pid: str, part: str) -> str: return _j(B.rfq_package(M(pid), part) or {"error": "no such part"})

    @srv.tool(description="Quality: supplier PPM from incoming inspections, CAPA/8D rows with step completion, field-quality Pareto.")
    def quality(pid: str) -> str:
        m = M(pid); rep = derive.coverage_report(m)
        return _j({"ppm": B.supplier_ppm(m), "capa": B.capa_rows(m), "field": B.field_quality_view(m, rep), "launch": B.launch_quality_view(m, rep)})

    @srv.tool(description="Trade studies: list with hygiene checks, or one study evaluated (weighted matrix, knock-outs, Pugh, sensitivity, decision).")
    def trade_studies(pid: str, tid: str = "") -> str:
        m = M(pid); return _j(TRADES.evaluate(m, tid) if tid else {"studies": TRADES.summary(m), "checks": TRADES.checks(m)})

    @srv.tool(description="Leading indicators with thresholds grouped by GAO theme, gate-slip risk per upcoming gate, and the intervention each red/amber calls for.")
    def leading_indicators(pid: str) -> str:
        s = S(pid); r = IND.compute(s.store.load(), s.store); r["interventions"] = IND.interventions(r); return _j(r)

    @srv.tool(description="Analytics aggregate incl. project maturity (composite vs expected profile at the next gate), gates, departments, verification, risk, quality, supply, cost, TRL, CDAs, change, activity.")
    def analytics(pid: str) -> str:
        s = S(pid); return _j(AN.compute(s.store.load(), s.store))

    @srv.tool(description="Technology readiness (declared vs demonstrated per part) and critical design attributes with current values, margins and trends.")
    def maturity(pid: str) -> str:
        m = M(pid); return _j({"trl": MAT.trl_rows(m), "cdas": MAT.cda_rows(m)})

    @srv.tool(description="Development process: gates with dates, the gate × team deliverable matrix with automatic check results, unowned deliverables.")
    def gates(pid: str) -> str: return _j(pdp.matrix(M(pid)))

    @srv.tool(description="Impact of changing a set of items (parts, requirements): downstream functions, requirements, interfaces, tests to re-run, failure modes, tooling, awarded quotes, open POs, owning teams.")
    def change_impact(pid: str, affected: list[str]) -> str: return _j(OPS.change_order_impact(M(pid), {"affected": affected}))

    # ---------------- skills: the catalog as data, each skill as an MCP prompt ----------------
    @srv.tool(description="Named skills (packaged jobs: trigger, reads, procedure, outputs, role) and which of them apply to this project right now with the reason and ids to scope them to. Run one by using its prompt (skill_<id>) or by following the procedure with the read tools and propose_patch.")
    def skills(pid: str) -> str:
        s = S(pid); m = s.store.load()
        try: ind = IND.compute(m, s.store)
        except Exception: ind = {}
        return _j({"suggested": SK.suggest(m, ind), "catalog": SK.catalog()})
    def _mk(sk):
        def _p(pid: str, ids: str = "") -> str:
            return f"Project {pid}. " + SK.prompt_for(sk, [x.strip() for x in ids.split(",") if x.strip()]) + " Read with the launch tools; write only through propose_patch (staged for review) or the record_* tools for data you observed."
        _p.__name__ = "skill_" + sk["id"].replace("-", "_"); return _p
    for _sk in SK.SKILLS: srv.prompt(name="skill_" + _sk["id"].replace("-", "_"), title=_sk["name"], description=f"[{_sk['department']}/{_sk['role']}] {_sk['trigger']}")(_mk(_sk))

    # ---------------- writes ----------------
    @srv.tool(description="Propose a change to the graph for human review (staged in the project's inbox). ops: list of {op: add|update|remove, kind, id, value}. Give a rationale and the source ids the change rests on. Returns the staged patch id.")
    def propose_patch(pid: str, ops: list[dict], rationale: str, sources: list[str] | None = None) -> str:
        s = S(pid); m = s.store.load(); clean = []
        for o in ops:
            op = o.get("op", "update"); kind = o.get("kind"); eid = o.get("id"); val = o.get("value", o.get("data", o.get("fields")))
            if op not in ("add", "update", "remove"): return _j({"error": f"op must be add|update|remove, got {op!r}"})
            if kind not in m: return _j({"error": f"unknown collection {kind!r}", "collections": sorted(k for k in m if isinstance(m[k], dict))})
            if not eid: return _j({"error": "each op needs an id"})
            if op == "add" and eid in m[kind]: return _j({"error": f"{eid} already exists in {kind}; use update"})
            if op != "add" and eid not in m[kind]: return _j({"error": f"{eid} not in {kind}"})
            if op != "remove" and not isinstance(val, dict): return _j({"error": f"{op} needs value {{field: value}}"})
            clean.append(Op(op=op, kind=kind, id=eid, value=val))
        p = Patch(ops=clean, author=who(), rationale=rationale[:300], sources=sources or [])
        return _j({"staged": s.store.stage(p), "ops": len(clean), "review": f"/p/{pid}/inbox"})

    @srv.tool(description="Record an inspection lot (incoming | in-process | eol): part, qty, defects, optional supplier, lot, defect_codes, disposition, station, build. Applied immediately with your name; feeds supplier PPM and launch quality.")
    def record_inspection(pid: str, part: str, stage: str, qty: int, defects: int, supplier: str = "", lot: str = "", defect_codes: list[str] | None = None, disposition: str = "", station: str = "", build: str = "", notes: str = "") -> str:
        s = S(pid); m = s.store.load(); n = len(m.get("inspections", {})) + 1; iid = f"INS-{n:02d}"
        val = {"date": time.strftime("%Y-%m-%d"), "part": part, "stage": stage, "qty": qty, "defects": defects, "supplier": supplier or None, "lot": lot, "defect_codes": defect_codes or [], "disposition": disposition, "station": station, "build": build or None, "by": who(), "notes": notes}
        p = Patch(ops=[Op(op="add", kind="inspections", id=iid, value=val)], author=who(), rationale=f"Inspection {iid}: {part} {stage} {defects}/{qty}", sources=[part]); sid = s.store.stage(p); s.store.approve(sid, approver=who())
        return _j({"id": iid, **val})

    @srv.tool(description="Record a test run: test id, result pass|fail, optional unit/serial, metrics {key: value} (feeds critical design attributes), notes. Applied immediately.")
    def record_test_run(pid: str, test: str, result: str, unit: str = "", metrics: dict | None = None, notes: str = "") -> str:
        s = S(pid); m = s.store.load()
        if test not in m["tests"]: return _j({"error": "no such test"})
        n = len(m.get("test_runs", {})) + 1; rid = f"RUN-{n:02d}"
        val = {"test": test, "date": time.strftime("%Y-%m-%d"), "result": result, "unit": unit, "metrics": metrics or {}, "notes": notes, "by": who()}
        ops = [Op(op="add", kind="test_runs", id=rid, value=val), Op(op="update", kind="tests", id=test, value={"status": "passed" if result == "pass" else "failed", "last_run": val["date"]})]
        p = Patch(ops=ops, author=who(), rationale=f"Run {rid}: {test} {result}", sources=[test]); sid = s.store.stage(p); s.store.approve(sid, approver=who())
        return _j({"id": rid, **val})

    @srv.tool(description="Record a station result for a serial on a work order (MES): work_order, serial, step (process step id), result pass|fail, data {key: value}, components {part: serial_or_lot}. Creates the unit on first sight; a fail becomes an in-process inspection.")
    def record_station_result(pid: str, work_order: str, serial: str, step: str, result: str, data: dict | None = None, components: dict | None = None, defect_codes: list[str] | None = None) -> str:
        s = S(pid); m = s.store.load(); wo = m.get("work_orders", {}).get(work_order)
        if not wo: return _j({"error": "no such work order"})
        uid = next((u for u, v in m.get("units", {}).items() if v.get("serial") == serial and v.get("work_order") == work_order), None)
        cur = m["units"][uid] if uid else {"serial": serial, "work_order": work_order, "components": {}, "stations": {}, "status": "in progress", "built": time.strftime("%Y-%m-%d")}
        st = dict(cur.get("stations") or {}); st[step] = {"result": result, "date": time.strftime("%Y-%m-%d"), "by": who(), "data": data or {}, "defect_codes": defect_codes or []}
        routing = wo.get("routing") or sorted(m.get("process_steps", {}), key=lambda x: m["process_steps"][x].get("order", 0))
        status = "failed" if any(v.get("result") == "fail" for v in st.values()) else ("complete" if all(st.get(x, {}).get("result") == "pass" for x in routing) else "in progress")
        value = {**cur, "stations": st, "components": {**(cur.get("components") or {}), **(components or {})}, "status": status}; uid2 = uid or f"U-{work_order}-{serial}"
        ops = [Op(op="update" if uid else "add", kind="units", id=uid2, value=value)]
        if result == "fail":
            n = len(m.get("inspections", {})) + 1; part = (m["process_steps"].get(step, {}).get("parts") or [next(iter(m["parts"]))])[0]
            ops.append(Op(op="add", kind="inspections", id=f"INS-{n:02d}", value={"date": time.strftime("%Y-%m-%d"), "part": part, "stage": "in-process", "qty": 1, "defects": 1, "station": step, "unit": uid2, "defect_codes": defect_codes or [], "build": wo.get("build"), "by": who()}))
        p = Patch(ops=ops, author=who(), rationale=f"{work_order} {serial} @ {step}: {result}", sources=[work_order]); sid = s.store.stage(p); s.store.approve(sid, approver=who())
        return _j({"unit": uid2, "status": status})

    # ---------------- resources: forms as documents ----------------
    @srv.resource("launch://{pid}/form/{name}", description="A derived artifact as JSON (headers + rows)")
    def form_resource(pid: str, name: str) -> str: return form(pid, name)

    return srv


def basic_auth_user(W, headers) -> str | None:
    """HTTP Basic email:token (token from /api/token) → user email, or None."""
    h = headers.get("authorization") or headers.get("Authorization") or ""
    if not h.lower().startswith("basic "): return None
    try: email, token = base64.b64decode(h.split(" ", 1)[1]).decode().split(":", 1)
    except Exception: return None
    return email if W.token_ok(email, token) else None
