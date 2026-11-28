"""Fault tree analysis to IEC 61025:2006.

A fault tree is a model element (kind fault_trees): a top event and a set of events, each one of
  top / intermediate  : the output of a gate (OR, AND, k/n voting, INHIBIT with a condition)
  basic               : a primary failure with a probability (q) or a failure rate (lambda_fit, FIT = 1e-9/h) over an exposure (hours)
  undeveloped         : an event not developed further (diamond)
  house               : a condition that is either present or not (q = 1 or 0, or a probability for a demand)
  transfer            : continues in another tree (triangle), resolved to that tree's top event
Basic events may point to an FMEA assessment (fm) and a part, so the tree stays traced to the DFMEA and the BOM.

Analysis: minimal cut sets (top-down MOCUS with absorption), top-event probability by the rare-event approximation and the
min-cut upper bound, Fussell-Vesely and Birnbaum importance, single points of failure (order-1 cut sets) and events shared
between the inputs of one AND gate (a common-cause warning: the redundancy is not independent)."""
from __future__ import annotations
from itertools import combinations
from math import prod

GATES = ("OR", "AND", "VOTE", "INHIBIT")
TYPES = ("top", "intermediate", "basic", "undeveloped", "house", "transfer")

def q_of(e: dict) -> float:
    if e.get("q") is not None: return float(e["q"])
    if e.get("lambda_fit") is not None: return min(1.0, float(e["lambda_fit"]) * 1e-9 * float(e.get("hours") or 1.0))
    return 0.0

def validate(t: dict, trees: dict | None = None) -> list[str]:
    ev = t["events"]; out = []
    if t["top"] not in ev: out.append(f"top event {t['top']} is not defined")
    for k, e in ev.items():
        ty = e.get("type")
        if ty not in TYPES: out.append(f"{k}: unknown type {ty}")
        if ty in ("top", "intermediate"):
            if e.get("gate") not in GATES: out.append(f"{k}: gate must be one of {GATES}")
            if not e.get("children"): out.append(f"{k}: a gate needs inputs")
            if e.get("gate") == "VOTE" and not (1 <= int(e.get("k") or 0) <= len(e.get("children") or [])): out.append(f"{k}: VOTE needs 1 ≤ k ≤ inputs")
            if e.get("gate") == "INHIBIT" and len(e.get("children") or []) != 2: out.append(f"{k}: INHIBIT takes one input and one condition")
        for c in e.get("children") or []:
            if c not in ev: out.append(f"{k}: input {c} is not defined")
        if ty in ("basic", "house") and e.get("q") is None and e.get("lambda_fit") is None: out.append(f"{k}: no probability or failure rate")
        if ty == "transfer" and (trees is None or e.get("tree") not in trees): out.append(f"{k}: transfer to unknown tree {e.get('tree')}")
    seen, stack = set(), []
    def cyc(k):
        if k in stack: return True
        if k in seen or k not in ev: return False
        seen.add(k); stack.append(k); r = any(cyc(c) for c in ev[k].get("children") or []); stack.pop(); return r
    if t["top"] in ev and cyc(t["top"]): out.append("the tree has a cycle")
    return out

def _expand(t, trees, k, depth=0):
    """Boolean expansion to a list of cut sets (frozensets of leaf ids), minimised."""
    ev = t["events"]; e = ev[k]; ty = e.get("type")
    if depth > 60: return [frozenset([k])]
    if ty == "transfer" and trees and e.get("tree") in trees:
        sub = trees[e["tree"]]; return _expand(sub, trees, sub["top"], depth + 1)
    if ty not in ("top", "intermediate"): return [frozenset([k])]
    kids = [_expand(t, trees, c, depth + 1) for c in e["children"]]
    g = e["gate"]
    if g == "OR": cs = [c for k_ in kids for c in k_]
    elif g in ("AND", "INHIBIT"):
        cs = [frozenset()]
        for k_ in kids: cs = [a | b for a in cs for b in k_]
    else:   # VOTE k-of-n
        cs = []
        for combo in combinations(kids, int(e["k"])):
            part = [frozenset()]
            for k_ in combo: part = [a | b for a in part for b in k_]
            cs += part
    return minimise(cs)

def minimise(cs):
    cs = sorted(set(cs), key=len); out = []
    for c in cs:
        if not any(o <= c for o in out): out.append(c)
    return out

