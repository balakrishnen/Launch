"""Named skills: packaged, repeatable jobs over the model — the way Anthropic packages its manufacturing skills, but each one
is a bounded procedure a role agent runs against this project's graph with propose_patch as the only write path.

A skill = when to use it (trigger), what it reads, the procedure, what it leaves behind (patches of which kinds, which form),
and the role that runs it. `suggest()` reads the model and says which skills apply right now and why, so the home page and the
MCP client can offer them without a person remembering the catalog. Skills are also exposed as MCP prompts."""
from __future__ import annotations
from . import schema as SCH

SKILLS: list[dict] = [
    # ---- engineering ----
    dict(id="options-to-trade-decision", name="Options → trade decision", department="engineering", role="analysis",
         trigger="An open architecture choice (a trade study with options but no decision, or an arch decision with alternatives and no trade).",
         picks="trades", reads=["trades", "requirements", "constraints", "parts", "budgets"],
         procedure="""For the trade study: confirm criteria trace to requirements/MoEs and that every knock-out limit is a real constraint
(cite the id). Score any unscored option from the model and documents (never invent numbers — mark unknowns). Run trade_study for
normalized totals and sensitivity; if the leader is not robust, say which weight flips it and what evidence would settle it. Then
trade_decide with the leading option, rationale, and the requirements/constraints it affects; propose follow-on work items for the
losing options' retirement and for any criterion that needs a test to verify. Report: leader, margin, robustness, open evidence.""",
         outputs=["trades (decision)", "work_items", "arch_decisions"], form="trades"),
    dict(id="dfmea-from-architecture", name="DFMEA from architecture", department="engineering", role="risk",
         trigger="Parts or interfaces without failure-mode assessments; a new or changed interface.",
         picks="parts", reads=["parts", "interfaces", "functions", "requirements", "library.failure_modes"],
         procedure="""For each selected part (default: parts with no fm_assessments), take its functions and interfaces, pull the discipline's
failure modes from the library, and write assessments: failure mode, effect on the function, cause, S/O/D with the rationale, current
controls, and the requirement or test that detects it. Anything with AP high gets a work item with an owner from the part's team.
Never score without naming the effect at system level; link every assessment to part + function + ≥1 requirement.""",
         outputs=["fm_assessments", "work_items"], form="dfmea"),
    dict(id="eol-test-plan", name="EOL test plan from requirements", department="engineering", role="verification",
         trigger="Requirements verified by test with no test, or a build (EVT/DVT/PVT) coming up without station tests.",
         picks="process_steps", reads=["requirements", "tests", "process_steps", "cdas", "work_orders"],
         procedure="""List requirements with verification=test and no test, and critical design attributes with no station measurement. For each,
write a test with method (library.test_methods), the gate it must pass before, pass/fail with units, sample size, and — for anything
measurable in production — the process step (station) that measures it and the metric key so station results feed the CDA. Group into
the DVP&R by gate; flag tests that need fixtures (tooling) and propose the tooling rows with need-by dates before the build.""",
         outputs=["tests", "tooling", "cdas (station source)"], form="dvpr"),
    dict(id="certification-plan", name="Certification & compliance plan", department="engineering", role="requirements",
         trigger="Target markets set but regulations missing, or regulations with no imposed requirement / test.",
         picks="markets", reads=["product (properties)", "markets", "regulations", "requirements", "tests", "library.regulations"],
         procedure="""From the product's properties (mains, battery, radio, skin contact, food contact, pressure, laser) and the target markets, pull
the applicable regulations and standards from the library and add the missing ones with trigger and market. For each regulation make sure ≥1
requirement is imposed and ≥1 test verifies it, with the certifying body/lab and the gate by which the report is needed. Produce the
submission sequence (what depends on what — e.g. EMC after safety pre-scan, DoC after both) as deliverables on the PDP with dates.""",
         outputs=["regulations", "requirements", "tests", "deliverables"], form="compliance"),
    dict(id="change-order-impact", name="Change order impact", department="engineering", role="physical",
         trigger="An ECO is drafted, or a part/interface change is being discussed.",
         picks="parts", reads=["parts", "interfaces", "requirements", "tests", "fm_assessments", "tooling", "quotes", "work_orders"],
         procedure="""Run change_order_impact on the affected parts: functions, requirements, interfaces, tests to rerun, failure modes to re-assess,
tooling and quotes affected, open work orders that would build the old revision. Write the ECO (change_orders) with the impact list,
the tests to rerun as work items for verification, re-quote requests for procurement, and tooling changes for industrialization.
State the effectivity (which build/serial) and whether units already built need rework or containment (field_quality).""",
         outputs=["change_orders", "work_items"], form="eco"),
    # ---- quality ----
    dict(id="inspection-to-capa", name="Inspection → CAPA", department="quality", role="launch_quality",
         trigger="An inspection lot with defects above the part's ppm target, a station failure cluster, or a field event.",
         picks="inspections", reads=["inspections", "units", "work_orders", "parts", "fm_assessments", "capa"],
         procedure="""Take the failing lots/stations: group defects by code and part, compare with the DFMEA (is this a predicted failure mode? was
the control supposed to catch it?). Open a CAPA with containment (what to hold, sort, or rework — by lot/serial from genealogy), the
root-cause method (5-why / Ishikawa, with the data to collect), corrective action owner and due date, and verification (which inspection
or test shows it worked, with the ppm target). Link the CAPA to part, supplier, inspection ids and the DFMEA assessment; update the
assessment's occurrence if the field data contradicts it.""",
         outputs=["capa", "work_items", "fm_assessments (update)"], form="capa"),
    dict(id="field-event-8d", name="Field event 8D", department="quality", role="field_quality",
         trigger="Field events (returns, complaints, service claims) that repeat on a part or symptom.",
         picks="field_events", reads=["field_events", "units", "parts", "fm_assessments", "requirements", "tests"],
         procedure="""Cluster the field events by symptom and part; pull the unit genealogy for serials (build, lot, components). Run an 8D: team,
problem statement with the numbers (rate per 1000 units, time to failure), containment for fielded units and finished goods, root cause
against the DFMEA and the test that should have caught it, permanent corrective action (design change → ECO, process → CAPA), prevention
(requirement or test added), and closure evidence. Propose each as linked elements; report the warranty exposure to finance (claims view).""",
         outputs=["capa", "change_orders", "requirements", "tests", "work_items"], form="field_loop"),
    dict(id="supplier-ppm-review", name="Supplier PPM review", department="quality", role="supplier_quality",
         trigger="Monthly, or when a supplier's incoming ppm breaches its target.",
         picks="suppliers", reads=["inspections", "suppliers", "parts", "quotes", "capa"],
         procedure="""Compute ppm per supplier and part from incoming inspections (supplier_ppm); rank by ppm × spend. For breaches: open a supplier
CAPA (SCAR) with the lot data, request 8D from the supplier, decide inspection level (tightened / normal / skip-lot) per part and record it
as the part's inspection plan. For parts with one source and a breach, raise a second-source work item to procurement. Report the top
three suppliers to act on with the evidence.""",
         outputs=["capa", "work_items", "parts (inspection plan)"], form="ppm"),
    dict(id="design-review-readiness", name="Design review readiness", department="quality", role="design_quality",
         trigger="A design review (PDR/CDR) is scheduled within 30 days.",
         picks="reviews", reads=["requirements", "tests", "fm_assessments", "trades", "cdas", "findings", "deliverables"],
         procedure="""Check the review's entry criteria against the model: requirements quality (check_requirement scores), trace coverage
(coverage), DFMEA complete for the parts in scope, trades decided, CDAs with demonstrated values, open findings from the last review.
Produce the review package as findings pre-filed (what the reviewers will find anyway) with owners, and the readiness verdict:
ready / ready-with-actions / not ready, with the three items that would change it.""",
         outputs=["findings", "work_items", "reviews"], form="findings"),
    # ---- supply chain ----
    dict(id="rfq-to-award", name="RFQ → award", department="supply_chain", role="procurement",
         trigger="Parts with make/buy=buy and no quote, long-lead parts not yet ordered, or quotes expiring before the build.",
         picks="parts", reads=["parts", "suppliers", "quotes", "process_steps (build qty)", "pdp (gates)", "tooling"],
         procedure="""Build the RFQ package per part (rfq_package: drawing rev, spec requirements, quantities per build and annual, quality
requirements, tooling ownership, delivery to need-by date). Compare received quotes on landed cost at the build quantities, MOQ vs
build quantity, lead time vs need-by, tooling NRE, and the supplier's ppm history; recommend an award with the rationale, and a
second source for anything critical or single-sourced. On award: po_from_quote for the long-lead parts whose order-by date is within
two weeks, and a work item for the rest with the order-by date.""",
         outputs=["quotes (awarded)", "purchase_orders", "work_items"], form="procurement"),
    dict(id="tooling-kickoff", name="Tooling kickoff & T1 plan", department="supply_chain", role="industrialization",
         trigger="Molded/cast/stamped parts released or near release with no tooling row, or tooling without a T1 date before the build.",
         picks="parts", reads=["parts", "tooling", "quotes", "pdp (gates)", "cdas"],
         procedure="""For each tooled part: confirm the tooling row (supplier, cavities, lead time, cost, owner), back-schedule kickoff from the
build need-by date (T1 → T2 → PPAP), and flag parts whose kickoff date has passed without a released drawing. Define the PPAP scope
(dimensional on CDAs, material certs, capability on the critical dimensions) and the first-article inspection as inspections to record.
Report tooling spend committed vs budget to finance.""",
         outputs=["tooling", "work_items", "inspections (planned)"], form="tooling"),
    # ---- program ----
    dict(id="gate-readiness-review", name="Gate readiness review", department="program", role="program",
         trigger="A gate within 30 days, or any red leading indicator on the next gate.",
         picks="gates", reads=["pdp (deliverables, checks)", "indicators", "maturity", "trl", "cdas", "risks", "work_items"],
         procedure="""For the next gate: list open deliverables with owners and the checks that fail (PDP), the TRL gaps against the gate's minimum,
CDAs without demonstrated values, red/amber indicators and the gate-slip risk with burn per week. Decide per open item: close (evidence
exists — propose the patch), waive (write the waiver as a finding with the condition), or slip (say by how long). Produce the one-page
readiness summary: recommendation (go / conditional go / hold), top three risks, decisions needed from the steering committee.""",
         outputs=["findings", "work_items", "deliverables (status)", "risks"], form="pdp"),
    dict(id="steering-summary", name="Steering committee summary", department="program", role="program",
         trigger="Weekly or before a steering meeting.",
         picks=None, reads=["analytics", "indicators", "risks", "work_items", "cost", "staffing", "claims"],
         procedure="""One page, numbers from the model: stage and days to gate; maturity score with the two sub-scores that moved; cost vs budget
(BOM, tooling, NRE) and the open quotes that could move it; schedule risk from indicators; top risks with trend; decisions needed with
options and recommendation; what changed since last week (patches applied). Write it as a document with every number linked to its
id. Do not propose model changes except risks whose status changed.""",
         outputs=["documents", "risks (update)"], form="analytics"),
    dict(id="maturity-review", name="Maturity & TRL review", department="program", role="program",
         trigger="Monthly, or when a part is marked new technology.",
         picks=None, reads=["trl", "cdas", "tests", "test_runs", "simulations", "pdp (gates)"],
         procedure="""For each new-technology part: compare declared vs demonstrated TRL (maturity), name the evidence that would raise it one
level (the test, the simulation, the build), and the gate by which it must be there. For CDAs: value vs target vs trend, and which are
not yet measured. Propose the work items and test placeholders; flag overstated TRLs as findings. Report the maturity profile against
the gate expectation.""",
         outputs=["work_items", "tests", "findings", "parts (trl)"], form="trl"),
    # ---- go-to-market / corporate ----
    dict(id="claims-substantiation", name="Claims substantiation", department="go_to_market", role="legal",
         trigger="Marketing claims without evidence, or a requirement change that affects a claimed figure.",
         picks="claims", reads=["claims", "requirements", "tests", "test_runs", "markets", "regulations"],
         procedure="""For each claim: name the requirement(s) it rests on, the test(s) and runs that substantiate it, the markets where it is
made and that market's advertising rules (library). Mark status: substantiated / pending test / unsupported / must-reword, and propose
the reworded claim where the evidence supports a weaker statement. Raise a work item to verification for each pending test with the
launch date as need-by. Report which claims block the launch materials.""",
         outputs=["claims (status)", "work_items"], form="claims"),
    dict(id="service-plan", name="Service & FRU plan", department="service", role="service",
         trigger="Parts with high predicted failure (DFMEA occurrence) and no FRU / repair procedure, or warranty cost above target.",
         picks="parts", reads=["parts", "fm_assessments", "field_events", "claims (warranty)", "process_steps"],
         procedure="""Rank parts by expected field failure (occurrence × fielded units) and repair cost; decide FRU vs whole-unit replacement
per part with the rationale; write the repair procedure outline (tools, steps, test to confirm) and the spares forecast at launch
quantities. Flag parts whose design makes repair impossible (fasteners, adhesives) as DfS findings to engineering.""",
         outputs=["parts (fru)", "findings", "work_items"], form="fru"),
    dict(id="set-us-up", name="Set us up (organization)", department="corporate", role="people",
         trigger="A new organization or project: departments exist but no sub-units, teams or owners.",
         picks=None, reads=["org (structure, teams, people)", "parts", "deliverables"],
         procedure="""From the people and their titles, the product's disciplines (parts), and the PDP deliverables: propose the sub-units under
each fixed department (e.g. Engineering → mechanical, electrical, firmware, industrial design, compliance), the teams with leads and
focus, and an owner for every unowned deliverable and part. Keep teams small; one owner per element. Put it to the organization as
patches to org and the project, not as text.""",
         outputs=["org (structure, teams)", "deliverables (owner)", "parts (team)"], form=None),
]
BY_ID = {s["id"]: s for s in SKILLS}

