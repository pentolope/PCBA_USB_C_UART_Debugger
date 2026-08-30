# PCBA_USB_C_UART_Debugger — USB-C UART Debug Adapter

**Benchmark ID:** 05  
**Difficulty:** 2/5  
**Brief detail:** 3/5  
**Category:** high-speed-lite  
**Likely layer count:** 2  
**Primary stressors:** USB 2.0 differential routing, ESD, USB-C CC resistors, small QFN

## Design brief

Create a USB-C to 3.3 V UART debug adapter. It must be a USB 2.0 Full-Speed device, bus-powered, and expose TX, RX, GND, 3V3 reference, and optional RTS/CTS on a 0.1-inch or compact locking header. Include the correct USB-C device-side CC network, USB ESD protection close to the connector, local decoupling, and clearly separated USB and target-side connectors. Choose a commonly available USB-UART bridge. Prefer two layers, but route D+/D- as a deliberate differential pair and document any impedance approximation.

## Benchmark intent

This brief is intentionally one member of a heterogeneous PCBA-autodesign benchmark. Treat stated requirements as authoritative; where the brief leaves choices open, make and document reasonable engineering decisions rather than inventing hidden user requirements. The repository should remain a consumer of the shared `PCBA_AutoDesignAndTest` toolkit rather than accumulating board-specific logic in the toolkit.
