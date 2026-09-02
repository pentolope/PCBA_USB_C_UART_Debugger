"""The design source: what the board is made of and what is joined to what.

Everything downstream - the schematic, the board, the manifest, the scenarios
and the requirement report - is generated from this module, so there is one
statement of the design rather than several that can drift apart.
"""
from __future__ import annotations

import os

PROJECT_NAME = "usb_c_uart_debugger"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SYMBOL_LIBRARY_PATHS = (
    os.path.join(_REPO_ROOT, "library"),
    "/usr/share/kicad/symbols",
)

LIBRARY_NAME = "UsbCUartDebugger"


# ---------------------------------------------------------------------------
# the two connectors, as pin-to-function maps

#: USB Type-C receptacle terminals this board uses, from the connector
#: drawing's own signal table. The receptacle brings D+ out on two terminals
#: and D- on two more because a USB 2.0 plug populates only its A-side
#: contacts: a flipped plug lands on B6/B7 instead of A6/A7, so the board has
#: to join them or the adapter works in one orientation only.
USB_C_PINS = {
    "GND": ("A1", "B1", "A12", "B12"),
    "VBUS": ("A4", "B4", "A9", "B9"),
    "CC1": ("A5",),
    "CC2": ("B5",),
    "DP": ("A6", "B6"),
    "DM": ("A7", "B7"),
    "SBU": ("A8", "B8"),
    "SHIELD": ("SH",),
}

#: The terminal of each data net the controlled pair is measured from. A6 and
#: A7 are the two centre lands, half a millimetre apart, so the pair leaves
#: the receptacle already at its routed spacing.
USB_C_PAIR_TERMINALS = {"USB_DP": "A6", "USB_DM": "A7"}

#: The terminal of each data net that carries the flipped plug, and which
#: therefore has to be joined to the one above.
USB_C_FLIPPED_TERMINALS = {"USB_DP": "B6", "USB_DM": "B7"}

#: Target header, in the pin order of the FTDI TTL-232R-3V3 cable, which is
#: what a 0.1-inch six-way debug header means in practice. TXD and RXD are
#: adjacent, so one shunt across pins 4 and 5 is the loopback.
#:
#: Every name is stated from the adapter's point of view: TXD is what this
#: board drives, RXD is what it receives, RTS is an output and CTS an input.
TARGET_HEADER_PINS = {
    1: ("GND", "GND"),
    2: ("CTS", "TGT_CTS"),
    3: ("3V3", "TGT_3V3"),
    4: ("TXD", "TGT_TXD"),
    5: ("RXD", "TGT_RXD"),
    6: ("RTS", "TGT_RTS"),
}

#: The two header pins a shunt bridges to exercise the whole data path with
#: no target attached.
LOOPBACK_HEADER_PINS = (4, 5)


# ---------------------------------------------------------------------------
# the bridge

#: CP2102N QFN28 pin numbers, from DS CP2102N Rev 1.5 table 5.1. Pin 29 is
#: the exposed pad, which the same table calls GND.
BRIDGE_PINS = {
    "DCD": "1", "RI_CLK": "2", "GND": "3", "DP": "4", "DM": "5",
    "VDD": "6", "VREGIN": "7", "VBUS": "8", "RSTB": "9", "NC": "10",
    "SUSPENDB": "11", "SUSPEND": "12", "CHREN": "13", "CHR1": "14",
    "CHR0": "15", "GPIO3": "16", "GPIO2": "17", "GPIO1": "18",
    "GPIO0": "19", "GPIO6": "20", "GPIO5": "21", "GPIO4": "22",
    "CTS": "23", "RTS": "24", "RXD": "25", "TXD": "26", "DSR": "27",
    "DTR": "28", "EPAD": "29",
}

