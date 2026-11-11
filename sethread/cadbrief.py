"""CAD brief — the design brief a part needs before anyone (a mechanical engineer, a text-to-CAD agent such as MecAgent, Zoo or
Studio, or Launch's own code-CAD generator) models it. Derived from the graph: what the part does, what it mates with and the
interface items it must carry, the requirement attributes that bound it, its budgets, materials and process, the DfX guidelines that
apply, and the failure modes to design out. Markdown, so it pastes anywhere; also returned as JSON for tool use."""
from __future__ import annotations
from . import derive as D

def brief(m: dict, pid: str) -> dict:
    p = m["parts"].get(pid)
    if not p: return {}
    kids = [c for c, v in m["parts"].items() if v.get("parent") == pid]
    parent = p.get("parent")
    funcs = [f for f, v in m["functions"].items() if pid in v.get("alloc", [])]
    reqs = sorted({r for f in funcs for r in m["functions"][f].get("reqs", [])})
    ifs = [{"id": i, **v, "other": v["b"] if v["a"] == pid else v["a"]} for i, v in m["interfaces"].items() if pid in (v.get("a"), v.get("b"))]
    fms = [x for x in D.fmea(m) if x.get("element") == pid or pid in (x.get("parts") or []) or x.get("element") in funcs]
    lcs = [lc for lc, v in m["logical_components"].items() if pid in v.get("parts", [])]
    attrs = p.get("attrs") or {}
    cons = [{"id": c, **v} for c, v in m.get("constraints", {}).items() if pid in (v.get("parts") or []) or pid in str(v)]
    regs = sorted({r for q in reqs for r in m["requirements"][q].get("regs", [])})
    dfx = []
    try:
        from . import dfx as DFX
        for s in DFX.sets():
            if s["id"] in ("manufacturing", "assembly", "maintainability", "service", "transportation", "environment"):
                dfx += [f"{s['short']} {it['id']}: {it['text']}" for it in s["items"] if it.get("check", {}).get("type") in ("manual", "attr")][:3]
    except Exception: pass
    return {"id": pid, "name": p.get("name"), "type": p.get("type"), "discipline": p.get("discipline"), "parent": parent, "children": kids, "make_buy": p.get("make_buy"), "supplier": p.get("supplier"), "owner_team": p.get("owner_team"),
            "attrs": attrs, "logical": lcs, "functions": [{"id": f, "name": m["functions"][f]["name"]} for f in funcs], "requirements": [{"id": r, "text": m["requirements"][r]["text"], "attr": m["requirements"][r].get("attr", ""), "type": m["requirements"][r].get("type")} for r in reqs],
            "interfaces": [{"id": i["id"], "name": i.get("name"), "kind": i.get("kind"), "other": i["other"], "other_name": m["parts"].get(i["other"], {}).get("name", ""), "items": i.get("items", [])} for i in ifs],
            "constraints": cons, "regulations": [{"id": r, "name": m["regulations"][r]["name"]} for r in regs], "failure_modes": [{"id": x["id"], "guide": x.get("guide"), "mode": x.get("mode"), "cause": x.get("cause"), "AP": x.get("AP")} for x in fms][:12],
            "dfx": dfx, "markdown": _md(m, pid, p, kids, funcs, reqs, ifs, fms, lcs, attrs, cons, regs, dfx)}

def _md(m, pid, p, kids, funcs, reqs, ifs, fms, lcs, attrs, cons, regs, dfx) -> str:
    L = [f"# CAD brief — {pid} {p.get('name','')}", f"*{p.get('discipline','')} · {p.get('type','')} · {p.get('make_buy','')}{' · ' + p['supplier'] if p.get('supplier') else ''}{' · in ' + p['parent'] if p.get('parent') else ''}*", ""]
    L.append("## Purpose"); L += [f"- {f}: {m['functions'][f]['name']}" for f in funcs] or ["- (no function allocated yet — allocate before modelling)"]
    if lcs: L.append(f"\nRealizes logical components: {', '.join(lcs)}")
    if kids: L.append("\n## Contains"); L += [f"- {c}: {m['parts'][c]['name']} ({m['parts'][c].get('discipline','')})" for c in kids]
    L.append("\n## Mates with / interfaces (design these first)")
    L += [f"- {i['id']} {i.get('name','')} — to **{i['other']}** {m['parts'].get(i['other'],{}).get('name','')} · {i.get('kind','')} · items: {', '.join(i.get('items',[])) or '—'}" for i in ifs] or ["- (no interfaces modelled)"]
    L.append("\n## Requirements and bounds"); L += [f"- {r} [{m['requirements'][r].get('type','')}] {m['requirements'][r]['text']}" + (f"  → **{m['requirements'][r]['attr']}**" if m['requirements'][r].get('attr') else "") for r in reqs] or ["- (none traced; the part realizes no requirement yet)"]
    if attrs: L.append("\n## Attributes / budgets"); L += [f"- {k}: {v}" for k, v in attrs.items()]
    if cons: L.append("\n## Constraints"); L += [f"- {c['id']}: {c.get('text') or c.get('name','')}" for c in cons]
    if regs: L.append("\n## Regulatory"); L += [f"- {r}: {m['regulations'][r]['name']}" for r in regs]
    if fms: L.append("\n## Failure modes to design out"); L += [f"- {x['id']} [{x.get('AP','')}] {x.get('guide','')}: {x.get('mode','')} — cause: {x.get('cause','')}" for x in fms[:12]]
    if dfx: L.append("\n## Design-for-X guidelines that apply"); L += [f"- {d}" for d in dfx]
    L.append("\n## Deliver back"); L.append(f"- Native CAD + STEP attached to {pid} with role `cad`; mass and envelope written to attrs (mass_g, envelope_mm); drawing with CTQs attached with role `drawing`.")
    return "\n".join(L)
