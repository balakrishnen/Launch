"""Market landscape: the companies, products and research reviewed while building Launch (products and startups only; training providers are out of scope) (Settings › Landscape, admins).
Each entry records what it is, why it matters to Launch, the stance we take (compete / partner / learn / watch) and the roadmap
items it produced, so a later conversation can reference it instead of re-reading the source."""
import os, time, yaml

CATEGORIES = ["competitor", "partner candidate", "adjacent", "incumbent", "research", "standard", "event", "person", "technology"]
STANCES = ["compete", "partner", "learn", "watch", "integrate"]

SEED = [
    dict(id="LS-01", name="Leo AI", url="https://www.getleo.ai/", category="partner candidate", stance="partner",
         what="CAD-side agent for mechanical teams: text/image to parametric parts and assemblies, Inspector design review on STEP (geometry, tolerances, GD&T, company standards), part search over PLM and 120M vendor parts, cited calculations. Claims a Large Mechanical Model trained on 3D CAD; CAD-agnostic (SOLIDWORKS, NX, Creo, Onshape, Fusion, Teamcenter, Windchill). Per-user annual enterprise pricing. 2026-11-25 post: autonomous motion (NVIDIA Newton), FEA verified on 185 NAFEMS/textbook cases, thermal, DFM/DFA and auto-fix loop ('Ansys is dead').",
         relevance="Owns geometry inside one engineer's CAD session; Launch owns the program graph. Launch should define what 'passes' means (requirements, CDAs, FMEA) and record Leo's results as evidence.",
         roadmap=["RM-40", "RM-41", "RM-42", "RM-37"], first_seen="2026-11-25", last_seen="2026-11-25", sources=["https://www.getleo.ai/", "LinkedIn launch post 2026-11-25 (Moti Moravia, co-founder and CTO)"],
         notes="Reaction to the 'Ansys is dead' post (2026-11-25), from simulation practitioners (Blue Origin, Constellium, ECM Space, ANSYS consultants): NAFEMS cases are a prerequisite, not real workflows; Ansys is bought for edge cases (anisotropic single-crystal blades, temperature-dependent viscoplasticity, turbomachinery, explicit rupture dynamics, DEM) and for its proven, supported codes; software cost is a small share of project cost; the 'dead' framing hurt the brand. The CTO's replies narrowed the claim: Ansys stays for advanced cases; Leo's edge is setting up large assemblies (every screw, weldment, connection and boundary condition) in minutes instead of days, works on existing SOLIDWORKS or STEP assemblies, live for all Leo users, full verification report 'soon'. Read: Leo targets routine design-engineer analysis, not the analyst seat. Launch angle holds: the market distrusts unverified automated analysis, which is the gap RM-37 (verification evidence per method) and RM-33 (hard-constraint gate) fill."),
    dict(id="LS-02", name="Neural Concept", url="https://www.neuralconcept.com/", category="adjacent", stance="learn",
         what="AI surrogates and an agentic design loop (brief, size, shape, check, evaluate, correct) inside the customer's CAD/CFD; Design Copilot UI; Evolving Design Space plus Bayesian optimisation. Vendor-reported cases: hydropower turbine +0.6 pt efficiency, bid in half the time; MAHLE blower 14% more efficient, 2.9 dB quieter; axial fan brief of 1,105 sourced facts from a one-line request; over 96% of designs assessed without CFD.",
         relevance="Deep in one physics domain where Launch is wide across the program. Validates check-before-simulate and fidelity ladders; source of the sourced-brief idea.",
         roadmap=["RM-36", "RM-37", "RM-38", "RM-39"], first_seen="2026-11-25", last_seen="2026-11-25", sources=["https://www.neuralconcept.com/industry-stories/agentic-engineering-design-turbomachinery-case-studies"]),
    dict(id="LS-03", name="PLE benchmark (Google Cloud AI Research)", url="https://arxiv.org/pdf/2610.30537", category="research", stance="learn",
         what="Physical-Engineering's Last Exam: 85 long-horizon tasks (electrical, mechanical, civil, structural) producing billable deliverables from messy corpora in MCP sandboxes; expert pool from Mercor. Best: Claude Opus 5.5 in Claude Code 50.6% at about $17 per task; mechanical 40.5%. Deliverables meet about 91% of constraints but only 41% meet every hard constraint. Model spread about 50 points vs harness spread about 3.",
         relevance="Evidence for hard-constraint gates on agent output and for a Launch-Bench; harness alone is not a moat. Does not cover MBSE, FMEA or the hardware life cycle: an opening for the INCOSE paper.",
         roadmap=["RM-32", "RM-33", "RM-34", "RM-35"], first_seen="2026-11-23", last_seen="2026-11-23", sources=["https://arxiv.org/pdf/2610.30537"]),
    dict(id="LS-04", name="Violet Labs", url="https://www.violetlabs.com/", category="competitor", stance="compete",
         what="Hardware engineering data platform; Data Lab gives one query across the hardware stack (PLM, ERP, requirements, test).",
         relevance="Closest overlap with Launch's graph-plus-query story. Launch differs by deriving the engineering deliverables (FMEA, DVP&R, control plan, gates) from the model, not only querying connected tools.",
         roadmap=["RM-29", "RM-30", "RM-31"], first_seen="2026-11-22", last_seen="2026-11-22", sources=["https://www.violetlabs.com/blog/introducing-data-lab-one-query-across-your-entire-hardware-stack"]),
    dict(id="LS-05", name="MOVEdot (moveOS)", url="https://www.movedot.com/", category="adjacent", stance="watch",
         what="Launched moveOS, an operating layer for engineering work with AI agents.",
         relevance="Prompted workflow-style skills, per-organization AI cost controls, customer-cloud deployment and an organization knowledge index. Mentioned in the INCOSE paper.",
         roadmap=["RM-25", "RM-26", "RM-27", "RM-28"], first_seen="2026-11-17", last_seen="2026-11-17", sources=["https://www.movedot.com/blog/introducing-moveos"]),
    dict(id="LS-06", name="Navier AI (Prism)", url="", category="adjacent", stance="learn",
         what="Prism: agents that message each other across roles.",
         relevance="Source of role-to-role work requests between agent threads on the graph.",
         roadmap=["RM-24"], first_seen="2026-11-13", last_seen="2026-11-13", sources=["LinkedIn post 2026-11-13"]),
    dict(id="LS-07", name="nTop", url="https://www.ntop.com/", category="adjacent", stance="learn",
         what="Computational design / implicit modelling; post on ten agents generating design variants.",
         relevance="Prompted organization-owned skills and recorded trade evaluation conditions.",
         roadmap=["RM-21", "RM-22"], first_seen="2026-11-12", last_seen="2026-11-12", sources=["LinkedIn post 2026-11-12"]),
    dict(id="LS-08", name="Autodesk Fusion + Google Gemini (FEA loop)", url="", category="adjacent", stance="integrate",
         what="Demonstration of an LLM driving a closed CAD to FEA loop in Fusion.",
         relevance="Launch sends the simulation brief and records results (record_simulation) rather than running FEA itself.",
         roadmap=["RM-01"], first_seen="2026-11-12", last_seen="2026-11-12", sources=["LinkedIn post 2026-11-12"]),
    dict(id="LS-09", name="Brian Moberley (SysML v2 cookbook)", url="", category="person", stance="learn",
         what="'How to Model Anything in SysML v2': modelling recipes per element kind.",
         relevance="Source of modelling recipes with a coverage check per kind.",
         roadmap=["RM-23"], first_seen="2026-11-12", last_seen="2026-11-12", sources=["LinkedIn post 2026-11-12"]),
    dict(id="LS-10", name="MBSE Insights (MCP servers for SysML v2)", url="https://www.mbseinsights.com/posts/mcp-servers-mbse-agentic-sysml-v2/", category="research", stance="learn",
         what="Article on MCP servers as the agent interface to SysML v2 models.",
         relevance="Supports Launch's MCP server design; cited in the INCOSE IS 2027 paper.",
         roadmap=["RM-13", "RM-15"], first_seen="2026-11-13", last_seen="2026-11-13", sources=["https://www.mbseinsights.com/posts/mcp-servers-mbse-agentic-sysml-v2/"]),
    dict(id="LS-11", name="Confetti", url="https://confetti.build/", category="adjacent", stance="watch",
         what="Reviewed and tried on 2026-11-13 for the INCOSE paper; product summary to be refreshed on the next visit.",
         relevance="Referenced in the paper's related work.", roadmap=[], first_seen="2026-11-13", last_seen="2026-11-13", sources=["https://confetti.build/"]),
    dict(id="LS-12", name="Omniconn / UL Solutions (UL 3115)", url="", category="standard", stance="learn",
         what="Case study of evaluating an AI-enabled product against UL 3115 (AI safety) with UL Solutions.",
         relevance="UL 3115 and the EU AI Act added to Launch's regulations library (triggered by AI functions).",
         roadmap=[], first_seen="2026-11-18", last_seen="2026-11-18", sources=["UL Solutions web case study"]),
    dict(id="LS-13", name="Future of Engineering Summit", url="", category="event", stance="watch",
         what="Industry summit on AI in engineering; recap reviewed.", relevance="Market signal for agentic engineering; contacts and talks to follow up.",
         roadmap=[], first_seen="2026-11-17", last_seen="2026-11-17", sources=["Summit recap"]),
    dict(id="LS-14", name="Bild", url="", category="competitor", stance="compete",
         what="Cloud PDM for hardware teams.", relevance="Benchmark for the agent-first PDM/PLM plan; Launch's part, BOM and ECO kinds overlap.",
         roadmap=["RM-31"], first_seen="2026-10-17", last_seen="2026-10-17", sources=[]),
    dict(id="LS-15", name="Ansys", url="https://www.ansys.com/", category="incumbent", stance="integrate",
         what="Incumbent simulation suite (now part of Synopsys).", relevance="Qualified solver history matters for certification; AI-native solvers are accepted per the fidelity ladder evidence.",
         roadmap=["RM-37"], first_seen="2026-11-25", last_seen="2026-11-25", sources=[]),
    dict(id="LS-16", name="Requirements tools: Jama, IBM DOORS, Siemens Polarion", url="", category="incumbent", stance="integrate",
         what="Incumbent requirements management tools named in SE job descriptions.", relevance="Import/export via OSLC and ReqIF so Launch can sit beside them.",
         roadmap=["RM-06"], first_seen="2026-11-10", last_seen="2026-11-10", sources=[]),
    dict(id="LS-17", name="PLM/ERP: Siemens Teamcenter, Arena, PTC Windchill, SAP", url="", category="incumbent", stance="integrate",
         what="Incumbent PLM and ERP systems of record.", relevance="Read-side ingest so Launch's forms and checks run on real data before replacing anything.",
         roadmap=["RM-11", "RM-31"], first_seen="2026-11-12", last_seen="2026-11-22", sources=[]),
    dict(id="LS-18", name="NVIDIA Newton", url="", category="technology", stance="watch",
         what="Open physics engine; powers Leo's motion simulation.", relevance="Candidate engine behind simulation briefs for motion and load extraction.",
         roadmap=["RM-01"], first_seen="2026-11-25", last_seen="2026-11-25", sources=[]),
]