#: Pins the QFN28 brings out that this board does not use. The battery-charger
#: outputs and the general-purpose pins are outputs or bidirectional, so
#: nothing is tied to them; the ring-indicator pin is left alone because the
#: same pin is a clock output when it is configured as one, and a conductor
#: tied to it would then be fighting a driver.
BRIDGE_UNUSED_PINS = ("RI_CLK", "NC", "SUSPEND", "CHREN", "CHR1", "CHR0",
                      "GPIO3", "GPIO2", "GPIO1", "GPIO0", "GPIO6", "GPIO5",
                      "GPIO4", "DTR")

#: The two modem pins the datasheet's pin table calls inputs and nothing
#: else. A CMOS input left floating is undefined, so both are tied, and they
#: are tied to the reference because both are active low: a target wired
#: directly to this adapter is by construction present and ready, and host
#: software that waits on either of them therefore proceeds.
BRIDGE_TIED_LOW_PINS = ("DCD", "DSR")

#: The bridge's power pins, each of which the datasheet requires to carry its
#: own 4.7 uF and 0.1 uF close to the pin.
BRIDGE_SUPPLY_PINS = ("VDD", "VREGIN")

#: What the internal regulator is not used for, and why. The regulator's
#: input pin is specified only to 5.25 V, and USB Type-C permits a source to
#: present 5.5 V, so a compliant source could run it outside its recommended
#: operating range. VREGIN is therefore tied to VDD, which is the connection
#: the datasheet prescribes when the regulator is unused.
BRIDGE_INTERNAL_REGULATOR_USED = False


def _part(lib_id, footprint, value, mpn=None, manufacturer=None, lcsc=None,
          datasheet="", in_bom=True, on_board=True):
    return {
        "lib_id": lib_id,
        "footprint": footprint,
        "value": value,
        "mpn": mpn,
        "manufacturer": manufacturer,
        "lcsc": lcsc,
        "datasheet": datasheet,
        "in_bom": in_bom,
        "on_board": on_board,
    }


#: Resistor values used on this board, and the catalogue part behind each.
RESISTOR_PARTS = {
    "1k": ("C21190", "0603WAF1001T5E"),
    "5.1k": ("C23186", "0603WAF5101T5E"),
    "10k": ("C25804", "0603WAF1002T5E"),
    "100k": ("C25803", "0603WAF1003T5E"),
    "220R": ("C22962", "0603WAF2200T5E"),
    "220k": ("C22961", "0603WAF2203T5E"),
}

#: Where every resistor goes.
RESISTOR_VALUES = {
    1: "5.1k",   # CC1 pull-down
    2: "5.1k",   # CC2 pull-down
    3: "1k",     # reset pull-up
    4: "100k",   # VBUS sense divider, upper
    5: "220k",   # VBUS sense divider, lower
    6: "100k",   # target-supply switch gate pull-up
    7: "10k",    # suspend-output pull-down
    8: "220R",   # TXD series
    9: "220R",   # RXD series
    10: "220R",  # RTS series
    11: "220R",  # CTS series
}

#: C1/C2 bypass VBUS and feed the regulator; C3/C4 sit at its output; C5..C8
#: are the pair the bridge's datasheet requires at each of its two supply
#: pins; C9 and C10 are rail bulk beside the target switch, and they are
#: there for one reason - a target plugged in live shares charge with this
#: capacitance before the regulator can respond, so how much of it there is
#: sets how much capacitance a target may present.
CAPACITOR_VALUES = {1: "4.7uF", 2: "100nF", 3: "4.7uF", 4: "100nF",
                    5: "4.7uF", 6: "100nF", 7: "4.7uF", 8: "100nF",
                    9: "4.7uF", 10: "4.7uF", 11: "4.7uF"}

CAPACITOR_PARTS = {
    "4.7uF": ("C19666", "CL10A475KO8NNNC", "Samsung Electro-Mechanics",
              "Capacitor_SMD:C_0603_1608Metric"),
    "100nF": ("C14663", "CC0603KRX7R9BB104", "YAGEO",
              "Capacitor_SMD:C_0603_1608Metric"),
}

