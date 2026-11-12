# Kiln — liquid-cooled accelerator rack (reconstructed; fictional name)

Reconstructed from Anthropic postings (Hardware Systems Architect: package → board → chassis → rack → interconnect → power →
cooling → datacenter interface; scale-up/scale-out fabric; 48V/HVDC; direct liquid cooling; BMC, secure boot, attestation;
fleet RAS. Manufacturing Engineer, Data Center Hardware: racks, servers, accelerator systems at CM/ODM; cold plates,
manifolds, CDUs, leak and fill test; PFMEA, control plans, SPC, pilot builds, second-site qualification) and from OpenAI's
Stargate manufacturing-test and rack-quality postings. Nothing here is confirmed by either company.

- 42U rack, 8 accelerator trays × 8 accelerators (partner silicon: GPU/TPU/custom), 2 host/NIC trays, 2 scale-up switch trays, direct-to-chip liquid cooling with rack manifold and quick disconnects, facility CDU interface.
- Power: 48V busbar from rack power shelves (HVDC-ready), ~120 kW per rack; per-tray hot-swap; 12 V/48 V derating policy.
- Interconnect: scale-up copper/optical within rack, scale-out 800G optics to the pod; PCIe/CXL to host; BMC on every tray; secure boot and attestation; telemetry to fleet health.
- Reliability: failure budget per 1,000 nodes, serviceability (tray swap < 15 min), leak detection and shutdown, RAS.
- Manufacturing: CM/ODM box build and rack integration; tests: leak/fill, hipot and ground bond on power shelves, burn-in, FCT, fabric link BER; takt and FPY targets; second-site qualification.
- Regulatory: UL 62368-1 / IEC 62368-1 for ITE, IEC 60950-style safety for power shelves, FCC 15A, CE EMC (EN 55032/55035), RoHS/REACH, liquid-cooling fluid compatibility and leak safety (OCP guidance), seismic rating.
