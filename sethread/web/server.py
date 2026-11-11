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
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from claude_agent_sdk import (ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, ResultMessage, UserMessage,
                              TextBlock, ToolUseBlock, ToolResultBlock, PermissionResultAllow, PermissionResultDeny)
from ..store import Store
from .. import derive, schema, tables, testdata, memory, pdp, dfx as DFX, org as ORG, policy as harness, sysml, views, docs, forms, quality, oslc, oslc_oauth, lifecycle, comments as C
from ..store import Patch, Op
from ..agents.tools import make_server
from ..agents import roles as R
from ..harness.prompt import HARNESS
from ..harness import toolchain

STATIC = os.path.join(os.path.dirname(__file__), "static")
SAFE_TOOLS = {"Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch", "TodoWrite", "Task", "ToolSearch"}
BUILTIN = ["Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch", "TodoWrite"]

STAGE_OF = schema.STAGE_OF  # kind → ISO 15288 process (drives the navigation)

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
        try: self.store.root = self.root
        except Exception: pass
        self.policy = harness.load_policy(self.root)
        self.tc = toolchain.detect()
        # Conversations: like Claude, a project has many threads; each thread is its own agent session with its own memory of the
        # conversation, all grounded in the same model graph. Persisted as JSONL so they survive restarts and are shared across users.
        self.threads: dict[str, dict] = {}; self.thread_dir = os.path.join(self.root, ".sethread", "threads"); os.makedirs(self.thread_dir, exist_ok=True)
        for fn in sorted(os.listdir(self.thread_dir)):
            if fn.endswith(".jsonl"):
                tid = fn[:-6]; evs = [json.loads(l) for l in open(os.path.join(self.thread_dir, fn)) if l.strip()]
                meta = next((e for e in evs if e.get("type") == "thread"), {"title": tid, "created": 0, "user": ""})
                self.threads[tid] = {"id": tid, "title": meta.get("title", tid), "created": meta.get("created", 0), "user": meta.get("user", ""), "client": None, "busy": False, "history": [e for e in evs if e.get("type") != "thread"], "updated": evs[-1]["ts"] if evs else 0}

    def new_thread(self, title: str, user: str) -> dict:
        tid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        t = {"id": tid, "title": title[:80] or "New conversation", "created": time.time(), "user": user, "client": None, "busy": False, "history": [], "updated": time.time()}
        self.threads[tid] = t
        with open(os.path.join(self.thread_dir, tid + ".jsonl"), "a") as fh: fh.write(json.dumps({"type": "thread", "title": t["title"], "created": t["created"], "user": user, "ts": t["created"]}) + "\n")
        return t
    def thread_summary(self, t: dict) -> dict:
        last = next((e for e in reversed(t["history"]) if e["type"] in ("assistant", "user")), None)
        return {"id": t["id"], "title": t["title"], "created": t["created"], "updated": t["updated"], "user": t["user"], "busy": t["busy"], "n": len([e for e in t["history"] if e["type"] in ("user", "assistant")]), "last": (last or {}).get("text", "")[:140]}

    def emit(self, type_: str, **data):
        ev = {"type": type_, "ts": time.time(), **data}; self.history.append(ev); self.events.put_nowait(ev)
        tid = data.get("thread")
        if tid and tid in self.threads:
            t = self.threads[tid]; t["history"].append(ev); t["updated"] = ev["ts"]
            if type_ not in ("idle",):
                with open(os.path.join(self.thread_dir, tid + ".jsonl"), "a") as fh: fh.write(json.dumps(ev, default=str) + "\n")
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

    async def ensure_client(self, thread: dict | None = None):
        if thread is not None and thread.get("client"): return thread["client"]
        if thread is None and self.client: return self.client
        sp = HARNESS + "\n\n# Toolchain\n" + toolchain.summary(self.tc) + f"\n\n# Project root\n{self.root}\n\n# UI\nYou are Launch: Claude for physical-product engineers, driven by this project's MBSE graph. Ground every answer in the model — read the relevant elements before answering, cite element ids, and prefer proposing a patch over describing a change. The engineer is in a web app, not a terminal. When you mention an element, write its id (e.g. R-012) — the app turns ids into links. Keep answers short; the app shows your staged patches as cards."
        opts = ClaudeAgentOptions(system_prompt=sp, mcp_servers={"sethread": self.server}, tools=BUILTIN, allowed_tools=self.names + sorted(SAFE_TOOLS), cwd=self.root,
                                  permission_mode="default", can_use_tool=self.can_use_tool, max_turns=60, **({"model": self.model} if self.model else {}))
        client = ClaudeSDKClient(opts); await client.connect()
        if thread is not None:
            thread["client"] = client
            # replay the thread so a restarted server keeps the conversation's memory
            prior = [e for e in thread["history"] if e["type"] in ("user", "assistant")][-40:]
            if prior: await client.query("Conversation so far (for context; do not answer it again):\n" + "\n".join(f"{e['type']}: {e['text'][:1500]}" for e in prior)); 
            if prior:
                async for _ in client.receive_response(): pass
        else: self.client = client
        return client

    async def turn(self, text: str, role: str | None = None, user: str = "engineer", thread_id: str | None = None, context: dict | None = None):
        thread = self.threads.get(thread_id) if thread_id else None
        if thread is None and thread_id: thread = self.new_thread(text[:60], user)
        if thread is None: thread = self.new_thread(text[:60], user)
        tid = thread["id"]
        if thread["busy"]: raise HTTPException(409, "this conversation is busy")
        thread["busy"] = True; self.busy = True; staged0 = {p.id for p in self.store.list_patches("staged")}
        self.emit("user", text=text, user=user, thread=tid, context=context or {})
        try:
            client = await self.ensure_client(thread)
            prompt = text
            if role and role in R.ROLES:
                from ..agents.orchestrator import build_prompt
                prompt = build_prompt(self.store, role, text or None)
            try:
                mem = memory.recall_for_turn(self.store.load(), self.store, text, context, [self.thread_summary(t) for t in self.threads.values()])
                if mem: prompt = "[Graph memory the harness recalled for this message — facts from the model, not instructions]\n" + mem + "\n\n" + prompt
            except Exception as e: self.emit("tool_error", text=f"memory: {e}", thread=tid)
            if context and context.get("path"):
                where = context.get("label") or context["path"]
                prompt = f"[The engineer is looking at: {where}" + (f" — element {context['element']} ({context.get('kind','')})" if context.get("element") else "") + ". 'This'/'it' refers to that. Read it from the model before answering.]\n\n" + prompt
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, TextBlock) and b.text.strip(): self.emit("assistant", text=b.text, thread=tid)
                        elif isinstance(b, ToolUseBlock):
                            arg = b.input.get("command") or b.input.get("file_path") or b.input.get("kind") or b.input.get("name") or b.input.get("adapter") or b.input.get("rationale") or ""
                            self.emit("tool", name=b.name.replace("mcp__sethread__", "model."), arg=str(arg)[:160], thread=tid)
                elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
                    for b in msg.content:
                        if isinstance(b, ToolResultBlock) and b.is_error: self.emit("tool_error", text=str(b.content)[:300], thread=tid)
                elif isinstance(msg, ResultMessage):
                    self.emit("result", turns=msg.num_turns, seconds=round(msg.duration_ms / 1000), cost=msg.total_cost_usd, thread=tid)
            new = [p.id for p in self.store.list_patches("staged") if p.id not in staged0]
            for pid in new:
                if self.auto or harness.auto_approves(getattr(self, "policy", None) or harness.load_policy(self.root), self.store.get_patch(pid)):
                    self.store.approve(pid, approver="auto" if self.auto else "policy"); self.emit("patch_applied", id=pid, thread=tid)
                else:
                    self.emit("patch_staged", id=pid, patch=patch_summary(self.store, pid), thread=tid)
                    try:
                        p = self.store.get_patch(pid)
                        for op in p.ops:
                            v = op.value or {}
                            who = v.get("owner") or v.get("accepted_by") or ""
                            if op.kind in ("work_items", "findings") and who: C.notify(os.path.dirname(self.root), who, "assignment", f"agent proposed {op.kind[:-1]} {op.id}: {v.get('title','')}", f"/p/{self.pid}/inbox", self.pid)
                    except Exception: pass
            if new: self.emit("model_changed")
        except Exception as e:
            self.emit("error", text=f"{type(e).__name__}: {e}", thread=tid)
        finally:
            thread["busy"] = False; self.busy = any(t["busy"] for t in self.threads.values()); self.emit("idle", thread=tid)

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
    thread: str | None = None
    context: dict | None = None
