"""Trade studies — the decision record behind every architecture choice, evaluated from the graph.

A trade study (kind `trades`) holds alternatives (options) scored against weighted criteria. Criteria are tied to the model:
each criterion may reference a MoE (`moes`), a requirement attribute (`reqs`) or a budget, carries a direction
(max/min), a unit and a weight. Scores may be entered as normalized 1–5 (`scores`) or as measured values (`raw`) that are
normalized here (linear, best = 5). Every score may cite evidence (element ids: tests, simulations, suppliers, notes).

Criteria may also carry a hard `limit` (a knock-out: an option whose raw value violates it is infeasible and ranked last whatever its score) —
this is how circuit limits, envelope, regulatory ceilings and cost caps enter a study without being averaged away.

Evaluation returns the weighted matrix, the ranking, the Pugh view when a datum is set, and a sensitivity analysis:
for each criterion the weight at which the leader changes (flip point), and whether a ±25 % weight change or a ±1 score
change on the leader flips the decision. A decision is robust when no single such perturbation changes the leader.

Standard form: INCOSE SE Handbook §4.3 / NASA SE Handbook 6.8 (trade studies), Pugh 1981 (datum comparison).
"""
from __future__ import annotations
import copy

SCALE = 5.0


def _w(t):
    c = t.get("criteria") or []; w = t.get("weights") or []
    return [float(w[i]) if i < len(w) and w[i] not in (None, "") else 1.0 for i in range(len(c))]


def _meta(t, c):
    return (t.get("criteria_meta") or {}).get(c) or {}


def normalized(t):
    """Scores per option per criterion on the 1–5 scale; raw values are normalized by direction within the study."""
    out = {}; crit = t.get("criteria") or []; sc = t.get("scores") or {}; raw = t.get("raw") or {}
    for c in crit:
        vals = {o: raw.get(o, {}).get(c) for o in t["options"] if isinstance(raw.get(o), dict) and raw.get(o, {}).get(c) not in (None, "")}
        nums = {}
        for o, v in vals.items():
            try: nums[o] = float(v)
            except (TypeError, ValueError): pass
        lo, hi = (min(nums.values()), max(nums.values())) if nums else (0, 0)
        direction = _meta(t, c).get("direction", "max")
        for o in t["options"]:
            s = sc.get(o, {}).get(c) if isinstance(sc.get(o), dict) else None
            if s in (None, "") and o in nums:
                if hi == lo: s = SCALE
                else:
                    f = (nums[o] - lo) / (hi - lo); f = 1 - f if direction == "min" else f
                    s = 1 + f * (SCALE - 1)
            try: s = float(s) if s not in (None, "") else None
            except (TypeError, ValueError): s = None
            out.setdefault(o, {})[c] = s
    return out


def infeasible(t):
    """Options knocked out by a hard limit: criteria_meta[c].limit with direction (max → value must be ≥ limit; min → ≤ limit)."""
    out = {}; raw = t.get("raw") or {}
    for c in t.get("criteria") or []:
        me = _meta(t, c); lim = me.get("limit")
        if lim in (None, ""): continue
        for o in t["options"]:
            v = (raw.get(o, {}) or {}).get(c)
            try: v = float(v); lim_ = float(lim)
            except (TypeError, ValueError): continue
            bad = v > lim_ if me.get("direction", "max") == "min" else v < lim_
            if bad: out.setdefault(o, []).append(f"{c} {v} {'>' if me.get('direction') == 'min' else '<'} limit {lim_}{(' ' + me.get('unit')) if me.get('unit') else ''}")
    return out


def totals(t, N=None, w=None):
    N = N if N is not None else normalized(t); w = w if w is not None else _w(t); crit = t.get("criteria") or []
    tot = {}; ko = infeasible(t)
    for o in t["options"]:
        if o in ko: tot[o] = {"score": -1.0, "filled": 0, "of": len(crit), "max": round(sum(w) * SCALE, 2), "infeasible": ko[o]}; continue
        s = 0.0; filled = 0
        for i, c in enumerate(crit):
            v = N.get(o, {}).get(c)
            if v is not None: s += w[i] * v; filled += 1
        tot[o] = {"score": round(s, 2), "filled": filled, "of": len(crit), "max": round(sum(w) * SCALE, 2)}
    return tot


def leader(tot):
    r = sorted(tot.items(), key=lambda kv: -kv[1]["score"])
    return (r[0][0] if r else None), r


def sensitivity(t):
    """Per criterion: flip point of its weight, effect of ±25 % weight, and of ±1 on the leader's score."""
    N = normalized(t); w = _w(t); crit = t.get("criteria") or []
    base = totals(t, N, w); lead, rank = leader(base)
    runner = rank[1][0] if len(rank) > 1 else None
    margin = round(rank[0][1]["score"] - rank[1][1]["score"], 2) if runner else None
    rows = []; robust = True
    for i, c in enumerate(crit):
        row = {"criterion": c, "weight": w[i]}
        # flip point: weight w' where leader and runner-up tie, holding other weights
        if runner:
            dl = N.get(lead, {}).get(c); dr = N.get(runner, {}).get(c)
            if dl is not None and dr is not None and dl != dr:
                others_l = base[lead]["score"] - w[i] * dl; others_r = base[runner]["score"] - w[i] * dr
                wp = (others_r - others_l) / (dl - dr)
                row["flip_weight"] = round(wp, 2) if wp >= 0 else None
            else: row["flip_weight"] = None
        for k, f in (("w_minus", 0.75), ("w_plus", 1.25)):
            w2 = list(w); w2[i] = w[i] * f; l2, _ = leader(totals(t, N, w2)); row[k] = l2
            if l2 != lead: robust = False
        N2 = copy.deepcopy(N)
        if N2.get(lead, {}).get(c) is not None:
            N2[lead][c] = max(1.0, N2[lead][c] - 1); l3, _ = leader(totals(t, N2, w)); row["leader_minus1"] = l3
            if l3 != lead: robust = False
        rows.append(row)
    return {"leader": lead, "runner_up": runner, "margin": margin, "robust": robust, "rows": rows}


