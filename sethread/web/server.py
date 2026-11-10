"""sethread web app — chat with the agent, navigate every artifact through the model graph, review patches.

    sethread ui <dir>                  one project, local                → http://127.0.0.1:8765
    sethread serve --data /srv/sethread  multi-project, multi-user web service (also: Dockerfile)

A Workspace holds many projects (one directory each under the data root). Each project has one agent session
(ClaudeSDKClient, same tools as the terminal harness) shared by its users; agent events, permission requests and staged
patches stream to every open browser over SSE. Users sign in with an email (and an invite code if SETHREAD_INVITE is set);
patch approvals are recorded under the approving user. Run one worker per container (sessions live in process)."""
from __future__ import annotations
import asyncio, json, os, uuid, shutil, difflib, yaml, webbrowser, threading, time
from typing import Any
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Response, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from claude_agent_sdk import (ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, ResultMessage, UserMessage,
                              TextBlock, ToolUseBlock, ToolResultBlock, PermissionResultAllow, PermissionResultDeny)
from ..store import Store
from .. import derive, schema, sysml, views, docs, forms, quality, oslc, oslc_oauth
from ..store import Patch, Op
from ..agents.tools import make_server
from ..agents import roles as R
from ..harness.prompt import HARNESS
from ..harness import toolchain

STATIC = os.path.join(os.path.dirname(__file__), "static")
SAFE_TOOLS = {"Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch", "TodoWrite", "Task", "ToolSearch"}
BUILTIN = ["Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch", "TodoWrite"]

STAGE_OF = {  # which OOSEM stage each collection belongs to (drives the navigation)
    "stakeholders": "1 Needs", "needs": "1 Needs", "moes": "1 Needs",
    "actors": "2 Requirements", "use_cases": "2 Requirements", "scenarios": "2 Requirements", "regulations": "2 Requirements", "requirements": "2 Requirements",
    "functions": "3 Logical architecture", "logical_components": "3 Logical architecture", "logical_interfaces": "3 Logical architecture",
    "parts": "4 Physical architecture", "nodes": "4 Physical architecture", "interfaces": "4 Physical architecture", "states": "4 Physical architecture",
    "transitions": "4 Physical architecture", "arch_decisions": "4 Physical architecture", "trades": "5 Analysis", "constraints": "5 Analysis",
    "tests": "6 Verification", "gates": "6 Verification", "fm_assessments": "Risk (derived)",
}

def _kind_of(m, eid: str) -> str | None:
    for k in schema.KINDS:
        if eid in m[k]: return k
    return None

