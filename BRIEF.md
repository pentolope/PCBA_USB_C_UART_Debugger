# PCBA_USB_C_UART_Debugger — USB-C UART Debug Adapter
## Design brief

Create a USB-C to 3.3 V UART debug adapter. It must be a USB 2.0 Full-Speed device, bus-powered, and expose TX, RX, GND, 3V3 reference, and optional RTS/CTS on a 0.1-inch or compact locking header. Include the correct USB-C device-side CC network, USB ESD protection close to the connector, local decoupling, and clearly separated USB and target-side connectors. Choose a commonly available USB-UART bridge. Prefer two layers, but route D+/D- as a deliberate differential pair and document any impedance approximation.

## Functional requirements

- Enumerates as a Full-Speed (12 Mbit/s) USB 2.0 device presenting one asynchronous serial port; driver support and baud range documented.
- Target-side signals are 3.3 V CMOS referenced to the shared GND pin, and TX, RX and any fitted RTS/CTS are labelled from a stated point of view.

## Power and rails

- Bus-powered only: no battery, no required target-side supply, no current sourced onto VBUS.
- Stays within the USB 2.0 unconfigured, configured and suspend current limits and the inrush capacitance limit.
- The 3.3 V rail holds tolerance across the permitted VBUS range and full load, with its source and current capability documented.
- Local decoupling at every supply pin on a short ground return, plus bulk capacitance on the rail.

## Connectors and pinout

- CC1 and CC2 each present an independent Rd for a sink taking default USB power, so orientation resolves either way; neither is tied to the other or to VBUS.
- The target header carries at least TX, RX, GND and 3V3, pin 1 marked, functions on the silkscreen, and the pinout documented.
- USB and target connectors sit on separated, visually distinct parts of the outline, neither obstructing access to the other.

## Signal integrity and layout

- D+/D- targets the USB 2.0 nominal differential impedance; where the stackup cannot reach it, the calculated value, stackup parameters and method are recorded.
- The pair runs over uninterrupted ground its whole length, with no split, gap or crossing trace beneath it and documented clearance to other nets.
- Pair length is short and documented, layer transitions minimised and symmetric, intra-pair skew matched to a stated tolerance, no stubs.
- Two layers unless a documented reason requires more; the stackup is recorded either way.

## Protection and robustness

- ESD protection covers D+ and D-, sits between the receptacle and everything downstream with the shortest practical ground return, and adds no more capacitance than full-speed edge and eye limits allow.
- Coverage of VBUS, CC and shield ground is a documented decision, and any CC protection leaves the Rd thresholds undisturbed.
- Nothing is damaged when the target drives TX, RX or 3V3 with VBUS absent, and hot-plugging the target does not drop the host connection.

## Test and bring-up

- A TX-to-RX loopback at the target header exercises the whole data path with no target attached, and VBUS, 3V3, GND, D+ and D- are probeable.
- Any on-chip descriptor programming interface the bridge needs is reachable when assembled.

## Open choices

- The USB-UART bridge, subject to Full-Speed USB 2.0 operation, 3.3 V logic I/O, the VBUS current budget, RTS/CTS if fitted, and documented availability and drivers.
- Header style — 0.1-inch pitch or compact locking — and whether RTS/CTS is fitted at all.
- Whether 3V3 is a reference only or may source current to the target, with its budget and any limiting; the rail's source follows.
