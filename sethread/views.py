"""Model views (domain-agnostic). render_all(model, outdir) -> (done, failed). Every view is a layout rule over model data."""
from __future__ import annotations
import os, math, textwrap, datetime as dt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Ellipse, Circle
from . import derive as D
from .schema import GUIDE_WORDS_FUNC, GUIDE_WORDS_IF, GUIDE_WORDS_TR

INK="#1F2A37"; QUIET="#5B6675"; EDGE="#7A8696"; GRID="#D6DCE3"; ACC="#1F6FB2"; ACC_F="#E3EEF8"; GOOD="#2E8B57"; WARN="#C98A00"; CRIT="#B23A3A"
C2="#7A4FB5"; C2F="#EFE8F8"; C3="#2B8C8C"; C3F="#E2F3F3"; C4="#B5651D"; C4F="#F8ECE1"
DPAL = {"mechanical": (C4F, C4), "textile": (C4F, C4), "chemical": (C4F, C4), "electrical": (ACC_F, ACC), "firmware": (C3F, C3), "software": (C3F, C3),
        "system": (C2F, C2), "optical": (C2F, C2), "thermal": ("#FBEAEA", CRIT), "manufacturing": ("#F3F4F6", EDGE), "external": ("white", EDGE)}
plt.rcParams["font.family"] = "DejaVu Sans"

def fig(w=13, h=7):
    f, ax = plt.subplots(figsize=(w, h), dpi=150); ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off"); return f, ax
def title(ax, t, sub=None, h=7):
    ax.text(0.3, h - 0.3, t, fontsize=14, fontweight="bold", color=INK, va="top")
    if sub: ax.text(0.3, h - 0.68, sub, fontsize=9.5, color=QUIET, va="top")
def box(ax, x, y, w, h, head, lines=(), fill="white", edge=EDGE, lw=1.3, fs=8.2, hs=9.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12", fc=fill, ec=edge, lw=lw))
    if lines:
        ax.text(x + w/2, y + h - 0.2, head, ha="center", va="top", fontsize=hs, fontweight="bold", color=INK, linespacing=1.1)
        ty = y + h - 0.5 - 0.22 * head.count("\n")
        for ln in lines: ax.text(x + 0.14, ty, ln, fontsize=fs, color=INK, va="top"); ty -= 0.22
    else: ax.text(x + w/2, y + h/2, head, ha="center", va="center", fontsize=hs, fontweight="bold", color=INK)
def arrow(ax, p, q, color=EDGE, lw=1.2, rad=0.0, ls="-", style="-|>"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=12, color=color, lw=lw, connectionstyle=f"arc3,rad={rad}", linestyle=ls))
def save(f, name, out): f.savefig(f"{out}/{name}.png", bbox_inches="tight", pad_inches=0.15, facecolor="white"); plt.close(f)
def pal(m, pid): return DPAL.get(m["parts"].get(pid, {}).get("discipline", "system"), ("white", EDGE))
def grid(ids, x0, x1, y0, y1, cols=None):
    n = max(1, len(ids)); cols = cols or max(1, math.ceil(math.sqrt(n * 1.6))); rows = math.ceil(n / cols); pos = {}
    for i, k in enumerate(ids):
        c, r = i % cols, i // cols
        pos[k] = ((x0 + (x1 - x0) * c / (cols - 1)) if cols > 1 else (x0 + x1) / 2, (y0 - (y0 - y1) * r / (rows - 1)) if rows > 1 else (y0 + y1) / 2)
    return pos, cols, rows
def wrap(s, n): return textwrap.wrap(s or "", n)

