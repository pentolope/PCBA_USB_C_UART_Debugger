"""Circuit scenarios, and what each one is allowed to establish.

Four questions the schematic can answer before any copper exists.

  * A target plugged in while the adapter is running connects its own bulk
    capacitance to the logic rail through the supply switch. The requirement
    report answers that by sharing charge instantaneously between two
    capacitances; here the network is solved, with the switch's resistance
    and the finite event in it, and the rail's minimum is what comes out.
  * The adapter's own output has to reach a valid level at the target
    through the series element and whatever the target and its wiring
    present, inside one bit at the highest baud rate the bridge offers.
  * The same path with a shunt across the two header pins that carry it is
    the bring-up loopback, and it has to close through two series elements
    and the receiver's own pin capacitance.
  * The supply switch has to stay off while nothing drives its gate, which
    is a question about one pull-up against one transistor's leakage.

The elements are resistors, capacitors and ideal sources, because that is
what the scenario contract accepts; every device that is not one of those is
a declared stand-in, and each stand-in says what it replaces.

Two questions are deliberately absent. The suspend and unconfigured current
ceilings are sums of currents each of which is a datasheet or declared
figure, and a linear network solves nothing about them that the arithmetic
does not. The back-feed case - a powered target driving a signal into an
unpowered adapter - is bounded by the series element alone, and every effect
a network would add reduces the current, so the arithmetic is already the
bound.
"""
from __future__ import annotations

import json
import os
import sys

from . import netlist, rules

REPO_ROOT = rules.REPO_ROOT
SIM_DIR = os.path.join(REPO_ROOT, "sim")

#: How long the rail is watched after a target is connected to it.
HOT_PLUG_WINDOW_S = 200.0e-6

#: How many bit periods each edge scenario runs for.
EDGE_PERIODS = 3

#: The resistance that stands in for the regulator during the hot-plug
#: event. Deliberately far above anything a regulator presents: the question
#: is how far the rail falls before the regulator can respond, and a source
#: that could respond would only hold the rail higher.
REGULATOR_STAND_IN_OHM = 10.0e3

#: The shunt across the two header pins, as its contact resistance. A
#: declared figure: a 0.1-inch shunt's specification is not among the frozen
#: documents, and the value is small enough that the answer does not turn on
#: it.
LOOPBACK_SHUNT_OHM = 0.05


def _parameters():
    return rules.load_parameters()


def _ideal(records):
    return {name: {"stands_in_for": detail,
                   "accepted_for_design_decision": True}
            for name, detail in records.items()}


def _measurement(name, kind, node, op=None, value=None, knowledge=None):
    record = {"name": name, "kind": kind, "node": node}
    if op is not None:
        record["assertion"] = {"op": op, "value": value}
    if knowledge is not None:
        record["knowledge"] = knowledge
    return record


def _pulse(v1, v2, period_s, delay_s=None):
    delay = period_s / 20.0 if delay_s is None else delay_s
    return {"v1": v1, "v2": v2, "delay_s": delay,
            "rise_s": period_s / 1.0e6, "fall_s": period_s / 1.0e6,
            "width_s": period_s / 2.0, "period_s": period_s}


def _driver_resistance(parameters):
    """The bridge's output as one resistance, from its own VOH point.

    The datasheet states an output high voltage at a stated source current.
    Their ratio is the resistance that produces exactly that drop at exactly
    that current, which is the strongest thing the datasheet says about the
    driver's strength. The low side's ratio is smaller, so the high side's
    is used for both and understates the drive in one direction.
    """
    outputs = _parameters()["parts"][
        netlist.PARTS["U1"]["mpn"]]["digital_outputs"]
    del parameters
    return (outputs["voh_below_vio_v"]["value"]
            / outputs["voh_below_vio_v"]["at_current_a"])


# ---------------------------------------------------------------------------

