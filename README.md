# Launch — agentic systems engineering for hardware

**Launch** (package `launch-se`, CLI `launch`, formerly `sethread`) is to a hardware product what a coding agent is to a codebase. You open a terminal in the project
directory and talk to it; it reads and writes the engineering files (CAD scripts, KiCad projects, Modelica/FMUs,
firmware, test results, datasheets), runs the toolchain on your machine, and keeps **one system model** — the digital
thread — under everything it produces. Design documentation, SysML v2, FMEA, verification matrix, certification plan
and the reliability plan are *generated* from that model, never hand-written.

The recent "brief → working prototype" demos (OpenAI's CAD/EDA work with Codex; Anthropic's three Diode-built boards
with Fable 5.2) stop at the files. Their own limitations lists are the same: no electrical validation, no thermal or
antenna sign-off, no certification, no durability, no instrument loop. That gap — requirements, architecture, FMEA,
V&V, certification, traced to every file — is what sethread adds.

## Web app

**Phase 1 of the SaaS architecture is in:** with `DATABASE_URL` set, the model, patches, provenance and baselines live
in Postgres (`dbstore.py`; SQLite for dev and tests), event-sourced: `patches` is the append-only log, `elements` the
materialized current model, `projects.rev` the revision. `launch import <dir…> --database URL` migrates YAML projects
as an import patch; every surface (web, agents, forms, OSLC, MCP) runs unchanged. New endpoints: `/history`,
`/baselines` (name a revision), `/diff/{a}/{b}`; `load(rev)` folds the log for any past revision.
`docker compose up` starts Postgres and Launch together.

`launch serve --data /srv/sethread` runs the multi-project, multi-user service (or `docker compose up`). Users sign in
with a work email (plus an invite code when `SETHREAD_INVITE` is set), land on the project list, and open a project at
`/p/<id>`. Every view has a URL (`/p/ebike#/element/requirements/R-012`, `#/dfmea`, `#/graph/P-CELL`), so a link in a
review comment or a Jira ticket lands on the exact artifact. Patch approvals are recorded under the approving user.
Each project is a directory (`model.yaml`, `docs/`, `out/`, `.sethread/`) under the data root, so it can live in git.
One container = one uvicorn worker (agent sessions are in-process); scale by project, not by worker.

## Standard forms, in the app

Also: **N²** (physical and logical), **ICD index**, **Pugh / weighted trade matrices**, **fault trees** (tabular, top events from safety decisions, IEC 61025), **DRBFM** per architecture decision (built on the impact graph), and **dependency matrices** for any pair of collections.


Engineers judge a tool by whether its tables look like the forms they already sign. The app renders them live from the
model — no Excel export, no second copy:

| View | Format |
|---|---|
| **DFMEA** | AIAG & VDA FMEA Handbook (2019) form: structure analysis (next higher level / focus element / next lower level, merged across the rows of one element, from the part tree), function analysis, failure analysis (FE / FM / FC), risk analysis (S, O, D, **Action Priority**, special characteristic), optimization columns, rating-table anchors on demand |
| **DVP&R** | Design Verification Plan & Report (AIAG APQP): plan and report columns, one row per test, linked requirements and failure modes |
| **VCRM / RTM** | Verification Cross-Reference Matrix (ISO/IEC/IEEE 29148): requirement × verifying test, with realizing functions and allocated parts |
| **Requirements spec** | 29148 attributes: statement, measurable attribute, rationale/source, method, verified-by, disciplines |
| **Hazard register** | Safety-decision functions and S ≥ 9 failure modes with mitigations and verification |

The grid has sticky grouped headers, click-to-sort, a filter box per column, AP quick filters, empty-column hiding and
every id linked to its element page. Cells in the DFMEA and requirements spec are editable in place: **Save** applies
the change as a logged patch under your name; **Stage for review** hands it to a colleague. The agent pane collapses to
give a wide table the full screen. A CSV copy is one click when someone insists on a spreadsheet.

## The app

`sethread/web/dist` is the built frontend (React + TypeScript, Vite; source in `web/app`). It is served at `/app/` by the
same backend, so `pip install -e .` is enough to run it; rebuild with `cd web/app && npm install && npm run build`.
Design: an icon rail, a project tree by OOSEM stage, tabs for open artifacts, a ⌘K command palette that finds any element,
artifact or agent action, an artifact library with type/stage/freshness filters, element pages with Overview / Trace /
Failure modes / Impact / History, the standard forms in a sticky-header grid with inline editing, and the agent as a
drawer that pushes the content rather than covering it, with a review inbox for patches. Light and dark themes.
The single-file UI remains at `/legacy`. A read-only review build (`VITE_REVIEW=1 npm run build`) runs the same app over
a frozen `data.json` for sharing without a backend.