class Session:
    """One project: store + agent client + event bus."""
    def __init__(self, root: str, model: str | None = None, pid: str = "default", store=None):
        self.pid = pid; self.root = os.path.abspath(root); os.makedirs(self.root, exist_ok=True); self.store = store or Store(self.root); self.docs_dir = os.path.join(self.root, "docs"); os.makedirs(self.docs_dir, exist_ok=True)
        self.model = model; self.auto = False; self.yolo = False
        self.events: asyncio.Queue = asyncio.Queue(); self.pending: dict[str, asyncio.Future] = {}
        self.client: ClaudeSDKClient | None = None; self.busy = False; self.history: list[dict] = []; self.last_score: dict | None = None
        self.server, self.names = make_server(self.store, docs_dir=self.docs_dir, author="agent:ui")
        self.tc = toolchain.detect()

    def emit(self, type_: str, **data):
        ev = {"type": type_, "ts": time.time(), **data}; self.history.append(ev); self.events.put_nowait(ev)
        if type_ == "model_changed":
            try: self.last_score = triage(self, self.last_score)
            except Exception as e: self.history.append({"type": "error", "ts": time.time(), "text": f"triage: {e}"})

    async def can_use_tool(self, name, inp, ctx):
        if self.yolo or name in SAFE_TOOLS or name.startswith("mcp__sethread__"): return PermissionResultAllow()
        pid = uuid.uuid4().hex[:8]; fut = asyncio.get_event_loop().create_future(); self.pending[pid] = fut
        self.emit("permission", id=pid, tool=name, detail=inp.get("command") or inp.get("file_path") or json.dumps(inp)[:400])
        try: ans = await asyncio.wait_for(fut, 600)
        except asyncio.TimeoutError: ans = "deny"
        finally: self.pending.pop(pid, None)
        if ans == "always": self.yolo = True
        return PermissionResultAllow() if ans in ("allow", "always") else PermissionResultDeny(message="engineer declined")

    async def ensure_client(self):
        if self.client: return
        sp = HARNESS + "\n\n# Toolchain\n" + toolchain.summary(self.tc) + f"\n\n# Project root\n{self.root}\n\n# UI\nThe engineer is in a web app, not a terminal. When you mention an element, write its id (e.g. R-012) — the app turns ids into links. Keep answers short; the app shows your staged patches as cards."
        opts = ClaudeAgentOptions(system_prompt=sp, mcp_servers={"sethread": self.server}, tools=BUILTIN, allowed_tools=self.names + sorted(SAFE_TOOLS), cwd=self.root,
                                  permission_mode="default", can_use_tool=self.can_use_tool, max_turns=60, **({"model": self.model} if self.model else {}))
        self.client = ClaudeSDKClient(opts); await self.client.connect()

    async def turn(self, text: str, role: str | None = None, user: str = "engineer"):
        if self.busy: raise HTTPException(409, "agent is busy")
        self.busy = True; staged0 = {p.id for p in self.store.list_patches("staged")}
        self.emit("user", text=text, user=user)
        try:
            await self.ensure_client()
            prompt = text
            if role and role in R.ROLES:
                from ..agents.orchestrator import build_prompt
                prompt = build_prompt(self.store, role, text or None)
            await self.client.query(prompt)
            async for msg in self.client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, TextBlock) and b.text.strip(): self.emit("assistant", text=b.text)
                        elif isinstance(b, ToolUseBlock):
                            arg = b.input.get("command") or b.input.get("file_path") or b.input.get("kind") or b.input.get("name") or b.input.get("adapter") or b.input.get("rationale") or ""
                            self.emit("tool", name=b.name.replace("mcp__sethread__", "model."), arg=str(arg)[:160])
                elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
                    for b in msg.content:
                        if isinstance(b, ToolResultBlock) and b.is_error: self.emit("tool_error", text=str(b.content)[:300])
                elif isinstance(msg, ResultMessage):
                    self.emit("result", turns=msg.num_turns, seconds=round(msg.duration_ms / 1000), cost=msg.total_cost_usd)
            new = [p.id for p in self.store.list_patches("staged") if p.id not in staged0]
            for pid in new:
                if self.auto: self.store.approve(pid, approver="auto"); self.emit("patch_applied", id=pid)
                else: self.emit("patch_staged", id=pid, patch=patch_summary(self.store, pid))
            if new: self.emit("model_changed")
        except Exception as e:
            self.emit("error", text=f"{type(e).__name__}: {e}")
        finally:
            self.busy = False; self.emit("idle")

def triage(S: "Session", before: dict | None):
    """Watcher: after a model change, emit what changed in the scorecard and the top new gaps with one-click agent actions."""
    m = S.store.load(); sc = quality.scorecard(m, S.store); gaps = derive.gaps_as_tasks(m)[:8]
    delta = {k: [before["dimensions"][k], v] for k, v in sc["dimensions"].items() if before and before["dimensions"].get(k) != v} if before else {}
    S.emit("triage", overall=sc["overall"], grade=sc["grade"], delta=delta, gaps=gaps, worst=sc["worst_requirements"][:3])
    return sc

def patch_summary(store: Store, pid: str) -> dict:
    p = store.get_patch(pid); m = store.load()
    try: new, issues = store.check_patch(m, p); ok = True
    except Exception as e: new, issues, ok = m, [], False
    diffs = []
    for op in p.ops:
        old = m.get(op.kind, {}).get(op.id); nw = new.get(op.kind, {}).get(op.id)
        a = yaml.safe_dump(old, sort_keys=False, allow_unicode=True).splitlines() if old else []
        b = yaml.safe_dump(nw, sort_keys=False, allow_unicode=True).splitlines() if nw else []
        diffs.append({"op": op.op, "kind": op.kind, "id": op.id, "name": (nw or old or {}).get("name") or (nw or old or {}).get("text", "")[:60],
                      "diff": "\n".join(list(difflib.unified_diff(a, b, lineterm="", n=2))[2:])})
    before, after = derive.coverage_report(m), derive.coverage_report(new)
    delta = {k: [len(before[k]), len(after[k])] for k in before if k not in ("counts", "clean") and len(before[k]) != len(after[k])}
    return {"id": p.id, "status": p.status, "author": p.author, "rationale": p.rationale, "sources": p.sources, "created": p.created, "ops": diffs,
            "warnings": [f"{i.where}: {i.msg}" for i in issues if i.level == "warning"][:10], "errors": [f"{i.where}: {i.msg}" for i in issues if i.level == "error"][:10],
            "coverage_delta": delta, "valid": ok}

