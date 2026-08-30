# Sources — USB-C UART Debug Adapter

The evidence this board's design will have to cite. **Classes of document, not
documents:** the specific parts are not chosen yet, so naming a datasheet here
would be choosing one.

A number that reaches the board carries its provenance: source, document id or
URL, retrieval date, units, and the condition it applies under. A number without
that is not evidence, and no live network lookup may change a validation or
release result.

| Kind of source | What the design needs from it |
|---|---|
| USB 2.0 specification | Full-Speed signalling requirements, D+/D- differential impedance expectation, and the pair-routing constraints the brief's "deliberate differential pair" requirement is measured against. |
| USB Type-C cable and connector specification | Defines what a "correct" device-side CC network is — termination type, pin assignment, value and tolerance, orientation handling, receptacle pinout — which the brief asserts but does not specify. |
| USB-UART bridge datasheet | Pinout, package and recommended land pattern, supply rails and current, internal regulator capability, clock requirements, decoupling requirements, and native flow-control support. |
| Distributor stock and lifecycle data | The only way to substantiate the brief's "commonly available" requirement for the bridge rather than asserting it. |
| USB-C receptacle datasheet and mechanical drawing | Footprint, keepouts, mounting/retention, shell grounding and any cutout the board outline must accommodate. |
| ESD protection device datasheet | Line capacitance versus Full-Speed signal integrity, clamping voltage, and the manufacturer's placement guidance for "close to the connector". |
| ESD immunity test standard (e.g. IEC 61000-4-2 class references) | Any stated ESD level needs a defined test condition behind it; the brief requires protection but names no level. |
| Fabricator capability documentation for the chosen layer count | Minimum trace/space, drill, annular ring and finish limits that bound the routing of the chosen package and a differential pair on the chosen stackup. |
| Fabricator stackup and impedance data or an impedance calculator | Supplies the dielectric thickness and Er that the documented impedance approximation depends on; without it the impedance claim has no basis. |
| Target-side header/connector datasheet | Pitch, current rating, polarisation and mating retention for whichever of the two permitted header styles is chosen. |
| Passive component datasheets | Decoupling capacitor voltage rating and DC-bias derating, and resistor tolerance for the CC network where the specification's window is tight. |
| Shared PCBA_AutoDesignAndTest toolkit documentation | Defines the repository structure and interfaces the board is meant to consume without pushing board-specific logic back into the toolkit. |

## Recording a source, once one is chosen

Replace the class with the actual document — manufacturer, part number, revision
and date — and state the fact taken from it, in the units the document uses.
Keep the class row: it says why the document was needed.

JLCPCB-wide process limits are **not** recorded here. They live in the toolkit's
`profiles/jlcpcb/`, with their own provenance; this board records only its own
tighter targets and its own selected options. A limit copied into two places is
a rival threshold, and the toolkit has a gate that says so.
