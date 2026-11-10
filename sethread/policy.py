"""The agent harness as a product surface. A project's harness = the roles it runs, the tools they may use, the skills
(library knowledge) they consult, the watchers that run after every change, and the POLICY that decides what an agent may
apply on its own, what needs a reviewer, and who reviews what. Policy lives in <root>/.sethread/harness.yaml and is
editable in the app. Also the agile-execution views (board, timeline, trend) since they are what the harness drives."""
from __future__ import annotations
import os, time, yaml
from . import derive as D
from .agents import roles as R
from .schema import KINDS, LIFECYCLE

DEFAULT_POLICY = {
    "auto_apply": {           # agent patches that apply without a human when ALL ops are in these kinds and under the size limit
        "kinds": ["fm_assessments", "work_items", "notes", "tables"], "max_ops": 25, "min_score": 85},
    "require_review": {       # kinds whose changes always need a named reviewer team (by owner_team / team of the element, else fallback)
        "kinds": ["requirements", "interfaces", "gates", "parts"], "fallback_team": None},
    "reviewers": {},          # kind -> team id
    "agents": {"enabled": list(R.ORDER), "max_turns": 60, "web": True, "shell": False},
    "watchers": ["scorecard", "gaps", "staleness", "gate_readiness"],
    "skills": ["regulations", "failure_modes", "test_methods"],
}

def policy_path(root): return os.path.join(root, ".sethread", "harness.yaml")
def load_policy(root) -> dict:
    p = policy_path(root)
    pol = yaml.safe_load(open(p)) if os.path.exists(p) else {}
    out = {k: (dict(v, **(pol.get(k) or {})) if isinstance(v, dict) else pol.get(k, v)) for k, v in DEFAULT_POLICY.items()}
    return out
def save_policy(root, pol: dict):
    os.makedirs(os.path.dirname(policy_path(root)), exist_ok=True)
    yaml.safe_dump(pol, open(policy_path(root), "w"), sort_keys=False, allow_unicode=True)

def auto_approves(pol: dict, patch) -> bool:
    a = pol.get("auto_apply", {}); kinds = set(a.get("kinds", []))
    if not kinds or len(patch.ops) > a.get("max_ops", 25): return False
    if not all(o.kind in kinds for o in patch.ops): return False
    if any(o.kind in set(pol.get("require_review", {}).get("kinds", [])) for o in patch.ops): return False
    return True

def reviewer_for(pol: dict, m: dict, patch) -> str | None:
    """who should review: explicit kind→team mapping, else owner_team/team of the touched elements, else fallback."""
    rv = pol.get("reviewers", {})
    for o in patch.ops:
        if o.kind in rv: return rv[o.kind]
        el = m.get(o.kind, {}).get(o.id) or (o.value or {})
        t = el.get("owner_team") or el.get("team")
        if t: return t
    return pol.get("require_review", {}).get("fallback_team")

def describe(S) -> dict:
    from .library import load
    pol = load_policy(S.root); lib = {}
    for k in ("regulations", "failure_modes", "test_methods"):
        try: v = load(k, S.root); lib[k] = len(v) if hasattr(v, "__len__") else 0
        except Exception: lib[k] = 0
    roles = [{"id": k, "title": v["title"], "kinds": v.get("kinds", []), "enabled": k in pol["agents"]["enabled"]} for k, v in R.ROLES.items()]
    tools = sorted(n.replace("mcp__sethread__", "model.") for n in S.names)
    watchers = [{"id": "scorecard", "what": "INCOSE GtWR scorecard after every applied patch; delta shown in the conversation"}, {"id": "gaps", "what": "trace gaps as tasks with one-click agent actions"},
                {"id": "staleness", "what": "verification links whose requirement changed after the last result"}, {"id": "gate_readiness", "what": "exit criteria of the next gate re-measured"}]
    return {"policy": pol, "roles": roles, "tools": tools, "skills": [{"id": k, "entries": n} for k, n in lib.items()], "watchers": [w for w in watchers if w["id"] in pol["watchers"]],
            "syscall": "propose_patch → staged → (policy auto-apply | reviewer approves) → applied with provenance", "memory": "graph memory: record, neighbourhood, decisions, comments, notes, failure modes, results, earlier conversations — recalled per message"}