# ---------------- V01 thread ----------------
def v01_thread(m, out):
    f, ax = fig(13, 7.6); rep = D.coverage_report(m); c = rep["counts"]
    title(ax, f"{m['meta'].get('name','System')} — digital thread: downstream artifacts are queries over the model", f"trace check: {'clean' if rep['clean'] else 'gaps open'} · {len(D.trace(m))} trace edges", h=7.6)
    cols = [("Stakeholders\n& needs", f"{len(m['stakeholders'])} stakeholders\n{len(m['needs'])} needs, {len(m['moes'])} MoEs", C4F, C4),
            ("Use cases &\nscenarios", f"{len(m['use_cases'])} use cases\n{len(m['scenarios'])} scenarios", C4F, C4),
            ("Requirements", f"{c['requirements']} requirements\n{len(m['regulations'])} regulations", "#FFF8E6", WARN),
            ("Functions &\nlogical arch.", f"{c['functions']} functions\n{c['logical_components']} logical comps", C2F, C2),
            ("Physical arch.", f"{c['parts']} parts, {len(m['nodes'])} nodes\n{c['interfaces']} interfaces\n{len(m['arch_decisions'])} decisions", ACC_F, ACC),
            ("States &\nconstraints", f"{len(m['states'])} states, {len(m['transitions'])} transitions\n{len(m['constraints'])} constraints", C3F, C3)]
    x = 0.4
    for head, body, fl, ed in cols:
        box(ax, x, 4.6, 1.95, 1.7, head, body.split("\n"), fill=fl, edge=ed, fs=7.8, hs=9.2)
        if x > 0.4: arrow(ax, (x - 0.15, 5.45), (x, 5.45), color=INK)
        x += 2.1
    derived = [("FMEA (derived)", f"{c['candidates']} candidates\n{c['assessed']} assessed, {c['screened']} screened\n{c['high_ap']} High AP, {c['safety_class']} safety", "#FBEAEA", CRIT),
               ("Verification matrix", f"{c['tests']} tests, each justified\nby a requirement or FM", "#EAF5EE", GOOD),
               ("Certification plan", f"{len(m['regulations'])} regimes →\nrequirements → tests", "#EAF5EE", GOOD),
               ("Discipline matrix", "requirements × disciplines\n(mech, elec, fw, sw …)", "#EAF5EE", GOOD),
               ("Program & gates", f"{len(m['gates'])} gates with exit\ncriteria from the matrix", "#EAF5EE", GOOD)]
    x = 0.9
    for head, body, fl, ed in derived:
        box(ax, x, 1.5, 2.2, 1.6, head, body.split("\n"), fill=fl, edge=ed, fs=7.8, hs=9.2); arrow(ax, (x + 1.1, 4.55), (x + 1.1, 3.1), color=ed, lw=1.4); x += 2.4
    ax.add_patch(Rectangle((0.4, 4.45), 12.5, 0.08, fc=GRID, ec="none"))
    ax.text(6.65, 0.9, "Reliability, safety, certification and test plans are by-products: regenerated whenever the model changes.", fontsize=9, color=INK, ha="center", fontweight="bold")
    save(f, "V01_digital_thread", out)

