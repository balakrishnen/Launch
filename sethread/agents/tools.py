"""In-process MCP tools the role agents use. The model is read freely; it is changed only through propose_patch,
which validates and stages. Tools are built with the Claude Agent SDK (@tool + create_sdk_mcp_server)."""
from __future__ import annotations
import json, os, time
from typing import Any
from claude_agent_sdk import tool, create_sdk_mcp_server
from ..store import Store, Patch, Op
from .. import schema, derive, adapters, quality, library, lifecycle, trades as TRADES

def _txt(obj) -> dict:
    return {"content": [{"type": "text", "text": obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False, default=str)}]}

def make_server(store: Store, docs_dir: str | None = None, author: str = "agent"):
    """Return (server_config, tool_names) bound to one project store."""

    @tool("read_model", "Read a whole collection or one element of the system model. kinds: " + ", ".join(schema.KINDS), {"kind": str, "id": str})
    async def read_model(args: dict[str, Any]):
        m = store.load(); kind = args["kind"]; eid = args.get("id") or ""
        if kind not in m: return _txt({"error": f"unknown kind {kind}", "kinds": list(schema.KINDS)})
        return _txt(m[kind] if not eid else m[kind].get(eid, {"error": "no such id"}))

    @tool("model_schema", "Field schema for a collection (required fields, optional fields with defaults, which fields reference which collection). Call before your first propose_patch on a kind.", {"kind": str})
    async def model_schema(args):
        k = args.get("kind")
        if k and k in schema.KINDS: return _txt({k: schema.KINDS[k], "disciplines": schema.DISCIPLINES})
        return _txt({k: {"req": v["req"], "refs": v.get("refs", {})} for k, v in schema.KINDS.items()})

    @tool("model_summary", "Counts per collection, meta, and the coverage report (gaps). Call this first.", {})
    async def model_summary(args):
        m = store.load(); rep = derive.coverage_report(m)
        return _txt({"meta": m["meta"], "counts": {k: len(m[k]) for k in schema.KINDS}, "coverage": {k: (len(v) if hasattr(v, '__len__') and not isinstance(v, dict) else v) for k, v in rep.items() if k != "counts"}})

    @tool("list_gaps", "Ordered list of trace gaps to close (highest leverage first). Each item names the gap type and the element.", {"limit": int})
    async def list_gaps(args):
        return _txt(derive.gaps_as_tasks(store.load())[: args.get("limit") or 50])

    @tool("fmea_candidates", "Failure-mode candidates not yet assessed or screened: (element, guide word) pairs with element name, requirements and parts, so an assessment can be proposed.", {"limit": int})
    async def fmea_candidates(args):
        m = store.load(); out = []
        for u in derive.unassessed(m)[: args.get("limit") or 40]:
            out.append({**u, "reqs": derive.element_reqs(m, u["kind"], u["element"]), "parts": derive.element_parts(m, u["kind"], u["element"])})
        return _txt(out)

    @tool("derived_view", "A derived artifact: fmea | verification_matrix | certification_plan | discipline_matrix | trace | screened", {"name": str})
    async def derived_view(args):
        m = store.load(); fn = {"fmea": derive.fmea, "verification_matrix": derive.verification_matrix, "certification_plan": derive.certification_plan,
                                "discipline_matrix": derive.discipline_matrix, "trace": derive.trace, "screened": derive.screened}.get(args["name"])
        return _txt(fn(m) if fn else {"error": "unknown view"})

    @tool("impact", "Impact analysis: everything downstream/dependent on an element (requirements, functions, parts, failure modes, architecture decisions) and the tests that must be re-run if it changes. Call before proposing a change to an existing element.", {"id": str})
    async def impact(args):
        return _txt(derive.impact(store.load(), args["id"]))

    @tool("budgets", "Mass / power / cost / current / volume roll-ups over the part tree from part attrs (mass_g, power_W, cost_usd, current_mA, volume_cm3) compared with requirement limits; lists parts without a value.", {})
    async def budgets(args):
        return _txt(derive.budgets(store.load()))

    @tool("check_requirement", "Score a requirement statement against INCOSE Guide-to-Writing-Requirements rules (vague terms, escape clauses, compound, negatives, pronouns, no measurable quantity, no unit, passive, TBD). Use BEFORE proposing any requirement; rewrite until score ≥ 85.", {"text": str, "attr": str, "type": str})
    async def check_requirement(args):
        return _txt(quality.requirement_quality(args["text"], args.get("attr") or "", args.get("type") or ""))

    @tool("scorecard", "Model quality scorecard: trace coverage, requirement quality, FMEA completeness, High-AP test coverage, architecture and verification completeness, provenance; plus the ten worst requirements. Use to decide what to work on next and to report progress.", {})
    async def scorecard(args):
        return _txt(quality.scorecard(store.load(), store))

    @tool("library", "Engineering knowledge library. name: regulations (args: triggers list e.g. radio, battery_liion, skin_contact, mains, wearable, outdoor, ebike, vehicle, medical_claim, children, consumer, digital_electronics, iot_cloud; markets list e.g. US, EU, CA) | failure_modes (arg: discipline) | test_methods (arg: query). Company additions under <project>/library/*.yaml are merged in. Use as prompts, then tie every item to the actual element.", {"name": str, "triggers": list, "markets": list, "discipline": str, "query": str})
    async def library_tool(args):
        root = store.root; n = args["name"]
        if n == "regulations": return _txt(library.regulations_for(args.get("triggers") or [], args.get("markets") or None, root))
        if n == "failure_modes":
            d = library.load("failure_modes", root); return _txt(d.get(args.get("discipline"), d) if args.get("discipline") else d)
        if n == "test_methods":
            q = (args.get("query") or "").lower(); return _txt([t for t in library.load("test_methods", root) if not q or q in json.dumps(t).lower()])
        return _txt({"error": "unknown library", "available": ["regulations", "failure_modes", "test_methods"]})

    @tool("gate_readiness", "Lifecycle state: current stage, every gate with its exit criteria measured (pass/fail), blockers (open findings, pending handoffs, stale verification) and alerts. Use to plan work before a gate.", {})
    async def gate_readiness(args):
        return _txt(lifecycle.gate_readiness(store.load(), store))

    @tool("cad_brief", "Design brief for a part derived from the graph (purpose, mates/interfaces and items, requirement bounds, budgets, constraints, regulations, failure modes to design out, DfX guidelines). Hand this to a CAD engineer or a text-to-CAD agent; what comes back is attached to the part with role cad.", {"part": str})
    async def cad_brief(args):
        from .. import cadbrief
        return _txt(cadbrief.brief(store.load(), args["part"]))

    @tool("cad_build", "Native CAD: build a part's geometry from build123d code (Python; mm; define `result`; set density_g_cm3; declare `features` and `mates` {interface_id: feature}). Exports STEP/STL, measures volume/mass/bbox, checks them against the part's attrs (mass_budget_g, envelope_mm), mechanical interfaces (mates) and requirement attrs, attaches the STEP to the part and writes measured attrs. Start from cad_brief. Returns the build result or the Python error to fix.", {"part": str, "code": str})
    async def cad_build_tool(args):
        from .. import cad as CAD
        from ..store import Patch, Op
        m = store.load(); part = args["part"]
        if part not in m["parts"]: return _txt({"error": "no such part"})
        root = getattr(store, "root", None) or "."; res = CAD.build(args["code"], os.path.join(root, "cad"), part)
        if not res["ok"]: return _txt({"ok": False, "error": res["error"]})
        chk = CAD.checks(m, part, res); cid = "CAD-" + part; cur = m.get("cad_models", {}).get(cid)
        value = {"part": part, "code": args["code"], "name": m["parts"][part].get("name", ""), "status": "built" if all(c["ok"] for c in chk) else "built-with-findings", "built": time.strftime("%Y-%m-%d %H:%M"), "by": author, "volume_mm3": res["volume_mm3"], "mass_g": res["mass_g"], "bbox_mm": res["bbox_mm"], "files": res["files"], "checks": chk, "features": res.get("features", []), "error": ""}
        attrs = dict(m["parts"][part].get("attrs") or {}); attrs.update({"envelope_actual_mm": "×".join(f"{x:g}" for x in res["bbox_mm"]), "volume_mm3": res["volume_mm3"]})
        if res["mass_g"] is not None: attrs["mass_g_cad"] = res["mass_g"]
        ops = [Op(op="update" if cur else "add", kind="cad_models", id=cid, value=value), Op(op="update", kind="parts", id=part, value={"attrs": attrs})]
        pid = store.stage(Patch(ops=ops, author=author, rationale=f"Native CAD build of {part}: {res['bbox_mm']} mm, {res.get('mass_g')} g", sources=[])); store.approve(pid, approver=author)
        return _txt({"ok": True, "patch": pid, "volume_mm3": res["volume_mm3"], "mass_g": res["mass_g"], "bbox_mm": res["bbox_mm"], "checks": chk})

    @tool("eda_board", "Native EDA: the electrical architecture as a board — components from electrical parts, nets from electrical interface items (power rails, buses, signals), test points, checks (dangling nets, missing GND, MPN/AVL, EOL, DfT, ≥48 V safety standard, High-AP modes) and the board brief for a part. Fix findings by patching interface items and part attrs (mpn, package, test_points, ref).", {"part": str})
    async def eda_board(args):
        from .. import eda as EDA
        m = store.load(); nl = EDA.netlist(m); part = (args or {}).get("part") or None
        return _txt({"summary": {k: nl[k] for k in ("n_components", "n_nets", "n_pins")}, "components": {p: {"ref": c["ref"], "pins": [x["name"] for x in c["pins"]], "mpn": c["mpn"], "supplier": c["supplier"]} for p, c in nl["components"].items()}, "nets": {n: {"kind": v["kind"], "refs": sorted({q["ref"] for q in v["pins"]}), "external": v.get("external", [])} for n, v in nl["nets"].items()}, "checks": EDA.checks(m, nl), "brief": EDA.board_brief(m, nl, part)})

    @tool("dfx_review", "Design-for-X evaluation: x = manufacturing|assembly|testability|reliability|safety|maintainability|service|transportation|cost|environment|emc|security|usability|quality|supply_chain, or omit for the summary of all. Returns guideline items with automatic status (pass/partial/fail/n/a) or 'unknown' for manual items, measured values and evidence ids. Record verdicts with dfx_set (one call per item); if you put them in propose_patch instead, use kind dfx_reviews, id DFX-<x>, value {x, items: {<guideline id>: {status, evidence, note}}}.", {"x": str})
    async def dfx_review(args):
        from .. import dfx as DFX
        m = store.load(); x = (args or {}).get("x")
        return _txt(DFX.evaluate(m, x, getattr(store, "root", None)) if x else DFX.summary(m, getattr(store, "root", None)))

    @tool("rfq_package", "Procurement: the RFQ package for a buy part derived from the graph — attributes and bounds, interfaces it must mate, drawings/CAD, applicable requirements and regulations (food contact, RoHS, UL), quantities per build and annual volume, quality asks (PPAP/FAI, CoC, DoCs), commercial asks. Send it to suppliers; record their answers as quotes (propose_patch kind quotes: part, supplier, qty, unit_cost_usd, moq, lead_time_d, tooling_usd, valid_until, status requested|received|awarded).", {"part": str})
    async def rfq_package(args):
        from .. import business as B
        m = store.load(); r = B.rfq_package(m, args["part"]); return _txt(r or {"error": "no such part"})

    @tool("procurement_plan", "Procurement status for every buy part: supplier, quote status and best unit cost vs BOM cost, lead time against the first build that needs it (order-by date, LATE flag), MOQ vs build quantity, second source, critical flag (High-AP or NRND/EOL). Builds come from meta.business.builds {gate: units}.", {})
    async def procurement_plan(args):
        from .. import business as B
        return _txt({"rows": B.procurement(store.load())})

    @tool("trade_study", "Evaluate a trade study from the model: weighted decision matrix (scores 1–5 or raw values normalized by direction), ranking, Pugh view vs the datum, and sensitivity (flip weight per criterion; ±25 % weight and −1 leader score perturbations; robust yes/no). Omit id for the list with hygiene checks. To create or change a study use propose_patch on kind trades: {name, question, options[], criteria[], weights[], criteria_meta{crit:{direction:max|min, unit, moe, req, basis}}, raw{option:{crit:value}} or scores{option:{crit:1-5}}, evidence{option:{crit:[ids]}}, datum, affects[], elements[]}. Tie criteria to MoEs/requirements and cite tests, simulations, suppliers or notes as evidence; never score from opinion alone.", {"id": str})
    async def trade_study(args):
        m = store.load(); tid = args.get("id")
        if not tid: return _txt({"studies": TRADES.summary(m), "checks": TRADES.checks(m)})
        e = TRADES.evaluate(m, tid); return _txt(e or {"error": "no such trade study"})

    @tool("trade_decide", "Record the decision of a trade study (one of its options) with the rationale — mandatory when the decision differs from the scored leader. Applied immediately with your name; also create an arch_decisions record via propose_patch pointing at the trade.", {"id": str, "decision": str, "rationale": str})
    async def trade_decide(args):
        m = store.load(); t = m.get("trades", {}).get(args["id"])
        if not t: return _txt({"error": "no such trade study"})
        if args.get("decision") not in t["options"]: return _txt({"error": "decision must be one of " + ", ".join(t["options"])})
        p = Patch(ops=[Op(op="update", kind="trades", id=args["id"], value={"decision": args["decision"], "rationale": args.get("rationale", ""), "status": "decided", "decided_by": author, "date": time.strftime("%Y-%m-%d")})], author=author, rationale=f"{args['id']} decided: {args['decision']} — {args.get('rationale', '')}"[:200], sources=[args["id"]])
        pid = store.stage(p); store.approve(pid, approver=author)
        return _txt({"ok": True, "patch": pid})

    @tool("dfx_set", "Record a reviewed status for a DfX guideline item (manual items, or to override an automatic one with justification). status: pass|partial|fail|n/a. evidence: element ids. Applied immediately as a dfx_reviews patch with your name.", {"x": str, "item": str, "status": str, "evidence": list, "note": str})
    async def dfx_set(args):
        from ..store import Patch, Op
        m = store.load(); x = args["x"]; rid = "DFX-" + x; cur = m.get("dfx_reviews", {}).get(rid) or {"x": x, "items": {}}
        items = dict(cur.get("items") or {}); items[args["item"]] = {"status": args["status"], "evidence": args.get("evidence") or [], "note": args.get("note", ""), "by": author, "date": time.strftime("%Y-%m-%d")}
        p = Patch(ops=[Op(op="update" if rid in m.get("dfx_reviews", {}) else "add", kind="dfx_reviews", id=rid, value={"x": x, "items": items, "date": time.strftime("%Y-%m-%d"), "by": author})], author=author, rationale=f"DfX {x}: {args['item']} → {args['status']} — {args.get('note', '')}"[:200], sources=args.get("evidence") or [])
        pid = store.stage(p); store.approve(pid, approver=author)
        return _txt({"ok": True, "patch": pid})

    @tool("team_workload", "Per team: open work items, findings, pending handoffs in/out, owned parts, tests and process steps.", {})
    async def team_workload(args):
        return _txt(lifecycle.team_workload(store.load()))

    @tool("propose_patch", "Propose a change to the model. ops: list of {op: add|update|remove, kind, id, value}. The patch is validated (schema + references) and STAGED for human approval; it is not applied. Give a rationale and the sources (documents, tool outputs, requirement ids) the change is derived from. Returns validation issues, the resulting coverage delta, and the patch id.",
          {"ops": list, "rationale": str, "sources": list})
    async def propose_patch(args):
        m = store.load()
        try:
            ops = [Op(**o) for o in args["ops"]]
            patch = Patch(ops=ops, author=author, rationale=args["rationale"], sources=args.get("sources") or [])
            new, issues = store.check_patch(m, patch)
        except Exception as e:
            return _txt({"accepted": False, "error": str(e)})
        errs = [f"{i.where}: {i.msg}" for i in issues if i.level == "error"]
        if errs: return _txt({"accepted": False, "errors": errs[:20]})
        before, after = derive.coverage_report(m), derive.coverage_report(new)
        delta = {k: (len(before[k]) if hasattr(before[k], '__len__') else before[k], len(after[k]) if hasattr(after[k], '__len__') else after[k]) for k in before if k not in ("counts", "clean") and before[k] != after[k]}
        store.stage(patch)
        return _txt({"accepted": True, "patch_id": patch.id, "status": "staged", "warnings": [f"{i.where}: {i.msg}" for i in issues if i.level == "warning"][:10], "coverage_delta(before,after)": delta})

    @tool("withdraw_patch", "Withdraw (reject) a STAGED patch you proposed earlier, e.g. one you superseded with a corrected patch. Only staged patches can be withdrawn.", {"patch_id": str})
    async def withdraw_patch(args):
        try:
            p = store.get_patch(args["patch_id"])
            if p.status != "staged": return _txt({"ok": False, "error": f"patch is {p.status}"})
            store.reject(args["patch_id"]); return _txt({"ok": True, "withdrawn": args["patch_id"]})
        except Exception as e: return _txt({"ok": False, "error": str(e)})

    @tool("list_patches", "Staged / applied / rejected patches.", {"status": str})
    async def list_patches(args):
        return _txt([{"id": p.id, "status": p.status, "author": p.author, "rationale": p.rationale, "ops": len(p.ops)} for p in store.list_patches(args.get("status") or None)])

    @tool("provenance", "Applied patches that touched kind.id, newest first.", {"kind": str, "id": str})
    async def provenance(args):
        return _txt(store.provenance(args["kind"], args["id"]))

    @tool("read_document", "Read a source document (markdown, txt, csv, json) from the project's docs directory, optionally a character window.", {"name": str, "offset": int, "length": int})
    async def read_document(args):
        if not docs_dir: return _txt({"error": "no docs dir configured"})
        p = os.path.join(docs_dir, os.path.basename(args["name"]))
        if not os.path.exists(p): return _txt({"error": "not found", "available": sorted(os.listdir(docs_dir))})
        txt = open(p, errors="ignore").read(); o = args.get("offset") or 0; n = args.get("length") or 20000
        return _txt({"name": args["name"], "total_chars": len(txt), "text": txt[o:o + n]})

    @tool("list_documents", "List source documents available for ingestion.", {})
    async def list_documents(args):
        return _txt(sorted(os.listdir(docs_dir)) if docs_dir and os.path.isdir(docs_dir) else [])

    @tool("tool_pull", "Import from an engineering tool file via an adapter: kicad (netlist), cad-bom (CSV), step, alm (requirements CSV/JSON), test-results (CSV/JSON). Returns a STAGED patch id.", {"adapter": str, "path": str, "parent": str})
    async def tool_pull(args):
        cls = adapters.REGISTRY.get(args["adapter"])
        if not cls: return _txt({"error": "unknown adapter", "available": list(adapters.REGISTRY)})
        m = store.load()
        try:
            patch = cls().pull(m, args["path"], parent=args.get("parent") or None)
            new, issues = store.check_patch(m, patch); errs = [f"{i.where}: {i.msg}" for i in issues if i.level == "error"]
            if errs: return _txt({"accepted": False, "errors": errs[:20]})
            store.stage(patch); return _txt({"accepted": True, "patch_id": patch.id, "ops": len(patch.ops)})
        except Exception as e: return _txt({"error": str(e)})

    @tool("tool_push", "Export model content to an engineering tool format via an adapter: kicad (design constraints), cad-bom (requirements sheet), modelica (parameter record), alm (requirements CSV), test-results (test plan CSV).", {"adapter": str, "path": str})
    async def tool_push(args):
        cls = adapters.REGISTRY.get(args["adapter"])
        if not cls: return _txt({"error": "unknown adapter", "available": list(adapters.REGISTRY)})
        try: return _txt({"written": cls().push(store.load(), args["path"])})
        except Exception as e: return _txt({"error": str(e)})

    @tool("simulate_fmu", "Run an FMU and evaluate constraints. checks: {constraint_id: {output, op, limit}}", {"fmu": str, "stop_time": float, "inputs": dict, "checks": dict})
    async def simulate_fmu(args):
        res = adapters.FmuAdapter().evaluate(store.load(), fmu=args["fmu"], stop_time=args.get("stop_time") or 10.0, inputs=args.get("inputs") or {}, checks=args.get("checks") or {})
        return _txt(res)

    tools = [model_schema, model_summary, impact, budgets, check_requirement, scorecard, library_tool, gate_readiness, team_workload, read_model, list_gaps, fmea_candidates, derived_view, propose_patch, withdraw_patch, list_patches, provenance, read_document, list_documents, tool_pull, tool_push, simulate_fmu, cad_brief, cad_build_tool, eda_board, dfx_review, dfx_set, trade_study, trade_decide, rfq_package, procurement_plan]
    server = create_sdk_mcp_server(name="sethread", version="0.1.0", tools=tools)
    names = [f"mcp__sethread__{t.name}" for t in tools]
    return server, names