def leaves(t, trees=None):
    out = {}
    def walk(tt, k):
        e = tt["events"][k]
        if e.get("type") == "transfer" and trees and e.get("tree") in trees: sub = trees[e["tree"]]; walk(sub, sub["top"]); return
        if e.get("type") in ("top", "intermediate"):
            for c in e["children"]: walk(tt, c)
        else: out[k] = e
    walk(t, t["top"]); return out

def analyse(t: dict, trees: dict | None = None) -> dict:
    errs = validate(t, trees)
    if errs: return {"errors": errs}
    L = leaves(t, trees); q = {k: q_of(e) for k, e in L.items()}
    mcs = _expand(t, trees, t["top"])
    qc = [prod(q[x] for x in c) for c in mcs]
    rare = sum(qc); mcub = 1 - prod(1 - x for x in qc)
    order = sorted(range(len(mcs)), key=lambda i: -qc[i])
    fv = {k: (sum(qc[i] for i, c in enumerate(mcs) if k in c) / mcub if mcub else 0) for k in L}
    def top_q(over):
        qq = dict(q); qq.update(over); return 1 - prod(1 - prod(qq[x] for x in c) for c in mcs)
    birn = {k: top_q({k: 1.0}) - top_q({k: 0.0}) for k in L}
    # common cause: an event that sits under two or more inputs of the same AND gate
    ccf = []
    for k, e in t["events"].items():
        if e.get("type") in ("top", "intermediate") and e.get("gate") in ("AND", "VOTE"):
            sets = [set(x for c in _expand(t, trees, ch) for x in c) for ch in e["children"]]
            shared = set.intersection(*sets) if len(sets) > 1 else set()
            if shared: ccf.append((k, sorted(shared)))
    return {"errors": [], "q": q, "leaves": L, "cut_sets": [(sorted(mcs[i]), qc[i]) for i in order], "top_rare": rare, "top_mcub": mcub,
            "fv": fv, "birnbaum": birn, "spof": [sorted(c)[0] for c in mcs if len(c) == 1], "ccf": ccf,
            "orders": {n: sum(1 for c in mcs if len(c) == n) for n in sorted({len(c) for c in mcs})}}