## Two front ends, one engine

* **`launch ui <dir>`** (one local project) / **`launch serve --data <root>`** (hosted, many projects and users) — the app most people use. A browser window with three panes: the digital thread on the left
  (OOSEM stages → collections → elements), the artifact in the middle, and the agent chat on the right. Every id anywhere
  is a link; every element page shows its fields, upstream, downstream, failure modes, provenance and an **impact
  analysis** ("if this changes: these requirements, functions, parts, failure modes; these tests must be re-run"). The
  graph view focuses on any element's neighbourhood. Patches arrive as cards in the chat with per-element diffs and the
  coverage delta if approved; Approve / Reject / "Ask for changes" are one click. Shell and file writes stop for a
  permission card; read-only tools do not. Works offline (no CDN), so it can run inside an ITAR network.
* **`launch <dir>`** — the same agent in a terminal, for engineers who prefer it.

## Versus CATIA Magic (Cameo), Flow Engineering and Dalus

CATIA Magic / Cameo Systems Modeler is the incumbent MBSE tool: full SysML, diagram editors, dependency matrices,
relation maps, simulation toolkit, Teamwork Cloud, DOORS sync, report wizard. It is a *drawing and recording* tool —
the engineer builds the model element by element, draws every diagram, writes every requirement, and the FMEA, DVP&R
and ICDs still live in Excel and Word beside it. Flow (flowengineering.com) is the graph-shaped requirements system of
record; Dalus (dalus.io) is Cameo-class SysML v2 with a copilot. Launch's position on each axis:

| | CATIA Magic / Cameo · Dalus · Flow | Launch |
|---|---|---|
| Who builds the model | engineers, element by element, diagram by diagram | the agent, stage by stage (OOSEM), from the PRD, datasheets and standards; engineers review patches |
| Diagrams | hand-drawn, drift from the model | generated from the model, every build, 13 views + SysML v2 text |
| Dependency matrices, relation maps | Cameo's signature features | built in: any kind × any kind matrix, N² (physical and logical), impact panel on every element, graph focused on any element |
| FMEA, DVP&R, ICD, FTA, DRBFM, Pugh, hazard register | Excel beside the model | live forms rendered from the same graph, AIAG-VDA / APQP / 29148 / IEC 61025 layouts, editable in place, every id a link |
| FMEA completeness | whatever the team wrote | functions × guide words + interfaces × guide words + transitions × guide words — every candidate assessed or screened with a reason |
| Impact analysis, budgets | plugins, scripts | graph queries, free, on every element and as agent tools |
| Engineering tools | import/export connectors | the agent runs CadQuery/FreeCAD, KiCad, OpenModelica/FMPy, ngspice, firmware builds on your machine and imports results |
| Collaboration | Teamwork Cloud server, thick client, per-seat licences ($5–15k/seat) | web app, email sign-in, deep links to any artifact, staged patches with provenance, Docker, your model API key |
| Learning curve | weeks of SysML training | type what you want; the model stays correct because patches are validated against the schema and the graph |

What Cameo still does that Launch does not: free-form diagram editing, SysML v1 import, executable state machines /
Cameo Simulation Toolkit, formal SysML v2 API interchange, enterprise SSO. Diagram editing is deliberately absent
(diagrams are generated); the others are on the roadmap below.

## What makes it the best agentic MBSE platform, measurably

1. **A scorecard the agent cannot argue with.** `quality.py` scores every model deterministically: trace coverage,
   requirement quality (INCOSE Guide to Writing Requirements rules R1–R12: vague terms, escape clauses, compound
   statements, negatives, pronouns, no measurable quantity, no unit, passive voice, TBD), FMEA completeness, High-AP
   test coverage, architecture and verification completeness, provenance. The agent calls `check_requirement` before
   proposing any requirement (≥ 85 or rewrite) and `scorecard` to choose what to work on. `launch eval --min 80` is a
   CI gate, so a model cannot regress. The Scorecard page shows the same numbers and the worst requirements with the
   rule that fired.
2. **Engineering knowledge that compounds.** `library/` ships regulations by product trigger (radio, Li-ion, skin
   contact, mains, e-bike, vehicle, children, …) with the standards and a requirement hint; failure mechanisms by
   discipline with typical causes and controls; standard test methods with default severities. Companies add their
   own under `<project>/library/*.yaml`, merged over the built-ins. Agents use the library as prompts and must still
   tie every item to a real element.
