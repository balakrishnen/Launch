"""Native CAD — the agent's own hands, inside the thread. A part's geometry is build123d code (Python, OpenCascade kernel) kept
as a `cad_models` element; building it runs the code in a subprocess sandbox, exports STEP + STL + GLB-less JSON mesh for the
in-app viewer, measures mass/volume/bounding box, and checks them against the part's attrs/budgets and interface mating features.
Engineers who use SolidWorks take the STEP; small teams never need to leave."""
from __future__ import annotations
import json, os, subprocess, sys, tempfile, textwrap, time

RUNNER = r'''
import json, sys, math
from build123d import *
import build123d as b123d
__out = {}
ns = {"__name__": "cadmodel"}
code = open(sys.argv[1]).read()
exec(compile(code, "cadmodel", "exec"), ns)
part = ns.get("result") or ns.get("part")
if part is None:
    for v in ns.values():
        if isinstance(v, BuildPart): part = v.part; break
if part is None: raise SystemExit("define `result` (a build123d Part/Compound) in the model code")
if isinstance(part, BuildPart): part = part.part
out = sys.argv[2]
export_step(part, out + ".step"); export_stl(part, out + ".stl", tolerance=0.05)
bb = part.bounding_box(); dens = float(ns.get("density_g_cm3", 0) or 0)
vol_mm3 = float(part.volume); mass_g = vol_mm3 / 1000.0 * dens if dens else None
# viewer mesh: tessellate → flat arrays
verts, tris = part.tessellate(0.1, 0.5)
mesh = {"v": [round(c, 3) for p in verts for c in (p.X, p.Y, p.Z)], "i": [i for t in tris for i in t]}
json.dump(mesh, open(out + ".mesh.json", "w"))
faces = len(part.faces()); edges = len(part.edges())
json.dump({"volume_mm3": round(vol_mm3, 2), "mass_g": round(mass_g, 2) if mass_g is not None else None, "density_g_cm3": dens or None,
           "bbox_mm": [round(bb.size.X, 3), round(bb.size.Y, 3), round(bb.size.Z, 3)], "bbox_min": [round(bb.min.X, 3), round(bb.min.Y, 3), round(bb.min.Z, 3)],
           "faces": faces, "edges": edges, "tris": len(tris), "features": ns.get("features", []), "mates": ns.get("mates", {})}, open(out + ".meta.json", "w"))
'''

def build(code: str, out_dir: str, name: str, timeout: int = 120) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "model.py"); open(src, "w").write(code)
        runner = os.path.join(td, "run.py"); open(runner, "w").write(RUNNER)
        out = os.path.join(out_dir, name)
        try:
            r = subprocess.run([sys.executable, "-I", runner, src, out], capture_output=True, text=True, timeout=timeout, cwd=td, env={"PATH": os.environ.get("PATH", ""), "HOME": td, "PYTHONPATH": ""})
        except subprocess.TimeoutExpired: return {"ok": False, "error": f"timed out after {timeout}s"}
        if r.returncode != 0: return {"ok": False, "error": (r.stderr or r.stdout)[-2000:]}
    meta = json.load(open(out + ".meta.json"))
    return {"ok": True, **meta, "files": {"step": f"{name}.step", "stl": f"{name}.stl", "mesh": f"{name}.mesh.json"}}

def _num(x):
    try: return float(str(x).split()[0])
    except Exception: return None

def checks(m: dict, part_id: str, meta: dict) -> list[dict]:
    """geometry vs the thread: mass budget, envelope constraint, mating features for every interface, requirement attrs on mass/size."""
    p = m["parts"].get(part_id, {}); attrs = p.get("attrs") or {}; out = []
    bud = _num(attrs.get("mass_budget_g") or attrs.get("mass_g"))
    if bud is not None and meta.get("mass_g") is not None: out.append({"check": "mass vs budget", "ok": meta["mass_g"] <= bud, "measured": f"{meta['mass_g']} g", "limit": f"≤ {bud} g (attrs)"})
    env = attrs.get("envelope_mm")
    if env:
        try:
            lim = [float(x) for x in str(env).replace("×", "x").lower().split("x")]; bb = sorted(meta["bbox_mm"], reverse=True); lim = sorted(lim, reverse=True)
            out.append({"check": "envelope", "ok": all(a <= b + 1e-6 for a, b in zip(bb, lim)), "measured": "×".join(f"{x:g}" for x in meta["bbox_mm"]) + " mm", "limit": f"≤ {env} mm (attrs)"})
        except Exception: pass
    mates = meta.get("mates") or {}
    for i, v in m["interfaces"].items():
        if part_id in (v.get("a"), v.get("b")) and (v.get("kind") or "").lower().startswith("mech"):
            out.append({"check": f"mating feature for {i}", "ok": i in mates or (v.get("name") or "") in mates, "measured": mates.get(i, "—"), "limit": f"declare mates['{i}'] = <feature> in the model code"})
    for f, fv in m["functions"].items():
        if part_id in fv.get("alloc", []):
            for r in fv.get("reqs", []):
                a = (m["requirements"][r].get("attr") or "").lower()
                for key, val in (("mass", meta.get("mass_g")), ("volume", meta.get("volume_mm3"))):
                    if a.startswith(key) and val is not None:
                        import re
                        mm = re.match(r"\w+\s*(<=|>=|<|>|=)\s*([\d.]+)", a)
                        if mm:
                            op, lim = mm.group(1), float(mm.group(2)); ok = {"<=": val <= lim, "<": val < lim, ">=": val >= lim, ">": val > lim}.get(op, abs(val - lim) < 1e-6)
                            out.append({"check": f"{r} {key}", "ok": ok, "measured": f"{val:g}", "limit": a})
    return out

TEMPLATE = textwrap.dedent('''
    # build123d model for {pid} — {name}
    # Conventions: mm; define `result`; set density_g_cm3 for mass; list `features` (strings) and `mates` {{interface_id: feature}}.
    from build123d import *
    density_g_cm3 = 2.7   # e.g. aluminium; 1.2 for ABS/PC, 7.85 steel
    with BuildPart() as model:
        Box(60, 40, 12)
        with Locations((20, 10, 0), (-20, 10, 0)):
            Hole(3.4)   # M3 clearance
    result = model.part
    features = ["body 60x40x12", "2x M3 clearance holes"]
    mates = {{}}   # e.g. {{"IF-04": "4x M3 holes on 50x30 pattern"}}
''')