#: Which nets each probe pad reaches. The set is the brief's, and each pad is
#: a point on its net rather than a spur off it.
PROBE_NETS = {"TP1": "VBUS", "TP2": "+3V3", "TP3": "GND",
              "TP4": "USB_DP", "TP5": "USB_DM"}


def _parts():
    parts = {
        "U1": _part(
            "Interface_USB:CP2102N-Axx-xQFN28",
            "Package_DFN_QFN:QFN-28-1EP_5x5mm_P0.5mm_EP3.25x3.25mm",
            "CP2102N-A02-GQFN28R", "CP2102N-A02-GQFN28R",
            "Silicon Labs", "C964632"),
        "U2": _part(
            "%s:XC6206Pxx2PR" % LIBRARY_NAME,
            "Package_TO_SOT_SMD:SOT-89-3",
            "XC6206P332PR-G", "XC6206P332PR-G", "Torex Semiconductor",
            "C526275"),
        "J1": _part(
            "Connector:USB_C_Receptacle_USB2.0_16P",
            "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
            "TYPE-C-31-M-12", "TYPE-C-31-M-12", "Korean Hroparts Elec",
            "C165948"),
        "J2": _part(
            "Connector_Generic:Conn_01x06",
            "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
            "KH-2.54PH180-1X6P-L11.5", "KH-2.54PH180-1X6P-L11.5",
            "Shenzhen Kinghelm Elec", "C2905486"),
        "D1": _part(
            "Power_Protection:USBLC6-2SC6",
            "Package_TO_SOT_SMD:SOT-23-6",
            "USBLC6-2SC6", "USBLC6-2SC6", "STMicroelectronics", "C7519"),
        "Q3": _part(
            "Transistor_FET:AO3400A", "Package_TO_SOT_SMD:SOT-23",
            "AO3400A", "AO3400A", "Alpha & Omega Semiconductor", "C20917"),
    }
    for reference in ("Q1", "Q2"):
        parts[reference] = _part(
            "Transistor_FET:AO3401A", "Package_TO_SOT_SMD:SOT-23",
            "AO3401A", "AO3401A", "Alpha & Omega Semiconductor", "C15127")
    for index, value in sorted(RESISTOR_VALUES.items()):
        lcsc, mpn = RESISTOR_PARTS[value]
        parts["R%d" % index] = _part(
            "Device:R", "Resistor_SMD:R_0603_1608Metric", value, mpn,
            "UNI-ROYAL(Uniroyal Elec)", lcsc)
    for index, value in sorted(CAPACITOR_VALUES.items()):
        lcsc, mpn, manufacturer, footprint = CAPACITOR_PARTS[value]
        parts["C%d" % index] = _part(
            "Device:C", footprint, value, mpn, manufacturer, lcsc)
    for reference in sorted(PROBE_NETS):
        parts[reference] = _part(
            "Connector:TestPoint", "TestPoint:TestPoint_Pad_D1.0mm",
            "TestPoint", in_bom=False)
    for index in range(1, 3):
        parts["#FLG%d" % index] = _part(
            "power:PWR_FLAG", "", "PWR_FLAG", in_bom=False, on_board=False)
    return parts


PARTS = _parts()


def _bridge(function):
    return "U1." + BRIDGE_PINS[function]


def _receptacle(function):
    return ["J1." + pin for pin in USB_C_PINS[function]]


