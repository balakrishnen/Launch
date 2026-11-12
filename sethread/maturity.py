"""Technology readiness (TRL) and critical design attributes (CDA) — the two GAO evidence themes Launch was missing.

TRL: every part (and logical component) may carry attrs.trl (1–9, NASA/DoD scale) and attrs.new_technology (yes). The graph also
gives a *demonstrated* floor: TRL 3 when a simulation exists, 4 when a test for a requirement allocated to it passed on the bench,
5–6 when it passed on a built unit (test run with a unit), 7 when the EVT build passed end-of-line, 8 when PPAP/certification is
approved, 9 when field events exist with the part in service. Declared TRL is never raised by the floor automatically; the gap
between declared and demonstrated is itself an indicator. Gates carry a minimum TRL for new-technology parts (appliance NPI:
G1 ≥ 4, EVT ≥ 5, DVT ≥ 6, PVT ≥ 8, MP ≥ 9).

CDA: the handful of parameters that decide the product (kind `cdas`): name, unit, target, direction, limit (hard), the MoE or
requirement it realises, the owning team, and a *source* that says where its current value comes from — the latest test run's
metrics[key], a unit station's data[key], a part attribute, or a simulation output. Current value, margin to target and limit,
and the trend over the last runs are derived; a CDA inside 10 % of its limit, or trending the wrong way, is a leading indicator.
"""
from __future__ import annotations
import datetime as _dt

TRL_MIN = {"G0": 3, "G1": 4, "EVT": 5, "DVT": 6, "PVT": 8, "MP": 9, "PDR": 4, "CDR": 6, "G2": 5, "G3": 6, "G4": 8}


def _passed_tests_for(m, part):
    funcs = [f for f, v in m["functions"].items() if part in v.get("alloc", [])]
    reqs = {r for f in funcs for r in m["functions"][f].get("reqs", [])}
    tests = {t for r in reqs for t in m["requirements"].get(r, {}).get("tests", [])} | {t for t, v in m["tests"].items() if v.get("element") == part}
    return tests, [t for t in tests if m["tests"].get(t, {}).get("status") == "passed"]


def demonstrated_trl(m, part):
    """The TRL the evidence in the graph supports, with the evidence."""
    ev = []; level = 1
    if any(s.get("element") == part or part in (s.get("parts") or []) for s in m.get("simulations", {}).values()): level = max(level, 3); ev.append("simulation")
    tests, passed = _passed_tests_for(m, part)
    if passed: level = max(level, 4); ev.append(f"{len(passed)} test(s) passed")
    runs = [r for r in m.get("test_runs", {}).values() if r.get("test") in tests and r.get("result") == "pass"]
    built = {u.get("serial") for u in m.get("units", {}).values()} | set(m.get("units", {}).keys())
    if any(r.get("unit") in built for r in runs): level = max(level, 6); ev.append("passed on a built unit")
    units = [u for u in m.get("units", {}).values() if part in (u.get("components") or {}) and u.get("status") == "complete"]
    if units: level = max(level, 7); ev.append(f"{len(units)} unit(s) through end-of-line")
    if any(t.get("part") == part and t.get("ppap") == "approved" for t in m.get("tooling", {}).values()): level = max(level, 8); ev.append("PPAP approved")
    if any(t.get("element") == part and t.get("status") == "passed" and (t.get("kind") in ("certification", "cert") or t.get("gate") == "PVT") for t in m["tests"].values()): level = max(level, 8); ev.append("certification test passed")
    if any(part in (u.get("components") or {}) and u.get("shipped") for u in m.get("units", {}).values()): level = max(level, 9); ev.append("in service")
    return level, ev


def trl_rows(m):
    out = []
    for p, v in m["parts"].items():
        if v.get("context"): continue
        a = v.get("attrs") or {}; declared = a.get("trl"); new = str(a.get("new_technology", "")).lower() in ("yes", "true", "1")
        try: declared = int(declared) if declared not in (None, "") else None
        except (TypeError, ValueError): declared = None
        demo, ev = demonstrated_trl(m, p)
        out.append({"part": p, "name": v["name"], "new_technology": new, "declared": declared, "demonstrated": demo, "evidence": ev, "gap": (declared - demo) if declared is not None else None, "owner_team": v.get("owner_team"), "make_buy": v.get("make_buy", "")})
    return out


def trl_check(m, c):
    gate = c.get("gate_ref"); need = c.get("min") or TRL_MIN.get(gate, 6)
    rows = [r for r in trl_rows(m) if r["new_technology"] or c.get("all")]
    if not rows: return {"status": "partial", "measured": "no parts flagged new_technology — mark the unproven ones", "link": "/form/trl"}
    ok = [r for r in rows if (r["declared"] if r["declared"] is not None else r["demonstrated"]) >= need]
    undeclared = [r for r in rows if r["declared"] is None]; overstated = [r for r in rows if r["gap"] is not None and r["gap"] >= 2]
    st = "done" if len(ok) == len(rows) and not overstated else ("partial" if ok else "missing")
    return {"status": st, "measured": f"{len(ok)}/{len(rows)} at TRL ≥ {need}" + (f" · {len(undeclared)} undeclared" if undeclared else "") + (f" · {len(overstated)} overstated vs evidence" if overstated else ""), "link": "/form/trl"}