3. **A watcher that works between sessions.** Every approved patch — from the agent, the table, a colleague or an
   OSLC client — triggers a triage: scorecard delta and the top new gaps, posted as a card with a one-click "ask the
   agent to close them". The model is never left silently inconsistent.
4. **Open by standard: OSLC.** Built to talk to IBM DOORS Next and Jama Connect specifically:
   - *DOORS Next / ELM as consumer:* Jazz-style `/oslc/rootservices` (RDF/XML, `jfs:oauth*` and `rm:rmServiceProviders`),
     OAuth 1.0a provider (consumer registration in the Integrations page, request/authorize/access tokens, HMAC-SHA1
     signature check honouring reverse-proxy headers), OSLC 2.0 headers accepted. Flow: ELM *Add Friend* → root services
     URI → paste consumer key/secret → project association → the user clicks Allow once on Launch's authorize page.
   - *Launch as consumer of DOORS Next:* `OSLC_AUTH=jazz` form login (`j_security_check`), `Configuration-Context` for
     global/local configurations, `oslc:nextPage` paging, `jazz_rm:primaryText` → requirement text.
   - *Jama Connect, Codebeamer, Polarion:* HTTP Basic with Launch API tokens, or `OSLC_AUTH=oauth2-client` for Jama's
     REST OAuth; selection and preview dialogs for link pickers.
   - Generic OSLC 3.0: Launch is an OSLC provider for RM, QM, AM and CM (patches are ChangeRequests) and a
   consumer: `/oslc/rootservices`, `/oslc/catalog`, service providers per project with query capabilities, creation
   factories, selection dialogs, resource shapes and compact previews; JSON-LD, Turtle and RDF/XML; `oslc.where`,
   `oslc.searchTerms`, paging; HTTP Basic with per-user API tokens. DOORS Next, Jama, Polarion, Codebeamer or
   Windchill can link to, preview and create Launch elements; Launch pulls their requirements into staged patches
   with origin URIs kept for round trips. Writes through OSLC go through the same validated-patch path and land in
   provenance under the authenticated user.

## How it works

```
┌──────────── engineer in a terminal ────────────┐
│ › design the charger board for the 2S pack     │
│   ⚙ model.model_summary  ⚙ model.list_gaps     │
│   ⚙ model.read_document datasheets/BQ25887.pdf │
│   ⚙ Write elec/charger/charger.kicad_sch       │
│   ⚙ Bash kicad-cli sch export netlist …        │   (asks before shell / writes)
│   ⚙ model.tool_pull kicad elec/charger.net     │
│   ⚙ model.propose_patch  (+ R-041, F18, P-CHG, │
│       IF-12, C-09, 6 FMEA assessments, T-27)   │
│ 2 patches staged — review now?  [diff] y/n/all │
└────────────────────────────────────────────────┘
          │ approve                                   model.yaml  (+ .sethread/provenance.jsonl)
          ▼
   launch build  →  out/sysml/*.sysml · out/views/*.png · out/docs/design_documentation.md (+ .docx)
```

* **Model** — `model.yaml`, 22 collections in OOSEM order: stakeholders, needs, MoEs → actors, use cases, scenarios,
  regulations, requirements → functions, logical components, logical interfaces → parts (with discipline), nodes,
  interfaces, states, transitions, architecture decisions, trades → constraints → tests, gates → FMEA assessments.
  `schema.py` validates fields and references; `derive.py` computes FMEA candidates (functions × guide words,
  interfaces × guide words, transitions × guide words), the verification matrix, certification plan, discipline
  matrix, trace graph and a coverage report with 18 checks.
* **Patches, not edits** — agents and tool imports can only *stage* a patch (ops + rationale + sources). You see a
  diff and approve or reject; approved patches are applied and logged with provenance per element.
* **Agent** — one interactive harness agent (`sethread`), plus eight narrow OOSEM role agents (`/stage <role>`,
  `launch agent <dir> <role|all>`): needs, requirements, logical, physical, analysis, risk, verification, reviewer.
  Built on the Claude Agent SDK; the model tools are an in-process MCP server, so the same tools can be served to
  Claude Code, Cursor or any MCP client with `launch serve-mcp <dir>`.