def element_page(store: Store, kind: str, eid: str) -> dict:
    m = store.load()
    if kind == "fmea":
        row = next((f for f in derive.fmea(m) if f["id"] == eid), None)
        if not row: raise HTTPException(404)
        return {"kind": "fmea", "id": eid, "data": row, "stage": "Risk (derived)", "up": [{"kind": row["kind"], "id": row["element"], "rel": "failure mode of", "name": row["element_name"]}],
                "down": [{"kind": "tests", "id": t, "rel": "covered by", "name": m["tests"].get(t, {}).get("name", "")} for t in row["tests"]], "provenance": store.provenance("fm_assessments", eid)}
    if kind not in m or eid not in m[kind]: raise HTTPException(404)
    el = m[kind][eid]; E = derive.trace(m); up, down = [], []
    def nm(x):
        k = _kind_of(m, x)
        if k: return k, m[k][x].get("name") or m[k][x].get("text", "")[:70] or m[k][x].get("title", "")
        if x.startswith("FM-"):
            r = next((f for f in derive.fmea(m) if f["id"] == x), None); return "fmea", (r["mode"] if r else x)
        return None, x
    FLIP = {"verifies": "verified by", "realizes": "realized by function", "covers": "covered by", "constrains": "constrained by"}  # edge source is the downstream element
    INV = {"verifies": "verifies", "realizes": "realizes", "covers": "covers", "constrains": "constrains"}
    for a, rel, b in E:
        if a == eid:
            k, n = nm(b)
            (up if rel in FLIP else down).append({"kind": k, "id": b, "rel": INV.get(rel, rel), "name": n})
        elif b == eid:
            k, n = nm(a)
            (down if rel in FLIP else up).append({"kind": k, "id": a, "rel": FLIP.get(rel, rel), "name": n})
    extra = {}
    if kind == "requirements": extra["disciplines"] = derive.discipline_matrix(m).get(eid, [])
    if kind in ("functions", "interfaces", "transitions"):
        extra["fmea"] = [f for f in derive.fmea(m) if f["element"] == eid]; extra["screened"] = [s for s in derive.screened(m) if s["element"] == eid]
        extra["unassessed"] = [u for u in derive.unassessed(m) if u["element"] == eid]
    if kind == "tests": extra["row"] = next((t for t in derive.verification_matrix(m) if t["id"] == eid), None)
    if kind == "regulations": extra["row"] = next((r for r in derive.certification_plan(m) if r["id"] == eid), None) if derive.certification_plan(m) and "id" in derive.certification_plan(m)[0] else None
    return {"kind": kind, "id": eid, "data": el, "stage": STAGE_OF.get(kind, ""), "up": up, "down": down, "provenance": store.provenance(kind, eid), **extra}

class Chat(BaseModel):
    text: str
    role: str | None = None
class HumanPatch(BaseModel):
    ops: list
    rationale: str = "edited in the app"
    apply: bool = True
class Sync(BaseModel):
    direction: str
    adapter: str
    path: str
    kind: str | None = None
    parent: str | None = None
class Baseline(BaseModel):
    name: str
class Perm(BaseModel):
    answer: str
class Settings(BaseModel):
    auto: bool | None = None
    yolo: bool | None = None