# ---------------- V02 needs ----------------
def v02_needs(m, out):
    n_s, n_n = len(m["stakeholders"]), len(m["needs"]); H = max(6, 1.2 + 0.6 * max(n_n, n_s * 1.6))
    f, ax = fig(13, H); title(ax, "OOSEM 1 — Stakeholders, needs and measures of effectiveness", h=H)
    ys = {}
    for i, (sid, s) in enumerate(m["stakeholders"].items()):
        y = H - 1.3 - i * ((H - 2.2) / max(1, n_s - 1)) if n_s > 1 else H / 2; ys[sid] = y
        box(ax, 0.4, y - 0.4, 2.7, 0.8, s["name"][:28], [s.get("role", "")[:38]], fill=C4F, edge=C4, fs=7.2, hs=8.6)
    ny, my = {}, {}
    moes = list(m["moes"].keys())
    for i, (nid, n) in enumerate(m["needs"].items()):
        y = H - 1.1 - i * 0.6; ny[nid] = y
        ax.add_patch(FancyBboxPatch((3.9, y - 0.25), 5.6, 0.5, boxstyle="round,pad=0,rounding_size=0.08", fc="#FFF8E6", ec=WARN, lw=1.0))
        ax.text(4.0, y, f"{nid}  {n['text'][:84]}", fontsize=7.0, color=INK, va="center")
        if n["stk"] in ys: arrow(ax, (3.1, ys[n["stk"]]), (3.9, y), color=EDGE, lw=0.8)
    for i, mid in enumerate(moes):
        y = H - 1.1 - i * 0.6; my[mid] = y; mo = m["moes"][mid]
        ax.add_patch(FancyBboxPatch((10.2, y - 0.25), 2.5, 0.5, boxstyle="round,pad=0,rounding_size=0.08", fc="#EAF5EE", ec=GOOD, lw=1.0))
        ax.text(10.3, y + 0.08, mo["name"][:30], fontsize=7.4, color=INK, va="center", fontweight="bold"); ax.text(10.3, y - 0.12, (str(mo["target"]) + (" " + str(mo["unit"]) if mo.get("unit") else ""))[:40], fontsize=6.4, color=QUIET, va="center")
    for nid, n in m["needs"].items():
        if n["moe"] in my: arrow(ax, (9.5, ny[nid]), (10.2, my[n["moe"]]), color=GOOD, lw=0.8)
    save(f, "V02_stakeholder_needs", out)

# ---------------- V03 use cases ----------------
def v03_usecase(m, out):
    f, ax = fig(13, 6.8); title(ax, "OOSEM 2 — Use case view (system context)", h=6.8)
    ax.add_patch(FancyBboxPatch((3.6, 0.6), 5.8, 5.2, boxstyle="round,pad=0,rounding_size=0.15", fc="#F9F8F5", ec=INK, lw=1.4)); ax.text(3.75, 5.7, m["meta"].get("name", "System"), fontsize=10, fontweight="bold", color=INK, va="top")
    pos, _, _ = grid(list(m["use_cases"]), 4.7, 8.3, 4.9, 1.3, cols=2)
    for uid, (x, y) in pos.items():
        u = m["use_cases"][uid]
        ax.add_patch(Ellipse((x, y), 2.1, 0.66, fc="white", ec=EDGE, lw=1.3)); ax.text(x, y + 0.08, u["name"][:22], ha="center", va="center", fontsize=8.4, color=INK); ax.text(x, y - 0.17, uid, ha="center", va="center", fontsize=6.4, color=QUIET)
    acts = list(m["actors"]); half = (len(acts) + 1) // 2
    apos = {a: (1.3, 4.9 - i * (3.6 / max(1, half - 1)) if half > 1 else 3.0) for i, a in enumerate(acts[:half])}
    apos.update({a: (11.6, 4.9 - i * (3.6 / max(1, len(acts) - half - 1)) if len(acts) - half > 1 else 3.0) for i, a in enumerate(acts[half:])})
    for a, (x, y) in apos.items():
        ax.add_patch(Circle((x, y + 0.45), 0.14, fc="white", ec=INK, lw=1.2)); ax.plot([x, x], [y + 0.31, y - 0.1], color=INK, lw=1.2); ax.plot([x - 0.22, x + 0.22], [y + 0.15, y + 0.15], color=INK, lw=1.2)
        ax.plot([x, x - 0.18], [y - 0.1, y - 0.45], color=INK, lw=1.2); ax.plot([x, x + 0.18], [y - 0.1, y - 0.45], color=INK, lw=1.2); ax.text(x, y - 0.62, m["actors"][a]["name"].split(" (")[0][:16], ha="center", va="top", fontsize=8.2, color=INK, fontweight="bold")
    for uid, u in m["use_cases"].items():
        ux, uy = pos[uid]
        for a in u["actors"]:
            if a in apos: ax.plot([apos[a][0] + (0.3 if apos[a][0] < 6 else -0.3), ux + (-1.0 if apos[a][0] < 6 else 1.0)], [apos[a][1], uy], color=EDGE, lw=0.9)
        for inc in u["includes"]:
            if inc in pos: arrow(ax, (ux, uy - 0.33), (pos[inc][0], pos[inc][1] + 0.33), color=ACC, ls="--", lw=1.0)
    save(f, "V03_use_cases", out)