# ---------------------------------------------------------------------------------------------------------------- IEC 61025 symbols (SVG)
def svg(t: dict, a: dict | None = None, trees: dict | None = None) -> str:
    """Draw the tree top-down with IEC 61025 symbols: event description boxes above gates (OR shield, AND D-shape,
    VOTE with k/n, INHIBIT hexagon), basic event circles, undeveloped diamonds, house pentagons, transfer triangles."""
    a = a or analyse(t, trees); W, BH, GW, GH, CW, VS = 190, 58, 34, 30, 34, 150
    # a repeated gate is drawn once and referenced elsewhere with a transfer triangle; a repeated basic event is drawn again
    # (IEC 61025 practice), so the picture stays a tree and every connector is vertical
    src = t["events"]; ev, pos, xs, seen, n = {}, {}, [0], set(), [0]
    def place(k, d, node):
        e = src[k]; gate = e.get("type") in ("top", "intermediate")
        if k in seen and gate:
            ev[node] = {"type": "transfer", "text": e.get("text", ""), "ref": k, "see": k}; kids = []
        else:
            ev[node] = dict(e, ref=k); kids = e.get("children") or [] if gate else []
            if k in seen: ev[node]["repeated"] = True
        seen.add(k)
        if not kids: x = xs[0]; xs[0] += W + 24
        else:
            ch = []
            for c in kids: n[0] += 1; ch.append(place(c, d + 1, f"{c}#{n[0]}"))
            ev[node]["children"] = [f"{c}#{i}" for c, i in zip(kids, range(n[0] - len(kids) + 1, n[0] + 1))] if False else ev[node].get("children")
            ev[node]["_kids"] = ch; x = (pos[ch[0]][0] + pos[ch[-1]][0]) / 2
        pos[node] = (x, d); return node
    place(t["top"], 0, t["top"])
    width = xs[0] + 40; depth = max(d for _, d in pos.values()) + 1; height = depth * VS + 80
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    def wrap(s, n=30):
        w, out, line = str(s).split(), [], ""
        for x in w:
            if len(line) + len(x) + 1 > n: out.append(line); line = x
            else: line = (line + " " + x).strip()
        if line: out.append(line)
        return out[:3] + (["…"] if len(out) > 3 else [])
    P = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="Helvetica,Arial,sans-serif" font-size="11">' % (width, height),
         '<style>.b{fill:#fff;stroke:#222;stroke-width:1.2}.g{fill:#fff;stroke:#222;stroke-width:1.4}.l{stroke:#222;stroke-width:1.1;fill:none}.id{font-weight:bold;font-size:10px}.q{fill:#555;font-size:9.5px}.spof{fill:#fde2e1}</style>']
    q, L = a.get("q", {}), a.get("leaves", {}); spof = set(a.get("spof", []))
    for k, (x, d) in pos.items():
        e = ev[k]; cx = x + 20 + W / 2; y = 30 + d * VS
        for c in e.get("_kids") or []:
            px, pd = pos[c]; ccx = px + 20 + W / 2; cy = 30 + pd * VS
            P.append(f'<path class="l" d="M{cx},{y + BH + 14 + GH} V{y + BH + 14 + GH + 14} H{ccx} V{cy}"/>')
        cls = "b spof" if e.get("ref", k) in spof else "b"
        P.append(f'<rect class="{cls}" x="{cx - W / 2}" y="{y}" width="{W}" height="{BH}"/>')
        rk = e.get("ref", k); P.append(f'<text class="id" x="{cx - W / 2 + 5}" y="{y + 12}">{esc(rk)}{" (repeated)" if e.get("repeated") else ""}</text>')
        if e.get("fm"): P.append(f'<text class="q" x="{cx + W / 2 - 5}" y="{y + 12}" text-anchor="end">{esc(e["fm"])}</text>')
        for i, ln in enumerate(wrap(e.get("text", k))): P.append(f'<text x="{cx - W / 2 + 5}" y="{y + 25 + 11 * i}">{esc(ln)}</text>')
        ty = e.get("type"); sy = y + BH; P.append(f'<path class="l" d="M{cx},{sy} V{sy + 14}"/>'); gy = sy + 14
        if ty in ("top", "intermediate"):
            g = e.get("gate")
            if g == "OR": P.append(f'<path class="g" d="M{cx - GW / 2},{gy + GH} Q{cx},{gy + GH - 10} {cx + GW / 2},{gy + GH} Q{cx + GW / 2},{gy + 8} {cx},{gy} Q{cx - GW / 2},{gy + 8} {cx - GW / 2},{gy + GH} Z"/>')
            elif g in ("AND", "VOTE"):
                P.append(f'<path class="g" d="M{cx - GW / 2},{gy + GH} V{gy + GH / 2} A{GW / 2},{GH / 2} 0 0 1 {cx + GW / 2},{gy + GH / 2} V{gy + GH} Z"/>')
                if g == "VOTE": P.append(f'<text x="{cx}" y="{gy + GH - 5}" text-anchor="middle" font-size="9">{e.get("k")}/{len(e["children"])}</text>')
            elif g == "INHIBIT":
                P.append(f'<path class="g" d="M{cx},{gy} L{cx + GW / 2},{gy + GH / 4} V{gy + 3 * GH / 4} L{cx},{gy + GH} L{cx - GW / 2},{gy + 3 * GH / 4} V{gy + GH / 4} Z"/>')
        elif ty == "basic": P.append(f'<circle class="g" cx="{cx}" cy="{gy + CW / 2}" r="{CW / 2}"/>')
        elif ty == "undeveloped": P.append(f'<path class="g" d="M{cx},{gy} L{cx + CW / 2},{gy + CW / 2} L{cx},{gy + CW} L{cx - CW / 2},{gy + CW / 2} Z"/>')
        elif ty == "house": P.append(f'<path class="g" d="M{cx},{gy} L{cx + CW / 2},{gy + CW / 3} V{gy + CW} H{cx - CW / 2} V{gy + CW / 3} Z"/>')
        elif ty == "transfer": P.append(f'<path class="g" d="M{cx},{gy} L{cx + CW / 2},{gy + CW} H{cx - CW / 2} Z"/><text x="{cx}" y="{gy + CW + 12}" text-anchor="middle" class="q">{"see " + esc(e["see"]) if e.get("see") else "to " + esc(e.get("tree", ""))}</text>')
        if e.get("ref", k) in L: P.append(f'<text class="q" x="{cx + CW / 2 + 6}" y="{gy + CW / 2 + 4}">q = {q.get(e.get("ref", k), 0):.1e}</text>')
    if a.get("cut_sets") is not None:
        P.append(f'<text x="20" y="{height - 18}" font-size="11"><tspan font-weight="bold">{esc(t.get("name", ""))}</tspan>: P(top) ≈ {a["top_mcub"]:.2e} (min-cut upper bound), {len(a["cut_sets"])} minimal cut sets{"; single points of failure shaded" if spof else ""}</text>')
    P.append("</svg>"); return "\n".join(P)
