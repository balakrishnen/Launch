"""Domain-agnostic systems-engineering model schema.

The model is a dict of collections keyed by element kind; every element has an `id` and the
fields declared here. Disciplines on parts (mechanical, electrical, firmware, software, textile,
optical, thermal, …) let one model span a whole hardware company's product.

Validation here is structural (required fields, referential integrity). Semantic completeness
(every requirement verified, every candidate assessed, …) is in derive.coverage_report.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

DISCIPLINES = ["system", "mechanical", "electrical", "firmware", "software", "textile", "optical", "thermal", "chemical", "manufacturing", "external"]
GUIDE_WORDS_FUNC = ["loss", "degraded", "intermittent", "unintended", "wrong timing", "wrong value"]
GUIDE_WORDS_IF = ["open", "degraded", "leakage/crosstalk", "mismatch"]
GUIDE_WORDS_TR = ["fails to fire", "fires falsely", "fires late"]
REQ_TYPES = ["FUNC", "PERF", "SAFE", "REL", "ENV", "IFACE", "REGU", "MFG", "SEC", "MAINT", "USAB"]
VERIFY_METHODS = ["test", "analysis", "inspection", "demonstration"]

# kind -> (required fields, optional fields with defaults, reference fields -> target kind)
KINDS: dict[str, dict[str, Any]] = {
    "stakeholders": dict(req=["name"], opt={"role": "", "concerns": ""}, refs={}),
    "moes": dict(req=["name", "target"], opt={}, refs={}),
    "needs": dict(req=["stk", "text", "moe"], opt={"program": False}, refs={"stk": "stakeholders", "moe": "moes"}),
    "actors": dict(req=["name"], opt={}, refs={}),
    "use_cases": dict(req=["name", "actors"], opt={"includes": [], "needs": []}, refs={"actors": "actors", "includes": "use_cases", "needs": "needs"}),
    "scenarios": dict(req=["uc", "name", "steps"], opt={"concurrent": []}, refs={"uc": "use_cases", "steps": "functions", "concurrent": "functions"}),
    "regulations": dict(req=["name", "market", "trigger", "standard"], opt={}, refs={}),
    "requirements": dict(req=["type", "text", "verify", "tests"], opt={"attrs": {}, "from_": [], "regs": [], "uc": [], "attr": ""}, refs={"from_": "needs", "regs": "regulations", "uc": "use_cases", "tests": "tests"}),
    "functions": dict(req=["name", "alloc", "reqs"], opt={"perf": "", "safety_decision": ""}, refs={"alloc": "parts", "reqs": "requirements"}),
    "logical_components": dict(req=["name", "role", "funcs"], opt={"quality": [], "parts": []}, refs={"funcs": "functions", "parts": "parts"}),
    "logical_interfaces": dict(req=["a", "b", "flow"], opt={}, refs={"a": "logical_components", "b": "logical_components"}),
    "parts": dict(req=["name", "type"], opt={"parent": None, "attrs": {}, "discipline": "system", "context": False, "supplier": None, "lifecycle": "active", "make_buy": "", "owner_team": None}, refs={"parent": "parts", "supplier": "suppliers", "owner_team": "teams"}),
    "nodes": dict(req=["name", "parts", "lcs"], opt={}, refs={"parts": "parts", "lcs": "logical_components"}),
    "interfaces": dict(req=["name", "a", "b", "items", "kind", "funcs"], opt={"attrs": {}, "owner_a": "", "owner_b": "", "icd": {}}, refs={"a": "parts", "b": "parts", "funcs": "functions"}),
    "states": dict(req=["name"], opt={}, refs={}),
    "transitions": dict(req=["frm", "to", "trigger", "func"], opt={"guard": "", "sensor": None}, refs={"frm": "states", "to": "states", "func": "functions", "sensor": "parts"}),
    "constraints": dict(req=["name", "formula", "reqs", "tests"], opt={"inputs": []}, refs={"reqs": "requirements", "tests": "tests"}),
    "trades": dict(req=["name", "options", "criteria"], opt={"question": "", "recommendation": "", "affects": [], "elements": [], "weights": [], "criteria_meta": {}, "scores": {}, "raw": {}, "evidence": {}, "datum": None,
                                                           "decision": "", "rationale": "", "status": "open", "decided_by": "", "date": "", "owner_team": None}, refs={"affects": "requirements", "owner_team": "teams"}),
    "arch_decisions": dict(req=["title", "decision", "rationale", "reqs"], opt={"trade": None, "consequences": [], "change_from": "", "concerns": []}, refs={"reqs": "requirements", "trade": "trades"}),
    "tests": dict(req=["name", "method", "gate", "passfail"], opt={"attrs": {}, "units": "", "kind": "test", "status": "planned", "result": "", "result_rev": None, "owner_team": None, "samples": ""}, refs={"owner_team": "teams"}),
    "gates": dict(req=["date", "exit"], opt={"stage": "", "criteria": {}, "status": "planned", "phase": None}, refs={"phase": "phases"}),
    # Company product-development process (PDP): phases in order, each closed by a gate; deliverables owed per team (or per team kind/focus)
    # at a gate, each with a check the model can evaluate (see pdp.CHECKS) — the "what does my team owe at CDR" layer.
    "phases": dict(req=["name", "order"], opt={"stage": "", "gate": None, "description": ""}, refs={}),
    "deliverables": dict(req=["name", "gate"], opt={"team": None, "team_kind": "", "focus": "", "check": {}, "required": True, "description": "", "artifact": "", "owner": "", "waived": {}}, refs={"gate": "gates", "team": "teams"}),
    "fm_assessments": dict(req=["element", "guide"], opt={"mode": "", "effect": "", "cause": "", "S": None, "O": None, "D": None, "controls": "", "tests": [], "ncr": ""}, refs={"tests": "tests"}),
    # ---- whole-company layers: teams, manufacturing, supply chain, program, quality/field ----
    # Two kinds of team. subsystem: owns a slice of the architecture (scope = root parts and/or logical components; the closure is computed —
    # subtree, functions, requirements, boundary interfaces, failure modes, tests, MoEs). functional: cuts across all subsystems with a focus
    # (reliability, quality, safety, compliance, test, manufacturing, sourcing, program, systems, software…).
    "teams": dict(req=["name"], opt={"kind": "functional", "discipline": "", "focus": "", "lead": "", "members": [], "parts": [], "lcs": [], "moes": []}, refs={"parts": "parts", "lcs": "logical_components", "moes": "moes"}),
    "process_steps": dict(req=["name", "station"], opt={"seq": 0, "parts": [], "output": None, "characteristics": [], "controls": "", "cycle_s": None, "team": None, "eol_test": None}, refs={"parts": "parts", "output": "parts", "team": "teams", "eol_test": "tests"}),
    "suppliers": dict(req=["name"], opt={"parts": [], "status": "approved", "lead_time_d": None, "country": "", "risk": "", "second_source": None, "owner": ""}, refs={"parts": "parts", "second_source": "suppliers"}),
    "work_items": dict(req=["title", "owner", "status"], opt={"team": None, "due": "", "links": [], "gate": None, "priority": "P2", "notes": ""}, refs={"team": "teams", "gate": "gates"}),
    "findings": dict(req=["title", "severity", "status"], opt={"element": "", "source": "review", "owner": "", "action": "", "due": "", "gate": None, "closed": ""}, refs={"gate": "gates"}),
    "handoffs": dict(req=["from_team", "to_team", "what"], opt={"elements": [], "status": "pending", "due": "", "gate": None, "accepted_by": "", "note": ""}, refs={"from_team": "teams", "to_team": "teams", "gate": "gates"}),
    "field_events": dict(req=["date", "symptom"], opt={"unit": "", "parts": [], "fm": "", "disposition": "", "status": "open", "count": 1, "severity": "", "eight_d": ""}, refs={"parts": "parts"}),
    "risks": dict(req=["title", "prob", "impact"], opt={"owner": "", "mitigation": "", "status": "open", "links": [], "team": None}, refs={"team": "teams"}),
    "reviews": dict(req=["name", "gate", "date"], opt={"attendees": [], "findings": [], "decision": "", "notes": ""}, refs={"gate": "gates", "findings": "findings"}),
    # Office replacement: ad-hoc tables (trackers, rollups, lists — what used to be a spreadsheet) and notes (specs, minutes, decision logs — what used to be a doc).
    # tables.columns: [{key, name, type: text|number|date|ref|formula, kind?: ref target, formula?: expression over row fields and the model}]
    "tables": dict(req=["name", "columns", "rows"], opt={"description": "", "owner_team": None, "elements": []}, refs={"owner_team": "teams"}),
    # Test results intake (execution stays in TestRUNS, analytics in Kanalysis — they post here): a run is one result of a test on a unit,
    # with optional data, computed metrics, limits (from the requirement attribute or explicit) and a verdict. tests.status/result/result_rev follow the latest run.
    "test_runs": dict(req=["test", "date", "result"], opt={"unit": "", "operator": "", "data": "", "channels": [], "metrics": {}, "limits": {}, "checks": [], "notes": "", "rev": None, "station": ""}, refs={"test": "tests"}),
    # Simulations: a model-based analysis (FMU, FEA, CFD, SPICE, Modelica…) run against an element, with inputs/outputs and the requirements it informs
    "simulations": dict(req=["name", "tool", "element"], opt={"inputs": {}, "outputs": {}, "requirements": [], "file": "", "status": "planned", "date": "", "owner_team": None, "notes": ""}, refs={"requirements": "requirements", "owner_team": "teams"}),
    # Attachments: CAD (STEP/native), drawings, schematics, reports — files pinned to an element with a role
    "attachments": dict(req=["element", "file", "role"], opt={"title": "", "format": "", "rev": "", "date": "", "size": 0, "uploaded_by": ""}, refs={}),
    # Design-for-X review state: reviewer/agent statuses per guideline item (auto checks come from the library); one record per X
    "dfx_reviews": dict(req=["x"], opt={"items": {}, "date": "", "by": "", "notes": ""}, refs={}),
    # Native CAD: a part's geometry as build123d code, built into STEP/STL + measurements, checked against the thread
    "cad_models": dict(req=["part", "code"], opt={"name": "", "status": "draft", "built": "", "by": "", "volume_mm3": None, "mass_g": None, "bbox_mm": [], "files": {}, "checks": [], "features": [], "notes": "", "error": ""}, refs={"part": "parts"}),
    "quotes": dict(req=["part", "supplier"], opt={"qty": None, "unit_cost_usd": None, "moq": None, "lead_time_d": None, "tooling_usd": None, "nre_usd": None, "valid_until": "", "incoterm": "", "status": "requested", "date": "", "ref": "", "notes": ""}, refs={"part": "parts", "supplier": "suppliers"}),
    # supply chain — industrialization: tooling per part with T-sample milestones and PPAP/FAI status
    "tooling": dict(req=["part", "supplier"], opt={"tool_id": "", "type": "injection mold", "cavities": None, "cost_usd": None, "owner": "customer", "quote": None, "kickoff": "", "t0": "", "t1": "", "t2": "", "status": "quoted", "ppap": "not started", "ppap_level": 3, "fai": "", "capacity_per_week": None, "notes": ""}, refs={"part": "parts", "supplier": "suppliers", "quote": "quotes"}),
    # quality — inspections (incoming / in-process / EoL) feed supplier PPM and launch quality
    "inspections": dict(req=["date", "part", "stage", "qty", "defects"], opt={"supplier": None, "lot": "", "defect_codes": [], "disposition": "", "build": None, "station": "", "by": "", "notes": ""}, refs={"part": "parts", "supplier": "suppliers", "build": "gates"}),
    # quality — CAPA / 8D: the closed loop from a finding, field event or inspection to a verified corrective action
    "capa": dict(req=["title", "source", "status"], opt={"source_id": "", "parts": [], "fm": "", "containment": "", "root_cause": "", "corrective": "", "preventive": "", "verification_test": None, "verified": "", "owner": "", "team": None, "due": "", "closed": "", "notes": ""}, refs={"parts": "parts", "verification_test": "tests", "team": "teams"}),
    "claims": dict(req=["text"], opt={"type": "performance", "markets": [], "reqs": [], "tests": [], "regs": [], "owner": "", "approved": "", "status": "draft", "notes": ""}, refs={"reqs": "requirements", "tests": "tests", "regs": "regulations"}),
    "notes": dict(req=["title", "body"], opt={"kind": "note", "date": "", "author": "", "elements": [], "owner_team": None, "status": "draft"}, refs={"owner_team": "teams"}),
}
# Departments and the functional focuses inside them (Tesla-style: engineering by subsystem + disciplines incl. the design studio;
# quality split into supplier / launch / field / design; supply chain split into sourcing (GSM) / procurement / industrialization / logistics).
DEPARTMENTS = {
    "Engineering": ["systems", "mechanical", "electrical", "software", "firmware", "industrial design", "cmf", "ux", "human factors", "test", "cae", "safety", "reliability", "compliance", "homologation", "ehs"],
    # Quality does both halves: design quality (reviews, DFMEA completeness, design findings, perceived quality) and
    # manufacturing quality (supplier PPM/PPAP, launch & in-process & EoL, field loop)
    "Quality": ["quality", "design_quality", "supplier_quality", "launch_quality", "field_quality"],
    "Supply chain": ["sourcing", "procurement", "industrialization", "logistics"],
    "Manufacturing": ["manufacturing", "production_control"],
    "Program": ["program"],
    "Service": ["service", "field"],
    "Go-to-market": ["marketing", "sales"],
    "Corporate": ["finance", "hr", "facilities", "legal"],
}
TEAM_FOCUS = [f for fs in DEPARTMENTS.values() for f in fs]
DEPARTMENT_OF = {f: d for d, fs in DEPARTMENTS.items() for f in fs}
QUALITY_HALVES = {"design quality": ["quality", "design_quality"], "manufacturing quality": ["quality", "supplier_quality", "launch_quality", "field_quality"]}
GUIDE_WORDS_PROC = ["omitted", "wrong part", "wrong orientation", "insufficient", "excessive", "contamination", "damage"]
# INCOSE SE Handbook / ISO/IEC/IEEE 15288 generic life-cycle stages
LIFECYCLE = ["Concept", "Development", "Production", "Utilization", "Support", "Retirement"]
# ISO 15288 technical processes (in handbook order), the stage where each is primarily exercised, and the model collections it owns.
# This drives navigation: the app is arranged by life-cycle stage → technical process → artifacts.
PROCESSES = [
    ("Business or mission analysis", "Concept", ["stakeholders", "moes"]),
    ("Stakeholder needs and requirements definition", "Concept", ["needs", "actors", "use_cases", "scenarios"]),
    ("System requirements definition", "Development", ["regulations", "requirements", "constraints"]),
    ("System architecture definition", "Development", ["functions", "logical_components", "logical_interfaces", "nodes", "interfaces", "states", "transitions", "arch_decisions"]),
    ("Design definition", "Development", ["parts", "cad_models", "attachments"]),
    ("System analysis", "Development", ["trades", "fm_assessments", "simulations", "dfx_reviews", "claims"]),
    ("Implementation", "Development", ["suppliers", "quotes"]),
    ("Integration", "Development", []),
    ("Verification", "Development", ["tests", "test_runs"]),
    ("Transition", "Production", ["process_steps", "inspections"]),
    ("Validation", "Production", []),
    ("Operation", "Utilization", ["field_events"]),
    ("Maintenance", "Support", []),
    ("Disposal", "Retirement", []),
]
# ISO 15288 technical management processes (cross-cutting) and the collections they own
MANAGEMENT = [
    ("Project planning", ["phases", "gates", "deliverables", "work_items"]),
    ("Project assessment and control", ["teams", "handoffs"]),
    ("Decision management", []),
    ("Risk management", ["risks"]),
    ("Configuration management", []),
    ("Information management", ["tables", "notes"]),
    ("Measurement", []),
    ("Quality assurance", ["findings", "reviews", "capa"]),
]
PROCESS_STAGE = {name: stage for name, stage, _ in PROCESSES}
STAGE_OF = {k: name for name, _, kinds in PROCESSES for k in kinds} | {k: name for name, kinds in MANAGEMENT for k in kinds}
GATE_CRITERIA_KEYS = ["requirements_without_tests", "unassessed_candidates", "high_ap_fm_without_tests", "functions_without_allocation", "open_findings_critical", "pending_handoffs", "stale_verification", "tests_passed_share", "process_steps_without_pfmea", "parts_without_supplier"]

def empty_model(name: str = "New system") -> dict:
    m = {"meta": {"name": name, "version": "0.1", "method": "OOSEM"}}
    for k in KINDS: m[k] = {}
    m["program"] = {"lanes": []}
    return m

@dataclass
class Issue:
    level: str   # error | warning
    where: str
    msg: str

def validate(model: dict) -> list[Issue]:
    issues: list[Issue] = []
    for kind, spec in KINDS.items():
        coll = model.get(kind, {})
        if not isinstance(coll, dict):
            issues.append(Issue("error", kind, "collection must be a mapping of id -> element")); continue
        for eid, el in coll.items():
            if not isinstance(el, dict):
                issues.append(Issue("error", f"{kind}.{eid}", "element must be a mapping")); continue
            for f in spec["req"]:
                if f not in el: issues.append(Issue("error", f"{kind}.{eid}", f"missing required field '{f}'"))
            for f, target in spec["refs"].items():
                v = el.get(f)
                if v is None: continue
                vals = v if isinstance(v, list) else [v]
                for x in vals:
                    if x is None: continue
                    if x not in model.get(target, {}):
                        issues.append(Issue("error", f"{kind}.{eid}.{f}", f"dangling reference '{x}' (no such {target})"))
    for eid, p in model.get("parts", {}).items():
        if p.get("discipline", "system") not in DISCIPLINES:
            issues.append(Issue("warning", f"parts.{eid}", f"unknown discipline '{p.get('discipline')}'"))
    for eid, r in model.get("requirements", {}).items():
        if r.get("type") not in REQ_TYPES: issues.append(Issue("warning", f"requirements.{eid}", f"unknown type '{r.get('type')}'"))
        if r.get("verify") not in VERIFY_METHODS: issues.append(Issue("warning", f"requirements.{eid}", f"unknown verify method '{r.get('verify')}'"))
    for eid, a in model.get("fm_assessments", {}).items():
        if not a.get("ncr") and any(a.get(k) is None for k in ("S", "O", "D")):
            issues.append(Issue("error", f"fm_assessments.{eid}", "assessment needs S, O, D or an ncr reason"))
        el = a.get("element", "")
        if el not in model.get("functions", {}) and el not in model.get("interfaces", {}) and el not in model.get("transitions", {}) and el not in model.get("process_steps", {}):
            issues.append(Issue("error", f"fm_assessments.{eid}", f"element '{el}' is not a function, interface, transition or process step"))
    return issues

def with_defaults(model: dict) -> dict:
    for kind, spec in KINDS.items():
        for el in model.get(kind, {}).values():
            for f, d in spec["opt"].items():
                el.setdefault(f, [] if isinstance(d, list) else dict(d) if isinstance(d, dict) else d)
    return model