def hot_plug_scenario(parameters):
    """A target's bulk capacitance connected to a running rail.

    The switch is already closed, because that is the case the requirement
    is about: a target plugged in after the adapter has enumerated. The
    target's capacitance starts uncharged, which the step source does by
    sitting at the rail's own potential until it steps to the reference.

    The target's steady load is not in this network. It is already in the
    source's value: the rail figure used is the regulator's output at the
    bottom of its band less the whole of its load regulation, which is what
    the rail sits at with the declared load on it. Adding the load again
    behind a stand-in that cannot supply it would only pull the starting
    point below where the regulator holds it.
    """
    supply = rules.Supply(parameters)
    rail_f = rules._effective_capacitance(parameters, "+3V3")
    monitor_v = rules._spec(parameters, "U1")[
        "supply_monitor_threshold_max_v"]["value"]
    return {
        "name": "logic_rail_when_a_target_is_plugged_in_live",
        "description": "the target's declared bulk capacitance connected to "
                       "the logic rail through the closed supply switch, "
                       "with the rail's own capacitance at the bottom of "
                       "everything stated about it",
        "elements": [
            {"kind": "vsource_dc", "name": "VREG", "nodes": ["src", "0"],
             "value": supply.rail_min_v},
            {"kind": "resistor", "name": "RREG", "nodes": ["src", "rail"],
             "value": REGULATOR_STAND_IN_OHM},
            {"kind": "capacitor", "name": "CRAIL", "nodes": ["rail", "0"],
             "value": rail_f},
            {"kind": "resistor", "name": "RSWITCH", "nodes": ["rail", "tgt"],
             "value": supply.switch_rds_ohm},
            {"kind": "capacitor", "name": "CTARGET", "nodes": ["tgt", "sink"],
             "value": netlist.TARGET_BULK_CAPACITANCE_F},
            {"kind": "vsource_pulse", "name": "PLUG", "nodes": ["sink", "0"],
             "pulse": _pulse(supply.rail_min_v, 0.0, 2 * HOT_PLUG_WINDOW_S,
                             delay_s=HOT_PLUG_WINDOW_S / 20.0)},
        ],
        "analyses": [{"kind": "tran", "step_s": HOT_PLUG_WINDOW_S / 4000.0,
                      "stop_s": HOT_PLUG_WINDOW_S}],
        "measurements": [
            _measurement("logic_rail_minimum", "tran_min_voltage", "rail",
                         ">=", monitor_v),
            _measurement("target_supply_final", "tran_final_voltage", "tgt"),
        ],
        "assumptions": _ideal({
            "VREG": "the regulator's output at the bottom of its accuracy "
                    "band less the whole of its load regulation, as an ideal "
                    "source",
            "RREG": "the regulator's ability to respond, deliberately "
                    "removed: at ten kilohms it supplies nothing over an "
                    "event this short, and a regulator that did respond "
                    "would only hold the rail higher",
            "CRAIL": "every capacitance on the logic rail as one ideal "
                     "capacitor, each at the low end of its tolerance and "
                     "with the declared DC-bias loss taken off, with no ESR "
                     "and no ESL",
            "RSWITCH": "the two series transistors as their on-resistance at "
                       "the 2.5 V gate drive the datasheet characterises, "
                       "below the rail that actually drives them",
            "CTARGET": "the largest bulk capacitance this board declares a "
                       "target may present, as one ideal capacitor with no "
                       "series resistance of its own; a real target's own "
                       "resistance would slow the event and raise the "
                       "minimum",
            "PLUG": "the instant of connection, as an ideal switch with no "
                    "contact resistance and no bounce",
        }),
    }


