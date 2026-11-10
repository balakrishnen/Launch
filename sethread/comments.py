"""Element comments (threads, @mentions, assignments) and per-user notifications. Stored as JSONL beside the project
(.sethread/comments.jsonl) and per data root (.notifications/<user>.jsonl); phase-2 moves both to the database."""
from __future__ import annotations
import json, os, re, time, uuid

def _path(root): d = os.path.join(root, ".sethread"); os.makedirs(d, exist_ok=True); return os.path.join(d, "comments.jsonl")
def _read(root): p = _path(root); return [json.loads(l) for l in open(p)] if os.path.exists(p) else []

def list_comments(root, element=None):
    rows = _read(root); res = {}
    for r in rows:
        if r.get("op") == "resolve": res[r["id"]] = r
    out = []
    for r in rows:
        if r.get("op") == "resolve": continue
        if element and r["element"] != element: continue
        out.append({**r, "resolved": r["id"] in res, "resolved_by": res.get(r["id"], {}).get("user")})
    return out

def add(root, element, user, text, parent=None, assign=None):
    rec = {"id": uuid.uuid4().hex[:8], "element": element, "user": user, "text": text, "parent": parent, "assign": assign, "ts": time.time(),
           "mentions": sorted({m[1:] for m in re.findall(r"@[\w.+-]+@[\w.-]+|@[\w.-]+", text)})}
    with open(_path(root), "a") as fh: fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec

def resolve(root, cid, user):
    with open(_path(root), "a") as fh: fh.write(json.dumps({"op": "resolve", "id": cid, "user": user, "ts": time.time()}) + "\n")
    return {"ok": True}

def _npath(data_root, user): d = os.path.join(data_root, ".notifications"); os.makedirs(d, exist_ok=True); return os.path.join(d, re.sub(r"[^\w.@-]", "_", user) + ".jsonl")
def notify(data_root, user, kind, text, link, project):
    with open(_npath(data_root, user), "a") as fh: fh.write(json.dumps({"id": uuid.uuid4().hex[:8], "kind": kind, "text": text, "link": link, "project": project, "ts": time.time(), "read": False}, ensure_ascii=False) + "\n")
def notifications_for(data_root, user):
    p = _npath(data_root, user)
    if not os.path.exists(p): return []
    rows = [json.loads(l) for l in open(p)]; reads = {r["id"] for r in rows if r.get("op") == "read"}; last_read = max([r["ts"] for r in rows if r.get("op") == "read_all"] or [0])
    return [{**r, "read": r["id"] in reads or r["ts"] <= last_read} for r in rows if not r.get("op")][-100:][::-1]
def mark_read(data_root, user):
    with open(_npath(data_root, user), "a") as fh: fh.write(json.dumps({"op": "read_all", "ts": time.time()}) + "\n")
