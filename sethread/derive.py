"""Derived artifacts and the trace check, over any model that follows schema.KINDS.

Nothing authored here. Every row carries the ids it was derived from.
"""
from __future__ import annotations
from .schema import GUIDE_WORDS_FUNC, GUIDE_WORDS_IF, GUIDE_WORDS_TR

def ap(S, O, D) -> str:
    if S >= 9: return "H"
    if S >= 7 and O >= 5: return "H"
    if S >= 7 and O >= 3 and D >= 5: return "H"
    if S >= 5 and O >= 5 and D >= 5: return "H"
    if S >= 5 and O >= 4: return "M"
    if S >= 7: return "M"
    if S >= 4 and O >= 3 and D >= 5: return "M"
    return "L"

def candidates(m):
    c = []
    for f in m["functions"]: c += [("function", f, g) for g in GUIDE_WORDS_FUNC]
    for i in m["interfaces"]: c += [("interface", i, g) for g in GUIDE_WORDS_IF]
    for t in m["transitions"]: c += [("transition", t, g) for g in GUIDE_WORDS_TR]
    return c

def _assess_index(m):
    return {(a["element"], a["guide"]): a for a in m["fm_assessments"].values()}

def element_name(m, kind, eid):
    if kind == "function": return m["functions"][eid]["name"]
    if kind == "interface": return m["interfaces"][eid]["name"]
    t = m["transitions"][eid]
    return f"{m['states'][t['frm']]['name']} → {m['states'][t['to']]['name']} on {t['trigger']}" + (f" [{t['guard']}]" if t.get("guard") else "")

def element_reqs(m, kind, eid):
    if kind == "function": return list(m["functions"][eid]["reqs"])
    if kind == "interface": return sorted({r for f in m["interfaces"][eid]["funcs"] for r in m["functions"][f]["reqs"]})
    return list(m["functions"][m["transitions"][eid]["func"]]["reqs"])

def element_parts(m, kind, eid):
    if kind == "function": return list(m["functions"][eid]["alloc"])
    if kind == "interface": return [m["interfaces"][eid]["a"], m["interfaces"][eid]["b"]]
    t = m["transitions"][eid]; ps = list(m["functions"][t["func"]]["alloc"])
    if t.get("sensor") and t["sensor"] not in ps: ps.append(t["sensor"])
    return ps

def fmea(m):
    idx = _assess_index(m); rows, n = [], 0
    for kind, eid, g in candidates(m):
        a = idx.get((eid, g))
        if a is None or a.get("ncr"): continue
        n += 1
        rows.append(dict(id=f"FM-{n:03d}", kind=kind, element=eid, element_name=element_name(m, kind, eid), guide=g, mode=a["mode"], effect=a["effect"],
                         cause=a["cause"], S=a["S"], O=a["O"], D=a["D"], AP=ap(a["S"], a["O"], a["D"]), controls=a.get("controls", ""), tests=list(a.get("tests", [])),
                         reqs=element_reqs(m, kind, eid), parts=element_parts(m, kind, eid), **structure_levels(m, kind, eid),
                         disciplines=sorted({m["parts"][p].get("discipline", "system") for p in element_parts(m, kind, eid) if p in m["parts"]})))
    return rows

def structure_levels(m, kind, eid):
    """AIAG-VDA structure analysis for an element: next higher level / focus element / next lower level, from the part tree."""
    parts = m["parts"]; alloc = [p for p in element_parts(m, kind, eid) if p in parts]
    if not alloc: return dict(higher=m["meta"].get("name", "System"), focus=element_name(m, kind, eid), lower="—")
    focus = alloc[0]; parent = parts[focus].get("parent")
    kids = [parts[c]["name"] for c, cv in parts.items() if cv.get("parent") in alloc]
    return dict(higher=parts[parent]["name"] if parent in parts else m["meta"].get("name", "System"),
                focus=", ".join(parts[p]["name"] for p in alloc[:3]), lower=", ".join(kids[:4]) or "—")

