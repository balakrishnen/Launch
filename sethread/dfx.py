"""Design for X — guideline sets (library/dfx/*.yaml; a project adds its own under .sethread/dfx/) evaluated against the model.
Each item has a check: automatic (coverage key, attribute share, FMEA severity rule, regulation present, test method, requirement type,
collection size) or manual (a reviewer or the dfx agent sets status with evidence). Review state lives in the `dfx_reviews` kind, so
scores are reproducible and auditable. Score = passed / applicable (n/a excluded)."""
from __future__ import annotations
import glob, os, re, yaml
from . import derive as D

HERE = os.path.join(os.path.dirname(__file__), "library", "dfx")

def sets(project_root: str | None = None) -> list[dict]:
    out = {}
    for p in sorted(glob.glob(os.path.join(HERE, "*.yaml"))) + (sorted(glob.glob(os.path.join(project_root, ".sethread", "dfx", "*.yaml"))) if project_root else []):
        d = yaml.safe_load(open(p)); out[d["id"]] = d
    return list(out.values())

def get(x: str, project_root=None) -> dict | None:
    return next((s for s in sets(project_root) if s["id"] == x), None)

def _share(m, kind, key, flt=None):
    rows = [v for v in m.get(kind, {}).values() if not flt or all(v.get(fk) == fv for fk, fv in flt.items())]
    if not rows: return None, 0
    hit = [v for v in rows if (v.get(key) not in ("", None, [], {})) or ((v.get("attrs") or {}).get(key) not in ("", None))]
    return len(hit) / len(rows), len(rows)

def check(m, rep, c: dict) -> dict:
    t = c.get("type", "manual")
    try:
        if t == "manual": return {"auto": False, "status": "unknown", "measured": "needs a reviewer or the dfx agent"}
        if t == "coverage":
            v = rep.get(c["key"]); n = len(v) if isinstance(v, list) else (v or 0)
            return {"auto": True, "status": "pass" if n <= c.get("max", 0) else "fail", "measured": f"{n} open", "link": "/gaps"}
        if t == "attr":
            sh, n = _share(m, c["kind"], c["key"], c.get("filter"))
            if sh is None: return {"auto": True, "status": "n/a", "measured": f"no {c['kind']}" + (f" with {c['filter']}" if c.get("filter") else "")}
            return {"auto": True, "status": "pass" if sh >= c.get("min_share", 1.0) else ("partial" if sh > 0 else "fail"), "measured": f"{int(sh * 100)}% of {n} have {c['key']}", "link": f"/collection/{c['kind']}"}
        if t == "fmea":
            rows = [f for f in D.fmea(m) if (f.get("S") or 0) >= c.get("sev_min", 9)]
            if "require" in c:
                bad = [f for f in rows if not f.get(c["require"])]
                return {"auto": True, "status": "pass" if rows and not bad else ("fail" if bad else "n/a"), "measured": f"{len(rows) - len(bad)}/{len(rows)} with {c['require']}", "link": "/form/hazards", "ids": [f["id"] for f in bad][:20]}
            return {"auto": True, "status": "pass" if len(rows) >= c.get("n", 1) else "fail", "measured": f"{len(rows)} failure modes with S ≥ {c.get('sev_min', 9)}", "link": "/form/hazards"}
        if t == "collection":
            n = len(m.get(c["kind"], {})); return {"auto": True, "status": "pass" if n >= c.get("n", 1) else "fail", "measured": f"{n} {c['kind']}", "link": f"/collection/{c['kind']}"}
        if t == "req_type":
            rows = [r for r, v in m["requirements"].items() if v.get("type") == c["req"]]
            return {"auto": True, "status": "pass" if len(rows) >= c.get("n", 1) else "fail", "measured": f"{len(rows)} {c['req']} requirements", "link": "/collection/requirements", "ids": rows[:20]}
        if t == "regulation":
            pat = re.compile(c["pattern"], re.I); rows = [r for r, v in m["regulations"].items() if pat.search(v.get("name", "") + " " + v.get("standard", ""))]
            return {"auto": True, "status": "pass" if rows else "fail", "measured": ", ".join(rows[:6]) or "none in the regulatory set", "link": "/collection/regulations", "ids": rows[:20]}
        if t == "tests_method":
            pat = re.compile(c["pattern"], re.I); rows = [t_ for t_, v in m["tests"].items() if pat.search(v.get("method", "") + " " + v.get("name", ""))]
            return {"auto": True, "status": "pass" if len(rows) >= c.get("n", 1) else "fail", "measured": f"{len(rows)} tests match", "link": "/collection/tests", "ids": rows[:20]}
        if t == "note":
            rows = [n for n, v in m.get("notes", {}).items() if v.get("kind") == c.get("kind")]
            return {"auto": True, "status": "pass" if len(rows) >= c.get("n", 1) else "fail", "measured": f"{len(rows)} notes", "link": "/notes"}
    except Exception as e: return {"auto": True, "status": "error", "measured": str(e)[:80]}
    return {"auto": False, "status": "unknown", "measured": ""}

def evaluate(m: dict, x: str, project_root=None) -> dict | None:
    s = get(x, project_root)
    if not s: return None
    rep = D.coverage_report(m)
    # review records for this X (canonical id DFX-<x>; tolerate agent-chosen ids and item keys that start with the guideline id)
    xs = {x.lower(), (s.get("short") or "").lower()}
    recs = [v for k, v in m.get("dfx_reviews", {}).items() if k == "DFX-" + x or str(v.get("x", "")).lower() in xs or k.upper().startswith("DFX-" + (s.get("short") or "~").upper())]
    rev = recs[-1] if recs else {}; manual = {}
    for r in recs:
        for k, v in (r.get("items") or {}).items():
            gid = next((it["id"] for it in s["items"] if str(k).upper().startswith(it["id"].upper())), None)
            if gid and isinstance(v, dict): manual[gid] = {"status": v.get("status") or v.get("verdict"), "evidence": v.get("evidence") or [], "note": v.get("note") or v.get("justification") or "", "by": v.get("by") or r.get("by"), "date": v.get("date") or r.get("date")}
    items = []
    for it in s["items"]:
        a = check(m, rep, it.get("check", {})); mv = manual.get(it["id"]) or {}
        status = mv.get("status") or a["status"]      # a reviewer's status overrides (recorded with who/when)
        items.append({**it, **a, "status": status, "auto_status": a["status"], "manual": mv, "overridden": bool(mv.get("status")) and mv.get("status") != a["status"]})
    appl = [i for i in items if i["status"] not in ("n/a",)]
    passed = len([i for i in appl if i["status"] == "pass"]); partial = len([i for i in appl if i["status"] == "partial"]); unknown = len([i for i in appl if i["status"] == "unknown"])
    score = round(100 * (passed + 0.5 * partial) / len(appl)) if appl else None
    return {"id": x, "name": s["name"], "short": s.get("short", x), "focus": s.get("focus"), "standard": s.get("standard", ""), "items": items, "score": score, "passed": passed, "partial": partial, "unknown": unknown, "failed": len([i for i in appl if i["status"] == "fail"]), "applicable": len(appl), "reviewed": rev.get("date"), "by": rev.get("by")}

def summary(m: dict, project_root=None, enabled: list | None = None) -> list[dict]:
    out = []
    for s in sets(project_root):
        if enabled is not None and s["id"] not in enabled: continue
        e = evaluate(m, s["id"], project_root); out.append({k: e[k] for k in ("id", "name", "short", "focus", "score", "passed", "partial", "unknown", "failed", "applicable", "reviewed", "by")})
    return out