# ---------------- V04 requirements by type ----------------
def v04_requirements(m, out):
    types = {}
    for r, v in m["requirements"].items(): types.setdefault(v["type"], []).append(r)
    rows = max(len(v) for v in types.values()) if types else 1; H = max(5, 1.8 + 0.46 * rows)
    f, ax = fig(13, H); title(ax, f"OOSEM 2 — Requirement view: {len(m['requirements'])} requirements by type with provenance (sources → requirement → tests)", h=H)
    colw = min(1.4, 12.2 / max(1, len(types))); x = 0.4
    for t, rs in types.items():
        box(ax, x, H - 1.4, colw, 0.5, f"{t} ({len(rs)})", fill="#FFF8E6", edge=WARN, hs=7.8); y = H - 1.9
        for r in rs:
            v = m["requirements"][r]
            ax.add_patch(Rectangle((x, y - 0.42), colw, 0.4, fc="white", ec=GRID, lw=0.6))
            ax.text(x + 0.05, y - 0.1, r, fontsize=6.6, fontweight="bold", color=INK, va="top")
            ax.text(x + 0.05, y - 0.26, ("← " + ",".join(v["from_"] + [g.split("-", 1)[-1] for g in v["regs"]]))[:22], fontsize=5.4, color=QUIET, va="top")
            ax.text(x + 0.05, y - 0.37, ("→ " + ",".join(v["tests"]))[:24], fontsize=5.4, color=GOOD, va="top"); y -= 0.46
        x += colw + 0.05
    save(f, "V04_requirements", out)

# ---------------- V05 action flows ----------------
def v05_action_flows(m, out):
    n = len(m["scenarios"]); H = max(5, 1.6 + 1.55 * n)
    f, ax = fig(13, H); title(ax, "OOSEM 3 — Action flow view: scenarios decomposed into functions", h=H); y = H - 1.5
    for sid, s in m["scenarios"].items():
        ax.text(0.4, y + 0.45, f"{s['name']}  ({sid}, {m['use_cases'][s['uc']]['name']})", fontsize=9.4, fontweight="bold", color=INK); ax.add_patch(Circle((0.7, y), 0.1, color=INK))
        x = 1.05; k = len(s["steps"]); w = min(1.35, (11.6 - 0.28 * k) / max(1, k))
        for i, st in enumerate(s["steps"]):
            fv = m["functions"][st]; crit = bool(fv.get("safety_decision"))
            ax.add_patch(FancyBboxPatch((x, y - 0.26), w, 0.52, boxstyle="round,pad=0,rounding_size=0.2", fc=("#FBEAEA" if crit else "white"), ec=(CRIT if crit else EDGE), lw=1.2))
            mx = max(6, int(w * 15)); nm = fv["name"]; nm = nm if len(nm) <= mx else nm[:mx-1] + "…"
            ax.text(x + w/2, y + 0.07, nm, ha="center", va="center", fontsize=6.8, color=INK); ax.text(x + w/2, y - 0.13, st, ha="center", va="center", fontsize=6.2, color=QUIET)
            if i == 0: ax.plot([0.8, x], [y, y], color=INK, lw=1.1)
            if i < k - 1: arrow(ax, (x + w, y), (x + w + 0.28, y), color=INK, lw=1.1)
            x += w + 0.28
        ax.text(x + 0.15, y, "●", fontsize=12, color=INK, va="center")
        if s["concurrent"]: ax.text(1.05, y - 0.55, "concurrent: " + ", ".join(f"{c} {m['functions'][c]['name'][:26]}" for c in s["concurrent"])[:150], fontsize=7, color=QUIET)
        y -= 1.55
    save(f, "V05_action_flows", out)