def _nets():
    ground = [
        _bridge("GND"), _bridge("EPAD"), "D1.2", "U2.1", "Q3.2",
        "R1.2", "R2.2", "R5.2", "R7.2", "J2.1", "TP3.1", "#FLG1.1",
    ]
    ground += _receptacle("GND") + _receptacle("SHIELD")
    ground += [_bridge(function) for function in BRIDGE_TIED_LOW_PINS]
    ground += ["C%d.2" % index for index in sorted(CAPACITOR_VALUES)]

    vbus = ["D1.5", "U2.2", "C1.1", "C2.1", "R4.1", "TP1.1", "#FLG2.1"]
    vbus += _receptacle("VBUS")

    logic_rail = [
        "U2.3", "C3.1", "C4.1", "C5.1", "C6.1", "C7.1", "C8.1",
        "C9.1", "C10.1", "C11.1", "R3.1", "Q1.3", "TP2.1",
    ]
    logic_rail += [_bridge(function) for function in BRIDGE_SUPPLY_PINS]

    nets = {
        "GND": ground,
        "VBUS": vbus,
        "+3V3": logic_rail,
        "USB_CC1": ["J1.A5", "R1.1"],
        "USB_CC2": ["J1.B5", "R2.1"],
        "USB_DP": _receptacle("DP") + ["D1.1", "D1.6", _bridge("DP"),
                                       "TP4.1"],
        "USB_DM": _receptacle("DM") + ["D1.3", "D1.4", _bridge("DM"),
                                       "TP5.1"],
        "VBUS_SENSE": ["R4.2", "R5.1", _bridge("VBUS")],
        "NRST": ["R3.2", _bridge("RSTB")],
        "SUSPENDB": [_bridge("SUSPENDB"), "R7.1", "Q3.1"],
        "SWITCH_GATE": ["Q3.3", "R6.1", "Q1.1", "Q2.1"],
        "SWITCH_MID": ["Q1.2", "Q2.2", "R6.2"],
        "TGT_3V3": ["Q2.3", "J2.3"],
        "UART_TXD": [_bridge("TXD"), "R8.1"],
        "UART_RXD": [_bridge("RXD"), "R9.1"],
        "UART_RTS": [_bridge("RTS"), "R10.1"],
        "UART_CTS": [_bridge("CTS"), "R11.1"],
        "TGT_TXD": ["R8.2", "J2.4"],
        "TGT_RXD": ["R9.2", "J2.5"],
        "TGT_RTS": ["R10.2", "J2.6"],
        "TGT_CTS": ["R11.2", "J2.2"],
    }
    return nets


NETS = _nets()

NO_CONNECT = tuple(
    [_bridge(function) for function in BRIDGE_UNUSED_PINS]
    + ["J1." + pin for pin in USB_C_PINS["SBU"]])


# ---------------------------------------------------------------------------
# what the board is required to do, as numbers

#: VBUS at this board's receptacle. The floor is the voltage a low-power
#: function has to work at, because the board enumerates as one; the ceiling
#: is the one the VBUS-max ECN raised the supplied voltage to, which is also
#: what USB Type-C permits a source to present.
VBUS_MIN_V = 4.40
VBUS_MAX_V = 5.50

#: The floor a function drawing more than one unit load may rely on. This
#: board never does, so this appears only where the distinction is being
#: evaluated.
VBUS_HIGH_POWER_MIN_V = 4.75

#: One unit load, and what this board declares in its configuration
#: descriptor. The board stays inside a single unit load in every state,
#: which is why it is declared as a low-power function rather than
#: negotiating five.
UNIT_LOAD_A = 0.100
DECLARED_MAX_POWER_A = 0.100

#: The suspend ceiling the suspend-current ECN sets for every device that is
#: not an inter-chip USB device.
SUSPEND_CURRENT_MAX_A = 0.0025

#: Bypass capacitance directly across VBUS, as the device-capacitance ECN
#: bounds it. Both ends are requirements: too little and the device cannot be
#: detected, too much and it droops the hub.
VBUS_BYPASS_MIN_F = 1.0e-6
VBUS_BYPASS_MAX_F = 10.0e-6

#: Full-speed signalling, from the USB 2.0 specification.
FULL_SPEED_BIT_RATE = 12.0e6
FULL_SPEED_RISE_MIN_S = 4.0e-9
USB_NOMINAL_DIFFERENTIAL_OHM = 90.0