class Workspace:
    """Projects under a data root. Single-project mode wraps one directory as project 'default'.
    With DATABASE_URL set, the model, patches and provenance live in the database (dbstore.DbStore, tenant = org);
    the data root then holds only each project's files (docs/, out/, engineering files)."""
    def __init__(self, data_root: str | None, single: str | None, model: str | None, database_url: str | None = None, tenant: str = "default"):
        self.model = model; self.sessions: dict[str, Session] = {}; self.tenant = tenant
        self.single = os.path.abspath(single) if single else None
        self.data_root = os.path.abspath(data_root) if data_root else None
        if self.data_root: os.makedirs(self.data_root, exist_ok=True)
        self.db = None
        if database_url:
            from ..dbstore import DB; self.db = DB(database_url)
    def _store(self, pid: str, root: str):
        if self.db is None: return Store(root)
        from ..dbstore import DbStore; return DbStore(self.db, self.tenant, pid)
    def ids(self) -> list[str]:
        if self.single: return ["default"]
        if self.db is not None:
            with self.db.connect() as c: return [r[0] for r in self.db.exec(c, "SELECT id FROM projects WHERE tenant=? ORDER BY id", (self.tenant,))]
        return sorted(d for d in os.listdir(self.data_root) if os.path.isdir(os.path.join(self.data_root, d)) and not d.startswith("."))
    def path(self, pid: str) -> str:
        if self.single: return self.single
        if not pid.replace("-", "").replace("_", "").isalnum(): raise HTTPException(400, "bad project id")
        return os.path.join(self.data_root, pid)
    def get(self, pid: str) -> Session:
        if pid not in self.sessions:
            root = self.path(pid)
            if pid not in self.ids(): raise HTTPException(404, "no such project")
            self.sessions[pid] = Session(root, self.model, pid, store=self._store(pid, root))
        return self.sessions[pid]
    def create(self, pid: str, name: str, description: str = "", user: str = "") -> Session:
        if self.single: raise HTTPException(400, "single-project mode")
        root = self.path(pid)
        if pid in self.ids(): raise HTTPException(409, "project exists")
        os.makedirs(os.path.join(root, "docs"), exist_ok=True)
        if self.db is None:
            from ..agents.orchestrator import init_project; init_project(root, name, description)
        st = self._store(pid, root); m = st.load(); m["meta"].update(name=name, description=description, created_by=user, method="OOSEM"); st.save(m)
        return self.get(pid)
    def summary(self, pid: str) -> dict:
        st = self._store(pid, self.path(pid)); m = st.load(); rep = derive.coverage_report(m)
        updated = os.path.getmtime(st.model_path) if getattr(st, "model_path", None) and os.path.exists(st.model_path) else None
        if updated is None and hasattr(st, "list_patches"):
            ap = [p.created for p in st.list_patches("applied")]; updated = max(ap) if ap else None
        return {"id": pid, "name": m["meta"].get("name", pid), "description": m["meta"].get("description", ""), "created_by": m["meta"].get("created_by", ""), "rev": m["meta"].get("rev"),
                "counts": {k: len(m[k]) for k in ("requirements", "parts", "tests")}, "clean": rep["clean"], "staged": len(st.list_patches("staged")),
                "busy": pid in self.sessions and self.sessions[pid].busy, "updated": updated}

class Login(BaseModel):
    email: str
    invite: str | None = None
class NewProject(BaseModel):
    id: str
    name: str
    description: str = ""