* **Tool adapters** — `adapters.py`: KiCad netlist ⇄ constraints, CAD BOM CSV ⇄ requirement sheet, STEP, FMU run
  (FMPy) with constraint checks, Modelica parameter record push, ALM CSV/JSON (Jama/Codebeamer shaped), test results
  (TestRUNS-style CSV/JSON), generic MCP adapter, vendor stubs (Onshape, Jama). `toolchain.py` detects what is
  installed (kicad-cli, FreeCAD, CadQuery, omc, FMPy, ngspice, gmsh/CalculiX, PlatformIO, …) and tells the agent.
* **Outputs** — SysML v2 textual packages (needs, use cases, requirements, logical, structure, behavior, states,
  analysis, risk), 13 model-rendered views, OOSEM-ordered design documentation with provenance columns, Word export.

## Install and run

```bash
pip install -e .              # python ≥3.10; needs the `claude` CLI on PATH (Claude Agent SDK)
pip install fmpy cadquery     # optional: simulation / parametric CAD

launch init my-product --name "E-Bike Drive Unit"   # model.yaml + docs/
cp PRD.md datasheets/*.pdf my-product/docs/
launch ui my-product         # web app (opens the browser)
launch my-product            # or: the terminal harness
```

Inside the harness:

```
› read the PRD and set up stakeholders, needs and MoEs
› derive the regulatory context (EU + US, 2.4 GHz radio, Li-ion pack) and write the requirements
› define the logical and physical architecture; the pack is 10S4P 21700, controller is a 3-phase FOC inverter
› /gaps                          # what is still untraced
› /fmea 20                       # unassessed failure-mode candidates
› assess all FMEA candidates for the inverter and the pack interface
› /sync pull kicad elec/controller.net --parent P-CTRL
› write a CadQuery script for the die-cast housing meeting R-012 and IPX6, export STEP, and import the part
› /build --docx                  # SysML + views + design documentation + Word
```

Non-interactive:

```bash
launch check <dir>                      # validation + coverage (exit 1 if gaps)
launch agent <dir> needs|requirements|logical|physical|analysis|risk|verification|reviewer|all [--auto-approve]
launch patches <dir>  ·  launch show <dir> <id>  ·  launch approve|reject <dir> <id…>
launch sync pull|push <dir> <adapter> <path>
launch build <dir> [--docx]
launch serve-mcp <dir>                  # expose model tools over stdio MCP
```

## Worked example

`examples/sabi/` is a complete thread for a non-invasive EEG BCI beanie: 7 stakeholders, 12 needs, 13 regulations,
39 requirements, 27 functions, 12 logical components, 32 parts across textile/electrical/chemical/firmware/software,
9 interfaces, 16 transitions, 8 constraints, 50 tests, 246 FMEA candidates (98 assessed, 148 screened with reason),
trace clean. `launch build examples/sabi --docx` regenerates the 47-page design documentation.

`/tmp/ebike` in this session: `launch init` + a six-line PRD → the needs agent staged 5 stakeholders, 14 needs
and 14 MoEs with numeric targets in two patches (reviewed and approved from the CLI) → `launch build`.

## Layout

```
sethread/
  schema.py store.py derive.py sysml.py views.py docs.py docx_export.py adapters.py cli.py
  agents/   tools.py (MCP tools) roles.py (OOSEM role prompts) orchestrator.py (stage runner / pipeline)
  harness/  repl.py (interactive terminal) prompt.py (harness system prompt) toolchain.py (tool detection)
  web/      server.py (FastAPI: workspace, login, model/graph/impact/budgets/matrix/forms/patches/chat-SSE) static/index.html (the app, no build step)
  quality.py  requirement quality rules (INCOSE GtWR) and the model scorecard · library/ regulations, failure mechanisms, test methods (YAML)
  oslc.py     OSLC 3.0 provider (RM/QM/AM/CM) · adapters.OslcRmAdapter consumer
  forms.py    AIAG-VDA DFMEA · DVP&R · VCRM · 29148 requirements spec · hazard register · N² (physical/logical) · ICD index · Pugh matrices · FTA (tabular) · DRBFM · dependency matrices
Dockerfile docker-compose.yml
examples/sabi/  model.yaml out/{sysml,views,docs}
```

## Roadmap

* Live instrument loop: TestRUNS / DAQ adapters so a test result closes a requirement automatically.
* Vendor APIs behind the stubs (Onshape, Fusion, Altium 365, Jama, Windchill) and a KiCad/FreeCAD MCP pair.
* Model diffs as pull requests (git-backed store), multi-user review, and a web view of the thread.
* SysML v2 API/KerML export for Cameo/Syside interchange.
