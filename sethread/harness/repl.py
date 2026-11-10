"""Interactive terminal harness — `sethread` with no subcommand, or `sethread chat <dir>`.

One long-lived agent session over a project directory, Claude-Code style: the engineer types, the agent reads/writes files,
runs the toolchain, and proposes model patches; the harness streams tool activity, asks permission for shell/file writes,
and offers each staged patch for review (diff → approve/reject) after every turn. Slash commands give direct access to the
model without spending a model turn."""
from __future__ import annotations
import asyncio, json, os, sys, difflib, yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from claude_agent_sdk import (ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, ResultMessage, UserMessage, SystemMessage,
                              TextBlock, ToolUseBlock, ToolResultBlock, PermissionResultAllow, PermissionResultDeny)
from ..store import Store
from .. import derive, schema
from ..agents.tools import make_server
from .prompt import HARNESS
from . import toolchain

con = Console()
SAFE_TOOLS = {"Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch", "TodoWrite", "Task"}
BUILTIN = ["Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch", "TodoWrite"]

def _cov(m):
    rep = derive.coverage_report(m)
    return {k: (len(v) if hasattr(v, "__len__") and not isinstance(v, dict) else v) for k, v in rep.items() if k not in ("counts",)}

def patch_diff(store: Store, pid: str) -> str:
    p = store.get_patch(pid); m = store.load(); new, issues = store.check_patch(m, p); out = []
    for op in p.ops:
        old = m.get(op.kind, {}).get(op.id); nw = new.get(op.kind, {}).get(op.id)
        a = yaml.safe_dump(old, sort_keys=False, allow_unicode=True).splitlines() if old else []
        b = yaml.safe_dump(nw, sort_keys=False, allow_unicode=True).splitlines() if nw else []
        out.append(f"## {op.op} {op.kind}/{op.id}")
        out += list(difflib.unified_diff(a, b, lineterm="", n=2))[2:] or ["(no change)"]
    warn = [f"! {i.where}: {i.msg}" for i in issues if i.level == "warning"]
    return "\n".join(out + ([""] + warn if warn else []))

def show_patch(store: Store, pid: str):
    p = store.get_patch(pid)
    con.print(Panel(f"[bold]{pid}[/] · {p.author} · {len(p.ops)} ops\n[italic]{p.rationale}[/]\nsources: {', '.join(p.sources) or '—'}", title="staged patch", border_style="yellow"))
    con.print(Syntax(patch_diff(store, pid), "diff", theme="ansi_dark", word_wrap=True))

def review_patches(store: Store, session: PromptSession, only: list[str] | None = None) -> list[str]:
    applied = []
    for p in store.list_patches("staged"):
        if only and p.id not in only: continue
        show_patch(store, p.id)
        ans = session.prompt(f"approve {p.id}? [y]es / [n]o / [s]kip / [a]ll remaining: ").strip().lower()
        if ans in ("a", "all"):
            for q in store.list_patches("staged"):
                if not only or q.id in only:
                    try: store.approve(q.id); applied.append(q.id); con.print(f"[green]applied {q.id}[/]")
                    except ValueError as e: con.print(f"[red]{q.id}: {e}[/]")
            break
        if ans in ("y", "yes"):
            try: store.approve(p.id); applied.append(p.id); con.print(f"[green]applied {p.id}[/]")
            except ValueError as e: con.print(f"[red]{e}[/]")
        elif ans in ("n", "no"): store.reject(p.id); con.print(f"[red]rejected {p.id}[/]")
    if applied:
        rep = derive.coverage_report(store.load()); con.print(f"coverage after: {'[green]clean[/]' if rep['clean'] else '[yellow]gaps open[/]'}  {json.dumps({k: v for k, v in _cov(store.load()).items() if k != 'clean'})}")
    return applied

def status_table(store: Store):
    m = store.load(); t = Table(title=f"{m['meta'].get('name','(unnamed)')} — model status", show_lines=False)
    t.add_column("collection"); t.add_column("n", justify="right"); t.add_column("collection"); t.add_column("n", justify="right")
    ks = list(schema.KINDS); half = (len(ks) + 1) // 2
    for i in range(half):
        a = ks[i]; b = ks[i + half] if i + half < len(ks) else ""
        t.add_row(a, str(len(m[a])), b, str(len(m[b])) if b else "")
    con.print(t); cov = _cov(m)
    con.print(("[green]trace clean[/] " if cov.pop("clean") else "[yellow]gaps open[/] ") + json.dumps(cov))