#: How the pair is drawn, and how long it is allowed to be. The width and
#: the gap are the USB net class's; the length is a budget, and the routed
#: board is measured against it rather than the other way round.
USB_PAIR_TRACE_WIDTH_MM = 0.25
USB_PAIR_GAP_MM = 0.25
USB_PAIR_LENGTH_BUDGET_MM = 25.0
USB_PAIR_SKEW_BUDGET_MM = 0.2

#: One layer change per conductor. It is not a preference: the receptacle's
#: four data terminals alternate along the land row, so the two links that
#: join each line's pair of terminals cannot both be drawn on one layer.
USB_PAIR_VIA_BUDGET_PER_NET = 2

#: The receptacle's data terminals, left to right along the land row, from
#: the connector drawing. The order is what makes the links non-planar.
USB_C_DATA_TERMINAL_ORDER = ("B7", "A6", "A7", "B6")

#: One data land's width, from the recommended layout on the same drawing.
#: It is the yardstick the "could this stackup reach 90 ohm by widening the
#: conductor" question is answered against.
USB_C_DATA_LAND_WIDTH_MM = 0.30

#: How much of the shortest transition a round trip along the pair may take
#: before the interconnect stops behaving as a lump. A design target, not a
#: figure from the specification.
LUMPED_FRACTION_OF_RISE = 1.0 / 6.0

#: What this board allows on a full-speed data line, and how closely the two
#: lines have to match. Both are declarations: the specification bounds the
#: transceiver's rise and fall times into a stated load rather than naming a
#: capacitance a device may carry, so the board states the budget it sized
#: its clamp against.
USB_LINE_CAPACITANCE_BUDGET_F = 20.0e-12
USB_LINE_CAPACITANCE_MATCH_F = 0.1e-12

#: The discharge level the data lines' clamp has to be rated for.
ESD_CONTACT_DISCHARGE_KV = 8.0

#: The highest a sink's CC conductor sits, from the sink-termination table's
#: own maximum-voltage column for the tolerance grade this board fits.
TYPE_C_CC_MAX_V = 2.04

#: Rd for a sink taking default USB power, and the tolerance band the Type-C
#: specification's sink-termination table allows the tighter of its two
#: resistor implementations - the one that can also read the source's
#: advertised current.
TYPE_C_RD_OHM = 5100.0
TYPE_C_RD_TOLERANCE = 0.10

#: What the target header may take from the adapter, and the ambient the
#: budget is claimed at. The budget is set by the regulator's dissipation at
#: the top of the VBUS range, not by its current rating.
TARGET_SUPPLY_BUDGET_A = 0.040
AMBIENT_MAX_C = 85.0

#: The bridge's own supply current. The datasheet states a typical and no
#: maximum, so the board declares one and says so: twice the typical at the
#: highest baud rate. Every current claim that uses it is a bound resting on
#: this declaration, not a datasheet limit.
BRIDGE_SUPPLY_CURRENT_TYPICAL_A = 0.0137
BRIDGE_SUPPLY_CURRENT_ASSUMED_MAX_MULTIPLE = 2.0

#: The 44 ohm the specification's own inrush reference load carries, which
#: is what "matches the characteristics of the above load" is measured
#: against.
USB_INRUSH_REFERENCE_OHM = 44.0

#: Baud rate the series elements in the target-side signals are sized for.
#: The bridge reaches this rate; whether a given edge arrives in time through
#: the series element depends on what the target and its wiring present, so
#: the load below is a declared budget rather than a measurement.
MAX_BAUD = 3.0e6
TARGET_LOAD_CAPACITANCE_F = 50.0e-12

#: How far an edge has to get before it counts as arrived, and how much of a
#: bit it may take getting there. Both are design targets.
EDGE_SETTLE_FRACTION = 0.9
EDGE_BUDGET_FRACTION_OF_BIT = 0.2

#: What a 3.3 V CMOS target is taken to require and to drive. Declarations,
#: not figures from any one target: the adapter cannot know which part is on
#: the other end of the header, so it states what it is designed against.
TARGET_VIH_V = 2.31
TARGET_VIL_V = 0.99
TARGET_DRIVE_MAX_V = 3.6