class NewThread(BaseModel):
    title: str = ""
class SheetCommit(BaseModel):
    file: str = "sheet"
    sheet: str = ""
    headers: list[str]
    rows: list[list]
    kind: str
    mapping: dict[str, str] = {}
    id_column: str = ""
    id_prefix: str = ""
    table_name: str = ""
    table_id: str = ""
    apply: bool = False
def _cell(x):
    if hasattr(x, "isoformat"): return x.isoformat()
    return x
def _slug(s: str) -> str: return "".join(ch if ch.isalnum() else "-" for ch in s.strip().upper()).strip("-")[:24] or "TABLE"
def _guess_kind(headers: list[str]) -> str:
    h = " ".join(headers).lower()
    for kind, words in [("requirements", ["requirement", "shall", "verify"]), ("tests", ["test", "pass/fail", "passfail", "method"]), ("parts", ["part", "bom", "qty", "supplier"]), ("suppliers", ["vendor", "supplier"]),
                        ("work_items", ["action", "owner", "due", "task"]), ("findings", ["finding", "severity"]), ("risks", ["risk", "prob", "impact"]), ("field_events", ["symptom", "field", "return"]), ("needs", ["need", "stakeholder"])]:
        if sum(w in h for w in words) >= 2: return kind
    return "tables"
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
class CommentIn(BaseModel):
    element: str
    text: str
    parent: str | None = None
    assign: str | None = None
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
    process: str | None = None   # organization process variant to inherit

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

    # ---- organization: process, teams & members, tools, policy — defined once, inherited by every project
    def org_root(): return W.data_root or os.path.dirname(W.single or ".")
    @app.get("/api/org")
    def get_org(user: str = U): o = ORG.load(org_root(), W.tenant); return {**o, "me": {"email": user, "role": ORG.role_of(o, user), "teams": ORG.member_teams(o, user)}}
    @app.post("/api/org")
    def set_org(body: dict, user: str = U):
        o = ORG.load(org_root(), W.tenant)
        if ORG.role_of(o, user) not in ("admin", "program_manager"): raise HTTPException(403, "admins and program managers edit the organization")
        for k in ("name", "process", "teams", "members", "tools", "policy"):
            if k in body: o[k] = body[k]
        ORG.save(org_root(), o); return get_org(user)
    @app.post("/api/org/apply/{pid}")
    def apply_org(pid: str, body: dict, user: str = U):
        S = W.get(pid); m = S.store.load(); o = ORG.load(org_root(), W.tenant)
        ops = ORG.apply_ops(o, m, body.get("start") or time.strftime("%Y-%m-%d"))
        if not ops: return {"ok": True, "patch_id": None}
        ops = ORG.apply_ops(o, m, body.get("start") or time.strftime("%Y-%m-%d"), body.get("variant"), set(body["only"]) if body.get("only") else None)
        if not ops: return {"ok": True, "patch_id": None}
        pr = ORG.process_variant(o, body.get("variant"))
        r = human_patch(pid, HumanPatch(ops=ops, rationale=f"Apply organization process '{pr.get('name','')}' and teams" + (f" (re-sync {len(body['only'])} item(s))" if body.get("only") else ""), apply=bool(body.get("apply", True))), user)
        m = S.store.load(); m.setdefault("program", {}).update(pdp=pr.get("name", ""), pdp_source={"variant": pr.get("id", "default"), "applied": time.strftime("%Y-%m-%d"), "by": user}); S.store.save(m); return r
    # ---- Design for X
    def _dfx_enabled():
        try:
            o = ORG.load(org_root(), W.tenant); en = [t["id"].split(":", 1)[1] for t in o.get("tools", []) if t["id"].startswith("dfx:") and t.get("enabled")]
            return en if en else None
        except Exception: return None
    @app.get("/api/p/{pid}/dfx")
    def dfx_list(pid: str, user: str = U):
        S = W.get(pid); m = S.store.load(); return DFX.summary(m, S.root, _dfx_enabled())
    @app.get("/api/p/{pid}/dfx/{x}")
    def dfx_one(pid: str, x: str, user: str = U):
        S = W.get(pid); m = S.store.load(); e = DFX.evaluate(m, x, S.root)
        if not e: raise HTTPException(404, "no such DfX set")
        return e
    @app.post("/api/p/{pid}/dfx/{x}/item")
    def dfx_set(pid: str, x: str, body: dict, user: str = U):
        """reviewer sets a manual status (pass/fail/partial/n/a/unknown) with evidence ids and a note → patch on dfx_reviews"""
        S = W.get(pid); m = S.store.load(); rid = "DFX-" + x; cur = m.get("dfx_reviews", {}).get(rid) or {"x": x, "items": {}}
        items = dict(cur.get("items") or {}); iid = body["item"]
        if body.get("status") in (None, "", "auto"): items.pop(iid, None)
        else: items[iid] = {"status": body["status"], "evidence": body.get("evidence", []), "note": body.get("note", ""), "by": user, "date": time.strftime("%Y-%m-%d")}
        value = {"x": x, "items": items, "date": time.strftime("%Y-%m-%d"), "by": user}
        return human_patch(pid, HumanPatch(ops=[{"op": "update" if rid in m.get("dfx_reviews", {}) else "add", "kind": "dfx_reviews", "id": rid, "value": value}], rationale=f"DfX {x}: {iid} → {body.get('status') or 'auto'}" + (f" — {body.get('note')}" if body.get("note") else ""), apply=True), user)

    @app.get("/api/p/{pid}/pdp/tailoring")
    def pdp_tailoring(pid: str, user: str = U):
        S = W.get(pid); m = S.store.load(); o = ORG.load(org_root(), W.tenant); return {**ORG.tailoring(o, m), "variants": [{"id": x["id"], "name": x.get("name", x["id"])} for x in o.get("processes", [])]}
    @app.post("/api/p/{pid}/pdp/waive")
    def pdp_waive(pid: str, body: dict, user: str = U):
        S = W.get(pid); m = S.store.load(); did = body.get("id")
        if did not in m.get("deliverables", {}): raise HTTPException(404, "no such deliverable")
        value = {"waived": {} if body.get("unwaive") else {"by": user, "reason": body.get("reason", ""), "date": time.strftime("%Y-%m-%d")}}
        return human_patch(pid, HumanPatch(ops=[{"op": "update", "kind": "deliverables", "id": did, "value": value}], rationale=("Un-waive " if body.get("unwaive") else "Waive ") + f"deliverable {did}: {body.get('reason', '')}", apply=True), user)

    @app.get("/api/org/templates")
    def org_templates(user: str = U): return {"templates": pdp.templates(org_root()), "detail": {t["id"]: pdp.template(t["id"], org_root()) for t in pdp.templates(org_root())}}

    @app.get("/api/projects")
    def projects(user: str = U): return [W.summary(p) for p in W.ids()]
    @app.post("/api/projects")
    def new_project(np: NewProject, user: str = U):
        pid = np.id.strip().lower(); W.create(pid, np.name.strip(), np.description, user)
        try:
            o = ORG.load(org_root(), W.tenant); S = W.get(pid); m = S.store.load(); ops = ORG.apply_ops(o, m, time.strftime("%Y-%m-%d"), np.process)
            if ops:
                human_patch(pid, HumanPatch(ops=ops, rationale=f"Organization defaults: teams and process ({o.get('name')})", apply=True), user)
                pr = ORG.process_variant(o, np.process); m = S.store.load(); m.setdefault("program", {}).update(pdp=pr.get("name", ""), pdp_source={"variant": pr.get("id", "default"), "applied": time.strftime("%Y-%m-%d"), "by": user}); S.store.save(m)
        except Exception as e: pass
        return W.summary(pid)

    # ---- examples: shipped product models to assess the app with (examples/<id>/{example.yaml, model.yaml, docs/})
    def examples_dir():
        for d in (os.environ.get("LAUNCH_EXAMPLES"), os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "examples")):
            if d and os.path.isdir(d): return d
        return None
    @app.get("/api/examples")
    def examples(user: str = U):
        d = examples_dir(); out = []
        if not d: return out
        existing = set(W.ids())
        for eid in sorted(os.listdir(d)):
            ep = os.path.join(d, eid, "example.yaml")
            if not os.path.isfile(ep): continue
            meta = yaml.safe_load(open(ep)) or {}
            try: cnt = {k: len(v) for k, v in yaml.safe_load(open(os.path.join(d, eid, "model.yaml"))).items() if isinstance(v, dict) and k in schema.KINDS}
            except Exception: cnt = {}
            out.append({"id": eid, **meta, "counts": cnt, "project": eid if eid in existing else None, "docs": sorted(os.listdir(os.path.join(d, eid, "docs"))) if os.path.isdir(os.path.join(d, eid, "docs")) else []})
        return out
    @app.post("/api/examples/{eid}")
    def create_example(eid: str, user: str = U):
        """Create a project from a shipped example: copies docs/ and loads model.yaml (file mode copies the directory; DB mode imports it as the first patch)."""
        d = examples_dir(); src = os.path.join(d or "", eid)
        if not d or not os.path.isfile(os.path.join(src, "example.yaml")): raise HTTPException(404, "no such example")
        if W.single: raise HTTPException(400, "single-project mode")
        if eid in W.ids(): return W.summary(eid)
        root = W.path(eid); os.makedirs(root, exist_ok=True)
        if os.path.isdir(os.path.join(src, "docs")): shutil.copytree(os.path.join(src, "docs"), os.path.join(root, "docs"), dirs_exist_ok=True)
        if W.db is None:
            shutil.copy(os.path.join(src, "model.yaml"), os.path.join(root, "model.yaml"))
        else:
            from ..dbstore import import_yaml_project; import_yaml_project(W.db, W.tenant, eid, src)
        st = W._store(eid, root); m = st.load(); m["meta"]["created_by"] = user; st.save(m)
        return W.summary(eid)

    @app.get("/p/{pid}/out/{path:path}")
    def out_file(pid: str, path: str, user: str = U):
        S = W.get(pid); p = os.path.abspath(os.path.join(S.root, "out", path))
        if not p.startswith(os.path.join(S.root, "out")) or not os.path.isfile(p): raise HTTPException(404)
        return FileResponse(p)

    @app.get("/api/p/{pid}/project")
    def project(pid: str, user: str = U):
        S = W.get(pid)
        m = S.store.load(); rep = derive.coverage_report(m)
        return {"id": pid, "user": user, "root": S.root, "meta": m["meta"], "counts": {k: len(m[k]) for k in schema.KINDS}, "teams": m.get("teams", {}), "stage": lifecycle.convergence(m), "stage_of": STAGE_OF, "lifecycle": schema.LIFECYCLE, "processes": [{"name": n, "stage": st, "kinds": ks} for n, st, ks in schema.PROCESSES], "management": [{"name": n, "kinds": ks} for n, ks in schema.MANAGEMENT], "schema": {k: {"req": v["req"], "opt": v["opt"], "refs": v["refs"]} for k, v in schema.KINDS.items()}, "fmea_counts": rep["counts"],
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

    @app.get("/api/p/{pid}/lifecycle")
    def lifecycle_state(pid: str, user: str = U):
        S = W.get(pid); m = S.store.load()
        return {**lifecycle.gate_readiness(m, S.store), "workflows": lifecycle.workflows(m), "teams": lifecycle.team_workload(m), "staleness": lifecycle.staleness(m, S.store)}

    @app.get("/api/p/{pid}/comments")
    def list_comments(pid: str, element: str | None = None, user: str = U):
        S = W.get(pid); return C.list_comments(S.root, element)
    @app.post("/api/p/{pid}/comments")
    def add_comment(pid: str, c: CommentIn, user: str = U):
        S = W.get(pid); rec = C.add(S.root, c.element, user, c.text, c.parent, c.assign)
        for who in rec["mentions"] + ([c.assign] if c.assign else []): C.notify(S.root, who, "mention" if who in rec["mentions"] else "assignment", f"{user} on {c.element}: {c.text[:120]}", f"/p/{pid}/element/{{kind}}/{c.element}", pid)
        S.emit("comment", **rec); return rec
    @app.post("/api/p/{pid}/comments/{cid}/resolve")
    def resolve_comment(pid: str, cid: str, user: str = U):
        S = W.get(pid); return C.resolve(S.root, cid, user)
    @app.get("/api/notifications")
    def notifications(request: Request, user: str = U):
        return C.notifications_for(W.data_root or os.path.dirname(W.single), user)
    @app.post("/api/notifications/read")
    def notifications_read(request: Request, user: str = U):
        C.mark_read(W.data_root or os.path.dirname(W.single), user); return {"ok": True}

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

    # ---- office replacement: tables with formulas, spreadsheet import (xlsx/csv/pasted TSV) into any collection or a new table
    @app.get("/api/p/{pid}/table/{tid}")
    def table(pid: str, tid: str, user: str = U):
        S = W.get(pid); m = S.store.load()
        if tid not in m.get("tables", {}): raise HTTPException(404, "no such table")
        return tables.render(m, tid)
    @app.post("/api/p/{pid}/table/{tid}/eval")
    def table_eval(pid: str, tid: str, body: dict, user: str = U):
        """Evaluate a candidate formula against the current rows (used while typing a formula)."""
        S = W.get(pid); m = S.store.load(); t = m["tables"].get(tid) or {"rows": [], "columns": []}
        rows = t["rows"][:5]
        return {"sample": [tables.evaluate(body.get("formula", ""), m, t["rows"], r) for r in rows]}
    @app.post("/api/p/{pid}/sheet/preview")
    async def sheet_preview(pid: str, file: UploadFile = File(...), user: str = U):
        """Parse an uploaded .xlsx/.csv/.tsv: every sheet with headers and rows, plus a guess of the target collection."""
        W.get(pid); data = await file.read(); name = file.filename or "sheet"
        sheets = []
        if name.lower().endswith((".xlsx", ".xlsm")):
            import openpyxl, io
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
            for ws in wb.worksheets:
                rows = [[("" if c is None else c) for c in r] for r in ws.iter_rows(values_only=True)]
                rows = [r for r in rows if any(str(x).strip() for x in r)]
                if rows: sheets.append({"name": ws.title, "headers": [str(h) for h in rows[0]], "rows": [[_cell(x) for x in r] for r in rows[1:]]})
        else:
            import csv, io
            txt = data.decode("utf-8-sig", errors="replace"); dialect = csv.excel_tab if "\t" in txt.splitlines()[0] else csv.excel
            rows = [r for r in csv.reader(io.StringIO(txt), dialect) if any(x.strip() for x in r)]
            if rows: sheets.append({"name": name, "headers": rows[0], "rows": rows[1:]})
        for sh in sheets: sh["guess"] = _guess_kind(sh["headers"])
        return {"file": name, "sheets": sheets, "kinds": {k: {"req": v["req"], "opt": list(v["opt"]), "refs": v["refs"]} for k, v in schema.KINDS.items()}}
    @app.post("/api/p/{pid}/sheet/commit")
    def sheet_commit(pid: str, body: SheetCommit, user: str = U):
        """Rows → elements of a kind (mapping: field → column header) or → a new table. Becomes a human patch (applied or staged)."""
        S = W.get(pid); m = S.store.load(); hdr = {h: i for i, h in enumerate(body.headers)}
        ops = []
        if body.kind == "tables":
            t = tables.from_sheet(body.headers, body.rows); tid = body.table_id or ("TBL-" + _slug(body.table_name or body.sheet or "table"))
            ops.append({"op": "add" if tid not in m.get("tables", {}) else "update", "kind": "tables", "id": tid, "value": {"name": body.table_name or body.sheet or tid, "description": f"imported from {body.file}", **t}})
        else:
            if body.kind not in schema.KINDS: raise HTTPException(400, "unknown kind")
            spec = schema.KINDS[body.kind]; n = 0
            for r in body.rows:
                val = {}
                for field, col in body.mapping.items():
                    if col in hdr and hdr[col] < len(r):
                        v = r[hdr[col]]
                        if field in spec["refs"] and isinstance(spec["opt"].get(field, None), list) or field in ("tests", "reqs", "funcs", "alloc", "from_", "regs", "parts", "elements", "members"): v = [x.strip() for x in str(v).replace(";", ",").split(",") if x.strip()] if v != "" else []
                        val[field] = v
                for f in spec["req"]:
                    if f not in val: val[f] = [] if f in ("tests", "reqs", "funcs", "alloc", "parts", "lcs", "items", "columns", "rows") else ""
                eid = (r[hdr[body.id_column]] if body.id_column in hdr and hdr[body.id_column] < len(r) and r[hdr[body.id_column]] else "") or f"{body.id_prefix or body.kind[:3].upper()}-{len(m[body.kind]) + n + 1:03d}"
                n += 1; ops.append({"op": "update" if eid in m[body.kind] else "add", "kind": body.kind, "id": str(eid), "value": val})
        if not ops: raise HTTPException(400, "nothing to import")
        hp = HumanPatch(ops=ops, rationale=f"Imported {len(ops)} row(s) from {body.file} → {body.kind}", apply=body.apply)
        return human_patch(pid, hp, user)

    # ---- test execution & data: upload a run's data file for a test → metrics, limit checks, verdict, chart series; test status follows
    def _runs_dir(S, rid): d = os.path.join(S.root, "runs", rid); os.makedirs(d, exist_ok=True); return d
    @app.post("/api/p/{pid}/runs")
    async def new_run(pid: str, test: str = Form(...), unit: str = Form(""), operator: str = Form(""), station: str = Form(""), notes: str = Form(""), limits: str = Form(""), file: UploadFile | None = File(None), user: str = U):
        S = W.get(pid); m = S.store.load()
        if test not in m["tests"]: raise HTTPException(404, "no such test")
        n = len([r for r in m.get("test_runs", {}).values() if r["test"] == test]) + 1; rid = f"RUN-{test}-{n:02d}"
        value = {"test": test, "date": time.strftime("%Y-%m-%d"), "unit": unit, "operator": operator or user, "station": station, "notes": notes, "rev": m["meta"].get("rev"), "result": "recorded", "channels": [], "metrics": {}, "limits": {}, "checks": []}
        lims = testdata.limits_for_test(m, test)
        for line in (limits or "").splitlines():
            L = testdata.parse_limit(line)
            if L: lims.append(L)
        if file is not None and file.filename:
            raw = (await file.read()).decode("utf-8-sig", errors="replace"); d = testdata.parse(raw)
            dest = _runs_dir(S, rid); open(os.path.join(dest, os.path.basename(file.filename)), "w").write(raw)
            mets = testdata.metrics(d); checks = testdata.check(mets, lims); ser = testdata.series(d)
            json.dump(ser, open(os.path.join(dest, "series.json"), "w"))
            value.update(data=os.path.basename(file.filename), channels=[c for c in d["columns"] if c != d["time"]], metrics=mets, checks=checks, limits={L["channel"]: f"{L['op']} {L['value']} {L.get('unit', '')}".strip() for L in lims})
            if checks and all(c["ok"] is not None for c in checks): value["result"] = "pass" if all(c["ok"] for c in checks) else "fail"
            elif checks: value["result"] = "pass" if all(c["ok"] for c in checks if c["ok"] is not None) and any(c["ok"] is not None for c in checks) else "inconclusive"
        ops = [{"op": "add", "kind": "test_runs", "id": rid, "value": value}]
        if value["result"] in ("pass", "fail"):
            tv = m["tests"][test]; attrs = dict(tv.get("attrs") or {}); attrs["result_ts"] = time.time()
            ops.append({"op": "update", "kind": "tests", "id": test, "value": {"status": "passed" if value["result"] == "pass" else "failed", "result": value["result"], "result_rev": m["meta"].get("rev"), "attrs": attrs}})
        r = human_patch(pid, HumanPatch(ops=ops, rationale=f"Test run {rid}: {value['result']}" + (f" ({value['data']})" if value.get("data") else ""), apply=True), user)
        return {"id": rid, **value, "patch_id": r["patch_id"]}
    @app.get("/api/p/{pid}/run/{rid}")
    def run(pid: str, rid: str, user: str = U):
        S = W.get(pid); m = S.store.load(); v = m.get("test_runs", {}).get(rid)
        if not v: raise HTTPException(404, "no such run")
        p = os.path.join(S.root, "runs", rid, "series.json"); ser = json.load(open(p)) if os.path.exists(p) else None
        t = m["tests"].get(v["test"], {}); reqs = [r for r, rv in m["requirements"].items() if v["test"] in rv.get("tests", [])]
        return {"id": rid, **v, "series": ser, "test_name": t.get("name", ""), "requirements": reqs}
    @app.get("/api/p/{pid}/runs")
    def runs(pid: str, user: str = U):
        S = W.get(pid); m = S.store.load()
        return [{"id": k, **v, "metrics": {c: {kk: mv.get(kk) for kk in ("min", "max", "mean")} for c, mv in (v.get("metrics") or {}).items()}, "test_name": m["tests"].get(v["test"], {}).get("name", "")} for k, v in sorted(m.get("test_runs", {}).items(), key=lambda kv: kv[1].get("date", ""), reverse=True)]

    # ---- attachments: CAD, drawings, schematics, reports pinned to an element
    @app.post("/api/p/{pid}/attach")
    async def attach(pid: str, element: str = Form(...), role: str = Form("document"), title: str = Form(""), rev: str = Form(""), file: UploadFile = File(...), user: str = U):
        S = W.get(pid); m = S.store.load(); kind = _kind_of(m, element)
        if not kind: raise HTTPException(404, "no such element")
        d = os.path.join(S.root, "files", element); os.makedirs(d, exist_ok=True); name = os.path.basename(file.filename or "file"); dest = os.path.join(d, name)
        with open(dest, "wb") as fh: shutil.copyfileobj(file.file, fh)
        aid = f"ATT-{element}-{len([a for a in m.get('attachments', {}).values() if a['element'] == element]) + 1:02d}"
        value = {"element": element, "file": f"files/{element}/{name}", "role": role, "title": title or name, "format": name.rsplit(".", 1)[-1].lower() if "." in name else "", "rev": rev, "date": time.strftime("%Y-%m-%d"), "size": os.path.getsize(dest), "uploaded_by": user}
        human_patch(pid, HumanPatch(ops=[{"op": "add", "kind": "attachments", "id": aid, "value": value}], rationale=f"Attached {name} to {element} as {role}", apply=True), user)
        return {"id": aid, **value}
    @app.get("/api/p/{pid}/attachments/{element}")
    def attachments(pid: str, element: str, user: str = U):
        S = W.get(pid); m = S.store.load(); return [{"id": k, **v} for k, v in m.get("attachments", {}).items() if v["element"] == element]

    @app.get("/api/p/{pid}/memory/{eid}")
    def element_mem(pid: str, eid: str, user: str = U):
        S = W.get(pid); m = S.store.load(); mem = memory.element_memory(m, S.store, eid, [S.thread_summary(t) for t in S.threads.values()])
        if not mem: raise HTTPException(404, "no such element")
        return {**mem, "text": memory.recall_text(mem)}

    # ---- the harness, as a product surface: policy, roles, skills, watchers; editable and versioned with the project
    @app.get("/api/p/{pid}/harness")
    def get_harness(pid: str, user: str = U):
        S = W.get(pid); return harness.describe(S)
    @app.post("/api/p/{pid}/harness")
    def set_harness(pid: str, body: dict, user: str = U):
        S = W.get(pid); harness.save_policy(S.root, body.get("policy", {})); S.policy = harness.load_policy(S.root); return harness.describe(S)

    # ---- agile execution visuals: board (kanban over work items), timeline (gates, handoffs, work items, runs), trend (coverage over revs)
    @app.get("/api/p/{pid}/board")
    def board(pid: str, user: str = U):
        S = W.get(pid); m = S.store.load(); return harness.board(m)
    @app.get("/api/p/{pid}/timeline")
    def timeline(pid: str, user: str = U):
        S = W.get(pid); m = S.store.load(); return harness.timeline(m)
    @app.get("/api/p/{pid}/trend")
    def trend(pid: str, user: str = U):
        S = W.get(pid); return harness.trend(S.store)

    # ---- product development process: phases, gates, deliverables per team; templates; the gate × team matrix
    @app.get("/api/p/{pid}/pdp")
    def get_pdp(pid: str, user: str = U):
        S = W.get(pid); m = S.store.load(); return {**pdp.matrix(m), "templates": pdp.templates(S.root), "name": (m.get("program") or {}).get("pdp", "")}
    @app.post("/api/p/{pid}/pdp/apply")
    def apply_pdp(pid: str, body: dict, user: str = U):
        S = W.get(pid); m = S.store.load(); t = pdp.template(body.get("template", ""), S.root)
        if not t: raise HTTPException(404, "no such template")
        ops = pdp.apply_ops(m, t, body.get("start") or time.strftime("%Y-%m-%d"), int(body.get("spacing_days", 45)))
        r = human_patch(pid, HumanPatch(ops=ops, rationale=f"Adopt PDP template: {t['name']}", apply=bool(body.get("apply", True))), user)
        m = S.store.load(); m.setdefault("program", {})["pdp"] = t["name"]; S.store.save(m)
        return r
    @app.get("/api/p/{pid}/team/{tid}/deliverables")
    def team_deliv(pid: str, tid: str, user: str = U):
        S = W.get(pid); m = S.store.load(); return pdp.team_deliverables(m, tid)

    @app.get("/api/p/{pid}/team/{tid}")
    def team_ws(pid: str, tid: str, user: str = U):
        S = W.get(pid); m = S.store.load()
        if tid not in m["teams"]: raise HTTPException(404, "no such team")
        return lifecycle.team_workspace(m, tid, S.store, [S.thread_summary(t) for t in S.threads.values()])
    @app.get("/api/p/{pid}/me/team")
    def my_team(pid: str, user: str = U):
        """which team(s) the signed-in user belongs to (members/lead emails) — drives 'My team' in the sidebar"""
        S = W.get(pid); m = S.store.load(); u = user.lower()
        mine = [t for t, v in m["teams"].items() if u in [x.lower() for x in v.get("members", [])] or v.get("lead", "").lower() == u]
        try: mine += [t for t in ORG.member_teams(ORG.load(org_root(), W.tenant), user) if t in m["teams"] and t not in mine]
        except Exception: pass
        return {"teams": mine, "user": user}

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
        t = S.threads.get(c.thread) if c.thread else None
        if t is None: t = S.new_thread(c.text[:60], user)
        if t["busy"]: raise HTTPException(409, "this conversation is busy")
        asyncio.create_task(S.turn(c.text, c.role, user, t["id"], c.context)); return {"ok": True, "thread": t["id"]}
    @app.get("/api/p/{pid}/threads")
    def threads(pid: str, user: str = U):
        S = W.get(pid); return sorted((S.thread_summary(t) for t in S.threads.values()), key=lambda t: -t["updated"])
    @app.post("/api/p/{pid}/threads")
    def new_thread(pid: str, nt: NewThread, user: str = U):
        S = W.get(pid); return S.thread_summary(S.new_thread(nt.title, user))
    @app.get("/api/p/{pid}/threads/{tid}")
    def thread(pid: str, tid: str, user: str = U):
        S = W.get(pid); t = S.threads.get(tid)
        if not t: raise HTTPException(404, "no such conversation")
        return {**S.thread_summary(t), "events": t["history"][-500:]}
    @app.delete("/api/p/{pid}/threads/{tid}")
    def del_thread(pid: str, tid: str, user: str = U):
        S = W.get(pid); t = S.threads.pop(tid, None)
        if t:
            p = os.path.join(S.thread_dir, tid + ".jsonl")
            if os.path.exists(p): os.remove(p)
        return {"ok": True}
    @app.post("/api/p/{pid}/interrupt")
    async def interrupt(pid: str, thread: str | None = None, user: str = U):
        S = W.get(pid)
        for t in S.threads.values():
            if t.get("client") and (thread is None or t["id"] == thread) and t["busy"]: await t["client"].interrupt()
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