# ---------------------------------------------------------------------------------------------------------------------
def create_app(root: str | None = None, model: str | None = None, data_root: str | None = None, database_url: str | None = None, tenant: str = "default") -> FastAPI:
    W = Workspace(data_root, root, model, database_url, tenant); app = FastAPI(title="Launch")
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    INVITE = os.environ.get("SETHREAD_INVITE"); SECRET = os.environ.get("SETHREAD_SECRET", "dev")
    import hmac, hashlib, base64
    def sign(email): return base64.urlsafe_b64encode(hmac.new(SECRET.encode(), email.encode(), hashlib.sha256).digest()).decode()[:24]
    def current_user(request: Request) -> str:
        c = request.cookies.get("sethread_user", "")
        if "|" in c:
            email, sig = c.rsplit("|", 1)
            if hmac.compare_digest(sig, sign(email)): return email
        if W.single and not INVITE: return os.environ.get("USER", "engineer")   # local single-project mode needs no login
        raise HTTPException(401, "sign in")
    U = Depends(current_user)
    W.token_ok = lambda email, token: hmac.compare_digest(token, sign("token:" + email.strip().lower()))
    OA = oslc_oauth.OAuthStore(W.data_root or os.path.dirname(W.single))
    app.include_router(oslc.router(W, current_user, OA)); app.include_router(oslc_oauth.router(OA, current_user))

    @app.get("/api/token")
    def api_token(request: Request):
        """Per-user API token for OSLC / scripts: HTTP Basic email:token."""
        user = current_user(request); return {"user": user, "token": sign("token:" + user), "basic_auth_example": f"curl -u '{user}:<token>' -H 'Accept: text/turtle' {str(request.base_url).rstrip('/')}/oslc/catalog"}

    DIST = os.path.join(os.path.dirname(__file__), "dist")
    if os.path.isdir(os.path.join(DIST, "assets")): app.mount("/app/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="app-assets")
    def spa():
        if os.path.exists(os.path.join(DIST, "index.html")): return open(os.path.join(DIST, "index.html"), encoding="utf-8").read()
        return open(os.path.join(STATIC, "index.html"), encoding="utf-8").read()   # legacy single-file UI as fallback
    @app.get("/", response_class=HTMLResponse)
    def index(): return Response(status_code=307, headers={"Location": "/app/"}) if os.path.exists(os.path.join(DIST, "index.html")) else spa()
    @app.get("/app", response_class=HTMLResponse)
    @app.get("/app/", response_class=HTMLResponse)
    @app.get("/app/{path:path}", response_class=HTMLResponse)
    def app_index(path: str = ""): return spa()
    @app.get("/legacy", response_class=HTMLResponse)
    def legacy(): return open(os.path.join(STATIC, "index.html"), encoding="utf-8").read()
    @app.get("/p/{pid}", response_class=HTMLResponse)
    def index_p(pid: str): return Response(status_code=307, headers={"Location": f"/app/p/{pid}"})

    @app.post("/api/login")
    def login(l: Login, response: Response):
        email = l.email.strip().lower()
        if "@" not in email: raise HTTPException(400, "email please")
        if INVITE and l.invite != INVITE: raise HTTPException(403, "invite code required")
        response.set_cookie("sethread_user", f"{email}|{sign(email)}", httponly=True, samesite="lax", max_age=90 * 86400); return {"user": email}
    @app.post("/api/logout")
    def logout(response: Response): response.delete_cookie("sethread_user"); return {"ok": True}
    @app.get("/api/me")
    def me(request: Request):
        try: return {"user": current_user(request), "single": bool(W.single), "invite_required": bool(INVITE)}
        except HTTPException: return {"user": None, "single": bool(W.single), "invite_required": bool(INVITE)}

    @app.get("/api/projects")
    def projects(user: str = U): return [W.summary(p) for p in W.ids()]
    @app.post("/api/projects")
    def new_project(np: NewProject, user: str = U): W.create(np.id.strip().lower(), np.name.strip(), np.description, user); return W.summary(np.id.strip().lower())

    @app.get("/p/{pid}/out/{path:path}")
    def out_file(pid: str, path: str, user: str = U):
        S = W.get(pid); p = os.path.abspath(os.path.join(S.root, "out", path))
        if not p.startswith(os.path.join(S.root, "out")) or not os.path.isfile(p): raise HTTPException(404)
        return FileResponse(p)

    @app.get("/api/p/{pid}/project")
    def project(pid: str, user: str = U):
        S = W.get(pid)
        m = S.store.load(); rep = derive.coverage_report(m)
        return {"id": pid, "user": user, "root": S.root, "meta": m["meta"], "counts": {k: len(m[k]) for k in schema.KINDS}, "stage_of": STAGE_OF, "fmea_counts": rep["counts"],
                "coverage": {k: (len(v) if hasattr(v, "__len__") and not isinstance(v, dict) else v) for k, v in rep.items() if k != "counts"},
                "staged": len(S.store.list_patches("staged")), "busy": S.busy, "auto": S.auto, "toolchain": S.tc, "roles": {k: v["title"] for k, v in R.ROLES.items()}, "role_order": R.ORDER}

    @app.get("/api/p/{pid}/collection/{kind}")
    def collection(pid: str, kind: str, user: str = U):
        S = W.get(pid)
        m = S.store.load()
        if kind == "fmea": return derive.fmea(m)
        if kind == "screened": return derive.screened(m)
        if kind == "unassessed": return derive.unassessed(m)
        if kind == "gaps": return derive.gaps_as_tasks(m)
        if kind == "verification_matrix": return derive.verification_matrix(m)
        if kind == "certification_plan": return derive.certification_plan(m)
        if kind not in m: raise HTTPException(404)
        return [{"id": k, **v} for k, v in m[kind].items()]

    @app.get("/api/p/{pid}/element/{kind}/{eid}")
    def element(pid: str, kind: str, eid: str, user: str = U):
        S = W.get(pid); return element_page(S.store, kind, eid)

    @app.get("/api/p/{pid}/impact/{eid}")
    def impact(pid: str, eid: str, user: str = U):
        S = W.get(pid); return derive.impact(S.store.load(), eid)
    @app.get("/api/p/{pid}/budgets")
    def budgets(pid: str, user: str = U):
        S = W.get(pid); return derive.budgets(S.store.load())

    @app.get("/api/p/{pid}/form/{name}")
    def form(pid: str, name: str, user: str = U):
        S = W.get(pid)
        if name not in forms.FORMS: raise HTTPException(404)
        return forms.form(S.store.load(), name)

    @app.get("/api/p/{pid}/history")
    def history(pid: str, user: str = U):
        S = W.get(pid); st = S.store
        if not hasattr(st, "baselines"): return {"supported": False, "note": "history needs the database store (DATABASE_URL)"}
        return {"supported": True, "rev": st.rev(), "baselines": st.baselines(), "patches": [{"id": p.id, "author": p.author, "rationale": p.rationale, "created": p.created, "status": p.status} for p in st.list_patches("applied")][-50:]}
    @app.post("/api/p/{pid}/baselines")
    def make_baseline(pid: str, b: Baseline, user: str = U):
        S = W.get(pid)
        if not hasattr(S.store, "baseline"): raise HTTPException(400, "history needs the database store")
        return {"name": b.name, "rev": S.store.baseline(b.name, user)}
    @app.get("/api/p/{pid}/diff/{rev_a}/{rev_b}")
    def diff(pid: str, rev_a: int, rev_b: int, user: str = U):
        S = W.get(pid)
        if not hasattr(S.store, "diff"): raise HTTPException(400, "history needs the database store")
        return S.store.diff(rev_a, rev_b)

    @app.get("/api/p/{pid}/scorecard")
    def scorecard(pid: str, user: str = U):
        S = W.get(pid); return quality.scorecard(S.store.load(), S.store)
    @app.get("/api/p/{pid}/requirements_quality")
    def req_quality(pid: str, user: str = U):
        S = W.get(pid); return quality.requirements_report(S.store.load())

    @app.get("/api/p/{pid}/matrix/{rows_kind}/{cols_kind}")
    def matrix(pid: str, rows_kind: str, cols_kind: str, user: str = U):
        S = W.get(pid); m = S.store.load()
        if rows_kind not in schema.KINDS or cols_kind not in schema.KINDS: raise HTTPException(404)
        groups, headers, widths, rows = forms.dependency_matrix(m, rows_kind, cols_kind)
        return {"name": f"matrix-{rows_kind}-{cols_kind}", "title": f"Dependency matrix — {rows_kind} × {cols_kind}", "standard": "rows × columns, cells are relations from the trace graph", "groups": groups, "headers": headers, "widths": widths, "rows": rows, "pairs": forms.MATRIX_PAIRS}

    @app.post("/api/p/{pid}/sync")
    def sync(pid: str, sy: Sync, user: str = U):
        from .. import adapters
        S = W.get(pid); m = S.store.load(); cls = adapters.REGISTRY.get(sy.adapter)
        if not cls: raise HTTPException(404, f"unknown adapter; available {list(adapters.REGISTRY)}")
        kw = {k: v for k, v in (("kind", sy.kind), ("parent", sy.parent)) if v}
        try:
            if sy.direction == "push": return {"written": cls().push(m, sy.path, **kw)}
            patch = cls().pull(m, sy.path, **kw); patch.author = f"adapter:{sy.adapter} via {user}"
            new, issues = S.store.check_patch(m, patch); errs = [f"{i.where}: {i.msg}" for i in issues if i.level == "error"]
            if errs: raise HTTPException(400, "; ".join(errs[:5]))
            S.store.stage(patch); S.emit("patch_staged", id=patch.id, patch=patch_summary(S.store, patch.id)); return {"patch_id": patch.id, "ops": len(patch.ops)}
        except HTTPException: raise
        except Exception as e: raise HTTPException(400, str(e))

    @app.post("/api/p/{pid}/patch")
    def human_patch(pid: str, hp: HumanPatch, user: str = U):
        """A change made by a person in a table or element page. Validated like an agent patch; applied at once when apply=true
        (the person is the reviewer), otherwise staged for someone else to approve. Either way it is in the provenance log."""
        S = W.get(pid); m = S.store.load()
        try:
            patch = Patch(ops=[Op(**o) for o in hp.ops], author=f"user:{user}", rationale=hp.rationale, sources=["app"])
            new, issues = S.store.check_patch(m, patch)
        except Exception as e: raise HTTPException(400, str(e))
        errs = [f"{i.where}: {i.msg}" for i in issues if i.level == "error"]
        if errs: raise HTTPException(400, "; ".join(errs[:5]))
        S.store.stage(patch)
        if hp.apply:
            S.store.approve(patch.id, approver=user); S.emit("patch_applied", id=patch.id, user=user); S.emit("model_changed")
        else: S.emit("patch_staged", id=patch.id, patch=patch_summary(S.store, patch.id))
        return {"ok": True, "patch_id": patch.id, "applied": hp.apply, "warnings": [f"{i.where}: {i.msg}" for i in issues if i.level == "warning"][:5]}

    @app.get("/api/p/{pid}/graph")
    def graph(pid: str, user: str = U):
        S = W.get(pid)
        m = S.store.load(); nodes = {}
        for k in schema.KINDS:
            for i, v in m[k].items(): nodes[i] = {"id": i, "kind": k, "stage": STAGE_OF.get(k, ""), "name": (v.get("name") or v.get("text", "")[:50] or v.get("title", ""))}
        for f in derive.fmea(m): nodes[f["id"]] = {"id": f["id"], "kind": "fmea", "stage": "Risk (derived)", "name": f["mode"][:50], "ap": f["AP"]}
        edges = [{"source": a, "target": b, "rel": r} for a, r, b in derive.trace(m) if a in nodes and b in nodes]
        return {"nodes": list(nodes.values()), "edges": edges}

    @app.get("/api/p/{pid}/search")
    def search(pid: str, q: str, user: str = U):
        S = W.get(pid)
        m = S.store.load(); q = q.lower(); hits = []
        for k in schema.KINDS:
            for i, v in m[k].items():
                blob = (i + " " + json.dumps(v, ensure_ascii=False)).lower()
                if q in blob: hits.append({"kind": k, "id": i, "name": v.get("name") or v.get("text", "")[:80] or v.get("title", "")})
        return hits[:60]

    @app.get("/api/p/{pid}/patches")
    def patches(pid: str, status: str | None = None, user: str = U):
        S = W.get(pid); return [patch_summary(S.store, p.id) for p in S.store.list_patches(status)]
    @app.post("/api/p/{pid}/patches/{patch_id}/approve")
    def approve(pid: str, patch_id: str, user: str = U):
        S = W.get(pid)
        try: S.store.approve(patch_id, approver=user); S.emit("patch_applied", id=patch_id, user=user); S.emit("model_changed"); return {"ok": True}
        except ValueError as e: raise HTTPException(400, str(e))
    @app.post("/api/p/{pid}/patches/{patch_id}/reject")
    def reject(pid: str, patch_id: str, user: str = U):
        S = W.get(pid); S.store.reject(patch_id); S.emit("patch_rejected", id=patch_id, user=user); return {"ok": True}

    @app.post("/api/p/{pid}/chat")
    async def chat(pid: str, c: Chat, user: str = U):
        S = W.get(pid)
        if S.busy: raise HTTPException(409, "agent is busy")
        asyncio.create_task(S.turn(c.text, c.role, user)); return {"ok": True}
    @app.post("/api/p/{pid}/interrupt")
    async def interrupt(pid: str, user: str = U):
        S = W.get(pid)
        if S.client: await S.client.interrupt()
        return {"ok": True}
    @app.post("/api/p/{pid}/permission/{perm_id}")
    def permission(pid: str, perm_id: str, p: Perm, user: str = U):
        S = W.get(pid)
        fut = S.pending.get(perm_id)
        if fut and not fut.done(): fut.set_result(p.answer)
        return {"ok": True}
    @app.post("/api/p/{pid}/settings")
    def settings(pid: str, s: Settings, user: str = U):
        S = W.get(pid)
        if s.auto is not None: S.auto = s.auto
        if s.yolo is not None: S.yolo = s.yolo
        return {"auto": S.auto, "yolo": S.yolo}

    @app.get("/api/p/{pid}/events")
    async def events(pid: str, user: str = U):
        S = W.get(pid)
        async def gen():
            for ev in S.history[-200:]: yield {"event": "ev", "data": json.dumps(ev, default=str)}
            while True:
                try: ev = await asyncio.wait_for(S.events.get(), 15); yield {"event": "ev", "data": json.dumps(ev, default=str)}
                except asyncio.TimeoutError: yield {"event": "ping", "data": "{}"}
        return EventSourceResponse(gen())

    @app.post("/api/p/{pid}/build")
    def build(pid: str, docx: bool = False, user: str = U):
        S = W.get(pid)
        m = S.store.load()
        for s in ("sysml", "views", "docs"): os.makedirs(os.path.join(os.path.join(S.root, "out"), s), exist_ok=True)
        files = sysml.emit(m, os.path.join(os.path.join(S.root, "out"), "sysml")); done, failed = views.render_all(m, os.path.join(os.path.join(S.root, "out"), "views")); md = docs.build(m, os.path.join(os.path.join(S.root, "out"), "docs"))
        res = {"sysml": sorted(files), "views": sorted(os.listdir(os.path.join(os.path.join(S.root, "out"), "views"))), "docs": f"/p/{pid}/out/docs/design_documentation.md", "failed": failed}
        if docx:
            from ..docx_export import export
            name = m["meta"].get("name", "System").replace(" ", "_"); res["docx"] = f"/p/{pid}/out/" + os.path.basename(export(md, os.path.join(os.path.join(S.root, "out"), f"{name}_System_Design_Documentation.docx")))
        S.emit("built", **res); return res

    @app.get("/api/p/{pid}/artifacts")
    def artifacts(pid: str, user: str = U):
        S = W.get(pid)
        r = {"views": [], "sysml": [], "docs": [], "docx": []}
        for sub, key in (("views", "views"), ("sysml", "sysml"), ("docs", "docs")):
            d = os.path.join(os.path.join(S.root, "out"), sub)
            if os.path.isdir(d): r[key] = sorted(os.listdir(d))
        od = os.path.join(S.root, "out"); r["docx"] = sorted(f for f in os.listdir(od) if f.endswith(".docx")) if os.path.isdir(od) else []
        r["documents"] = sorted(os.listdir(S.docs_dir)) if os.path.isdir(S.docs_dir) else []
        return r

    @app.post("/api/p/{pid}/documents")
    async def upload(pid: str, file: UploadFile = File(...), user: str = U):
        S = W.get(pid); dest = os.path.join(S.docs_dir, os.path.basename(file.filename))
        with open(dest, "wb") as fh: shutil.copyfileobj(file.file, fh)
        return {"ok": True, "name": os.path.basename(dest)}

    @app.get("/api/p/{pid}/file")
    def file(pid: str, path: str, user: str = U):
        S = W.get(pid)
        p = os.path.abspath(os.path.join(S.root, path))
        if not p.startswith(S.root) or not os.path.exists(p): raise HTTPException(404)
        return FileResponse(p)
    return app

def main(root: str | None = ".", port: int = 8765, model: str | None = None, open_browser: bool = True, data_root: str | None = None, host: str = "127.0.0.1", database_url: str | None = None, tenant: str = "default"):
    import uvicorn
    app = create_app(root if not data_root else None, model, data_root, database_url or os.environ.get("DATABASE_URL"), tenant or os.environ.get("SETHREAD_TENANT", "default"))
    if open_browser: threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
