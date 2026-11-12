"""Industry-standard artifact forms, generated from the model and rendered in the app (not exported to Excel).

- AIAG & VDA FMEA Handbook (2019) DFMEA form sheet — the 7-step layout (structure / function / failure / risk /
  optimization) with Action Priority, one row per (failure effect, failure mode, failure cause) chain.
- DVP&R (Design Verification Plan & Report), the AIAG APQP layout used by automotive and consumer-durable OEMs.
- VCRM / RTM (Verification Cross-Reference Matrix / Requirements Traceability Matrix), ISO/IEC/IEEE 29148-style.
- Requirements specification sheet (29148 attributes: id, type, statement, rationale/source, verification method,
  verifying tests, parent need/regulation, disciplines).
- Hazard / safety-class register (from safety-decision functions and S>=9 failure modes).

Every row carries the model ids it was derived from, so the sheet is a *view* of the thread, not a second truth.
Call form(model, name) -> {title, standard, groups, headers, widths, rows, assess_key?}; names in FORMS."""
from __future__ import annotations
import os, datetime as dt
from . import derive as D

def _focus(m, f):
    """Structure analysis for a failure mode row: next higher level / focus element / next lower level, from the part tree."""
    parts = m["parts"]; alloc = D.element_parts(m, f["kind"], f["element"]) if hasattr(D, "element_parts") else []
    alloc = [p for p in alloc if p in parts]
    if not alloc: return (m["meta"].get("name", "System"), f["element_name"], "—")
    focus = alloc[0]; parent = parts[focus].get("parent"); kids = [parts[c]["name"] for c, cv in parts.items() if cv.get("parent") == focus]
    higher = parts[parent]["name"] if parent in parts else m["meta"].get("name", "System")
    return (higher, ", ".join(parts[p]["name"] for p in alloc[:3]), ", ".join(kids[:4]) or "—")

def _func_levels(m, f):
    """Function analysis: function of next higher level (the requirement the element realizes), of focus element, of next lower level."""
    reqs = D.element_reqs(m, f["kind"], f["element"]) if hasattr(D, "element_reqs") else []
    higher = "; ".join(f"{r}: {m['requirements'][r]['text']}" for r in reqs[:2] if r in m["requirements"]) or "—"
    if f["kind"] == "functions": focus = f"{f['element']}: {f['element_name']}" + (f" ({m['functions'][f['element']].get('perf','')})" if m["functions"][f["element"]].get("perf") else "")
    elif f["kind"] == "interfaces": focus = f"{f['element']}: carry {', '.join(m['interfaces'][f['element']].get('items', []))}"
    else: focus = f"{f['element']}: {f['element_name']}"
    return higher, focus

def dfmea(m):
    rows = []; fm = D.fmea(m)
    for i, f in enumerate(fm, 1):
        hi, fo, lo = f['higher'], f['focus'], f['lower']; fh, ff = _func_levels(m, f)
        det = "; ".join(f"{t} {m['tests'][t]['name']}" for t in f["tests"] if t in m["tests"]) or "—"
        rows.append([i, f["id"], "", hi, fo, lo, fh, ff, "—", f["effect"], f["S"], f["mode"], f["cause"], f["controls"], f["O"], det, f["D"], f["AP"],
                     "SC" if f["S"] >= 9 else "", "", "", "", "", "", "", "", "", "", "", "", f"{f['element']} / {f['guide']}; disciplines: {', '.join(f.get('disciplines', []))}"])
    groups = [("", 3), ("STRUCTURE ANALYSIS (STEP 2)", 3), ("FUNCTION ANALYSIS (STEP 3)", 3), ("FAILURE ANALYSIS (STEP 4)", 4), ("RISK ANALYSIS (STEP 5)", 6), ("OPTIMIZATION (STEP 6)", 13)]
    headers = ["Issue #", "FM id", "History / Change Authorization", "1. Next Higher Level", "2. Focus Element", "3. Next Lower Level or Characteristic Type",
               "1. Next Higher Level Function and Requirement", "2. Focus Element Function and Requirement", "3. Next Lower Level Function and Requirement or Characteristic",
               "1. Failure Effects (FE) to the Next Higher Level Element and/or End User", "Severity (S) of FE", "2. Failure Mode (FM) of the Focus Element", "3. Failure Cause (FC) of the Next Lower Element or Characteristic",
               "Current Prevention Control (PC) of FC", "Occurrence (O) of FC", "Current Detection Controls (DC) of FC or FM", "Detection (D) of FC/FM", "DFMEA AP", "Filter Code (Optional)",
               "DFMEA Prevention Action", "DFMEA Detection Action", "Responsible Person's Name", "Target Completion Date", "Status", "Action Taken with Pointer to Evidence", "Completion Date", "Severity (S)", "Occurrence (O)", "Detection (D)", "DFMEA AP", "Remarks"]
    widths = [5, 8, 8, 10, 14, 16, 26, 24, 10, 30, 7, 28, 30, 28, 7, 28, 7, 7, 6, 18, 18, 14, 12, 10, 18, 12, 7, 7, 7, 7, 24]
    return groups, headers, widths, rows

