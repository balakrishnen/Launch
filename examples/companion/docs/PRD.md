# Hearth — AI companion speaker (reconstructed; fictional name)

Reconstructed from OpenAI job postings (Consumer Devices: camera software, connectivity, RTOS firmware, on-device transformers,
system power, system performance, release engineering, hardware exploratory & product manufacturing in Singapore, device
safety & risk operations) and press reports (MacRumors 2026-07-28 relaying Bloomberg/Kuo: screenless portable speaker developed
with Jony Ive, rechargeable, camera for context, mechanical elements that move, GPT-Live conversation, smart-home control,
$200–300, early 2027). Nothing here is confirmed by the company; it is a plausible systems model to exercise Launch.

- Portable screenless speaker, 1.2 kg class, rechargeable; carried room to room; always-listening wake and conversation via cloud LLM with an on-device transformer for wake/VAD/intent and fallback.
- Sensing: 4-mic array with beamforming and AEC, wide-angle camera for scene context (privacy shutter + LED), ambient light, IMU (pick-up / orientation).
- Expression: a small motorised element ("alive") — 2 actuators, haptic, light ring; full-range driver + passive radiator.
- Connectivity: Wi-Fi 6, BLE, Thread/Matter for smart home, USB-C PD charging.
- Compute: application SoC with NPU, 8 GB LPDDR, eMMC; RTOS co-processor for always-on audio and power sequencing.
- Power: 20 Wh Li-ion pack, 8 h active / 24 h standby, 25 W USB-C PD; thermal envelope silent (no fan).
- Regulatory: FCC 15B/15C, RED (EN 300 328, EN 18031 cybersecurity), IEC 62368-1 safety, IEC 62133-2 / UN 38.3 battery, RoHS/REACH/WEEE, CA Prop 65, Matter certification, audio EN 50332 not applicable; privacy: camera/mic indicators by design, child-safety (CPSC) not toy-classified.
- Manufacturing: CM in Vietnam/China (Luxshare reported for a sibling device), EoL: audio chamber test, camera MTF, RF test, battery charge/discharge, OTA provisioning. Target 2M units first year.
