"""Native EDA — the electrical side of the thread as a board. From the model: electrical parts become components (with MPN,
supplier, package from attrs), electrical interface items become nets (power rails, buses, signals), connectors come from
boundary interfaces, test points from DfT. Produces: the board brief (for an EE or an EDA copilot such as CopperPilot/Quilter),
the netlist as a KiCad .net export (import into KiCad PCB layout / Altium), BOM vs AVL, and checks against the thread.
Schematic capture itself stays in KiCad/Altium (or the agent writes SKiDL when a symbol library is configured)."""
from __future__ import annotations
import re, time
from . import derive as D

ELEC = ("electrical", "firmware", "software")
RAIL = re.compile(r"(\d+(?:\.\d+)?)\s*V|VBAT|VBUS|GND|3V3|5V|12V|48V|PGND|AGND", re.I)
BUS = re.compile(r"CAN|I2C|SPI|UART|USB|ETH|LIN|PWM|JTAG|SWD|BLE|LTE|GNSS", re.I)

def _is_elec_iface(v): return any(k in (v.get("kind") or "").lower() for k in ("elec", "can", "usb", "i2c", "spi", "uart", "signal", "power", "48", "12 v", "5 v", "lte", "ble", "rf"))

def netlist(m: dict, scope: list[str] | None = None) -> dict:
    parts = {p: v for p, v in m["parts"].items() if v.get("discipline") in ELEC and not v.get("context") and (not scope or p in scope)}
    comps = {}; nets = {}; n = 0
    for p, v in parts.items():
        a = v.get("attrs") or {}
        comps[p] = {"ref": a.get("ref") or _ref(p, v), "value": v.get("name"), "mpn": a.get("mpn") or a.get("part_number") or "", "supplier": v.get("supplier") or "", "package": a.get("package") or "", "make_buy": v.get("make_buy"), "lifecycle": v.get("lifecycle", ""), "pins": []}
    for i, v in m["interfaces"].items():
        if not _is_elec_iface(v): continue
        a, b = v.get("a"), v.get("b")
        if a not in parts and b not in parts: continue
        for item in v.get("items") or [v.get("name") or i]:
            kind = "power" if RAIL.search(item) else ("bus" if BUS.search(item) else "signal")
            net = nets.setdefault(item, {"name": item, "kind": kind, "interfaces": [], "pins": [], "voltage": (RAIL.search(item).group(0) if RAIL.search(item) and kind == "power" else "")})
            net["interfaces"].append(i)
            for side in (a, b):
                if side in comps:
                    n += 1; pin = {"comp": side, "ref": comps[side]["ref"], "pin": f"{item}", "num": len(comps[side]["pins"]) + 1}
                    comps[side]["pins"].append({"num": pin["num"], "name": item, "net": item, "iface": i}); net["pins"].append(pin)
                else:   # the other side is not an electrical part (mechanical/external) → connector pin on this board edge
                    net.setdefault("external", []).append(side)
    tps = [p for p, v in parts.items() if (v.get("attrs") or {}).get("test_points")]
    return {"components": comps, "nets": nets, "test_points": tps, "n_components": len(comps), "n_nets": len(nets), "n_pins": sum(len(c["pins"]) for c in comps.values())}

def _ref(p, v):
    nm = (v.get("name") or "").lower(); t = (v.get("type") or "").lower()
    pre = "J" if "connector" in nm or "port" in nm else "U" if any(k in nm + t for k in ("mcu", "controller", "module", "unit", "bms", "driver", "soc", "asic", "radio", "telematics")) else "BT" if "batt" in nm or "pack" in nm else "M" if "motor" in nm or "generator" in nm else "DS" if "display" in nm or "led" in nm or "light" in nm else "A"
    return pre + str(abs(hash(p)) % 90 + 10)

def kicad_net(m: dict, nl: dict, title: str) -> str:
    L = [f'(export (version "E")', f'  (design (source "launch:{title}") (date "{time.strftime("%Y-%m-%d %H:%M")}") (tool "Launch native EDA"))', "  (components"]
    for p, c in nl["components"].items():
        L.append(f'    (comp (ref "{c["ref"]}") (value "{_q(c["value"])}") (footprint "{_q(c["package"])}") (fields (field (name "MPN") "{_q(c["mpn"])}") (field (name "Supplier") "{_q(c["supplier"])}") (field (name "LaunchId") "{p}")) (sheetpath (names "/") (tstamps "/")) (tstamp "{p}"))')
    L.append("  )"); L.append("  (nets")
    for k, (name, net) in enumerate(nl["nets"].items(), 1):
        L.append(f'    (net (code "{k}") (name "{_q(name)}")'); L += [f'      (node (ref "{pin["ref"]}") (pin "{pin["num"]}") (pinfunction "{_q(pin["pin"])}"))' for pin in net["pins"]]; L.append("    )")
    L.append("  )"); L.append(")")
    return "\n".join(L)
def _q(s): return str(s or "").replace('"', "'")

