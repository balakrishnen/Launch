"""Model views (domain-agnostic). render_all(model, outdir) -> (done, failed). Every view is a layout rule over model data."""
from __future__ import annotations
import os, math, textwrap, datetime as dt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Ellipse, Circle
from . import derive as D
from .schema import GUIDE_WORDS_FUNC, GUIDE_WORDS_IF, GUIDE_WORDS_TR, GUIDE_WORDS_PROC

INK="#1F2A37"; QUIET="#5B6675"; EDGE="#7A8696"; GRID="#D6DCE3"; ACC="#1F6FB2"; ACC_F="#E3EEF8"; GOOD="#2E8B57"; WARN="#C98A00"; CRIT="#B23A3A"
C2="#7A4FB5"; C2F="#EFE8F8"; C3="#2B8C8C"; C3F="#E2F3F3"; C4="#B5651D"; C4F="#F8ECE1"
DPAL = {"mechanical": (C4F, C4), "textile": (C4F, C4), "chemical": (C4F, C4), "electrical": (ACC_F, ACC), "firmware": (C3F, C3), "software": (C3F, C3),
        "system": (C2F, C2), "optical": (C2F, C2), "thermal": ("#FBEAEA", CRIT), "manufacturing": ("#F3F4F6", EDGE), "external": ("white", EDGE)}
plt.rcParams["font.family"] = "DejaVu Sans"

def fig(w=13, h=7):
    f, ax = plt.subplots(figsize=(w, h), dpi=150); ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off"); return f, ax
def _width(ax, t):
    """Rendered width of a text artist in data units (measured through the axes transform, so axes margins are accounted for)."""
    r = ax.figure.canvas.get_renderer(); bb = t.get_window_extent(renderer=r)
    (x0, _), (x1, _) = ax.transData.inverted().transform([[bb.x0, 0], [bb.x1, 0]]); return x1 - x0
def fit(ax, x, y, s, maxw, fs, min_fs=5.0, **kw):
    """Place text and shrink it until it fits maxw (inches); nothing ever runs past its box."""
    t = ax.text(x, y, s, fontsize=fs, **kw)
    while fs > min_fs and _width(ax, t) > maxw: fs -= 0.3; t.set_fontsize(fs)
    return t
def title(ax, t, sub=None, h=7, w=13):
    t = t.replace(" — ", ": ")
    fit(ax, 0.3, h - 0.3, t, w - 0.6, 14, min_fs=9, fontweight="bold", color=INK, va="top")
    if sub: fit(ax, 0.3, h - 0.68, sub, w - 0.6, 9.5, color=QUIET, va="top")
