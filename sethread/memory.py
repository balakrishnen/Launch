"""Graph memory: what the harness remembers about any element and hands to an agent before it answers.
Not a vector store — the model graph IS the memory. For an element we assemble: its record, its neighbourhood (upstream/downstream
with names), the decisions and rationale that produced it (applied patches touching it), comments and notes that mention it,
derived facts (failure modes, impact radius, test results, gate relevance) and the conversations that touched it.
recall(m, store, ids, threads) -> a compact text block the harness prepends to a turn, and a dict for the UI."""
from __future__ import annotations
import os, re, time
from . import derive as D
from . import comments as C

ID_RE = re.compile(r"\b(?:[A-Z]{1,5}-[A-Za-z0-9][\w.-]*|F\d{2}[a-z]?)\b")

def _kind_of(m, eid):
    from . import schema
    for k in schema.KINDS:
        if eid in m.get(k, {}): return k
    return None

def element_memory(m, store, eid: str, threads: list | None = None, data_root: str | None = None, pid: str = "") -> dict | None:
    kind = _kind_of(m, eid)
    if not kind: return None
    el = m[kind][eid]; name = el.get("name") or el.get("title") or str(el.get("text", ""))[:80]
    up, down = [], []
    for a, rel, b in D.trace(m):
        if b == eid: up.append({"id": a, "rel": rel, "name": _name(m, a)})
        if a == eid: down.append({"id": b, "rel": rel, "name": _name(m, b)})
    decisions = []
    try:
        for p in sorted(store.list_patches("applied"), key=lambda p: -(getattr(p, "applied", None) or p.created)):
            ops = [o for o in p.ops if o.id == eid]
            if ops: decisions.append({"ts": getattr(p, "applied", None) or p.created, "author": p.author, "rationale": p.rationale, "sources": p.sources, "ops": [o.op for o in ops]})
            if len(decisions) >= 12: break
    except Exception: pass
    cm = []
    try: cm = C.list_comments(getattr(store, "root", None) or os.path.dirname(getattr(store, "model_path", "") or "") or ".", eid)
    except Exception: pass
    notes = [{"id": n, "title": v["title"], "kind": v.get("kind")} for n, v in m.get("notes", {}).items() if eid in (v.get("elements") or []) or eid in v.get("body", "")]
    fms = [f for f in D.fmea(m) if f.get("element") == eid or eid in (f.get("parts") or [])][:12]
    runs = [{"id": r, "result": v["result"], "date": v["date"]} for r, v in m.get("test_runs", {}).items() if v["test"] == eid] if kind == "tests" else []
    rel_threads = [t for t in (threads or []) if eid in (t.get("title", "") + " " + t.get("last", ""))][:6]
    try: imp = D.impact(m, eid); radius = len(imp.get("affected", []))
    except Exception: radius = None
    return {"id": eid, "kind": kind, "name": name, "record": el, "upstream": up[:30], "downstream": down[:30], "decisions": decisions, "comments": cm[-10:], "notes": notes, "failure_modes": fms, "runs": runs, "threads": rel_threads, "impact_radius": radius}

def _name(m, eid):
    k = _kind_of(m, eid)
    if not k: return ""
    v = m[k][eid]; return (v.get("name") or v.get("title") or str(v.get("text", ""))[:60])

def recall_text(mem: dict) -> str:
    if not mem: return ""
    L = [f"## Memory: {mem['id']} ({mem['kind']}) — {mem['name']}"]
    rec = {k: v for k, v in mem["record"].items() if v not in ("", None, [], {})}
    L.append("record: " + "; ".join(f"{k}={v}" for k, v in list(rec.items())[:14]))
    if mem["upstream"]: L.append("upstream: " + "; ".join(f"{x['id']} ({x['rel']}) {x['name']}" for x in mem["upstream"][:12]))
    if mem["downstream"]: L.append("downstream: " + "; ".join(f"{x['id']} ({x['rel']}) {x['name']}" for x in mem["downstream"][:12]))
    if mem["decisions"]: L.append("decisions (latest first): " + " | ".join(f"{time.strftime('%Y-%m-%d', time.localtime(d['ts']))} {d['author']}: {d['rationale'][:120]}" for d in mem["decisions"][:6]))
    if mem["comments"]: L.append("comments: " + " | ".join(f"{c.get('user','')}: {c.get('text','')[:120]}" for c in mem["comments"][-5:]))
    if mem["notes"]: L.append("notes: " + ", ".join(f"{n['id']} {n['title']}" for n in mem["notes"]))
    if mem["failure_modes"]: L.append("failure modes: " + "; ".join(f"{f['id']} AP={f.get('AP')} {f.get('guide')}: {f.get('mode','')[:50]}" for f in mem["failure_modes"][:8]))
    if mem["runs"]: L.append("test results: " + ", ".join(f"{r['id']} {r['result']} {r['date']}" for r in mem["runs"]))
    if mem["impact_radius"] is not None: L.append(f"impact radius: {mem['impact_radius']} elements within 3 hops")
    if mem["threads"]: L.append("earlier conversations: " + "; ".join(t["title"][:60] for t in mem["threads"]))
    return "\n".join(L)

def recall_for_turn(m, store, text: str, context: dict | None, threads=None, limit=4) -> str:
    """ids mentioned in the message + the element on screen → memory blocks (bounded)."""
    ids = []
    if context and context.get("element"): ids.append(context["element"])
    ids += [i for i in ID_RE.findall(text or "") if i not in ids]
    out = []
    for eid in ids[:limit]:
        mem = element_memory(m, store, eid, threads)
        if mem: out.append(recall_text(mem))
    return "\n\n".join(out)
