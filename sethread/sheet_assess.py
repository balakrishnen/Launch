"""Spreadsheet assessment: read a customer's workbook to learn what they are doing and what Launch would give them.

For every sheet: which engineering artifact it is (requirements, FMEA, DVP&R, BOM, control plan, risk register, schedule,
test log, CAPA, ECO, quotes, trade study...), how its columns map to Launch fields, which columns Launch does not model yet
(product gaps to learn from), how much manual machinery it carries (formulas, cross-sheet links, dropdown lists, colour
coding), and what Launch adds over the sheet for that artifact. Nothing is exported back to a spreadsheet."""
from __future__ import annotations
import io, re

def _n(s): return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

# artifact signatures: keyword -> Launch field. A header matches a keyword when the keyword appears in it.
SIG = {
    "reqspec": dict(title="Requirements specification", kind="requirements", where="Engineering › Requirement specification",
        keys={"requirement": "text", "shall": "text", "verification": "verify", "verify": "verify", "parent": "parent", "priority": "priority", "rationale": "attrs.rationale",
              "status": "status", "owner": "owner", "related": "related", "source": "from_", "trace": "tests", "subsystem": "attrs.subsystem", "req id": "id"},
        adds=["Flow-down tree with parent/children and suspect links when anything upstream changes", "Quality checks on every statement (INCOSE GtWR-style: shall, measurable, atomic)",
              "Trace to needs, regulations, functions, tests and results; the VCRM is computed, not typed", "Revision history per requirement instead of a change-log tab"]),
    "dfmea": dict(title="DFMEA", kind="fm_assessments", where="Risk › DFMEA (AIAG-VDA form)",
        keys={"failure mode": "mode", "effect": "effect", "cause": "cause", "severity": "S", "occurrence": "O", "detection": "D", "rpn": "(RPN, replaced by AP)", "action priority": "AP",
              "prevention": "controls", "detection control": "tests", "recommended action": "actions", "responsib": "actions.owner", "target date": "actions.due", "function": "element", "item": "element", "component": "element"},
        adds=["Rows generated from functions, interfaces and states (nothing missed), with AIAG-VDA Action Priority instead of RPN", "Detection controls linked to real tests and their results",
              "Actions with owner, due, evidence and revised ratings tracked to closure", "Process and design FMEA connected to the control plan and special characteristics"]),
    "pfmea": dict(title="PFMEA", kind="fm_assessments", where="Industrialization › PFMEA",
        keys={"process step": "element", "operation": "element", "failure mode": "mode", "effect": "effect", "cause": "cause", "severity": "S", "occurrence": "O", "detection": "D", "rpn": "(RPN, replaced by AP)", "station": "element"},
        adds=["Rows per process step × process guide word", "Feeds the control plan and special characteristics automatically"]),
    "dvpr": dict(title="DVP&R / test plan", kind="tests", where="Verification › DVP&R",
        keys={"test": "name", "procedure": "method", "acceptance": "passfail", "criteria": "passfail", "sample": "samples", "result": "result", "responsib": "owner_team", "start": "start",
              "complete": "end", "finish": "end", "pass": "status", "status": "status", "requirement": "requirements.tests", "gate": "gate", "build": "gate"},
        adds=["Results from test runs with metrics and limits, not typed in", "Every requirement's verification status live; tests made suspect when a requirement changes", "Failure modes and constraints each test covers"]),
    "control_plan": dict(title="Control plan", kind="process_steps", where="Industrialization › Control plan",
        keys={"characteristic": "characteristics.name", "specification": "characteristics.spec", "tolerance": "characteristics.spec", "measurement": "characteristics.method", "evaluation": "characteristics.method",
              "sample size": "characteristics.size", "frequency": "characteristics.freq", "control method": "characteristics.control", "reaction plan": "characteristics.reaction", "machine": "machine", "process name": "name", "special": "characteristics.sc"},
        adds=["Generated from process steps and the PFMEA; SC/CC carried from the FMEAs", "Phase (prototype, pre-launch, production) from the gates"]),
    "bom": dict(title="Bill of materials", kind="parts", where="Engineering › Indented BOM",
        keys={"part number": "id", "part no": "id", "p n": "id", "description": "name", "qty": "attrs.qty", "quantity": "attrs.qty", "rev": "attrs.rev", "level": "parent", "parent": "parent",
              "supplier": "supplier", "vendor": "supplier", "mpn": "attrs.mpn", "manufacturer": "attrs.mpn", "cost": "attrs.cost_usd", "price": "attrs.cost_usd", "uom": "attrs.uom", "make buy": "make_buy", "material": "attrs.material", "weight": "attrs.mass_g", "mass": "attrs.mass_g"},
        adds=["Cost roll-up against target and AVL/second-source checks", "ECO impact and revision bumps per part", "Failure modes, tests and interfaces per part"]),
    "risks": dict(title="Risk register", kind="risks", where="Program › Risks",
        keys={"risk": "title", "probability": "prob", "likelihood": "prob", "impact": "impact", "consequence": "impact", "mitigation": "mitigation", "owner": "owner", "status": "status", "score": "(computed)"},
        adds=["Risks linked to the parts, suppliers, tests and findings they concern", "5×5 matrix and burn-down computed"]),
    "work_items": dict(title="Task list / schedule", kind="work_items", where="Program › Work items",
        keys={"task": "title", "activity": "title", "start": "(start)", "finish": "due", "due": "due", "end date": "due", "owner": "owner", "assigned": "owner", "status": "status", "complete": "status", "duration": "(duration)", "predecessor": "(dependency)", "milestone": "gate"},
        adds=["Work tied to gates, deliverables and the elements it changes", "Gate readiness computed from deliverable checks"]),
    "test_log": dict(title="Test data / results log", kind="test_runs", where="Verification › Test report log",
        keys={"serial": "unit", "unit": "unit", "date": "date", "result": "result", "pass": "result", "measured": "metrics", "value": "metrics", "limit": "limits", "operator": "operator", "station": "station", "test": "test"},
        adds=["Runs linked to tests, requirements and units; CDA trends and suspect results after a requirement change"]),
    "capa": dict(title="CAPA / 8D log", kind="capa", where="Quality › CAPA",
        keys={"root cause": "root_cause", "containment": "containment", "corrective": "corrective", "preventive": "preventive", "verification": "verified", "8d": "(8D)", "problem": "title", "d1": "(8D)", "d4": "root_cause"},
        adds=["CAPAs tied to the failure mode, test or field event that raised them, and to the DFMEA row they update"]),
    "eco": dict(title="Engineering change log", kind="change_orders", where="Engineering › Change orders",
        keys={"change": "title", "eco": "id", "ecn": "id", "ecr": "id", "reason": "reason", "affected": "affected", "approv": "approvals", "effectivity": "effectivity", "disposition": "(disposition)"},
        adds=["Impact computed (parts, tests, tooling, open POs) and DRBFM generated", "Release bumps part revisions"]),
    "procurement": dict(title="Quotes / sourcing", kind="quotes", where="Supply chain › Procurement",
        keys={"supplier": "supplier", "vendor": "supplier", "quote": "id", "unit price": "unit_cost_usd", "price": "unit_cost_usd", "moq": "moq", "lead time": "lead_time_d", "tooling": "tooling_usd", "incoterm": "incoterm"},
        adds=["Need-by dates from the next build; late-order and single-source flags"]),
    "pugh": dict(title="Trade study / decision matrix", kind="trades", where="Engineering › Trade studies",
        keys={"criteria": "criteria", "criterion": "criteria", "weight": "weights", "option": "options", "alternative": "options", "score": "scores", "datum": "datum", "baseline": "datum"},
        adds=["Scores with their evidence, sensitivity, and the decision recorded on the architecture"]),
    "tooling": dict(title="Tooling tracker", kind="tooling", where="Industrialization › Tooling",
        keys={"tool": "tool_id", "mold": "tool_id", "cavit": "cavities", "t0": "t0", "t1": "t1", "t2": "t2", "ppap": "ppap", "fai": "fai", "kickoff": "kickoff"},
        adds=["T1 vs build date checks and PPAP status per gate"]),
    "icd": dict(title="Interface list / ICD", kind="interfaces", where="Engineering › ICD index",
        keys={"interface": "name", "signal": "attrs.signal", "connector": "attrs.connector", "pin": "attrs.pin", "protocol": "attrs.protocol", "voltage": "attrs.voltage", "from": "a", "to": "b"},
        adds=["N² matrices, interface failure modes and owners per side"]),
}