SEED += [
    dict(id="LS-19", name="OpenBOM (Oleg Shilovitsky)", url="https://www.openbom.com/", category="adjacent", stance="watch",
         what="Cloud BOM and data management for hardware teams; Oleg Shilovitsky (CEO, BeyondPLM blog) is a widely read PLM commentator.",
         relevance="Overlaps Launch's part/BOM/ECO kinds; his commentary is a useful read of how the PLM community receives AI-agent claims (skeptical of Leo's 'Ansys is dead').",
         roadmap=["RM-31"], first_seen="2026-11-25", last_seen="2026-11-25", sources=["Comment on Leo AI post 2026-11-25"]),
    dict(id="LS-20", name="MatAlytics (Dr. Benedikt Engel)", url="", category="adjacent", stance="watch",
         what="Physics-informed AI startup (CEO and co-founder Benedikt Engel); asked whether Leo handles anisotropic, temperature-dependent viscoplastic single-crystal blades.",
         relevance="Material-model depth is where AI-native solvers will be tested; a possible source of material behaviour models for simulation briefs.",
         roadmap=["RM-37"], first_seen="2026-11-25", last_seen="2026-11-25", sources=["Comment on Leo AI post 2026-11-25"]),
]
SEED += [dict(id=i, name=n, url=u, category=c, stance=st, what=w, relevance=r, roadmap=rm, first_seen="2026-11-10", last_seen="2026-11-10", sources=[u] if u else []) for i, n, u, c, st, w, r, rm in [
    ("LS-21", "Flow Engineering", "https://www.flowengineering.com/", "competitor", "compete", "Requirements and systems engineering tool for hardware teams with live engineering values.", "Named benchmark: Launch targets 10x better by deriving the full artifact set and gates from the model.", []),
    ("LS-22", "Dalus", "https://www.dalus.io/", "competitor", "compete", "AI-native MBSE / systems design platform.", "Direct comparison point for agentic MBSE.", ["RM-13"]),
    ("LS-23", "Trace.Space", "", "competitor", "compete", "AI requirements and traceability platform for hardware.", "Overlaps Launch's requirements and trace views.", ["RM-06"]),
    ("LS-24", "Syndeia (Intercax)", "", "adjacent", "integrate", "Digital-thread integration across MBSE, PLM, ALM and simulation tools.", "Integration-layer alternative; Launch keeps the thread in its own graph and connects via OSLC/MCP.", ["RM-06", "RM-31"]),
    ("LS-25", "Nominal", "https://nominal.io/", "adjacent", "watch", "Test and operations data platform for hardware (aerospace, defense).", "Adjacent to TestRUNS/Kanalysis rather than Launch; test evidence would flow into Launch's runs.", ["RM-03"]),
    ("LS-26", "MecAgent", "", "partner candidate", "partner", "CAD-side copilot for mechanical design.", "Same seat as Leo AI; candidate for the CAD-side agent connector.", ["RM-42"]),
    ("LS-27", "CopperPilot", "", "partner candidate", "partner", "Electronics-side (EDA) copilot.", "EDA counterpart to the CAD-side connector; Launch sends the electrical brief and records results.", ["RM-11"]),
]]
FIELDS = ("id", "name", "url", "category", "stance", "what", "relevance", "roadmap", "first_seen", "last_seen", "sources", "notes")

def path(root): return os.path.join(root, ".org", "landscape.yaml")

def load(root: str) -> dict:
    p = path(root)
    d = (yaml.safe_load(open(p)) or {}) if os.path.exists(p) else {"seeded": time.strftime("%Y-%m-%d")}
    d.setdefault("items", []); have = {x.get("id") for x in d["items"]}
    d["items"] += [dict(x) for x in SEED if x["id"] not in have]
    d["categories"] = CATEGORIES; d["stances"] = STANCES
    return d

def save(root: str, items: list[dict], by: str) -> dict:
    os.makedirs(os.path.dirname(path(root)), exist_ok=True); cur = load(root)
    clean = [{k: it.get(k) for k in FIELDS} for it in items if it.get("id") and it.get("name")]
    yaml.safe_dump({"items": clean, "seeded": cur.get("seeded"), "updated": time.strftime("%Y-%m-%d"), "updated_by": by}, open(path(root), "w"), sort_keys=False, allow_unicode=True)
    return load(root)