# ---------------- V06 logical ----------------
def v06_logical(m, out):
    ids = list(m["logical_components"]); pos, cols, rows = grid(ids, 1.8, 11.25, 6.2, 2.1, cols=4); H = max(6, 2.6 + 2.0 * rows)
    pos, cols, rows = grid(ids, 1.8, 11.25, H - 2.2, 1.3, cols=4)
    f, ax = fig(13, H); title(ax, f"OOSEM 3 — Logical architecture: {len(ids)} components partition {len(m['functions'])} functions", h=H)
    W, Hb = 2.85, 1.35
    for lc, (x, y) in pos.items():
        lv = m["logical_components"][lc]
        box(ax, x - W/2, y - Hb/2, W, Hb, lv["name"][:28], [f"{lc} · " + ", ".join(lv["funcs"])[:34]] + wrap(lv["role"], 44)[:2], fill=C2F, edge=C2, fs=6.5, hs=8.4)
    for li, lv in m["logical_interfaces"].items():
        if lv["a"] not in pos or lv["b"] not in pos: continue
        p, q = pos[lv["a"]], pos[lv["b"]]; dx, dy = q[0]-p[0], q[1]-p[1]; L = max(math.hypot(dx, dy), 0.1)
        sp = (p[0] + dx/L*1.2, p[1] + dy/L*0.72); ep = (q[0] - dx/L*1.2, q[1] - dy/L*0.72)
        arrow(ax, sp, ep, color=C2, lw=1.0, style="<|-|>"); ax.text((sp[0]+ep[0])/2, (sp[1]+ep[1])/2 + 0.1, li, fontsize=6.2, color=C2, ha="center", bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none"))
    save(f, "V06_logical_architecture", out)

# ---------------- V07 nodes ----------------
def v07_physical(m, out):
    nodes = list(m["nodes"].items()); n = max(1, len(nodes)); W = min(2.4, 12.4 / n)
    f, ax = fig(13, 7.6); title(ax, "OOSEM 4 — Physical architecture: nodes, parts (coloured by discipline) and the logical components each realizes", h=7.6)
    x = 0.4
    for nd, nv in nodes:
        fl, ed = pal(m, nv["parts"][0]) if nv["parts"] else ("white", EDGE)
        parts = [m["parts"][p]["name"] for p in nv["parts"] if p in m["parts"]]
        lcs = [m["logical_components"][l]["name"] for l in nv["lcs"] if l in m["logical_components"]]
        lines = ["parts:"] + ["  " + l for l in wrap(", ".join(parts), int(W * 12))][:4] + ["realizes:"] + [f"  • {l[:28]}" for l in lcs][:9]
        box(ax, x, 1.4, W, 4.7, nv["name"][:24], lines, fill=fl, edge=ed, fs=6.8, hs=9); x += W + 0.1
    ax.text(6.5, 0.7, "Allocation rule: every function's parts ⊆ its logical component's realizing parts (checked by the trace report).", fontsize=8.2, color=QUIET, ha="center")
    save(f, "V07_physical_nodes", out)

# ---------------- V09 decomposition ----------------
def v09_decomposition(m, out):
    roots = [p for p, v in m["parts"].items() if v.get("parent") is None and not v.get("context")]
    if not roots: return
    root = roots[0]; top = [p for p, v in m["parts"].items() if v.get("parent") == root]
    depth = max([len([c for c, cv in m["parts"].items() if cv.get("parent") == t]) for t in top] or [1]); H = max(6, 3.2 + 0.45 * depth)
    f, ax = fig(13, H); title(ax, "OOSEM 4 — Part decomposition (coloured by discipline)", h=H)
    box(ax, 5.5, H - 1.4, 2.0, 0.6, f"{m['parts'][root]['name']} : {m['parts'][root]['type']}", fill=ACC_F, edge=ACC, hs=9)
    xs = {p: 1.4 + i * (11.6 / max(1, len(top))) for i, p in enumerate(top)}
    for p in top:
        v = m["parts"][p]; fl, ed = pal(m, p)
        box(ax, xs[p] - 1.1, H - 2.8, 2.2, 0.6, f"{v['name']} : {v['type']}"[:30], fill=fl, edge=ed, hs=8.2); ax.plot([6.5, 6.5, xs[p], xs[p]], [H - 1.4, H - 1.8, H - 1.8, H - 2.2], color=EDGE, lw=1.0)
        kids = [c for c, cv in m["parts"].items() if cv.get("parent") == p]
        ax.plot([xs[p], xs[p]], [H - 2.8, H - 2.8 - 0.45 * len(kids) - 0.1], color=EDGE, lw=0.9)
        for j, c in enumerate(kids):
            y = H - 2.8 - 0.45 * (j + 1); cv = m["parts"][c]
            ax.plot([xs[p], xs[p] + 0.2], [y, y], color=EDGE, lw=0.9); ax.text(xs[p] + 0.27, y, f"{cv['name']} : {cv['type']}"[:30], fontsize=7.4, color=pal(m, c)[1], va="center")
    save(f, "V09_part_decomposition", out)

# ---------------- V10 states ----------------
def v10_states(m, out):
    ids = list(m["states"]);
    if not ids: return
    pos, _, _ = grid(ids, 1.3, 11.3, 5.6, 1.4, cols=min(4, max(2, math.ceil(len(ids) / 2))))
    f, ax = fig(13, 7.4); title(ax, "OOSEM 4 — State transition view; red transitions have sensor-dependent guards (behavioral FMEA rows)", h=7.4)
    W, H = 2.0, 0.8
    for sid, (x, y) in pos.items():
        n = m["states"][sid]["name"]; fault = "fault" in n.lower()
        ax.add_patch(FancyBboxPatch((x-W/2, y-H/2), W, H, boxstyle="round,pad=0,rounding_size=0.3", fc=("#FBEAEA" if fault else "white"), ec=(CRIT if fault else EDGE), lw=1.4)); ax.text(x, y, n, ha="center", va="center", fontsize=10, fontweight="bold", color=INK)
    seen = {}
    for tid, t in m["transitions"].items():
        if t["frm"] not in pos or t["to"] not in pos: continue
        p, q = pos[t["frm"]], pos[t["to"]]; key = tuple(sorted((t["frm"], t["to"]))); k = seen.get(key, 0); seen[key] = k + 1
        col = CRIT if t.get("sensor") else EDGE
        if t["frm"] == t["to"]: arrow(ax, (p[0] + W/2, p[1] + 0.2), (p[0] + W/2, p[1] - 0.2), color=col, rad=1.2); continue
        dx, dy = q[0]-p[0], q[1]-p[1]; L = max(math.hypot(dx, dy), 0.1)
        sp = (p[0] + dx/L*W/2*0.9, p[1] + dy/L*H/2*0.9); ep = (q[0] - dx/L*W/2*0.9, q[1] - dy/L*H/2*0.9)
        arrow(ax, sp, ep, color=col, rad=0.25 if k else 0.0)
        ax.text((sp[0]+ep[0])/2, (sp[1]+ep[1])/2 + (0.22 if k == 0 else -0.22), f"{tid} {t['trigger']}" + (f" [{t['guard']}]" if t.get("guard") else ""), fontsize=6.4, color=(col if col != EDGE else QUIET), ha="center", va="center", bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.85))
    save(f, "V10_states", out)

