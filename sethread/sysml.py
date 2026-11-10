"""SysML v2 textual emitter, domain-agnostic. emit(model, outdir) -> {filename: text}

Package prefix comes from meta.name; the system-of-interest is meta.system (a part id) or the first root part
that owns children; context parts are the other root parts; item defs come from interface items; port defs
are derived per part from the interfaces it participates in."""

import os, re
from . import derive as D

def ident(s):
    s = re.sub(r"[^A-Za-z0-9_]", "_", str(s)).strip("_") or "X"
    return s if not s[0].isdigit() else "_" + s

def q(s): return str(s).replace('"', "'").replace("*/", "* /")

def _ctx(m):
    parts = m["parts"]; roots = [k for k, v in parts.items() if not v.get("parent")]
    soi = m["meta"].get("system")
    if soi not in parts:
        withkids = [r for r in roots if any(v.get("parent") == r for v in parts.values())]
        soi = withkids[0] if withkids else (roots[0] if roots else None)
    pfx = ident(m["meta"].get("name", "System"))
    soi_type = ident(parts[soi]["type"]) if soi else "System"
    soi_name = ident(parts[soi]["name"]).lower() if soi else "system"
    return dict(pfx=pfx, soi=soi, soi_type=soi_type, soi_name=soi_name, roots=roots)

def _owner_root(m, pid):
    while m["parts"][pid].get("parent"): pid = m["parts"][pid]["parent"]
    return pid

def _path(m, pid, c):
    """Qualified usage path of a part from the context: cap.array or head"""
    chain = []; p = pid
    while p: chain.append(ident(m["parts"][p]["name"]).lower()); p = m["parts"][p].get("parent")
    return ".".join(reversed(chain))

def needs_pkg(m, c):
    L = [f"package {c['pfx']}_StakeholderNeeds {{", "    // OOSEM 1: Analyze stakeholder needs", "    part def Stakeholder;"]
    for sid, s in m["stakeholders"].items():
        L.append(f"    part def <'{sid}'> {ident(s['name'])} :> Stakeholder {{ doc /* {q(s.get('role',''))}. Concerns: {q(s.get('concerns',''))} */ }}")
    L.append("")
    for mid, mo in m["moes"].items():
        L.append(f"    attribute def <'{mid}'> {ident(mo['name'])} {{ doc /* target: {q(mo.get('target',''))} */ }}")
    L.append("")
    for nid, n in m["needs"].items():
        L.append(f"    requirement <'{nid}'> {ident(nid)} {{ doc /* {q(n['text'])} */ subject stakeholder : {ident(m['stakeholders'][n['stk']]['name'])}; attribute moe : {ident(m['moes'][n['moe']]['name'])}; }}")
    L.append("}")
    return "\n".join(L)

def usecase_pkg(m, c):
    L = [f"package {c['pfx']}_UseCases {{", f"    import {c['pfx']}_Structure::*;"]
    for a, av in m["actors"].items(): L.append(f"    part def <'{a}'> {ident(av['name'])};")
    L.append("")
    for uid, u in m["use_cases"].items():
        L.append(f"    use case def <'{uid}'> {ident(u['name'])} {{")
        L.append(f"        subject {c['soi_name']} : {c['soi_type']};")
        for a in u.get("actors", []): L.append(f"        actor {ident(m['actors'][a]['name']).lower()} : {ident(m['actors'][a]['name'])};")
        for inc in u.get("includes", []): L.append(f"        include use case {ident(m['use_cases'][inc]['name']).lower()} : {ident(m['use_cases'][inc]['name'])};")
        if u.get("needs"): L.append(f"        doc /* motivated by {', '.join(u['needs'])} */")
        L.append("    }")
    L.append("}")
    return "\n".join(L)

def requirements_pkg(m, c):
    L = [f"package {c['pfx']}_Requirements {{", f"    import {c['pfx']}_Structure::*;", "    // OOSEM 2: Define system requirements"]
    for rid, r in m["requirements"].items():
        L.append(f"    requirement def <'{rid}'> {ident(rid)} {{")
        L.append(f"        doc /* [{r.get('type','')}] {q(r['text'])} */")
        L.append(f"        subject {c['soi_name']} : {c['soi_type']};")
        if r.get("attr"): L.append(f"        require constraint {{ doc /* {q(r['attr'])} */ }}")
        src = r.get("from_", []) + r.get("regs", [])
        if src or r.get("tests"): L.append(f"        doc /* derived from: {', '.join(src) or '—'}; verify by {r.get('verify','')}: {', '.join(r.get('tests', []))} */")
        L.append("    }")
    L.append("")
    seen = set()
    for f, fv in m["functions"].items():
        for p in fv.get("alloc", []):
            for r in fv.get("reqs", []):
                key = (r, p)
                if key in seen or p not in m["parts"]: continue
                seen.add(key); L.append(f"    satisfy {ident(r)} by {_path(m, p, c)};")
    L.append("")
    for tid, t in m["tests"].items():
        reqs = [r for r, rv in m["requirements"].items() if tid in rv.get("tests", [])]
        L.append(f"    verification def <'{tid}'> {ident(t['name'])} {{ subject {c['soi_name']} : {c['soi_type']}; " + " ".join(f"verify {ident(r)};" for r in reqs) + f" doc /* {q(t.get('method',''))} | pass: {q(t.get('passfail',''))} */ }}")
    L.append("}")
    return "\n".join(L)