def dvpr(m):
    vm = D.verification_matrix(m); rows = []
    for i, t in enumerate(vm, 1):
        req_txt = "; ".join(f"{r}: {m['requirements'][r]['text']}" for r in t["reqs"] if r in m["requirements"])
        rows.append([i, t["id"], t["name"], t["method"], req_txt, t["passfail"], t.get("units", ""), "", t.get("samples", ""), t["gate"], "", "", "", t.get("status", "planned"), "", ", ".join(t["fms"]), ", ".join(t["constraints"])])
    groups = [("TEST PLAN", 10), ("TEST REPORT", 5), ("TRACE", 2)]
    headers = ["Item #", "Test id", "Test Name / Description", "Test Procedure / Specification (standard, severity)", "Design Requirement(s) verified", "Acceptance Criteria", "Units", "Responsibility",
               "Sample Size / Qty", "Test Stage (gate)", "Timing — Start", "Timing — Complete", "Test Results (actual)", "Pass / Fail / Status", "Notes / Deviations", "Failure modes covered", "Constraints evaluated"]
    widths = [6, 8, 26, 34, 44, 30, 8, 14, 10, 10, 11, 11, 24, 12, 24, 20, 16]
    return groups, headers, widths, rows

def vcrm(m):
    rows = []
    for rid, r in m["requirements"].items():
        funcs = [f for f, fv in m["functions"].items() if rid in fv["reqs"]]
        parts = sorted({p for f in funcs for p in m["functions"][f]["alloc"] if p in m["parts"]})
        for t in (r["tests"] or ["—"]):
            tv = m["tests"].get(t, {})
            rows.append([rid, r["type"], r["text"], ", ".join(r.get("from_", []) + r.get("regs", [])), ", ".join(funcs), ", ".join(m["parts"][p]["name"] for p in parts), r["verify"], t, tv.get("name", ""), tv.get("method", ""), tv.get("gate", ""), tv.get("passfail", ""), tv.get("status", "planned")])
    groups = [("REQUIREMENT", 6), ("VERIFICATION", 7)]
    headers = ["Req id", "Type", "Requirement statement", "Parent (need / regulation)", "Realized by functions", "Allocated to parts", "Method (A/I/D/T)", "Test id", "Test name", "Procedure", "Stage", "Acceptance criteria", "Status"]
    widths = [8, 8, 50, 16, 16, 28, 9, 8, 24, 30, 8, 28, 10]
    return groups, headers, widths, rows

def req_spec(m):
    dm = D.discipline_matrix(m); rows = []
    for rid, r in m["requirements"].items():
        src = r.get("from_", []) + r.get("regs", [])
        rationale = "; ".join((m["needs"].get(s, {}).get("text") or m["regulations"].get(s, {}).get("trigger") or s) for s in src)
        rows.append([rid, r["type"], r["text"], r.get("attr", ""), rationale, ", ".join(src), r["verify"], ", ".join(r["tests"]), ", ".join(dm.get(rid, [])), r.get("uc", ""), "approved" if r.get("status") is None else r["status"]])
    groups = [("REQUIREMENTS SPECIFICATION (ISO/IEC/IEEE 29148 attributes)", 11)]
    headers = ["Id", "Type", "Statement", "Attribute / measurable condition", "Rationale (source need / regulation)", "Source ids", "Verification method", "Verified by", "Disciplines", "Use case", "Status"]
    widths = [8, 8, 60, 22, 44, 14, 10, 16, 18, 8, 9]
    return groups, headers, widths, rows

