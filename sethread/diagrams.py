"""Live SysML v2 diagrams for any record or artifact, rendered from the model with Graphviz in SysML v2 notation.
Every node carries the element id as a link, so a diagram is navigation: click a box, open the record.

element(m, kind, id)   → {"svg", "text", "view"}   view chosen by kind: interconnection (parts, logical components, interfaces),
                          requirement (requirements, needs, moes, stakeholders, regulations), action (functions), state machine
                          (states, transitions), verification (tests, test runs), fault chain (fmea), subsystem boundary (teams),
                          generic neighbourhood for anything else.
artifact(m, view, …)   → whole-artifact diagrams: interconnection, logical, requirements, verification, states, fmea, process, usecases.
"""
from __future__ import annotations
import html, subprocess, re
from . import derive as D
from . import sysml as S

STEREO = {"parts": "part", "logical_components": "part", "requirements": "requirement", "needs": "requirement", "moes": "attribute", "stakeholders": "part",
          "functions": "action", "states": "state", "transitions": "transition", "tests": "verification", "test_runs": "verification", "fmea": "occurrence",
          "interfaces": "connection", "logical_interfaces": "connection", "regulations": "concern", "constraints": "constraint", "use_cases": "use case", "scenarios": "case",
          "gates": "milestone", "work_items": "item", "findings": "item", "process_steps": "action", "suppliers": "part", "teams": "package", "hazards": "concern"}
FILL = {"parts": "#eef2ff", "logical_components": "#e6f7f4", "requirements": "#fff3e0", "needs": "#fdecec", "moes": "#fdecec", "stakeholders": "#fdecec", "functions": "#e9f0ff",
        "states": "#f3e8ff", "tests": "#eefbe7", "test_runs": "#eefbe7", "fmea": "#fde8e8", "interfaces": "#f5f5f4", "logical_interfaces": "#f5f5f4", "regulations": "#fff7ed",
        "process_steps": "#faf5ff", "teams": "#f1f5f9", "use_cases": "#fdf2f8"}
DISC = {"mechanical": "#0f766e", "electrical": "#1d4ed8", "firmware": "#7e22ce", "software": "#7e22ce", "system": "#334155", "optical": "#b45309", "textile": "#9f1239"}

def _kind_of(m, eid):
    from .schema import KINDS
    for k in KINDS:
        if eid in m.get(k, {}): return k
    return "fmea" if str(eid).startswith("FM-") else None
def _nm(m, eid, k=None):
    k = k or _kind_of(m, eid)
    if k == "fmea":
        r = next((f for f in D.fmea(m) if f["id"] == eid), None); return r["mode"] if r else eid
    if not k: return eid
    v = m[k][eid]; return v.get("name") or v.get("title") or str(v.get("text", ""))[:70] or eid
def _esc(s): return html.escape(str(s or ""))
def _wrap(s, n=28):
    import textwrap; return "<BR/>".join(_esc(x) for x in textwrap.wrap(str(s or ""), n)[:4])