# ---------------- V11 allocation ----------------
def v11_allocation(m, out):
    funcs = list(m["functions"]); used = {p for f in m["functions"].values() for p in f["alloc"]}; parts = [p for p in m["parts"] if p in used][:24]
    H = max(6, 2.6 + 0.24 * len(funcs)); f, ax = fig(13, H); title(ax, "OOSEM 4 — Allocation view: functions × parts (red = function on ≤ 2 parts: single-point-of-failure candidate)", h=H)
    x0, y0 = 3.6, H - 2.1; cw = min(0.47, 9.0 / max(1, len(parts))); rh = 0.24
    for j, p in enumerate(parts): ax.text(x0 + j*cw + 0.08, y0 + 0.1, m["parts"][p]["name"].replace("[*]", "")[:16], rotation=60, fontsize=6.6, ha="left", va="bottom", color=pal(m, p)[1])
    for i, fn in enumerate(funcs):
        y = y0 - i*rh; fv = m["functions"][fn]
        ax.text(x0 - 0.1, y - rh/2, f"{fn} {fv['name'][:30]}", fontsize=6.6, ha="right", va="center", color=INK)
        for j in range(len(parts)): ax.add_patch(Rectangle((x0 + j*cw, y - rh), cw, rh, fc=("#F3F4F6" if i % 2 else "white"), ec=GRID, lw=0.5))
        crit = len(fv["alloc"]) <= 2
        for p in fv["alloc"]:
            if p in parts: ax.text(x0 + parts.index(p)*cw + cw/2, y - rh/2, "X", ha="center", va="center", fontsize=7.4, fontweight="bold", color=(CRIT if crit else ACC))
    save(f, "V11_allocation", out)

