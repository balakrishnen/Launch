"""Generates the DfX guideline sets (run once; the YAML files are the source of truth afterwards).
Check types: coverage(key,max) · attr(kind,key,min_share[,filter]) · fmea(sev_min[,require|n]) · collection(kind,n) ·
req_type(type,n) · regulation(pattern) · tests_method(pattern,n) · note(kind,n) · manual"""
import yaml, os
H = os.path.dirname(__file__)
def it(i, text, check=None, ref=""): return {"id": i, "text": text, "check": check or {"type": "manual"}, **({"ref": ref} if ref else {})}
X = {
 "manufacturing": dict(name="Design for Manufacturing (DfM)", short="DfM", focus="manufacturing", standard="DFMA (Boothroyd–Dewhurst), AIAG APQP", items=[
  it("DFM-01", "Every part has a discipline and a make/buy decision", {"type": "attr", "kind": "parts", "key": "make_buy", "min_share": 1.0}),
  it("DFM-02", "Buy parts have an approved supplier", {"type": "coverage", "key": "buy_parts_without_supplier", "max": 0}),
  it("DFM-03", "A process flow exists for the product (process steps modelled)", {"type": "collection", "kind": "process_steps", "n": 1}),
  it("DFM-04", "Every process step has a PFMEA", {"type": "coverage", "key": "process_steps_without_pfmea", "max": 0}),
  it("DFM-05", "Parts carry a manufacturing process attribute (molding, machining, PCBA, …)", {"type": "attr", "kind": "parts", "key": "process", "min_share": 0.8}),
  it("DFM-06", "Tolerances and critical-to-quality characteristics identified on mechanical parts", {"type": "attr", "kind": "parts", "key": "ctq", "min_share": 0.5, "filter": {"discipline": "mechanical"}}),
  it("DFM-07", "Part count minimised: no two parts with the same function and discipline that could be combined"),
  it("DFM-08", "Standard / catalogue components preferred over custom where performance allows"),
  it("DFM-09", "Draft angles, wall thickness and undercuts reviewed for molded parts")]),
 "assembly": dict(name="Design for Assembly (DfA)", short="DfA", focus="manufacturing", standard="DFMA", items=[
  it("DFA-01", "Assembly sequence modelled as process steps with the parts consumed", {"type": "collection", "kind": "process_steps", "n": 3}),
  it("DFA-02", "Parts are self-locating / poka-yoke where orientation matters"),
  it("DFA-03", "Fastener count and types minimised; snap-fits where load allows"),
  it("DFA-04", "Top-down assembly with no re-orientation of the base part"),
  it("DFA-05", "Cable and connector interfaces have keyed, unique mates", {"type": "attr", "kind": "interfaces", "key": "keyed", "min_share": 0.6})]),
 "testability": dict(name="Design for Testability (DfT)", short="DfT", focus="test", standard="IEEE 1149 (JTAG), IPC-7912, DfT guidelines", items=[
  it("DFT-01", "Every requirement has at least one verifying test", {"type": "coverage", "key": "requirements_without_tests", "max": 0}),
  it("DFT-02", "Every test has a pass/fail criterion", {"type": "attr", "kind": "tests", "key": "passfail", "min_share": 1.0}),
  it("DFT-03", "Every High-AP failure mode is detected by a test", {"type": "coverage", "key": "high_ap_fm_without_tests", "max": 0}),
  it("DFT-04", "Electrical boards expose test points / boundary scan for end-of-line test", {"type": "attr", "kind": "parts", "key": "test_points", "min_share": 0.7, "filter": {"discipline": "electrical"}}),
  it("DFT-05", "A built-in self-test covers drive, power, sensors and radios (manufacturing requirement)", {"type": "req_type", "req": "MFG", "n": 1}),
  it("DFT-06", "End-of-line test time budget defined and met"),
  it("DFT-07", "Firmware exposes a diagnostic/telemetry interface usable by test and service")]),
 "reliability": dict(name="Design for Reliability (DfR)", short="DfR", focus="reliability", standard="MIL-HDBK-338, IEC 61709, AIAG-VDA FMEA, Telcordia SR-332", items=[
  it("DFR-01", "Reliability targets (MTBF / B10 / mission life) stated as requirements", {"type": "req_type", "req": "RELY", "n": 1}),
  it("DFR-02", "DFMEA complete: every candidate assessed or screened", {"type": "coverage", "key": "unassessed_candidates", "max": 0}),
  it("DFR-03", "Every High-AP failure mode has a test", {"type": "coverage", "key": "high_ap_fm_without_tests", "max": 0}),
  it("DFR-04", "Derating rules applied to electrical parts (voltage, current, temperature)", {"type": "attr", "kind": "parts", "key": "derating", "min_share": 0.6, "filter": {"discipline": "electrical"}}),
  it("DFR-05", "Life / wear-out mechanisms identified per part (fatigue, corrosion, electromigration, cycles)", {"type": "attr", "kind": "parts", "key": "wearout", "min_share": 0.5}),
  it("DFR-06", "Accelerated life / HALT planned for the top failure mechanisms", {"type": "tests_method", "pattern": "HALT|accelerated|life", "n": 1}),
  it("DFR-07", "Field events are linked to failure modes (FRACAS loop closed)", {"type": "coverage", "key": "field_events_without_fm", "max": 0}),
  it("DFR-08", "Single points of failure identified and justified or mitigated")]),
 "safety": dict(name="Design for Safety (DfS)", short="DfS", focus="safety", standard="ISO 12100, IEC 61508 / ISO 13849, ISO 14971, UL/IEC product standards", items=[
  it("DFS-01", "Hazard analysis exists: failure modes with severity ≥ 9 are identified", {"type": "fmea", "sev_min": 9, "n": 1}),
  it("DFS-02", "Every severity ≥ 9 failure mode has a verifying test", {"type": "fmea", "sev_min": 9, "require": "tests"}),
  it("DFS-03", "Safety requirements exist", {"type": "req_type", "req": "SAFE", "n": 1}),
  it("DFS-04", "Safety functions identified (safety_decision on functions)", {"type": "attr", "kind": "functions", "key": "safety_decision", "min_share": 0.2}),
  it("DFS-05", "Applicable safety standards are in the regulatory set with requirements", {"type": "coverage", "key": "regulations_without_requirements", "max": 0}),
  it("DFS-06", "Hierarchy of controls applied: inherently safe design before guards before warnings"),
  it("DFS-07", "Energy sources (electrical, stored mechanical, thermal, chemical) have isolation and discharge paths"),
  it("DFS-08", "Foreseeable misuse considered in scenarios", {"type": "collection", "kind": "scenarios", "n": 2})]),
 "maintainability": dict(name="Design for Maintainability (DfMt)", short="DfMt", focus="service", standard="MIL-HDBK-470, IEC 60300-3-10", items=[
  it("DFMT-01", "Maintainability targets (MTTR, maintenance interval) stated as requirements", {"type": "req_type", "req": "MAINT", "n": 1}),
  it("DFMT-02", "Wear and consumable parts identified with a service interval", {"type": "attr", "kind": "parts", "key": "service_interval", "min_share": 0.2}),
  it("DFMT-03", "Line-replaceable units defined (LRU flag on parts)", {"type": "attr", "kind": "parts", "key": "lru", "min_share": 0.3}),
  it("DFMT-04", "Fault isolation: diagnostics identify the failed LRU"),
  it("DFMT-05", "Access: LRUs replaceable without removing unrelated parts"),
  it("DFMT-06", "Standard tools only; captive fasteners where repeated access is expected")]),
 "service": dict(name="Design for Service (DfSv)", short="DfSv", focus="service", standard="industry practice; right-to-repair regulations (EU, US states)", items=[
  it("DFSV-01", "Serviceable parts carry a service level (user / field / depot / factory)", {"type": "attr", "kind": "parts", "key": "service_level", "min_share": 0.3}),
  it("DFSV-02", "Spare-parts strategy: parts have a lifecycle status", {"type": "attr", "kind": "parts", "key": "lifecycle", "min_share": 0.5}),
  it("DFSV-03", "Service documentation planned (report note)", {"type": "note", "kind": "report", "n": 1}),
  it("DFSV-04", "Firmware updatable in the field (OTA or service tool) with rollback"),
  it("DFSV-05", "Right-to-repair: parts, tools and documentation availability considered")]),
 "transportation": dict(name="Design for Transportation & Packaging", short="DfTr", focus="manufacturing", standard="ISTA 3A/6, ASTM D4169, UN 38.3, IATA DGR", items=[
  it("DFTR-01", "Shipping environment (shock, vibration, temperature, humidity) captured as environmental requirements", {"type": "req_type", "req": "ENV", "n": 1}),
  it("DFTR-02", "Lithium batteries: UN 38.3 in the regulatory set", {"type": "regulation", "pattern": "38\\.3"}),
  it("DFTR-03", "Packaging drop/vibration test planned (ISTA / ASTM D4169)", {"type": "tests_method", "pattern": "ISTA|D4169|drop|vibration", "n": 1}),
  it("DFTR-04", "Product ships in a transport-safe state (battery SoC, locks, modes)"),
  it("DFTR-05", "Package dimensions and mass fit the target shipping class / pallet pattern")]),
 "cost": dict(name="Design to Cost (DtC)", short="DtC", focus="program", standard="design-to-cost, should-cost", items=[
  it("DTC-01", "Unit cost target stated as a requirement", {"type": "req_type", "req": "COST", "n": 1}),
  it("DTC-02", "Parts carry a cost attribute so the rollup is live", {"type": "attr", "kind": "parts", "key": "cost_usd", "min_share": 0.7}),
  it("DTC-03", "Cost rollup table exists and is within target"),
  it("DTC-04", "Top-10 cost drivers have a should-cost or alternative")]),
 "environment": dict(name="Design for Environment & Sustainability (DfE)", short="DfE", focus="compliance", standard="RoHS, REACH, WEEE, EU Ecodesign / ESPR, ISO 14006", items=[
  it("DFE-01", "RoHS / REACH / WEEE (or market equivalents) in the regulatory set", {"type": "regulation", "pattern": "RoHS|REACH|WEEE|Ecodesign"}),
  it("DFE-02", "Materials declared per part (compliance and recycling)", {"type": "attr", "kind": "parts", "key": "material", "min_share": 0.6}),
  it("DFE-03", "Battery removable for recycling and replacement"),
  it("DFE-04", "Energy consumption in use measured against a target"),
  it("DFE-05", "End-of-life disassembly path considered (disposal requirements)", {"type": "req_type", "req": "DISP", "n": 1})]),
 "emc": dict(name="Design for EMC & Electrical Compliance", short="DfEMC", focus="compliance", standard="FCC Part 15, CISPR 32/35, IEC 61000-4-x, UL/IEC 62368-1", items=[
  it("DFEMC-01", "EMC / radio regulations in the regulatory set", {"type": "regulation", "pattern": "FCC|CISPR|61000|RED|ETSI"}),
  it("DFEMC-02", "Electrical safety standard identified (UL/IEC 62368-1, 60335, 2849…)", {"type": "regulation", "pattern": "62368|60335|2849|UL "}),
  it("DFEMC-03", "Pre-compliance EMC tests planned", {"type": "tests_method", "pattern": "EMC|emission|immunity|ESD", "n": 1}),
  it("DFEMC-04", "Grounding, shielding and cable-routing strategy documented")]),
 "security": dict(name="Design for Security (DfSec)", short="DfSec", focus="software", standard="IEC 62443, ETSI EN 303 645, NIST IR 8259, EU Cyber Resilience Act", items=[
  it("DFSEC-01", "Security requirements exist (authentication, update integrity, data)", {"type": "req_type", "req": "SEC", "n": 1}),
  it("DFSEC-02", "Connected-product cybersecurity regulation in the set (CRA, EN 303 645, RED art. 3.3)", {"type": "regulation", "pattern": "303 645|CRA|Cyber|62443"}),
  it("DFSEC-03", "Threat model: external interfaces (radio, USB, cloud) assessed"),
  it("DFSEC-04", "Signed firmware and secure boot; configuration cannot be changed without authorisation"),
  it("DFSEC-05", "Offline degradation: product remains safe and usable without the cloud")]),
 "usability": dict(name="Design for Usability & Ergonomics", short="DfU", focus="systems", standard="ISO 9241-210, IEC 62366, ISO 6385", items=[
  it("DFU-01", "Actors and use cases modelled for primary and secondary users", {"type": "collection", "kind": "use_cases", "n": 3}),
  it("DFU-02", "Usability requirements with measurable attributes", {"type": "req_type", "req": "USAB", "n": 1}),
  it("DFU-03", "Formative usability test planned", {"type": "tests_method", "pattern": "usability|user study|formative", "n": 1}),
  it("DFU-04", "Error states and recovery visible to the user (HMI covers fault states)")]),
 "quality": dict(name="Design for Quality (DfQ)", short="DfQ", focus="quality", standard="ISO 9001, IATF 16949, AIAG CQI", items=[
  it("DFQ-01", "Design reviews held at each gate (reviews recorded)", {"type": "collection", "kind": "reviews", "n": 1}),
  it("DFQ-02", "No open critical or major findings", {"type": "coverage", "key": "open_findings_critical", "max": 0}),
  it("DFQ-03", "Critical characteristics flow from DFMEA to PFMEA to control plan"),
  it("DFQ-04", "Measurement system analysis planned for critical characteristics")]),
 "supply_chain": dict(name="Design for Supply Chain", short="DfSC", focus="sourcing", standard="industry practice", items=[
  it("DFSC-01", "Buy parts have a supplier", {"type": "coverage", "key": "buy_parts_without_supplier", "max": 0}),
  it("DFSC-02", "Part lifecycle status known (active / NRND / EOL)", {"type": "attr", "kind": "parts", "key": "lifecycle", "min_share": 0.6}),
  it("DFSC-03", "Single-source parts identified with a second source or risk"),
  it("DFSC-04", "Lead times captured for long-lead parts", {"type": "attr", "kind": "parts", "key": "lead_time_weeks", "min_share": 0.3})]),
}
for k, v in X.items(): yaml.safe_dump({"id": k, **v}, open(os.path.join(H, k + ".yaml"), "w"), sort_keys=False, allow_unicode=True)
print(len(X), "sets written")
