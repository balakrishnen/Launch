"""Organization configuration — what a company defines once and every project inherits: its product-development process
(phases, gates, deliverables), its team catalog (subsystem and functional teams, kinds, focus), its members (people, roles,
team membership), the tools it uses (Launch apps and external integrations) and harness policy defaults.
Stored per tenant at <data_root>/.org/org.yaml; applied to a project as one reviewable patch (teams + phases + gates + deliverables)."""
from __future__ import annotations
import os, time, yaml
from . import pdp as PDP
from .schema import TEAM_FOCUS

TOOLS = [  # the tool catalog: Launch apps (built in) and integrations (drivers)
    {"id": "requirements", "name": "Requirements & specs", "kind": "app", "default": True}, {"id": "architecture", "name": "Architecture (N², ICD, SysML v2)", "kind": "app", "default": True},
    {"id": "dfmea", "name": "DFMEA / hazards / FTA", "kind": "app", "default": True}, {"id": "verification", "name": "DVP&R / VCRM / test results", "kind": "app", "default": True},
    {"id": "manufacturing", "name": "Process flow / PFMEA / control plan", "kind": "app", "default": True}, {"id": "sourcing", "name": "AVL / suppliers / make-buy", "kind": "app", "default": True},
    {"id": "program", "name": "Gates, board, timeline, deliverables", "kind": "app", "default": True}, {"id": "office", "name": "Tables, notes, import", "kind": "app", "default": True},
    {"id": "fracas", "name": "Field events / FRACAS", "kind": "app", "default": True}, {"id": "cad", "name": "Code-CAD generation & viewer", "kind": "app", "default": False, "status": "planned"},
    {"id": "testruns", "name": "TestRUNS (test execution) → results intake", "kind": "integration", "default": False, "config": {"url": "", "token": ""}},
    {"id": "kanalysis", "name": "Kanalysis (time-series analytics)", "kind": "integration", "default": False, "config": {"url": ""}},
    {"id": "oslc_rm", "name": "IBM DOORS / Jama via OSLC", "kind": "integration", "default": False, "config": {"url": "", "auth": "basic"}},
    {"id": "plm", "name": "PLM / PDM (Windchill, Teamcenter, Arena, Duro)", "kind": "integration", "default": False, "config": {"url": ""}, "status": "planned"},
    {"id": "git", "name": "Git (firmware / software)", "kind": "integration", "default": False, "config": {"url": ""}, "status": "planned"},
    {"id": "jira", "name": "Jira / Asana (work sync)", "kind": "integration", "default": False, "config": {"url": ""}, "status": "planned"},
    {"id": "sso", "name": "SSO / SCIM (identity)", "kind": "integration", "default": False, "config": {"idp": ""}, "status": "planned"},
]
ROLES = ["admin", "program_manager", "engineer", "reviewer", "viewer"]

def path(data_root): return os.path.join(data_root, ".org", "org.yaml")

def default(tenant: str) -> dict:
    t = PDP.template("stage_gate") or {"phases": [], "gates": [], "deliverables": []}
    return {"name": tenant, "created": time.time(), "process": {"template": "stage_gate", "name": t.get("name", ""), "phases": t["phases"], "gates": t["gates"], "deliverables": t["deliverables"], "spacing_days": 45},
            "teams": [{"id": "TM-SE", "name": "Systems engineering", "kind": "functional", "focus": "systems"}, {"id": "TM-REL", "name": "Reliability", "kind": "functional", "focus": "reliability"},
                      {"id": "TM-QA", "name": "Quality & compliance", "kind": "functional", "focus": "quality"}, {"id": "TM-TEST", "name": "Test", "kind": "functional", "focus": "test"},
                      {"id": "TM-MFG", "name": "Manufacturing", "kind": "functional", "focus": "manufacturing"}, {"id": "TM-SC", "name": "Supply chain", "kind": "functional", "focus": "sourcing"}, {"id": "TM-PM", "name": "Program", "kind": "functional", "focus": "program"}],
            "members": [], "tools": [{"id": x["id"], "enabled": x["default"], "config": x.get("config", {})} for x in TOOLS],
            "policy": {"auto_apply_kinds": ["fm_assessments", "work_items", "notes", "tables"], "require_review_kinds": ["requirements", "interfaces", "gates", "parts"]}, "focus_options": TEAM_FOCUS}

def load(data_root: str, tenant: str) -> dict:
    p = path(data_root)
    if os.path.exists(p): o = yaml.safe_load(open(p)) or {}
    else: o = {}
    d = default(tenant); d.update({k: v for k, v in o.items() if v is not None}); d["focus_options"] = TEAM_FOCUS; d["tool_catalog"] = TOOLS; d["roles"] = ROLES
    return d

def save(data_root: str, org: dict) -> dict:
    os.makedirs(os.path.dirname(path(data_root)), exist_ok=True)
    keep = {k: org.get(k) for k in ("name", "created", "process", "teams", "members", "tools", "policy")}
    yaml.safe_dump(keep, open(path(data_root), "w"), sort_keys=False, allow_unicode=True); return keep

def apply_ops(org: dict, m: dict, start_date: str) -> list[dict]:
    """patch ops that install the organization's teams (with members by email) and process into a project"""
    ops = []
    members_of = {}
    for u in org.get("members", []):
        for t in u.get("teams", []): members_of.setdefault(t, []).append(u["email"])
    for t in org.get("teams", []):
        v = {"name": t["name"], "kind": t.get("kind", "functional"), "focus": t.get("focus", ""), "discipline": t.get("discipline", ""), "lead": t.get("lead", ""), "members": sorted(set(members_of.get(t["id"], [])) | set(m.get("teams", {}).get(t["id"], {}).get("members", [])))}
        if t.get("kind") == "subsystem": v.update(parts=[p for p in t.get("parts", []) if p in m["parts"]], lcs=[l for l in t.get("lcs", []) if l in m["logical_components"]], moes=[x for x in t.get("moes", []) if x in m["moes"]])
        ops.append({"op": "update" if t["id"] in m.get("teams", {}) else "add", "kind": "teams", "id": t["id"], "value": v})
    pr = org.get("process") or {}
    if pr.get("phases"): ops += PDP.apply_ops(m, {"phases": pr["phases"], "gates": pr["gates"], "deliverables": pr["deliverables"]}, start_date, int(pr.get("spacing_days", 45)))
    return ops

def member_teams(org: dict, email: str) -> list[str]:
    e = (email or "").lower()
    return [t for u in org.get("members", []) if u.get("email", "").lower() == e for t in u.get("teams", [])]

def role_of(org: dict, email: str) -> str:
    e = (email or "").lower()
    for u in org.get("members", []):
        if u.get("email", "").lower() == e: return u.get("role", "engineer")
    return "admin" if not org.get("members") else "viewer"   # first users before anyone is listed are admins
