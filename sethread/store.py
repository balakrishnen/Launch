"""Model persistence and governed change: load/save YAML, patch proposals, provenance log.

Agents never write the model directly. They produce Patches; a Patch is validated against the
schema and referential integrity, staged under .sethread/patches/, and applied only on approval
(by a human, or by policy for low-risk kinds). Every applied patch is appended to the provenance log.
"""
from __future__ import annotations
import copy, fcntl, json, os, time, uuid
from dataclasses import dataclass, field, asdict
from typing import Any
import yaml
from . import schema

@dataclass
class Op:
    op: str            # add | update | remove
    kind: str          # collection name
    id: str
    value: dict | None = None   # for add/update (update merges fields)

@dataclass
class Patch:
    ops: list[Op]
    author: str                 # agent role or human
    rationale: str
    sources: list[str] = field(default_factory=list)   # documents / tool outputs the change is derived from
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    created: float = field(default_factory=time.time)
    status: str = "staged"      # staged | approved | rejected | applied

    def to_dict(self) -> dict:
        d = asdict(self); return d
    @staticmethod
    def from_dict(d: dict) -> "Patch":
        d = dict(d); d["ops"] = [Op(**o) for o in d["ops"]]; return Patch(**d)

class Store:
    def __init__(self, root: str):
        self.root = root
        self.model_path = os.path.join(root, "model.yaml")
        self.meta_dir = os.path.join(root, ".sethread")
        self.patch_dir = os.path.join(self.meta_dir, "patches")
        self.log_path = os.path.join(self.meta_dir, "provenance.jsonl")
        os.makedirs(self.patch_dir, exist_ok=True)

    # ---- model ----
    def load(self) -> dict:
        if not os.path.exists(self.model_path):
            return schema.empty_model(os.path.basename(os.path.abspath(self.root)))
        with open(self.model_path) as fh: m = yaml.safe_load(fh) or {}
        for k in schema.KINDS: m.setdefault(k, {})
        m.setdefault("meta", {}); m.setdefault("program", {"lanes": []})
        return schema.with_defaults(m)

    def save(self, model: dict) -> None:
        with open(os.path.join(self.root, ".sethread", ".lock"), "a+") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            self._save(model)
            fcntl.flock(lk, fcntl.LOCK_UN)

    def _save(self, model: dict) -> None:
        with open(self.model_path, "w") as fh:
            yaml.safe_dump(model, fh, sort_keys=False, allow_unicode=True, width=120)

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
            elif o.op == "remove":
                coll.pop(o.id, None)
            else:
                raise ValueError(f"unknown op {o.op}")
        return schema.with_defaults(m)

    def check_patch(self, model: dict, patch: Patch) -> tuple[dict, list[schema.Issue]]:
        new = self.apply_ops(model, patch.ops)
        return new, schema.validate(new)

    def stage(self, patch: Patch) -> str:
        p = os.path.join(self.patch_dir, f"{patch.id}.json")
        with open(p, "w") as fh: json.dump(patch.to_dict(), fh, indent=2, ensure_ascii=False)
        return p

    def list_patches(self, status: str | None = None) -> list[Patch]:
        out = []
        for fn in sorted(os.listdir(self.patch_dir)):
            if not fn.endswith(".json"): continue
            with open(os.path.join(self.patch_dir, fn)) as fh: p = Patch.from_dict(json.load(fh))
            if status is None or p.status == status: out.append(p)
        return out

    def get_patch(self, pid: str) -> Patch:
        with open(os.path.join(self.patch_dir, f"{pid}.json")) as fh: return Patch.from_dict(json.load(fh))

    def set_status(self, patch: Patch, status: str) -> None:
        patch.status = status; self.stage(patch)

    def approve(self, pid: str, approver: str = "human") -> dict:
        patch = self.get_patch(pid)
        model = self.load()
        new, issues = self.check_patch(model, patch)
        errs = [i for i in issues if i.level == "error"]
        if errs: raise ValueError("patch would break the model: " + "; ".join(f"{i.where}: {i.msg}" for i in errs[:10]))
        self.save(new); self.set_status(patch, "applied")
        with open(self.log_path, "a") as fh:
            fh.write(json.dumps(dict(ts=time.time(), patch=patch.id, author=patch.author, approver=approver, rationale=patch.rationale,
                                     sources=patch.sources, ops=[asdict(o) for o in patch.ops]), ensure_ascii=False) + "\n")
        return new

    def reject(self, pid: str) -> None:
        self.set_status(self.get_patch(pid), "rejected")

    def provenance(self, kind: str, eid: str) -> list[dict]:
        """Every applied patch that touched kind.eid, newest first."""
        if not os.path.exists(self.log_path): return []
        hits = []
        for line in open(self.log_path):
            rec = json.loads(line)
            if any(o["kind"] == kind and o["id"] == eid for o in rec["ops"]): hits.append(rec)
        return list(reversed(hits))
