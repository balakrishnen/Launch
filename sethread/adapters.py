"""Tool adapters: map external engineering artifacts <-> model elements, as Patches (never direct writes).

Every adapter implements:
    name, discipline
    pull(model, source) -> Patch        import time, from the tool into the model (parts, attributes, interfaces, results)
    push(model, target) -> artifact     export model content to the tool (parameters, requirements, test plans)
    evaluate(model, **kw) -> results    run the tool (simulation, analysis) and return constraint evaluations

Adapters shipped here work on open file formats so they run without vendor licences:
    KiCadAdapter     EDA      KiCad netlist (.net, s-expression) -> electrical parts, nets -> interfaces
    BomCadAdapter    CAD      BOM CSV exported from any CAD (SolidWorks/Onshape/Fusion/Creo) -> mechanical parts with mass/material
    StepAdapter      CAD      STEP file -> part names only (assembly tree) via text scan
    FmuAdapter       SIM      FMI 2.0/3.0 FMU (Modelica, Simulink export) -> run via FMPy, evaluate constraints
    ModelicaAdapter  SIM      .mo parameter push: write requirement limits/constraint inputs into a parameter record
    AlmAdapter       ALM/PLM  ReqIF-lite CSV/JSON (Jama, Codebeamer, DOORS exports) <-> requirements
    TestResultsAdapter TEST   results CSV/JSON (TestRUNS, LabVIEW, pytest) -> test status; flags failed verification
    McpToolAdapter   any      wraps an MCP server the agent can call (CAD, EDA or sim vendors that expose one)

Commercial APIs (Onshape REST, Fusion 360, Altium 365, Jama REST, Codebeamer REST) plug in as subclasses of the
same three methods; stubs with the endpoint shapes are at the bottom.
"""
from __future__ import annotations
import csv, json, os, re, time
from typing import Any
from .store import Patch, Op

def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").upper()

class Adapter:
    name = "base"; discipline = "system"
    def pull(self, model: dict, source: str, **kw) -> Patch: raise NotImplementedError
    def push(self, model: dict, target: str, **kw) -> str: raise NotImplementedError
    def evaluate(self, model: dict, **kw) -> dict: raise NotImplementedError

# ----------------------------------------------------------------------------- EDA: KiCad netlist
class KiCadAdapter(Adapter):
    name = "kicad"; discipline = "electrical"
    _comp = re.compile(r'\(comp \(ref "?([^")\s]+)"?\)(.*?)\(value "?([^")]+)"?\)', re.S)
    _net = re.compile(r'\(net \(code "?\d+"?\) \(name "?([^")]+)"?\)(.*?)\)\s*\)', re.S)
    _node = re.compile(r'\(node \(ref "?([^")\s]+)"?\)')

    def pull(self, model: dict, source: str, parent: str = "P-PCBA", **kw) -> Patch:
        txt = open(source).read(); ops = []
        if parent not in model["parts"]:
            ops.append(Op("add", "parts", parent, dict(name=os.path.basename(source).split(".")[0], type="PCBA", parent=None, discipline="electrical", attrs={})))
        for ref, _, val in self._comp.findall(txt):
            pid = f"P-{_slug(ref)}"
            el = dict(name=ref, type=val, parent=parent, discipline="electrical", attrs={"source": os.path.basename(source)})
            ops.append(Op("update" if pid in model["parts"] else "add", "parts", pid, el))
        # nets with >1 component become electrical interfaces between the first two refs (others listed in items)
        for net, body in self._net.findall(txt):
            refs = sorted(set(self._node.findall(body)))
            if len(refs) < 2 or net.startswith("unconnected"): continue
            iid = f"IF-NET-{_slug(net)}"[:40]
            ops.append(Op("update" if iid in model["interfaces"] else "add", "interfaces", iid,
                          dict(name=f"net {net}", a=f"P-{_slug(refs[0])}", b=f"P-{_slug(refs[1])}", items=[f"net {net}"] + [f"P-{_slug(r)}" for r in refs[2:]], kind="electrical", funcs=[])))
        return Patch(ops=ops, author="adapter:kicad", rationale=f"Imported components and nets from {os.path.basename(source)}", sources=[source])

    def push(self, model: dict, target: str, **kw) -> str:
        """Export electrical requirements and interface specs as a design-rule note the EE pastes into the schematic."""
        lines = ["# Electrical design constraints from the system model"]
        for rid, r in model["requirements"].items():
            if any(model["parts"].get(p, {}).get("discipline") == "electrical" for f in model["functions"].values() if rid in f["reqs"] for p in f["alloc"]):
                lines.append(f"- {rid} [{r['type']}] {r['text']}")
        open(target, "w").write("\n".join(lines)); return target