def logical_pkg(m, c):
    L = [f"package {c['pfx']}_LogicalArchitecture {{", "    // OOSEM 3: Define logical architecture", "    abstract part def LogicalComponent;", f"    part def Logical{c['soi_type']};"]
    for lc, lv in m["logical_components"].items():
        L.append(f"    part def <'{lc}'> {ident(lv['name'])} :> LogicalComponent {{ doc /* {q(lv.get('role',''))}. Quality: {', '.join(lv.get('quality', []))} */")
        for f in lv.get("funcs", []): L.append(f"        perform action {ident(f)} : {c['pfx']}_Behavior::{ident(m['functions'][f]['name'])};")
        L.append("    }")
    L.append(f"    part logical : Logical{c['soi_type']} {{")
    for lc, lv in m["logical_components"].items(): L.append(f"        part {ident(lv['name']).lower()} : {ident(lv['name'])};")
    for li, lv in m["logical_interfaces"].items():
        L.append(f"        connect {ident(m['logical_components'][lv['a']]['name']).lower()} to {ident(m['logical_components'][lv['b']]['name']).lower()}; // {li}: {q(lv.get('flow',''))}")
    L.append("    }")
    L.append("}")
    return "\n".join(L)

def structure_pkg(m, c):
    L = [f"package {c['pfx']}_Structure {{", "    import ScalarValues::*;", "    // OOSEM 4: Physical architecture"]
    items = sorted({ident(i) for iv in m["interfaces"].values() for i in iv.get("items", [])})
    if items: L.append("    " + " ".join(f"item def {i};" for i in items))
    # port defs: one per (part, interface) side
    ports = {}
    for iid, iv in m["interfaces"].items():
        for side in ("a", "b"):
            pid = iv[side]
            if pid in m["parts"]:
                ports.setdefault(pid, []).append((iid, [ident(i) for i in iv.get("items", [])]))
    L.append("")
    done = set()
    for pid, p in m["parts"].items():
        t = ident(p["type"])
        if t in done: continue
        done.add(t)
        body = []
        body += [f"attribute {ident(k)} : String; // {q(v)}" for k, v in p.get("attrs", {}).items()]
        body += [f"part {ident(cv['name']).lower()} : {ident(cv['type'])};" for cid, cv in m["parts"].items() if cv.get("parent") == pid]
        for iid, its in ports.get(pid, []):
            body.append(f"port {ident(iid).lower()} {{ " + " ".join(f"inout item {i.lower()} : {i};" for i in its) + " }")
        disc = p.get("discipline", "system")
        L.append(f"    part def {t} {{ doc /* {pid} {q(p['name'])} [{disc}] */ " + " ".join(body) + " }")
    L.append("")
    L.append("    part context {")
    L.append("        " + " ".join(f"part {ident(m['parts'][r]['name']).lower()} : {ident(m['parts'][r]['type'])};" for r in c["roots"]))
    for iid, iv in m["interfaces"].items():
        if iv["a"] in m["parts"] and iv["b"] in m["parts"]:
            L.append(f"        connect {_path(m, iv['a'], c)}.{ident(iid).lower()} to {_path(m, iv['b'], c)}.{ident(iid).lower()}; // {iid}: {q(iv['name'])} [{iv.get('kind','')}]")
    L.append("    }")
    L.append("")
    L.append("    // Physical nodes host logical components")
    for nid, nv in m["nodes"].items():
        L.append(f"    part def <'{nid}'> {ident(nv['name'])} {{ doc /* parts: {', '.join(nv.get('parts', []))}; hosts: {', '.join(nv.get('lcs', []))} */ }}")
    L.append("    // Logical → physical allocation (OOSEM 4)")
    for lc, lv in m["logical_components"].items():
        for p in lv.get("parts", []):
            if p in m["parts"]: L.append(f"    allocate {c['pfx']}_LogicalArchitecture::{ident(lv['name'])} to {_path(m, p, c)};")
    L.append("}")
    return "\n".join(L)