HELP = """[bold]slash commands[/] (no model turn)
 /status            counts + coverage          /gaps [n]         ranked open gaps
 /patches           staged patches             /review [id...]   diff + approve/reject
 /show <id>         diff of one patch          /approve <id..>   /reject <id..>
 /fmea [n]          unassessed FM candidates   /derive <fmea|vm|cert|disc|trace|screened>
 /build [--docx]    sysml + views + docs       /sync pull|push <adapter> <path> [--parent P-X]
 /stage <role>      run one OOSEM role agent (needs|requirements|logical|physical|analysis|risk|verification|reviewer)
 /tools             detected toolchain         /model <name>     switch model     /auto on|off  auto-approve agent patches
 /help  /quit
anything else is sent to the agent. It can read/write files in this directory, run the shell (asks first), and propose model patches."""

class Harness:
    def __init__(self, root: str, model: str | None = None, auto: bool = False, yolo: bool = False):
        self.store = Store(root); self.root = os.path.abspath(root); self.auto = auto; self.yolo = yolo
        self.docs_dir = os.path.join(self.root, "docs"); os.makedirs(self.docs_dir, exist_ok=True)
        self.session = PromptSession(history=FileHistory(os.path.join(self.root, ".sethread", "history")))
        self.server, self.names = make_server(self.store, docs_dir=self.docs_dir, author="agent:harness")
        self.tc = toolchain.detect(); self.model = model
        sp = HARNESS + "\n\n# Toolchain\n" + toolchain.summary(self.tc) + f"\n\n# Project root\n{self.root} (model.yaml, docs/, mech/, elec/, fw/, sim/, test/)"
        self.opts = ClaudeAgentOptions(system_prompt=sp, mcp_servers={"sethread": self.server}, tools=BUILTIN, allowed_tools=self.names + sorted(SAFE_TOOLS),
                                       cwd=self.root, permission_mode="default", can_use_tool=self.can_use_tool, max_turns=60,
                                       **({"model": model} if model else {}))
        self.client: ClaudeSDKClient | None = None

    async def can_use_tool(self, name, inp, ctx):
        if self.yolo or name in SAFE_TOOLS or name.startswith("mcp__sethread__"): return PermissionResultAllow()
        desc = inp.get("command") or inp.get("file_path") or json.dumps(inp)[:200]
        con.print(Panel(str(desc)[:800], title=f"[bold]{name}[/] wants to run", border_style="magenta"))
        ans = (await asyncio.to_thread(self.session.prompt, "allow? [y]es / [n]o / [A]lways this session: ")).strip()
        if ans == "A": self.yolo = True; return PermissionResultAllow()
        if ans.lower() in ("y", "yes"): return PermissionResultAllow()
        return PermissionResultDeny(message="engineer declined")

    async def turn(self, text: str):
        staged0 = {p.id for p in self.store.list_patches("staged")}
        await self.client.query(text)
        async for msg in self.client.receive_response():
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock) and b.text.strip(): con.print(Markdown(b.text))
                    elif isinstance(b, ToolUseBlock):
                        arg = b.input.get("command") or b.input.get("file_path") or b.input.get("kind") or b.input.get("name") or b.input.get("adapter") or ""
                        con.print(f"  [dim]⚙ {b.name.replace('mcp__sethread__','model.')}[/] [dim cyan]{str(arg)[:100]}[/]")
            elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
                for b in msg.content:
                    if isinstance(b, ToolResultBlock) and b.is_error: con.print(f"  [red]✗ {str(b.content)[:200]}[/]")
            elif isinstance(msg, ResultMessage):
                con.print(f"[dim]turns {msg.num_turns} · {msg.duration_ms/1000:.0f}s" + (f" · ${msg.total_cost_usd:.3f}" if msg.total_cost_usd else "") + "[/]")
        new = [p.id for p in self.store.list_patches("staged") if p.id not in staged0]
        if new:
            if self.auto:
                for pid in new: self.store.approve(pid, approver="auto"); con.print(f"[green]auto-applied {pid}[/]")
            else:
                con.print(f"[yellow]{len(new)} patch(es) staged[/] — review now?")
                review_patches(self.store, self.session, new)

    def slash(self, line: str) -> bool:
        parts = line.split(); cmd, args = parts[0].lower(), parts[1:]
        st = self.store
        try:
            if cmd in ("/quit", "/exit", "/q"): return False
            elif cmd == "/help": con.print(HELP)
            elif cmd == "/status": status_table(st)
            elif cmd == "/gaps":
                for g in derive.gaps_as_tasks(st.load())[: int(args[0]) if args else 30]: con.print(f" · {g}")
            elif cmd == "/patches":
                for p in st.list_patches(args[0] if args else None): con.print(f" {p.id}  {p.status:8} {p.author:18} ops={len(p.ops):3}  {p.rationale[:80]}")
            elif cmd == "/review": review_patches(st, self.session, args or None)
            elif cmd == "/show": show_patch(st, args[0])
            elif cmd == "/approve":
                for pid in args: st.approve(pid); con.print(f"[green]applied {pid}[/]")
            elif cmd == "/reject":
                for pid in args: st.reject(pid); con.print(f"[red]rejected {pid}[/]")
            elif cmd == "/fmea":
                for u in derive.unassessed(st.load())[: int(args[0]) if args else 30]: con.print(f" · {u}")
            elif cmd == "/derive":
                fn = {"fmea": derive.fmea, "vm": derive.verification_matrix, "cert": derive.certification_plan, "disc": derive.discipline_matrix, "trace": derive.trace, "screened": derive.screened}[args[0]]
                con.print_json(json.dumps(fn(st.load()), default=str, ensure_ascii=False))
            elif cmd == "/build":
                from ..cli import cmd_build; import argparse
                cmd_build(argparse.Namespace(dir=self.root, docx="--docx" in args))
            elif cmd == "/sync":
                from ..cli import cmd_sync; import argparse
                parent = args[args.index("--parent") + 1] if "--parent" in args else None
                cmd_sync(argparse.Namespace(direction=args[0], dir=self.root, adapter=args[1], path=args[2], parent=parent))
            elif cmd == "/stage":
                from ..agents import orchestrator as O
                res = O.run_stage(st, args[0], " ".join(args[1:]) or None, docs_dir=self.docs_dir, model=self.model, on_event=lambda k, s: con.print(f"  [dim]⚙ {s}[/]" if k == "tool" else Markdown(s)))
                con.print(f"staged: {res.patches_staged}")
                if res.patches_staged: review_patches(st, self.session, res.patches_staged)
            elif cmd == "/tools": con.print(toolchain.summary(self.tc))
            elif cmd == "/auto": self.auto = (args[0] == "on") if args else not self.auto; con.print(f"auto-approve {'on' if self.auto else 'off'}")
            elif cmd == "/model":
                self.model = args[0]; asyncio.get_event_loop().run_until_complete(self.client.set_model(args[0])) if self.client else None; con.print(f"model → {args[0]}")
            else: con.print("[red]unknown command[/]  /help")
        except Exception as e: con.print(f"[red]{type(e).__name__}: {e}[/]")
        return True

    async def run(self):
        m = self.store.load()
        con.print(Panel(f"[bold]sethread[/] — agentic systems engineering for hardware\nproject: [cyan]{m['meta'].get('name','(unnamed)')}[/]  root: {self.root}\n"
                        f"tools: {', '.join(list(self.tc['cli'])[:8])}{' …' if len(self.tc['cli'])>8 else ''} · python: {', '.join(self.tc['python'][:8])}\n/help for commands · Ctrl-D to quit", border_style="cyan"))
        status_table(self.store)
        async with ClaudeSDKClient(self.opts) as client:
            self.client = client
            while True:
                try:
                    with patch_stdout(): line = await asyncio.to_thread(self.session.prompt, "\n› ")
                except (EOFError, KeyboardInterrupt): break
                line = line.strip()
                if not line: continue
                if line.startswith("/"):
                    if not self.slash(line): break
                    continue
                try: await self.turn(line)
                except KeyboardInterrupt: await client.interrupt(); con.print("[yellow]interrupted[/]")
                except Exception as e: con.print(f"[red]{type(e).__name__}: {e}[/]")
        con.print("bye")

def main(root: str = ".", model: str | None = None, auto: bool = False, yolo: bool = False):
    asyncio.run(Harness(root, model, auto, yolo).run())