# ----------------------------------------------------------------------------- CAD: BOM CSV and STEP
class BomCadAdapter(Adapter):
    name = "cad-bom"; discipline = "mechanical"
    def pull(self, model: dict, source: str, parent: str | None = None, **kw) -> Patch:
        ops = []
        with open(source, newline="") as fh:
            for row in csv.DictReader(fh):
                name = row.get("Part Number") or row.get("Name") or row.get("Description")
                if not name: continue
                pid = f"P-{_slug(name)}"[:40]
                attrs = {k: v for k, v in row.items() if k and v and k.lower() in ("material", "mass", "mass (g)", "quantity", "qty", "description", "supplier", "finish", "revision")}
                attrs["source"] = os.path.basename(source)
                el = dict(name=name, type=row.get("Description") or "MechanicalPart", parent=parent or row.get("Parent") or None, discipline="mechanical", attrs=attrs)
                ops.append(Op("update" if pid in model["parts"] else "add", "parts", pid, el))
        return Patch(ops=ops, author="adapter:cad-bom", rationale=f"Imported mechanical BOM from {os.path.basename(source)}", sources=[source])

    def push(self, model: dict, target: str, **kw) -> str:
        """Export mechanical requirements (drop, ingress, thermal, mass) as a CAD design-requirements sheet."""
        rows = [("Requirement", "Type", "Text", "Verified by")]
        for rid, r in model["requirements"].items():
            if r["type"] in ("ENV", "SAFE", "IFACE") or "mechanical" in str(kw.get("disciplines", "mechanical")):
                rows.append((rid, r["type"], r["text"], ", ".join(r["tests"])))
        with open(target, "w", newline="") as fh: csv.writer(fh).writerows(rows)
        return target

class StepAdapter(Adapter):
    name = "step"; discipline = "mechanical"
    _prod = re.compile(r"PRODUCT\('([^']+)'")
    def pull(self, model: dict, source: str, parent: str | None = None, **kw) -> Patch:
        names = sorted(set(self._prod.findall(open(source, errors="ignore").read())))
        ops = [Op("update" if f"P-{_slug(n)}"[:40] in model["parts"] else "add", "parts", f"P-{_slug(n)}"[:40],
                  dict(name=n, type="StepBody", parent=parent, discipline="mechanical", attrs={"source": os.path.basename(source)})) for n in names]
        return Patch(ops=ops, author="adapter:step", rationale=f"Imported assembly tree from {os.path.basename(source)}", sources=[source])

# ----------------------------------------------------------------------------- Simulation: FMU / Modelica
class FmuAdapter(Adapter):
    """Runs an FMU (exported from OpenModelica, Dymola, Simulink, …) and evaluates model constraints on the outputs."""
    name = "fmu"; discipline = "system"
    def evaluate(self, model: dict, fmu: str = "", stop_time: float = 10.0, inputs: dict | None = None, checks: dict | None = None, **kw) -> dict:
        """checks: {constraint_id: {"output": "T_scalp", "op": "<=", "limit": 41.0}}"""
        try:
            from fmpy import simulate_fmu
        except ImportError:
            return {"error": "fmpy not installed (pip install fmpy); returning dry-run", "checks": checks or {}}
        res = simulate_fmu(fmu, stop_time=stop_time, start_values=inputs or {})
        out = {}
        for cid, ck in (checks or {}).items():
            series = res[ck["output"]]; val = float(series.max() if ck.get("op", "<=") == "<=" else series.min())
            ok = (val <= ck["limit"]) if ck.get("op", "<=") == "<=" else (val >= ck["limit"])
            out[cid] = dict(output=ck["output"], value=val, limit=ck["limit"], op=ck.get("op", "<="), pass_=ok)
        return out

    def results_as_patch(self, model: dict, results: dict, test_id: str) -> Patch:
        ops = []
        for cid, r in results.items():
            if cid in model["constraints"]:
                ops.append(Op("update", "constraints", cid, {"inputs": model["constraints"][cid].get("inputs", []), "last_eval": r}))
        return Patch(ops=ops, author="adapter:fmu", rationale=f"Simulation results for {test_id}", sources=[f"fmu:{test_id}"])

