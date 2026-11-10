"""Model service storage on a database (phase 1 of the SaaS architecture).

Same interface as `store.Store` (load, save, check_patch, stage, list_patches, get_patch, approve, reject, provenance),
so every surface — web, agents, OSLC, forms — works unchanged. Storage is event-sourced:

  patches  (tenant, project, id, author, approver, rationale, sources, ops JSON, status, created, applied, rev)   append-only
  elements (tenant, project, kind, id, body JSON, rev, deleted)                                                     materialized view
  projects (tenant, id, name, meta JSON, rev)

`rev` is the project revision: each applied patch increments it. `load(rev)` folds the patch log up to `rev`, so
baselines and diffs are free. Two drivers: Postgres (psycopg, production, row-level security ready) and SQLite
(dev/test, same SQL). Pick with DATABASE_URL: postgresql://… or sqlite:///path.db.
"""
from __future__ import annotations
import copy, json, os, time
from dataclasses import asdict
from .store import Patch, Op
from . import schema

DDL = """
CREATE TABLE IF NOT EXISTS projects (tenant TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, meta TEXT NOT NULL DEFAULT '{}', program TEXT NOT NULL DEFAULT '{}', rev INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, PRIMARY KEY (tenant, id));
CREATE TABLE IF NOT EXISTS elements (tenant TEXT NOT NULL, project TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, rev INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (tenant, project, kind, id));
CREATE TABLE IF NOT EXISTS patches (tenant TEXT NOT NULL, project TEXT NOT NULL, id TEXT NOT NULL, author TEXT NOT NULL, approver TEXT, rationale TEXT NOT NULL, sources TEXT NOT NULL, ops TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL, applied REAL, rev INTEGER, PRIMARY KEY (tenant, project, id));
CREATE INDEX IF NOT EXISTS patches_proj ON patches (tenant, project, status, created);
CREATE TABLE IF NOT EXISTS baselines (tenant TEXT NOT NULL, project TEXT NOT NULL, name TEXT NOT NULL, rev INTEGER NOT NULL, created_by TEXT, created REAL NOT NULL, PRIMARY KEY (tenant, project, name));
"""

class DB:
    """Thin driver wrapper: one placeholder style, one connect, Postgres or SQLite."""
    def __init__(self, url: str):
        self.url = url; self.pg = url.startswith("postgres")
        if self.pg:
            import psycopg; self.psycopg = psycopg
        else:
            import sqlite3; self.sqlite3 = sqlite3; self.path = url.replace("sqlite:///", "")
        self.init()
    def connect(self):
        if self.pg: return self.psycopg.connect(self.url, autocommit=False)
        c = self.sqlite3.connect(self.path, timeout=30, isolation_level=None); c.execute("PRAGMA journal_mode=WAL"); c.execute("BEGIN"); return c
    def q(self, sql): return sql.replace("?", "%s") if self.pg else sql
    def init(self):
        with self.connect() as c:
            for stmt in DDL.strip().split(";"):
                if stmt.strip(): c.execute(stmt if not self.pg else stmt.replace("REAL", "DOUBLE PRECISION"))
            c.commit()
    def exec(self, c, sql, args=()): cur = c.cursor(); cur.execute(self.q(sql), args); return cur