def checks(m: dict, nl: dict) -> list[dict]:
    out = []; comps = nl["components"]; nets = nl["nets"]
    noitems = [i for i, v in m["interfaces"].items() if _is_elec_iface(v) and not v.get("items")]
    out.append({"check": "every electrical interface defines its items (nets)", "ok": not noitems, "measured": f"{len(noitems)} without items", "ids": noitems[:10]})
    dang = [n for n, v in nets.items() if len(v["pins"]) < 2 and not v.get("external")]
    out.append({"check": "no net with a single pin (dangling)", "ok": not dang, "measured": f"{len(dang)} dangling", "ids": dang[:10]})
    nogr = not any(re.search(r"GND|PGND|AGND|return", n, re.I) for n in nets)
    out.append({"check": "a ground / return net exists", "ok": not nogr, "measured": "none found — add GND to the power interfaces' items" if nogr else "ok"})
    nomp = [p for p, c in comps.items() if c["make_buy"] == "buy" and not c["mpn"]]
    out.append({"check": "buy components carry an MPN", "ok": not nomp, "measured": f"{len(nomp)} without MPN", "ids": nomp[:10]})
    nosup = [p for p, c in comps.items() if c["make_buy"] == "buy" and not c["supplier"]]
    out.append({"check": "buy components have a supplier (AVL)", "ok": not nosup, "measured": f"{len(nosup)} without supplier", "ids": nosup[:10]})
    eol = [p for p, c in comps.items() if (c["lifecycle"] or "").upper() in ("EOL", "NRND", "OBSOLETE")]
    out.append({"check": "no EOL / NRND components", "ok": not eol, "measured": f"{len(eol)} at risk", "ids": eol[:10]})
    notp = [p for p, c in comps.items() if c["ref"].startswith("U") and p not in nl["test_points"]]
    out.append({"check": "boards/modules declare test points (DfT)", "ok": not notp, "measured": f"{len(notp)} without attrs.test_points", "ids": notp[:10]})
    hv = [n for n, v in nets.items() if v["kind"] == "power" and (lambda mm: mm and float(mm.group(1) or 0) >= 48)(re.search(r"(\d+(?:\.\d+)?)\s*V", n, re.I))]
    if hv:
        regs = [r for r, v in m["regulations"].items() if re.search(r"2849|62368|60335|61010", v.get("name", "") + v.get("standard", ""))]
        out.append({"check": f"≥48 V nets ({', '.join(hv[:3])}) covered by an electrical safety standard", "ok": bool(regs), "measured": ", ".join(regs) or "no UL/IEC electrical safety standard in the regulatory set", "ids": hv})
    fms = [x for x in D.fmea(m) if x.get("AP") == "H" and x.get("element") in comps]
    out.append({"check": "High-AP failure modes on components have a detecting test", "ok": all(x.get("tests") for x in fms), "measured": f"{len([x for x in fms if not x.get('tests')])} of {len(fms)} without a test", "ids": [x["id"] for x in fms if not x.get("tests")][:10]})
    return out

def board_brief(m: dict, nl: dict, part: str | None = None) -> str:
    comps = nl["components"]; nets = nl["nets"]
    L = [f"# Board brief — {part or 'electrical architecture'}", ""]
    if part and part in comps:
        c = comps[part]; L += [f"**{part}** {c['value']} · ref {c['ref']} · {c['make_buy']}{' · ' + c['supplier'] if c['supplier'] else ''}", "", "## Nets on this component"]
        L += [f"- {p['name']} ({nets[p['name']]['kind']}{', ' + nets[p['name']]['voltage'] if nets[p['name']]['voltage'] else ''}) via {p['iface']} → " + ", ".join(sorted({q['ref'] + ' ' + q['comp'] for q in nets[p['name']]['pins'] if q['comp'] != part}) or ['external']) for p in c["pins"]] or ["- none — add items to this part's electrical interfaces"]
    else:
        L.append("## Components"); L += [f"- {c['ref']} {p} {c['value']}{' · ' + c['mpn'] if c['mpn'] else ''}" for p, c in comps.items()]
        L.append("\n## Nets"); L += [f"- {n} [{v['kind']}] " + ", ".join(sorted({q['ref'] for q in v['pins']})) + (" + external " + ", ".join(v['external']) if v.get('external') else "") for n, v in nets.items()]
    L.append("\n## Power rails"); L += [f"- {n}{' ' + v['voltage'] if v['voltage'] else ''}" for n, v in nets.items() if v["kind"] == "power"] or ["- none identified — name rails in interface items (e.g. VBAT_48V, 3V3, GND)"]
    L.append("\n## Requirements that bound the electronics")
    for p in ([part] if part else list(comps)):
        for f, fv in m["functions"].items():
            if p in fv.get("alloc", []):
                for r in fv.get("reqs", []): L.append(f"- {r} {m['requirements'][r]['text'][:120]}" + (f" → **{m['requirements'][r]['attr']}**" if m['requirements'][r].get('attr') else ""))
    regs = [f"- {r}: {v['name']}" for r, v in m["regulations"].items() if re.search(r"FCC|CISPR|EMC|UL|IEC|RED|ETSI|2849|62368", v.get("name", "") + v.get("standard", ""))]
    if regs: L.append("\n## EMC / electrical safety"); L += regs
    L.append("\n## Deliver back"); L.append("- Schematic (KiCad/Altium), layout, BOM with MPNs → attach to the part with roles schematic / layout; test points for every net in attrs.test_points; results of ERC/DRC as a finding if any.")
    return "\n".join(L)


def wire_list(m: dict, nl: dict) -> str:
    """CSV wire list (one row per net segment between two components) for harness tools (HarnessHive import, Capital, E3)."""
    rows = ["from_ref,from_part,from_pin,to_ref,to_part,to_pin,signal,kind,voltage,interface"]
    for n, v in nl["nets"].items():
        pins = v["pins"]
        for i in range(len(pins) - 1):
            a, b = pins[i], pins[i + 1]
            rows.append(",".join(str(x).replace(",", ";") for x in [a["ref"], a["comp"], a["num"], b["ref"], b["comp"], b["num"], n, v["kind"], v.get("voltage", ""), a.get("iface", "")]))
        for ext in v.get("external", []):
            for a in pins: rows.append(",".join(str(x).replace(",", ";") for x in [a["ref"], a["comp"], a["num"], "EXT", ext, "", n, v["kind"], v.get("voltage", ""), a.get("iface", "")]))
    return "\n".join(rows)
