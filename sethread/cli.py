"""sethread command line.

  sethread init <dir> --name "Product"          new project (model.yaml + docs/)
  sethread check [dir]                          validate + coverage report
  sethread eval [dir] [--min 80]                quality scorecard (CI gate)
  sethread derive [dir] <fmea|vm|cert|disc|gaps|trace>
  sethread build [dir] [--docx]                 sysml + views + docs (+ Word)
  sethread patches [dir] [--status staged]      list patches
  sethread approve|reject <dir> <patch-id>
  sethread show <dir> <patch-id>
  sethread sync pull <dir> <adapter> <path> [--parent P-X]
  sethread sync push <dir> <adapter> <path>
  sethread agent <dir> <stage|all> [--goal ...] [--auto-approve] [--model m]
  sethread serve-mcp <dir>                      expose the model tools as a stdio MCP server for other agents/IDEs
  sethread ui [dir] [--port 8765]               web app, one local project
  sethread serve --data <root> [--database URL]  multi-project, multi-user web service (SETHREAD_INVITE, SETHREAD_SECRET, DATABASE_URL)
  sethread import <dir…> --database URL        migrate YAML projects into the database
  sethread [chat] [dir] [--model m] [--auto] [--yolo]   interactive harness (default when no subcommand)
"""
from __future__ import annotations
import argparse, json, os, sys
from . import schema, derive, sysml, views, docs
from .store import Store

SUBS = {"ui","serve","import","eval","init","check","derive","build","patches","show","approve","reject","sync","agent","serve-mcp","chat"}

def _store(d): return Store(d or ".")

def cmd_init(a):
    from .agents.orchestrator import init_project
    init_project(a.dir, a.name, a.description or "", a.system)
    print(f"created {a.dir}/model.yaml and {a.dir}/docs/ — drop source documents (PRD, standards, BOMs) into docs/ and run `sethread agent {a.dir} needs`")

def cmd_check(a):
    st = _store(a.dir); m = st.load(); issues = schema.validate(m)
    for i in issues: print(f"{i.level:8} {i.where}: {i.msg}")
    rep = derive.coverage_report(m)
    print(json.dumps({k: (len(v) if hasattr(v, "__len__") and not isinstance(v, dict) else v) for k, v in rep.items()}, indent=1))
    sys.exit(1 if any(i.level == "error" for i in issues) or not rep["clean"] else 0)

def cmd_eval(a):
    """Quality scorecard; exit 1 below --min. Use in CI so a model cannot regress."""
    from . import quality
    st = _store(a.dir); sc = quality.scorecard(st.load(), st)
    print(json.dumps(sc if a.verbose else {k: sc[k] for k in ("overall", "grade", "dimensions", "gaps")}, indent=1, ensure_ascii=False))
    sys.exit(0 if sc["overall"] >= a.min else 1)

def cmd_derive(a):
    m = _store(a.dir).load()
    fn = {"fmea": derive.fmea, "vm": derive.verification_matrix, "cert": derive.certification_plan, "disc": derive.discipline_matrix,
          "gaps": derive.gaps_as_tasks, "trace": derive.trace, "screened": derive.screened, "unassessed": derive.unassessed}[a.what]
    print(json.dumps(fn(m), indent=1, ensure_ascii=False, default=str))

def cmd_build(a):
    st = _store(a.dir); m = st.load(); out = os.path.join(st.root, "out")
    for s in ("sysml", "views", "docs"): os.makedirs(os.path.join(out, s), exist_ok=True)
    files = sysml.emit(m, os.path.join(out, "sysml")); print(f"sysml: {len(files)} packages")
    done, failed = views.render_all(m, os.path.join(out, "views")); print(f"views: {len(done)} rendered" + (f", failed: {failed}" if failed else ""))
    md = docs.build(m, os.path.join(out, "docs")); print(f"docs: {md} ({os.path.getsize(md)//1024} KB)")
    if a.docx:
        from .docx_export import export
        name = (m["meta"].get("name", "System")).replace(" ", "_")
        print("docx:", export(md, os.path.join(out, f"{name}_System_Design_Documentation.docx")))

def cmd_patches(a):
    for p in _store(a.dir).list_patches(a.status):
        print(f"{p.id}  {p.status:8} {p.author:22} ops={len(p.ops):3}  {p.rationale[:90]}")