def box(ax, x, y, w, h, head, lines=(), fill="white", edge=EDGE, lw=1.3, fs=8.2, hs=9.4):
    """Rounded box with a bold head and body lines. Text is fitted to the width, and the line pitch to the height."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12", fc=fill, ec=edge, lw=lw))
    inner = w - 0.26
    if not lines:
        fit(ax, x + w/2, y + h/2, head, inner, hs, ha="center", va="center", fontweight="bold", color=INK, linespacing=1.15); return
    hl = head.count("\n") + 1
    fit(ax, x + w/2, y + h - 0.16, head, inner, hs, ha="center", va="top", fontweight="bold", color=INK, linespacing=1.15)
    top = y + h - 0.2 - hl * hs * 1.25 / 72 - 0.08; room = top - (y + 0.1)
    pitch = min(0.22, room / max(1, len(lines))); bfs = min(fs, pitch * 72 / 1.3)
    ty = top
    for ln in lines: fit(ax, x + 0.13, ty, ln, inner, bfs, color=INK, va="top"); ty -= pitch
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

# Graphviz for the network views (states, logical architecture, use cases): a real layout engine routes edges around
# boxes and places every label without overlap, which a fixed grid cannot do once a graph has more than a few edges.
def _h(s): return (str(s or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
def _wrapbr(s, n, align="left"): return f'<br align="{align}"/>'.join(_h(l) for l in wrap(s, n)) + (f'<br align="{align}"/>' if align != "center" and s else "")
def dot(src, name, out):
    import subprocess
    r = subprocess.run(["dot", "-Tpng", "-Gdpi=150", "-o", f"{out}/{name}.png"], input=src.encode(), capture_output=True, timeout=60)
    if r.returncode: raise RuntimeError(r.stderr.decode()[:300])
def _graph(t, rankdir="LR", extra=""):
    return (f'digraph G {{ graph [rankdir={rankdir}, bgcolor=white, pad=0.35, nodesep=0.55, ranksep=0.9, fontname="DejaVu Sans", '
            f'label=<<b>{_h(t.replace(" — ", ": "))}</b>>, labelloc=t, labeljust=l, fontsize=20, fontcolor="{INK}", splines=true, {extra}]\n'
            f'node [fontname="DejaVu Sans", fontcolor="{INK}", color="{EDGE}", penwidth=1.5]\n'
            f'edge [fontname="DejaVu Sans", fontsize=10, color="{EDGE}", fontcolor="{QUIET}", arrowsize=0.8, penwidth=1.3]\n')

# ---------------- V01 thread ----------------
def v01_thread(m, out):
    f, ax = fig(13, 7.6); rep = D.coverage_report(m); c = rep["counts"]
    title(ax, f"{m['meta'].get('name','System')}: digital thread: downstream artifacts are queries over the model", f"trace check: {'clean' if rep['clean'] else 'gaps open'} · {len(D.trace(m))} trace edges", h=7.6)
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
        box(ax, 0.4, y - 0.45, 2.7, 0.9, s["name"], wrap(s.get("role", ""), 44)[:2], fill=C4F, edge=C4, fs=7.2, hs=8.6)
    ny, my = {}, {}
    moes = list(m["moes"].keys())
    for i, (nid, n) in enumerate(m["needs"].items()):
        y = H - 1.1 - i * 0.6; ny[nid] = y
        ax.add_patch(FancyBboxPatch((3.9, y - 0.25), 5.6, 0.5, boxstyle="round,pad=0,rounding_size=0.08", fc="#FFF8E6", ec=WARN, lw=1.0))
        fit(ax, 4.0, y, f"{nid}  {n['text']}", 5.4, 7.0, color=INK, va="center")
        if n["stk"] in ys: arrow(ax, (3.1, ys[n["stk"]]), (3.9, y), color=EDGE, lw=0.8)
    for i, mid in enumerate(moes):
        y = H - 1.1 - i * 0.6; my[mid] = y; mo = m["moes"][mid]
        ax.add_patch(FancyBboxPatch((10.2, y - 0.27), 2.6, 0.54, boxstyle="round,pad=0,rounding_size=0.08", fc="#EAF5EE", ec=GOOD, lw=1.0))
        fit(ax, 10.28, y + 0.12, mo["name"], 2.44, 7.4, color=INK, va="center", fontweight="bold")
        tl = wrap(str(mo["target"]) + (" " + str(mo["unit"]) if mo.get("unit") else ""), 52)
        for k, ln in enumerate(tl[:2]): fit(ax, 10.28, y - 0.05 - 0.13 * k, ln + ("…" if k == 1 and len(tl) > 2 else ""), 2.44, 5.8, color=QUIET, va="center")
    for nid, n in m["needs"].items():
        if n["moe"] in my: arrow(ax, (9.5, ny[nid]), (10.2, my[n["moe"]]), color=GOOD, lw=0.8)
    save(f, "V02_stakeholder_needs", out)

# ---------------- V03 use cases ----------------
def v03_usecase(m, out):
    acts = list(m["actors"]); first = {}
    for u in m["use_cases"].values():
        for i, a in enumerate(u["actors"]): first[a] = min(first.get(a, 9), i)
    left = [a for a in acts if first.get(a, 0) == 0] or acts[: (len(acts) + 1) // 2]; right = [a for a in acts if a not in left]
    g = _graph("OOSEM 2 — Use case view (system context): actors outside the boundary, use cases inside")
    g += f'subgraph cluster_sys {{ label=<<b>{_h(m["meta"].get("name","System"))}</b>>; labeljust=l; fontsize=14; style="rounded,filled"; fillcolor="#F9F8F5"; color="{INK}"; penwidth=1.6; margin=18;\n'
    for uid, u in m["use_cases"].items():
        g += f'  "{uid}" [shape=ellipse, style=filled, fillcolor=white, fontsize=12, margin="0.18,0.06", label=<{_h(u["name"])}<br/><font point-size="9" color="{QUIET}">{uid}</font>>];\n'
    g += "}\n"
    for a in acts:
        g += f'"{a}" [shape=box, style="rounded,filled", fillcolor="{C4F}", color="{C4}", fontsize=12, label=<<font point-size="9" color="{QUIET}">«actor»</font><br/><b>{_h(m["actors"][a]["name"])}</b>>];\n'
    if left: g += "{ rank=source; " + "; ".join(f'"{a}"' for a in left) + " }\n"
    if right: g += "{ rank=sink; " + "; ".join(f'"{a}"' for a in right) + " }\n"
    for uid, u in m["use_cases"].items():
        for a in u["actors"]:
            if a not in m["actors"]: continue
            g += (f'"{a}" -> "{uid}" [dir=none];\n' if a in left else f'"{uid}" -> "{a}" [dir=none];\n')
        for inc in u.get("includes", []):
            if inc in m["use_cases"]: g += f'"{uid}" -> "{inc}" [style=dashed, color="{ACC}", fontcolor="{ACC}", label="«include»", constraint=false];\n'
    dot(g + "}", "V03_use_cases", out)

# ---------------- V04 requirements by type ----------------
def v04_requirements(m, out):
    types = {}
    for r, v in m["requirements"].items(): types.setdefault(v["type"], []).append(r)
    n = max(1, len(types)); gap = 0.06; colw = min(1.6, (12.2 - gap * (n - 1)) / n); chars = max(12, int(colw * 15))
    cards = {}
    for t, rs in types.items():
        for r in rs:
            v = m["requirements"][r]
            src = wrap("← " + ", ".join(v["from_"] + [g.split("-", 1)[-1] for g in v["regs"]]), chars)[:2]
            tst = wrap("→ " + ", ".join(v["tests"]), chars)[:2]
            cards[r] = (src, tst, 0.24 + 0.13 * (len(src) + len(tst)))
    colh = max(sum(cards[r][2] + 0.06 for r in rs) for rs in types.values()) if types else 1
    H = max(5, 2.2 + colh)
    f, ax = fig(13, H); title(ax, f"OOSEM 2 — Requirement view: {len(m['requirements'])} requirements by type with provenance (sources → requirement → tests)", h=H)
    x = 0.4
    for t, rs in types.items():
        box(ax, x, H - 1.4, colw, 0.5, f"{t} ({len(rs)})", fill="#FFF8E6", edge=WARN, hs=7.8); y = H - 1.98
        for r in rs:
            src, tst, ch = cards[r]
            ax.add_patch(Rectangle((x, y - ch), colw, ch, fc="white", ec=GRID, lw=0.6))
            fit(ax, x + 0.06, y - 0.06, r, colw - 0.12, 6.8, fontweight="bold", color=INK, va="top"); ty = y - 0.22
            for ln in src: fit(ax, x + 0.06, ty, ln, colw - 0.12, 5.6, color=QUIET, va="top"); ty -= 0.13
            for ln in tst: fit(ax, x + 0.06, ty, ln, colw - 0.12, 5.6, color=GOOD, va="top"); ty -= 0.13
            y -= ch + 0.06
        x += colw + gap
    save(f, "V04_requirements", out)

# ---------------- V05 action flows ----------------
def v05_action_flows(m, out):
    PER = 7; gap = 0.26; bh = 0.8; rowh = 1.2
    rows_of = {sid: max(1, math.ceil(len(s["steps"]) / PER)) for sid, s in m["scenarios"].items()}
    note = lambda s: bool(s.get("concurrent") or s.get("triggers") or s.get("response"))
    H = max(5, 1.4 + sum(0.9 + rowh * r + (0.42 if note(s) else 0) for (sid, s), r in zip(m["scenarios"].items(), rows_of.values())))
    f, ax = fig(13, H); title(ax, "OOSEM 3 — Action flow view: scenarios decomposed into functions (red = safety decision)", h=H); y = H - 1.55
    for sid, s in m["scenarios"].items():
        uc = m["use_cases"].get(s["uc"], {}).get("name", s["uc"])
        kind = s.get("kind", "nominal"); tag = "" if kind == "nominal" else f"[{kind}]  "
        fit(ax, 0.4, y + 0.6, f"{tag}{s['name']}  ({sid}, {uc})", 12.2, 9.4, fontweight="bold", color=(CRIT if kind == "exception" else INK)); ax.add_patch(Circle((0.7, y), 0.1, color=INK))
        steps = s["steps"]; k = len(steps); w = (11.4 - gap * PER) / PER if k > PER else min(1.6, (11.4 - gap * k) / max(1, k))
        x = 1.05; prev = None
        for i, st in enumerate(steps):
            if i and i % PER == 0:   # continue on the next row: elbow from the last box down and back to the left margin
                px, py = prev; y -= rowh; x = 1.05
                ax.plot([px + w / 2, px + w / 2, 0.75, 0.75], [py - bh / 2, py - bh / 2 - 0.12, py - bh / 2 - 0.12, y], color=INK, lw=1.1)
                arrow(ax, (0.75, y), (x, y), color=INK, lw=1.1)
            fv = m["functions"][st]; crit = bool(fv.get("safety_decision"))
            ax.add_patch(FancyBboxPatch((x, y - bh/2), w, bh, boxstyle="round,pad=0,rounding_size=0.14", fc=("#FBEAEA" if crit else "white"), ec=(CRIT if crit else EDGE), lw=1.2))
            nl = wrap(fv["name"], max(10, int(w * 12.5)))[:3]
            for j, ln in enumerate(nl): fit(ax, x + w/2, y + 0.24 - 0.16 * j, ln, w - 0.12, 7.0, ha="center", va="center", color=INK)
            ax.text(x + w/2, y - 0.29, st, ha="center", va="center", fontsize=6.4, color=QUIET)
            if i == 0: ax.plot([0.8, x], [y, y], color=INK, lw=1.1)
            if i < k - 1 and (i + 1) % PER: arrow(ax, (x + w, y), (x + w + gap, y), color=INK, lw=1.1)
            prev = (x, y); x += w + gap
        ax.add_patch(Circle((x + 0.05, y), 0.1, fc="white", ec=INK, lw=1.4)); ax.add_patch(Circle((x + 0.05, y), 0.05, color=INK))
        if s.get("ends_in"): fit(ax, x + 0.25, y, f"ends in {s['ends_in']} {m.get('states', {}).get(s['ends_in'], {}).get('name', '')}".strip(), max(1.0, 12.6 - x), 7.4, va="center", color=QUIET)
        if note(s):
            parts = []
            if s.get("triggers"): parts.append("trigger: " + ", ".join(s["triggers"]))
            if s.get("response"): parts.append("response: " + s["response"])
            if s.get("concurrent"): parts.append("concurrent: " + "; ".join(f"{c} {m['functions'][c]['name']}" for c in s["concurrent"] if c in m["functions"]))
            for j, ln in enumerate(wrap("   ".join(parts), 170)[:3]): fit(ax, 1.05, y - 0.62 - 0.16 * j, ln, 11.6, 7, color=QUIET)
            y -= 0.42
        y -= 0.9 + rowh
    save(f, "V05_action_flows", out)

# ---------------- V06 logical ----------------
def v06_logical(m, out):
    ids = list(m["logical_components"])
    g = _graph(f"OOSEM 3 — Logical architecture: {len(ids)} components partition {len(m['functions'])} functions; edges are logical interfaces", rankdir="TB", extra="nodesep=0.35, ranksep=0.75")
    for lc in ids:
        lv = m["logical_components"][lc]
        g += (f'"{lc}" [shape=box, style="rounded,filled", fillcolor="{C2F}", color="{C2}", margin="0.16,0.1", label=<'
              f'<b><font point-size="13">{_h(lv["name"])}</font></b><br/>'
              f'<font point-size="9" color="{QUIET}">{_h(lc)} · {_wrapbr(", ".join(lv["funcs"]), 40, "center")}</font><br/>'
              f'<font point-size="10">{_wrapbr(lv.get("role", ""), 38, "center")}</font>>];\n')
    for li, lv in m["logical_interfaces"].items():
        if lv["a"] in m["logical_components"] and lv["b"] in m["logical_components"]:
            g += f'"{lv["a"]}" -> "{lv["b"]}" [dir=both, color="{C2}", fontcolor="{C2}", label=<<font point-size="9"><b>{_h(li)}</b><br/>{_wrapbr(lv.get("flow", ""), 26, "center")}</font>>];\n'
    dot(g + "}", "V06_logical_architecture", out)

# ---------------- V07 nodes ----------------
def v07_physical(m, out):
    nodes = list(m["nodes"].items()); n = max(1, len(nodes)); W = min(2.4, 12.4 / n)
    f, ax = fig(13, 7.6); title(ax, "OOSEM 4 — Physical architecture: nodes, parts (coloured by discipline) and the logical components each realizes", h=7.6)
    x = 0.4
    for nd, nv in nodes:
        fl, ed = pal(m, nv["parts"][0]) if nv["parts"] else ("white", EDGE)
        parts = [m["parts"][p]["name"] for p in nv["parts"] if p in m["parts"]]
        lcs = [m["logical_components"][l]["name"] for l in nv["lcs"] if l in m["logical_components"]]
        lines = ["parts:"] + ["  " + l for l in wrap(", ".join(parts), int(W * 11))][:6] + ["realizes:"]
        for l in lcs: lines += ["  • " + w_ if k == 0 else "     " + w_ for k, w_ in enumerate(wrap(l, int(W * 11) - 3))]
        box(ax, x, 1.4, W, 4.7, "\n".join(wrap(nv["name"], int(W * 9))[:2]), lines, fill=fl, edge=ed, fs=6.8, hs=9); x += W + 0.1
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
    sp = 11.6 / max(1, len(top)); bw = min(2.2, sp - 0.15); xs = {p: 0.4 + bw / 2 + i * sp for i, p in enumerate(top)}
    for p in top:
        v = m["parts"][p]; fl, ed = pal(m, p)
        box(ax, xs[p] - bw/2, H - 2.8, bw, 0.6, f"{v['name']} : {v['type']}", fill=fl, edge=ed, hs=8.2); ax.plot([6.5, 6.5, xs[p], xs[p]], [H - 1.4, H - 1.8, H - 1.8, H - 2.2], color=EDGE, lw=1.0)
        kids = [c for c, cv in m["parts"].items() if cv.get("parent") == p]
        ax.plot([xs[p], xs[p]], [H - 2.8, H - 2.8 - 0.45 * len(kids) - 0.1], color=EDGE, lw=0.9)
        for j, c in enumerate(kids):
            y = H - 2.8 - 0.45 * (j + 1); cv = m["parts"][c]
            ax.plot([xs[p], xs[p] + 0.2], [y, y], color=EDGE, lw=0.9); fit(ax, xs[p] + 0.27, y, f"{cv['name']} : {cv['type']}", sp - 0.35, 7.4, color=pal(m, c)[1], va="center")
    save(f, "V09_part_decomposition", out)

# ---------------- V10 states ----------------
def v10_states(m, out):
    ids = list(m["states"])
    if not ids: return
    g = _graph("OOSEM 4 — State machine: red transitions have sensor-dependent guards (behavioral FMEA rows)", extra="nodesep=0.5, ranksep=1.4")
    g += f'"__init" [shape=point, width=0.18, color="{INK}"];\n'
    for sid in ids:
        n = m["states"][sid]["name"]; fault = "fault" in n.lower()
        g += f'"{sid}" [shape=box, style="rounded,filled", fillcolor="{"#FBEAEA" if fault else "white"}", color="{CRIT if fault else EDGE}", fontsize=14, margin="0.3,0.14", label=<<b>{_h(n)}</b>>];\n'
    init = next((s_ for s_ in ids if m["states"][s_]["name"].lower() in ("off", "shipmode", "idle")), ids[0])
    g += f'"__init" -> "{init}" [color="{INK}"];\n'
    for tid, t in m["transitions"].items():
        if t["frm"] not in m["states"] or t["to"] not in m["states"]: continue
        col = CRIT if t.get("sensor") else EDGE
        lab = f'<b>{_h(tid)}</b> {_h(t["trigger"])}' + (f'<br/>[{_wrapbr(t["guard"], 30, "center")}]' if t.get("guard") else "")
        g += f'"{t["frm"]}" -> "{t["to"]}" [color="{col}", fontcolor="{CRIT if col == CRIT else QUIET}", label=<<font point-size="9">{lab}</font>>];\n'
    dot(g + "}", "V10_states", out)

# ---------------- V11 allocation ----------------
def v11_allocation(m, out):
    funcs = list(m["functions"]); used = {p for f in m["functions"].values() for p in f["alloc"]}; parts = [p for p in m["parts"] if p in used][:24]
    H = max(6, 2.6 + 0.24 * len(funcs)); f, ax = fig(13, H); title(ax, "OOSEM 4 — Allocation view: functions × parts (red = function on ≤ 2 parts: single-point-of-failure candidate)", h=H)
    x0, y0 = 4.3, H - 2.1; cw = min(0.47, 8.4 / max(1, len(parts))); rh = 0.24
    for j, p in enumerate(parts): ax.text(x0 + j*cw + 0.08, y0 + 0.1, m["parts"][p]["name"].replace("[*]", "")[:16], rotation=60, fontsize=6.6, ha="left", va="bottom", color=pal(m, p)[1])
    for i, fn in enumerate(funcs):
        y = y0 - i*rh; fv = m["functions"][fn]
        fit(ax, x0 - 0.1, y - rh/2, f"{fn} {fv['name']}", x0 - 0.3, 6.6, ha="right", va="center", color=INK)
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
        inp = c.get("inputs", []); inp = ", ".join(inp) if isinstance(inp, list) else ", ".join(f"{k}={v}" for k, v in inp.items())
        body = wrap(c["formula"], 46)[:4] + wrap("inputs: " + inp, 46)[:2] + wrap(f"→ {', '.join(c['reqs'])} | {', '.join(c['tests'])}", 46)[:2]
        box(ax, x, y, 3.0, 2.3, "«constraint def»\n" + "\n".join(wrap(c["name"], 30)[:2]), body, fill=C3F, edge=C3, fs=6.5, hs=7.8)
    save(f, "V12_analysis", out)

# ---------------- V13 FMEA coverage ----------------
def v13_fmea_coverage(m, out):
    cands = D.candidates(m); idx = {a["element"]: None for a in m["fm_assessments"].values()}
    fm = {(f["element"], f["guide"]): f for f in D.fmea(m)}; assess = {(a["element"], a["guide"]): a for a in m["fm_assessments"].values()}
    elems = list(dict.fromkeys(e for _, e, _ in cands)); gws = list(dict.fromkeys(GUIDE_WORDS_FUNC + GUIDE_WORDS_IF + GUIDE_WORDS_TR + GUIDE_WORDS_PROC))
    H = max(6, 2.6 + 0.17 * len(elems)); f, ax = fig(13, H); title(ax, "Risk — FMEA completeness map: every element × guide word assessed (colour = Action Priority) or screened (grey); white = gap", h=H)
    x0, y0, rh = 4.0, H - 1.8, 0.17; cw = min(0.7, (12.7 - x0) / max(1, len(gws))); colors = {"H": CRIT, "M": WARN, "L": GOOD}
    for j, g in enumerate(gws): ax.text(x0 + j*cw + cw/2, y0 + 0.08, g, rotation=60, fontsize=6.4, ha="left", va="bottom", color=INK)
    for i, e in enumerate(elems):
        y = y0 - i*rh; kind = "function" if e in m["functions"] else "interface" if e in m["interfaces"] else "transition" if e in m["transitions"] else "process"
        fit(ax, x0 - 0.08, y - rh/2, f"{e} {D.element_name(m, kind, e)}", x0 - 0.25, 5.6, min_fs=4.2, ha="right", va="center", color=INK)
        valid = {"function": GUIDE_WORDS_FUNC, "interface": GUIDE_WORDS_IF, "transition": GUIDE_WORDS_TR, "process": GUIDE_WORDS_PROC}[kind]
        for j, g in enumerate(gws):
            if g not in valid: continue
            a = assess.get((e, g)); fc = "white" if a is None else "#E5E7EB" if a.get("ncr") else colors[fm[(e, g)]["AP"]]
            ax.add_patch(Rectangle((x0 + j*cw, y - rh), cw, rh, fc=fc, ec="white", lw=0.5, alpha=0.9))
            if a and not a.get("ncr"): ax.text(x0 + j*cw + cw/2, y - rh/2, fm[(e, g)]["id"][3:], fontsize=4.2 if cw < 0.55 else 4.4, ha="center", va="center", color="white")
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
            c = CRIT if n.lower() in ("launch", "ship") else INK; ax.plot([s], [i], marker="D", ms=9, color=c, zorder=3); ax.text(s + dt.timedelta(days=1.6), i, s.strftime("%b %d"), va="center", fontsize=8.5, color=QUIET)
        else:
            e = dt.date.fromisoformat(e); ax.barh(i, (e - s).days, left=s, height=0.5, color=ACC, alpha=0.85, zorder=2); ax.text(e + dt.timedelta(days=1.2), i, f"{s:%b %d} – {e:%b %d}", va="center", fontsize=8.5, color=QUIET)
    ax.set_xlim(d0 - dt.timedelta(days=1), d1 + dt.timedelta(days=max(6, (d1 - d0).days * 0.12)))
    ax.set_title("Program: gates and lanes from the model", fontsize=12.5, fontweight="bold", color=INK, loc="left", pad=14); f.tight_layout(); save(f, "V14_roadmap", out)

ALL = [v01_thread, v02_needs, v03_usecase, v04_requirements, v05_action_flows, v06_logical, v07_physical, v09_decomposition, v10_states, v11_allocation, v12_analysis, v13_fmea_coverage, v14_roadmap]

def render_all(m, outdir):
    os.makedirs(outdir, exist_ok=True); done, failed = [], {}
    for fn in ALL:
        try: fn(m, outdir); done.append(fn.__name__)
        except Exception as e: failed[fn.__name__] = repr(e)
    return done, failed