def target_edge_scenario(parameters):
    """One adapter output driving a target input at the top baud rate."""
    supply = rules.Supply(parameters)
    series_max_ohm = netlist.SIGNAL_SERIES_OHM * (
        1.0 + rules._tolerance(parameters, "R8", "resistor"))
    period_s = 1.0 / netlist.MAX_BAUD
    return {
        "name": "target_side_edge_at_the_highest_baud_rate",
        "description": "one adapter output driving the declared target and "
                       "wiring capacitance through its series element, at "
                       "the highest baud rate the bridge offers",
        "elements": [
            {"kind": "vsource_pulse", "name": "DRIVE", "nodes": ["drv", "0"],
             "pulse": _pulse(supply.rail_min_v, 0.0, period_s)},
            {"kind": "resistor", "name": "RDRV", "nodes": ["drv", "out"],
             "value": _driver_resistance(parameters)},
            {"kind": "resistor", "name": "RSERIES", "nodes": ["out", "tgt"],
             "value": series_max_ohm},
            {"kind": "capacitor", "name": "CTGT", "nodes": ["tgt", "0"],
             "value": netlist.TARGET_LOAD_CAPACITANCE_F},
            {"kind": "resistor", "name": "RTGT", "nodes": ["tgt", "0"],
             "value": supply.rail_max_v
                      / rules._spec(parameters, "U1")[
                          "input_leakage_max_a"]["value"]},
        ],
        "analyses": [{"kind": "tran", "step_s": period_s / 4000.0,
                      "stop_s": EDGE_PERIODS * period_s}],
        "measurements": [
            _measurement("target_input_high", "tran_max_voltage", "tgt",
                         ">=", netlist.TARGET_VIH_V),
            _measurement("target_input_low", "tran_min_voltage", "tgt",
                         "<=", netlist.TARGET_VIL_V),
        ],
        "assumptions": _ideal({
            "DRIVE": "the bridge's transmit output as an ideal switch "
                     "between the reference and the rail at the bottom of "
                     "its band, at the highest baud rate the bridge states",
            "RDRV": "the driver's own strength as the resistance that "
                    "produces its stated output high voltage at the stated "
                    "source current",
            "RSERIES": "the series element at the high end of its tolerance",
            "CTGT": "the budget this board declares for the target's input "
                    "and the wiring to it, as one ideal capacitance to the "
                    "reference",
            "RTGT": "the target's input as a leakage path only, sized from "
                    "the bridge's own input-leakage limit because the "
                    "target's is not a document this board holds",
        }),
    }


def loopback_scenario(parameters):
    """The bring-up loopback: transmit to receive through a header shunt."""
    supply = rules.Supply(parameters)
    series_max_ohm = netlist.SIGNAL_SERIES_OHM * (
        1.0 + rules._tolerance(parameters, "R8", "resistor"))
    bridge = rules._spec(parameters, "U1")
    period_s = 1.0 / netlist.MAX_BAUD
    vih_v = supply.rail_min_v - bridge["digital_inputs"][
        "vih_below_vio_v"]["value"]
    vil_v = bridge["digital_inputs"]["vil_max_v"]["value"]
    return {
        "name": "loopback_across_the_two_adjacent_header_pins",
        "description": "the transmit output driving the receive input "
                       "through both series elements and a shunt across the "
                       "header, which is the bring-up test with no target "
                       "attached",
        "elements": [
            {"kind": "vsource_pulse", "name": "DRIVE", "nodes": ["drv", "0"],
             "pulse": _pulse(supply.rail_min_v, 0.0, period_s)},
            {"kind": "resistor", "name": "RDRV", "nodes": ["drv", "txd"],
             "value": _driver_resistance(parameters)},
            {"kind": "resistor", "name": "RTX", "nodes": ["txd", "hdr_tx"],
             "value": series_max_ohm},
            {"kind": "resistor", "name": "RSHUNT",
             "nodes": ["hdr_tx", "hdr_rx"], "value": LOOPBACK_SHUNT_OHM},
            {"kind": "resistor", "name": "RRX", "nodes": ["hdr_rx", "rxd"],
             "value": series_max_ohm},
            {"kind": "capacitor", "name": "CPIN", "nodes": ["rxd", "0"],
             "value": bridge["pin_capacitance_f"]["value"]},
            {"kind": "resistor", "name": "RLEAK", "nodes": ["rxd", "0"],
             "value": supply.rail_max_v
                      / bridge["input_leakage_max_a"]["value"]},
        ],
        "analyses": [{"kind": "tran", "step_s": period_s / 4000.0,
                      "stop_s": EDGE_PERIODS * period_s}],
        "measurements": [
            _measurement("receiver_high", "tran_max_voltage", "rxd",
                         ">=", vih_v),
            _measurement("receiver_low", "tran_min_voltage", "rxd",
                         "<=", vil_v),
        ],
        "assumptions": _ideal({
            "DRIVE": "the transmit output as an ideal switch at the "
                     "highest baud rate the bridge states",
            "RDRV": "the driver's strength as the resistance that produces "
                    "its stated output high voltage at the stated current",
            "RTX": "the transmit series element at the high end of its "
                   "tolerance",
            "RSHUNT": "the shunt across the header as a declared contact "
                      "resistance; no shunt specification is among the "
                      "frozen documents",
            "RRX": "the receive series element at the high end of its "
                   "tolerance",
            "CPIN": "the receiver's own pin capacitance, with nothing for "
                    "the copper because there is none yet",
            "RLEAK": "the receiver's input leakage at the datasheet limit, "
                     "as the resistance that sinks it to the reference",
        }),
    }