def _match(headers):
    hs = [_n(h) for h in headers if str(h).strip()]
    best = []
    for form, sg in SIG.items():
        hit = {}
        for h in hs:   # the longest keyword wins ("detection control" over "detection")
            ks = sorted((k for k in sg["keys"] if k in h), key=len, reverse=True)
            if ks: hit[h] = sg["keys"][ks[0]]
        score = len(set(hit.values()))
        if score: best.append((score, form, hit))
    best.sort(key=lambda x: -x[0])
    return best

def _header_row(rows):
    """First row with several text cells that looks like a header (title rows above are common)."""
    for i, r in enumerate(rows[:20]):
        txt = [c for c in r if isinstance(c, str) and c.strip() and not c.strip().startswith("=")]
        if len(txt) >= 3 and len(txt) >= 0.6 * len([c for c in r if c not in (None, "")]): return i
    return 0

def assess(data: bytes, name: str) -> dict:
    sheets = []
    if name.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        wbv = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        wbf = openpyxl.load_workbook(io.BytesIO(data), data_only=False)
        for ws in wbv.worksheets:
            wf = wbf[ws.title]
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            frm = [c.value for row in wf.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
            xref = sum(1 for f in frm if "!" in f)
            dv = sum(len(x.sqref.ranges) for x in (wf.data_validations.dataValidation if wf.data_validations else []))
            cf = len(list(wf.conditional_formatting))
            sheets.append(dict(name=ws.title, rows=rows, formulas=len(frm), cross_sheet=xref, dropdowns=dv, color_rules=cf,
                               sample_formulas=list(dict.fromkeys(re.sub(r"\d+", "#", f) for f in frm))[:5]))
    else:
        import csv
        txt = data.decode("utf-8-sig", errors="replace"); dialect = csv.excel_tab if "\t" in txt.splitlines()[0] else csv.excel
        sheets.append(dict(name=name, rows=[list(r) for r in csv.reader(io.StringIO(txt), dialect)], formulas=0, cross_sheet=0, dropdowns=0, color_rules=0, sample_formulas=[]))
    out = []
    for sh in sheets:
        rows = [r for r in sh["rows"] if any(c not in (None, "") for c in r)]
        if not rows: continue
        hi = _header_row(rows); headers = [str(c).strip() for c in rows[hi] if c not in (None, "")]; body = rows[hi + 1:]
        m = _match(headers); top = m[0] if m and m[0][0] >= 2 else None
        res = dict(sheet=sh["name"], rows=len(body), columns=headers, formulas=sh["formulas"], cross_sheet=sh["cross_sheet"], dropdowns=sh["dropdowns"], color_rules=sh["color_rules"], sample_formulas=sh["sample_formulas"])
        if top:
            score, form, hit = top; sg = SIG[form]
            mapped = [{"column": c, "launch_field": hit[_n(c)]} for c in headers if _n(c) in hit]
            unmapped = [c for c in headers if _n(c) not in hit]
            res.update(artifact=sg["title"], form=form, kind=sg["kind"], where=sg["where"], confidence=round(min(1.0, score / 5), 2),
                       also_looks_like=[SIG[f]["title"] for s, f, _ in m[1:3] if s >= 2], mapped=mapped, unmapped=unmapped, launch_adds=sg["adds"])
        else:
            res.update(artifact="Unrecognized (keep as a Launch table)", form=None, kind="tables", where="Office › Tables", confidence=0, mapped=[], unmapped=headers,
                       launch_adds=["Kept whole as a Launch table with formulas over model data; tell us what it tracks so it can become a first-class artifact"])
        manual = []
        if sh["formulas"]: manual.append(f"{sh['formulas']} formulas" + (f", {sh['cross_sheet']} reaching other sheets" if sh["cross_sheet"] else ""))
        if sh["dropdowns"]: manual.append(f"{sh['dropdowns']} dropdown lists")
        if sh["color_rules"]: manual.append(f"{sh['color_rules']} colour rules")
        res["manual_machinery"] = manual
        out.append(res)
    known = [s for s in out if s["form"]]
    gaps = sorted({c for s in out if s["form"] for c in s["unmapped"]})
    return dict(file=name, sheets=out, summary=dict(sheets=len(out), recognized=len(known), artifacts=sorted({s["artifact"] for s in known}),
                rows=sum(s["rows"] for s in out), formulas=sum(s["formulas"] for s in out), unmapped_columns=gaps))