def hazards(m):
    rows = []; n = 0
    for f, fv in m["functions"].items():
        if fv.get("safety_decision"):
            n += 1; fms = [x for x in D.fmea(m) if x["element"] == f and x["S"] >= 8]
            rows.append([f"HZ-{n:02d}", f, fv["name"], fv["safety_decision"], "; ".join(x["effect"] for x in fms) or "—", max([x["S"] for x in fms] or [0]), "; ".join(x["controls"] for x in fms) or "—", ", ".join(sorted({t for x in fms for t in x["tests"]})) or "—", ", ".join(fv["reqs"])])
    for x in D.fmea(m):
        if x["S"] >= 9 and not m["functions"].get(x["element"], {}).get("safety_decision"):
            n += 1; rows.append([f"HZ-{n:02d}", x["element"], x["element_name"], x["guide"], x["effect"], x["S"], x["controls"], ", ".join(x["tests"]), x["id"]])
    groups = [("HAZARD / SAFETY-CLASS REGISTER", 9)]
    headers = ["Hazard id", "Element", "Name", "Hazardous condition / safety decision", "Worst credible effect", "Severity", "Mitigations (design controls)", "Verification", "Trace"]
    widths = [8, 8, 26, 36, 40, 8, 44, 24, 16]
    return groups, headers, widths, rows

RATING_TABLES = {
    "Severity (S)": [(10, "Affects safe operation / regulatory non-compliance without warning"), (9, "…with warning"), (8, "Loss of primary function"), (7, "Degradation of primary function"), (6, "Loss of secondary function"), (5, "Degradation of secondary function"), (4, "Appearance/noise, noticed by most"), (3, "…by many"), (2, "…by discriminating customers"), (1, "No discernible effect")],
    "Occurrence (O)": [(10, "Extremely high; new technology, no prevention"), (8, "High; new design with changes"), (6, "Moderate; similar design, some changes"), (4, "Low; proven design, minor changes"), (2, "Very low; carry-over with field history"), (1, "Extremely low; failure eliminated by design")],
    "Detection (D)": [(10, "No test or analysis"), (8, "Pass/fail test after design freeze"), (6, "Test on prototype, verified before freeze"), (4, "Analysis + test correlated"), (2, "Proven analysis or test to failure, correlated"), (1, "Failure mode cannot occur / fully prevented")],
}

FORMS = {
    "dfmea": ("DFMEA — AIAG & VDA form", "AIAG & VDA FMEA Handbook (2019) form sheet; Action Priority per Table AP", dfmea),
    "dvpr": ("DVP&R", "Design Verification Plan & Report (AIAG APQP)", dvpr),
    "vcrm": ("VCRM / RTM", "Verification Cross-Reference Matrix (ISO/IEC/IEEE 29148)", vcrm),
    "reqspec": ("Requirements specification", "System Requirements Specification attributes (ISO/IEC/IEEE 29148)", req_spec),
    "hazards": ("Hazard register", "Safety-decision functions and S ≥ 9 failure modes", hazards),
}

def form(m, name):
    title, std, fn = FORMS[name]; groups, headers, widths, rows = fn(m)
    rows = [[(", ".join(map(str, c)) if isinstance(c, (list, tuple, set)) else c) for c in r] for r in rows]
    out = {"name": name, "title": title, "standard": std, "groups": groups, "headers": headers, "widths": widths, "rows": rows}
    if name == "dfmea":
        out["rating_tables"] = RATING_TABLES
        # which assessment each row edits, and which columns map to which assessment field
        fm = D.fmea(m); idx = {(a["element"], a["guide"]): k for k, a in m["fm_assessments"].items()}
        out["row_keys"] = [idx.get((f["element"], f["guide"])) for f in fm]
        out["editable"] = {headers.index(h): fld for h, fld in [
            ("1. Failure Effects (FE) to the Next Higher Level Element and/or End User", "effect"), ("Severity (S) of FE", "S"), ("2. Failure Mode (FM) of the Focus Element", "mode"),
            ("3. Failure Cause (FC) of the Next Lower Element or Characteristic", "cause"), ("Current Prevention Control (PC) of FC", "controls"), ("Occurrence (O) of FC", "O"), ("Detection (D) of FC/FM", "D")]}
        out["merge_cols"] = [3, 4, 5, 6, 7]   # structure/function cells merge across consecutive rows of the same element
        out["row_elements"] = [f["element"] for f in fm]
    if name in ("work_items", "findings", "handoffs", "risks", "fracas"):
        kind = {"work_items": "work_items", "findings": "findings", "handoffs": "handoffs", "risks": "risks", "fracas": "field_events"}[name]
        out["row_keys"] = [r[0] for r in rows]; out["kind"] = kind
        ed = {"work_items": {"Title": "title", "Priority": "priority", "Status": "status", "Owner": "owner", "Due": "due", "Notes": "notes"},
              "findings": {"Title": "title", "Severity": "severity", "Status": "status", "Owner": "owner", "Action": "action", "Due": "due", "Closed": "closed"},
              "handoffs": {"Evidence / deliverable": "what", "Due": "due", "Status": "status", "Accepted by": "accepted_by", "Note": "note"},
              "risks": {"Title": "title", "Probability (1-5)": "prob", "Impact (1-5)": "impact", "Owner": "owner", "Mitigation": "mitigation", "Status": "status"},
              "fracas": {"Symptom": "symptom", "Disposition": "disposition", "8D status": "eight_d", "Status": "status", "FM id": "fm"}}[name]
        out["editable"] = {headers.index(h): f for h, f in ed.items() if h in headers}
    if name == "pfmea":
        fm = [f for f in D.fmea(m) if f["kind"] == "process"]; idx = {(a["element"], a["guide"]): k for k, a in m["fm_assessments"].items()}
        out["row_keys"] = [idx.get((f["element"], f["guide"])) for f in fm]; out["kind"] = "fm_assessments"
        out["editable"] = {headers.index(h): fld for h, fld in [("Failure effect (FE)", "effect"), ("S", "S"), ("Failure mode (FM)", "mode"), ("Failure cause (FC)", "cause"), ("O", "O"), ("D", "D")]}
        out["rating_tables"] = RATING_TABLES; out["merge_cols"] = [2, 3, 4]; out["row_elements"] = [f["element"] for f in fm]
    if name == "reqspec":
        out["row_keys"] = list(m["requirements"]); out["kind"] = "requirements"
        out["editable"] = {headers.index("Statement"): "text", headers.index("Attribute / measurable condition"): "attr", headers.index("Type"): "type", headers.index("Verification method"): "verify"}
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Matrices and analysis forms derived from the architecture (no new model content needed)