# ---------------- V12 analysis ----------------
def v12_analysis(m, out):
    cs = list(m["constraints"].items()); rows = math.ceil(len(cs) / 4) or 1; H = max(5, 1.4 + 2.6 * rows)
    f, ax = fig(13, H); title(ax, "OOSEM 5 — Analysis view: constraint definitions bind model attributes to pass/fail limits", h=H)
    for i, (cid, c) in enumerate(cs):
        col, row = i % 4, i // 4; x = 0.4 + col * 3.15; y = H - 3.3 - row * 2.6
        box(ax, x, y, 3.0, 2.3, f"«constraint def»\n{c['name'][:26]}", wrap(c["formula"], 40)[:3] + [f"inputs: {', '.join(c.get('inputs', []))[:38]}", f"→ {', '.join(c['reqs'])} | {', '.join(c['tests'])[:28]}"], fill=C3F, edge=C3, fs=6.5, hs=7.8)
    save(f, "V12_analysis", out)

# ---------------- V13 FMEA coverage ----------------
def v13_fmea_coverage(m, out):
    cands = D.candidates(m); idx = {a["element"]: None for a in m["fm_assessments"].values()}
    fm = {(f["element"], f["guide"]): f for f in D.fmea(m)}; assess = {(a["element"], a["guide"]): a for a in m["fm_assessments"].values()}
    elems = list(dict.fromkeys(e for _, e, _ in cands)); gws = list(dict.fromkeys(GUIDE_WORDS_FUNC + GUIDE_WORDS_IF + GUIDE_WORDS_TR))
    H = max(6, 2.6 + 0.17 * len(elems)); f, ax = fig(13, H); title(ax, "Risk — FMEA completeness map: every element × guide word assessed (colour = Action Priority) or screened (grey); white = gap", h=H)
    x0, y0, cw, rh = 3.2, H - 1.8, 0.72, 0.17; colors = {"H": CRIT, "M": WARN, "L": GOOD}
    for j, g in enumerate(gws): ax.text(x0 + j*cw + cw/2, y0 + 0.08, g, rotation=45, fontsize=6.6, ha="left", va="bottom", color=INK)
    for i, e in enumerate(elems):
        y = y0 - i*rh; kind = "function" if e in m["functions"] else "interface" if e in m["interfaces"] else "transition"
        ax.text(x0 - 0.08, y - rh/2, f"{e} {D.element_name(m, kind, e)[:34]}", fontsize=5.4, ha="right", va="center", color=INK)
        valid = {"function": GUIDE_WORDS_FUNC, "interface": GUIDE_WORDS_IF, "transition": GUIDE_WORDS_TR}[kind]
        for j, g in enumerate(gws):
            if g not in valid: continue
            a = assess.get((e, g)); fc = "white" if a is None else "#E5E7EB" if a.get("ncr") else colors[fm[(e, g)]["AP"]]
            ax.add_patch(Rectangle((x0 + j*cw, y - rh), cw, rh, fc=fc, ec="white", lw=0.5, alpha=0.9))
            if a and not a.get("ncr"): ax.text(x0 + j*cw + cw/2, y - rh/2, fm[(e, g)]["id"][3:], fontsize=4.4, ha="center", va="center", color="white")
            elif a is None: ax.text(x0 + j*cw + cw/2, y - rh/2, "?", fontsize=5, ha="center", va="center", color=CRIT)
    c = D.coverage_report(m)["counts"]
    ax.text(0.4, 0.3, f"{c['candidates']} candidates · {c['assessed']} assessed ({c['high_ap']} High, {c['safety_class']} safety-class) · {c['screened']} screened · {len(D.unassessed(m))} unassessed", fontsize=8, color=QUIET)
    save(f, "V13_fmea_coverage", out)