def catalog() -> list[dict]:
    return [{k: v for k, v in s.items() if k != "procedure"} | {"procedure": s["procedure"].strip()} for s in SKILLS]

def prompt_for(skill: dict, ids: list[str] | None = None, note: str = "") -> str:
    """The chat message that runs the skill: the procedure, scoped to the chosen elements."""
    scope = f"\nScope: {', '.join(ids)}." if ids else ""
    return f"Run the skill “{skill['name']}”.{scope}\nReads: {', '.join(skill['reads'])}.\nProcedure: {skill['procedure'].strip()}\nLeave behind: {', '.join(skill['outputs'])}.{(' ' + note) if note else ''}"

# ---------------------------------------------------------------------------------------------------------------------
def suggest(m: dict, extra: dict | None = None) -> list[dict]:
    """Which skills apply to this project right now, with the reason and the ids to scope them to. `extra` may carry
    indicators / gates computed elsewhere (to avoid recomputing)."""
    out = []
    def add(sid, why, ids=None):
        s = BY_ID[sid]; out.append({"id": sid, "name": s["name"], "role": s["role"], "department": s["department"], "why": why, "ids": (ids or [])[:12], "n": len(ids or []), "always": sid == "steering-summary"})
    g = lambda k: m.get(k, {}) or {}
    # trades without a decision
    undecided = [t for t, v in g("trades").items() if v.get("options") and not v.get("decision")]
    if undecided: add("options-to-trade-decision", f"{len(undecided)} trade study without a decision", undecided)
    # parts with no DFMEA
    from . import derive as D
    covered = set()
    for a in g("fm_assessments").values():
        e = a.get("element"); kind = "function" if e in g("functions") else "interface" if e in g("interfaces") else "transition" if e in g("transitions") else "process" if e in g("process_steps") else None
        if kind:
            try: covered |= set(D.element_parts(m, kind, e))
            except Exception: pass
    unassessed = [p for p, v in g("parts").items() if p not in covered and v.get("parent") and v.get("discipline") not in ("system",)]
    if unassessed and g("parts"): add("dfmea-from-architecture", f"{len(unassessed)} parts with no failure-mode assessment", unassessed)
    # requirements verified by test with no test
    untested = [r for r, v in g("requirements").items() if (v.get("verify") or "test") == "test" and not [t for t in (v.get("tests") or []) if t in g("tests")]]
    if untested: add("eol-test-plan", f"{len(untested)} requirements with no verifying test", untested)
    # regulations without requirement / markets without regulations
    imposed = {r for v in g("requirements").values() for r in (v.get("regs") or [])}
    unimposed = [r for r in g("regulations") if r not in imposed]
    if (g("markets") and not g("regulations")) or unimposed: add("certification-plan", f"{len(unimposed)} regulations impose no requirement" if unimposed else "target markets set but no regulations", unimposed)
    # draft ECOs
    drafts = [c for c, v in g("change_orders").items() if v.get("status") in (None, "draft", "proposed")]
    if drafts: add("change-order-impact", f"{len(drafts)} change order in draft", drafts)
    # inspections with defects and no CAPA
    capa_src = {v.get("source_id") for v in g("capa").values()}
    bad = [i for i, v in g("inspections").items() if (v.get("defects") or 0) > 0 and i not in capa_src and (v.get("disposition") or "") not in ("accept", "use-as-is")]
    if bad: add("inspection-to-capa", f"{len(bad)} inspection lots with defects and no CAPA", bad)
    # field events open
    fe = [f for f, v in g("field_events").items() if v.get("status") not in ("closed", "resolved")]
    if fe: add("field-event-8d", f"{len(fe)} open field events", fe)
    # supplier ppm
    by_sup: dict[str, list] = {}
    for v in g("inspections").values():
        if v.get("stage") == "incoming" and v.get("supplier"): by_sup.setdefault(v["supplier"], []).append(v)
    breach = [s for s, rows in by_sup.items() if sum(r.get("qty") or 0 for r in rows) and sum(r.get("defects") or 0 for r in rows) / max(1, sum(r.get("qty") or 0 for r in rows)) * 1e6 > 10000]
    if breach: add("supplier-ppm-review", f"{len(breach)} suppliers over ppm target", breach)
    # procurement: buy parts without quotes
    quoted = {q.get("part") for q in g("quotes").values()}
    unquoted = [p for p, v in g("parts").items() if v.get("make_buy") == "buy" and p not in quoted]
    if unquoted: add("rfq-to-award", f"{len(unquoted)} buy parts with no quote", unquoted)
    # tooling
    tooled = {t.get("part") for t in g("tooling").values()}
    needs_tool = [p for p, v in g("parts").items() if any(w in str((v.get("attrs") or {}).get("process", "") or (v.get("attrs") or {}).get("material", "")).lower() for w in ("mold", "cast", "stamp", "pp ", "abs", "pc/abs", "tritan")) and p not in tooled]
    if needs_tool: add("tooling-kickoff", f"{len(needs_tool)} tooled parts with no tooling plan", needs_tool)
    # claims
    unsub = [c for c, v in g("claims").items() if v.get("status") not in ("substantiated",)]
    if unsub: add("claims-substantiation", f"{len(unsub)} claims not yet substantiated", unsub)
    # gate within 30 days / reds
    ex = extra or {}
    nxt = ex.get("days_to_next"); reds = (ex.get("summary") or {}).get("red", 0)
    if (nxt is not None and nxt <= 30) or reds: add("gate-readiness-review", (f"{ex.get('next_gate')} in {nxt} days" if nxt is not None and nxt <= 30 else "") + (f"{'; ' if nxt is not None and nxt <= 30 else ''}{reds} red indicators" if reds else ""), [])
    # TRL
    newtech = [p for p, v in g("parts").items() if str((v.get("attrs") or {}).get("new_technology", "")).lower() in ("yes", "true", "1")]
    if newtech: add("maturity-review", f"{len(newtech)} new-technology parts", newtech)
    # org
    if not g("teams"): add("set-us-up", "no teams defined yet", [])
    # always-available, low priority
    add("steering-summary", "one page for the steering committee, from the model", [])
    return out