def behavior_pkg(m, c):
    L = [f"package {c['pfx']}_Behavior {{", f"    import {c['pfx']}_Structure::*;"]
    for f, fv in m["functions"].items():
        sd = f" doc /* safety decision on: {q(fv['safety_decision'])} */" if fv.get("safety_decision") else ""
        L.append(f"    action def <'{f}'> {ident(fv['name'])} {{ doc /* realizes {', '.join(fv.get('reqs', []))}; perf: {q(fv.get('perf',''))} */{sd} }}")
    L.append("")
    for sid, s in m["scenarios"].items():
        L.append(f"    action def <'{sid}'> {ident(s.get('name', sid))} {{ // for {m['use_cases'][s['uc']]['name']}")
        L.append("        first start;")
        for i, st in enumerate(s.get("steps", [])):
            if st in m["functions"]: L.append(f"        then action {ident(st).lower()}_{i} : {ident(m['functions'][st]['name'])};")
        L.append("        then done;")
        for cc in s.get("concurrent", []):
            if cc in m["functions"]: L.append(f"        action {ident(cc).lower()}_mon : {ident(m['functions'][cc]['name'])}; // concurrent")
        L.append("    }")
    L.append("")
    for f, fv in m["functions"].items():
        for p in fv.get("alloc", []):
            if p in m["parts"]: L.append(f"    allocate {ident(fv['name'])} to {c['pfx']}_Structure::context::{_path(m, p, c)};")
    L.append("}")
    return "\n".join(L)

def states_pkg(m, c):
    L = [f"package {c['pfx']}_States {{", "    state def DeviceStates {"]
    init = m["meta"].get("initial_state")
    first = m["states"][init]["name"] if init in m["states"] else (next(iter(m["states"].values()))["name"] if m["states"] else None)
    if first: L.append(f"        entry; then {ident(first)};")
    for s in m["states"].values(): L.append(f"        state {ident(s['name'])};")
    for tid, t in m["transitions"].items():
        g = f" if {t['guard']}" if t.get("guard") else ""
        sens = f" // {tid}; function {t.get('func','')}" + (f"; guard sensor: {m['parts'][t['sensor']]['name']}" if t.get("sensor") in m["parts"] else "")
        L.append(f"        transition {ident(m['states'][t['frm']]['name'])} to {ident(m['states'][t['to']]['name'])} accept {ident(t['trigger'])}{g};{sens}")
    L += ["    }", "}"]
    return "\n".join(L)

def analysis_pkg(m, c):
    L = [f"package {c['pfx']}_Analysis {{", f"    import {c['pfx']}_Structure::*;", "    // OOSEM 5: Optimize and evaluate alternatives"]
    for cid, cv in m["constraints"].items():
        L.append(f"    constraint def <'{cid}'> {ident(cv['name'])} {{ doc /* {q(cv.get('formula',''))} | inputs: {', '.join(cv.get('inputs', []))} | constrains {', '.join(cv.get('reqs', []))} | evaluated by {', '.join(cv.get('tests', []))} */ }}")
    L.append(f"    analysis def QualificationAnalysis {{ subject {c['soi_name']} : {c['soi_type']}; objective {{ doc /* all constraints met at the stated reliability and confidence */ }}")
    for cid, cv in m["constraints"].items(): L.append(f"        assert constraint {ident(cid).lower()} : {ident(cv['name'])};")
    L.append("        return verdict : Boolean; }")
    L.append("")
    for tid, t in m["trades"].items():
        L.append(f"    // {tid} {q(t['name'])}: options {t.get('options', [])}; criteria {t.get('criteria', [])}; recommendation: {q(t.get('recommendation',''))}; affects {', '.join(t.get('affects', []))}")
    for ad, a in m["arch_decisions"].items():
        L.append(f"    // {ad} {q(a['title'])}: {q(a.get('decision',''))} — {q(a.get('rationale',''))}" + (f" (trade {a['trade']})" if a.get("trade") else ""))
    L.append("}")
    return "\n".join(L)

def risk_pkg(m, c):
    L = [f"package {c['pfx']}_Risk {{", "    // Derived failure modes (candidates = functions × guide words, interfaces × guide words, transitions × guide words)"]
    for f in D.fmea(m):
        L.append(f"    // {f['id']} [{f['AP']}] {f['element']} / {f['guide']}: {q(f['mode'])} → {q(f['effect'])} | cause: {q(f['cause'])} | S{f['S']} O{f['O']} D{f['D']} | controls: {q(f['controls'])} | verified by {', '.join(f['tests'])}")
    L.append("}")
    return "\n".join(L)

def emit(m, outdir="out/sysml"):
    os.makedirs(outdir, exist_ok=True); c = _ctx(m)
    files = {"01_stakeholder_needs.sysml": needs_pkg(m, c), "02_use_cases.sysml": usecase_pkg(m, c), "03_requirements.sysml": requirements_pkg(m, c),
             "04_logical_architecture.sysml": logical_pkg(m, c), "05_structure.sysml": structure_pkg(m, c), "06_behavior.sysml": behavior_pkg(m, c),
             "07_states.sysml": states_pkg(m, c), "08_analysis.sysml": analysis_pkg(m, c), "09_risk_derived.sysml": risk_pkg(m, c)}
    for n, t in files.items():
        open(os.path.join(outdir, n), "w").write(t + "\n")
    return files
