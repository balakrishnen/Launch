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
    "parts": dict(req=["name", "type"], opt={"parent": None, "attrs": {}, "discipline": "system", "context": False}, refs={"parent": "parts"}),
    "nodes": dict(req=["name", "parts", "lcs"], opt={}, refs={"parts": "parts", "lcs": "logical_components"}),
    "interfaces": dict(req=["name", "a", "b", "items", "kind", "funcs"], opt={"attrs": {}, "owner_a": "", "owner_b": "", "icd": {}}, refs={"a": "parts", "b": "parts", "funcs": "functions"}),
    "states": dict(req=["name"], opt={}, refs={}),
    "transitions": dict(req=["frm", "to", "trigger", "func"], opt={"guard": "", "sensor": None}, refs={"frm": "states", "to": "states", "func": "functions", "sensor": "parts"}),
    "constraints": dict(req=["name", "formula", "reqs", "tests"], opt={"inputs": []}, refs={"reqs": "requirements", "tests": "tests"}),
    "trades": dict(req=["name", "options", "criteria", "recommendation"], opt={"affects": [], "weights": [], "scores": {}, "datum": None}, refs={"affects": "requirements"}),
    "arch_decisions": dict(req=["title", "decision", "rationale", "reqs"], opt={"trade": None, "consequences": [], "change_from": "", "concerns": []}, refs={"reqs": "requirements", "trade": "trades"}),
    "tests": dict(req=["name", "method", "gate", "passfail"], opt={"attrs": {}, "units": "", "kind": "test"}, refs={}),
    "gates": dict(req=["date", "exit"], opt={}, refs={}),
    "fm_assessments": dict(req=["element", "guide"], opt={"mode": "", "effect": "", "cause": "", "S": None, "O": None, "D": None, "controls": "", "tests": [], "ncr": ""}, refs={"tests": "tests"}),
}

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
        if el not in model.get("functions", {}) and el not in model.get("interfaces", {}) and el not in model.get("transitions", {}):
            issues.append(Issue("error", f"fm_assessments.{eid}", f"element '{el}' is not a function, interface or transition"))
    return issues

def with_defaults(model: dict) -> dict:
    for kind, spec in KINDS.items():
        for el in model.get(kind, {}).values():
            for f, d in spec["opt"].items():
                el.setdefault(f, [] if isinstance(d, list) else dict(d) if isinstance(d, dict) else d)
    return model