def screened(m):
    idx = _assess_index(m)
    return [dict(kind=k, element=e, element_name=element_name(m, k, e), guide=g, reason=idx[(e, g)]["ncr"]) for k, e, g in candidates(m) if (e, g) in idx and idx[(e, g)].get("ncr")]

def unassessed(m):
    idx = _assess_index(m)
    return [dict(kind=k, element=e, element_name=element_name(m, k, e), guide=g) for k, e, g in candidates(m) if (e, g) not in idx]

def verification_matrix(m):
    fm = fmea(m); rows = []
    for tid, t in m["tests"].items():
        rows.append(dict(id=tid, **t, reqs=sorted(r for r, rv in m["requirements"].items() if tid in rv["tests"]),
                         fms=sorted(f["id"] for f in fm if tid in f["tests"]), constraints=sorted(c for c, cv in m["constraints"].items() if tid in cv["tests"])))
    return rows

def certification_plan(m):
    rows = []
    for rid, reg in m["regulations"].items():
        reqs = [r for r, rv in m["requirements"].items() if rid in rv.get("regs", [])]
        tests = sorted({t for r in reqs for t in m["requirements"][r]["tests"]})
        parts = sorted({p for r in reqs for f in m["functions"].values() if r in f["reqs"] for p in f["alloc"]})
        rows.append(dict(id=rid, **reg, reqs=reqs, tests=tests, parts=parts))
    return rows

def discipline_matrix(m):
    """Requirements × disciplines: which disciplines carry each requirement (through functions → parts)."""
    out = {}
    for rid in m["requirements"]:
        ds = set()
        for f in m["functions"].values():
            if rid in f["reqs"]:
                for p in f["alloc"]:
                    if p in m["parts"]: ds.add(m["parts"][p].get("discipline", "system"))
        out[rid] = sorted(ds)
    return out

def trace(m):
    E = []
    for n, nv in m["needs"].items(): E += [(nv["stk"], "has need", n), (n, "measured by", nv["moe"])]
    for u, uv in m["use_cases"].items():
        E += [(n, "motivates", u) for n in uv["needs"]] + [(a, "participates", u) for a in uv["actors"]]
    for r, rv in m["requirements"].items():
        E += [(n, "derives", r) for n in rv["from_"]] + [(g, "imposes", r) for g in rv["regs"]] + [(t, "verifies", r) for t in rv["tests"]]
    for f, fv in m["functions"].items():
        E += [(f, "realizes", r) for r in fv["reqs"]] + [(f, "allocated to", p) for p in fv["alloc"]]
    for lc, lv in m["logical_components"].items():
        E += [(f, "partitioned into", lc) for f in lv["funcs"]] + [(lc, "realized by", p) for p in lv.get("parts", [])]
    for p, pv in m["parts"].items():
        if pv.get("parent"): E.append((pv["parent"], "contains", p))
    for i, iv in m["interfaces"].items(): E.append((iv["a"], i, iv["b"]))
    for c, cv in m["constraints"].items(): E += [(c, "constrains", r) for r in cv["reqs"]] + [(c, "evaluated by", t) for t in cv["tests"]]
    for ad, av in m["arch_decisions"].items():
        E += [(ad, "serves", r) for r in av["reqs"]]
        if av.get("trade"): E.append((av["trade"], "resolved by", ad))
    for f in fmea(m):
        E.append((f["element"], "has failure mode", f["id"])); E += [(t, "covers", f["id"]) for t in f["tests"]]
    return E

