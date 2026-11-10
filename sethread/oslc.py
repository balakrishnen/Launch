"""OSLC provider (Open Services for Lifecycle Collaboration, Core 3.0) for a Launch workspace.

Exposes the model as linked-data resources so DOORS Next, Jama, Polarion, Windchill, Teamcenter, Codebeamer and any other
OSLC consumer can discover, query, link to, preview and create elements — and so Launch can be the "RM/QM/AM provider"
in a customer's existing tool chain instead of yet another silo.

Domains and mapping
  OSLC RM  (oslc_rm:Requirement)       ← requirements (needs are oslc_rm:Requirement with dcterms:type "StakeholderNeed")
  OSLC QM  (oslc_qm:TestCase)          ← tests ; gates → oslc_qm:TestPlan
  OSLC AM  (oslc_am:Resource)          ← functions, logical_components, parts, interfaces, states, arch_decisions
  OSLC CM  (oslc_cm:ChangeRequest)     ← patches (staged/applied/rejected)
Links use the standard predicates: oslc_rm:validatedBy / oslc_qm:validatesRequirement, oslc_rm:satisfiedBy, oslc_rm:decomposedBy,
oslc_rm:elaboratedBy (need → requirement), oslc_am:… via dcterms:relation for allocation.

Discovery:  GET /oslc/catalog  →  ServiceProviderCatalog → ServiceProvider per project → Service per domain with
            QueryCapability, CreationFactory, selection/preview Dialogs and ResourceShapes.
Query:      oslc.where (= , !=, <, >, <=, >= on literal properties; `and`), oslc.select, oslc.searchTerms, oslc.paging/pageSize.
Formats:    application/ld+json (default), text/turtle, application/rdf+xml, application/json (compact); resource preview
            application/x-oslc-compact+xml and text/html small/large previews.
Auth:       HTTP Basic (email : api token from /api/token) or the app session cookie. Writes go through the same validated
            patch path as everything else (applied under the authenticated user; provenance logged).
"""
from __future__ import annotations
import base64, hmac, json, re, time, urllib.parse
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS, XSD
from rdflib.namespace import DCTERMS
from .store import Patch, Op
from . import schema, derive

OSLC = Namespace("http://open-services.net/ns/core#"); RM = Namespace("http://open-services.net/ns/rm#"); QM = Namespace("http://open-services.net/ns/qm#")
AM = Namespace("http://open-services.net/ns/am#"); CM = Namespace("http://open-services.net/ns/cm#"); LCH = Namespace("https://launch.twinmo.ai/ns/model#")
PREFIXES = {"oslc": OSLC, "oslc_rm": RM, "oslc_qm": QM, "oslc_am": AM, "oslc_cm": CM, "dcterms": DCTERMS, "rdf": RDF, "rdfs": RDFS, "launch": LCH}

RM_KINDS = {"requirements": RM.Requirement, "needs": RM.Requirement}
QM_KINDS = {"tests": QM.TestCase, "gates": QM.TestPlan}
AM_KINDS = {k: AM.Resource for k in ("functions", "logical_components", "logical_interfaces", "parts", "nodes", "interfaces", "states", "transitions", "arch_decisions", "constraints", "trades", "regulations", "stakeholders", "use_cases", "scenarios", "actors", "moes")}
ALL_KINDS = {**RM_KINDS, **QM_KINDS, **AM_KINDS}
SERVICES = {"rm": ("Requirements Management", RM, ["requirements", "needs"]), "qm": ("Quality Management", QM, ["tests", "gates"]), "am": ("Architecture Management", AM, list(AM_KINDS)), "cm": ("Change Management", CM, ["patches"])}

def _title(v): return v.get("name") or v.get("title") or v.get("text", "")[:120] or v.get("id", "")