def cmd_show(a):
    p = _store(a.dir).get_patch(a.patch); print(json.dumps(p.to_dict(), indent=1, ensure_ascii=False, default=str))

def cmd_approve(a):
    st = _store(a.dir)
    for pid in a.patch:
        st.approve(pid, approver=a.by); print("applied", pid)
    rep = derive.coverage_report(st.load()); print("coverage clean:", rep["clean"])

def cmd_reject(a):
    st = _store(a.dir)
    for pid in a.patch: st.reject(pid); print("rejected", pid)

def cmd_sync(a):
    from . import adapters
    st = _store(a.dir); m = st.load(); cls = adapters.REGISTRY.get(a.adapter)
    if not cls: sys.exit(f"unknown adapter {a.adapter}; available: {list(adapters.REGISTRY)}")
    if a.direction == "pull":
        patch = cls().pull(m, a.path, **({"parent": a.parent} if a.parent else {}))
        new, issues = st.check_patch(m, patch); errs = [i for i in issues if i.level == "error"]
        if errs: sys.exit("\n".join(f"{i.where}: {i.msg}" for i in errs))
        st.stage(patch); print(f"staged {patch.id} ({len(patch.ops)} ops) — review with `sethread show`, then approve")
    else:
        print("written", cls().push(m, a.path))

def cmd_agent(a):
    from .agents import orchestrator as O, roles as R
    st = _store(a.dir); docs_dir = os.path.join(st.root, "docs")
    def ev(kind, s): print(("  ⚙ " + s) if kind == "tool" else s, flush=True)
    stages = R.ORDER if a.stage == "all" else [a.stage]
    for stg in stages:
        print(f"\n=== {R.ROLES[stg]['title']} ===")
        res = O.run_stage(st, stg, a.goal, docs_dir=docs_dir, model=a.model, max_turns=a.max_turns, on_event=ev)
        print(f"\n-- staged patches: {res.patches_staged}  tool calls: {res.tool_calls}  cost: {res.cost_usd}")
        print("-- coverage before:", json.dumps(res.coverage_before)); print("-- coverage after (if approved):", json.dumps(res.coverage_after))
        if res.patches_staged and a.auto_approve:
            for pid in res.patches_staged: st.approve(pid, approver="auto"); print("applied", pid)
        elif res.patches_staged or res.needs_human:
            print("stopping for human review: `sethread patches`, `sethread show <id>`, `sethread approve <dir> <id>`"); break

def cmd_serve_mcp(a):
    """Expose the model tools over stdio so Claude Code, Cursor or any MCP client can use the digital thread directly."""
    import anyio
    from .agents.tools import make_server
    from claude_agent_sdk import create_sdk_mcp_server  # noqa: F401 (same server object)
    st = _store(a.dir); server, names = make_server(st, docs_dir=os.path.join(st.root, "docs"), author="mcp-client")
    inst = server["instance"]
    from mcp.server.stdio import stdio_server
    async def main():
        async with stdio_server() as (r, w): await inst.run(r, w, inst.create_initialization_options())
    anyio.run(main)

def cmd_ui(a):
    from .web.server import main as ui
    ui(a.dir, a.port, a.model, not a.no_browser)

def cmd_mcp(a):
    """Organization-wide MCP server over stdio: every project, read tools in standard shape, proposals staged for review."""
    from .web.server import Workspace
    from . import mcp_server as MCPS
    W = Workspace(a.data, None, None, a.database or os.environ.get("DATABASE_URL"), a.tenant)
    MCPS.build(W, user_of=lambda: a.user).run("stdio")

def cmd_serve(a):
    from .web.server import main as ui
    ui(None, a.port, a.model, False, data_root=a.data, host=a.host, database_url=a.database, tenant=a.tenant)

def cmd_import(a):
    """Phase-1 migration: load YAML projects into the database as patch chains."""
    from .dbstore import DB, import_yaml_project
    db = DB(a.database or os.environ["DATABASE_URL"])
    for d in a.dirs:
        pid = os.path.basename(os.path.abspath(d)); st = import_yaml_project(db, a.tenant, pid, d); print(f"imported {d} → {a.tenant}/{pid} rev {st.rev()}")