# ---------------- V14 roadmap ----------------
def v14_roadmap(m, out):
    rows = [(g, v["date"], None) for g, v in m["gates"].items()] + [((l["name"], l["start"], l["end"]) if isinstance(l, dict) else tuple(l)) for l in m["program"].get("lanes", [])]
    if not rows: return
    rows.sort(key=lambda r: r[1]); ds = [dt.date.fromisoformat(r[1]) for r in rows] + [dt.date.fromisoformat(r[2]) for r in rows if r[2]]; d0, d1 = min(ds), max(ds) + dt.timedelta(days=3)
    f, ax = plt.subplots(figsize=(13, max(3.5, 0.45 * len(rows) + 1.5)), dpi=150); ax.set_xlim(d0 - dt.timedelta(days=1), d1); ax.set_ylim(-0.6, len(rows) - 0.4); ax.invert_yaxis()
    for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], fontsize=9.5, color=INK); ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_locator(matplotlib.dates.AutoDateLocator()); ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %d")); ax.tick_params(axis="x", colors=QUIET, labelsize=9); ax.grid(axis="x", color=GRID, lw=0.8)
    for i, (n, s, e) in enumerate(rows):
        s = dt.date.fromisoformat(s)
        if e is None:
            c = CRIT if n.lower() in ("launch", "ship") else INK; ax.plot([s], [i], marker="D", ms=9, color=c, zorder=3); ax.text(s + dt.timedelta(days=1.2), i, s.strftime("%b %d"), va="center", fontsize=8.5, color=QUIET)
        else:
            e = dt.date.fromisoformat(e); ax.barh(i, (e - s).days, left=s, height=0.5, color=ACC, alpha=0.85, zorder=2); ax.text(e + dt.timedelta(days=0.8), i, f"{s:%b %d} – {e:%b %d}", va="center", fontsize=8.5, color=QUIET)
    ax.set_title("Program: gates and lanes from the model", fontsize=12.5, fontweight="bold", color=INK, loc="left", pad=14); f.tight_layout(); save(f, "V14_roadmap", out)

ALL = [v01_thread, v02_needs, v03_usecase, v04_requirements, v05_action_flows, v06_logical, v07_physical, v09_decomposition, v10_states, v11_allocation, v12_analysis, v13_fmea_coverage, v14_roadmap]

def render_all(m, outdir):
    os.makedirs(outdir, exist_ok=True); done, failed = [], {}
    for fn in ALL:
        try: fn(m, outdir); done.append(fn.__name__)
        except Exception as e: failed[fn.__name__] = repr(e)
    return done, failed
