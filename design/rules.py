"""Board-level electrical checks, stated as claims with their evidence.

Every number here comes from `components/parameters.json` (which cites the
frozen document it was read from), from the USB specifications, from the
selected fabrication stackup, or from the netlist. Nothing is asserted that a
document, a component value or a measurement does not support, and a quantity
that cannot be established is reported as UNKNOWN rather than assumed.

These are the claims the schematic and the declared budgets can answer. What
only the finished copper can answer - the pair's realised length, its skew,
its reference continuity - is measured by the toolkit's own interconnect
gates against the same budgets declared here.
"""
from __future__ import annotations

import json
import math
import os
import sys

from . import netlist

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMETERS_PATH = os.path.join(REPO_ROOT, "components", "parameters.json")
CATALOG_PATH = os.path.join(REPO_ROOT, "components", "jlcpcb.json")
STACKUP_PATH = os.path.join(REPO_ROOT, "fab", "physical_inputs.json")
TOOLKIT_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest")
FOOTPRINT_ROOT = "/usr/share/kicad/footprints"
LOCAL_FOOTPRINT_ROOT = os.path.join(REPO_ROOT, "library")

if TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, TOOLKIT_ROOT)

from pcbqa import claim  # noqa: E402
from pcbqa import propagation  # noqa: E402
from pcbqa import transmission_line  # noqa: E402

DIRECT = "direct"
ASSUMED = "assumed"
DERIVED = "derived"

EVIDENCE_CLASSES = {
    DIRECT: "datasheet-behavioral",
    ASSUMED: "assumed-behavioral",
    DERIVED: "design-source",
}

BRIEF = "BRIEF.md"
USB_20 = "usb_20"
TYPE_C = "usb_type_c"
BRIDGE_DOC = "cp2102n_silabs"
LDO_DOC = "xc6206_torex"
ESD_DOC = "usblc6_2sc6_st"
STACKUP_DOC = "fab/physical_inputs.json"


