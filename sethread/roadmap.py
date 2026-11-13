"""Platform roadmap — the superadmin's list of what Launch itself should do next, kept per tenant at <data_root>/.org/roadmap.yaml.
Not product work (that lives in the projects' graphs): this is the backlog of the platform, seeded with what the build sessions
parked, and edited under Settings › Roadmap by organization admins."""
from __future__ import annotations
import os, time, yaml

STATUSES = ["idea", "decision needed", "planned", "in progress", "done", "dropped"]
HORIZONS = ["now", "next", "later"]
AREAS = ["model", "engineering", "quality", "supply chain", "manufacturing", "program", "go-to-market", "integrations", "agents & skills", "platform", "ui", "ops"]

SEED = [
    dict(id="RM-01", title="Simulation brief + record_simulation (closed-loop FEA/CFD with the CAD-side agent)", area="integrations", horizon="next", status="planned", priority=1,
         notes="Launch issues the brief (loads from interfaces, targets from requirements/CDAs, mass budget, material); a Fusion/Onshape agent runs the loop as an MCP client and posts margins back as a simulations row feeding CDAs and TRL. Add a 'design-loop brief' skill.", source="Gemini 4 Carbon / Fusion FEA loop post, 2026-11-12"),
    dict(id="RM-02", title="Simulation-in-the-loop for trade studies", area="engineering", horizon="next", status="planned", priority=2,
         notes="Trade criteria scored from simulation and test-run evidence instead of hand-entered numbers; sensitivity re-runs when evidence changes.", source="trade-study session"),
    dict(id="RM-03", title="TestRUNS / Kanalysis connector", area="integrations", horizon="now", status="planned", priority=1,
         notes="A test result in TestRUNS closes the requirement in Launch (record_test_run over MCP); Kanalysis reports attach as evidence. Twinmo's own products first.", source="roadmap"),
    dict(id="RM-04", title="Hazard analysis: ISO 14971 / HARA views", area="quality", horizon="next", status="idea", priority=2,
         notes="Hazards → hazardous situations → harms with severity/probability, risk controls traced to requirements and tests; sits next to DFMEA.", source="claude-for-manufacturing review"),
    dict(id="RM-05", title="Controlled documents and e-signature (DHF / release records)", area="quality", horizon="later", status="idea", priority=3,
         notes="Document control with revision, approvers, signature meaning; needed for regulated products and for ECO release records.", source="claude-for-manufacturing review"),
    dict(id="RM-06", title="OSLC / ReqIF import-export (Jama, DOORS, Polarion)", area="integrations", horizon="later", status="idea", priority=3,
         notes="Round-trip requirements with incumbent tools so Launch can enter companies that already have one.", source="SE job-description research"),
    dict(id="RM-07", title="Product variants and platform derivatives", area="model", horizon="later", status="idea", priority=3,
         notes="Variant points in the graph (parts, requirements, markets) and a derivative project that inherits a platform model.", source="SE job-description research"),
    dict(id="RM-08", title="Model Hardware Standard alignment", area="model", horizon="later", status="idea", priority=4,
         notes="Map Launch collections to the Model Hardware Standard vocabulary where it exists so exports and partner tools line up.", source="claude-for-manufacturing review"),
    dict(id="RM-09", title="Twinmo brand colors in the UI tokens", area="ui", horizon="now", status="decision needed", priority=2,
         notes="Brand set is wired as --brand-* swatches only (chrome, not charts — the set failed the dataviz palette check). Need the official hex values.", source="UI session"),
    dict(id="RM-10", title="Make appliance_npi the organization default process?", area="program", horizon="now", status="decision needed", priority=2,
         notes="Examples carry their own PDP; the org default is still the generic template. Decide whether consumer-appliance NPI becomes the default for new orgs.", source="BrewMaster session"),
    dict(id="RM-11", title="Vendor APIs behind the CAD/EDA/PLM stubs", area="integrations", horizon="later", status="idea", priority=3,
         notes="Onshape, Fusion, Altium 365, Windchill; plus a KiCad/FreeCAD MCP pair for the open-source stack.", source="roadmap"),
    dict(id="RM-12", title="Git-backed model diffs as pull requests", area="platform", horizon="later", status="idea", priority=4,
         notes="Patches as PRs with multi-user review; the thread viewable on the web.", source="roadmap"),
    dict(id="RM-13", title="SysML v2 API / KerML export", area="model", horizon="later", status="idea", priority=4,
         notes="Interchange with Cameo / Syside.", source="roadmap"),
    dict(id="RM-14", title="Review the skill procedures against real experience", area="agents & skills", horizon="now", status="planned", priority=1,
         notes="First-draft procedures in sethread/skills.py; RFQ → award, inspection → CAPA and gate readiness need the appliance-industry version.", source="skills session"),
    dict(id="RM-15", title="MCP OAuth for hosted clients", area="platform", horizon="next", status="planned", priority=2,
         notes="HTTP Basic email:token works for Claude Code and local clients; hosted connectors (claude.ai) need OAuth 2.1 with dynamic client registration.", source="MCP session"),
    dict(id="RM-16", title="Sub-function templates under each fixed department", area="program", horizon="next", status="planned", priority=2,
         notes="Engineering → mechanical / electrical / firmware / industrial design / compliance; Manufacturing → ME / test / production; shipped as org structure templates the admin tailors.", source="org-structure session"),
    dict(id="RM-17", title="MES/ERP-lite growth: inventory and MRP from BOM × build plan", area="manufacturing", horizon="later", status="idea", priority=3,
         notes="Purchase orders and work orders exist; next is on-hand inventory, MRP netting against builds, and cost roll-up actuals.", source="PLM/MES/ERP session"),
    dict(id="RM-18", title="Indicator thresholds tunable under Policy", area="program", horizon="next", status="planned", priority=3,
         notes="Leading-indicator amber/red thresholds and the history window are platform defaults; expose them in org policy.", source="indicators session"),
    dict(id="RM-19", title="Review-build data size near the 16 MB artifact limit", area="ops", horizon="now", status="planned", priority=2,
         notes="data.json is ~16.0 MB with six examples; split per project or drop history from the snapshot before adding examples.", source="review build"),
    dict(id="RM-20", title="Skills as MCP prompts: evaluate with real runs", area="agents & skills", horizon="next", status="idea", priority=3,
         notes="Each skill should have a worked run on an example project (expected patches) so a change to a procedure can be checked.", source="skills session"),
]

def path(data_root): return os.path.join(data_root, ".org", "roadmap.yaml")

def load(data_root: str) -> dict:
    p = path(data_root)
    if os.path.exists(p): d = yaml.safe_load(open(p)) or {}
    else: d = {"items": [dict(x, created=time.strftime("%Y-%m-%d")) for x in SEED], "seeded": time.strftime("%Y-%m-%d")}
    d.setdefault("items", []); d["statuses"] = STATUSES; d["horizons"] = HORIZONS; d["areas"] = AREAS
    return d

def save(data_root: str, items: list[dict], by: str) -> dict:
    os.makedirs(os.path.dirname(path(data_root)), exist_ok=True)
    cur = load(data_root)
    clean = []
    for it in items:
        if not it.get("id") or not it.get("title"): continue
        clean.append({k: it.get(k) for k in ("id", "title", "area", "horizon", "status", "priority", "notes", "source", "created", "owner", "due")})
    d = {"items": clean, "seeded": cur.get("seeded"), "updated": time.strftime("%Y-%m-%d"), "updated_by": by}
    yaml.safe_dump(d, open(path(data_root), "w"), sort_keys=False, allow_unicode=True); return load(data_root)
