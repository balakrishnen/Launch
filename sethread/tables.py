"""Ad-hoc tables — the spreadsheet replacement. A table is columns + rows stored in the model; formula columns are evaluated
here against the row and the model, so a cost rollup, a test tracker or an action list never leaves the digital thread.

Formula language (safe subset of Python expressions):
  row fields by key:        qty * unit_cost
  model lookups:            part(part_id).attrs.mass      el('parts', part_id, 'name')      ref(part_id)  (any kind by id)
  column aggregates:        sum('unit_cost') or sum(cols.unit_cost), avg(cols.qty), count(cols.status), min, max   — over the whole table
  helpers:                  if_(cond, a, b), round(x, n), len(x), str(x), float(x), int(x), days(date_a, date_b), today()
"""
from __future__ import annotations
import ast, datetime as _dt, math
from . import schema

class _El(dict):
    """dict with attribute access and a safe default for missing keys (so formulas never blow up on a blank cell)."""
    def __getattr__(self, k):
        v = self.get(k)
        return _wrap(v)
def _wrap(v):
    if isinstance(v, dict) and not isinstance(v, _El): return _El(v)
    return v if v is not None else ""

_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Attribute, ast.IfExp,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv, ast.USub, ast.UAdd, ast.And, ast.Or, ast.Not,
            ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Subscript, ast.Tuple, ast.List)

def _num(v):
    try: return float(v) if v not in ("", None) else 0.0
    except (TypeError, ValueError): return 0.0

def _env(m, rows, row):
    def find(eid):
        for k in schema.KINDS:
            if eid in m.get(k, {}): return _El({"id": eid, "kind": k, **m[k][eid]})
        return _El({})
    class _Cols:
        def __getattr__(self, k): return k
    col = lambda key: [r.get(str(key)) for r in rows]
    nums = lambda key: [_num(x) for x in col(key) if x not in ("", None)]
    def days(a, b):
        try: return (_dt.date.fromisoformat(str(b)) - _dt.date.fromisoformat(str(a))).days
        except Exception: return ""
    env = {"sum": lambda k: sum(nums(k)), "avg": lambda k: (sum(nums(k)) / len(nums(k))) if nums(k) else 0, "count": lambda k: len([x for x in col(k) if x not in ("", None)]),
           "min": lambda k: min(nums(k)) if nums(k) else 0, "max": lambda k: max(nums(k)) if nums(k) else 0,
           "part": lambda i: find(i), "ref": find, "el": lambda kind, i, f=None: (_wrap(m.get(kind, {}).get(i, {}).get(f)) if f else _El(m.get(kind, {}).get(i, {}))),
           "if_": lambda c, a, b: a if c else b, "round": round, "len": len, "str": str, "float": _num, "int": lambda x: int(_num(x)), "abs": abs, "math": math,
           "today": lambda: _dt.date.today().isoformat(), "days": days, "cols": _Cols(), "True": True, "False": False, "None": None}
    for k, v in row.items(): env[k] = _wrap(v)
    return env

def evaluate(expr: str, m, rows, row):
    try: tree = ast.parse(expr, mode="eval")
    except SyntaxError as e: return f"#SYNTAX {e.msg}"
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED): return f"#NOTALLOWED {type(node).__name__}"
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"): return "#NOTALLOWED private"
    try:
        v = eval(compile(tree, "<formula>", "eval"), {"__builtins__": {}}, _env(m, rows, row))
        if isinstance(v, float) and v.is_integer(): v = int(v)
        if isinstance(v, float): v = round(v, 4)
        return v
    except Exception as e: return f"#ERR {e}"

def render(m, tid: str) -> dict:
    """Table as a grid: headers, typed columns, rows with formulas evaluated, totals for numeric columns."""
    t = m["tables"][tid]; cols = t["columns"]; raw = t["rows"]
    # evaluate formulas on a first pass using raw rows (aggregates over raw numeric columns), then once more so formulas can use formula columns
    rows = [dict(r) for r in raw]
    for _ in range(2):
        for r in rows:
            for c in cols:
                if c.get("type") == "formula" and c.get("formula"): r[c["key"]] = evaluate(c["formula"], m, rows, r)
    totals = {}
    for c in cols:
        if c.get("type") in ("number", "formula"):
            vals = [_num(r.get(c["key"])) for r in rows if isinstance(r.get(c["key"]), (int, float))]
            if vals: totals[c["key"]] = round(sum(vals), 4)
    return {"id": tid, "name": t["name"], "description": t.get("description", ""), "columns": cols, "rows": rows, "totals": totals, "owner_team": t.get("owner_team"), "elements": t.get("elements", [])}

def from_sheet(headers: list[str], rows: list[list]) -> dict:
    """Columns + rows from a pasted/imported sheet: numeric-looking columns become number columns."""
    keys = [_key(h, i) for i, h in enumerate(headers)]
    out = [{k: (r[i] if i < len(r) else "") for i, k in enumerate(keys)} for r in rows if any(str(x).strip() for x in r)]
    cols = []
    for i, k in enumerate(keys):
        vals = [r[k] for r in out if str(r[k]).strip() != ""]
        typ = "number" if vals and all(_isnum(v) for v in vals) else "text"
        if typ == "number":
            for r in out:
                if str(r[k]).strip() != "": r[k] = float(r[k]) if "." in str(r[k]) else int(float(r[k]))
        cols.append({"key": k, "name": str(headers[i]), "type": typ})
    return {"columns": cols, "rows": out}

def _isnum(v):
    try: float(str(v).replace(",", "")); return True
    except ValueError: return False
def _key(h, i):
    k = "".join(ch if ch.isalnum() else "_" for ch in str(h).strip().lower()).strip("_") or f"c{i}"
    if k[0].isdigit(): k = "c_" + k
    return k
