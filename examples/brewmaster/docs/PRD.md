# BrewMaster One — product brief (fictional smart drip coffee maker)

A 10-cup connected drip coffee maker for the US and EU, $179 retail, launching at a 1,000-person appliance company as the first
product of a new "connected kitchen" platform. The platform (controller, Wi-Fi/BLE module, HMI, app, cloud) will be reused by a kettle and a grinder.

## Consumer and use
- Household, 1–4 people; brews 1–10 cups (150–1,500 ml); schedule a brew from the app or the dial; strength and temperature profiles.
- Target "Golden Cup" extraction: water at 92–96 °C at the shower head, 4–6 min brew for 10 cups, ≥18 % extraction.
- Keep-warm plate or thermal carafe (variants); auto shut-off; descale reminders from a water hardness sensor.

## Architecture
- Water system: 1.6 L reservoir with level sensor, inlet valve (plumbed variant later), pump (vibration pump 15 bar not needed — gravity-fed drip with thermoblock), flow meter.
- Thermal system: 1,400 W thermoblock heater with NTC, thermal cutoff (TCO) and PTC, triac control; shower head; keep-warm plate 60 W.
- Brew system: brew basket with #4 filter, shower head pattern, drip-stop valve, carafe 1.5 L glass or 1.2 L thermal.
- Controls: main board with MCU (IEC 60730 class B software), Wi-Fi/BLE module (pre-certified), mains PSU 5 V/3.3 V, triac driver, sensors; HMI board with 2.4" display and dial; app + cloud.
- Enclosure: PP housing, stainless trim, cord with NEMA 5-15 / Schuko variants, GFCI not integrated.

## Regulatory context (US + EU)
- Safety: UL 1082 (US), IEC/EN 60335-1 + 60335-2-15 (EU), IEC 60730-1 Annex H class B for the thermal control software.
- EMC/radio: FCC 15B + 15C (module), EN 55014-1/-2, IEC 61000-3-2/-3-3, RED 2014/53/EU incl. art. 3.3 cybersecurity (EN 18031).
- Food contact: FDA 21 CFR 174–178, EU 1935/2004 + 10/2011; California Prop 65.
- Energy: EU ecodesign standby (≤0.5 W), DOE/ENERGY STAR if claimed. Environmental: RoHS, REACH, WEEE.

## Manufacturing and service
- Contract manufacturer in Vietnam; injection-molded housing; PCBA from an EMS partner; EoL test: hipot, ground bond, functional brew (water), Wi-Fi provisioning.
- Service: descaling, user-replaceable carafe and filter basket; field-replaceable main board; 2-year warranty; FRACAS from service centers and app telemetry.

## Teams (subsystem + functional)
Brew performance · Thermal & water · Controls & connectivity · Industrial design & enclosure · Reliability & safety · Compliance · Test · Manufacturing · Sourcing · Program.