def n2(m):
    """N² diagram: physical parts (or logical components) on the diagonal; off-diagonal cells list the interfaces/items."""
    parts = [p for p, pv in m["parts"].items() if pv.get("parent")]  # leaf-ish: anything below a root
    leafs = [p for p in parts if not any(cv.get("parent") == p for cv in m["parts"].values())]
    used = sorted({x for iv in m["interfaces"].values() for x in (iv["a"], iv["b"])})
    nodes = [p for p in leafs if p in used] + [p for p in used if p not in leafs and p in m["parts"]]
    nodes = list(dict.fromkeys(nodes))
    cell = {}
    for iid, iv in m["interfaces"].items():
        cell.setdefault((iv["a"], iv["b"]), []).append(f"{iid}: {', '.join(iv['items'])}")
        cell.setdefault((iv["b"], iv["a"]), []).append(f"{iid}: {', '.join(iv['items'])}")
    headers = ["↓ from / to →"] + [m["parts"][p]["name"] for p in nodes]
    rows = []
    for a in nodes:
        rows.append([f"{a} {m['parts'][a]['name']}"] + [("■ " + m["parts"][a]["name"]) if a == b else "; ".join(cell.get((a, b), [])) for b in nodes])
    return [("N² — physical interfaces", len(headers))], headers, [18] + [14] * len(nodes), rows

def n2_logical(m):
    lcs = list(m["logical_components"]); cell = {}
    for li, lv in m["logical_interfaces"].items():
        cell.setdefault((lv["a"], lv["b"]), []).append(f"{li}: {lv['flow']}"); cell.setdefault((lv["b"], lv["a"]), []).append(f"{li}: {lv['flow']}")
    headers = ["↓ from / to →"] + [m["logical_components"][l]["name"] for l in lcs]
    rows = [[f"{a} {m['logical_components'][a]['name']}"] + [("■ " + m["logical_components"][a]["name"]) if a == b else "; ".join(cell.get((a, b), [])) for b in lcs] for a in lcs]
    return [("N² — logical interfaces", len(headers))], headers, [18] + [16] * len(lcs), rows

def icd(m):
    """Interface Control Document index: one row per interface with both sides, items, type, functions, requirements, failure modes, tests."""
    fm = D.fmea(m); rows = []
    for iid, iv in m["interfaces"].items():
        pa, pb = m["parts"].get(iv["a"], {}), m["parts"].get(iv["b"], {})
        reqs = sorted({r for f in iv["funcs"] if f in m["functions"] for r in m["functions"][f]["reqs"]})
        fms = [x for x in fm if x["element"] == iid]
        attrs = "; ".join(f"{k}={v}" for k, v in (iv.get("attrs") or {}).items())
        rows.append([iid, iv["name"], f"{iv['a']} {pa.get('name','')} [{pa.get('discipline','')}]", f"{iv['b']} {pb.get('name','')} [{pb.get('discipline','')}]", iv["kind"], ", ".join(iv["items"]), attrs or "—",
                     ", ".join(iv["funcs"]), ", ".join(reqs), ", ".join(x["id"] for x in fms), ", ".join(sorted({t for x in fms for t in x["tests"]})), iv.get("owner_a", "") + " / " + iv.get("owner_b", "") if (iv.get("owner_a") or iv.get("owner_b")) else "—"])
    groups = [("INTERFACE", 7), ("TRACE", 5)]
    headers = ["ICD id", "Interface", "Side A (part, discipline)", "Side B (part, discipline)", "Type", "Items crossing", "Characteristics (voltage, connector, protocol, load, tolerance)", "Functions carried", "Requirements", "Failure modes", "Verified by", "Owners A / B"]
    return groups, headers, [7, 24, 22, 22, 14, 22, 30, 12, 16, 16, 16, 12], rows