class Provider:
    def __init__(self, workspace, base: str = ""):
        self.W = workspace; self.base = base.rstrip("/")

    # ---------------- URIs ----------------
    def uri(self, req: Request, path: str) -> URIRef:
        root = self.base or str(req.base_url).rstrip("/")
        return URIRef(root + path)
    def res_uri(self, req, pid, kind, eid): return self.uri(req, f"/oslc/p/{pid}/{kind}/{urllib.parse.quote(eid)}")

    # ---------------- RDF building ----------------
    def graph(self): g = Graph(); [g.bind(p, ns) for p, ns in PREFIXES.items()]; return g

    def element_graph(self, req, pid, m, kind, eid, g=None):
        g = g or self.graph(); v = m[kind][eid]; s = self.res_uri(req, pid, kind, eid)
        g.add((s, RDF.type, ALL_KINDS[kind])); g.add((s, DCTERMS.identifier, Literal(eid))); g.add((s, DCTERMS.title, Literal(_title(v))))
        g.add((s, OSLC.shortTitle, Literal(eid))); g.add((s, DCTERMS.type, Literal(kind[:-1] if kind.endswith("s") else kind)))
        g.add((s, OSLC.serviceProvider, self.uri(req, f"/oslc/p/{pid}")))
        g.add((s, OSLC.instanceShape, self.uri(req, f"/oslc/p/{pid}/shapes/{kind}")))
        if v.get("text"): g.add((s, DCTERMS.description, Literal(v["text"])))
        if v.get("rationale"): g.add((s, DCTERMS.description, Literal(v["rationale"])))
        for k, val in v.items():
            if k in ("name", "title", "text") or val in (None, "", [], {}): continue
            refs = schema.KINDS[kind].get("refs", {})
            if k in refs:
                for x in (val if isinstance(val, list) else [val]):
                    if x in m.get(refs[k], {}): g.add((s, LCH[k], self.res_uri(req, pid, refs[k], x)))
            elif isinstance(val, (str, int, float, bool)): g.add((s, LCH[k], Literal(val)))
            elif isinstance(val, list) and all(isinstance(x, (str, int, float)) for x in val): [g.add((s, LCH[k], Literal(x))) for x in val]
            elif isinstance(val, dict): g.add((s, LCH[k], Literal(json.dumps(val), datatype=RDF.JSON)))
        # standard OSLC links
        if kind == "requirements":
            for t in v.get("tests", []):
                if t in m["tests"]: g.add((s, RM.validatedBy, self.res_uri(req, pid, "tests", t)))
            for n in v.get("from_", []):
                if n in m["needs"]: g.add((self.res_uri(req, pid, "needs", n), RM.elaboratedBy, s)); g.add((s, RM.elaborates, self.res_uri(req, pid, "needs", n)))
            for f, fv in m["functions"].items():
                if eid in fv.get("reqs", []):
                    g.add((s, RM.satisfiedBy, self.res_uri(req, pid, "functions", f)))
                    for p in fv.get("alloc", []):
                        if p in m["parts"]: g.add((s, RM.satisfiedBy, self.res_uri(req, pid, "parts", p)))
            for c, cv in m["constraints"].items():
                if eid in cv.get("reqs", []): g.add((s, RM.constrainedBy, self.res_uri(req, pid, "constraints", c)))
            for r, rv in m["regulations"].items():
                if r in v.get("regs", []): g.add((s, RM.decomposes, self.res_uri(req, pid, "regulations", r)))
        if kind == "tests":
            for r, rv in m["requirements"].items():
                if eid in rv.get("tests", []): g.add((s, QM.validatesRequirement, self.res_uri(req, pid, "requirements", r)))
            if v.get("gate") in m["gates"]: g.add((self.res_uri(req, pid, "gates", v["gate"]), QM.usesTestCase, s))
            if v.get("status"): g.add((s, OSLC.state, Literal(v["status"])))
        if kind == "functions":
            for p in v.get("alloc", []):
                if p in m["parts"]: g.add((s, DCTERMS.relation, self.res_uri(req, pid, "parts", p)))
        if kind == "parts" and v.get("parent") in m["parts"]: g.add((self.res_uri(req, pid, "parts", v["parent"]), DCTERMS.hasPart, s))
        return g

    def patch_graph(self, req, pid, p, g=None):
        g = g or self.graph(); s = self.uri(req, f"/oslc/p/{pid}/patches/{p.id}")
        g.add((s, RDF.type, CM.ChangeRequest)); g.add((s, DCTERMS.identifier, Literal(p.id))); g.add((s, DCTERMS.title, Literal(p.rationale[:120]))); g.add((s, DCTERMS.description, Literal(p.rationale)))
        g.add((s, DCTERMS.creator, Literal(p.author))); g.add((s, DCTERMS.created, Literal(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.created)), datatype=XSD.dateTime)))
        g.add((s, OSLC.state, Literal(p.status))); g.add((s, CM.status, Literal({"staged": "Submitted", "applied": "Closed", "rejected": "Rejected"}.get(p.status, p.status))))
        g.add((s, CM.closed, Literal(p.status in ("applied", "rejected"), datatype=XSD.boolean))); g.add((s, CM.reviewed, Literal(p.status != "staged", datatype=XSD.boolean)))
        for op in p.ops:
            if op.kind in ALL_KINDS: g.add((s, CM.affectsRequirement if op.kind == "requirements" else CM.relatedChangeRequest if False else DCTERMS.relation, self.res_uri(req, pid, op.kind, op.id)))
        return g

    # ---------------- serialization / content negotiation ----------------
    def serialize(self, g: Graph, req: Request, compact_json=None) -> Response:
        acc = (req.headers.get("accept") or "application/ld+json").lower()
        if "text/turtle" in acc: return Response(g.serialize(format="turtle"), media_type="text/turtle")
        if "application/rdf+xml" in acc or "application/xml" in acc: return Response(g.serialize(format="pretty-xml"), media_type="application/rdf+xml")
        if "application/json" in acc and "ld+json" not in acc and compact_json is not None: return JSONResponse(compact_json)
        ctx = {p: str(ns) for p, ns in PREFIXES.items()}
        return Response(g.serialize(format="json-ld", context=ctx, auto_compact=True), media_type="application/ld+json")

    # ---------------- discovery documents ----------------
    def catalog(self, req):
        g = self.graph(); c = self.uri(req, "/oslc/catalog")
        g.add((c, RDF.type, OSLC.ServiceProviderCatalog)); g.add((c, DCTERMS.title, Literal("Launch — systems engineering digital thread")))
        g.add((c, DCTERMS.publisher, Literal("Twinmo AI / Launch")))
        for d in SERVICES.values(): g.add((c, OSLC.domain, URIRef(str(d[1]))))
        for pid in self.W.ids():
            sp = self.uri(req, f"/oslc/p/{pid}"); g.add((c, OSLC.serviceProvider, sp)); g.add((sp, RDF.type, OSLC.ServiceProvider)); g.add((sp, DCTERMS.title, Literal(self.W.summary(pid)["name"])))
        return g

    def service_provider(self, req, pid):
        g = self.graph(); sp = self.uri(req, f"/oslc/p/{pid}"); name = self.W.summary(pid)["name"]
        g.add((sp, RDF.type, OSLC.ServiceProvider)); g.add((sp, DCTERMS.title, Literal(name))); g.add((sp, DCTERMS.identifier, Literal(pid)))
        g.add((sp, OSLC.details, self.uri(req, f"/p/{pid}")))
        for key, (title, ns, kinds) in SERVICES.items():
            svc = URIRef(str(sp) + f"#service-{key}"); g.add((sp, OSLC.service, svc)); g.add((svc, RDF.type, OSLC.Service)); g.add((svc, OSLC.domain, URIRef(str(ns)))); g.add((svc, DCTERMS.title, Literal(title)))
            for kind in kinds:
                qc = URIRef(str(sp) + f"#query-{kind}"); g.add((svc, OSLC.queryCapability, qc)); g.add((qc, RDF.type, OSLC.QueryCapability)); g.add((qc, DCTERMS.title, Literal(f"Query {kind}")))
                g.add((qc, OSLC.queryBase, self.uri(req, f"/oslc/p/{pid}/{kind}"))); g.add((qc, OSLC.resourceShape, self.uri(req, f"/oslc/p/{pid}/shapes/{kind}")))
                if kind in ALL_KINDS: g.add((qc, OSLC.resourceType, ALL_KINDS[kind]))
                if kind != "patches":
                    cf = URIRef(str(sp) + f"#create-{kind}"); g.add((svc, OSLC.creationFactory, cf)); g.add((cf, RDF.type, OSLC.CreationFactory)); g.add((cf, DCTERMS.title, Literal(f"Create {kind[:-1]}")))
                    g.add((cf, OSLC.creation, self.uri(req, f"/oslc/p/{pid}/{kind}"))); g.add((cf, OSLC.resourceShape, self.uri(req, f"/oslc/p/{pid}/shapes/{kind}"))); g.add((cf, OSLC.resourceType, ALL_KINDS[kind]))
                    sd = URIRef(str(sp) + f"#select-{kind}"); g.add((svc, OSLC.selectionDialog, sd)); g.add((sd, RDF.type, OSLC.Dialog)); g.add((sd, DCTERMS.title, Literal(f"Select {kind}")))
                    g.add((sd, OSLC.dialog, self.uri(req, f"/oslc/p/{pid}/dialogs/select/{kind}"))); g.add((sd, OSLC.hintWidth, Literal("600px"))); g.add((sd, OSLC.hintHeight, Literal("400px"))); g.add((sd, OSLC.resourceType, ALL_KINDS[kind]))
        return g

    def shape(self, req, pid, kind):
        g = self.graph(); s = self.uri(req, f"/oslc/p/{pid}/shapes/{kind}"); g.add((s, RDF.type, OSLC.ResourceShape)); g.add((s, DCTERMS.title, Literal(f"Shape of {kind}")))
        if kind in ALL_KINDS: g.add((s, OSLC.describes, ALL_KINDS[kind]))
        spec = schema.KINDS.get(kind, {"req": [], "opt": {}, "refs": {}})
        def prop(name, occurs, rng=None, vt=None):
            p = URIRef(str(s) + "#" + name); g.add((s, OSLC.property, p)); g.add((p, RDF.type, OSLC.Property)); g.add((p, OSLC.name, Literal(name))); g.add((p, OSLC.propertyDefinition, LCH[name] if name not in ("title", "description", "identifier") else DCTERMS[name]))
            g.add((p, OSLC.occurs, OSLC[occurs]))
            if rng: g.add((p, OSLC.range, rng)); g.add((p, OSLC.valueType, OSLC.Resource)); g.add((p, OSLC.representation, OSLC.Reference))
            else: g.add((p, OSLC.valueType, vt or XSD.string))
        prop("identifier", "Exactly-one"); prop("title", "Exactly-one"); prop("description", "Zero-or-one")
        for f in spec["req"]: prop(f, "Exactly-one" if f not in spec.get("refs", {}) else "One-or-many", ALL_KINDS.get(spec["refs"].get(f)) if f in spec.get("refs", {}) else None)
        for f, d in spec["opt"].items(): prop(f, "Zero-or-many" if isinstance(d, list) else "Zero-or-one", ALL_KINDS.get(spec["refs"].get(f)) if f in spec.get("refs", {}) else None, XSD.integer if isinstance(d, int) else None)
        return g

    # ---------------- query ----------------
    def query(self, req, pid, kind):
        S = self.W.get(pid); m = S.store.load()
        if kind == "patches": items = {p.id: {"id": p.id, "rationale": p.rationale, "status": p.status, "author": p.author} for p in S.store.list_patches(None)}
        elif kind in ALL_KINDS: items = m[kind]
        else: raise HTTPException(404)
        q = req.query_params; where = q.get("oslc.where", ""); terms = (q.get("oslc.searchTerms") or "").strip('"').lower()
        def ok(eid, v):
            if terms and terms not in (eid + " " + json.dumps(v, ensure_ascii=False)).lower(): return False
            for clause in [c.strip() for c in where.split(" and ") if c.strip()]:
                mm = re.match(r"([\w:]+)\s*(=|!=|<=|>=|<|>)\s*(.+)", clause)
                if not mm: continue
                prop, op, val = mm.groups(); prop = prop.split(":")[-1]; val = val.strip().strip('"<>')
                if prop == "identifier": act = eid
                elif prop in ("title", "shortTitle"): act = _title(v)
                else: act = v.get(prop, "")
                if isinstance(act, list): act = ",".join(map(str, act))
                try: a, b = float(act), float(val)
                except (TypeError, ValueError): a, b = str(act), str(val)
                if not {"=": a == b, "!=": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]: return False
            return True
        ids = [i for i, v in items.items() if ok(i, v)]
        size = int(q.get("oslc.pageSize") or 200); page = int(q.get("page") or 0); chunk = ids[page * size:(page + 1) * size]
        g = self.graph(); info = self.uri(req, f"/oslc/p/{pid}/{kind}?" + str(req.url.query)); g.add((info, RDF.type, OSLC.ResponseInfo)); g.add((info, OSLC.totalCount, Literal(len(ids), datatype=XSD.integer)))
        if (page + 1) * size < len(ids): g.add((info, OSLC.nextPage, self.uri(req, f"/oslc/p/{pid}/{kind}?oslc.pageSize={size}&page={page+1}" + (f"&oslc.where={urllib.parse.quote(where)}" if where else ""))))
        base = self.uri(req, f"/oslc/p/{pid}/{kind}")
        for eid in chunk:
            if kind == "patches": self.patch_graph(req, pid, S.store.get_patch(eid), g); g.add((base, RDFS.member, self.uri(req, f"/oslc/p/{pid}/patches/{eid}")))
            else: self.element_graph(req, pid, m, kind, eid, g); g.add((base, RDFS.member, self.res_uri(req, pid, kind, eid)))
        compact = [{"rdf:about": str(self.res_uri(req, pid, kind, i)), "dcterms:identifier": i, "dcterms:title": _title(items[i]) if kind != "patches" else items[i]["rationale"], **{k: v for k, v in (items[i].items() if isinstance(items[i], dict) else []) if isinstance(v, (str, int, float, list))}} for i in chunk]
        return self.serialize(g, req, compact_json={"oslc:totalCount": len(ids), "oslc:results": compact})

    # ---------------- single resource / preview ----------------
    def resource(self, req, pid, kind, eid):
        S = self.W.get(pid); m = S.store.load()
        if kind == "patches":
            try: return self.serialize(self.patch_graph(req, pid, S.store.get_patch(eid)), req)
            except Exception: raise HTTPException(404)
        if kind not in ALL_KINDS or eid not in m[kind]: raise HTTPException(404)
        acc = (req.headers.get("accept") or "").lower()
        if "x-oslc-compact" in acc:
            v = m[kind][eid]; small = self.uri(req, f"/oslc/p/{pid}/preview/{kind}/{eid}?size=small"); large = self.uri(req, f"/oslc/p/{pid}/preview/{kind}/{eid}?size=large")
            xml = f'''<?xml version="1.0" encoding="UTF-8"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:oslc="http://open-services.net/ns/core#">
<oslc:Compact rdf:about="{self.res_uri(req, pid, kind, eid)}"><dcterms:title>{eid} {_esc(_title(v))}</dcterms:title><oslc:shortTitle>{eid}</oslc:shortTitle><oslc:icon rdf:resource="{self.uri(req, '/static/favicon.svg')}"/>
<oslc:smallPreview><oslc:Preview><oslc:document rdf:resource="{small}"/><oslc:hintWidth>420px</oslc:hintWidth><oslc:hintHeight>180px</oslc:hintHeight></oslc:Preview></oslc:smallPreview>
<oslc:largePreview><oslc:Preview><oslc:document rdf:resource="{large}"/><oslc:hintWidth>800px</oslc:hintWidth><oslc:hintHeight>500px</oslc:hintHeight></oslc:Preview></oslc:largePreview></oslc:Compact></rdf:RDF>'''
            return Response(xml, media_type="application/x-oslc-compact+xml")
        if "text/html" in acc and "ld+json" not in acc and "turtle" not in acc:
            return Response(status_code=303, headers={"Location": f"/p/{pid}#/element/{kind}/{eid}"})
        return self.serialize(self.element_graph(req, pid, m, kind, eid), req, compact_json={"rdf:about": str(self.res_uri(req, pid, kind, eid)), "dcterms:identifier": eid, **m[kind][eid]})

    def preview(self, req, pid, kind, eid, size="small"):
        S = self.W.get(pid); m = S.store.load()
        if kind not in ALL_KINDS or eid not in m[kind]: raise HTTPException(404)
        v = m[kind][eid]; rows = "".join(f"<tr><th>{_esc(k)}</th><td>{_esc(json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else x)}</td></tr>" for k, x in v.items() if x not in (None, "", [], {}))
        im = derive.impact(m, eid) if size == "large" else None
        extra = f"<p><b>Impact if changed:</b> {len(im['affected'])} elements, {len(im['tests_to_rerun'])} tests to re-run</p>" if im else ""
        return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><style>body{{font:13px -apple-system,Segoe UI,sans-serif;margin:10px;color:#1d2430}}th{{text-align:left;color:#6b7280;padding:2px 8px 2px 0;vertical-align:top}}td{{padding:2px 0}}h3{{margin:0 0 6px;font-size:15px}}</style></head>
<body><h3>{eid} — {_esc(_title(v))}</h3><div style="color:#6b7280;font-size:12px">{kind} · Launch · <a href="/p/{pid}#/element/{kind}/{eid}" target="_top">open</a></div><table>{rows}</table>{extra}</body></html>""")

    def selection_dialog(self, req, pid, kind):
        return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><style>body{{font:13px -apple-system,Segoe UI,sans-serif;margin:10px}}input{{width:100%;padding:6px;margin-bottom:6px}}li{{padding:3px;cursor:pointer}}li:hover{{background:#eef2ff}}</style></head><body>
<input id="q" placeholder="search {kind}…" autofocus><ul id="l"></ul><script>
const q=document.getElementById('q'),l=document.getElementById('l');async function run(){{const r=await fetch('/oslc/p/{pid}/{kind}?oslc.searchTerms="'+encodeURIComponent(q.value)+'"',{{headers:{{accept:'application/json'}},credentials:'include'}});const j=await r.json();l.innerHTML=j['oslc:results'].slice(0,50).map(x=>`<li data-u="${{x['rdf:about']}}" data-t="${{x['dcterms:identifier']}} ${{(x['dcterms:title']||'').replace(/"/g,'')}}"><b>${{x['dcterms:identifier']}}</b> ${{x['dcterms:title']||''}}</li>`).join('')}}
q.oninput=run;run();l.onclick=e=>{{const li=e.target.closest('li');if(!li)return;const msg='oslc-response:'+JSON.stringify({{"oslc:results":[{{"oslc:label":li.dataset.t,"rdf:resource":li.dataset.u}}]}});(window.parent||window.opener).postMessage(msg,'*');}}
</script></body></html>""")

    # ---------------- create / update ----------------
    async def create(self, req, pid, kind, user):
        if kind not in ALL_KINDS: raise HTTPException(404)
        body = await req.body(); data = _parse_incoming(body, req.headers.get("content-type", ""), kind)
        eid = data.pop("identifier", None) or data.pop("id", None) or _next_id(self.W.get(pid).store.load(), kind)
        return self._write(req, pid, kind, eid, data, user, "add")
    async def update(self, req, pid, kind, eid, user):
        body = await req.body(); data = _parse_incoming(body, req.headers.get("content-type", ""), kind); data.pop("identifier", None); data.pop("id", None)
        return self._write(req, pid, kind, eid, data, user, "update")
    def _write(self, req, pid, kind, eid, data, user, op):
        S = self.W.get(pid); m = S.store.load()
        if op == "update" and eid not in m[kind]: raise HTTPException(404)
        patch = Patch(ops=[Op(op, kind, eid, data)], author=f"oslc:{user}", rationale=f"OSLC {op} {kind}/{eid} by {user}", sources=["oslc"])
        try: new, issues = S.store.check_patch(m, patch)
        except Exception as e: raise HTTPException(400, str(e))
        errs = [f"{i.where}: {i.msg}" for i in issues if i.level == "error"]
        if errs: raise HTTPException(409, "; ".join(errs[:5]))
        S.store.stage(patch); S.store.approve(patch.id, approver=user); S.emit("patch_applied", id=patch.id, user=user); S.emit("model_changed")
        g = self.element_graph(req, pid, S.store.load(), kind, eid); r = self.serialize(g, req); r.status_code = 201 if op == "add" else 200; r.headers["Location"] = str(self.res_uri(req, pid, kind, eid)); r.headers["ETag"] = f'W/"{int(time.time())}"'; return r

def _esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def _next_id(m, kind):
    pfx = {"requirements": "R-", "needs": "N-", "tests": "T-", "functions": "F", "parts": "P-", "interfaces": "IF-", "logical_components": "LC-", "constraints": "C-", "arch_decisions": "AD-", "trades": "TD-", "regulations": "REG-", "stakeholders": "STK-", "states": "S-", "transitions": "TR-", "nodes": "ND-", "gates": "G-", "use_cases": "UC-", "scenarios": "SC-", "actors": "ACT-", "moes": "MOE-", "logical_interfaces": "LI-"}.get(kind, kind[:2].upper() + "-")
    n = len(m[kind]) + 1
    while f"{pfx}{n:03d}" in m[kind]: n += 1
    return f"{pfx}{n:03d}"

def _parse_incoming(body: bytes, ctype: str, kind: str) -> dict:
    """Accept JSON-LD / Turtle / RDF-XML / plain JSON; map dcterms:title→name|text, dcterms:description→text, launch:* → fields."""
    ctype = ctype.lower(); data = {}
    if "json" in ctype and "ld+json" not in ctype:
        try: data = json.loads(body or b"{}")
        except Exception: raise HTTPException(400, "bad JSON")
        data = {k.split(":")[-1]: v for k, v in data.items() if not k.startswith("rdf:")}
    else:
        g = Graph(); fmt = "turtle" if "turtle" in ctype else "xml" if "xml" in ctype else "json-ld"
        try: g.parse(data=body, format=fmt)
        except Exception as e: raise HTTPException(400, f"cannot parse {fmt}: {e}")
        subj = next((s for s in g.subjects(RDF.type, None)), None) or next(iter(g.subjects()), None)
        for p, o in g.predicate_objects(subj):
            if p == RDF.type: continue
            key = str(p).split("#")[-1].split("/")[-1]
            val = str(o).split("/")[-1] if isinstance(o, URIRef) else (o.toPython() if isinstance(o, Literal) else str(o))
            if key in data: data[key] = (data[key] if isinstance(data[key], list) else [data[key]]) + [val]
            else: data[key] = val
    if "title" in data:
        t = data.pop("title"); data.setdefault("text" if kind in ("requirements", "needs") else "title" if kind == "arch_decisions" else "name", t)
    if "description" in data and kind in ("requirements", "needs"): data["text"] = data.pop("description")
    spec = schema.KINDS[kind]
    for f, d in spec["opt"].items():
        if isinstance(d, list) and f in data and not isinstance(data[f], list): data[f] = [data[f]]
    for f in spec["req"]:
        if f in spec.get("refs", {}):
            if f not in data: data[f] = []
            elif not isinstance(data[f], list): data[f] = [data[f]]
    if kind == "requirements": data.setdefault("type", "FUNC"); data.setdefault("verify", "test")
    if kind == "tests": data.setdefault("method", ""); data.setdefault("gate", ""); data.setdefault("passfail", "")
    return {k: v for k, v in data.items() if k not in ("serviceProvider", "instanceShape", "shortTitle", "about")}

def router(workspace, current_user_dep, oauth_store=None):
    from fastapi import Depends
    from . import oslc_oauth
    P = Provider(workspace); r = APIRouter()
    def user_or_basic(request: Request) -> str:
        try: return current_user_dep(request)
        except HTTPException:
            auth = request.headers.get("authorization", "")
            if oauth_store is not None and auth.lower().startswith("oauth "):
                u = oslc_oauth.verify(oauth_store, request, oslc_oauth.oauth_params(request))
                if u: return u
            if auth.lower().startswith("basic "):
                try: email, token = base64.b64decode(auth[6:]).decode().split(":", 1)
                except Exception: raise HTTPException(401, "bad basic auth")
                if workspace.token_ok(email, token): return email
            raise HTTPException(401, "OSLC: authenticate with the app session or HTTP Basic email:api-token", headers={"WWW-Authenticate": 'Basic realm="Launch OSLC"'})
    U = Depends(user_or_basic)
    @r.get("/oslc/catalog")
    def catalog(request: Request, user: str = U): return P.serialize(P.catalog(request), request)
    @r.get("/oslc/rootservices")
    def rootservices(request: Request):
        """Jazz-style root services document: what an ELM/DOORS Next admin points 'Add Friend' at. Unauthenticated by design."""
        JFS = Namespace("http://jazz.net/xmlns/prod/jazz/jfs/1.0/"); JD = Namespace("http://jazz.net/xmlns/prod/jazz/discovery/1.0/")
        g = P.graph(); g.bind("jfs", JFS); g.bind("jd", JD); s = P.uri(request, "/oslc/rootservices")
        g.add((s, DCTERMS.title, Literal("Launch root services"))); g.add((s, JD.oslcCatalogs, P.uri(request, "/oslc/catalog")))
        for key, (title, ns, kinds) in SERVICES.items():
            g.add((s, URIRef(f"http://open-services.net/xmlns/{key}/1.0/{key}ServiceProviders"), P.uri(request, "/oslc/catalog")))
            g.add((s, URIRef(f"http://open-services.net/ns/{key}#{key}ServiceProviders"), P.uri(request, "/oslc/catalog")))
        g.add((s, JFS.oauthRealmName, Literal("Launch"))); g.add((s, JFS.oauthDomain, P.uri(request, "/")))
        g.add((s, JFS.oauthRequestConsumerKeyUrl, P.uri(request, "/api/oslc/consumers")))
        g.add((s, JFS.oauthApprovalModuleUrl, P.uri(request, "/p/default#/integrations")))
        g.add((s, JFS.oauthRequestTokenUrl, P.uri(request, "/oslc/oauth/request_token"))); g.add((s, JFS.oauthUserAuthorizationUrl, P.uri(request, "/oslc/oauth/authorize"))); g.add((s, JFS.oauthAccessTokenUrl, P.uri(request, "/oslc/oauth/access_token")))
        g.add((s, OSLC.oauthConfiguration, URIRef(str(s) + "#oauth"))); oc = URIRef(str(s) + "#oauth"); g.add((oc, RDF.type, OSLC.OAuthConfiguration))
        g.add((oc, OSLC.oauthRequestTokenURI, P.uri(request, "/oslc/oauth/request_token"))); g.add((oc, OSLC.authorizationURI, P.uri(request, "/oslc/oauth/authorize"))); g.add((oc, OSLC.oauthAccessTokenURI, P.uri(request, "/oslc/oauth/access_token")))
        acc = (request.headers.get("accept") or "").lower()
        if "turtle" not in acc and "json" not in acc: return Response(g.serialize(format="pretty-xml"), media_type="application/rdf+xml")   # Jazz expects RDF/XML
        return P.serialize(g, request)
    @r.get("/oslc/p/{pid}")
    def sp(pid: str, request: Request, user: str = U): return P.serialize(P.service_provider(request, pid), request)
    @r.get("/oslc/p/{pid}/shapes/{kind}")
    def shape(pid: str, kind: str, request: Request, user: str = U): return P.serialize(P.shape(request, pid, kind), request)
    @r.get("/oslc/p/{pid}/dialogs/select/{kind}")
    def dialog(pid: str, kind: str, request: Request, user: str = U): return P.selection_dialog(request, pid, kind)
    @r.get("/oslc/p/{pid}/preview/{kind}/{eid}")
    def preview(pid: str, kind: str, eid: str, request: Request, size: str = "small", user: str = U): return P.preview(request, pid, kind, eid, size)
    @r.get("/oslc/p/{pid}/{kind}")
    def query(pid: str, kind: str, request: Request, user: str = U): return P.query(request, pid, kind)
    @r.post("/oslc/p/{pid}/{kind}")
    async def create(pid: str, kind: str, request: Request, user: str = U): return await P.create(request, pid, kind, user)
    @r.get("/oslc/p/{pid}/{kind}/{eid}")
    def resource(pid: str, kind: str, eid: str, request: Request, user: str = U): return P.resource(request, pid, kind, eid)
    @r.put("/oslc/p/{pid}/{kind}/{eid}")
    async def update(pid: str, kind: str, eid: str, request: Request, user: str = U): return await P.update(request, pid, kind, eid, user)
    return r
