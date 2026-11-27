"""Importers for known spreadsheet formats teams start from, so their first Launch project keeps its history.

syseng-toolkit Requirements template (syseng-toolkit.github.io, CC BY 4.0, v1.0.0): tabs Requirements (ID REQ-###, Title,
Requirement, Subsystem, Parent, Related, Priority, Status, Verification, Rationale, Owner, Notes) and Change Log (Date, REQ ID,
What Changed, Was, Now, Reason, By). Each requirement becomes a Launch requirement with its parent flow-down, related links,
priority, status and owner; the change log sets its revision and last-changed date and is kept on the element."""
import re

VERIFY = {"test": "test", "analysis": "analysis", "inspection": "inspection", "design": "inspection", "demonstration": "demonstration", "demo": "demonstration"}
STATUS = {"draft": "draft", "needs review": "needs review", "accepted": "approved", "verified": "verified", "obsolete": "obsolete"}
UNIT = re.compile(r"\d\s*(%|°|mm|cm|m|km|kg|g|n|nm|n·m|s|ms|min|h|hz|khz|mhz|ghz|v|a|ma|w|kw|°c|k|db|pa|kpa|bar|psi|l|ml)\b", re.I)

def _norm(h): return re.sub(r"[^a-z0-9]", "", str(h).lower())

def _table(sheet):
    """Find the header row (contains id and requirement/date) in a sheet that may have title rows above it."""
    rows = [sheet["headers"]] + sheet["rows"]
    for i, r in enumerate(rows[:15]):
        n = [_norm(x) for x in r]
        if "id" in n and ("requirement" in n or "title" in n) or ("date" in n and "reqid" in n):
            return [str(x).strip() for x in r], rows[i + 1:]
    return None, []

def detect(sheets) -> dict | None:
    names = {s["name"].strip().lower(): s for s in sheets}
    req = names.get("requirements")
    if not req: return None
    h, rows = _table(req)
    if not h or not {"id", "requirement", "parent", "verification"} <= {_norm(x) for x in h}: return None
    n = sum(1 for r in rows if str(r[[_norm(x) for x in h].index("id")]).strip())
    return {"format": "syseng-toolkit", "label": "syseng-toolkit Requirements template", "requirements": n, "change_log": bool(names.get("change log"))}

def syseng_toolkit(sheets, model) -> tuple[list[dict], list[str]]:
    names = {s["name"].strip().lower(): s for s in sheets}; notes = []
    h, rows = _table(names["requirements"]); ix = {_norm(x): i for i, x in enumerate(h)}
    g = lambda r, k: (str(r[ix[k]]).strip() if k in ix and ix[k] < len(r) and r[ix[k]] is not None else "")
    log = {}
    if names.get("change log"):
        ch, crow = _table(names["change log"]); cx = {_norm(x): i for i, x in enumerate(ch or [])}
        for r in crow:
            rid = str(r[cx["reqid"]]).strip() if "reqid" in cx and cx["reqid"] < len(r) else ""
            if rid: log.setdefault(rid, []).append({k: str(r[cx[c]]).strip() if c in cx and cx[c] < len(r) else "" for k, c in (("date", "date"), ("what", "whatchanged"), ("was", "was"), ("now", "now"), ("reason", "reason"), ("by", "by"))})
    ids = [g(r, "id") for r in rows if g(r, "id")]; ops = []
    for r in rows:
        rid = g(r, "id")
        if not rid: continue
        text = g(r, "requirement"); ver = VERIFY.get(g(r, "verification").lower(), "")
        if not ver: notes.append(f"{rid}: no verification method, set to 'test' for review")
        parent = g(r, "parent") or None
        if parent and parent not in ids and parent not in model.get("requirements", {}): notes.append(f"{rid}: parent {parent} not found, dropped"); parent = None
        related = [x.strip() for x in re.split(r"[,;\s]+", g(r, "related")) if x.strip() and (x.strip() in ids or x.strip() in model.get("requirements", {}))]
        hist = sorted(log.get(rid, []), key=lambda e: e["date"])
        attrs = {k: v for k, v in (("title", g(r, "title")), ("subsystem", g(r, "subsystem")), ("rationale", g(r, "rationale")), ("notes", g(r, "notes")), ("source", "syseng-toolkit requirements template")) if v}
        if hist: attrs["change_log"] = hist
        v = {"type": "PERF" if UNIT.search(text) else "FUNC", "text": text, "verify": ver or "test", "tests": [], "parent": parent, "related": related,
             "priority": g(r, "priority"), "status": STATUS.get(g(r, "status").lower(), g(r, "status").lower() or None), "owner": g(r, "owner"), "attrs": attrs,
             "rev": 1 + len(hist), "changed": hist[-1]["date"][:10] if hist else ""}
        if g(r, "verification").lower() == "design": attrs["verify_note"] = "verified by design review (template method 'Design')"
        ops.append({"op": "update" if rid in model.get("requirements", {}) else "add", "kind": "requirements", "id": rid, "value": v})
    # parents must exist before children reference them: order adds parent-first
    order = {o["id"]: i for i, o in enumerate(ops)}
    depth = lambda o, d=0: d if not o["value"].get("parent") or d > 50 else depth(next((p for p in ops if p["id"] == o["value"]["parent"]), {"value": {}}), d + 1)
    ops.sort(key=lambda o: (depth(o), order[o["id"]]))
    return ops, notes
