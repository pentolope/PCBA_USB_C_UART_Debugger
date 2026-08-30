# Architecture — USB-C UART Debug Adapter

**A worksheet, not a design.** Every line below is a question this board has to
answer, and none of them is answered here. Nothing in this file is a
recommendation, and the order of the sections carries no preference.

The questions were derived from [the brief](../BRIEF.md) and from what this
board is meant to stress in the benchmark:

- USB 2.0 differential routing
- ESD
- USB-C CC resistors
- small QFN

Those are the places where a wrong answer shows up in copper.

Answer them in this file as the design is made, each answer carrying the
evidence that supports it, and record the corresponding choice against its
`OPEN-nn` entry in [board/requirements.md](../board/requirements.md). An answer
without evidence is a guess wearing a document's clothes — and this benchmark is
allowed to refuse an unsupported claim rather than invent one.

## USB-C receptacle and the device-side CC network

- Which receptacle variant is used, and what does its datasheet require for footprint, keepout and shell retention?
- What device-side CC termination does the USB Type-C specification require, on which pins is it fitted, and what value and tolerance does the specification set for the current level this board is designed to draw?
- Does the CC implementation work identically in both cable orientations, and how is that demonstrated?
- Is any current level advertised to the source, and if not, what does the board rely on getting?
- Are the SBU, VCONN and unused pins terminated, left open, or deliberately not routed — and why?
- How is the shell/shield connected to board ground, and what evidence supports that choice?

## USB-UART bridge selection

- Which bridge is chosen, and what evidence shows it is "commonly available" rather than merely well known?
- Does the device natively support USB 2.0 Full-Speed operation without an external PHY?
- What does its datasheet require for supply rails, reset, configuration pins and any clock source?
- Does it provide RTS/CTS natively, and at what logic level relative to the required 3.3 V?
- What package does it come in, and what land pattern, paste-mask and thermal-pad treatment does the datasheet specify?
- What is its supply current, and does that fit inside the bus-power budget assumed for this board?

## USB 2.0 Full-Speed differential routing under the two-layer preference

- What differential impedance is targeted for D+/D-, and on what basis is that target chosen?
- What trace width, spacing and reference geometry produce that impedance on the chosen stackup, and what tool or formula produced the numbers?
- How is the approximation's uncertainty stated — what is genuinely controlled versus estimated?
- What is the routed length of the pair, and how are intra-pair skew and matching handled?
- Is the reference under the pair continuous for its whole length, and what happens at the connector, the ESD device and the bridge pins?
- What discontinuities does the pair cross (vias, component pads, plane splits), and how is each justified?

## ESD and port protection

- Which nets are protected, and why were the unprotected nets judged not to need it?
- What ESD device is chosen, and what does its datasheet state for line capacitance, clamping voltage and dynamic resistance?
- Is the device capacitance low enough not to degrade Full-Speed signalling, and what evidence supports that?
- How close to the connector is the protection actually placed in the layout, and what is the discharge path from device to ground?
- What ESD immunity level is being claimed, against which test standard, and is that claim substantiated or aspirational?
- Are the target-side signals exposed to the outside world too, and does that change the protection requirement?

## Power path, bus power budget and the 3V3 rail

- Where does the 3.3 V rail come from, and what is its maximum load including anything the target may draw from the 3V3 pin?
- What is the total board current from VBUS, and does it stay inside the power the board is entitled to draw?
- Is the 3V3 pin a reference only or a usable supply, and how is that documented on the silkscreen and in the pinout?
- What protection exists if a target back-feeds the 3V3 pin or shorts it to ground?
- What bulk and local decoupling values are used, at which pins, and what does the bridge datasheet ask for?
- Is any inrush or hot-plug behaviour on VBUS considered?

## Target-side header and signal set

- Is the header 0.1-inch or a compact locking type, and what drove that choice?
- What is the pin order, and how is TX/RX direction labelled so a user cannot mis-wire it?
- Is RTS/CTS provided at all, and what does "optional" mean for it mechanically and electrically — populated pins, DNP parts, jumpers or a build variant — and what pinout consequences follow?
- What logic level and drive strength do the target-facing signals present, and are series resistors or level protection warranted?
- What is the connector's current rating relative to whatever the 3V3 pin may deliver?
- Is the header keyed or polarised, and what happens on reverse insertion?

## Connector separation and mechanical form

- What board outline and size are chosen, and what constrains them?
- How far apart are the USB and target-side connectors, and what makes that separation "clear" in practical use?
- Where do the two connectors sit relative to each other, and does the resulting routing keep the differential pair short?
- Are mounting holes, strain relief or an enclosure assumed, and if so on what basis?
- Does the receptacle overhang, mid-mount cutout or shell keepout impose anything on the outline?

## Stackup, impedance approximation and its documentation

- What is the exact stackup — copper weight, dielectric thickness, dielectric constant, surface finish — and where do those numbers come from?
- If the chosen layer count cannot deliver the impedance target, is the two-layer preference departed from, or is the deviation accepted and documented?
- What exactly is being claimed about impedance: a controlled value the fabricator will verify, or an approximation the design accepts?
- Where in the repository is the approximation recorded so a reviewer can reproduce it?
- What tolerance does the fabricator quote on the parameters the impedance depends on?

## Grounding and decoupling

- What ground strategy does the chosen stackup allow, and — if the two-layer preference is kept — which areas of the board still get an intact reference?
- Which pins get local decoupling, at what value, and what does the bridge datasheet require?
- Where do the decoupling capacitor return vias sit relative to the pins they serve?
- Is there a separate quiet region near the USB port, and if so, how are the ground regions tied?
- How does the target-side cable's ground return interact with the USB-side ground?

## Manufacturability and sourcing

- Which fabricator and process are assumed, and what are their minimum trace, space, drill and annular-ring limits?
- Does the layout stay inside those limits, especially around the bridge package and the receptacle footprint?
- Is assembly single- or double-sided, and does the component placement match?
- What evidence supports the availability claim for every part, not just the bridge?
- If the chosen parts are fine-pitch, what stencil, paste or reflow accommodation do their datasheets call for?

## Bring-up and verification

- What is the minimum test that proves operation as a Full-Speed device on a real host?
- How is the CC network verified — measured, or inferred from the schematic?
- What loopback or target-side test proves TX, RX and, if fitted, RTS/CTS actually work?
- What test points or probe access does the layout provide for D+/D-, VBUS and the 3.3 V rail?
- Which claims in the design documentation are measured, which are simulated, and which are cited from a datasheet?

## Answers still owed

All of them. See [status.md](status.md).