def pugh(m):
    """Pugh / weighted decision matrix per trade study; scores optional (−1/0/+1 or weighted), datum marked."""
    rows = []
    for tid, t in m["trades"].items():
        w = t.get("weights") or [1] * len(t["criteria"]); sc = t.get("scores") or {}
        for i, c in enumerate(t["criteria"]):
            row = [tid if i == 0 else "", t["name"] if i == 0 else "", c, w[i] if i < len(w) else 1]
            for o in t["options"]: row.append(sc.get(o, {}).get(c, "") if isinstance(sc.get(o), dict) else "")
            rows.append(row)
        tot = [tid, "Σ weighted", "", ""]
        for o in t["options"]:
            s_ = sc.get(o, {}) if isinstance(sc.get(o), dict) else {}
            tot.append(sum((w[i] if i < len(w) else 1) * float(s_.get(c, 0) or 0) for i, c in enumerate(t["criteria"])) if s_ else "")
        rows.append(tot); rows.append([tid, "Recommendation", t["recommendation"], "", *[("← datum" if t.get("datum") == o else "") for o in t["options"]]]); rows.append(["", "affects " + ", ".join(t.get("affects", [])), "", ""] + [""] * len(t["options"]))
    maxo = max([len(t["options"]) for t in m["trades"].values()] or [2])
    headers = ["Trade", "Study", "Criterion", "Weight"] + [f"Option {i+1}" for i in range(maxo)]
    rows = [r + [""] * (len(headers) - len(r)) for r in rows]
    # put option names in the first row of each trade
    out = []; seen = set()
    for r in rows:
        if r[0] and r[0] not in seen and r[0] in m["trades"]:
            seen.add(r[0]); t = m["trades"][r[0]]; hdr = [r[0], t["name"], "options →", ""] + list(t["options"]) + [""] * (maxo - len(t["options"])); out.append(hdr); r = ["", ""] + r[2:]
        out.append(r)
    return [("PUGH / WEIGHTED DECISION MATRIX", len(headers))], headers, [7, 26, 20, 7] + [22] * maxo, out

def fta(m):
    """Fault trees: top event per safety-decision function; intermediate = High/Medium-AP failure modes; basic events = causes."""
    fm = D.fmea(m); rows = []
    tops = [(f, fv) for f, fv in m["functions"].items() if fv.get("safety_decision")]
    for n, (f, fv) in enumerate(tops, 1):
        rows.append([f"FT-{n:02d}", "TOP", f"Unsafe outcome of {f} {fv['name']}", fv["safety_decision"], "OR", "", "", "", ""])
        for x in [x for x in fm if x["element"] == f]:
            rows.append([f"FT-{n:02d}", "  INTERMEDIATE", x["id"] + " " + x["mode"], x["effect"], "OR", x["S"], x["O"], x["AP"], ", ".join(x["tests"])])
            for c in [c.strip() for c in x["cause"].replace(";", ",").split(",") if c.strip()]:
                rows.append([f"FT-{n:02d}", "    BASIC", c, "", "", "", "", "", x["controls"]])
        # interfaces and transitions that feed this function
        for iid, iv in m["interfaces"].items():
            if f in iv["funcs"]:
                for x in [x for x in fm if x["element"] == iid]:
                    rows.append([f"FT-{n:02d}", "  INTERMEDIATE", f"{x['id']} {iid}: {x['mode']}", x["effect"], "OR", x["S"], x["O"], x["AP"], ", ".join(x["tests"])])
        for tid, tv in m["transitions"].items():
            if tv.get("func") == f:
                for x in [x for x in fm if x["element"] == tid]:
                    rows.append([f"FT-{n:02d}", "  INTERMEDIATE", f"{x['id']} {tid}: {x['mode']}", x["effect"], "OR", x["S"], x["O"], x["AP"], ", ".join(x["tests"])])
    headers = ["Tree", "Level", "Event", "Consequence / condition", "Gate", "S", "O", "AP", "Barriers (controls) / verification"]
    return [("FAULT TREE (tabular) — top events from safety decisions", len(headers))], headers, [7, 14, 40, 36, 6, 4, 4, 5, 36], rows

