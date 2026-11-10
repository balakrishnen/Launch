"""Runs OOSEM role agents over a project store with the Claude Agent SDK.

run_stage(store, stage, goal) -> RunResult   one role, one bounded job, patches staged for review
run_pipeline(store, stages, goal)            roles in OOSEM order; stops when a stage asks for a human decision
"""
from __future__ import annotations
import asyncio, dataclasses, json, os, time
from typing import Iterable
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock, ToolUseBlock
from ..store import Store
from .. import derive
from . import roles as R
from .tools import make_server

@dataclasses.dataclass
class RunResult:
    stage: str
    text: str
    patches_staged: list[str]
    tool_calls: int
    cost_usd: float | None
    coverage_before: dict
    coverage_after: dict
    needs_human: bool

def _cov(m):
    rep = derive.coverage_report(m)
    return {k: (len(v) if hasattr(v, "__len__") and not isinstance(v, dict) else v) for k, v in rep.items() if k != "counts"}

def build_prompt(store: Store, stage: str, goal: str | None) -> str:
    role = R.ROLES[stage]; m = store.load()
    cov = _cov(m)
    gaps = derive.gaps_as_tasks(m)[:25]
    return "\n".join([
        f"# Role: {role['title']}", role["prompt"], "",
        f"# Project: {m['meta'].get('name','(unnamed)')} — {m['meta'].get('description','')}",
        f"Collections you own: {', '.join(role['kinds']) or 'none (read-only review)'}",
        f"Current coverage: {json.dumps(cov)}",
        f"Top open gaps: {json.dumps(gaps, ensure_ascii=False)}",
        "", f"# Goal for this run\n{goal or 'Advance the stage to its exit criterion; stage patches in reviewable chunks (≤ 40 ops each).'}",
    ])

async def run_stage_async(store: Store, stage: str, goal: str | None = None, docs_dir: str | None = None,
                          model: str | None = None, max_turns: int = 40, extra_mcp: dict | None = None,
                          on_event=None) -> RunResult:
    if stage not in R.ROLES: raise ValueError(f"unknown stage {stage}; one of {R.ORDER}")
    before = _cov(store.load())
    staged0 = {p.id for p in store.list_patches("staged")}
    server, names = make_server(store, docs_dir=docs_dir, author=f"agent:{stage}")
    mcp = {"sethread": server, **(extra_mcp or {})}
    allowed = names + [f"mcp__{k}__*" for k in (extra_mcp or {})]
    opts = ClaudeAgentOptions(system_prompt=R.COMMON, mcp_servers=mcp, allowed_tools=allowed,
                              permission_mode="bypassPermissions", max_turns=max_turns, **({"model": model} if model else {}))
    text, calls, cost = [], 0, None
    async for msg in query(prompt=build_prompt(store, stage, goal), options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock): text.append(b.text); on_event and on_event("text", b.text)
                elif isinstance(b, ToolUseBlock): calls += 1; on_event and on_event("tool", b.name)
        elif isinstance(msg, ResultMessage):
            cost = getattr(msg, "total_cost_usd", None)
    staged = [p.id for p in store.list_patches("staged") if p.id not in staged0]
    full = "\n".join(text)
    needs_human = any(k in full.lower() for k in ("human decision", "need a decision", "needs a decision", "decision required"))
    return RunResult(stage, full, staged, calls, cost, before, _cov(store.load()), needs_human)

def run_stage(store: Store, stage: str, goal: str | None = None, **kw) -> RunResult:
    return asyncio.run(run_stage_async(store, stage, goal, **kw))

def run_pipeline(store: Store, stages: Iterable[str] | None = None, goal: str | None = None, auto_approve: bool = False, **kw) -> list[RunResult]:
    """Run stages in order. With auto_approve the staged patches of each stage are applied before the next stage
    (useful for bootstrapping an empty model); otherwise later stages see only the approved model and the run stops
    after the first stage that staged patches, so a human can review."""
    out = []
    for st in (stages or R.ORDER):
        res = run_stage(store, st, goal, **kw); out.append(res)
        if res.patches_staged and auto_approve:
            for pid in res.patches_staged: store.approve(pid, approver="auto")
        elif res.patches_staged or res.needs_human:
            break
    return out

def init_project(root: str, name: str, description: str = "", system: str | None = None) -> Store:
    from .. import schema
    st = Store(root); m = schema.empty_model(); m["meta"].update(name=name, description=description, method="OOSEM")
    if system: m["meta"]["system"] = system
    st.save(m); os.makedirs(os.path.join(root, "docs"), exist_ok=True); return st