# ---- agile execution views
COLS = ["open", "in_progress", "blocked", "review", "done"]
def board(m: dict) -> dict:
    cols = {c: [] for c in COLS}
    for w, v in m.get("work_items", {}).items():
        st = v.get("status", "open"); st = st if st in cols else ("done" if st in ("closed", "complete") else "open")
        cols[st].append({"id": w, **v, "overdue": bool(v.get("due")) and v["due"] < time.strftime("%Y-%m-%d") and st != "done"})
    for c in cols: cols[c].sort(key=lambda x: (x.get("priority", "P2"), x.get("due") or "9999"))
    gates = sorted(({"id": g, **v} for g, v in m["gates"].items()), key=lambda g: g["date"])
    teams = {t: v["name"] for t, v in m.get("teams", {}).items()}
    return {"columns": COLS, "items": cols, "gates": gates, "teams": teams, "findings_open": [{"id": f, **v} for f, v in m.get("findings", {}).items() if v["status"] != "closed"],
            "handoffs_pending": [{"id": h, **v} for h, v in m.get("handoffs", {}).items() if v["status"] == "pending"]}

def timeline(m: dict) -> dict:
    rows = []
    for g, v in m["gates"].items(): rows.append({"id": g, "lane": "Gates", "label": g, "start": v["date"], "end": v["date"], "kind": "gates", "status": v.get("status", "planned"), "stage": v.get("stage", "")})
    for h, v in m.get("handoffs", {}).items():
        if v.get("due"): rows.append({"id": h, "lane": f"{m['teams'].get(v['from_team'], {}).get('name', v['from_team'])} → {m['teams'].get(v['to_team'], {}).get('name', v['to_team'])}", "label": v["what"][:60], "start": v.get("due"), "end": v.get("due"), "kind": "handoffs", "status": v.get("status")})
    for w, v in m.get("work_items", {}).items():
        if v.get("due"): rows.append({"id": w, "lane": m["teams"].get(v.get("team"), {}).get("name", v.get("team") or "Unassigned"), "label": v["title"][:60], "start": v.get("start") or v.get("due"), "end": v["due"], "kind": "work_items", "status": v.get("status")})
    for r, v in m.get("test_runs", {}).items(): rows.append({"id": r, "lane": "Test results", "label": f"{v['test']} {v['result']}", "start": v["date"], "end": v["date"], "kind": "test_runs", "status": v["result"]})
    for lane in m.get("program", {}).get("lanes", []) or []:
        if lane.get("start") and lane.get("end"): rows.append({"id": lane["name"], "lane": "Program", "label": lane["name"], "start": lane["start"], "end": lane["end"], "kind": "program", "status": ""})
    rows = [r for r in rows if r["start"]]
    rows.sort(key=lambda r: (r["lane"], r["start"]))
    return {"rows": rows, "today": time.strftime("%Y-%m-%d"), "stage": (m.get("program") or {}).get("stage") or ""}

def trend(store, points: int = 12) -> dict:
    """coverage, scorecard-ish counts and open findings over revisions — the burndown of the thread (DB store only)."""
    out = []
    try:
        rev = store.rev(); step = max(1, rev // points)
        for r in list(range(1, rev + 1, step))[-points:] + ([rev] if rev % step else []):
            m = store.load(r); rep = D.coverage_report(m)
            open_gaps = sum(len(v) for k, v in rep.items() if isinstance(v, list) and k not in ("counts",))
            tests = list(m["tests"].values()); passed = sum(1 for t in tests if t.get("status") == "passed")
            out.append({"rev": r, "elements": sum(len(m[k]) for k in KINDS), "requirements": len(m["requirements"]), "open_gaps": open_gaps, "high_ap": rep["counts"].get("high_ap", 0), "unassessed": len(rep.get("unassessed_candidates", [])),
                        "tests_passed": passed, "tests": len(tests), "open_findings": len([f for f in m.get("findings", {}).values() if f["status"] != "closed"]), "open_work": len([w for w in m.get("work_items", {}).values() if w["status"] != "done"])})
    except Exception as e: return {"supported": False, "note": str(e), "points": []}
    return {"supported": True, "points": out}
