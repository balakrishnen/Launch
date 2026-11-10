"""Test execution & data: parse a run's data file (CSV/TSV time series or tabular), compute per-channel metrics, check limits,
decide pass/fail and keep a downsampled series for the in-app chart. Limits come from the test's requirement attributes
('pedal_latency <= 50 ms' → channel pedal_latency, op <=, 50) or from explicit limits on the run ({channel: 'op value'})."""
from __future__ import annotations
import csv, io, math, re, statistics

LIMIT_RE = re.compile(r"^\s*([A-Za-z_][\w.]*)\s*(<=|>=|==|=|<|>)\s*(-?[\d.]+)\s*([^\s]*)")

def parse(text: str) -> dict:
    """{'columns': [...], 'rows': [[...]], 'time': col name or None} from CSV/TSV; numeric columns parsed to float."""
    lines = [l for l in text.replace("\r", "").split("\n") if l.strip()]
    if not lines: return {"columns": [], "rows": [], "time": None}
    sep = "\t" if "\t" in lines[0] else (";" if lines[0].count(";") > lines[0].count(",") else ",")
    rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=sep))
    hdr = [h.strip() for h in rows[0]]; body = []
    for r in rows[1:]:
        out = []
        for x in r:
            x = x.strip()
            try: out.append(float(x))
            except ValueError: out.append(x)
        body.append(out)
    time_col = next((h for h in hdr if h.lower() in ("time", "t", "timestamp", "time_s", "seconds", "elapsed")), None)
    return {"columns": hdr, "rows": body, "time": time_col}

def metrics(d: dict) -> dict:
    """per numeric channel: n, min, max, mean, rms, p95, first, last, and (if a time column exists) duration and rise time 10→90 %."""
    cols = d["columns"]; out = {}
    ti = cols.index(d["time"]) if d["time"] in cols else None
    t = [r[ti] for r in d["rows"] if ti is not None and isinstance(r[ti], (int, float))] if ti is not None else []
    for i, c in enumerate(cols):
        if i == ti: continue
        v = [r[i] for r in d["rows"] if i < len(r) and isinstance(r[i], (int, float)) and not math.isnan(r[i])]
        if not v: continue
        sv = sorted(v); m = {"n": len(v), "min": round(min(v), 6), "max": round(max(v), 6), "mean": round(statistics.fmean(v), 6), "rms": round(math.sqrt(sum(x * x for x in v) / len(v)), 6),
                             "p95": round(sv[min(len(sv) - 1, int(0.95 * len(sv)))], 6), "first": v[0], "last": v[-1]}
        if len(v) > 1: m["std"] = round(statistics.pstdev(v), 6)
        if t and len(t) == len(v):
            m["duration"] = round(t[-1] - t[0], 6)
            lo, hi = v[0] + 0.1 * (v[-1] - v[0]), v[0] + 0.9 * (v[-1] - v[0])
            if v[-1] != v[0]:
                asc = v[-1] > v[0]
                t10 = next((tt for tt, x in zip(t, v) if (x >= lo if asc else x <= lo)), None); t90 = next((tt for tt, x in zip(t, v) if (x >= hi if asc else x <= hi)), None)
                if t10 is not None and t90 is not None: m["rise_10_90"] = round(t90 - t10, 6)
        out[c] = m
    return out

def parse_limit(s: str):
    mm = LIMIT_RE.match(str(s))
    if not mm: return None
    ch, op, val, unit = mm.groups(); return {"channel": ch, "op": "<=" if op == "=<" else op, "value": float(val), "unit": unit}

def check(mets: dict, limits: list[dict]) -> list[dict]:
    """Each limit against the channel's metric: for <=/< use max, for >=/> use min, for == use mean. Channel may be 'chan.metric'."""
    out = []
    for L in limits:
        ch = L["channel"]; metric = None
        if "." in ch and ch.split(".")[0] in mets: ch, metric = ch.split(".", 1)
        m = mets.get(ch)
        if not m: out.append({**L, "measured": None, "ok": None, "note": "channel not in data"}); continue
        metric = metric or {"<=": "max", "<": "max", ">=": "min", ">": "min"}.get(L["op"], "mean")
        x = m.get(metric)
        ok = {"<=": x <= L["value"], "<": x < L["value"], ">=": x >= L["value"], ">": x > L["value"]}.get(L["op"], abs(x - L["value"]) <= 1e-9 * max(1, abs(L["value"])))
        out.append({**L, "metric": metric, "measured": x, "ok": bool(ok)})
    return out

def series(d: dict, max_points: int = 1500) -> dict:
    """downsampled x/y per numeric channel for the chart (min/max bucket preserving)."""
    cols = d["columns"]; ti = cols.index(d["time"]) if d["time"] in cols else None
    n = len(d["rows"]); step = max(1, n // max_points); out = {"x": [], "channels": {}}
    idx = list(range(0, n, step))
    out["x"] = [d["rows"][i][ti] if ti is not None and isinstance(d["rows"][i][ti], (int, float)) else i for i in idx]
    for j, c in enumerate(cols):
        if j == ti: continue
        ys = []
        for i in idx:
            chunk = [r[j] for r in d["rows"][i:i + step] if j < len(r) and isinstance(r[j], (int, float))]
            ys.append(round(sum(chunk) / len(chunk), 6) if chunk else None)
        if any(y is not None for y in ys): out["channels"][c] = ys
    return out

def limits_for_test(m: dict, tid: str) -> list[dict]:
    """limits implied by the requirement attributes this test verifies"""
    out = []
    for r, rv in m["requirements"].items():
        if tid in rv.get("tests", []):
            L = parse_limit(rv.get("attr", ""))
            if L: out.append({**L, "requirement": r})
    return out
