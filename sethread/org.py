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
    {"id": "fracas", "name": "Field events / FRACAS", "kind": "app", "default": True},
    # Design for X — each a guideline set evaluated against the model (library/dfx); the organization chooses which apply
    {"id": "dfx:manufacturing", "name": "Design for Manufacturing (DfM)", "kind": "dfx", "default": True}, {"id": "dfx:assembly", "name": "Design for Assembly (DfA)", "kind": "dfx", "default": True},
    {"id": "dfx:testability", "name": "Design for Testability (DfT)", "kind": "dfx", "default": True}, {"id": "dfx:reliability", "name": "Design for Reliability (DfR)", "kind": "dfx", "default": True},
    {"id": "dfx:safety", "name": "Design for Safety (DfS)", "kind": "dfx", "default": True}, {"id": "dfx:maintainability", "name": "Design for Maintainability (DfMt)", "kind": "dfx", "default": True},
    {"id": "dfx:service", "name": "Design for Service (DfSv)", "kind": "dfx", "default": True}, {"id": "dfx:transportation", "name": "Design for Transportation & Packaging", "kind": "dfx", "default": True},
    {"id": "dfx:cost", "name": "Design to Cost (DtC)", "kind": "dfx", "default": True}, {"id": "dfx:environment", "name": "Design for Environment & Sustainability (DfE)", "kind": "dfx", "default": True},
    {"id": "dfx:emc", "name": "Design for EMC & Electrical Compliance", "kind": "dfx", "default": True}, {"id": "dfx:security", "name": "Design for Security (DfSec)", "kind": "dfx", "default": True},
    {"id": "dfx:usability", "name": "Design for Usability & Ergonomics", "kind": "dfx", "default": True}, {"id": "dfx:quality", "name": "Design for Quality (DfQ)", "kind": "dfx", "default": True},
    {"id": "dfx:supply_chain", "name": "Design for Supply Chain", "kind": "dfx", "default": True}, {"id": "cad", "name": "Code-CAD generation & viewer", "kind": "app", "default": False, "status": "planned"},
    {"id": "testruns", "name": "TestRUNS (test execution) → results intake", "kind": "integration", "default": False, "config": {"url": "", "token": ""}},
    {"id": "kanalysis", "name": "Kanalysis (time-series analytics)", "kind": "integration", "default": False, "config": {"url": ""}},
    {"id": "oslc_rm", "name": "IBM DOORS / Jama via OSLC", "kind": "integration", "default": False, "config": {"url": "", "auth": "basic"}},
    {"id": "plm", "name": "PLM / PDM (Windchill, Teamcenter, Arena, Duro)", "kind": "integration", "default": False, "config": {"url": ""}, "status": "planned"},
    # authoring copilots — discipline agents that live inside the authoring tool; Launch sends the brief, they return the artifact
    {"id": "cad_copilot", "name": "CAD copilot (MecAgent, Zoo, Studio) ← CAD brief from the graph, native CAD/STEP back as attachment", "kind": "integration", "default": True, "config": {}},
    {"id": "harness", "name": "Wire harness tool (HarnessHive via MCP) ← wire list from the interfaces, harness + BOM + formboard back", "kind": "integration", "default": True, "config": {"mcp_url": ""}},
    {"id": "eda_copilot", "name": "Electronics copilot (CopperPilot, Quilter, Flux) ← board brief from the graph, schematic/BOM back", "kind": "integration", "default": True, "config": {}, "status": "planned"},
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
    # process variants: a multi-product organization keeps several (platform, derivative, accessory…); `process` is the default one
    if not d.get("processes"): d["processes"] = [{"id": "default", **d["process"]}]
    if not any(x.get("id") == d.get("default_process", "default") for x in d["processes"]): d["default_process"] = d["processes"][0]["id"]
    d.setdefault("default_process", "default")
    d["process"] = next(x for x in d["processes"] if x["id"] == d["default_process"])
    return d

def process_variant(org: dict, vid: str | None) -> dict:
    return next((x for x in org.get("processes", []) if x.get("id") == vid), None) or org["process"]

