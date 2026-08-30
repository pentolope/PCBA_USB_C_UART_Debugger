# Requirements — USB-C UART Debug Adapter

Two lists. The difference between them is the whole point of this file.

A **fixed requirement** is something [BRIEF.md](../BRIEF.md) asks for. Each one
below quotes the brief text that substantiates it; if a statement cannot be
quoted, it is not a requirement here. An **open decision** is a choice the brief
deliberately left to whoever designs this board.

> Missing details are design freedom, not permission to fabricate unstated user
> requirements.

Promoting a decision into a requirement is the failure this file exists to
prevent. Record a choice under the decision it answers, with the reasoning that
made it — never by adding it to the list above.

Bound to `BRIEF.md` SHA-256 `0c5897542317b8fdc90d1251febe01efa33c86589f59024910c426d053b9a461`.

## Fixed by the brief

### REQ-01 — The board is a USB-C to UART debug adapter operating at a 3.3 V UART level.

Brief text:

> Create a USB-C to 3.3 V UART debug adapter.

### REQ-02 — It must be a USB 2.0 Full-Speed device.

Brief text:

> It must be a USB 2.0 Full-Speed device, bus-powered

### REQ-03 — It must be bus-powered; the brief names no other supply input.

Brief text:

> 3.3 V UART debug adapter. It must be a USB 2.0 Full-Speed device, bus-powered

### REQ-04 — The target-side header must expose TX, RX, GND and a 3V3 reference.

Brief text:

> expose TX, RX, GND, 3V3 reference, and optional RTS/CTS on a 0.1-inch or compact locking header

### REQ-05 — RTS/CTS is optional, not required: the brief permits it on the target-side header alongside the mandatory signals, and a design that omits it is still compliant.

Brief text:

> and optional RTS/CTS on a 0.1-inch or compact locking header.

### REQ-06 — The target-side header must be either a 0.1-inch header or a compact locking header; the brief permits either.

Brief text:

> optional RTS/CTS on a 0.1-inch or compact locking header.

### REQ-07 — A correct USB-C device-side CC network must be included.

Brief text:

> Include the correct USB-C device-side CC network

### REQ-08 — USB ESD protection must be included and physically placed close to the connector.

Brief text:

> USB ESD protection close to the connector, local decoupling

### REQ-09 — Local decoupling must be provided.

Brief text:

> local decoupling, and clearly separated USB and target-side connectors.

### REQ-10 — The USB connector and the target-side connector must be clearly separated on the board.

Brief text:

> clearly separated USB and target-side connectors. Choose a commonly available USB-UART bridge.

### REQ-11 — The USB-UART bridge chosen must be a commonly available part.

Brief text:

> Choose a commonly available USB-UART bridge.

### REQ-12 — Two layers are preferred for the stackup; the brief states a preference, not a mandate.

Brief text:

> Prefer two layers, but route D+/D- as a deliberate differential pair

### REQ-13 — D+/D- must be routed as a deliberate differential pair, not as two ordinary nets.

Brief text:

> route D+/D- as a deliberate differential pair and document any impedance approximation.

### REQ-14 — Any impedance approximation used for the differential pair must be documented.

Brief text:

> as a deliberate differential pair and document any impedance approximation.

### REQ-15 — Stated requirements are authoritative; open choices must be made and documented as engineering decisions rather than presented as user requirements.

Brief text:

> Treat stated requirements as authoritative; where the brief leaves choices open, make and document reasonable engineering decisions rather than inventing hidden user requirements.

### REQ-16 — The repository should remain a consumer of the shared PCBA_AutoDesignAndTest toolkit rather than accumulating board-specific logic in the toolkit.

Brief text:

> The repository should remain a consumer of the shared `PCBA_AutoDesignAndTest` toolkit rather than accumulating board-specific logic in the toolkit.

## Open — the design agent decides

### OPEN-01 — Which USB-UART bridge device to use.

The brief requires only that the bridge be "commonly available" and names no manufacturer, part number or family.

*Decision:* **not yet made.**

### OPEN-02 — The bridge's package, and how its land pattern, thermal pad (if any) and assembly process are handled.

The brief names no package. "small QFN" appears only in the benchmark header block and in metadata as a stressor, never in the design brief's requirements, so whether the chosen bridge is a QFN at all is a design outcome.

*Decision:* **not yet made.**

### OPEN-03 — Which USB-C receptacle to use — pin count, SMT versus through-hole, vertical/horizontal/mid-mount, retention scheme.

The brief says "USB-C" and nothing about the receptacle variant or mounting style.

*Decision:* **not yet made.**

### OPEN-04 — The concrete implementation of the device-side CC network: what termination the USB Type-C specification requires for a device of this kind, on which pins, at what value and tolerance, and how both cable orientations are handled.

The brief demands a "correct" CC network but states no values, tolerances or topology; correctness is defined by the USB Type-C specification, which the design must cite rather than assume.

*Decision:* **not yet made.**

### OPEN-05 — The ESD protection strategy: discrete devices versus an array, which nets are protected (D+/D-, VBUS, CC, target-side signals), and the target ESD immunity level.

The brief requires "USB ESD protection close to the connector" but names no device, no protected-net list beyond USB, and no immunity level or test standard.

*Decision:* **not yet made.**