def drbfm(m):
    """Design Review Based on Failure Mode: for each architecture decision (a change), what changed, concerns, affected
    functions / failure modes, and the tests that must cover it — built from the impact graph."""
    rows = []
    for ad, a in m["arch_decisions"].items():
        im = D.impact(m, ad)
        reqs = a["reqs"]; funcs = sorted({f for r in reqs for f, fv in m["functions"].items() if r in fv["reqs"]})
        fms = [x for x in D.fmea(m) if x["element"] in funcs]
        rows.append([ad, a["title"], a.get("change_from") or "new design", a["decision"], "; ".join(a.get("concerns") or a.get("consequences", [])) or "—",
                     ", ".join(funcs), ", ".join(x["id"] for x in fms if x["AP"] in ("H", "M")), ", ".join(sorted({t for x in fms for t in x["tests"]})) or "—",
                     ", ".join(im["tests_to_rerun"]) or "—", a["rationale"]])
    headers = ["Decision", "Change (title)", "Changed from", "Changed to", "Concerns (what could go wrong because of the change)", "Functions affected", "Failure modes (H/M)", "Existing verification", "Tests to re-run (impact)", "Rationale"]
    return [("DRBFM — design review based on failure mode", len(headers))], headers, [7, 22, 18, 30, 34, 14, 18, 18, 18, 30], rows

def dependency_matrix(m, rows_kind, cols_kind):
    """Generic dependency matrix (the Cameo 'dependency matrix'): rows × columns, cell = relation names from the trace graph."""
    E = D.trace(m); rk = m[rows_kind]; ck = m[cols_kind]; cell = {}
    for a, rel, b in E:
        if a in rk and b in ck: cell.setdefault((a, b), set()).add(rel)
        if b in rk and a in ck: cell.setdefault((b, a), set()).add(rel + " ←")
    def nm(k, i): v = m[k][i]; return v.get("name") or v.get("text", "")[:30] or v.get("title", "") or i
    headers = [f"{rows_kind} ↓ / {cols_kind} →"] + [f"{c} {nm(cols_kind, c)[:18]}" for c in ck]
    rows = [[f"{r} {nm(rows_kind, r)[:30]}"] + ["; ".join(sorted(cell.get((r, c), []))) for c in ck] for r in rk]
    rows = [r for r in rows if any(x for x in r[1:])]
    return [(f"DEPENDENCY MATRIX {rows_kind} × {cols_kind}", len(headers))], headers, [26] + [12] * len(ck), rows

FORMS.update({
    "n2": ("N² diagram — physical", "Interface N² matrix over parts (DoD SE Fundamentals / NASA SE Handbook)", n2),
    "n2l": ("N² diagram — logical", "Interface N² matrix over logical components", n2_logical),
    "icd": ("Interface Control Document index", "One row per interface: sides, items, characteristics, trace (MIL-STD-961/NASA ICD outline)", icd),
    "pugh": ("Trade studies — Pugh / weighted matrix", "Decision matrix per trade study (Pugh 1981; INCOSE SEH §4.3)", pugh),
    "fta": ("Fault trees (tabular)", "Top events from safety decisions; intermediate events from FMEA; basic events from causes (IEC 61025)", fta),
    "drbfm": ("DRBFM", "Design Review Based on Failure Mode — change-focused review of each architecture decision (Toyota GD³)", drbfm),
})

MATRIX_PAIRS = [("requirements", "functions"), ("functions", "parts"), ("requirements", "tests"), ("needs", "requirements"), ("regulations", "requirements"), ("logical_components", "parts"), ("functions", "logical_components"), ("constraints", "tests")]


# ---------------------------------------------------------------------------------------------------------------------
# Whole-company forms: manufacturing, supply chain, program, quality/field

