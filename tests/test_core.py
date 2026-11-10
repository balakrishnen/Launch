import os, shutil, tempfile
from sethread import schema, derive, sysml, docs, views
from sethread.store import Store, Patch, Op

EX = os.path.join(os.path.dirname(__file__), "..", "examples", "sabi")

def test_example_validates_and_is_clean():
    m = Store(EX).load(); assert not [i for i in schema.validate(m) if i.level == "error"]
    assert derive.coverage_report(m)["clean"]

def test_patch_roundtrip():
    d = tempfile.mkdtemp(); shutil.copy(os.path.join(EX, "model.yaml"), d); st = Store(d); m = st.load()
    p = Patch(ops=[Op("add", "parts", "P-X", {"name": "x", "type": "X", "discipline": "mechanical", "parent": "P-CAP"})], author="t", rationale="r")
    st.stage(p); assert st.list_patches("staged"); st.approve(p.id); assert "P-X" in st.load()["parts"]; assert st.provenance("parts", "P-X")
    bad = Patch(ops=[Op("add", "needs", "N-X", {"stk": "NOPE", "moe": "MOE-01", "text": "t"})], author="t", rationale="r")
    _, issues = st.check_patch(st.load(), bad); assert any(i.level == "error" for i in issues)

def test_emitters(tmp_path):
    m = Store(EX).load(); assert len(sysml.emit(m, str(tmp_path / "s"))) == 9
    done, failed = views.render_all(m, str(tmp_path / "v")); assert not failed and len(done) >= 12
    assert os.path.getsize(docs.build(m, str(tmp_path / "d"), views_rel="../v")) > 20000

def test_empty_model_builds(tmp_path):
    m = schema.empty_model("Empty"); assert not derive.coverage_report(m)["clean"]
    sysml.emit(m, str(tmp_path / "s")); docs.build(m, str(tmp_path / "d"))

def test_requirement_quality_and_scorecard():
    from sethread import quality
    good = quality.requirement_quality("The cap shall operate ≥ 4 h continuously on-head per charge.", "runtime_h >= 4", "PERF")
    bad = quality.requirement_quality("The system should be fast and user-friendly where possible and it shall also be reliable.", "", "PERF")
    assert good["score"] == 100 and bad["score"] < 50 and any(f["rule"] == "R4" for f in bad["findings"])
    sc = quality.scorecard(Store(EX).load()); assert sc["grade"] in "ABCDF" and 0 <= sc["overall"] <= 100

def test_oslc_roundtrip():
    from fastapi.testclient import TestClient
    from sethread.web.server import create_app
    d = tempfile.mkdtemp(); shutil.copytree(EX, os.path.join(d, "sabi")); os.environ.pop("SETHREAD_INVITE", None)
    c = TestClient(create_app(None, None, d)); c.post("/api/login", json={"email": "t@x.io"})
    tok = c.get("/api/token").json()["token"]; auth = ("t@x.io", tok)
    assert c.get("/oslc/catalog", auth=auth, headers={"Accept": "text/turtle"}).status_code == 200
    r = c.get('/oslc/p/sabi/requirements?oslc.where=launch:type="SAFE"', auth=auth, headers={"Accept": "application/json"}).json(); assert r["oslc:totalCount"] > 0
    created = c.post("/oslc/p/sabi/requirements", auth=auth, headers={"Content-Type": "application/json"}, json={"dcterms:title": "The cap shall survive a 1.2 m drop with no loss of function.", "launch:type": "ENV", "launch:attr": "drop_m >= 1.2"})
    assert created.status_code == 201 and "Location" in created.headers
    assert c.get("/oslc/p/sabi/requirements/R-001", auth=auth, headers={"Accept": "application/x-oslc-compact+xml"}).status_code == 200
    assert TestClient(create_app(None, None, d)).get("/oslc/catalog").status_code == 401

