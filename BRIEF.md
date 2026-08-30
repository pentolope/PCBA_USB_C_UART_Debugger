# PCBA_USB_C_UART_Debugger — USB-C UART Debug Adapter
## Design brief

Create a USB-C to 3.3 V UART debug adapter. It must be a USB 2.0 Full-Speed device, bus-powered, and expose TX, RX, GND, 3V3 reference, and optional RTS/CTS on a 0.1-inch or compact locking header. Include the correct USB-C device-side CC network, USB ESD protection close to the connector, local decoupling, and clearly separated USB and target-side connectors. Choose a commonly available USB-UART bridge. Prefer two layers, but route D+/D- as a deliberate differential pair and document any impedance approximation.