# ---------------- critical design attributes ----------------
def _series(m, src):
    """[(date, value)] for a CDA source."""
    kind = (src or {}).get("kind"); key = (src or {}).get("key"); out = []
    if kind == "test_run":
        for r in m.get("test_runs", {}).values():
            if src.get("test") and r.get("test") != src["test"]: continue
            v = (r.get("metrics") or {}).get(key)
            if v not in (None, ""): out.append((r.get("date", ""), float(v)))
    elif kind == "unit_station":
        for u in m.get("units", {}).values():
            st = (u.get("stations") or {}).get(src.get("step") or "", {}) if src.get("step") else None
            cands = [st] if st else list((u.get("stations") or {}).values())
            for s in cands:
                v = ((s or {}).get("data") or {}).get(key)
                if v not in (None, ""): out.append(((s or {}).get("date") or u.get("built", ""), float(v)))
    elif kind == "part_attr":
        v = (m["parts"].get(src.get("part"), {}).get("attrs") or {}).get(key)
        if v not in (None, ""):
            try: out.append(("", float(v)))
            except (TypeError, ValueError): pass
    elif kind == "simulation":
        for s in m.get("simulations", {}).values():
            v = (s.get("outputs") or s.get("results") or {}).get(key)
            if v not in (None, ""): out.append((s.get("date", ""), float(v)))
    return sorted(out, key=lambda x: x[0])


def cda_rows(m):
    out = []
    for c, v in m.get("cdas", {}).items():
        ser = _series(m, v.get("source")); cur = ser[-1][1] if ser else None
        direction = v.get("direction", "max"); target = v.get("target"); limit = v.get("limit")
        f = lambda x: float(x) if x not in (None, "") else None
        target, limit = f(target), f(limit)
        margin_t = margin_l = None
        if cur is not None and target is not None and target: margin_t = round(100 * ((cur - target) / abs(target)) * (1 if direction == "max" else -1), 1)
        if cur is not None and limit is not None and limit: margin_l = round(100 * ((cur - limit) / abs(limit)) * (1 if direction == "max" else -1), 1)
        trend = None
        if len(ser) >= 3:
            a, b = ser[-3][1], ser[-1][1]; trend = "improving" if (b > a) == (direction == "max") and b != a else ("worsening" if b != a else "flat")
        status = "unmeasured" if cur is None else ("violating limit" if margin_l is not None and margin_l < 0 else ("below target" if margin_t is not None and margin_t < 0 else ("tight" if margin_l is not None and margin_l < 10 else "ok")))
        out.append({"id": c, **v, "current": cur, "n": len(ser), "last": ser[-1][0] if ser else "", "margin_to_target_pct": margin_t, "margin_to_limit_pct": margin_l, "trend": trend, "status": status, "series": [x[1] for x in ser[-8:]]})
    return out


def cda_check(m, c):
    rows = cda_rows(m)
    if not rows: return {"status": "missing", "measured": "no critical design attributes defined", "link": "/form/cda"}
    meas = [r for r in rows if r["current"] is not None]; bad = [r for r in meas if r["status"] in ("violating limit", "below target")]
    st = "done" if len(meas) == len(rows) and not bad else ("partial" if meas else "missing")
    return {"status": st, "measured": f"{len(meas)}/{len(rows)} measured · {len(bad)} below target or over limit", "link": "/form/cda"}


# ---------------- forms ----------------
def trl_form(m):
    rows = [[r["part"], r["name"], "yes" if r["new_technology"] else "", r["declared"] if r["declared"] is not None else "— undeclared", r["demonstrated"], "; ".join(r["evidence"]) or "no evidence in the model", (f"+{r['gap']}" if r["gap"] and r["gap"] > 0 else r["gap"]) if r["gap"] is not None else "", r["owner_team"] or "", r["make_buy"]] for r in trl_rows(m)]
    rows.sort(key=lambda r: (r[2] != "yes", r[4]))
    headers = ["Part", "Name", "New tech", "Declared TRL", "Demonstrated", "Evidence (from the model)", "Declared − demonstrated", "Owner", "Make/buy"]
    return [("TECHNOLOGY READINESS (declared vs demonstrated by evidence in the graph; NASA/DoD 1–9)", len(headers))], headers, [8, 26, 7, 9, 9, 40, 10, 10, 7], rows


def cda_form(m):
    rows = [[r["id"], r["name"], r.get("unit", ""), r.get("target", ""), r.get("limit", ""), r.get("direction", "max"), r["current"] if r["current"] is not None else "— unmeasured", r["margin_to_target_pct"] if r["margin_to_target_pct"] is not None else "", r["margin_to_limit_pct"] if r["margin_to_limit_pct"] is not None else "", r["trend"] or "", r["n"], r.get("moe") or r.get("req") or "", r.get("owner_team") or "", r["status"]] for r in cda_rows(m)]
    headers = ["CDA", "Attribute", "Unit", "Target", "Limit", "Dir.", "Current", "Margin to target %", "Margin to limit %", "Trend", "Samples", "Realises", "Owner", "Status"]
    return [("CRITICAL DESIGN ATTRIBUTES (the parameters that decide the product; current value from runs, units, attributes or simulations)", len(headers))], headers, [7, 26, 6, 8, 8, 5, 10, 9, 9, 9, 7, 8, 9, 12], rows


FORMS = {"trl": ("Technology readiness", "Declared vs demonstrated TRL per part with the evidence", trl_form), "cda": ("Critical design attributes", "Targets, limits, current values, margins and trends", cda_form)}