def switch_off_state_scenario(parameters):
    """The supply switch with nothing driving its gate.

    The state the bridge leaves it in from reset until enumeration is
    complete, and again in suspend: the driver is off, so the only thing
    setting the gate is the pull-up against that driver's leakage.
    """
    supply = rules.Supply(parameters)
    pfet = rules._spec(parameters, "Q1")["fet"]
    nfet = rules._spec(parameters, "Q3")["fet"]
    threshold_v = abs(pfet["vgs_threshold_min_v"]["value"])
    off_ohm = supply.rail_max_v / abs(
        nfet["drain_leakage_max_a"]["value"])
    return {
        "name": "the_supply_switch_with_nothing_driving_its_gate",
        "description": "the gate network of the target-supply switch with "
                       "its driver off, which is the state the bridge holds "
                       "from reset until enumeration and again in suspend",
        "elements": [
            {"kind": "vsource_dc", "name": "RAIL", "nodes": ["source", "0"],
             "value": supply.rail_max_v},
            {"kind": "resistor", "name": "RPULLUP",
             "nodes": ["source", "gate"],
             "value": rules._resistor_ohms("R6")},
            {"kind": "resistor", "name": "RDRIVEROFF", "nodes": ["gate", "0"],
             "value": off_ohm},
        ],
        "analyses": [{"kind": "op"}],
        "measurements": [
            _measurement("switch_gate_voltage", "op_voltage", "gate",
                         ">=", supply.rail_max_v - threshold_v),
        ],
        "assumptions": _ideal({
            "RAIL": "the shared source of the two switch transistors, held "
                    "at the top of the rail's band, which is the largest "
                    "gate-to-source difference the pull-up has to close",
            "RPULLUP": "the gate pull-up at its nominal value",
            "RDRIVEROFF": "the driver transistor in its off state, as the "
                          "resistance that passes its datasheet drain "
                          "leakage from the rail",
        }),
    }


SCENARIOS = (
    ("pre_layout_hot_plug.json", hot_plug_scenario),
    ("pre_layout_loopback.json", loopback_scenario),
    ("pre_layout_switch_off_state.json", switch_off_state_scenario),
    ("pre_layout_target_edge.json", target_edge_scenario),
)


def documents():
    parameters = _parameters()
    return {name: builder(parameters) for name, builder in SCENARIOS}


def _write(path, document):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def write():
    return [_write(os.path.join(SIM_DIR, name), document)
            for name, document in sorted(documents().items())]


if __name__ == "__main__":
    for path in write():
        sys.stdout.write(path + "\n")