def cmd_chat(a):
    from .harness.repl import main as chat
    chat(a.dir, a.model, a.auto, a.yolo)

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or (argv[0] not in SUBS and argv[0] not in ("-h", "--help") and (os.path.isdir(argv[0]) or argv[0].startswith("--"))): argv = ["chat"] + argv
    p = argparse.ArgumentParser(prog="sethread", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("init"); s.add_argument("dir"); s.add_argument("--name", required=True); s.add_argument("--description"); s.add_argument("--system", help="part id of the system of interest"); s.set_defaults(f=cmd_init)
    s = sp.add_parser("check"); s.add_argument("dir", nargs="?", default="."); s.set_defaults(f=cmd_check)
    s = sp.add_parser("eval"); s.add_argument("dir", nargs="?", default="."); s.add_argument("--min", type=int, default=0); s.add_argument("--verbose", action="store_true"); s.set_defaults(f=cmd_eval)
    s = sp.add_parser("derive"); s.add_argument("dir"); s.add_argument("what", choices=["fmea", "vm", "cert", "disc", "gaps", "trace", "screened", "unassessed"]); s.set_defaults(f=cmd_derive)
    s = sp.add_parser("build"); s.add_argument("dir", nargs="?", default="."); s.add_argument("--docx", action="store_true"); s.set_defaults(f=cmd_build)
    s = sp.add_parser("patches"); s.add_argument("dir", nargs="?", default="."); s.add_argument("--status"); s.set_defaults(f=cmd_patches)
    s = sp.add_parser("show"); s.add_argument("dir"); s.add_argument("patch"); s.set_defaults(f=cmd_show)
    s = sp.add_parser("approve"); s.add_argument("dir"); s.add_argument("patch", nargs="+"); s.add_argument("--by", default=os.environ.get("USER", "human")); s.set_defaults(f=cmd_approve)
    s = sp.add_parser("reject"); s.add_argument("dir"); s.add_argument("patch", nargs="+"); s.set_defaults(f=cmd_reject)
    s = sp.add_parser("sync"); s.add_argument("direction", choices=["pull", "push"]); s.add_argument("dir"); s.add_argument("adapter"); s.add_argument("path"); s.add_argument("--parent"); s.set_defaults(f=cmd_sync)
    s = sp.add_parser("agent"); s.add_argument("dir"); s.add_argument("stage"); s.add_argument("--goal"); s.add_argument("--model"); s.add_argument("--max-turns", type=int, default=40); s.add_argument("--auto-approve", action="store_true"); s.set_defaults(f=cmd_agent)
    s = sp.add_parser("chat"); s.add_argument("dir", nargs="?", default="."); s.add_argument("--model"); s.add_argument("--auto", action="store_true", help="auto-approve agent patches"); s.add_argument("--yolo", action="store_true", help="no permission prompts for shell/file writes"); s.set_defaults(f=cmd_chat)
    s = sp.add_parser("ui"); s.add_argument("dir", nargs="?", default="."); s.add_argument("--port", type=int, default=8765); s.add_argument("--model"); s.add_argument("--no-browser", action="store_true"); s.set_defaults(f=cmd_ui)
    s = sp.add_parser("serve"); s.add_argument("--data", required=True, help="directory holding one sub-directory per project (files; the model too unless --database)"); s.add_argument("--database", help="postgresql://… or sqlite:///… (default: env DATABASE_URL; unset = YAML files)"); s.add_argument("--tenant", default=os.environ.get("SETHREAD_TENANT", "default")); s.add_argument("--host", default="0.0.0.0"); s.add_argument("--port", type=int, default=8765); s.add_argument("--model"); s.set_defaults(f=cmd_serve)
    s = sp.add_parser("import"); s.add_argument("dirs", nargs="+"); s.add_argument("--database"); s.add_argument("--tenant", default=os.environ.get("SETHREAD_TENANT", "default")); s.set_defaults(f=cmd_import)
    s = sp.add_parser("serve-mcp"); s.add_argument("dir", nargs="?", default="."); s.set_defaults(f=cmd_serve_mcp)
    s = sp.add_parser("mcp", help="Launch as an MCP server over stdio for the whole organization (multi-project); for Claude Code / desktop configs"); s.add_argument("--data", required=True); s.add_argument("--database"); s.add_argument("--tenant", default=os.environ.get("SETHREAD_TENANT", "default")); s.add_argument("--user", default=os.environ.get("USER", "mcp")); s.set_defaults(f=cmd_mcp)
    a = p.parse_args(argv); a.f(a)

if __name__ == "__main__": main()