def pugh(t, N=None):
    """Pugh matrix relative to the datum: +, S, − per criterion; counts per option."""
    d = t.get("datum")
    if not d or d not in t["options"]: return None
    N = N if N is not None else normalized(t); crit = t.get("criteria") or []; out = {}
    for o in t["options"]:
        marks = {}; plus = minus = same = 0
        for c in crit:
            a = N.get(o, {}).get(c); b = N.get(d, {}).get(c)
            if a is None or b is None: marks[c] = ""; continue
            if o == d or abs(a - b) < 1e-9: marks[c] = "S"; same += 1
            elif a > b: marks[c] = "+"; plus += 1
            else: marks[c] = "−"; minus += 1
        out[o] = {"marks": marks, "plus": plus, "minus": minus, "same": same, "net": plus - minus}
    return {"datum": d, "options": out}


def evaluate(m, tid):
    t = m.get("trades", {}).get(tid)
    if not t: return None
    N = normalized(t); w = _w(t); tot = totals(t, N, w); lead, rank = leader(tot); sens = sensitivity(t)
    crit = []
    for i, c in enumerate(t.get("criteria") or []):
        me = _meta(t, c)
        crit.append({"name": c, "weight": w[i], "direction": me.get("direction", "max"), "unit": me.get("unit", ""), "moe": me.get("moe"), "req": me.get("req"), "basis": me.get("basis", ""), "limit": me.get("limit")})
    ev = t.get("evidence") or {}; raw = t.get("raw") or {}
    options = []
    for o in t["options"]:
        options.append({"name": o, "scores": {c["name"]: N.get(o, {}).get(c["name"]) for c in crit}, "raw": {c["name"]: (raw.get(o, {}) or {}).get(c["name"]) for c in crit},
                        "evidence": {c["name"]: (ev.get(o, {}) or {}).get(c["name"], []) for c in crit}, "total": tot[o], "rank": [r[0] for r in rank].index(o) + 1, "datum": t.get("datum") == o, "infeasible": tot[o].get("infeasible", [])})
    # linked elements
    links = {"requirements": [r for r in t.get("affects", []) if r in m.get("requirements", {})], "elements": t.get("elements", []), "moes": sorted({c["moe"] for c in crit if c.get("moe")}),
             "decisions": [a for a, av in m.get("arch_decisions", {}).items() if av.get("trade") == tid]}
    decision = t.get("decision") or ""
    agrees = (decision == lead) if decision else None
    feasible = [o for o in t["options"] if not tot[o].get("infeasible")]
    return {"id": tid, "name": t["name"], "question": t.get("question", ""), "feasible": feasible, "status": t.get("status", "open" if not decision else "decided"), "criteria": crit, "options": options,
            "leader": lead, "decision": decision, "decision_agrees_with_scores": agrees, "recommendation": t.get("recommendation", ""), "rationale": t.get("rationale", ""),
            "decided_by": t.get("decided_by", ""), "date": t.get("date", ""), "sensitivity": sens, "pugh": pugh(t, N), "links": links,
            "complete": all(all(v is not None for v in o["scores"].values()) for o in options if not o["infeasible"]) and bool(options) and bool(crit)}


def summary(m):
    out = []
    for tid in m.get("trades", {}):
        e = evaluate(m, tid)
        out.append({"id": tid, "name": e["name"], "status": e["status"], "options": len(e["options"]), "criteria": len(e["criteria"]), "leader": e["leader"], "decision": e["decision"],
                    "robust": e["sensitivity"]["robust"], "margin": e["sensitivity"]["margin"], "complete": e["complete"], "agrees": e["decision_agrees_with_scores"], "affects": e["links"]["requirements"], "elements": e["links"]["elements"]})
    return out


def TRADES_feasible(m, tid): return evaluate(m, tid)["feasible"]


def checks(m):
    """Trade-study hygiene for gates: decided studies without rationale, open studies on gated elements, non-robust decisions, decisions that contradict the scores."""
    out = []
    for e in summary(m):
        t = m["trades"][e["id"]]
        if e["status"] == "decided" and not t.get("rationale"): out.append({"id": e["id"], "issue": "decided without rationale"})
        if e["status"] != "decided": out.append({"id": e["id"], "issue": "open"})
        if not e["complete"]: out.append({"id": e["id"], "issue": "scores incomplete"})
        if e["agrees"] is False: out.append({"id": e["id"], "issue": f"decision {e['decision']} contradicts the leader {e['leader']} — rationale must say why"})
        if e["complete"] and not e["robust"]: out.append({"id": e["id"], "issue": "not robust: a single weight or score change flips the leader"})
        if len(m["trades"][e["id"]]["options"]) - len(TRADES_feasible(m, e["id"])) == len(m["trades"][e["id"]]["options"]): out.append({"id": e["id"], "issue": "every option is infeasible against a limit"})
    return out