def pfmea(m):
    """AIAG-VDA PFMEA: process steps × process guide words (candidates), rows from fm_assessments with element = process step."""
    fm = [f for f in D.fmea(m) if f["kind"] == "process"]; rows = []
    for i, f in enumerate(fm, 1):
        ps = m["process_steps"][f["element"]]
        rows.append([i, f["id"], ps["station"], ps["name"], ", ".join(ps.get("characteristics", [])), f["effect"], f["S"], f["mode"], f["cause"], ps.get("controls", "") or f["controls"], f["O"],
                     "; ".join(f"{t} {m['tests'][t]['name']}" for t in f["tests"] if t in m["tests"]) or (f"EOL {ps['eol_test']}" if ps.get("eol_test") else "—"), f["D"], f["AP"], "SC" if f["S"] >= 9 else "", f["guide"]])
    groups = [("", 2), ("STRUCTURE / PROCESS STEP", 3), ("FAILURE ANALYSIS", 4), ("RISK ANALYSIS", 6), ("", 1)]
    headers = ["#", "FM id", "Station / work element", "Process step", "Product / process characteristics", "Failure effect (FE)", "S", "Failure mode (FM)", "Failure cause (FC)", "Prevention control", "O", "Detection control (incl. EOL test)", "D", "AP", "SC", "Guide word"]
    return groups, headers, [4, 8, 16, 24, 26, 30, 5, 28, 30, 28, 5, 28, 5, 5, 5, 12], rows

def control_plan(m):
    rows = []
    for p, ps in sorted(m.get("process_steps", {}).items(), key=lambda kv: kv[1].get("seq", 0)):
        fms = [f for f in D.fmea(m) if f["element"] == p]
        chars = ps.get("characteristics") or ["—"]
        for c in chars:
            rows.append([ps.get("seq", ""), p, ps["station"], ps["name"], c, "SC" if any(f["S"] >= 9 for f in fms) else "", ", ".join(m["parts"][x]["name"] for x in ps.get("parts", []) if x in m["parts"]),
                         ps.get("controls", ""), (m["tests"][ps["eol_test"]]["name"] if ps.get("eol_test") in m["tests"] else "—"), (m["tests"][ps["eol_test"]].get("passfail", "") if ps.get("eol_test") in m["tests"] else ""), ps.get("cycle_s", ""), m.get("teams", {}).get(ps.get("team"), {}).get("name", ""), ", ".join(f["id"] for f in fms)])
    headers = ["Seq", "Step id", "Station", "Process step", "Characteristic", "Special char.", "Parts", "Control method (prevention)", "Measurement / EOL test", "Spec / pass-fail", "Cycle (s)", "Owner team", "PFMEA rows"]
    return [("CONTROL PLAN (AIAG APQP)", len(headers))], headers, [4, 7, 14, 24, 22, 7, 22, 30, 24, 20, 7, 12, 14], rows

def avl(m):
    rows = []
    for p, pv in m["parts"].items():
        if pv.get("parent") is None and not pv.get("make_buy"): continue
        sp = m.get("suppliers", {}).get(pv.get("supplier") or "", {})
        rows.append([p, pv["name"], pv.get("discipline", ""), pv.get("make_buy", ""), pv.get("lifecycle", "active"), pv.get("supplier") or "", sp.get("name", ""), sp.get("status", ""), sp.get("country", ""), sp.get("lead_time_d", ""), (m["suppliers"][sp["second_source"]]["name"] if sp.get("second_source") in m.get("suppliers", {}) else ""), pv.get("attrs", {}).get("cost_usd", ""), pv.get("attrs", {}).get("mass_g", ""), sp.get("risk", "")])
    headers = ["Part", "Name", "Discipline", "Make/buy", "Lifecycle", "Supplier id", "Supplier", "Status", "Country", "Lead time (d)", "Second source", "Cost (USD)", "Mass (g)", "Supply risk"]
    return [("APPROVED VENDOR LIST / SOURCING", len(headers))], headers, [7, 22, 10, 8, 9, 9, 20, 9, 9, 9, 18, 9, 8, 20], rows

def risk_register(m):
    rows = []
    for r, rv in m.get("risks", {}).items():
        score = int(rv["prob"]) * int(rv["impact"]); lvl = "H" if score >= 15 else "M" if score >= 8 else "L"
        rows.append([r, rv["title"], rv["prob"], rv["impact"], score, lvl, rv.get("owner", ""), m.get("teams", {}).get(rv.get("team"), {}).get("name", ""), rv.get("mitigation", ""), rv.get("status", "open"), ", ".join(rv.get("links", []))])
    headers = ["Risk", "Title", "Probability (1-5)", "Impact (1-5)", "Score", "Level", "Owner", "Team", "Mitigation", "Status", "Linked elements"]
    rows.sort(key=lambda r: -r[4])
    return [("PROGRAM RISK REGISTER (5×5)", len(headers))], headers, [7, 30, 8, 8, 6, 5, 12, 12, 36, 8, 18], rows