class ModelicaAdapter(Adapter):
    """Pushes requirement limits and constraint inputs into a Modelica parameter record so the simulation model
    uses the same numbers as the system model."""
    name = "modelica"; discipline = "system"
    _num = re.compile(r"(-?\d+(?:\.\d+)?)")
    def push(self, model: dict, target: str, package: str = "SystemLimits", **kw) -> str:
        lines = [f"within;", f"record {package} \"Limits generated from the system model; do not edit by hand\"", "  extends Modelica.Icons.Record;"]
        for rid, r in model["requirements"].items():
            attr = r.get("attr", "")
            nums = self._num.findall(attr)
            if attr and nums:
                lines.append(f"  parameter Real {rid.replace('-', '_')} = {nums[-1]} \"{attr} | {r['text'][:60]}\";")
        for cid, c in model["constraints"].items():
            lines.append(f"  // {cid} {c['name']}: {c['formula']}")
        lines.append(f"end {package};")
        open(target, "w").write("\n".join(lines)); return target

# ----------------------------------------------------------------------------- ALM / PLM
class AlmAdapter(Adapter):
    """CSV/JSON requirement exchange in the shape Jama, Codebeamer and DOORS export (id, type, text, parent, verification)."""
    name = "alm"; discipline = "system"
    def pull(self, model: dict, source: str, **kw) -> Patch:
        ops = []
        rows = json.load(open(source)) if source.endswith(".json") else list(csv.DictReader(open(source, newline="")))
        for row in rows:
            rid = row.get("id") or row.get("ID"); text = row.get("text") or row.get("Text") or row.get("Description")
            if not rid or not text: continue
            el = dict(type=(row.get("type") or "FUNC").upper()[:5], text=text, verify=(row.get("verify") or "test").lower(), tests=[],
                      from_=[x for x in (row.get("from") or "").split(";") if x], regs=[], uc=[], attr=row.get("attr", ""))
            ops.append(Op("update" if rid in model["requirements"] else "add", "requirements", rid, el))
        return Patch(ops=ops, author="adapter:alm", rationale=f"Imported requirements from {os.path.basename(source)}", sources=[source])
    def push(self, model: dict, target: str, **kw) -> str:
        rows = [dict(id=rid, type=r["type"], text=r["text"], verify=r["verify"], tests=";".join(r["tests"]), from_=";".join(r["from_"]), regs=";".join(r["regs"])) for rid, r in model["requirements"].items()]
        with open(target, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        return target

# ----------------------------------------------------------------------------- Test platform
class TestResultsAdapter(Adapter):
    """Results export (TestRUNS, LabVIEW TestStand, pytest-json) -> test status on the model; failed verification raises a gap."""
    name = "test-results"; discipline = "manufacturing"
    def pull(self, model: dict, source: str, **kw) -> Patch:
        rows = json.load(open(source)) if source.endswith(".json") else list(csv.DictReader(open(source, newline="")))
        ops = []
        for row in rows:
            tid = row.get("test") or row.get("id"); status = (row.get("status") or row.get("result") or "").lower()
            if tid in model["tests"]:
                ops.append(Op("update", "tests", tid, {"status": status, "result_source": os.path.basename(source), "measured": row.get("measured", "")}))
        return Patch(ops=ops, author="adapter:test-results", rationale=f"Test results from {os.path.basename(source)}", sources=[source])
    def push(self, model: dict, target: str, **kw) -> str:
        """Export the verification matrix as a test plan the platform can import (one row per test with pass/fail)."""
        from .derive import verification_matrix
        rows = [dict(id=t["id"], name=t["name"], method=t["method"], gate=t["gate"], units=t["units"], passfail=t["passfail"], verifies=";".join(t["reqs"]), covers=";".join(t["fms"])) for t in verification_matrix(model)]
        with open(target, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        return target

# ----------------------------------------------------------------------------- Generic MCP tool
class McpToolAdapter(Adapter):
    """Configuration record for an external MCP server (vendor CAD/EDA/sim/PLM). The agent layer mounts it so role agents
    can call its tools directly; results come back as Patches through propose_patch."""
    name = "mcp"
    def __init__(self, server_name: str, config: dict, discipline: str = "system"):
        self.server_name = server_name; self.config = config; self.discipline = discipline
    def mcp_config(self) -> dict: return {self.server_name: self.config}

# ----------------------------------------------------------------------------- Vendor API stubs (shapes only)
class OnshapeAdapter(BomCadAdapter):
    """Onshape REST: GET /api/v6/assemblies/d/{did}/w/{wid}/e/{eid}/bom -> rows like BomCadAdapter expects."""
    name = "onshape"
    def pull(self, model, source, **kw): raise NotImplementedError("set ONSHAPE_ACCESS_KEY/SECRET and fetch BOM JSON, then BomCadAdapter.pull")

class JamaAdapter(AlmAdapter):
    """Jama REST: GET /rest/v1/items?project={id}&itemType={reqType} -> rows like AlmAdapter expects."""
    name = "jama"
    def pull(self, model, source, **kw): raise NotImplementedError("set JAMA_TOKEN and page /rest/v1/items, then AlmAdapter.pull")

# ----------------------------------------------------------------------------- OSLC consumer (DOORS Next, Jama, Polarion, Codebeamer, Windchill RV&S …)
class OslcRmAdapter(Adapter):
    """Pull requirements / test cases from any OSLC provider's query capability. source = query base URL (from the provider's
    ServiceProvider document), e.g. https://jazz.example.com/rm/views?oslc.query=true&projectURL=…  Auth via env
    OSLC_USER / OSLC_TOKEN (Basic) or OSLC_BEARER. Each imported element keeps its origin URI in attrs.oslc_uri so links
    survive round trips; re-pulling updates in place instead of duplicating."""
    name = "oslc"; discipline = "system"
    _jar = None
    def _opener(self):
        import urllib.request, http.cookiejar
        if self._jar is None: self._jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))
    def _auth_headers(self, url):
        """OSLC_AUTH = basic (default; Jama, Codebeamer, Polarion) | bearer | oauth2-client (Jama OAuth2 client credentials:
        OSLC_TOKEN_URL, OSLC_CLIENT_ID, OSLC_CLIENT_SECRET) | jazz (DOORS Next / ELM form login j_security_check with OSLC_USER/OSLC_TOKEN)."""
        import os, base64, urllib.request, urllib.parse, json as _json
        mode = os.environ.get("OSLC_AUTH", "bearer" if os.environ.get("OSLC_BEARER") else "basic"); h = {}
        if mode == "bearer": h["Authorization"] = "Bearer " + os.environ["OSLC_BEARER"]
        elif mode == "oauth2-client":
            if not getattr(self, "_bearer", None):
                data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
                req = urllib.request.Request(os.environ["OSLC_TOKEN_URL"], data=data, headers={"Authorization": "Basic " + base64.b64encode(f"{os.environ['OSLC_CLIENT_ID']}:{os.environ['OSLC_CLIENT_SECRET']}".encode()).decode()})
                with urllib.request.urlopen(req, timeout=30) as r: self._bearer = _json.loads(r.read())["access_token"]
            h["Authorization"] = "Bearer " + self._bearer
        elif mode == "jazz":
            if not getattr(self, "_jazz_ok", False):
                base = os.environ.get("OSLC_JAZZ_BASE") or url.split("/rm/")[0] + "/rm"
                op = self._opener(); op.open(base + "/authenticated/identity", timeout=30)   # sets JSESSIONID / asks for form auth
                data = urllib.parse.urlencode({"j_username": os.environ["OSLC_USER"], "j_password": os.environ["OSLC_TOKEN"]}).encode()
                op.open(urllib.request.Request(base + "/j_security_check", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=30); self._jazz_ok = True
        elif os.environ.get("OSLC_USER"): h["Authorization"] = "Basic " + base64.b64encode(f"{os.environ['OSLC_USER']}:{os.environ.get('OSLC_TOKEN','')}".encode()).decode()
        if os.environ.get("OSLC_CONFIG"): h["Configuration-Context"] = os.environ["OSLC_CONFIG"]   # DOORS Next global/local configuration URI
        return h
    def _fetch(self, url, accept="application/rdf+xml, application/ld+json;q=0.9, text/turtle;q=0.8"):
        import urllib.request, os
        req = urllib.request.Request(url, headers={"Accept": accept, "OSLC-Core-Version": os.environ.get("OSLC_VERSION", "2.0"), **self._auth_headers(url)})
        with self._opener().open(req, timeout=60) as r:
            body = r.read()
            if "x-com-ibm-team-repository-web-auth-msg" in r.headers and r.headers["x-com-ibm-team-repository-web-auth-msg"] == "authrequired": raise RuntimeError("DOORS Next: authentication required — set OSLC_AUTH=jazz with OSLC_USER/OSLC_TOKEN")
            return body, r.headers.get("content-type", "")
    def pull(self, model, source, kind="requirements", **kw):
        from rdflib import Graph, RDF, URIRef, Namespace
        from rdflib.namespace import DCTERMS
        OSLC = Namespace("http://open-services.net/ns/core#"); RM = Namespace("http://open-services.net/ns/rm#"); QM = Namespace("http://open-services.net/ns/qm#")
        body, ctype = self._fetch(source); g = Graph(); g.parse(data=body, format="turtle" if "turtle" in ctype else "xml" if "xml" in ctype else "json-ld")
        # follow oslc:nextPage (DOORS Next pages at 50 by default)
        from rdflib import Namespace as _NS; _O = _NS("http://open-services.net/ns/core#"); seen = {source}
        while True:
            nxt = next((str(o) for o in g.objects(None, _O.nextPage) if str(o) not in seen), None)
            if not nxt: break
            seen.add(nxt); b2, c2 = self._fetch(nxt); g.parse(data=b2, format="turtle" if "turtle" in c2 else "xml" if "xml" in c2 else "json-ld")
        existing = {v.get("attrs", {}).get("oslc_uri"): k for k, v in model[kind].items() if isinstance(v.get("attrs"), dict) and v.get("attrs", {}).get("oslc_uri")}
        rtype = RM.Requirement if kind == "requirements" else QM.TestCase; ops = []; n = len(model[kind])
        for s in set(g.subjects(RDF.type, rtype)):
            title = str(g.value(s, DCTERMS.title) or ""); desc = str(g.value(s, DCTERMS.description) or ""); ident = str(g.value(s, DCTERMS.identifier) or "")
            JRM = Namespace("http://jazz.net/ns/rm#"); prim = g.value(s, JRM.primaryText)
            if prim is not None and not desc: desc = re.sub(r"<[^>]+>", " ", str(prim)).strip()
            eid = existing.get(str(s))
            if not eid:
                n += 1; eid = (("R-" if kind == "requirements" else "T-") + (re.sub(r"[^A-Za-z0-9]", "", ident)[:8] or f"{n:03d}"))
                while eid in model[kind]: eid += "x"
            links = {"validated_by": [str(o) for o in g.objects(s, RM.validatedBy)], "satisfied_by": [str(o) for o in g.objects(s, RM.satisfiedBy)], "validates": [str(o) for o in g.objects(s, QM.validatesRequirement)]}
            attrs = {"oslc_uri": str(s), "oslc_identifier": ident, "oslc_links": {k: v for k, v in links.items() if v}, "imported": time.strftime("%Y-%m-%d")}
            if kind == "requirements": value = {"text": desc or title, "type": "FUNC", "verify": "test", "tests": [], "from_": [], "regs": [], "attr": "", "attrs": attrs}
            else: value = {"name": title or ident, "method": desc, "gate": "", "passfail": "", "attrs": attrs}
            ops.append(Op("update" if eid in model[kind] else "add", kind, eid, value))
        return Patch(ops=ops, author="adapter:oslc", rationale=f"OSLC pull of {len(ops)} {kind} from {source}", sources=[source])
    def push(self, model, target, kind="requirements", **kw):
        """POST elements without an oslc_uri to the provider's creation factory URL; returns count."""
        import os, urllib.request, json as _json, base64
        n = 0
        for eid, v in model[kind].items():
            if isinstance(v.get("attrs"), dict) and v["attrs"].get("oslc_uri"): continue
            doc = {"@context": {"dcterms": "http://purl.org/dc/terms/", "oslc_rm": "http://open-services.net/ns/rm#"}, "@type": "oslc_rm:Requirement" if kind == "requirements" else "oslc_qm:TestCase",
                   "dcterms:title": (v.get("name") or v.get("text", "")[:80]), "dcterms:description": v.get("text", v.get("method", "")), "dcterms:identifier": eid}
            req = urllib.request.Request(target, data=_json.dumps(doc).encode(), method="POST", headers={"Content-Type": "application/ld+json", "Accept": "application/ld+json", "OSLC-Core-Version": "3.0"})
            if os.environ.get("OSLC_USER"): req.add_header("Authorization", "Basic " + base64.b64encode(f"{os.environ['OSLC_USER']}:{os.environ.get('OSLC_TOKEN','')}".encode()).decode())
            with urllib.request.urlopen(req, timeout=60) as r: n += 1 if r.status in (200, 201) else 0
        return f"{n} {kind} created at {target}"

REGISTRY: dict[str, type[Adapter]] = {a.name: a for a in (KiCadAdapter, BomCadAdapter, StepAdapter, FmuAdapter, ModelicaAdapter, AlmAdapter, TestResultsAdapter, OnshapeAdapter, JamaAdapter, OslcRmAdapter)}
