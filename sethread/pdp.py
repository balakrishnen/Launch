"""Company product-development process (PDP): phases closed by gates, deliverables owed per team at each gate, each deliverable
with a check the model evaluates. Templates under library/pdp/*.yaml (stage-gate, EVT/DVT/PVT, APQP, ISO 15288); a company tailors
its own. The matrix (gate × team → deliverables with status) is what every team sees as "what we owe", and gate readiness folds it in."""
from __future__ import annotations
import os, glob, yaml
from . import derive as D
from .schema import KINDS

HERE = os.path.join(os.path.dirname(__file__), "library", "pdp")

def templates(project_root: str | None = None) -> list[dict]:
    out = []
    for p in sorted(glob.glob(os.path.join(HERE, "*.yaml"))) + (sorted(glob.glob(os.path.join(project_root, ".sethread", "pdp", "*.yaml"))) if project_root else []):
        t = yaml.safe_load(open(p)); t["id"] = os.path.basename(p)[:-5]; out.append({"id": t["id"], "name": t["name"], "description": t.get("description", ""), "phases": len(t["phases"]), "gates": len(t["gates"]), "deliverables": len(t["deliverables"])})
    return out

def template(tid: str, project_root: str | None = None) -> dict | None:
    for d in ([os.path.join(project_root, ".sethread", "pdp")] if project_root else []) + [HERE]:
        p = os.path.join(d, tid + ".yaml")
        if os.path.exists(p): return yaml.safe_load(open(p))
    return None

def apply_ops(m: dict, t: dict, start_date: str, spacing_days: int = 45) -> list[dict]:
    """patch ops that install a template: phases, gates (keeping dates/status of gates that already exist), deliverables."""
    import datetime as dt
    ops = []
    for ph in t["phases"]:
        v = {k: ph[k] for k in ("name", "order")}; v.update(stage=ph.get("stage", ""), gate=ph.get("gate"), description=ph.get("description", ""))
        ops.append({"op": "update" if ph["id"] in m.get("phases", {}) else "add", "kind": "phases", "id": ph["id"], "value": v})
    d0 = dt.date.fromisoformat(start_date)
    for i, g in enumerate(t["gates"]):
        ph = next((p["id"] for p in t["phases"] if p.get("gate") == g["id"]), None)
        if g["id"] in m["gates"]: ops.append({"op": "update", "kind": "gates", "id": g["id"], "value": {"exit": g["exit"], "phase": ph, "stage": next((p.get("stage", "") for p in t["phases"] if p["id"] == ph), "")}})
        else: ops.append({"op": "add", "kind": "gates", "id": g["id"], "value": {"date": (d0 + dt.timedelta(days=spacing_days * (i + 1))).isoformat(), "exit": g["exit"], "status": "planned", "phase": ph, "stage": next((p.get("stage", "") for p in t["phases"] if p["id"] == ph), "")}})
    for d in t["deliverables"]:
        v = {"name": d["name"], "gate": d["gate"], "team": d.get("team"), "team_kind": d.get("team_kind", ""), "focus": d.get("focus", ""), "check": d.get("check", {}), "required": d.get("required", True), "description": d.get("description", "")}
        ops.append({"op": "update" if d["id"] in m.get("deliverables", {}) else "add", "kind": "deliverables", "id": d["id"], "value": v})
    return ops

# ---- deliverable checks
def _scope(m, tv):
    from .lifecycle import subsystem_scope
    return subsystem_scope(m, tv)