class DbStore:
    def __init__(self, db: DB, tenant: str, project: str, name: str | None = None):
        self.db, self.tenant, self.project = db, tenant, project; self.root = f"{tenant}/{project}"   # root kept for callers that build paths
        with db.connect() as c:
            row = db.exec(c, "SELECT id FROM projects WHERE tenant=? AND id=?", (tenant, project)).fetchone()
            if not row: db.exec(c, "INSERT INTO projects (tenant,id,name,meta,program,rev,created) VALUES (?,?,?,?,?,0,?)", (tenant, project, name or project, json.dumps({"name": name or project, "method": "OOSEM"}), json.dumps({"lanes": []}), time.time()))
            c.commit()
        self.model_path = None; self.log_path = None

    # ---- model ----
    def rev(self) -> int:
        with self.db.connect() as c: return self.db.exec(c, "SELECT rev FROM projects WHERE tenant=? AND id=?", (self.tenant, self.project)).fetchone()[0]

    def load(self, rev: int | None = None) -> dict:
        with self.db.connect() as c:
            pr = self.db.exec(c, "SELECT name, meta, program, rev FROM projects WHERE tenant=? AND id=?", (self.tenant, self.project)).fetchone()
            m = schema.empty_model(pr[0]); m["meta"] = json.loads(pr[1]); m["program"] = json.loads(pr[2]); m["meta"]["rev"] = pr[3]
            if rev is None or rev >= pr[3]:
                for kind, eid, body in self.db.exec(c, "SELECT kind,id,body FROM elements WHERE tenant=? AND project=? AND deleted=0 ORDER BY kind, id", (self.tenant, self.project)):
                    m.setdefault(kind, {})[eid] = json.loads(body)
            else:   # fold the log up to rev (baseline / history read)
                m["meta"]["rev"] = rev
                for (ops,) in self.db.exec(c, "SELECT ops FROM patches WHERE tenant=? AND project=? AND status='applied' AND rev<=? ORDER BY rev", (self.tenant, self.project, rev)):
                    m = self.apply_ops(m, [Op(**o) for o in json.loads(ops)])
        return schema.with_defaults(m)

    def save(self, model: dict) -> None:
        """Full-model write (imports, migrations, seeding). Recorded as one 'import' patch so provenance stays complete."""
        cur = self.load(); ops = []
        for kind in schema.KINDS:
            for eid, v in model.get(kind, {}).items():
                if eid not in cur.get(kind, {}): ops.append(Op("add", kind, eid, v))
                elif cur[kind][eid] != v: ops.append(Op("update", kind, eid, v))
            for eid in cur.get(kind, {}):
                if eid not in model.get(kind, {}): ops.append(Op("remove", kind, eid))
        p = Patch(ops=ops, author="system:import", rationale="full model write", sources=[])
        with self.db.connect() as c:
            self.db.exec(c, "UPDATE projects SET name=?, meta=?, program=? WHERE tenant=? AND id=?", (model.get("meta", {}).get("name", self.project), json.dumps({k: v for k, v in model.get("meta", {}).items() if k != "rev"}), json.dumps(model.get("program", {"lanes": []})), self.tenant, self.project))
            c.commit()
        if ops: self._apply(p, approver="system")

    # ---- patches ----
    def apply_ops(self, model: dict, ops: list[Op]) -> dict:
        m = copy.deepcopy(model)
        for o in ops:
            coll = m.setdefault(o.kind, {})
            if o.op == "add":
                if o.id in coll: raise ValueError(f"{o.kind}.{o.id} already exists (use update)")
                coll[o.id] = dict(o.value or {})
            elif o.op == "update":
                if o.id not in coll: raise ValueError(f"{o.kind}.{o.id} does not exist (use add)")
                coll[o.id].update(o.value or {})
            elif o.op == "remove": coll.pop(o.id, None)
            else: raise ValueError(f"unknown op {o.op}")
        return schema.with_defaults(m)

    def check_patch(self, model: dict, patch: Patch):
        new = self.apply_ops(model, patch.ops); return new, schema.validate(new)

    def stage(self, patch: Patch) -> str:
        with self.db.connect() as c:
            self.db.exec(c, "DELETE FROM patches WHERE tenant=? AND project=? AND id=?", (self.tenant, self.project, patch.id))
            self.db.exec(c, "INSERT INTO patches (tenant,project,id,author,approver,rationale,sources,ops,status,created) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (self.tenant, self.project, patch.id, patch.author, None, patch.rationale, json.dumps(patch.sources), json.dumps([asdict(o) for o in patch.ops], ensure_ascii=False), patch.status, patch.created))
            c.commit()
        return patch.id

    def _row_to_patch(self, r) -> Patch:
        return Patch(ops=[Op(**o) for o in json.loads(r[5])], author=r[1], rationale=r[3], sources=json.loads(r[4]), id=r[0], created=r[7], status=r[6])

    def list_patches(self, status: str | None = None) -> list[Patch]:
        with self.db.connect() as c:
            sql = "SELECT id,author,approver,rationale,sources,ops,status,created FROM patches WHERE tenant=? AND project=?" + (" AND status=?" if status else "") + " ORDER BY created"
            return [self._row_to_patch(r) for r in self.db.exec(c, sql, (self.tenant, self.project) + ((status,) if status else ()))]

    def get_patch(self, pid: str) -> Patch:
        with self.db.connect() as c:
            r = self.db.exec(c, "SELECT id,author,approver,rationale,sources,ops,status,created FROM patches WHERE tenant=? AND project=? AND id=?", (self.tenant, self.project, pid)).fetchone()
        if not r: raise FileNotFoundError(pid)
        return self._row_to_patch(r)

    def approve(self, pid: str, approver: str = "human") -> dict:
        patch = self.get_patch(pid)
        if patch.status != "staged": raise ValueError(f"patch is {patch.status}")
        return self._apply(patch, approver)

    def _apply(self, patch: Patch, approver: str) -> dict:
        model = self.load(); new, issues = self.check_patch(model, patch)
        errs = [i for i in issues if i.level == "error"]
        if errs: raise ValueError("patch would break the model: " + "; ".join(f"{i.where}: {i.msg}" for i in errs[:10]))
        with self.db.connect() as c:
            # serialize writers per project: bump rev with an optimistic check
            cur_rev = self.db.exec(c, "SELECT rev FROM projects WHERE tenant=? AND id=?", (self.tenant, self.project)).fetchone()[0]
            if cur_rev != model["meta"].get("rev", cur_rev): raise ValueError("model changed during approval; retry")
            rev = cur_rev + 1
            for o in patch.ops:
                if o.op == "remove":
                    self.db.exec(c, "UPDATE elements SET deleted=1, rev=? WHERE tenant=? AND project=? AND kind=? AND id=?", (rev, self.tenant, self.project, o.kind, o.id))
                else:
                    body = json.dumps(new[o.kind][o.id], ensure_ascii=False)
                    self.db.exec(c, "DELETE FROM elements WHERE tenant=? AND project=? AND kind=? AND id=?", (self.tenant, self.project, o.kind, o.id))
                    self.db.exec(c, "INSERT INTO elements (tenant,project,kind,id,body,rev,deleted) VALUES (?,?,?,?,?,?,0)", (self.tenant, self.project, o.kind, o.id, body, rev))
            self.db.exec(c, "DELETE FROM patches WHERE tenant=? AND project=? AND id=?", (self.tenant, self.project, patch.id))
            self.db.exec(c, "INSERT INTO patches (tenant,project,id,author,approver,rationale,sources,ops,status,created,applied,rev) VALUES (?,?,?,?,?,?,?,?,'applied',?,?,?)",
                         (self.tenant, self.project, patch.id, patch.author, approver, patch.rationale, json.dumps(patch.sources), json.dumps([asdict(o) for o in patch.ops], ensure_ascii=False), patch.created, time.time(), rev))
            self.db.exec(c, "UPDATE projects SET rev=? WHERE tenant=? AND id=?", (rev, self.tenant, self.project))
            c.commit()
        new["meta"]["rev"] = rev; return new

    def reject(self, pid: str) -> None:
        with self.db.connect() as c:
            self.db.exec(c, "UPDATE patches SET status='rejected' WHERE tenant=? AND project=? AND id=? AND status='staged'", (self.tenant, self.project, pid)); c.commit()

    def provenance(self, kind: str, eid: str) -> list[dict]:
        out = []
        with self.db.connect() as c:
            for r in self.db.exec(c, "SELECT id,author,approver,rationale,sources,ops,applied,rev FROM patches WHERE tenant=? AND project=? AND status='applied' ORDER BY rev DESC", (self.tenant, self.project)):
                ops = json.loads(r[5])
                mine = [o for o in ops if o["kind"] == kind and o["id"] == eid]
                if mine:
                    out.append({"ts": r[6], "patch": r[0], "author": r[1], "approver": r[2], "rationale": r[3], "sources": json.loads(r[4]), "ops": mine, "n_ops": len(ops), "rev": r[7]})
        return out

    # ---- history ----
    def baseline(self, name: str, user: str = "") -> int:
        rev = self.rev()
        with self.db.connect() as c:
            self.db.exec(c, "DELETE FROM baselines WHERE tenant=? AND project=? AND name=?", (self.tenant, self.project, name))
            self.db.exec(c, "INSERT INTO baselines (tenant,project,name,rev,created_by,created) VALUES (?,?,?,?,?,?)", (self.tenant, self.project, name, rev, user, time.time())); c.commit()
        return rev
    def baselines(self) -> list[dict]:
        with self.db.connect() as c: return [{"name": r[0], "rev": r[1], "created_by": r[2], "created": r[3]} for r in self.db.exec(c, "SELECT name,rev,created_by,created FROM baselines WHERE tenant=? AND project=? ORDER BY rev", (self.tenant, self.project))]
    def diff(self, rev_a: int, rev_b: int) -> dict:
        a, b = self.load(rev_a), self.load(rev_b); out = {"added": [], "removed": [], "changed": []}
        for kind in schema.KINDS:
            for eid in b.get(kind, {}):
                if eid not in a.get(kind, {}): out["added"].append(f"{kind}/{eid}")
                elif a[kind][eid] != b[kind][eid]: out["changed"].append({"id": f"{kind}/{eid}", "fields": sorted(k for k in set(a[kind][eid]) | set(b[kind][eid]) if a[kind][eid].get(k) != b[kind][eid].get(k))})
            for eid in a.get(kind, {}):
                if eid not in b.get(kind, {}): out["removed"].append(f"{kind}/{eid}")
        return out

def import_yaml_project(db: DB, tenant: str, project: str, root: str) -> DbStore:
    """Phase-1 migration: a YAML project becomes a DbStore whose first patch is the import; its staged/applied patch files are replayed."""
    from .store import Store
    fs = Store(root); m = fs.load(); st = DbStore(db, tenant, project, m["meta"].get("name", project)); st.save(m)
    for p in fs.list_patches():
        if p.status == "staged": st.stage(p)
    return st
