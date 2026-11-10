"""Detect the engineering toolchain on this machine so the agent knows what it can actually run."""
from __future__ import annotations
import shutil, importlib, platform

CLI_TOOLS = {
    # mechanical CAD
    "kicad-cli": "EDA: KiCad CLI (netlist/BOM/DRC/ERC/gerbers)",
    "FreeCAD": "MCAD: FreeCAD (STEP/FCStd, python scripting)",
    "freecadcmd": "MCAD: FreeCAD headless",
    "openscad": "MCAD: OpenSCAD",
    "blender": "Geometry/rendering: Blender",
    # simulation
    "omc": "Simulation: OpenModelica compiler (Modelica → FMU/results)",
    "ngspice": "Simulation: ngspice circuit simulator",
    "gmsh": "FEA: Gmsh mesher",
    "ccx": "FEA: CalculiX solver",
    "ElmerSolver": "FEA: Elmer",
    "simpleFoam": "CFD: OpenFOAM",
    "pyspice": "Simulation: PySpice",
    # firmware / software
    "arm-none-eabi-gcc": "Firmware: ARM GCC toolchain",
    "pio": "Firmware: PlatformIO",
    "idf.py": "Firmware: ESP-IDF",
    "west": "Firmware: Zephyr west",
    "openocd": "Firmware: OpenOCD debugger",
    "cmake": "Build: CMake", "make": "Build: make", "git": "VCS: git",
    # docs
    "pandoc": "Docs: pandoc (markdown → docx/pdf)",
    "mmdc": "Diagrams: Mermaid CLI",
    "node": "Runtime: node.js", "docker": "Containers: docker",
}
PY_MODULES = {
    "cadquery": "MCAD scripting: CadQuery (parametric B-rep, STEP/STL export)",
    "build123d": "MCAD scripting: build123d",
    "OCP": "MCAD kernel: OpenCascade python bindings",
    "trimesh": "Mesh: trimesh",
    "fmpy": "Simulation: FMPy (run FMUs)",
    "OMPython": "Simulation: OMPython (drive OpenModelica)",
    "pyvista": "Post-processing: PyVista",
    "scipy": "Numerics: SciPy", "numpy": "Numerics: NumPy", "pandas": "Data: pandas", "matplotlib": "Plots: matplotlib",
    "skidl": "EDA scripting: SKiDL (netlists in python)",
    "pcbnew": "EDA scripting: KiCad pcbnew python API",
    "PySpice": "Simulation: PySpice (ngspice binding)",
    "control": "Controls: python-control",
    "reliability": "Reliability: reliability (Weibull fitting, ALT)",
    "lifelines": "Reliability: lifelines (survival analysis)",
    "docx": "Docs: python-docx", "openpyxl": "Data: openpyxl (xlsx)",
}

def detect() -> dict:
    cli = {k: shutil.which(k) for k in CLI_TOOLS}
    py = {}
    for mod in PY_MODULES:
        try: importlib.import_module(mod); py[mod] = True
        except Exception: py[mod] = False
    return {"platform": platform.platform(), "cli": {k: v for k, v in cli.items() if v}, "cli_missing": [k for k, v in cli.items() if not v],
            "python": [k for k, v in py.items() if v], "python_missing": [k for k, v in py.items() if not v]}

def summary(d: dict | None = None) -> str:
    d = d or detect()
    lines = ["Available engineering tools on this machine:"]
    for k in d["cli"]: lines.append(f"  - {k}: {CLI_TOOLS[k]}")
    for k in d["python"]: lines.append(f"  - python:{k}: {PY_MODULES[k]}")
    if not d["cli"] and not d["python"]: lines.append("  (none detected)")
    lines.append("Not installed (do not call; offer to pip/apt install if the task needs one): " + ", ".join(d["cli_missing"][:12] + [f"python:{m}" for m in d["python_missing"][:8]]))
    return "\n".join(lines)