def coverage_report(m):
    fm = fmea(m); rep = {}
    rep["requirements_without_tests"] = [r for r, v in m["requirements"].items() if not v["tests"]]
    rep["requirements_not_realized_by_function"] = [r for r, v in m["requirements"].items() if v["type"] != "REGU" and not any(r in f["reqs"] for f in m["functions"].values())]
    rep["functions_without_allocation"] = [f for f, v in m["functions"].items() if not v["alloc"]]
    rep["functions_not_in_logical_component"] = [f for f in m["functions"] if not any(f in lc["funcs"] for lc in m["logical_components"].values())]
    rep["functions_in_multiple_logical_components"] = [f for f in m["functions"] if sum(f in lc["funcs"] for lc in m["logical_components"].values()) > 1]
    rep["functions_not_in_scenario"] = [f for f in m["functions"] if not any(f in s["steps"] or f in s["concurrent"] for s in m["scenarios"].values())]
    rep["tests_unreferenced"] = [t for t in m["tests"] if not any(t in v["tests"] for v in m["requirements"].values()) and not any(t in f["tests"] for f in fm)]
    rep["tests_referenced_but_undefined"] = sorted({t for v in m["requirements"].values() for t in v["tests"] if t not in m["tests"]} | {t for f in fm for t in f["tests"] if t not in m["tests"]})
    rep["fm_without_tests"] = [f["id"] for f in fm if not f["tests"]]
    rep["high_ap_fm_without_tests"] = [f["id"] for f in fm if f["AP"] == "H" and not f["tests"]]
    rep["unassessed_candidates"] = unassessed(m)
    rep["needs_without_requirements"] = [n for n, nv in m["needs"].items() if not nv.get("program") and not any(n in v["from_"] for v in m["requirements"].values())]
    rep["regulations_without_requirements"] = [g for g in m["regulations"] if not any(g in v["regs"] for v in m["requirements"].values())]
    rep["alloc_outside_logical_component"] = [(f, p) for f, v in m["functions"].items() for p in v["alloc"] for lc, lv in m["logical_components"].items() if f in lv["funcs"] and lv.get("parts") and p not in lv["parts"]]
    rep["logical_components_without_parts"] = [lc for lc, lv in m["logical_components"].items() if not lv.get("parts")]
    rep["interfaces_without_functions"] = [i for i, v in m["interfaces"].items() if not v["funcs"]]
    rep["arch_decisions_without_requirements"] = [a for a, v in m["arch_decisions"].items() if not v["reqs"]]
    rep["parts_without_discipline"] = [p for p, v in m["parts"].items() if not v.get("discipline")]
    rep["counts"] = dict(candidates=len(candidates(m)), assessed=len(fm), screened=len(screened(m)), high_ap=sum(f["AP"] == "H" for f in fm),
                         safety_class=sum(f["S"] >= 8 for f in fm), tests=len(m["tests"]), requirements=len(m["requirements"]), functions=len(m["functions"]),
                         parts=len(m["parts"]), logical_components=len(m["logical_components"]), interfaces=len(m["interfaces"]))
    rep["clean"] = bool(m["requirements"]) and bool(m["tests"]) and all(not v for k, v in rep.items() if k not in ("counts", "clean"))
    return rep

def gaps_as_tasks(m):
    """Turn the coverage report into an ordered work list an agent can act on (highest leverage first)."""
    rep = coverage_report(m); tasks = []
    order = ["needs_without_requirements", "regulations_without_requirements", "requirements_not_realized_by_function", "functions_not_in_logical_component",
             "functions_in_multiple_logical_components", "logical_components_without_parts", "functions_without_allocation", "alloc_outside_logical_component",
             "functions_not_in_scenario", "interfaces_without_functions", "unassessed_candidates", "high_ap_fm_without_tests", "fm_without_tests",
             "requirements_without_tests", "tests_referenced_but_undefined", "tests_unreferenced", "arch_decisions_without_requirements", "parts_without_discipline"]
    for k in order:
        for item in rep.get(k, []): tasks.append(dict(gap=k, item=item))
    return tasks

