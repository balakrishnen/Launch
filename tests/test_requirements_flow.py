import os
from sethread import importers as IMP, derive as D
from sethread.store import Store, Op

EX = os.path.join(os.path.dirname(__file__), "..", "examples", "brewmaster")
H = ["ID", "Title", "Requirement", "Subsystem", "Parent", "Related", "Priority", "Status", "Verification", "Rationale", "Owner", "Notes"]

def sheets():
    req = {"name": "Requirements", "headers": ["Requirements (syseng-toolkit v1.0.0)"], "rows": [H,
        ["REQ-001", "Mass", "The drone shall carry a payload of 0.75 kg.", "System", "", "", "Must", "Accepted", "Test", "", "Ana", ""],
        ["REQ-002", "Arm", "Each arm shall be 300 mm ±1 mm long.", "Frame", "REQ-001", "REQ-001", "Must", "Draft", "Design", "", "Ben", ""]]}
    log = {"name": "Change Log", "headers": ["Date", "REQ ID", "What Changed", "Was", "Now", "Reason", "By"], "rows": [["2026-11-20", "REQ-001", "Requirement", "0.5 kg", "0.75 kg", "update", "Ana"]]}
    return [req, log]

def test_import_and_suspect_links():
    st = Store(EX); m = st.load(); sh = sheets()
    assert IMP.detect(sh)["requirements"] == 2
    ops, notes = IMP.syseng_toolkit(sh, m)
    m = st.apply_ops(m, [Op(**o) for o in ops])
    assert m["requirements"]["REQ-002"]["parent"] == "REQ-001" and m["requirements"]["REQ-002"]["verify"] == "inspection"
    assert m["requirements"]["REQ-001"]["rev"] == 2
    m = st.apply_ops(m, [Op(op="update", kind="requirements", id="REQ-001", value={"text": "The drone shall carry a payload of 1.0 kg."})])
    assert any(u == "REQ-001" and d == "REQ-002" for u, d, _ in D.suspect_links(m))
    m = st.apply_ops(m, [Op(op="update", kind="requirements", id="REQ-002", value={"reviewed": "2999-01-01"})])
    assert not any(d == "REQ-002" for _, d, _ in D.suspect_links(m))