def test_oauth1_handshake():
    import time, secrets, urllib.parse
    from fastapi.testclient import TestClient
    from sethread.web.server import create_app
    from sethread.oslc_oauth import sign
    d = tempfile.mkdtemp(); shutil.copytree(EX, os.path.join(d, "sabi")); os.environ.pop("SETHREAD_INVITE", None)
    c = TestClient(create_app(None, None, d)); c.post("/api/login", json={"email": "admin@x.io"})
    cons = c.post("/api/oslc/consumers", json={"name": "ELM"}).json()
    def hdr(method, url, extra, tsec=""):
        p = {"oauth_consumer_key": cons["key"], "oauth_nonce": secrets.token_hex(4), "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": str(int(time.time())), "oauth_version": "1.0", **extra}
        p["oauth_signature"] = sign(method, url, p, cons["secret"], tsec); return "OAuth " + ", ".join(f'{k}="{urllib.parse.quote(v, safe="~")}"' for k, v in p.items())
    base = "http://testserver"
    rt = dict(urllib.parse.parse_qsl(c.post("/oslc/oauth/request_token", headers={"Authorization": hdr("POST", base + "/oslc/oauth/request_token", {"oauth_callback": "oob"})}).text))
    r = c.post("/oslc/oauth/authorize", data={"oauth_token": rt["oauth_token"]}); ver = r.text.split("<code>")[1].split("</code>")[0]
    at = dict(urllib.parse.parse_qsl(c.post("/oslc/oauth/access_token", headers={"Authorization": hdr("POST", base + "/oslc/oauth/access_token", {"oauth_token": rt["oauth_token"], "oauth_verifier": ver}, rt["oauth_token_secret"])}).text))
    anon = TestClient(create_app(None, None, d)); u = base + "/oslc/p/sabi/requirements/R-001"
    assert anon.get(u, headers={"Authorization": hdr("GET", u, {"oauth_token": at["oauth_token"]}, at["oauth_token_secret"])}).status_code == 200
    assert anon.get(u, headers={"Authorization": hdr("GET", u, {"oauth_token": at["oauth_token"]}, "wrong")}).status_code == 401

def test_dbstore_sqlite_roundtrip():
    from sethread.dbstore import DB, import_yaml_project
    d = tempfile.mkdtemp(); db = DB(f"sqlite:///{d}/t.db"); st = import_yaml_project(db, "t", "sabi", EX)
    m = st.load(); assert derive.coverage_report(m)["clean"] and st.rev() == 1
    p = Patch(ops=[Op("add", "parts", "P-X", {"name": "x", "type": "X", "discipline": "mechanical", "parent": "P-CAP"})], author="t", rationale="r"); st.stage(p)
    r0 = st.baseline("B0"); st.approve(p.id, "u"); assert st.rev() == 2 and "P-X" in st.load()["parts"] and "P-X" not in st.load(r0)["parts"]
    assert st.diff(r0, 2)["added"] == ["parts/P-X"] and st.provenance("parts", "P-X")[0]["approver"] == "u"

def test_app_on_database():
    from fastapi.testclient import TestClient
    from sethread.web.server import create_app
    from sethread.dbstore import DB, import_yaml_project
    d = tempfile.mkdtemp(); url = f"sqlite:///{d}/t.db"; import_yaml_project(DB(url), "acme", "sabi", EX); os.environ.pop("SETHREAD_INVITE", None)
    c = TestClient(create_app(None, None, os.path.join(d, "files"), url, "acme")); c.post("/api/login", json={"email": "t@x.io"})
    assert [p["id"] for p in c.get("/api/projects").json()] == ["sabi"]
    r = c.post("/api/p/sabi/patch", json={"ops": [{"op": "update", "kind": "requirements", "id": "R-001", "value": {"attr": "runtime_h >= 5"}}], "rationale": "t"}); assert r.json()["applied"]
    assert c.post("/api/p/sabi/baselines", json={"name": "PDR"}).json()["rev"] == 2
    assert c.get("/api/p/sabi/diff/1/2").json()["changed"][0]["id"] == "requirements/R-001"
    assert c.get("/api/p/sabi/element/requirements/R-001").json()["provenance"][0]["author"] == "user:t@x.io"
    assert len(c.get("/api/p/sabi/form/dfmea").json()["rows"]) > 50