def save(data_root: str, org: dict) -> dict:
    os.makedirs(os.path.dirname(path(data_root)), exist_ok=True)
    keep = {k: org.get(k) for k in ("name", "created", "processes", "default_process", "teams", "members", "tools", "policy")}
    if not keep.get("processes"): keep["processes"] = [{"id": "default", **(org.get("process") or {})}]
    keep["process"] = next((x for x in keep["processes"] if x["id"] == keep.get("default_process")), keep["processes"][0])
    yaml.safe_dump(keep, open(path(data_root), "w"), sort_keys=False, allow_unicode=True); return keep

def apply_ops(org: dict, m: dict, start_date: str, variant: str | None = None, only: set | None = None) -> list[dict]:
    """patch ops that install the organization's teams (with members by email) and process into a project.
    `only` restricts to a set of element ids (re-sync of chosen items); `variant` picks a process variant."""
    ops = []
    members_of = {}
    for u in org.get("members", []):
        for t in u.get("teams", []): members_of.setdefault(t, []).append(u["email"])
    for t in org.get("teams", []):
        v = {"name": t["name"], "kind": t.get("kind", "functional"), "focus": t.get("focus", ""), "discipline": t.get("discipline", ""), "lead": t.get("lead", ""), "members": sorted(set(members_of.get(t["id"], [])) | set(m.get("teams", {}).get(t["id"], {}).get("members", [])))}
        if t.get("kind") == "subsystem": v.update(parts=[p for p in t.get("parts", []) if p in m["parts"]], lcs=[l for l in t.get("lcs", []) if l in m["logical_components"]], moes=[x for x in t.get("moes", []) if x in m["moes"]])
        ops.append({"op": "update" if t["id"] in m.get("teams", {}) else "add", "kind": "teams", "id": t["id"], "value": v})
    pr = process_variant(org, variant) or {}
    if pr.get("phases"): ops += PDP.apply_ops(m, {"phases": pr["phases"], "gates": pr["gates"], "deliverables": pr["deliverables"]}, start_date, int(pr.get("spacing_days", 45)))
    if only is not None: ops = [o for o in ops if o["id"] in only]
    return ops

# ---- tailoring: how a project's process differs from the organization's variant it was taken from
_FIELDS = {"phases": ("name", "order", "stage", "gate"), "gates": ("exit",), "deliverables": ("name", "gate", "team", "team_kind", "focus", "check", "required")}
def tailoring(org: dict, m: dict) -> dict:
    src = (m.get("program") or {}).get("pdp_source") or {}
    pr = process_variant(org, src.get("variant"))
    out = {"variant": pr.get("id", "default"), "variant_name": pr.get("name", ""), "applied": src.get("applied"), "items": [], "removed": [], "summary": {}}
    for kind in ("phases", "gates", "deliverables"):
        org_items = {x["id"]: x for x in pr.get(kind, [])}; proj = m.get(kind, {})
        for i, v in proj.items():
            if kind == "gates" and i not in org_items and not any(p.get("gate") == i for p in m.get("phases", {}).values()) and v.get("phase") is None:
                continue   # project gates outside the process (e.g. engineering builds) are not tailoring
            if i not in org_items: st = "added"
            else:
                o = org_items[i]
                norm = lambda d, f: (d.get(f, True) if f == "required" else (d.get(f) if d.get(f) not in ("", None, {}) else None))
                diff = [f for f in _FIELDS[kind] if norm(v, f) != norm(o, f)]
                st = "tailored" if diff else "inherited"
            if kind == "deliverables" and v.get("waived"): st = "waived"
            out["items"].append({"kind": kind, "id": i, "name": v.get("name") or v.get("exit", "")[:60], "status": st, "diff": diff if st == "tailored" else [], "waived": v.get("waived") if st == "waived" else None, "org": org_items.get(i)})
        for i, o in org_items.items():
            if i not in proj: out["removed"].append({"kind": kind, "id": i, "name": o.get("name") or o.get("exit", "")[:60]})
    for st in ("inherited", "tailored", "added", "waived"): out["summary"][st] = len([x for x in out["items"] if x["status"] == st])
    out["summary"]["removed"] = len(out["removed"])
    return out

def member_teams(org: dict, email: str) -> list[str]:
    e = (email or "").lower()
    return [t for u in org.get("members", []) if u.get("email", "").lower() == e for t in u.get("teams", [])]

def role_of(org: dict, email: str) -> str:
    e = (email or "").lower()
    for u in org.get("members", []):
        if u.get("email", "").lower() == e: return u.get("role", "engineer")
    return "admin" if not org.get("members") else "viewer"   # first users before anyone is listed are admins
