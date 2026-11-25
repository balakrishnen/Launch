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
    dict(id="RM-19", title="Review-build data size near the 16 MB artifact limit", area="ops", horizon="now", status="done", priority=2,
         notes="Snapshot split into proj_<pid>.json files loaded lazily by the review shim; data.json carries only the lists, org and roadmap.", source="review build"),
    dict(id="RM-20", title="Skills as MCP prompts: evaluate with real runs", area="agents & skills", horizon="next", status="idea", priority=3,
         notes="Each skill should have a worked run on an example project (expected patches) so a change to a procedure can be checked.", source="skills session"),
    dict(id="RM-21", title="Organization-owned skills: edit, add and version the catalog in Settings", area="agents & skills", horizon="next", status="planned", priority=1,
         notes="Skills live in sethread/skills.py today. Move the catalog into the org record (seeded from the built-ins), editable under Settings › Skills, versioned with process/teams; 'learn a skill from this run' turns a successful conversation into a procedure. The org's way of working is the asset, not the model.", source="nTop ten-variants post, 2026-11-12"),
    dict(id="RM-22", title="Trade evaluation conditions: record per option, check for consistency", area="engineering", horizon="next", status="planned", priority=2,
         notes="Options scored under different conditions (mesh, load case, solver settings, fixture, sample size) make the comparison meaningless. Add conditions to trade criteria_meta and per-option evidence; the trades check fails when options differ. Prerequisite for sub-agents generating N variants onto one trade.", source="nTop ten-variants post, 2026-11-12"),
    dict(id="RM-23", title="Modeling recipes: the Launch answer to 'how would you model this?' per kind, with a coverage check", area="model", horizon="next", status="idea", priority=2,
         notes="Each schema kind is a modeling recipe (question, one-sentence answer, fields, refs, the derived form, the common wrong model). Publish them as the schema reference, and check Launch's coverage against Moberley's 75 SysML v2 recipes: known gaps today are pins/nets on a schematic (EDA adapter only), message/frame definitions (CAN, protocol fields), software/cloud deployment, and non-physical items (licences, data). Pair with RM-13 so exports validate in a SysML v2 parser.", source="Brian Moberley, How to Model Anything in SysML v2, 2026-11-12"),
    dict(id="RM-24", title='Role-to-role work requests between agent threads (raise → wake → run → reply, on the graph)', area="agents & skills", horizon="next", status="planned", priority=2,
         notes="Data already flows between roles through the graph (simulations, CDAs, test runs, with provenance). Missing is work: an agent in one thread raises a request owned by another role (a work item with the ask and the ids), that role's thread wakes and runs it (usually a skill), writes the result as patches, and the asking thread resumes with the answer. Reviewable on both sides; fan-out/fan-in for trade option generation (RM-22).", source='Navier AI Prism agent messaging post, 2026-11-13'),
    dict(id='RM-25', title='Skills as workflows: deterministic steps, agent only where reasoning is needed', area='agents & skills', horizon='next', status='planned', priority=2,
         notes='Today every skill is a full agent run. Split each procedure into deterministic steps (queries, checks, form generation, patch templates) that cost nothing and are repeatable, and agent steps only where judgment is needed (root cause, rationale, rewording). Lowers cost, makes runs reproducible, and makes skills testable.', source='MOVEdot moveOS launch post, 2026-11-17'),
    dict(id='RM-26', title='AI cost controls and model choice per organization', area='platform', horizon='next', status='planned', priority=2,
         notes='Spend limits per org, team and skill; usage dashboard for admins; model routing (frontier for reasoning steps, small or open-weight for extraction). Enterprise buyers ask for this before a pilot.', source='MOVEdot moveOS launch post, 2026-11-17'),
    dict(id='RM-27', title="Deploy in the customer's cloud (single-tenant / BYO-cloud option)", area='platform', horizon='later', status='idea', priority=3,
         notes="Appliance and automotive OEMs keep design data in their own cloud. Package Launch (app, Postgres, agents, MCP) for single-tenant deployment in AWS/Azure/GCP with the customer's IdP and model endpoint.", source='MOVEdot moveOS launch post, 2026-11-17'),
    dict(id='RM-28', title="Knowledge index over the organization's reports, specs and methods", area='model', horizon='next', status='idea', priority=2,
         notes='Agents start from prior test reports, design guides and lessons learned. Index uploaded documents per org and project, cite them as sources on staged patches, and link extracted facts to model elements.', source='MOVEdot moveOS launch post, 2026-11-17'),
    dict(id='RM-29', title='Query workspace: plain-English and SQL questions across the whole graph, pinned to dashboards', area='platform', horizon='next', status='planned', priority=2,
         notes="Forms answer the standard questions; teams also ask one-off cross-cutting ones ('which released parts still have open DFMEA actions', 'which requirements changed since PDR and which tests did that touch'). Expose the model as read-only SQL tables (DuckDB over a nightly or per-revision export), let the agent write and run the query with each step visible, chart the result, pin it to a team page, and alert when a pinned query breaks or its answer changes.", source='Violet Labs Data Lab post, 2026-11-22'),
    dict(id='RM-30', title='Time travel: any artifact or query as of a date, gate baseline or revision', area='model', horizon='next', status='planned', priority=2,
         notes="Launch already keeps every revision and baselines at gates. Surface it: render any form as of a baseline, diff two baselines (what changed in the DFMEA between PDR and CDR), and allow 'as of' in the query workspace. Gate reviews and audits ask for exactly this.", source='Violet Labs Data Lab post, 2026-11-22'),
    dict(id='RM-31', title='Ingest from incumbent PLM/ERP/MES into the graph (read-side connectors)', area='integrations', horizon='later', status='idea', priority=3,
         notes="For companies that keep Teamcenter, Arena or an ERP, sync parts, BOMs, change orders and PO lines into the graph on a schedule, mapped to Launch kinds, so Launch's forms and checks run on their real data without replacing those tools first.", source='Violet Labs Data Lab post, 2026-11-22'),
    dict(id='RM-32', title='Launch-Bench: score agents on billable deliverables from the example programs', area='agents & skills', horizon='next', status='idea', priority=2,
         notes="PLE-style tasks built from BrewMaster, Sabi and the other examples (write the PVT PFMEA, close CAPA-06 with an 8D, draft the PVT entry review, size EoL fixtures for 150k/yr). Each task has a weighted rubric of binary, evidence-bound checks plus executable graders that run the Launch validators. Run per model and per skill on every release so skill changes are measured, not guessed. Keep a private held-out set.", source="PLE: Physical-Engineering's Last Exam (Google Cloud AI Research, arXiv 2610.30537), 2026-11-23"),
    dict(id='RM-33', title='Hard-constraint gate on every agent deliverable before it is accepted', area='agents & skills', horizon='now', status='idea', priority=1,
         notes="PLE found Opus 5.5 meets about 91% of constraints on average but only 41% of deliverables meet every hard constraint. Before a patch or form from an agent is accepted, run the deterministic checks (schema, trace, S≥9 needs a test, AP H needs an action, control-plan SC lines need a reaction plan, cost under target). Any hard failure blocks acceptance and goes back to the agent with the failing rows, instead of relying on the agent's own claim that it is done.", source="PLE: Physical-Engineering's Last Exam (Google Cloud AI Research, arXiv 2610.30537), 2026-11-23"),
    dict(id='RM-34', title='Applied-clause list: every requirement and deliverable cites the standard clause and value it used', area='model', horizon='next', status='idea', priority=2,
         notes="PLE solvers must list the requirements they applied (clause + value) and graders check them against the source documents. In Launch: regulation links carry clause (e.g. IEC 60335-1 cl. 11, 60 K) and limit; agents must fill them; a checker compares the value against the regulations library so a wrong limit is caught rather than silently traced.", source="PLE: Physical-Engineering's Last Exam (Google Cloud AI Research, arXiv 2610.30537), 2026-11-23"),
    dict(id='RM-35', title='Economic objective in trades and deliverables: compliant is not enough', area='engineering', horizon='later', status='idea', priority=3,
         notes="PLE scores designs that pass every check but cost 20% more than a certified bound lower. Add an objective (cost, mass, cycle time) with a known bound to trade studies, BOM and EoL station sizing, and show the gap to the bound next to the pass/fail result.", source="PLE: Physical-Engineering's Last Exam (Google Cloud AI Research, arXiv 2610.30537), 2026-11-23"),

    dict(id='RM-36', title='Sourced brief: one-line product idea to needs and requirements, every fact cited, gaps asked', area='agents & skills', horizon='next', status='idea', priority=2,
         notes="Neural Concept's fan agent turned a one-line request into a brief of 1,105 sourced facts from 26 public documents and asked for what was missing. In Launch: a new-project skill that reads datasheets, standards and competitor specs into stakeholder needs, requirements and constraints, each with its source document and page, and lists open questions as findings instead of guessing.", source='Neural Concept, Agentic engineering design: turbomachinery case studies, 2026-11-25'),
    dict(id='RM-37', title='Fidelity ladder on analyses: screen fast, confirm at higher fidelity before a CDA counts as met', area='engineering', horizon='next', status='idea', priority=2,
         notes="Record the method fidelity on each simulation (hand calc / 1D / surrogate / FEA-CFD / test). A CDA or requirement is only 'met' when confirmed at the fidelity its policy names; a surrogate prediction outside its training range is flagged, not trusted. Correlation between levels (SIM-02 52 K predicted vs TST-05 49 K measured) is stored and shown, so model error is known per method. Each method also carries its verification evidence (e.g. NAFEMS benchmark cases passed for an FEA solver, model-test correlation for a surrogate), so an AI-native solver claiming parity with Ansys is accepted on the evidence for the load cases it was verified on, not on the claim.", source='Neural Concept, Agentic engineering design: turbomachinery case studies, 2026-11-25'),
    dict(id='RM-38', title='Design-space exploration on trades: variable ranges, governing-variable sensitivity, edge-of-range flag', area='engineering', horizon='later', status='idea', priority=3,
         notes="Extends RM-02. Trades get continuous variables with ranges; the loop freezes, narrows or extends each range between rounds. Show which variable governs which CDA (chord → pressure ratio, blade count → efficiency in the compressor case) and flag when the best candidates sit at a range edge, which means the range is wrong, not that the optimum was found.", source='Neural Concept, Agentic engineering design: turbomachinery case studies, 2026-11-25'),
    dict(id='RM-39', title='Agent-built engineering tools: small interactive calculators bound to the model', area='agents & skills', horizon='later', status='idea', priority=3,
         notes="Neural Concept's agent built a propeller app that re-solves in about 60 ms so the engineer explores in real time. In Launch: the agent generates a calculator page (EoL fixture count vs demand, thermoblock sizing, tolerance stack) that reads its inputs from the model, checks results against requirements and writes the chosen point back as a patch with its evidence.", source='Neural Concept, Agentic engineering design: turbomachinery case studies, 2026-11-25'),

    dict(id='RM-40', title='Geometry design review: run DfM, tolerance and ICD checks on attached STEP files, ranked by severity', area='engineering', horizon='later', status='idea', priority=2,
         notes="Leo's Inspector reviews an assembly or STEP file for geometry, interfaces, tolerances, GD&T and company standards and ranks issues by severity. In Launch the same review gains the model: check wall thickness and draft against the part's CTQ and process (e.g. P-ENCL 2.5 ±0.15 mm molded PP), mating features against the ICD tolerances (IF-15 rail gap), and file each issue as a finding on the part with severity, so it reaches the gate review instead of a CAD comment.", source='Leo AI (getleo.ai), 2026-11-25'),
    dict(id='RM-41', title='Part reuse search: suggest existing parts from past programs and vendor catalogs before a new part is added', area='model', horizon='later', status='idea', priority=3,
         notes="When a part is added or a function is allocated, search the organization's other programs (same attrs, qualified supplier, PPAP history, field PPM) and vendor catalogs, and show reuse candidates with their evidence. A reused part brings its test history and FMEA rows with it, which is worth more than the CAD.", source='Leo AI (getleo.ai), 2026-11-25'),
    dict(id='RM-42', title='CAD-side agent connector (Leo AI, Onshape/Fusion agents) over MCP', area='integrations', horizon='later', status='idea', priority=3,
         notes="Launch should not build CAD generation. Treat CAD-side agents as peers: Launch sends the brief (requirements, CTQs, ICD characteristics, envelope) and receives geometry, mass properties and design-review issues back as a patch with evidence. Complements RM-01 (simulation brief) and RM-11 (vendor APIs behind the CAD stubs). Leo is positioned as a mechanical design copilot with PLM read access, so it is more likely a partner than a competitor. Update 2026-11-25: Leo now claims an autonomous loop of motion simulation (NVIDIA Newton), FEA (verified on 185 NAFEMS/textbook cases), thermal, DFM/DFA review and automatic fixes until the design passes. That makes the connector more valuable: each result should come back as a simulation record with method, solver version, load case, boundary conditions and verification evidence, and 'passes' must mean passes against Launch's requirements and CDAs, not Leo's own criteria.", source='Leo AI (getleo.ai), 2026-11-25'),

]

def path(data_root): return os.path.join(data_root, ".org", "roadmap.yaml")

def load(data_root: str) -> dict:
    p = path(data_root)
    if os.path.exists(p): d = yaml.safe_load(open(p)) or {}
    else: d = {"items": [dict(x, created=time.strftime("%Y-%m-%d")) for x in SEED], "seeded": time.strftime("%Y-%m-%d")}
    d.setdefault("items", [])
    have = {x.get("id") for x in d["items"]}   # seed items added in later releases join an existing roadmap; edits to existing ones are kept
    d["items"] += [dict(x, created=time.strftime("%Y-%m-%d")) for x in SEED if x["id"] not in have]
    d["statuses"] = STATUSES; d["horizons"] = HORIZONS; d["areas"] = AREAS
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