def evaluate(m: dict, d: dict, team_id: str | None, tv: dict | None, rep: dict) -> dict:
    """status: done | partial | missing | n/a, with a measured value and a link to the evidence"""
    c = d.get("check") or {}; typ = c.get("type")
    try:
        if typ == "coverage":
            key = c["key"]; v = rep.get(key); n = len(v) if isinstance(v, list) else (v or 0)
            mc = c.get("min_count")
            if mc and len(m.get(mc["kind"], {})) < mc["n"]: return {"status": "missing", "measured": f"no {mc['kind']}", "link": f"/collection/{mc['kind']}"}
            return {"status": "done" if n <= c.get("max", 0) else "partial", "measured": f"{n} open", "link": "/gaps"}
        if typ == "scope":
            if not tv or tv.get("kind") != "subsystem": return {"status": "n/a", "measured": "", "link": ""}
            s = _scope(m, tv); key = c["key"]
            if key == "boundary_items":
                ok = bool(s["interfaces_boundary"]) and all(m["interfaces"][i].get("items") for i in s["interfaces_boundary"])
                return {"status": "done" if ok else ("partial" if s["interfaces_boundary"] else "missing"), "measured": f"{len(s['interfaces_boundary'])} boundary interfaces", "link": f"/team/{team_id}"}
            if key == "req_coverage":
                v = s["verification"]; return {"status": "done" if v["total"] and v["covered"] == v["total"] else ("partial" if v["covered"] else "missing"), "measured": f"{v['covered']}/{v['total']}", "link": f"/team/{team_id}"}
            if key == "fmea_complete":
                un = [u for u in rep.get("unassessed_candidates", []) if (u.get("element") if isinstance(u, dict) else u) in set(s["parts"]) | set(s["functions"])]
                return {"status": "done" if s["fmea"] and not un else ("partial" if s["fmea"] else "missing"), "measured": f"{len(s['fmea'])} assessed · {len(un)} unassessed", "link": "/form/dfmea"}
            if key == "tests_passed":
                v = s["verification"]; return {"status": "done" if v["tests"] and v["passed"] == v["tests"] else ("partial" if v["passed"] else "missing"), "measured": f"{v['passed']}/{v['tests']} passed", "link": "/runs"}
        if typ == "attachment":
            roles = set(c.get("roles", [])); parts = set(_scope(m, tv)["parts"]) if tv and tv.get("kind") == "subsystem" else {p for p, v in m["parts"].items() if v.get("owner_team") == team_id}
            att = [a for a in m.get("attachments", {}).values() if a["element"] in parts and a["role"] in roles]
            return {"status": "done" if att and len({a["element"] for a in att}) >= max(1, len(parts) // 3) else ("partial" if att else "missing"), "measured": f"{len(att)} file(s) on {len({a['element'] for a in att})} of {len(parts)} parts", "link": f"/team/{team_id}" if team_id else "/collection/parts"}
        if typ == "note":
            ns = [n for n, v in m.get("notes", {}).items() if v.get("kind") == c.get("kind") and (not team_id or v.get("owner_team") in (team_id, None))]
            fin = [n for n in ns if m["notes"][n].get("status") == c.get("status", "final")]
            return {"status": "done" if fin else ("partial" if ns else "missing"), "measured": f"{len(fin)} final / {len(ns)}", "link": "/notes"}
        if typ == "collection":
            n = len(m.get(c["kind"], {})); return {"status": "done" if n >= c.get("n", 1) else "missing", "measured": str(n), "link": f"/collection/{c['kind']}"}
        if typ == "tests_passed_share":
            tests = list(m["tests"].values()); passed = sum(1 for t in tests if t.get("status") == "passed"); share = passed / len(tests) if tests else 0
            return {"status": "done" if tests and share >= c.get("min", 1.0) else ("partial" if passed else "missing"), "measured": f"{passed}/{len(tests)}", "link": "/runs"}
    except Exception as e: return {"status": "error", "measured": str(e)[:80], "link": ""}
    return {"status": "missing", "measured": "no check", "link": ""}

def owes(d: dict, tid: str, tv: dict) -> bool:
    if d.get("team"): return d["team"] == tid
    if d.get("team_kind"): return (tv.get("kind") or "functional") == d["team_kind"]
    if d.get("focus"): return (tv.get("focus") or tv.get("discipline")) == d["focus"]
    return False

def matrix(m: dict) -> dict:
    """gate × team → deliverables with status; plus per-gate and per-team rollups."""
    rep = D.coverage_report(m); teams = m.get("teams", {}); gates = sorted(m["gates"].items(), key=lambda kv: kv[1]["date"])
    phases = sorted(m.get("phases", {}).items(), key=lambda kv: kv[1]["order"])
    cells = {}; per_gate = {}; per_team = {}; unowned = []
    for did, d in m.get("deliverables", {}).items():
        owners = [t for t, tv in teams.items() if owes(d, t, tv)]
        if not owners:
            ev = evaluate(m, d, None, None, rep); unowned.append({"id": did, **d, **ev}); per_gate.setdefault(d["gate"], []).append(ev["status"]); continue
        for t in owners:
            ev = evaluate(m, d, t, teams[t], rep)
            cells.setdefault(d["gate"], {}).setdefault(t, []).append({"id": did, **d, **ev})
            per_gate.setdefault(d["gate"], []).append(ev["status"]); per_team.setdefault(t, []).append(ev["status"])
    roll = lambda xs: {"done": xs.count("done"), "partial": xs.count("partial"), "missing": xs.count("missing"), "total": len([x for x in xs if x != "n/a"])}
    return {"phases": [{"id": p, **v} for p, v in phases], "gates": [{"id": g, **v} for g, v in gates], "teams": {t: {"name": v["name"], "kind": v.get("kind", "functional"), "focus": v.get("focus", "")} for t, v in teams.items()},
            "cells": cells, "unowned": unowned, "per_gate": {g: roll(xs) for g, xs in per_gate.items()}, "per_team": {t: roll(xs) for t, xs in per_team.items()},
            "next_gate": next((g for g, v in gates if v.get("status") != "passed"), None)}

def team_deliverables(m: dict, tid: str) -> list[dict]:
    mx = matrix(m); out = []
    for g in mx["gates"]:
        for d in mx["cells"].get(g["id"], {}).get(tid, []): out.append({**d, "gate_date": g["date"], "gate_status": g.get("status")})
    return out