def fracas(m):
    rows = []
    for e, ev in sorted(m.get("field_events", {}).items(), key=lambda kv: kv[1]["date"], reverse=True):
        fm = next((f for f in D.fmea(m) if f["id"] == ev.get("fm")), None)
        rows.append([e, ev["date"], ev.get("unit", ""), ev["symptom"], ev.get("count", 1), ev.get("severity", ""), ", ".join(m["parts"][p]["name"] for p in ev.get("parts", []) if p in m["parts"]), ev.get("fm", ""), fm["mode"] if fm else "— not tied to a failure mode", fm["AP"] if fm else "", ev.get("disposition", ""), ev.get("eight_d", ""), ev.get("status", "open")])
    headers = ["Event", "Date", "Unit / lot", "Symptom", "Count", "Severity", "Parts", "FM id", "Failure mode (DFMEA)", "AP", "Disposition", "8D status", "Status"]
    return [("FRACAS — FIELD FAILURE LOG", len(headers))], headers, [7, 10, 12, 34, 6, 8, 22, 8, 30, 5, 24, 10, 8], rows

def work_items(m):
    rows = []
    order = {"blocked": 0, "open": 1, "in_progress": 2, "done": 3}
    for w, wv in sorted(m.get("work_items", {}).items(), key=lambda kv: (order.get(kv[1]["status"], 9), kv[1].get("due", ""))):
        rows.append([w, wv["title"], wv.get("priority", "P2"), wv["status"], wv["owner"], m.get("teams", {}).get(wv.get("team"), {}).get("name", ""), wv.get("due", ""), wv.get("gate") or "", ", ".join(wv.get("links", [])), wv.get("notes", "")])
    headers = ["Item", "Title", "Priority", "Status", "Owner", "Team", "Due", "Gate", "Linked elements", "Notes"]
    return [("WORK ITEMS", len(headers))], headers, [7, 34, 6, 10, 12, 12, 10, 6, 20, 24], rows

def findings_log(m):
    rows = []
    sev = {"critical": 0, "major": 1, "minor": 2}
    for f, fv in sorted(m.get("findings", {}).items(), key=lambda kv: (kv[1]["status"] == "closed", sev.get(kv[1]["severity"], 9))):
        rows.append([f, fv["title"], fv["severity"], fv["status"], fv.get("source", ""), fv.get("element", ""), fv.get("owner", ""), fv.get("action", ""), fv.get("due", ""), fv.get("gate") or "", fv.get("closed", "")])
    headers = ["Finding", "Title", "Severity", "Status", "Source", "Element", "Owner", "Action", "Due", "Gate", "Closed"]
    return [("FINDINGS (REVIEWS, AUDITS, TESTS, FIELD)", len(headers))], headers, [7, 34, 8, 8, 9, 10, 12, 30, 10, 6, 10], rows

def handoffs_board(m):
    rows = []; teams = m.get("teams", {})
    for h, hv in sorted(m.get("handoffs", {}).items(), key=lambda kv: (kv[1]["status"] != "pending", kv[1].get("due", ""))):
        rows.append([h, teams.get(hv["from_team"], {}).get("name", hv["from_team"]), teams.get(hv["to_team"], {}).get("name", hv["to_team"]), hv["what"], ", ".join(hv.get("elements", [])), hv.get("gate") or "", hv.get("due", ""), hv["status"], hv.get("accepted_by", ""), hv.get("note", "")])
    headers = ["Handoff", "From team", "To team", "Evidence / deliverable", "Elements", "Gate", "Due", "Status", "Accepted by", "Note"]
    return [("CROSS-FUNCTIONAL HANDOFFS", len(headers))], headers, [7, 14, 14, 32, 20, 6, 10, 9, 14, 24], rows

FORMS.update({
    "pfmea": ("PFMEA — AIAG & VDA", "Process FMEA over the process flow (process steps × process guide words)", pfmea),
    "control_plan": ("Control plan", "AIAG APQP control plan from process steps, characteristics and EOL tests", control_plan),
    "avl": ("AVL / sourcing", "Approved vendor list: supplier, status, lead time, second source, cost, lifecycle", avl),
    "risks": ("Program risk register", "5×5 probability × impact with owners and mitigations", risk_register),
    "fracas": ("FRACAS", "Field failure reporting, analysis and corrective action, tied to the DFMEA", fracas),
    "work_items": ("Work items", "Program tasks with owners, teams, due dates, gates and linked elements", work_items),
    "findings": ("Findings", "Review, audit, test and field findings with closure", findings_log),
    "handoffs": ("Handoffs", "Cross-functional evidence handoffs between teams, pending until accepted", handoffs_board),
})

from . import business as _B
FORMS.update(_B.FORMS)   # claims, cost, markets, staffing