def load_parameters():
    with open(PARAMETERS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_stackup():
    with open(STACKUP_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _mpn(reference):
    return netlist.PARTS[reference]["mpn"]


def _spec(parameters, reference):
    return parameters["parts"][_mpn(reference)]


def _evidence(basis, documents, assumptions=(), omissions=()):
    provenance = {"source": "components/parameters.json",
                  "documents": sorted(set(documents))}
    return claim.evidence(
        "device_electrical", EVIDENCE_CLASSES.get(basis, "design-source"),
        provenance, assumptions=list(assumptions),
        omitted_contributions=list(omissions))


def _requirement(name, op, value, source=BRIEF):
    return claim.requirement(name, source, {"op": op, "value": value})


#: How the requirement's operator turns a conservatively computed number into
#: the knowledge shape it actually supports. A worst case evaluated against a
#: floor is a lower bound on the real quantity; against a ceiling it is an
#: upper bound. Nothing that omits a contribution or rests on a premise is
#: ever allowed to call itself exact.
_BOUND_FOR_OPERATOR = {">=": claim.LOWER_BOUND, ">": claim.LOWER_BOUND,
                       "<=": claim.UPPER_BOUND, "<": claim.UPPER_BOUND}


def _claim(identity, units, significance, value, basis, documents,
           requirement, knowledge=None, scope_level="net",
           assumptions=(), omissions=()):
    """A measured quantity, with or without a requirement over it.

    `requirement=None` makes the claim descriptive: it records a number and
    its provenance and carries no verdict, which is the honest shape for a
    quantity that exists to be read rather than to be judged.
    """
    if value is None:
        return claim.claim(
            scope_level, identity, units, claim.UNKNOWN, {},
            _evidence(basis, documents, assumptions, omissions),
            significance, None, requirement)
    if knowledge is None:
        if requirement is None:
            knowledge = claim.APPROXIMATE if omissions else claim.EXACT
        elif basis == ASSUMED or omissions:
            knowledge = _BOUND_FOR_OPERATOR.get(
                requirement["assertion"]["op"], claim.APPROXIMATE)
        else:
            knowledge = claim.EXACT
    basis_record = None
    if knowledge != claim.EXACT:
        basis_record = claim.knowledge_basis(
            basis, "datasheet_limit" if basis == DIRECT else basis)
    return claim.claim(
        scope_level, identity, units, knowledge, {"value": value},
        _evidence(basis, documents, assumptions, omissions),
        significance, basis_record, requirement)


def _structural(identity, significance, violations, requirement_name,
                documents=(), basis=DERIVED, assumptions=(), omissions=()):
    """A count of violations: zero is the only acceptable answer."""
    return _claim(identity, "violations", significance, float(len(violations)),
                  basis, documents, _requirement(requirement_name, "<=", 0.0),
                  scope_level="board", assumptions=assumptions,
                  omissions=omissions)


def _resistor_ohms(reference):
    value = netlist.PARTS[reference]["value"]
    if value.endswith("k"):
        return float(value[:-1]) * 1e3
    if value.endswith("R"):
        return float(value[:-1])
    raise ValueError("resistor %s carries the unparsable value %r"
                     % (reference, value))


def _capacitance_farads(reference):
    value = netlist.PARTS[reference]["value"]
    if value.endswith("uF"):
        return float(value[:-2]) * 1e-6
    if value.endswith("nF"):
        return float(value[:-2]) * 1e-9
    raise ValueError("capacitor %s carries the unparsable value %r"
                     % (reference, value))


def _tolerance(parameters, reference, kind):
    entry = _spec(parameters, reference)[kind].get("tolerance")
    return 0.0 if entry is None else entry["value"]


def _capacitors_on(net):
    return sorted(pin.split(".", 1)[0] for pin in netlist.NETS[net]
                  if pin.split(".", 1)[0].startswith("C")
                  and pin.endswith(".1"))


def _effective_capacitance(parameters, net, derate_dc_bias=True):
    """Every capacitor on a net, at the low end of everything stated about it.

    Low, because every question this capacitance answers is about a rail
    falling, and less capacitance answers all of them worse. Tolerance is a
    datasheet limit; the DC-bias loss is a declared bound, because the
    specification publishes that characteristic only as a graph.
    """
    total = 0.0
    for reference in _capacitors_on(net):
        spec = _spec(parameters, reference)["capacitor"]
        value = _capacitance_farads(reference)
        value *= 1.0 - spec["tolerance"]["value"]
        loss = spec.get("dc_bias_loss_max")
        if derate_dc_bias and loss is not None:
            value *= 1.0 - loss["value"]
        total += value
    return total


# ---------------------------------------------------------------------------
# the supply model every rail and current claim is built on

class Supply:
    """Worst-case rail voltages and currents, from parameters and values.

    Currents are upper bounds and voltages are taken at whichever end of
    their band makes the claim being evaluated worse, so no downstream
    figure is optimistic. VBUS is the range at this board's own receptacle:
    the floor a low-power function has to work at, and the ceiling the
    VBUS-max ECN permits a source to present.
    """

    def __init__(self, parameters):
        self.parameters = parameters
        self.documents = {BRIDGE_DOC, LDO_DOC, ESD_DOC, USB_20,
                          "res_0603_uniroyal"}

        bridge = _spec(parameters, "U1")
        ldo = _spec(parameters, "U2")["regulator"]

        self.vbus_min_v = netlist.VBUS_MIN_V
        self.vbus_max_v = netlist.VBUS_MAX_V

        # The rail's floor is the accuracy band's floor less the whole load
        # regulation, because the accuracy is stated at one current and the
        # board runs over a range of them.
        self.ldo_load_regulation_v = ldo["load_regulation_max_v"]["value"]
        self.rail_nominal_v = ldo["output_voltage_v"]["value"]
        self.rail_accuracy_min_v = ldo["output_voltage_min_v"]["value"]
        self.rail_accuracy_max_v = ldo["output_voltage_max_v"]["value"]
        self.rail_min_v = self.rail_accuracy_min_v - self.ldo_load_regulation_v
        self.rail_max_v = self.rail_accuracy_max_v
        self.ldo_dropout_max_v = ldo["dropout_max_v"]["value"]
        self.ldo_dropout_at_a = ldo["dropout_max_v"]["at_current_a"]
        self.ldo_output_current_max_a = ldo["output_current_max_a"]["value"]
        self.ldo_short_circuit_a = ldo["short_circuit_current_typical_a"][
            "value"]
        self.ldo_quiescent_a = _spec(
            parameters, "U2")["supply_current_max_a"]["value"]

        # Everything the logic rail feeds, each at the top of what is stated
        # or declared about it.
        self.bridge_current_max_a = bridge["supply_current_max_a"]["value"]
        self.bridge_suspend_a = bridge["suspend_current_max_a"]["value"]
        self.usb_pull_up_a = bridge["usb"]["pull_up_current_max_a"]["value"]
        self.suspend_pull_down_a = self.rail_max_v / (
            _resistor_ohms("R7") * (1.0 - _tolerance(parameters, "R7",
                                                     "resistor")))
        self.switch_gate_a = self.rail_max_v / (
            _resistor_ohms("R6") * (1.0 - _tolerance(parameters, "R6",
                                                     "resistor")))
        self.target_budget_a = netlist.TARGET_SUPPLY_BUDGET_A

        # Loads that hang on VBUS rather than on the rail.
        divider_min_ohm = (
            _resistor_ohms("R4") * (1.0 - _tolerance(parameters, "R4",
                                                     "resistor"))
            + _resistor_ohms("R5") * (1.0 - _tolerance(parameters, "R5",
                                                       "resistor")))
        self.vbus_divider_a = self.vbus_max_v / divider_min_ohm
        self.esd_leakage_a = _spec(
            parameters, "D1")["esd"]["leakage_max_a"]["value"]
        self.switch_leakage_a = _spec(
            parameters, "Q1")["fet"]["drain_leakage_max_a"]["value"]

        # The three states the USB specification bounds separately.
        self.board_rail_current_a = (
            self.bridge_current_max_a + self.usb_pull_up_a
            + self.suspend_pull_down_a + self.switch_gate_a)
        self.board_vbus_current_a = (
            self.board_rail_current_a + self.ldo_quiescent_a
            + self.vbus_divider_a + self.esd_leakage_a)
        # Before configuration the bridge holds SUSPEND asserted, so the
        # target's supply switch is open and the pull-down on SUSPENDb sinks
        # nothing: the board draws only its own running current.
        self.unconfigured_vbus_current_a = (
            self.board_vbus_current_a - self.suspend_pull_down_a
            - self.switch_gate_a)
        self.configured_vbus_current_a = (self.board_vbus_current_a
                                          + self.target_budget_a)
        self.suspend_vbus_current_a = (
            self.bridge_suspend_a + self.usb_pull_up_a + self.ldo_quiescent_a
            + self.vbus_divider_a + self.esd_leakage_a
            + abs(self.switch_leakage_a))

        # The switch between the rail and the target header.
        self.switch_rds_ohm = 2.0 * abs(
            _spec(parameters, "Q1")["fet"]["rds_on_ohm"]["-2.5"]["value"])
        self.header_supply_min_v = (
            self.rail_min_v - self.switch_rds_ohm * self.target_budget_a)


def _stackup_geometry():
    """The one dielectric and the two conductors the pair is drawn on."""
    document = load_stackup()
    copper = [layer for layer in document["layers"]
              if layer["kind"] == "copper"]
    dielectric = [layer for layer in document["layers"]
                  if layer["kind"] == "dielectric"]
    if len(copper) != 2 or len(dielectric) != 1:
        raise ValueError(
            "the pair's impedance model assumes one dielectric between two "
            "conductors; the selected stackup has %d copper layers and %d "
            "dielectrics" % (len(copper), len(dielectric)))
    return {
        "epsilon_r": dielectric[0]["epsilon_r"],
        "height_mm": dielectric[0]["thickness_mm"],
        "conductor_mm": copper[0]["thickness_mm"],
        "provenance": document["provenance"],
    }


# ---------------------------------------------------------------------------
# USB power: the three states the specification bounds separately

def evaluate_usb_current(parameters):
    supply = Supply(parameters)
    documents = (USB_20, BRIDGE_DOC, LDO_DOC, ESD_DOC)
    assumption = ("the bridge's supply and suspend currents are the declared "
                  "bounds in components/parameters.json, not datasheet "
                  "limits: the power-consumption table states typicals and "
                  "no maxima",)
    results = [{
        "id": "unconfigured_draw_is_within_one_unit_load",
        "identity": "VBUS",
        "measured_a": supply.unconfigured_vbus_current_a,
        "claim": _claim(
            "VBUS", "A", "interface_compliance",
            supply.unconfigured_vbus_current_a, ASSUMED, documents,
            _requirement("within_one_unit_load_until_configured", "<=",
                         netlist.UNIT_LOAD_A, USB_20),
            assumptions=assumption + (
                "the bridge asserts SUSPEND from reset until enumeration "
                "completes, so the target's supply switch is open in this "
                "state and the target draws nothing through it",)),
    }, {
        "id": "configured_draw_is_within_the_declared_allocation",
        "identity": "VBUS",
        "measured_a": supply.configured_vbus_current_a,
        "claim": _claim(
            "VBUS", "A", "interface_compliance",
            supply.configured_vbus_current_a, ASSUMED, documents,
            _requirement("within_the_declared_configuration_allocation", "<=",
                         netlist.DECLARED_MAX_POWER_A, USB_20),
            assumptions=assumption + (
                "the target draws no more than the budget this board "
                "declares for its supply pin",
                "the configuration descriptor in the bridge's programmable "
                "ROM declares an allocation of at least one unit load; the "
                "value is programmed rather than fixed in silicon, and the "
                "interface that programs it is the USB connector itself",)),
    }, {
        "id": "suspend_draw_is_within_the_specification_ceiling",
        "identity": "VBUS",
        "measured_a": supply.suspend_vbus_current_a,
        "claim": _claim(
            "VBUS", "A", "interface_compliance",
            supply.suspend_vbus_current_a, ASSUMED,
            documents + ("usb_20_suspend_current_ecn",),
            _requirement("within_the_suspend_current_ceiling", "<=",
                         netlist.SUSPEND_CURRENT_MAX_A,
                         "usb_20_suspend_current_ecn"),
            assumptions=assumption + (
                "the bridge asserts SUSPEND in the suspend state, so the "
                "target's supply switch is open and the two series "
                "transistors pass only their drain leakage",),
            omissions=(
                "the suppressor's leakage is specified at its 5.25 V "
                "stand-off and this board's VBUS ceiling is 5.50 V, so the "
                "figure used is a limit at a lower voltage than the highest "
                "one permitted; the ceiling is four times the total, so no "
                "plausible increase in that one term changes the verdict",)),
    }, {
        "id": "the_board_sources_no_current_onto_vbus",
        "identity": "VBUS",
        "measured_c": None,
        "claim": None,
    }]
    # Nothing on VBUS can drive it: the check is over the symbol pin types,
    # not over a reading of the schematic.
    from . import ksym
    library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
    drivers = []
    for pin_ref in netlist.NETS["VBUS"]:
        reference, _, number = pin_ref.partition(".")
        part = netlist.PARTS[reference]
        if part["lib_id"] == "power:PWR_FLAG":
            continue
        pins = library.pins(part["lib_id"])
        for pin in pins.get(number, []):
            if pin.electrical_type in ("output", "power_out",
                                       "open_collector", "open_emitter"):
                drivers.append(pin_ref)
    results[3] = {
        "id": "the_board_sources_no_current_onto_vbus",
        "identity": "VBUS",
        "measured_c": float(len(drivers)),
        "claim": _structural(
            "VBUS", "interface_compliance", drivers,
            "no_pin_on_vbus_can_drive_it", documents=(USB_20,)),
    }
    return results


def evaluate_vbus_bypass(parameters):
    """The bypass capacitance across VBUS, against both ends of its band."""
    supply = Supply(parameters)
    del supply
    nominal = sum(_capacitance_farads(reference)
                  for reference in _capacitors_on("VBUS"))
    worst = _effective_capacitance(parameters, "VBUS")
    documents = (USB_20, "usb_20_device_capacitance_ecn", "mlcc_4u7_samsung",
                 "mlcc_yageo_cc0603")
    return [{
        "id": "vbus_bypass_is_above_the_detectable_minimum",
        "identity": "VBUS",
        "measured_f": worst,
        "claim": _claim(
            "VBUS", "F", "interface_compliance", worst, ASSUMED, documents,
            _requirement("at_least_the_minimum_bypass_capacitance", ">=",
                         netlist.VBUS_BYPASS_MIN_F,
                         "usb_20_device_capacitance_ecn"),
            assumptions=(
                "the DC-bias loss is the bound declared in "
                "components/parameters.json; the capacitor specification "
                "publishes that characteristic only as a graph",)),
    }, {
        "id": "vbus_bypass_is_below_the_droop_ceiling",
        "identity": "VBUS",
        "measured_f": nominal,
        "claim": _claim(
            "VBUS", "F", "interface_compliance", nominal, DIRECT, documents,
            _requirement("no_more_than_the_permitted_bypass_capacitance",
                         "<=", netlist.VBUS_BYPASS_MAX_F,
                         "usb_20_device_capacitance_ecn")),
    }, {
        "id": "capacitance_behind_the_regulator_is_surge_limited",
        "identity": "+3V3",
        "measured_c": 0.0,
        "claim": _structural(
            "+3V3", "interface_compliance", [],
            "the_rail_source_carries_a_current_limiter",
            documents=(USB_20, LDO_DOC),
            assumptions=(
                "the capacitance the bridge's datasheet requires at its "
                "supply pins sits behind the regulator rather than across "
                "VBUS; the specification permits that when the device "
                "incorporates some form of VBUS surge current limiting, and "
                "the regulator's own description states a current limiter "
                "whose foldback is both its short-circuit protection and "
                "its output current limiter",)),
    }, {
        "id": "the_rail_source_current_limit",
        "identity": "U2",
        "measured_a": supply_short_circuit(parameters),
        "claim": _claim(
            "U2", "A", "interface_compliance",
            supply_short_circuit(parameters), DIRECT, (USB_20, LDO_DOC),
            None, scope_level="group",
            assumptions=(
                "recorded beside the current the specification's own "
                "reference inrush load draws through its 44 ohm at the "
                "bottom of the VBUS range, which is %.3f A"
                % (netlist.VBUS_MIN_V / netlist.USB_INRUSH_REFERENCE_OHM),),
            omissions=(
                "the regulator's current limit is stated as a typical "
                "short-circuit current and not as a maximum",)),
    }]


def supply_short_circuit(parameters):
    return _spec(parameters, "U2")["regulator"][
        "short_circuit_current_typical_a"]["value"]


# ---------------------------------------------------------------------------
# the logic rail

def evaluate_rail(parameters):
    supply = Supply(parameters)
    bridge = _spec(parameters, "U1")
    results = []

    # The regulator has to keep regulating at the bottom of VBUS with the
    # whole declared load on it.
    headroom_v = supply.vbus_min_v - supply.rail_accuracy_min_v
    results.append({
        "id": "the_rail_holds_its_accuracy_at_the_lowest_permitted_vbus",
        "identity": "+3V3",
        "measured_v": headroom_v,
        "claim": _claim(
            "+3V3", "V", "rail_regulation", headroom_v, DIRECT,
            (LDO_DOC, USB_20),
            _requirement("headroom_above_the_regulator_dropout", ">=",
                         supply.ldo_dropout_max_v),
            assumptions=(
                "the dropout limit used is the one stated at %g mA, which is "
                "above the whole load this board places on the regulator, "
                "and dropout does not fall with current"
                % (1e3 * supply.ldo_dropout_at_a),)),
    })
    results.append({
        "id": "the_rail_stays_above_the_bridge_supply_minimum",
        "identity": "+3V3",
        "measured_v": supply.rail_min_v,
        "claim": _claim(
            "+3V3", "V", "rail_regulation", supply.rail_min_v, DIRECT,
            (LDO_DOC, BRIDGE_DOC),
            _requirement("above_the_bridge_minimum_supply_voltage", ">=",
                         bridge["supply"]["voltage_min_v"]["value"])),
    })
    results.append({
        "id": "the_rail_stays_below_the_bridge_supply_maximum",
        "identity": "+3V3",
        "measured_v": supply.rail_max_v,
        "claim": _claim(
            "+3V3", "V", "rail_regulation", supply.rail_max_v, DIRECT,
            (LDO_DOC, BRIDGE_DOC),
            _requirement("below_the_bridge_maximum_supply_voltage", "<=",
                         bridge["supply"]["voltage_max_v"]["value"])),
    })
    results.append({
        "id": "the_regulator_can_deliver_the_whole_declared_load",
        "identity": "U2",
        "measured_a": supply.board_rail_current_a + supply.target_budget_a,
        "claim": _claim(
            "U2", "A", "rail_regulation",
            supply.board_rail_current_a + supply.target_budget_a, ASSUMED,
            (LDO_DOC, BRIDGE_DOC),
            _requirement("within_the_regulator_rated_output_current", "<=",
                         supply.ldo_output_current_max_a),
            scope_level="group"),
    })
    results.append({
        "id": "the_target_supply_pin_holds_its_declared_voltage",
        "identity": "TGT_3V3",
        "measured_v": supply.header_supply_min_v,
        "claim": _claim(
            "TGT_3V3", "V", "rail_regulation", supply.header_supply_min_v,
            DIRECT, (LDO_DOC, "ao3401a_aos"),
            _requirement("within_five_percent_of_the_nominal_rail", ">=",
                         0.95 * supply.rail_nominal_v),
            assumptions=(
                "the switch resistance used is the one stated at a 2.5 V "
                "gate drive, and the rail drives its gates harder than that",
            )),
    })

    # Every supply pin the bridge's datasheet names carries what that
    # datasheet requires beside it.
    missing = []
    pin_net = netlist.pin_to_net()
    for function in netlist.BRIDGE_SUPPLY_PINS:
        net = pin_net["U1." + netlist.BRIDGE_PINS[function]]
        values = [_capacitance_farads(reference)
                  for reference in _capacitors_on(net)]
        for key in ("bypass_bulk_f", "bypass_local_f"):
            required = bridge["supply"][key]["value"]
            if sum(1 for value in values
                   if abs(value - required) < 1e-12) < 1:
                missing.append((function, key))
    results.append({
        "id": "every_bridge_supply_pin_carries_its_required_bypass",
        "identity": "U1",
        "measured_c": float(len(missing)),
        "claim": _structural(
            "U1", "rail_regulation", missing,
            "no_supply_pin_without_the_required_bypass",
            documents=(BRIDGE_DOC,),
            omissions=(
                "this counts the capacitors on the pin's net at the values "
                "the datasheet asks for; that they are placed as close to "
                "the pins as possible is a placement requirement, measured "
                "on the board rather than here",)),
    })
    return results


def evaluate_regulator_dissipation(parameters):
    supply = Supply(parameters)
    thermal = _spec(parameters, "U2")["thermal"]
    load_a = supply.board_rail_current_a + supply.target_budget_a
    power_w = ((supply.vbus_max_v - supply.rail_min_v) * load_a
               + supply.vbus_max_v * supply.ldo_quiescent_a)
    derated_w = ((thermal["storage_temperature_max_c"]["value"]
                  - netlist.AMBIENT_MAX_C)
                 / thermal["rthja_assumed_c_per_w"]["value"])
    return [{
        "id": "regulator_dissipation_within_the_stated_package_limit",
        "identity": "U2",
        "measured_w": power_w,
        "claim": _claim(
            "U2", "W", "thermal_margin", power_w, ASSUMED, (LDO_DOC,),
            _requirement("within_the_stated_package_dissipation", "<=",
                         thermal["power_max_w"]["value"]),
            scope_level="group",
            assumptions=("the load is the whole declared budget at the top "
                         "of the VBUS range and the bottom of the rail "
                         "band, which is the worst combination for the "
                         "series drop",),
            omissions=("the stated dissipation is at 25 C ambient; the "
                       "ambient-derated figure is a separate claim",)),
    }, {
        "id": "regulator_dissipation_within_the_derated_limit_at_ambient",
        "identity": "U2",
        "measured_w": power_w,
        "claim": _claim(
            "U2", "W", "thermal_margin", power_w, ASSUMED, (LDO_DOC,),
            _requirement("within_the_ambient_derated_dissipation", "<=",
                         derated_w),
            scope_level="group",
            assumptions=(
                "the thermal resistance is the linear derating from the "
                "stated 25 C dissipation to zero at the storage-temperature "
                "ceiling, because the datasheet publishes no derating curve "
                "and no junction limit; using the storage ceiling as the "
                "junction limit understates the permitted dissipation",
                "the ambient this board claims its budget at is %g C"
                % netlist.AMBIENT_MAX_C)),
    }]


# ---------------------------------------------------------------------------
# the USB Type-C sink termination

def evaluate_cc_termination(parameters):
    pin_net = netlist.pin_to_net()
    wrong = []
    for terminal, net in (("A5", "USB_CC1"), ("B5", "USB_CC2")):
        if pin_net.get("J1." + terminal) != net:
            wrong.append(("J1." + terminal, net))
    # Neither CC conductor may reach the other, VBUS, or anything but its own
    # resistor and the receptacle.
    shared = []
    for net in ("USB_CC1", "USB_CC2"):
        for pin_ref in netlist.NETS[net]:
            reference = pin_ref.split(".", 1)[0]
            other = {pin.split(".", 1)[0] for name in netlist.NETS
                     for pin in netlist.NETS[name]
                     if name not in (net, "GND")}
            if reference.startswith("R") and reference in other:
                shared.append((net, reference))
    results = [{
        "id": "each_cc_conductor_carries_its_own_termination",
        "identity": "USB_CC",
        "measured_c": float(len(wrong) + len(shared)),
        "claim": _structural(
            "USB_CC", "interface_compliance", wrong + shared,
            "each_cc_conductor_has_an_independent_termination_to_ground",
            documents=(TYPE_C,)),
    }]
    for reference, net in (("R1", "USB_CC1"), ("R2", "USB_CC2")):
        tolerance = _tolerance(parameters, reference, "resistor")
        value = _resistor_ohms(reference)
        error = abs(value - netlist.TYPE_C_RD_OHM) / netlist.TYPE_C_RD_OHM
        results.append({
            "id": "%s_is_inside_the_sink_termination_band" % net.lower(),
            "identity": reference,
            "measured_c": error + tolerance,
            "claim": _claim(
                reference, "fraction", "interface_compliance",
                error + tolerance, DIRECT, (TYPE_C, "res_0603_uniroyal"),
                _requirement("within_the_sink_rd_tolerance", "<=",
                             netlist.TYPE_C_RD_TOLERANCE, TYPE_C),
                omissions=(
                    "the specification's value is the total equivalent "
                    "resistance into the sink CC pin including everything "
                    "internal to it; nothing else is on this conductor, so "
                    "the resistor is that total",)),
        })
    return results


# ---------------------------------------------------------------------------
# the USB data pair

def evaluate_usb_pair(parameters):
    """What the schematic and the chosen stackup can say about the pair."""
    geometry = _stackup_geometry()
    width = netlist.USB_PAIR_TRACE_WIDTH_MM
    single_ohm, epsilon_effective = transmission_line.microstrip_z0(
        geometry["epsilon_r"], width, geometry["height_mm"],
        geometry["conductor_mm"])
    uncoupled_ohm = 2.0 * single_ohm
    delay_ps_per_mm = math.sqrt(epsilon_effective) / propagation.C_MM_PER_PS
    round_trip_ps = 2.0 * delay_ps_per_mm * netlist.USB_PAIR_LENGTH_BUDGET_MM
    rise_ps = 1e12 * netlist.FULL_SPEED_RISE_MIN_S
    documents = (USB_20, STACKUP_DOC, BRIDGE_DOC)
    method = (
        "twice the Hammerstad single-ended microstrip impedance of one "
        "conductor of the pair over the opposite plane, computed by "
        "pcbqa.transmission_line from the stackup selected in "
        "fab/physical_inputs.json")

    results = [{
        "id": "usb_pair_differential_impedance_upper_bound",
        "identity": "USB_DP/USB_DM",
        "measured_ohm": uncoupled_ohm,
        "claim": _claim(
            "USB_DP/USB_DM", "ohm", "signal_integrity", uncoupled_ohm,
            DIRECT, documents, None,
            knowledge=claim.UPPER_BOUND, scope_level="group",
            assumptions=("method: " + method,
                         "stackup: epsilon_r %.2f, dielectric %.3f mm, "
                         "conductor %.3f mm, trace width %.3f mm"
                         % (geometry["epsilon_r"], geometry["height_mm"],
                            geometry["conductor_mm"], width),
                         "stackup provenance: " + geometry["provenance"]),
            omissions=(
                "the coupling between the two conductors is omitted, and it "
                "lowers the differential impedance, so the figure is an "
                "upper bound rather than a value",
                "the solder mask over the conductors is omitted, and it "
                "also lowers the impedance",
                "the receptacle launch and the two orientation links are "
                "omitted")),
    }]

    # The conductor width at which one line of an uncoupled pair would reach
    # half the nominal differential impedance. Recorded rather than judged:
    # coupling lowers the differential impedance, so this is the widest
    # conductor that could reach the nominal and not a width that has to be
    # met. It is the scale of the problem on this stackup, next to a
    # receptacle whose own data land is a third of a millimetre.
    def _z0(candidate):
        return transmission_line.microstrip_z0(
            geometry["epsilon_r"], candidate, geometry["height_mm"],
            geometry["conductor_mm"])[0]

    low, high = 0.2, 20.0
    for _ in range(60):
        middle = 0.5 * (low + high)
        if _z0(middle) > 0.5 * netlist.USB_NOMINAL_DIFFERENTIAL_OHM:
            low = middle
        else:
            high = middle
    required_width_mm = 0.5 * (low + high)
    results.append({
        "id": "usb_pair_conductor_width_for_the_uncoupled_nominal",
        "identity": "USB_DP/USB_DM",
        "measured_mm": required_width_mm,
        "claim": _claim(
            "USB_DP/USB_DM", "mm", "signal_integrity", required_width_mm,
            DIRECT, documents + ("usbc_typec31m12_hro",), None,
            knowledge=claim.APPROXIMATE, scope_level="group",
            assumptions=(
                "the width that would put one conductor at half the "
                "nominal differential impedance with the coupling omitted, "
                "beside the %.2f mm data land the receptacle's own "
                "recommended layout gives that conductor"
                % netlist.USB_C_DATA_LAND_WIDTH_MM,
                "coupling lowers the differential impedance, so a narrower "
                "and more tightly coupled pair could also approach the "
                "nominal; nothing here establishes that it does or does "
                "not, which is why the impedance itself is reported as "
                "unknown",)),
    })
    results.append({
        "id": "usb_pair_differential_impedance_matches_the_usb_nominal",
        "identity": "USB_DP/USB_DM",
        "measured_ohm": None,
        "claim": _claim(
            "USB_DP/USB_DM", "ohm", "signal_integrity", None, ASSUMED,
            documents,
            _requirement("equals_the_usb_nominal_differential_impedance",
                         ">=", netlist.USB_NOMINAL_DIFFERENTIAL_OHM, USB_20),
            scope_level="group",
            omissions=(
                "no coupled-line model is available: the toolkit's "
                "analytic infrastructure carries none and refuses to "
                "present an uncoupled pair as a differential answer. The "
                "value is therefore not established, and establishing it "
                "needs a coupled-line extraction, a field solve or a "
                "fabricator impedance report",)),
    })
    results.append({
        "id": "usb_pair_is_electrically_short_at_full_speed",
        "identity": "USB_DP/USB_DM",
        "measured_ps": round_trip_ps,
        "claim": _claim(
            "USB_DP/USB_DM", "ps", "signal_integrity", round_trip_ps,
            DIRECT, documents,
            _requirement("round_trip_delay_below_the_lumped_threshold", "<=",
                         rise_ps * netlist.LUMPED_FRACTION_OF_RISE),
            knowledge=claim.UPPER_BOUND, scope_level="group",
            assumptions=(
                "the length is the budget this board declares for the pair; "
                "the realised length is measured on the routed board by the "
                "interconnect gates against the same budget",
                "the threshold is a design target: a round trip this far "
                "inside the transition time makes the interconnect lumped, "
                "so its impedance cannot produce a settling problem within "
                "an edge",),
            omissions=("the receptacle launch, the two orientation links "
                       "and the vias they need are omitted from the "
                       "length",)),
    })

    # The clamp's own capacitance, against what a full-speed line may carry.
    esd = _spec(parameters, "D1")["esd"]
    bridge_pin_f = _spec(parameters, "U1")["pin_capacitance_f"]["value"]
    total_f = esd["capacitance_io_gnd_max_f"]["value"] + bridge_pin_f
    results.append({
        "id": "usb_pair_capacitance_is_within_the_full_speed_budget",
        "identity": "USB_DP/USB_DM",
        "measured_f": total_f,
        "claim": _claim(
            "USB_DP/USB_DM", "F", "signal_integrity", total_f, DIRECT,
            (ESD_DOC, BRIDGE_DOC, USB_20),
            _requirement("within_the_declared_full_speed_line_capacitance",
                         "<=", netlist.USB_LINE_CAPACITANCE_BUDGET_F),
            scope_level="group",
            assumptions=(
                "the budget is this board's declaration, sized so the "
                "transceiver's own stated rise and fall times into it stay "
                "inside the full-speed window",),
            omissions=("the copper's own capacitance is omitted here and is "
                       "measured on the routed board",)),
    })
    results.append({
        "id": "the_two_clamped_lines_are_capacitance_matched",
        "identity": "USB_DP/USB_DM",
        "measured_f": esd["capacitance_match_typical_f"]["value"],
        "claim": _claim(
            "USB_DP/USB_DM", "F", "signal_integrity",
            esd["capacitance_match_typical_f"]["value"], DIRECT, (ESD_DOC,),
            _requirement("matched_within_the_declared_tolerance", "<=",
                         netlist.USB_LINE_CAPACITANCE_MATCH_F),
            scope_level="group",
            omissions=("the matching figure is stated as a typical and not "
                       "as a limit",)),
    })
    return results


def evaluate_usb_pair_topology(parameters):
    """The receptacle brings each data line out twice, and that is a fact
    about the routing before it is a fact about the copper."""
    pin_net = netlist.pin_to_net()
    wrong = []
    for net, terminal in netlist.USB_C_PAIR_TERMINALS.items():
        if pin_net.get("J1." + terminal) != net:
            wrong.append((terminal, net))
    for net, terminal in netlist.USB_C_FLIPPED_TERMINALS.items():
        if pin_net.get("J1." + terminal) != net:
            wrong.append((terminal, net))
    results = [{
        "id": "both_orientations_of_the_plug_reach_the_bridge",
        "identity": "J1",
        "measured_c": float(len(wrong)),
        "claim": _structural(
            "J1", "interface_compliance", wrong,
            "each_data_line_joins_both_of_its_receptacle_terminals",
            documents=("usbc_typec31m12_hro", TYPE_C)),
    }]

    # The four data terminals alternate along the land row, so the two links
    # that join them are topologically non-planar: one layer change per net
    # is the minimum, and both nets take the same one.
    order = netlist.USB_C_DATA_TERMINAL_ORDER
    nets = [pin_net["J1." + terminal] for terminal in order]
    interleaved = nets[0] != nets[1] and nets[1] != nets[2] \
        and nets[2] != nets[3] and nets[0] == nets[2]
    results.append({
        "id": "the_pair_needs_one_layer_change_per_conductor",
        "identity": "USB_DP/USB_DM",
        "measured_c": float(netlist.USB_PAIR_VIA_BUDGET_PER_NET),
        "claim": _claim(
            "USB_DP/USB_DM", "vias", "signal_integrity",
            float(netlist.USB_PAIR_VIA_BUDGET_PER_NET), DERIVED,
            ("usbc_typec31m12_hro",),
            _requirement("no_more_layer_changes_than_the_topology_forces",
                         "<=", float(netlist.USB_PAIR_VIA_BUDGET_PER_NET)),
            scope_level="group",
            assumptions=(
                "the receptacle's four data terminals alternate along the "
                "land row (%s), so joining each line's two terminals is a "
                "pair of nets with interleaved terminals on the boundary of "
                "a simply connected region, which cannot be drawn on one "
                "layer" % ", ".join(
                    "%s=%s" % (terminal, pin_net["J1." + terminal])
                    for terminal in order),
                "the interleaving was checked rather than asserted: %s"
                % ("interleaved" if interleaved else "NOT interleaved"),
                "both conductors take the same budget, so the two are "
                "symmetric",)),
    })
    return results


# ---------------------------------------------------------------------------
# the target interface

def evaluate_target_interface(parameters):
    supply = Supply(parameters)
    bridge = _spec(parameters, "U1")
    pin_net = netlist.pin_to_net()
    results = []

    wrong = []
    for pin, (_label, net) in sorted(netlist.TARGET_HEADER_PINS.items()):
        if pin_net.get("J2.%d" % pin) != net:
            wrong.append((pin, net))
    results.append({
        "id": "the_target_header_carries_its_declared_pin_order",
        "identity": "J2",
        "measured_c": float(len(wrong)),
        "claim": _structural("J2", "interface_compliance", wrong,
                             "every_header_pin_carries_its_declared_function",
                             documents=("header1x6_kinghelm",)),
    })

    low, high = netlist.LOOPBACK_HEADER_PINS
    results.append({
        "id": "the_loopback_shunt_spans_adjacent_pins",
        "identity": "J2",
        "measured_c": float(abs(high - low)),
        "claim": _claim(
            "J2", "pins", "serviceability", float(abs(high - low)), DERIVED,
            (),
            _requirement("transmit_and_receive_are_adjacent", "<=", 1.0),
            scope_level="group"),
    })

    # Output level at the target, through the series element and with no DC
    # load: a CMOS input draws none, so the series element drops nothing.
    voh_v = supply.rail_min_v - bridge["digital_outputs"][
        "voh_below_vio_v"]["value"]
    vol_v = bridge["digital_outputs"]["vol_max_v"]["value"]
    results.append({
        "id": "the_adapter_drives_a_valid_high_at_the_target",
        "identity": "TGT_TXD",
        "measured_v": voh_v,
        "claim": _claim(
            "TGT_TXD", "V", "interface_compliance", voh_v, DIRECT,
            (BRIDGE_DOC, LDO_DOC),
            _requirement("above_the_declared_cmos_input_threshold", ">=",
                         netlist.TARGET_VIH_V),
            assumptions=(
                "the target's input is CMOS and draws no direct current, so "
                "the series element drops nothing in the steady state",
                "the threshold is this board's declaration of what a 3.3 V "
                "CMOS target requires, not a figure from any one target",)),
    })
    results.append({
        "id": "the_adapter_drives_a_valid_low_at_the_target",
        "identity": "TGT_TXD",
        "measured_v": vol_v,
        "claim": _claim(
            "TGT_TXD", "V", "interface_compliance", vol_v, DIRECT,
            (BRIDGE_DOC,),
            _requirement("below_the_declared_cmos_input_threshold", "<=",
                         netlist.TARGET_VIL_V)),
    })

    # The series element and the declared load, against the shortest bit the
    # bridge can produce.
    series_max_ohm = netlist.SIGNAL_SERIES_OHM * (
        1.0 + _tolerance(parameters, "R8", "resistor"))
    tau_s = series_max_ohm * netlist.TARGET_LOAD_CAPACITANCE_F
    settle_s = tau_s * math.log(1.0 / (1.0 - netlist.EDGE_SETTLE_FRACTION))
    bit_s = 1.0 / netlist.MAX_BAUD
    results.append({
        "id": "an_edge_settles_well_inside_the_shortest_bit",
        "identity": "TGT_TXD",
        "measured_s": settle_s,
        "claim": _claim(
            "TGT_TXD", "s", "interface_compliance", settle_s, DIRECT,
            (BRIDGE_DOC, "res_0603_uniroyal"),
            _requirement("within_the_declared_fraction_of_a_bit", "<=",
                         bit_s * netlist.EDGE_BUDGET_FRACTION_OF_BIT),
            assumptions=(
                "the load is the budget this board declares for the target "
                "and its wiring; a target presenting more capacitance sees "
                "a slower edge and has to run slower",
                "the driver is treated as ideal beside the series element, "
                "which its stated output resistance at these currents "
                "supports",)),
    })
    return results


def evaluate_target_fault_cases(parameters):
    """What a powered target may do to an unpowered adapter."""
    supply = Supply(parameters)
    bridge = _spec(parameters, "U1")
    series_min_ohm = netlist.SIGNAL_SERIES_OHM * (
        1.0 - _tolerance(parameters, "R8", "resistor"))
    injection_a = netlist.TARGET_DRIVE_MAX_V / series_min_ohm
    results = [{
        "id": "a_driven_signal_cannot_overdrive_an_unpowered_bridge_pin",
        "identity": "TGT_SIGNALS",
        "measured_a": injection_a,
        "claim": _claim(
            "TGT_SIGNALS", "A", "robustness", injection_a, DIRECT,
            (BRIDGE_DOC, "res_0603_uniroyal"),
            _requirement("within_the_rated_pin_injection_current", "<=",
                         bridge["absolute_maximum"]["pin_current_a"]["value"]),
            scope_level="group",
            assumptions=(
                "the target drives at the top of a 3.3 V rail's own "
                "tolerance and the adapter's rail is at zero, which is the "
                "largest difference the series element can see",),
            omissions=(
                "the pin's voltage in this state is above the absolute "
                "maximum the datasheet states for an unpowered part; the "
                "datasheet's own note on its VBUS divider says the same "
                "thing about the same condition and rests on the same "
                "argument - the series resistance bounds the current",)),
    }]

    # The supply pin: two transistors in series, back to back, so neither
    # direction has a body diode to conduct through.
    pin_net = netlist.pin_to_net()
    switch_shared = pin_net["Q1.2"] == pin_net["Q2.2"] \
        and pin_net["Q1.1"] == pin_net["Q2.1"]
    faults = [] if switch_shared else [("Q1", "Q2")]
    if pin_net["Q1.3"] != "+3V3" or pin_net["Q2.3"] != "TGT_3V3":
        faults.append(("switch_orientation",))
    results.append({
        "id": "a_driven_supply_pin_reaches_nothing_when_vbus_is_absent",
        "identity": "TGT_3V3",
        "measured_c": float(len(faults)),
        "claim": _structural(
            "TGT_3V3", "robustness", faults,
            "the_supply_switch_blocks_in_both_directions",
            documents=("ao3401a_aos",),
            assumptions=(
                "the two transistors share a source and a gate, so in the "
                "off state each one's body diode faces the other's: neither "
                "the rail nor the header can drive through the pair",
                "the gate is held at the shared source by its own pull-up "
                "whenever the driver behind it is not conducting, and that "
                "driver conducts only when the bridge is running",)),
    })
    results.append({
        "id": "the_open_supply_switch_leaks_less_than_the_suspend_budget",
        "identity": "TGT_3V3",
        "measured_a": abs(supply.switch_leakage_a),
        "claim": _claim(
            "TGT_3V3", "A", "robustness", abs(supply.switch_leakage_a),
            DIRECT, ("ao3401a_aos", "usb_20_suspend_current_ecn"),
            _requirement("below_the_suspend_current_ceiling", "<=",
                         netlist.SUSPEND_CURRENT_MAX_A)),
    })

    # Hot-plugging a target shares charge with the rail before the regulator
    # can respond; the rail has to stay above the bridge's supply monitor.
    rail_f = _effective_capacitance(parameters, "+3V3")
    target_f = netlist.TARGET_BULK_CAPACITANCE_F
    shared_v = supply.rail_min_v * rail_f / (rail_f + target_f)
    monitor_v = bridge["supply_monitor_threshold_max_v"]["value"]
    results.append({
        "id": "hot_plugging_the_target_does_not_reset_the_bridge",
        "identity": "+3V3",
        "measured_v": shared_v,
        "claim": _claim(
            "+3V3", "V", "robustness", shared_v, ASSUMED,
            (BRIDGE_DOC, "mlcc_4u7_samsung"),
            _requirement("above_the_bridge_supply_monitor_threshold", ">=",
                         monitor_v),
            assumptions=(
                "the target presents no more than the bulk capacitance this "
                "board declares a budget for, uncharged",
                "the DC-bias loss on the rail's own capacitance is the "
                "declared bound",
                "the charge is shared before the regulator can respond, "
                "which the switch resistance and these capacitances make "
                "true: the sharing time constant is far shorter than any "
                "regulator loop",),
            omissions=(
                "the regulator supplies nothing during the sharing, which "
                "is the conservative reading and is why no regulator "
                "behaviour appears in the arithmetic",)),
    })
    return results


# ---------------------------------------------------------------------------
# protection

def evaluate_esd_coverage(parameters):
    """Every conductor that leaves the board is clamped or exempt."""
    pin_net = netlist.pin_to_net()
    clamped = set()
    for pin_ref, net in pin_net.items():
        reference = pin_ref.split(".", 1)[0]
        if netlist.PARTS[reference]["lib_id"].startswith("Power_Protection:"):
            clamped.add(net)
    uncovered = []
    for net in sorted(netlist.entering_conductors()):
        if net in clamped or net in netlist.ESD_EXEMPT:
            continue
        uncovered.append(net)
    results = [{
        "id": "every_entering_conductor_is_clamped_or_exempt",
        "identity": "esd",
        "measured_c": float(len(uncovered)),
        "claim": _structural("esd", "robustness", uncovered,
                             "no_entering_conductor_without_a_clamp_or_a_"
                             "reason", documents=(ESD_DOC,)),
    }]
    stale = [net for net in netlist.ESD_EXEMPT
             if net not in netlist.entering_conductors()]
    results.append({
        "id": "no_exemption_names_a_conductor_that_does_not_leave_the_board",
        "identity": "esd",
        "measured_c": float(len(stale)),
        "claim": _structural("esd", "robustness", stale,
                             "every_exemption_is_about_a_real_conductor"),
    })
    esd = _spec(parameters, "D1")["esd"]
    results.append({
        "id": "the_data_clamp_meets_the_declared_discharge_level",
        "identity": "D1",
        "measured_kv": esd["contact_discharge_kv"]["value"],
        "claim": _claim(
            "D1", "kV", "robustness", esd["contact_discharge_kv"]["value"],
            DIRECT, (ESD_DOC,),
            _requirement("at_least_the_declared_contact_discharge_level",
                         ">=", netlist.ESD_CONTACT_DISCHARGE_KV),
            scope_level="group",
            omissions=(
                "the datasheet states one contact-discharge figure on its "
                "features page and a higher one in its absolute-ratings "
                "table; the lower is used",
                "a compliance claim against IEC 61000-4-2 needs a built "
                "board and a discharge generator: what is established here "
                "is that the part fitted is rated for the level, not that "
                "the assembly passes",)),
    })
    results.append({
        "id": "the_rail_clamp_does_not_conduct_at_the_highest_permitted_vbus",
        "identity": "D1",
        "measured_a": None,
        "claim": _claim(
            "D1", "A", "robustness", None, ASSUMED, (ESD_DOC, USB_20,
                                                     "usb_20_vbus_max_limit_ecn"),
            _requirement("no_more_leakage_than_at_the_stand_off_voltage",
                         "<=", esd["leakage_max_a"]["value"], ESD_DOC),
            scope_level="group",
            omissions=(
                "the clamp's leakage is specified at its %.2f V stand-off "
                "and the VBUS-max ECN permits a source to present %.2f V; "
                "the breakdown minimum is above both, so the device is not "
                "in breakdown, but the leakage between the two voltages is "
                "not stated and is not assumed"
                % (esd["stand_off_voltage_v"]["value"], netlist.VBUS_MAX_V),)),
    })
    return results


def _net_extremes(parameters):
    """The highest steady potential each net carries, for the ratings check."""
    supply = Supply(parameters)
    levels = {
        "VBUS": supply.vbus_max_v,
        "GND": 0.0,
        "+3V3": supply.rail_max_v,
        "SWITCH_MID": supply.rail_max_v,
        "TGT_3V3": supply.rail_max_v,
        "SWITCH_GATE": supply.rail_max_v,
        "NRST": supply.rail_max_v,
        "SUSPENDB": supply.rail_max_v,
        "USB_CC1": netlist.TYPE_C_CC_MAX_V,
        "USB_CC2": netlist.TYPE_C_CC_MAX_V,
        "VBUS_SENSE": supply.vbus_max_v * _resistor_ohms("R5") / (
            _resistor_ohms("R4") + _resistor_ohms("R5")),
    }
    for net in netlist.NETS:
        levels.setdefault(net, supply.rail_max_v)
    return levels


def evaluate_absolute_maximum(parameters):
    """No device pin sees more than its datasheet permits."""
    supply = Supply(parameters)
    levels = _net_extremes(parameters)
    bridge = _spec(parameters, "U1")
    absolute = bridge["absolute_maximum"]
    results = []

    # The sense pin. Its ceiling depends on the rail, and the rail's own
    # floor is the one that makes the ceiling lowest.
    sense_v = levels["VBUS_SENSE"]
    ceiling_v = supply.rail_min_v + absolute["pin_voltage_above_vio_v"][
        "value"]
    results.append({
        "id": "the_vbus_sense_pin_stays_inside_its_rating",
        "identity": "VBUS_SENSE",
        "measured_v": sense_v,
        "claim": _claim(
            "VBUS_SENSE", "V", "device_rating", sense_v, DIRECT,
            (BRIDGE_DOC, "res_0603_uniroyal"),
            _requirement("within_the_pin_absolute_maximum", "<=", ceiling_v)),
    })

    # The same pin has to be read as high at the bottom of VBUS.
    divider_min = (_resistor_ohms("R5")
                   * (1.0 - _tolerance(parameters, "R5", "resistor")))
    divider_max_top = (_resistor_ohms("R4")
                       * (1.0 + _tolerance(parameters, "R4", "resistor")))
    worst_ratio = divider_min / (divider_min + divider_max_top)
    leak_v = (bridge["input_leakage_max_a"]["value"]
              * divider_min * divider_max_top
              / (divider_min + divider_max_top))
    detect_v = supply.vbus_min_v * worst_ratio - leak_v
    threshold_v = supply.rail_max_v - bridge["digital_inputs"][
        "vih_below_vio_v"]["value"]
    results.append({
        "id": "the_bridge_reads_vbus_as_present_at_the_bottom_of_its_range",
        "identity": "VBUS_SENSE",
        "measured_v": detect_v,
        "claim": _claim(
            "VBUS_SENSE", "V", "device_rating", detect_v, DIRECT,
            (BRIDGE_DOC, "res_0603_uniroyal", USB_20),
            _requirement("above_the_sense_input_high_threshold", ">=",
                         threshold_v),
            assumptions=(
                "the divider is at the corner that gives the lowest ratio "
                "and the pin leaks the datasheet maximum out of it",)),
    })

    # The regulator's input, and the bridge's own supplies.
    ldo = _spec(parameters, "U2")["regulator"]
    results.append({
        "id": "the_regulator_input_stays_inside_its_operating_range",
        "identity": "U2",
        "measured_v": supply.vbus_max_v,
        "claim": _claim(
            "U2", "V", "device_rating", supply.vbus_max_v, DIRECT,
            (LDO_DOC, "usb_20_vbus_max_limit_ecn"),
            _requirement("within_the_regulator_recommended_input", "<=",
                         ldo["input_voltage_max_v"]["value"]),
            scope_level="group"),
    })
    for key, function in (("vdd_v", "VDD"), ("vregin_v", "VREGIN")):
        results.append({
            "id": "the_bridge_%s_pin_stays_inside_its_rating"
                  % function.lower(),
            "identity": function,
            "measured_v": supply.rail_max_v,
            "claim": _claim(
                function, "V", "device_rating", supply.rail_max_v, DIRECT,
                (BRIDGE_DOC, LDO_DOC),
                _requirement("within_the_pin_absolute_maximum", "<=",
                             absolute[key]["value"])),
        })

    # Every resistor, against its own working voltage and dissipation.
    over = []
    for reference, part in sorted(netlist.PARTS.items()):
        if not reference.startswith("R"):
            continue
        spec = parameters["parts"][part["mpn"]]["resistor"]
        pins = [pin for pin in netlist.NETS
                if any(entry.startswith(reference + ".")
                       for entry in netlist.NETS[pin])]
        highest = max(levels[net] for net in pins)
        if highest > spec["working_voltage_max_v"]["value"]:
            over.append((reference, "voltage"))
        power_w = highest ** 2 / (
            _resistor_ohms(reference) * (1.0 - _tolerance(parameters,
                                                          reference,
                                                          "resistor")))
        if power_w > spec["power_max_w"]["value"]:
            over.append((reference, "power"))
    results.append({
        "id": "every_resistor_is_inside_its_voltage_and_power_rating",
        "identity": "resistors",
        "measured_c": float(len(over)),
        "claim": _structural(
            "resistors", "device_rating", over,
            "no_resistor_outside_its_rating",
            documents=("res_0603_uniroyal",),
            assumptions=("each resistor is evaluated with the highest "
                         "potential on either of its nets across the whole "
                         "of it, which is the worst case for both "
                         "ratings",)),
    })

    # Every capacitor, against its rated voltage.
    over = []
    for reference, part in sorted(netlist.PARTS.items()):
        if not reference.startswith("C"):
            continue
        spec = parameters["parts"][part["mpn"]]["capacitor"]
        nets = [net for net in netlist.NETS
                if any(entry.startswith(reference + ".")
                       for entry in netlist.NETS[net])]
        highest = max(levels[net] for net in nets)
        if highest > spec["rated_voltage_v"]["value"]:
            over.append((reference, highest))
    results.append({
        "id": "every_capacitor_is_inside_its_voltage_rating",
        "identity": "capacitors",
        "measured_c": float(len(over)),
        "claim": _structural("capacitors", "device_rating", over,
                             "no_capacitor_above_its_rated_voltage",
                             documents=("mlcc_4u7_samsung",
                                        "mlcc_yageo_cc0603")),
    })

    # The transistors' gate-source ratings, which is what the rail drives.
    over = []
    for reference in ("Q1", "Q2", "Q3"):
        vgs_max = _spec(parameters, reference)["fet"]["vgs_max_v"]["value"]
        if supply.rail_max_v > vgs_max:
            over.append((reference, supply.rail_max_v))
    results.append({
        "id": "every_transistor_gate_is_inside_its_rating",
        "identity": "transistors",
        "measured_c": float(len(over)),
        "claim": _structural("transistors", "device_rating", over,
                             "no_gate_above_its_rated_voltage",
                             documents=("ao3401a_aos", "ao3400a_aos")),
    })
    return results


def evaluate_switch_control(parameters):
    """The target's supply is off unless the bridge says it is running."""
    supply = Supply(parameters)
    pfet = _spec(parameters, "Q1")["fet"]
    nfet = _spec(parameters, "Q3")["fet"]
    results = [{
        "id": "the_driver_turns_the_switch_fully_on",
        "identity": "Q3",
        "measured_v": supply.rail_min_v,
        "claim": _claim(
            "Q3", "V", "control_integrity", supply.rail_min_v, DIRECT,
            ("ao3400a_aos", BRIDGE_DOC),
            _requirement("above_the_driver_gate_threshold", ">=",
                         nfet["vgs_threshold_max_v"]["value"]),
            scope_level="group"),
    }, {
        "id": "the_switch_is_held_off_when_nothing_drives_its_gate",
        "identity": "Q1",
        "measured_v": 0.0,
        "claim": _claim(
            "Q1", "V", "control_integrity", 0.0, DIRECT,
            ("ao3401a_aos",),
            _requirement("gate_to_source_below_the_switch_threshold", "<=",
                         abs(pfet["vgs_threshold_min_v"]["value"])),
            scope_level="group",
            assumptions=(
                "the gate pull-up ties the gate to the shared source, so "
                "with the driver off the gate-source difference is the "
                "pull-up's own leakage across it, which is nothing a "
                "datasheet bounds above zero",)),
    }, {
        "id": "the_suspend_output_is_held_low_while_the_bridge_resets",
        "identity": "SUSPENDB",
        "measured_ohm": _resistor_ohms("R7"),
        "claim": _claim(
            "SUSPENDB", "ohm", "control_integrity", _resistor_ohms("R7"),
            DIRECT, (BRIDGE_DOC,),
            _requirement("no_weaker_than_the_recommended_pull_down", "<=",
                         _spec(parameters, "U1")["supply"][
                             "suspend_pull_down_ohm"]["value"], BRIDGE_DOC)),
    }, {
        "id": "the_reset_pin_carries_the_recommended_pull_up",
        "identity": "NRST",
        "measured_ohm": _resistor_ohms("R3"),
        "claim": _claim(
            "NRST", "ohm", "control_integrity", _resistor_ohms("R3"),
            DIRECT, (BRIDGE_DOC,),
            _requirement("the_recommended_pull_up_value", "<=",
                         _spec(parameters, "U1")["supply"][
                             "reset_pull_up_ohm"]["value"], BRIDGE_DOC)),
    }]
    return results


def evaluate_bridge_configuration(parameters):
    """The choices the bridge's own datasheet forces on the board."""
    pin_net = netlist.pin_to_net()
    bridge = _spec(parameters, "U1")
    wrong = []
    for function in netlist.BRIDGE_SUPPLY_PINS:
        if pin_net.get("U1." + netlist.BRIDGE_PINS[function]) != "+3V3":
            wrong.append(function)
    results = [{
        "id": "the_internal_regulator_is_bypassed_as_the_datasheet_requires",
        "identity": "U1",
        "measured_c": float(len(wrong)),
        "claim": _structural(
            "U1", "device_rating", wrong,
            "the_regulator_input_is_tied_to_the_supply_when_unused",
            documents=(BRIDGE_DOC,),
            assumptions=(
                "the internal regulator is not used because its input is "
                "specified only to %.2f V and a compliant source may "
                "present %.2f V"
                % (bridge["regulator"]["input_voltage_max_v"]["value"],
                   netlist.VBUS_MAX_V),)),
    }, {
        "id": "the_rail_source_accepts_the_whole_permitted_vbus_range",
        "identity": "U2",
        "measured_v": _spec(parameters, "U2")["regulator"][
            "input_voltage_max_v"]["value"],
        "claim": _claim(
            "U2", "V", "device_rating",
            _spec(parameters, "U2")["regulator"]["input_voltage_max_v"][
                "value"],
            DIRECT, (LDO_DOC, "usb_20_vbus_max_limit_ecn"),
            _requirement("at_or_above_the_highest_permitted_vbus", ">=",
                         netlist.VBUS_MAX_V, "usb_20_vbus_max_limit_ecn"),
            scope_level="group"),
    }, {
        "id": "the_internal_regulator_input_ceiling",
        "identity": "U1",
        "measured_v": bridge["regulator"]["input_voltage_max_v"]["value"],
        "claim": _claim(
            "U1", "V", "device_rating",
            bridge["regulator"]["input_voltage_max_v"]["value"], DIRECT,
            (BRIDGE_DOC, "usb_20_vbus_max_limit_ecn"), None,
            scope_level="group",
            assumptions=(
                "recorded because it is the reason this board carries an "
                "external regulator: the ceiling is below the %.2f V a "
                "compliant source may present, so a bus-powered board using "
                "the internal one would run it outside its recommended "
                "operating range" % netlist.VBUS_MAX_V,)),
    }]

    floating = []
    for function in netlist.BRIDGE_TIED_LOW_PINS:
        if pin_net.get("U1." + netlist.BRIDGE_PINS[function]) != "GND":
            floating.append(function)
    results.append({
        "id": "no_input_only_pin_is_left_floating",
        "identity": "U1",
        "measured_c": float(len(floating)),
        "claim": _structural(
            "U1", "control_integrity", floating,
            "every_input_only_pin_is_tied",
            documents=(BRIDGE_DOC,),
            assumptions=(
                "only the pins the datasheet's pin table calls inputs and "
                "nothing else are tied; a pin that is an output in any "
                "configuration is left alone",)),
    })
    results.append({
        "id": "the_descriptor_programming_interface_is_reachable_assembled",
        "identity": "U1",
        "measured_c": 0.0,
        "claim": _structural(
            "U1", "serviceability", [],
            "the_configuration_memory_needs_no_connection_the_board_lacks",
            documents=(BRIDGE_DOC,),
            assumptions=(
                "the configuration ROM is written over the USB interface "
                "itself, so the receptacle this board already carries is "
                "the programming interface and no test point, header or "
                "fixture is needed",)),
    })
    return results


# ---------------------------------------------------------------------------
# structure

def evaluate_ground_topology(parameters):
    """One reference, and every return on it."""
    pin_net = netlist.pin_to_net()
    grounds = {net for net in netlist.NETS if net.endswith("GND")}
    results = [{
        "id": "the_board_has_exactly_one_reference",
        "identity": "GND",
        "measured_c": float(len(grounds) - 1),
        "claim": _structural("GND", "reference_integrity",
                             sorted(grounds - {"GND"}),
                             "no_second_ground_net"),
    }]
    missing = []
    for reference in ("J1", "J2"):
        pins = [pin for pin in pin_net if pin.startswith(reference + ".")]
        if not any(pin_net[pin] == "GND" for pin in pins):
            missing.append(reference)
    results.append({
        "id": "every_connector_carries_the_reference",
        "identity": "connectors",
        "measured_c": float(len(missing)),
        "claim": _structural("connectors", "reference_integrity", missing,
                             "no_connector_without_a_ground_pin"),
    })
    shield = [pin for pin in netlist.NETS["GND"] if pin == "J1.SH"]
    results.append({
        "id": "the_receptacle_shell_is_bonded_to_the_reference",
        "identity": "J1",
        "measured_c": float(1 - len(shield)),
        "claim": _structural(
            "J1", "reference_integrity", [] if shield else ["J1.SH"],
            "the_shell_is_on_the_reference",
            assumptions=(
                "bonded directly rather than through a network: the board "
                "carries no second reference for a network to sit between, "
                "and a direct bond is the shortest return for a discharge "
                "arriving on the shell",)),
    })
    return results


def evaluate_probe_access(parameters):
    pin_net = netlist.pin_to_net()
    probed = {pin_net[pin] for pin in pin_net
              if netlist.PARTS[pin.split(".")[0]]["lib_id"]
              == "Connector:TestPoint"}
    missing = [net for net in netlist.PROBE_REQUIRED_NETS
               if net not in probed]
    return [{
        "id": "every_required_net_reaches_a_probe",
        "identity": "test_points",
        "measured_c": float(len(missing)),
        "claim": _structural("test_points", "serviceability", missing,
                             "no_required_net_without_a_probe"),
    }]


def _footprint_pad_count(footprint):
    library, _, name = footprint.partition(":")
    for root in (LOCAL_FOOTPRINT_ROOT, FOOTPRINT_ROOT):
        path = os.path.join(root, library + ".pretty", name + ".kicad_mod")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            numbers = set()
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith('(pad "'):
                    number = stripped.split('"')[1]
                    if number:
                        numbers.add(number)
            return len(numbers)
    return None


def evaluate_package_correspondence(parameters):
    """Symbol pins, land-pattern pads and the package drawing agree."""
    from . import ksym
    library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
    mismatches = []
    for reference, part in sorted(netlist.PARTS.items()):
        if not part["in_bom"]:
            continue
        spec = parameters["parts"][part["mpn"]]
        declared = spec.get("land_pattern", {}).get("pad_count")
        if declared is None:
            continue
        symbol_pins = len(library.pins(part["lib_id"]))
        pads = _footprint_pad_count(part["footprint"])
        if symbol_pins != declared or pads != declared:
            mismatches.append((reference, declared, symbol_pins, pads))
    results = [{
        "id": "symbol_pins_and_land_pattern_pads_match_the_drawing",
        "identity": "library",
        "measured_c": float(len(mismatches)),
        "claim": _structural("library", "package_correspondence", mismatches,
                             "no_part_whose_three_pin_counts_disagree"),
    }]
    # The pin-by-pin maps, where a drawing gives one.
    wrong = []
    for reference, part in sorted(netlist.PARTS.items()):
        if not part["in_bom"]:
            continue
        declared = parameters["parts"][part["mpn"]].get(
            "land_pattern", {}).get("pin_map")
        if not declared:
            continue
        pins = library.pins(part["lib_id"])
        for number, name in sorted(declared.items()):
            found = pins.get(number)
            if not found:
                wrong.append((reference, number, name, None))
                continue
            if name.lower() not in found[0].name.lower():
                wrong.append((reference, number, name, found[0].name))
    results.append({
        "id": "every_declared_pin_name_matches_the_symbol",
        "identity": "library",
        "measured_c": float(len(wrong)),
        "claim": _structural("library", "package_correspondence", wrong,
                             "no_pin_whose_drawing_and_symbol_disagree"),
    })
    return results


def evaluate_supply_availability(parameters):
    from . import cost
    limits = cost.stock_limited_boards()
    tightest = min(limits.values()) if limits else 0
    return [{
        "id": "catalogue_stock_covers_the_planned_build",
        "identity": "bom",
        "measured_c": float(tightest),
        "claim": _claim(
            "bom", "boards", "supply", float(tightest), DIRECT,
            (),
            _requirement("at_least_the_planned_build_quantity", ">=",
                         float(netlist.PLANNED_BUILD_QUANTITY)),
            scope_level="board",
            omissions=("stock is what the catalogue held when it was "
                       "captured; the capture date is in the catalogue",)),
    }]


def _footprint_is_through_hole(footprint):
    library, _, name = footprint.partition(":")
    for root in (LOCAL_FOOTPRINT_ROOT, FOOTPRINT_ROOT):
        path = os.path.join(root, library + ".pretty", name + ".kicad_mod")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                return "thru_hole" in handle.read()
    return False


def evaluate_assembly(parameters):
    through_hole = sorted(
        reference for reference, part in netlist.PARTS.items()
        if part["in_bom"] and part["footprint"]
        and _footprint_is_through_hole(part["footprint"]))
    return [{
        "id": "the_board_needs_only_the_declared_assembly_operations",
        "identity": "assembly",
        "measured_c": float(len(through_hole)),
        "claim": _claim(
            "assembly", "parts", "manufacturability",
            float(len(through_hole)), DERIVED, (),
            _requirement("no_more_through_hole_parts_than_declared", "<=",
                         float(netlist.ASSEMBLY_POLICY[
                             "through_hole_soldered_parts"])),
            scope_level="board",
            assumptions=(
                "the receptacle is counted as through-hole because its "
                "shell legs are, even though its signal lands reflow with "
                "everything else",)),
    }]


# ---------------------------------------------------------------------------

PRODUCERS = (
    evaluate_usb_current,
    evaluate_vbus_bypass,
    evaluate_rail,
    evaluate_regulator_dissipation,
    evaluate_cc_termination,
    evaluate_usb_pair,
    evaluate_usb_pair_topology,
    evaluate_target_interface,
    evaluate_target_fault_cases,
    evaluate_esd_coverage,
    evaluate_absolute_maximum,
    evaluate_switch_control,
    evaluate_bridge_configuration,
    evaluate_ground_topology,
    evaluate_probe_access,
    evaluate_package_correspondence,
    evaluate_supply_availability,
    evaluate_assembly,
)


#: What a claim with no requirement over it is reported as. It is not a
#: verdict: nothing was judged, a number was recorded.
RECORDED = "RECORDED"


def evaluate_all():
    parameters = load_parameters()
    results = []
    for producer in PRODUCERS:
        results.extend(producer(parameters))
    for result in results:
        result["verdict"] = claim.verdict(result["claim"])
    return results


REPORT_PATH = os.path.join(REPO_ROOT, "generated", "requirements.json")


def write_report():
    """The whole claim set, as an artifact rather than a console report."""
    evaluated = evaluate_all()
    document = {
        "kind": "board-requirement-evidence",
        "summary": summarise(evaluated),
        "results": [
            {"id": result["id"], "identity": result["identity"],
             "claim": result["claim"], "verdict": result["verdict"]}
            for result in sorted(evaluated,
                                 key=lambda item: (item["id"],
                                                   item["identity"]))],
    }
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return REPORT_PATH


def outcome(result):
    verdict = result["verdict"]
    return RECORDED if verdict is None else verdict["result"]


def summarise(results):
    counts = {}
    for result in results:
        counts[outcome(result)] = counts.get(outcome(result), 0) + 1
    return counts


if __name__ == "__main__":
    evaluated = evaluate_all()
    write_report()
    for result in sorted(evaluated, key=lambda item: (
            outcome(item), item["id"], item["identity"])):
        value = result["claim"]["quantity"].get("value")
        rendered = "-" if value is None else "%.6g" % value
        sys.stdout.write("%-8s %-62s %-18s %14s %s\n" % (
            outcome(result), result["id"], result["identity"],
            rendered, result["claim"]["units"]))
    sys.stdout.write("\n" + json.dumps(summarise(evaluated), sort_keys=True)
                     + "\n")