#: What a target may present on the supply pin when it is plugged in live.
#: A declared budget: the adapter cannot know the target's bulk capacitance,
#: so it states the largest it is designed to survive without dropping the
#: host connection, and carries the rail capacitance that makes it true.
TARGET_BULK_CAPACITANCE_F = 4.7e-6

#: Series element in each target-side signal. It is what bounds the current
#: into a bridge pin when a powered target drives a signal and VBUS is
#: absent, and what slows the edge into the target's own capacitance; the
#: value is the compromise between those two.
SIGNAL_SERIES_OHM = 220.0

#: Nets that leave the board through a connector, with the signal that has to
#: reach a probe.
PROBE_REQUIRED_NETS = tuple(sorted(set(PROBE_NETS.values())))

#: The build this board is costed and supplied for.
PLANNED_BUILD_QUANTITY = 50

#: What the assembler has to do beyond one reflow of the front side: the
#: target header, and the receptacle, whose signal lands reflow with
#: everything else but whose four shell legs go through the board.
ASSEMBLY_POLICY = {
    "placement_sides": 1,
    "through_hole_soldered_parts": 2,
}

CONNECTOR_FUNCTION_NETS = {
    "J1": dict(
        [(pin, "GND") for pin in USB_C_PINS["GND"] + USB_C_PINS["SHIELD"]]
        + [(pin, "VBUS") for pin in USB_C_PINS["VBUS"]]
        + [("A5", "USB_CC1"), ("B5", "USB_CC2")]
        + [(pin, "USB_DP") for pin in USB_C_PINS["DP"]]
        + [(pin, "USB_DM") for pin in USB_C_PINS["DM"]]),
    "J2": {str(pin): net for pin, (_label, net)
           in TARGET_HEADER_PINS.items()},
}

#: A conductor that enters the board and needs no clamp of its own, and why.
ESD_EXEMPT = {
    "GND": "the reference the clamps divert into",
    "VBUS": "clamped by the suppressor's own rail diode, which is what the "
            "steering diodes on the data lines divert into and is specified "
            "by the same document",
    "USB_CC1": "no semiconductor is on this conductor: it carries one "
               "resistor to the reference and nothing else, so there is no "
               "junction for a clamp to protect, and a clamp's leakage and "
               "capacitance would sit in parallel with a resistance the "
               "source measures to decide what it may supply",
    "USB_CC2": "as CC1",
    "TGT_3V3": "the switch that feeds it is off whenever the bridge is not "
               "running, and both of its transistors block, so this "
               "conductor reaches no powered node when the board is idle",
    "TGT_TXD": "a series element bounds the current into the only "
               "semiconductor behind it to far below that pin's rated "
               "injection",
    "TGT_RXD": "as TXD",
    "TGT_RTS": "as TXD",
    "TGT_CTS": "as TXD",
}


def entering_conductors():
    """Every conductor that enters the board, and the connector it enters by.

    Each one either carries a clamp or appears in ESD_EXEMPT with a reason.
    """
    entering = {}
    for reference, functions in CONNECTOR_FUNCTION_NETS.items():
        for net in functions.values():
            entering.setdefault(net, []).append(reference)
    return {net: sorted(set(refs)) for net, refs in entering.items()}


def pin_to_net():
    mapping = {}
    for net_name, pin_refs in NETS.items():
        for pin_ref in pin_refs:
            if pin_ref in mapping:
                raise ValueError(
                    "pin %s assigned to both %s and %s"
                    % (pin_ref, mapping[pin_ref], net_name))
            mapping[pin_ref] = net_name
    for pin_ref in NO_CONNECT:
        if pin_ref in mapping:
            raise ValueError(
                "pin %s is both no-connect and on net %s"
                % (pin_ref, mapping[pin_ref]))
    return mapping