# ---- impact analysis and budgets (what Flow/Dalus sell as agents; here they are derived from the graph) ----
def impact(m, eid, max_depth=3):
    """Everything downstream of eid in the trace graph, by depth, plus the tests that must be re-run and the FMs to re-assess."""
    E = trace(m); fwd = {}
    BOTH = {"allocated to", "realized by", "contains", "verifies", "realizes", "covers", "constrains", "evaluated by", "imposes", "serves",
            "partitioned into", "measured by", "derives", "resolved by", "has failure mode"}
    STOP = set(m["stakeholders"]) | set(m["actors"]) | set(m["moes"])   # impact does not propagate into the stakeholder layer
    for a, rel, b in E:
        fwd.setdefault(a, []).append((rel, b))
        if rel in BOTH or rel in m["interfaces"]: fwd.setdefault(b, []).append((rel + " ←", a))
    seen = {eid: 0}; frontier = [eid]; edges = []
    for d in range(1, max_depth + 1):
        nxt = []
        for a in frontier:
            for rel, b in fwd.get(a, []):
                if b in STOP: continue
                edges.append((a, rel, b))
                if b not in seen: seen[b] = d; nxt.append(b)
        frontier = nxt
        if not frontier: break
    seen.pop(eid, None)
    fm = {f["id"]: f for f in fmea(m)}
    tests = sorted({t for x in seen for t in (m["tests"] and [x] if x in m["tests"] else [])} |
                   {t for r, rv in m["requirements"].items() if r in seen for t in rv["tests"]} |
                   {t for x in seen if x in fm for t in fm[x]["tests"]})
    reqs = [x for x in seen if x in m["requirements"]]; funcs = [x for x in seen if x in m["functions"]]; parts = [x for x in seen if x in m["parts"]]
    fms = [x for x in seen if x in fm]; decisions = [x for x in seen if x in m["arch_decisions"]]
    return {"element": eid, "affected": [{"id": k, "depth": v, "kind": next((kk for kk in m if isinstance(m[kk], dict) and k in m[kk]), "fmea" if k in fm else None)} for k, v in sorted(seen.items(), key=lambda kv: kv[1])],
            "edges": edges, "requirements": reqs, "functions": funcs, "parts": parts, "failure_modes": fms, "arch_decisions": decisions,
            "tests_to_rerun": tests, "high_ap_fms": [x for x in fms if fm[x]["AP"] == "H"]}

BUDGET_KEYS = {"mass": ("mass_g", "g"), "power": ("power_W", "W"), "cost": ("cost_usd", "USD"), "current": ("current_mA", "mA"), "volume": ("volume_cm3", "cm3")}

def _num(v):
    try: return float(str(v).split()[0].replace(",", ""))
    except Exception: return None

def budgets(m):
    """Roll numeric part attributes (mass_g, power_W, cost_usd, …) up the part tree and compare with requirement limits
    whose attr names the same quantity. Parts without a value are listed so the budget is honest about its coverage."""
    out = {}
    kids = {}
    for p, pv in m["parts"].items(): kids.setdefault(pv.get("parent"), []).append(p)
    def roll(p, key):
        own = _num(m["parts"][p].get("attrs", {}).get(key)); subs = [roll(c, key) for c in kids.get(p, [])]
        total = (own or 0.0) + sum(s[0] for s in subs); missing = ([] if own is not None or kids.get(p) else [p]) + [x for s in subs for x in s[1]]
        return total, missing
    roots = [p for p, pv in m["parts"].items() if not pv.get("parent") and kids.get(p)]
    for name, (key, unit) in BUDGET_KEYS.items():
        if not any(key in pv.get("attrs", {}) for pv in m["parts"].values()): continue
        rows = []
        for r in roots:
            total, missing = roll(r, key)
            rows.append({"root": r, "name": m["parts"][r]["name"], "total": round(total, 3), "unit": unit, "parts_without_value": missing,
                         "children": [{"id": c, "name": m["parts"][c]["name"], "value": round(roll(c, key)[0], 3)} for c in kids.get(r, [])]})
        limits = [{"req": rid, "text": rv["text"], "attr": rv.get("attr", "")} for rid, rv in m["requirements"].items() if name in (rv.get("attr", "") + " " + rv["text"]).lower() and _num(rv.get("attr", "")) is not None]
        for row in rows:
            row["limits"] = [{**l, "limit": _num(l["attr"]), "margin": round(_num(l["attr"]) - row["total"], 3)} for l in limits]
        out[name] = rows
    return out