def node(m, eid, kind=None, focus=False, extra: list[str] | None = None, label=None):
    kind = kind or _kind_of(m, eid) or "parts"; st = STEREO.get(kind, "item"); fill = FILL.get(kind, "#ffffff")
    v = m.get(kind, {}).get(eid, {}) if kind in m else {}
    color = DISC.get(v.get("discipline", ""), "#475569") if kind == "parts" else "#475569"
    rows = [f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="8" COLOR="#64748b">«{st}»</FONT></TD></TR>', f'<TR><TD ALIGN="LEFT"><B>{_esc(eid)}</B> {_wrap(label or _nm(m, eid, kind))}</TD></TR>']
    for x in (extra or [])[:5]: rows.append(f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="8">{_wrap(x, 34)}</FONT></TD></TR>')
    pen = 2.4 if focus else 1.1
    return f'"{eid}" [label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3">{"".join(rows)}</TABLE>> shape=box style="rounded,filled" fillcolor="{fill}" color="{color}" penwidth="{pen}" URL="#el:{kind}:{eid}" tooltip="{_esc(eid)}"];'

def edge(a, b, label="", style="solid", arrow="normal", color="#475569"):
    lab = f' label=<<FONT POINT-SIZE="8" COLOR="#64748b">{_wrap(label, 22)}</FONT>>' if label else ""
    return f'"{a}" -> "{b}" [style={style} arrowhead={arrow} color="{color}"{lab}];'

HEAD = 'digraph G { graph [rankdir=LR, fontname="Inter,Helvetica", bgcolor="transparent", pad=0.2, nodesep=0.35, ranksep=0.6, splines=true]; node [fontname="Inter,Helvetica", fontsize=10]; edge [fontname="Inter,Helvetica", fontsize=8];'

def render(dot: str) -> str:
    return _render(dot)
_LAST = {}
def _rv(dot: str) -> str:
    _LAST["dot"] = dot; return _render(dot)
def _render(dot: str) -> str:
    try:
        svg = subprocess.run(["dot", "-Tsvg"], input=dot.encode(), capture_output=True, timeout=20).stdout.decode()
    except Exception as e: return f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="40"><text x="4" y="20">diagram error: {_esc(e)}</text></svg>'
    svg = re.sub(r"<\?xml.*?\?>\s*", "", svg, flags=re.S); svg = re.sub(r"<!DOCTYPE.*?>\s*", "", svg, flags=re.S)
    def _scale(mm):
        w = float(mm.group(1)) * 1.25; h = float(mm.group(2)) * 1.25; return f'<svg width="{w:.0f}" height="{h:.0f}"'
    svg = re.sub(r'<svg width="([\d.]+)pt" height="([\d.]+)pt"', _scale, svg, count=1)   # natural size, slightly enlarged; container scrolls
    return svg.replace('xlink:href="#el:', 'data-el="').replace("xlink:title", "data-title")

# ---------------------------------------------------------------- element views
def element(m, kind, eid) -> dict:
    r = _element(m, kind, eid); r["dot"] = _LAST.get("dot", ""); return r
def _element(m, kind, eid) -> dict:
    kind = kind if kind in m or kind == "fmea" else _kind_of(m, eid)
    if kind in ("parts", "logical_components"): return {"view": "interconnection", "svg": _rv(_interconnection(m, eid, kind)), "text": _text(m, kind, eid)}
    if kind in ("interfaces", "logical_interfaces"): return {"view": "interconnection", "svg": _rv(_interface(m, eid, kind)), "text": _text(m, kind, eid)}
    if kind in ("requirements", "needs", "moes", "stakeholders", "regulations", "constraints"): return {"view": "requirement", "svg": _rv(_requirement(m, eid, kind)), "text": _text(m, kind, eid)}
    if kind == "functions": return {"view": "action", "svg": _rv(_action(m, eid)), "text": _text(m, kind, eid)}
    if kind in ("states", "transitions"): return {"view": "state machine", "svg": _rv(_states(m, eid)), "text": _text(m, kind, eid)}
    if kind in ("tests", "test_runs"): return {"view": "verification", "svg": _rv(_verification(m, eid, kind)), "text": _text(m, kind, eid)}
    if kind == "fmea": return {"view": "fault chain", "svg": _rv(_fault(m, eid)), "text": _text(m, kind, eid)}
    if kind == "teams" and m["teams"].get(eid, {}).get("kind") == "subsystem": return {"view": "subsystem boundary", "svg": _rv(_subsystem(m, eid)), "text": _text(m, kind, eid)}
    return {"view": "neighbourhood", "svg": _rv(_neighbourhood(m, eid)), "text": _text(m, kind, eid)}

def _interconnection(m, eid, kind):
    L = [HEAD]; parts = m["parts"] if kind == "parts" else m["logical_components"]; ifs = m["interfaces"] if kind == "parts" else m["logical_interfaces"]
    children = [c for c, v in parts.items() if v.get("parent") == eid] if kind == "parts" else []
    L.append(f'subgraph "cluster_{eid}" {{ label=<<B>{_esc(eid)}</B> {_esc(_nm(m, eid, kind))}>; style="rounded,dashed"; color="#94a3b8"; fontsize=10;')
    L.append(node(m, eid, kind, focus=True, extra=[f"{k}: {v}" for k, v in (parts[eid].get("attrs") or {}).items()][:4] if kind == "parts" else [f"funcs: {', '.join(parts[eid].get('funcs', [])[:4])}"]))
    for c in children[:12]: L.append(node(m, c, kind)); L.append(edge(eid, c, "", "solid", "odiamond"))
    L.append("}")
    seen = set()
    for i, v in ifs.items():
        a, b = v.get("a"), v.get("b")
        if eid in (a, b) or (set(children) & {a, b}):
            other = b if a in (eid, *children) else a
            if other not in seen and other in parts: seen.add(other); L.append(node(m, other, kind))
            lab = (v.get("name") or i) + ((" · " + ", ".join(v.get("items", [])[:3])) if v.get("items") else (" · " + v.get("flow", "")[:40] if v.get("flow") else ""))
            L.append(edge(a, b, lab, "solid", "none", "#1d4ed8"))
    # allocated functions and requirements satisfied (dashed, SysML allocate / satisfy)
    funcs = [f for f, v in m["functions"].items() if eid in v.get("alloc", [])] if kind == "parts" else parts[eid].get("funcs", [])
    for f in funcs[:6]: L.append(node(m, f, "functions")); L.append(edge(f, eid, "allocate", "dashed", "open", "#7e22ce"))
    reqs = sorted({r for f in funcs for r in m["functions"].get(f, {}).get("reqs", [])})[:6]
    for r in reqs: L.append(node(m, r, "requirements")); L.append(edge(eid, r, "satisfy", "dashed", "open", "#c2410c"))
    if kind == "parts":
        for lc, v in m["logical_components"].items():
            if eid in v.get("parts", []): L.append(node(m, lc, "logical_components")); L.append(edge(eid, lc, "realizes", "dashed", "open", "#0f766e"))
    L.append("}"); return "\n".join(L)

def _interface(m, eid, kind):
    v = (m["interfaces"] if kind == "interfaces" else m["logical_interfaces"])[eid]; pk = "parts" if kind == "interfaces" else "logical_components"
    L = [HEAD, node(m, v["a"], pk), node(m, v["b"], pk), edge(v["a"], v["b"], (v.get("name") or eid) + " · " + (", ".join(v.get("items", [])) or v.get("flow", "")), "solid", "none", "#1d4ed8")]
    for f in v.get("funcs", [])[:6]: L.append(node(m, f, "functions")); L.append(edge(f, v["a"], "carried by " + eid, "dashed", "open", "#7e22ce"))
    for x in D.fmea(m):
        if x.get("element") == eid: L.append(node(m, x["id"], "fmea", label=x["mode"])); L.append(edge(x["id"], v["a"], x["guide"], "dotted", "open", "#b91c1c"))
    L.append("}"); return "\n".join(L)

def _requirement(m, eid, kind):
    L = [HEAD]; seen = set()
    def add(x, k=None, focus=False):
        if x in seen or not x: return
        seen.add(x); L.append(node(m, x, k, focus=focus))
    add(eid, kind, True)
    if kind == "requirements":
        v = m["requirements"][eid]
        for n in v.get("from_", []): add(n, "needs"); L.append(edge(eid, n, "derive", "dashed", "open", "#b91c1c"))
        for r in v.get("regs", []): add(r, "regulations"); L.append(edge(eid, r, "refine", "dashed", "open", "#b45309"))
        for f in v.get("functions", []) or [f for f, fv in m["functions"].items() if eid in fv.get("reqs", [])]:
            add(f, "functions"); L.append(edge(f, eid, "satisfy", "dashed", "open", "#7e22ce"))
            for p in m["functions"].get(f, {}).get("alloc", [])[:3]: add(p, "parts"); L.append(edge(p, f, "allocate", "dashed", "open", "#1d4ed8"))
        for t in v.get("tests", []): add(t, "tests"); L.append(edge(t, eid, "verify", "dashed", "open", "#15803d"))
        for x in D.fmea(m):
            if eid in (x.get("reqs") or []): add(x["id"], "fmea"); L.append(edge(x["id"], eid, "threatens", "dotted", "open", "#b91c1c"))
    elif kind == "needs":
        v = m["needs"][eid]; add(v.get("stk"), "stakeholders"); L.append(edge(v["stk"], eid, "has need", "solid", "open")); add(v.get("moe"), "moes"); L.append(edge(eid, v["moe"], "measured by", "dashed", "open"))
        for r, rv in m["requirements"].items():
            if eid in rv.get("from_", []): add(r, "requirements"); L.append(edge(r, eid, "derive", "dashed", "open", "#b91c1c"))
    elif kind == "stakeholders":
        for n, nv in m["needs"].items():
            if nv.get("stk") == eid: add(n, "needs"); L.append(edge(eid, n, "has need", "solid", "open"))
    elif kind == "moes":
        for n, nv in m["needs"].items():
            if nv.get("moe") == eid: add(n, "needs"); L.append(edge(n, eid, "measured by", "dashed", "open"))
    elif kind == "regulations":
        for r, rv in m["requirements"].items():
            if eid in rv.get("regs", []): add(r, "requirements"); L.append(edge(r, eid, "refine", "dashed", "open", "#b45309"))
    L.append("}"); return "\n".join(L)

def _action(m, eid):
    v = m["functions"][eid]; L = [HEAD, node(m, eid, "functions", focus=True)]
    for r in v.get("reqs", []): L.append(node(m, r, "requirements")); L.append(edge(eid, r, "satisfy", "dashed", "open", "#c2410c"))
    for p in v.get("alloc", []): L.append(node(m, p, "parts")); L.append(edge(eid, p, "allocate", "dashed", "open", "#1d4ed8"))
    for lc, lv in m["logical_components"].items():
        if eid in lv.get("funcs", []): L.append(node(m, lc, "logical_components")); L.append(edge(lc, eid, "performs", "solid", "open", "#0f766e"))
    for i, iv in m["interfaces"].items():
        if eid in iv.get("funcs", []): L.append(node(m, i, "interfaces")); L.append(edge(eid, i, "flows over", "dotted", "open"))
    for x in D.fmea(m):
        if x.get("element") == eid: L.append(node(m, x["id"], "fmea", label=x["mode"])); L.append(edge(eid, x["id"], x["guide"], "dotted", "open", "#b91c1c"))
    for t, tv in m["transitions"].items():
        if tv.get("func") == eid: L.append(node(m, tv["frm"], "states")); L.append(node(m, tv["to"], "states")); L.append(edge(tv["frm"], tv["to"], f"{t}: {tv.get('trigger','')}", "solid", "normal", "#7e22ce"))
    L.append("}"); return "\n".join(L)

def _states(m, focus_id):
    L = [HEAD.replace("rankdir=LR", "rankdir=LR")]
    for s_, v in m["states"].items():
        f = s_ == focus_id or any(t == focus_id and (tv["frm"] == s_ or tv["to"] == s_) for t, tv in m["transitions"].items())
        L.append(f'"{s_}" [label=<<FONT POINT-SIZE="8" COLOR="#64748b">«state»</FONT><BR/><B>{_esc(s_)}</B> {_esc(v.get("name",""))}> shape=box style="rounded,filled" fillcolor="#f3e8ff" color="#7e22ce" penwidth="{2.4 if f else 1}" URL="#el:states:{s_}"];')
    for t, tv in m["transitions"].items():
        lab = f"{t}: {tv.get('trigger','')}" + (f" [{tv['guard']}]" if tv.get("guard") else "") + (f" / {tv['func']}" if tv.get("func") else "")
        L.append(f'"{tv["frm"]}" -> "{tv["to"]}" [label=<<FONT POINT-SIZE="8">{_wrap(lab, 30)}</FONT>> color="{"#b91c1c" if t == focus_id else "#475569"}" penwidth="{2 if t == focus_id else 1}" URL="#el:transitions:{t}"];')
    L.append("}"); return "\n".join(L)

def _verification(m, eid, kind):
    L = [HEAD]
    tid = eid if kind == "tests" else m["test_runs"][eid]["test"]
    L.append(node(m, tid, "tests", focus=kind == "tests", extra=[m["tests"][tid].get("method", "")[:60], "status: " + m["tests"][tid].get("status", "planned")]))
    for r, rv in m["requirements"].items():
        if tid in rv.get("tests", []):
            L.append(node(m, r, "requirements")); L.append(edge(tid, r, "verify", "dashed", "open", "#15803d"))
            for f in [f for f, fv in m["functions"].items() if r in fv.get("reqs", [])][:3]: L.append(node(m, f, "functions")); L.append(edge(f, r, "satisfy", "dashed", "open", "#7e22ce"))
    for x in D.fmea(m):
        if tid in (x.get("tests") or []): L.append(node(m, x["id"], "fmea", label=x["mode"])); L.append(edge(tid, x["id"], "detects", "dotted", "open", "#b91c1c"))
    for r, rv in m.get("test_runs", {}).items():
        if rv["test"] == tid: L.append(node(m, r, "test_runs", focus=r == eid, label=f"{rv['result']} · {rv['date']}")); L.append(edge(r, tid, "result of", "solid", "open", "#15803d"))
    L.append("}"); return "\n".join(L)

def _fault(m, eid):
    x = next((f for f in D.fmea(m) if f["id"] == eid), None); L = [HEAD]
    if not x: L.append("}"); return "\n".join(L)
    L.append(f'"cause" [label=<<FONT POINT-SIZE="8" COLOR="#64748b">«cause»</FONT><BR/>{_wrap(x.get("cause",""), 30)}> shape=box style="rounded,filled" fillcolor="#fff7ed" color="#b45309"];')
    L.append(node(m, eid, "fmea", focus=True, label=x["mode"], extra=[f"S {x.get('S')} · O {x.get('O')} · D {x.get('D')} · AP {x.get('AP')}", "controls: " + (x.get("controls") or "—")]))
    L.append(f'"effect" [label=<<FONT POINT-SIZE="8" COLOR="#64748b">«effect»</FONT><BR/>{_wrap(x.get("effect",""), 30)}> shape=box style="rounded,filled" fillcolor="#fde8e8" color="#b91c1c"];')
    L.append(edge("cause", eid, "", "solid", "normal", "#b45309")); L.append(edge(eid, "effect", x.get("guide", ""), "solid", "normal", "#b91c1c"))
    L.append(node(m, x["element"], x["kind"] if x["kind"] in m else None)); L.append(edge(x["element"], eid, "has failure mode", "dotted", "open"))
    for p in (x.get("parts") or [])[:4]: L.append(node(m, p, "parts")); L.append(edge(p, "cause", "", "dotted", "none", "#94a3b8"))
    for r in (x.get("reqs") or [])[:4]: L.append(node(m, r, "requirements")); L.append(edge(eid, r, "threatens", "dotted", "open", "#b91c1c"))
    for t in (x.get("tests") or [])[:5]: L.append(node(m, t, "tests")); L.append(edge(t, eid, "detects", "dashed", "open", "#15803d"))
    L.append("}"); return "\n".join(L)

def _subsystem(m, tid):
    from .lifecycle import subsystem_scope
    s = subsystem_scope(m, m["teams"][tid]); L = [HEAD]
    L.append(f'subgraph "cluster_{tid}" {{ label=<<B>{_esc(m["teams"][tid]["name"])}</B> «subsystem»>; style="rounded,filled"; fillcolor="#f8fafc"; color="#334155"; fontsize=11;')
    for p in s["parts"][:30]: L.append(node(m, p, "parts"))
    for i in s["interfaces_internal"]: v = m["interfaces"][i]; L.append(edge(v["a"], v["b"], v.get("name") or i, "solid", "none", "#1d4ed8"))
    L.append("}")
    for b in s["boundary"]:
        L.append(node(m, b["outside"], "parts")); L.append(edge(b["a"], b["b"], (b.get("name") or b["id"]) + " · " + ", ".join(b.get("items", [])[:3]), "bold", "none", "#c2410c"))
    L.append("}"); return "\n".join(L)

def _neighbourhood(m, eid):
    L = [HEAD, node(m, eid, focus=True)]; n = 0
    for a, rel, b in D.trace(m):
        if eid in (a, b) and n < 24:
            other = b if a == eid else a; k = _kind_of(m, other)
            if not k: continue
            L.append(node(m, other, k)); L.append(edge(a, b, rel, "dashed", "open")); n += 1
    L.append("}"); return "\n".join(L)

# ---------------------------------------------------------------- artifact views
ARTIFACT_VIEWS = {"interconnection": "Physical interconnection (parts, ports, connections)", "logical": "Logical architecture (components, flows)", "requirements": "Requirements (derive / satisfy / verify)",
                  "verification": "Verification (tests → requirements → functions)", "states": "State machine", "fmea": "Failure network (High-AP modes → parts, tests)", "process": "Process flow (steps, parts consumed, PFMEA)", "usecases": "Use cases (actors, functions)"}

def artifact(m, view, ids: list | None = None) -> dict:
    L = [HEAD]; ids = set(ids or [])
    if view == "interconnection":
        roots = [p for p, v in m["parts"].items() if not v.get("parent")]
        def cl(p, depth=0):
            kids = [c for c, v in m["parts"].items() if v.get("parent") == p]
            if kids and depth < 2:
                L.append(f'subgraph "cluster_{p}" {{ label=<<B>{_esc(p)}</B> {_esc(_nm(m, p, "parts"))}>; style="rounded,dashed"; color="#94a3b8"; URL="#el:parts:{p}";')
                for c in kids: cl(c, depth + 1)
                L.append("}")
            else: L.append(node(m, p, "parts", focus=p in ids))
        for r in roots: cl(r)
        for i, v in m["interfaces"].items(): L.append(edge(v["a"], v["b"], (v.get("name") or i)[:40], "solid", "none", "#1d4ed8"))
    elif view == "logical":
        for lc in m["logical_components"]: L.append(node(m, lc, "logical_components", focus=lc in ids, extra=[", ".join(m["logical_components"][lc].get("funcs", [])[:5])]))
        for i, v in m["logical_interfaces"].items(): L.append(edge(v["a"], v["b"], (v.get("flow") or i)[:40], "solid", "none", "#0f766e"))
    elif view == "requirements":
        for n, v in m["needs"].items(): L.append(node(m, n, "needs"))
        for r, v in m["requirements"].items():
            L.append(node(m, r, "requirements", focus=r in ids))
            for n in v.get("from_", []): L.append(edge(r, n, "derive", "dashed", "open", "#b91c1c"))
            for t in v.get("tests", []): L.append(node(m, t, "tests")); L.append(edge(t, r, "verify", "dashed", "open", "#15803d"))
    elif view == "verification":
        for t, v in m["tests"].items(): L.append(node(m, t, "tests", focus=t in ids, extra=["status: " + v.get("status", "planned")]))
        for r, v in m["requirements"].items():
            if v.get("tests"): L.append(node(m, r, "requirements"))
            for t in v.get("tests", []): L.append(edge(t, r, "verify", "dashed", "open", "#15803d"))
    elif view == "states": return {"view": view, "svg": _rv(_states(m, next(iter(ids), ""))), "dot": _LAST.get("dot", ""), "title": ARTIFACT_VIEWS[view]}
    elif view == "fmea":
        for x in D.fmea(m):
            if x.get("AP") == "H" or x["id"] in ids:
                L.append(node(m, x["id"], "fmea", focus=x["id"] in ids, label=x["mode"], extra=[f"AP {x.get('AP')} · S{x.get('S')} O{x.get('O')} D{x.get('D')}"]))
                L.append(node(m, x["element"], x["kind"] if x["kind"] in m else None)); L.append(edge(x["element"], x["id"], x["guide"], "dotted", "open", "#b91c1c"))
                for t in (x.get("tests") or [])[:3]: L.append(node(m, t, "tests")); L.append(edge(t, x["id"], "detects", "dashed", "open", "#15803d"))
    elif view == "process":
        prev = None
        for p, v in sorted(m.get("process_steps", {}).items(), key=lambda kv: kv[1].get("order", 0)):
            L.append(node(m, p, "process_steps", focus=p in ids, extra=[v.get("station", ""), "consumes: " + ", ".join(v.get("parts", [])[:4])]))
            if prev: L.append(edge(prev, p, "", "solid", "normal"))
            prev = p
            for x in D.fmea(m):
                if x.get("element") == p and x.get("AP") == "H": L.append(node(m, x["id"], "fmea", label=x["mode"])); L.append(edge(p, x["id"], x["guide"], "dotted", "open", "#b91c1c"))
    elif view == "usecases":
        for a in m["actors"]: L.append(node(m, a, "stakeholders"))
        for u, v in m["use_cases"].items():
            L.append(node(m, u, "use_cases", focus=u in ids))
            for a in v.get("actors", []): L.append(edge(a, u, "", "solid", "none"))
            for f in v.get("funcs", [])[:6]: L.append(node(m, f, "functions")); L.append(edge(u, f, "include", "dashed", "open", "#7e22ce"))
    L.append("}"); return {"view": view, "svg": _rv("\n".join(L)), "dot": _LAST.get("dot", ""), "title": ARTIFACT_VIEWS.get(view, view)}

# ---------------------------------------------------------------- SysML v2 textual excerpt for a record
def _text(m, kind, eid) -> str:
    v = m.get(kind, {}).get(eid, {}) if kind in m else {}
    i = S.ident(eid) if hasattr(S, "ident") else eid
    if kind == "parts":
        kids = [c for c, cv in m["parts"].items() if cv.get("parent") == eid]
        lines = [f"part def {S.ident(v.get('type') or eid)} {{", *[f"    attribute {k} = {S.q(x)};" for k, x in (v.get("attrs") or {}).items()], *[f"    part {S.ident(c)} : {S.ident(m['parts'][c].get('type') or c)};" for c in kids]]
        for ifc, iv in m["interfaces"].items():
            if eid in (iv.get("a"), iv.get("b")): lines.append(f"    port {S.ident(ifc)} : ~{S.ident(iv.get('name') or ifc)}Port; // {', '.join(iv.get('items', []))}")
        for f, fv in m["functions"].items():
            if eid in fv.get("alloc", []): lines.append(f"    perform action {S.ident(f)}; // {fv.get('name','')}")
        lines.append("}")
        return "\n".join(lines)
    if kind == "requirements":
        return "\n".join([f"requirement def {S.ident(eid)} {{", f"    doc /* {S.q(v.get('text',''))} */", *(["    attribute " + S.q(v["attr"]) + ";"] if v.get("attr") else []), *[f"    satisfy by {S.ident(f)};" for f, fv in m["functions"].items() if eid in fv.get("reqs", [])], *[f"    verify by {S.ident(t)};" for t in v.get("tests", [])], "}"])
    if kind == "functions":
        return "\n".join([f"action def {S.ident(eid)} {{ // {S.q(v.get('name',''))}", *[f"    satisfy requirement {S.ident(r)};" for r in v.get("reqs", [])], *[f"    allocate to {S.ident(p)};" for p in v.get("alloc", [])], "}"])
    if kind == "interfaces":
        return f"interface def {S.ident(eid)} {{ // {S.q(v.get('name',''))}\n    end a : {S.ident(v.get('a',''))}; end b : {S.ident(v.get('b',''))};\n" + "".join(f"    flow {S.ident(x)};\n" for x in v.get("items", [])) + "}"
    if kind == "states":
        outs = [f"    transition {S.ident(t)} first {S.ident(eid)} accept {S.q(tv.get('trigger',''))} then {S.ident(tv['to'])};" for t, tv in m["transitions"].items() if tv.get("frm") == eid]
        return "\n".join([f"state {S.ident(eid)} {{ // {S.q(v.get('name',''))}", *outs, "}"])
    if kind == "tests":
        return "\n".join([f"verification def {S.ident(eid)} {{ // {S.q(v.get('name',''))}", f"    doc /* method: {S.q(v.get('method',''))}; pass/fail: {S.q(v.get('passfail',''))} */", *[f"    verify requirement {S.ident(r)};" for r, rv in m['requirements'].items() if eid in rv.get('tests', [])], "}"])
    if kind == "fmea":
        x = next((f for f in D.fmea(m) if f["id"] == eid), None)
        return f"occurrence def {S.ident(eid)} {{ // failure mode of {x['element']}: {S.q(x['mode'])}\n    doc /* cause: {S.q(x.get('cause',''))}; effect: {S.q(x.get('effect',''))}; S={x.get('S')} O={x.get('O')} D={x.get('D')} AP={x.get('AP')} */\n}}" if x else ""
    return f"// {kind} {eid}\n" + "\n".join(f"// {k}: {S.q(str(x))[:120]}" for k, x in list(v.items())[:12])

# ---------------------------------------------------------------- where used: every artifact and record that carries an element
def where_used(m, eid, store=None, threads=None, project_root=None) -> list[dict]:
    from . import forms as F
    out = []; kind = _kind_of(m, eid)
    for name, (title, std, fn) in F.FORMS.items():
        try:
            groups, headers, widths, rows = fn(m); hit = [i for i, r in enumerate(rows) if any(eid == c or (isinstance(c, (list, tuple, set)) and eid in c) or (isinstance(c, str) and re.search(rf"\b{re.escape(eid)}\b", c)) for c in r)]
        except Exception: hit = []
        if hit: out.append({"type": "form", "id": name, "name": title, "rows": len(hit), "link": f"/form/{name}"})
    for lc, v in m.get("teams", {}).items():
        if v.get("kind") == "subsystem":
            from .lifecycle import subsystem_scope
            s = subsystem_scope(m, v)
            if eid in s["parts"] or eid in s["functions"] or eid in s["requirements"] or eid in s["interfaces_boundary"] or eid in s["tests"]: out.append({"type": "team", "id": lc, "name": v["name"] + " (subsystem scope)", "link": f"/team/{lc}"})
        elif v.get("members") and kind == "parts" and m["parts"][eid].get("owner_team") == lc: out.append({"type": "team", "id": lc, "name": v["name"], "link": f"/team/{lc}"})
    for t, v in m.get("tables", {}).items():
        n = sum(1 for r in v.get("rows", []) if any(x == eid for x in r.values()))
        if n: out.append({"type": "table", "id": t, "name": v["name"], "rows": n, "link": f"/table/{t}"})
    for n, v in m.get("notes", {}).items():
        if eid in (v.get("elements") or []) or re.search(rf"\b{re.escape(eid)}\b", v.get("body", "")): out.append({"type": "note", "id": n, "name": v["title"], "link": f"/note/{n}"})
    for r, v in m.get("dfx_reviews", {}).items():
        for iid, it in (v.get("items") or {}).items():
            if isinstance(it, dict) and eid in (it.get("evidence") or []): out.append({"type": "dfx", "id": v.get("x"), "name": f"DfX {v.get('x')} · {iid[:20]}", "link": f"/dfx/{v.get('x')}"})
    for d, v in m.get("deliverables", {}).items():
        if v.get("team") == eid: out.append({"type": "deliverable", "id": d, "name": v["name"], "link": "/pdp"})
    for r, v in m.get("test_runs", {}).items():
        if v.get("test") == eid: out.append({"type": "run", "id": r, "name": f"{r} · {v['result']}", "link": f"/run/{r}"})
    for w, v in m.get("work_items", {}).items():
        if eid in (v.get("links") or []): out.append({"type": "work item", "id": w, "name": v["title"], "link": f"/element/work_items/{w}"})
    for f, v in m.get("findings", {}).items():
        if eid in (v.get("links") or []) or v.get("element") == eid: out.append({"type": "finding", "id": f, "name": v["title"], "link": f"/element/findings/{f}"})
    for h, v in m.get("handoffs", {}).items():
        if eid in (v.get("links") or []): out.append({"type": "handoff", "id": h, "name": v["what"], "link": f"/element/handoffs/{h}"})
    for a, v in m.get("attachments", {}).items():
        if v.get("element") == eid: out.append({"type": "file", "id": a, "name": f"{v['title']} ({v['role']})", "link": f"/element/{kind}/{eid}"})
    for t in (threads or []):
        if eid in (t.get("title", "") + " " + t.get("last", "")): out.append({"type": "conversation", "id": t["id"], "name": t["title"], "link": f"/chat/{t['id']}"})
    for g, v in m["gates"].items():
        if kind == "tests" and m["tests"][eid].get("gate") == g: out.append({"type": "gate", "id": g, "name": g, "link": f"/element/gates/{g}"})
    return out