### OPEN-06 — How the 3.3 V rail and the 3V3 reference pin are generated — bridge internal regulator, external regulator, or otherwise.

The brief fixes 3.3 V as the UART level and requires a 3V3 reference pin, but is silent on where that rail comes from.

*Decision:* **not yet made.**

### OPEN-07 — Whether the 3V3 pin may source current to the target, and if so what current limit, protection or fusing applies.

The brief calls it a "3V3 reference" without specifying whether it is an output rail, and states no current budget.

*Decision:* **not yet made.**

### OPEN-08 — The VBUS input budget, the current level (if any) advertised to the source, and whether input protection (fuse, current limit, reverse protection, bulk capacitance) is included.

The brief says only "bus-powered" and specifies no current draw, protection or advertised current level.

*Decision:* **not yet made.**

### OPEN-09 — The target header pinout, pin order, pin count and — if the compact locking option is taken — which connector family and pitch.

The brief fixes the mandatory signal set and offers two header styles but does not choose between them, fix a pin order, or name a connector.

*Decision:* **not yet made.**

### OPEN-10 — Whether RTS/CTS is provided at all and, if it is, how its optionality is expressed: always-populated extra pins, do-not-populate parts, jumpers, or a build variant.

The brief marks RTS/CTS optional without requiring it or saying what optionality means mechanically or electrically.

*Decision:* **not yet made.**

### OPEN-11 — Board outline, dimensions, mounting holes, and whether the board is a bare dongle, an inline adapter or an enclosed unit.

The brief is silent on mechanical form beyond requiring that the two connectors be clearly separated.

*Decision:* **not yet made.**

### OPEN-12 — How much separation between the USB and target-side connectors counts as "clearly separated", and how that is justified.

The brief states the requirement qualitatively and gives no distance, keepout or creepage figure.

*Decision:* **not yet made.**

### OPEN-13 — Whether to actually use two layers or depart from that preference, and the full stackup: copper weight, dielectric thickness, dielectric constant, finish.

"Prefer two layers" is a preference, and the brief gives no stackup parameters; metadata's layer count is a likelihood, not a mandate.

*Decision:* **not yet made.**

### OPEN-14 — The differential impedance target for D+/D-, the method used to approximate it on the chosen stackup, and the trace geometry that follows.

The brief requires a documented impedance approximation but states no target value, tolerance, or calculation method.

*Decision:* **not yet made.**

### OPEN-15 — The grounding strategy on whatever stackup is chosen — how continuous a reference the differential pair gets, and how that is traded against routing the rest of the board.

The brief is silent on planes or return-path strategy; it follows only indirectly from the layer preference and the differential-pair requirement.

*Decision:* **not yet made.**

### OPEN-16 — Whether to include status/activity indication, additional broken-out control lines (for example a reset or bootloader line), test points, or bridge configuration such as descriptors and stored settings.

The brief mentions none of these; adding them is allowed as design freedom but must not be presented as a user requirement.

*Decision:* **not yet made.**

### OPEN-17 — Fabricator and assembly process selection, and the capability limits (minimum trace/space, drill, annular ring, single- versus double-sided assembly) the layout must respect.

The brief names no fabricator, process or capability set; "commonly available" constrains the bridge, not the process.

*Decision:* **not yet made.**

## Where a decision gets recorded

1. Answer it under its `OPEN-nn` heading above, with the reasoning and the
   evidence that made the choice.
2. Set `chosen` and `rationale` on the matching entry in
   [requirements.json](requirements.json).
3. Cite the datasheet or standard in [docs/sources.md](../docs/sources.md).

A choice recorded this way stays visibly a choice. That is what lets a later
reader tell this board's engineering apart from its brief.

## Where this board is most likely to be faked

Places where a design run would be tempted to assert something it cannot
substantiate:

- The impedance claim is the softest spot. The brief asks only for a documented approximation, which makes it easy to state a differential impedance number with no stackup, no calculator output and no fabricator data behind it. Any number must be traceable to a stated dielectric thickness and Er.
- "Correct CC network" invites assertion. The termination type, pin assignment, value and tolerance must be cited from the Type-C specification, and both cable orientations must be shown to work — not declared correct because a resistor exists.
- ESD protection is a stressor, not a chosen part. Picking a device without checking its line capacitance against Full-Speed signalling, or claiming an immunity level with no test standard and no datasheet backing, is the classic failure here.
- The 3V3 pin's current budget is easy to overstate. Whether it can power a target depends on the rail's actual source and the bus power the board is entitled to draw; both need real numbers, not an assumed allowance.
- "Commonly available" is a verifiable claim. Asserting availability from familiarity, without stock or lifecycle evidence, fails the requirement while appearing to satisfy it.
- If the chosen bridge comes in a fine-pitch package, its land pattern, paste treatment and process capability must come from the datasheet and the fabricator, not from the assumption that small QFNs are routine.
- The brief is silent on outline, dimensions, enclosure, indicator LEDs, auto-reset control lines and every connector part number. Introducing any of these as a requirement rather than a documented design decision corrupts the benchmark.
- The brief's modality must survive into the design. RTS/CTS is optional and two layers is a preference; restating either as a hard requirement — or inventing a specific clearance figure for "clearly separated" and presenting it as stated — is over-capture, and dropping them entirely is under-capture.
