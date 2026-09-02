from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from design import (build, cost, evidence, ksym, layout,  # noqa: E402
                    libraries, manifest, netlist, rules, simulation)

TOOLKIT_ROOT = os.path.join(REPO_ROOT, "tooling", "PCBA_AutoDesignAndTest")
if TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, TOOLKIT_ROOT)

from pcbqa.sim import model_registry, ngspice  # noqa: E402
from pcbqa.sim import scenario as sim_scenario  # noqa: E402


class DesignSource(unittest.TestCase):
    def test_pin_assignment_is_unique(self):
        mapping = netlist.pin_to_net()
        self.assertEqual(mapping and len(mapping),
                         sum(len(pins) for pins in netlist.NETS.values()))

    def test_every_symbol_pin_is_connected_or_declared_no_connect(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        mapping = netlist.pin_to_net()
        declared = set(netlist.NO_CONNECT)
        unresolved = []
        for reference, part in netlist.PARTS.items():
            for number in library.pins(part["lib_id"]):
                pin_ref = "%s.%s" % (reference, number)
                if pin_ref not in mapping and pin_ref not in declared:
                    unresolved.append(pin_ref)
        self.assertEqual(unresolved, [])

    def test_declared_pins_exist_on_the_symbol(self):
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        missing = []
        for pin_ref in list(netlist.pin_to_net()) + list(netlist.NO_CONNECT):
            reference, _, number = pin_ref.partition(".")
            lib_id = netlist.PARTS[reference]["lib_id"]
            if number not in library.pins(lib_id):
                missing.append(pin_ref)
        self.assertEqual(missing, [])

    def test_the_library_holds_nothing_the_design_source_does_not_write(self):
        produced = set(libraries.artifacts())
        present = set()
        for root, _, names in os.walk(libraries.FOOTPRINT_DIR):
            for name in names:
                present.add(os.path.join(root, name))
        present.add(libraries.SYMBOL_LIB_PATH)
        self.assertEqual(sorted(present - produced), [])

    def test_the_committed_design_files_are_the_generated_ones(self):
        with open(build.schematic_path(), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), build.generate_schematic_text())
        for path, text in libraries.artifacts().items():
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), text, path)


class UsbInterface(unittest.TestCase):
    def setUp(self):
        self.mapping = netlist.pin_to_net()

    def test_each_data_line_reaches_both_of_its_receptacle_terminals(self):
        for net, terminal in netlist.USB_C_PAIR_TERMINALS.items():
            self.assertEqual(self.mapping["J1." + terminal], net)
        for net, terminal in netlist.USB_C_FLIPPED_TERMINALS.items():
            self.assertEqual(self.mapping["J1." + terminal], net)

    def test_the_receptacle_data_terminals_alternate_along_the_land_row(self):
        """The fact that forces one layer change per conductor."""
        nets = [self.mapping["J1." + terminal]
                for terminal in netlist.USB_C_DATA_TERMINAL_ORDER]
        self.assertEqual(len(set(nets)), 2)
        self.assertNotEqual(nets[0], nets[1])
        self.assertNotEqual(nets[1], nets[2])
        self.assertEqual(nets[0], nets[2])
        self.assertEqual(nets[1], nets[3])

    def test_each_cc_conductor_carries_one_independent_termination(self):
        for net, reference in (("USB_CC1", "R1"), ("USB_CC2", "R2")):
            self.assertEqual(sorted(netlist.NETS[net]),
                             sorted(["J1." + terminal
                                     for terminal in
                                     netlist.USB_C_PINS[net[-3:]]]
                                    + [reference + ".1"]))
            self.assertEqual(self.mapping[reference + ".2"], "GND")

    def test_the_sink_termination_is_inside_the_specification_band(self):
        for reference in ("R1", "R2"):
            value = rules._resistor_ohms(reference)
            error = abs(value - netlist.TYPE_C_RD_OHM) / netlist.TYPE_C_RD_OHM
            tolerance = rules._tolerance(rules.load_parameters(), reference,
                                         "resistor")
            self.assertLessEqual(error + tolerance,
                                 netlist.TYPE_C_RD_TOLERANCE)

    def test_the_data_lines_pass_through_the_suppressor(self):
        for net, pins in (("USB_DP", ("1", "6")), ("USB_DM", ("3", "4"))):
            for pin in pins:
                self.assertEqual(self.mapping["D1." + pin], net)
        self.assertEqual(self.mapping["D1.2"], "GND")
        self.assertEqual(self.mapping["D1.5"], "VBUS")

    def test_nothing_on_vbus_can_drive_it(self):
        results = {result["id"]: result
                   for result in rules.evaluate_usb_current(
                       rules.load_parameters())}
        self.assertEqual(
            results["the_board_sources_no_current_onto_vbus"][
                "claim"]["quantity"]["value"], 0.0)


class TargetInterface(unittest.TestCase):
    def test_the_header_carries_the_declared_pin_order(self):
        mapping = netlist.pin_to_net()
        for pin, (_label, net) in netlist.TARGET_HEADER_PINS.items():
            self.assertEqual(mapping["J2.%d" % pin], net)

    def test_transmit_and_receive_are_adjacent_so_one_shunt_loops_back(self):
        low, high = netlist.LOOPBACK_HEADER_PINS
        self.assertEqual(abs(high - low), 1)
        self.assertEqual(netlist.TARGET_HEADER_PINS[low][0], "TXD")
        self.assertEqual(netlist.TARGET_HEADER_PINS[high][0], "RXD")

    def test_every_target_signal_carries_its_series_element(self):
        mapping = netlist.pin_to_net()
        for reference in ("R8", "R9", "R10", "R11"):
            bridge_side = mapping[reference + ".1"]
            target_side = mapping[reference + ".2"]
            self.assertTrue(bridge_side.startswith("UART_"), reference)
            self.assertTrue(target_side.startswith("TGT_"), reference)
            self.assertEqual(rules._resistor_ohms(reference),
                             netlist.SIGNAL_SERIES_OHM)

    def test_the_supply_switch_blocks_in_both_directions(self):
        mapping = netlist.pin_to_net()
        self.assertEqual(mapping["Q1.2"], mapping["Q2.2"])
        self.assertEqual(mapping["Q1.1"], mapping["Q2.1"])
        self.assertEqual(mapping["Q1.3"], "+3V3")
        self.assertEqual(mapping["Q2.3"], "TGT_3V3")

    def test_the_switch_is_driven_from_the_suspend_output(self):
        mapping = netlist.pin_to_net()
        self.assertEqual(mapping["U1." + netlist.BRIDGE_PINS["SUSPENDB"]],
                         mapping["Q3.1"])
        self.assertEqual(mapping["Q3.2"], "GND")
        self.assertEqual(mapping["Q3.3"], mapping["Q1.1"])


class Evidence(unittest.TestCase):
    def test_the_frozen_documents_are_intact_and_all_referenced(self):
        self.assertEqual(evidence.verify(), [])

    def test_the_committed_index_is_the_computed_one(self):
        self.assertEqual(evidence.load_index(), evidence.compute_index())

    def test_every_parameter_names_a_frozen_document(self):
        known = set(evidence.load_index()["documents"])
        unknown = set()

        def walk(node):
            if isinstance(node, dict):
                document = node.get("document")
                if isinstance(document, str) and document not in known:
                    unknown.add(document)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(rules.load_parameters()["parts"])
        self.assertEqual(sorted(unknown), [])

    def test_every_bom_part_has_frozen_parameters_and_a_catalogue_entry(self):
        parameters = rules.load_parameters()["parts"]
        catalog = rules.load_catalog()["parts"]
        for reference, part in netlist.PARTS.items():
            if not part["in_bom"]:
                continue
            self.assertIn(part["mpn"], parameters, reference)
            self.assertIn(part["lcsc"], catalog, reference)

    def test_the_catalogue_holds_no_part_the_board_does_not_use(self):
        used = {part["lcsc"] for part in netlist.PARTS.values()
                if part["in_bom"]}
        self.assertEqual(sorted(set(rules.load_catalog()["parts"]) - used), [])


class Requirements(unittest.TestCase):
    def setUp(self):
        self.results = rules.evaluate_all()

    def test_no_board_rule_fails(self):
        failed = sorted(result["id"] for result in self.results
                        if rules.outcome(result) == "FAIL")
        self.assertEqual(failed, [])

    def test_the_unresolved_claims_are_the_two_that_say_why(self):
        unknown = sorted({result["id"] for result in self.results
                          if rules.outcome(result) == "UNKNOWN"})
        self.assertEqual(unknown, [
            "the_rail_clamp_does_not_conduct_at_the_highest_permitted_vbus",
            "usb_pair_differential_impedance_matches_the_usb_nominal",
        ])

    def test_the_committed_requirement_evidence_is_current(self):
        with open(rules.REPORT_PATH, "r", encoding="utf-8") as handle:
            committed = json.load(handle)
        rules.write_report()
        with open(rules.REPORT_PATH, "r", encoding="utf-8") as handle:
            self.assertEqual(committed, json.load(handle))

    def test_every_probe_required_net_exists(self):
        for net in netlist.PROBE_REQUIRED_NETS:
            self.assertIn(net, netlist.NETS)

    def test_every_entering_conductor_is_clamped_or_exempt(self):
        parameters = rules.load_parameters()
        for result in rules.evaluate_esd_coverage(parameters):
            value = result["claim"]["quantity"].get("value")
            if result["claim"]["units"] == "violations":
                self.assertEqual(value, 0.0, result["id"])

    def test_the_board_stays_inside_one_unit_load_in_every_state(self):
        supply = rules.Supply(rules.load_parameters())
        for current in (supply.unconfigured_vbus_current_a,
                        supply.configured_vbus_current_a):
            self.assertLessEqual(current, netlist.UNIT_LOAD_A)
        self.assertLessEqual(supply.suspend_vbus_current_a,
                             netlist.SUSPEND_CURRENT_MAX_A)


class Supply(unittest.TestCase):
    def test_stock_covers_the_planned_build(self):
        limits = cost.stock_limited_boards()
        self.assertGreaterEqual(min(limits.values()),
                                netlist.PLANNED_BUILD_QUANTITY)

    def test_every_bom_line_prices(self):
        report = cost.bom_cost(netlist.PLANNED_BUILD_QUANTITY)
        self.assertGreater(report["per_board_usd"], 0.0)
        self.assertEqual(len(report["lines"]), len(cost.line_items()))


class Scenarios(unittest.TestCase):
    def setUp(self):
        self.documents = simulation.documents()

    def test_every_scenario_validates(self):
        for name, document in self.documents.items():
            sim_scenario.validate_scenario(document)
            del name

    def test_the_committed_scenarios_are_the_generated_ones(self):
        present = sorted(os.listdir(simulation.SIM_DIR))
        self.assertEqual(present, sorted(self.documents))
        for name, document in self.documents.items():
            with open(os.path.join(simulation.SIM_DIR, name), "r",
                      encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), document, name)

    def test_every_scenario_runs_and_every_assertion_holds(self):
        backend = ngspice.backend_identity()
        if not backend["available"]:
            self.skipTest("no ngspice backend: " + str(backend["detail"]))
        registry = model_registry.ModelRegistry([])
        work = os.path.join(REPO_ROOT, "out", "sim")
        for name, document in sorted(self.documents.items()):
            result = ngspice.run_scenario(
                registry, document, os.path.join(work, document["name"]))
            self.assertEqual(result["status"], "ran", name)
            self.assertTrue(result["converged"], name)
            for measurement, record in result["measurements"].items():
                verdict = record["verdict"]
                if verdict is None:
                    continue
                self.assertEqual(verdict["result"], "PASS",
                                 "%s: %s" % (name, measurement))

    def test_the_simulated_hot_plug_agrees_with_the_requirement(self):
        backend = ngspice.backend_identity()
        if not backend["available"]:
            self.skipTest("no ngspice backend: " + str(backend["detail"]))
        registry = model_registry.ModelRegistry([])
        document = self.documents["pre_layout_hot_plug.json"]
        result = ngspice.run_scenario(
            registry, document,
            os.path.join(REPO_ROOT, "out", "sim", document["name"]))
        simulated = result["measurements"]["logic_rail_minimum"][
            "claim"]["quantity"]["value"]
        stated = [entry for entry in rules.evaluate_target_fault_cases(
            rules.load_parameters())
            if entry["id"] == "hot_plugging_the_target_does_not_reset_the_"
                              "bridge"][0]["measured_v"]
        self.assertAlmostEqual(simulated, stated, delta=0.01)


class Manifest(unittest.TestCase):
    def setUp(self):
        self.document = manifest.document()

    def test_the_committed_manifest_is_the_generated_one(self):
        with open(manifest.MANIFEST_PATH, "r", encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), self.document)

    def test_every_connector_contract_matches_the_netlist(self):
        mapping = netlist.pin_to_net()
        for contract in self.document["connector_contracts"]:
            reference = contract["reference"]
            for number, net in contract["pin_map"].items():
                self.assertEqual(mapping["%s.%s" % (reference, number)], net)

    def test_the_constraint_floor_is_what_the_project_is_written_with(self):
        floor = self.document["checks"]["drc"]["constraint_floor"]
        self.assertEqual(floor["rules"], build.DESIGN_RULES)
        for entry in build.NET_CLASSES:
            self.assertIn(entry["name"], floor["net_classes"])

    def test_every_declared_scenario_file_exists(self):
        for stage, names in self.document["simulation"]["stages"].items():
            for name in names:
                self.assertTrue(
                    os.path.isfile(os.path.join(REPO_ROOT, name)),
                    "%s: %s" % (stage, name))
        for stage in self.document["simulation"]["required_stages"]:
            self.assertIn(stage, self.document["simulation"]["stages"])

    def test_every_placement_rule_counts_what_the_netlist_holds(self):
        for rule in self.document["placement_rules"]:
            pattern = re.compile(rule["reference_regex"])
            found = [reference for reference in netlist.PARTS
                     if pattern.match(reference)]
            self.assertEqual(len(found), rule["count"], rule["id"])

    def test_every_timing_path_names_a_terminal_the_netlist_carries(self):
        mapping = netlist.pin_to_net()
        interface = self.document["timing"]["interfaces"]["usb_data"]
        for path in interface["routes"]["paths"]:
            for step in path["steps"]:
                for key in ("from", "to"):
                    pin = step[key].strip("^$").replace("\\", "")
                    self.assertEqual(mapping[pin], step["net"], path["id"])
        self.assertEqual(interface["expected_path_count"],
                         len(interface["routes"]["paths"]))

    def test_the_timing_budgets_agree_with_the_design_source(self):
        interface = self.document["timing"]["interfaces"]["usb_data"]
        self.assertAlmostEqual(
            interface["limits"]["max_delay_ps"],
            netlist.USB_PAIR_LENGTH_BUDGET_MM
            * netlist.USB_PAIR_DELAY_PS_PER_MM)
        for group in interface["groups"].values():
            self.assertEqual(group["max_length_spread_mm"],
                             netlist.USB_PAIR_SKEW_BUDGET_MM)
        self.assertAlmostEqual(interface["max_unreferenced_mm"],
                               sum(layout.unreferenced_budgets_mm()))

    def test_the_reference_budget_prices_every_declared_interruption(self):
        """The budget is the list in the design source, priced once each.

        Not a tolerance: every millimetre in it belongs to something the
        design source says is there and could not have left out.
        """
        front, back = layout.unreferenced_budgets_mm()
        self.assertEqual(len(netlist.USB_PAIR_REFERENCE_INTERRUPTIONS), 5)
        self.assertAlmostEqual(
            front,
            2 * (netlist.USB_PAIR_TRACE_WIDTH_MM + 2 * layout.CLEARANCE_MM)
            + (layout.VIA_DIAMETER_MM + 2 * layout.CLEARANCE_MM)
            + 3 * layout.ZONE_MIN_WIDTH_MM)
        span = max(abs(layout.FANOUT_X_MM[netlist.USB_C_PAIR_TERMINALS[net]]
                       - layout.FANOUT_X_MM[
                           netlist.USB_C_FLIPPED_TERMINALS[net]])
                   for net in netlist.USB_C_PAIR_TERMINALS)
        self.assertAlmostEqual(back, span + 2 * layout.CLEARANCE_MM)


class Board(unittest.TestCase):
    def test_every_part_with_a_footprint_has_a_seed_pose(self):
        placed = layout.seed_placement()
        missing = sorted(reference for reference, part in netlist.PARTS.items()
                         if part["footprint"] and reference not in placed)
        self.assertEqual(missing, [])

    def test_the_locked_set_is_the_board_s_mechanical_contract(self):
        expected = {"D1", "U1"}
        for reference, part in netlist.PARTS.items():
            if not part["footprint"]:
                continue
            if reference.startswith("TP") or (
                    reference[0] == "J" and reference[1:].isdigit()):
                expected.add(reference)
        self.assertEqual(set(layout.LOCKED_REFERENCES), expected)

    def test_the_two_connectors_are_at_opposite_ends_of_the_outline(self):
        placed = layout.seed_placement()
        receptacle_y = placed["J1"][1]
        header_y = placed["J2"][1]
        self.assertLess(receptacle_y, layout.BOARD_H_MM / 4.0)
        self.assertGreater(header_y, 3.0 * layout.BOARD_H_MM / 4.0)

    def test_the_suppressor_sits_between_the_receptacle_and_the_bridge(self):
        placed = layout.seed_placement()
        self.assertLess(placed["J1"][1], placed["D1"][1])
        self.assertLess(placed["D1"][1], placed["U1"][1])

    def test_the_front_pour_is_kept_out_of_the_pair_s_corridor(self):
        """The corridor is why the microstrip model describes this board."""
        x0, _y0, x1, _y1 = layout.pair_corridor_mm()
        stackup = rules.load_stackup()
        dielectric = [layer for layer in stackup["layers"]
                      if layer["kind"] == "dielectric"][0]
        half = (x1 - x0) / 2.0
        self.assertGreater(half - netlist.USB_PAIR_TRACE_WIDTH_MM,
                           dielectric["thickness_mm"] / 2.0)

    def test_no_stitch_stands_inside_the_pair_s_own_area(self):
        board, _ = layout.build(with_copper=False)
        x0, y0, x1, y1 = layout.pair_plane_region_mm()
        for x_mm, y_mm in layout.stitch_positions(board):
            self.assertFalse(x0 <= x_mm <= x1 and y0 <= y_mm <= y1)

    def test_nothing_lands_part_way_along_a_pair_conductor(self):
        """Where the pair meets a via or a pad, it meets it end on.

        Copper landing part-way along a conductor leaves the meeting point
        ambiguous over the width of the overlap, and a length measured
        through it has to carry that ambiguity as an error bar. The pair is
        drawn with a vertex at every such meeting so its two orientations
        can be compared exactly rather than approximately.
        """
        import pcbnew
        board, _ = layout.build(with_copper=True)
        nets = ("USB_DP", "USB_DM")
        landings = []
        for item in board.GetTracks():
            if item.Type() == pcbnew.PCB_VIA_T and item.GetNetname() in nets:
                landings.append((item.GetPosition(),
                                 item.GetWidth(pcbnew.F_Cu) / 2.0,
                                 "via"))
        for footprint in board.GetFootprints():
            for pad in footprint.Pads():
                if pad.GetNetname() not in nets:
                    continue
                size = pad.GetSize()
                landings.append((pad.GetPosition(),
                                 min(size.x, size.y) / 2.0,
                                 "%s.%s" % (footprint.GetReference(),
                                            pad.GetNumber())))
        offenders = []
        for track in board.GetTracks():
            if track.Type() == pcbnew.PCB_VIA_T:
                continue
            if track.GetNetname() not in nets:
                continue
            start, end = track.GetStart(), track.GetEnd()
            dx, dy = end.x - start.x, end.y - start.y
            span = float(dx * dx + dy * dy)
            if span == 0.0:
                continue
            half = track.GetWidth() / 2.0
            for centre, radius, name in landings:
                t = ((centre.x - start.x) * dx
                     + (centre.y - start.y) * dy) / span
                if not 1e-6 < t < 1 - 1e-6:
                    continue
                near_x = start.x + t * dx
                near_y = start.y + t * dy
                distance = math.hypot(near_x - centre.x, near_y - centre.y)
                if distance < radius + half:
                    offenders.append(
                        (name, track.GetNetname(),
                         round(pcbnew.ToMM(near_x), 3),
                         round(pcbnew.ToMM(near_y), 3)))
        self.assertEqual(sorted(set(offenders)), [])


class StaticVerification(unittest.TestCase):
    def test_the_schematic_passes_erc(self):
        report = os.path.join(REPO_ROOT, "out", "erc_test.json")
        os.makedirs(os.path.dirname(report), exist_ok=True)
        completed = subprocess.run(
            ["kicad-cli", "sch", "erc", "--output", report, "--format",
             "json", "--severity-error", "--severity-warning",
             "--exit-code-violations", build.schematic_path()],
            capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout)
        with open(report, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        violations = [violation for sheet in document.get("sheets", [])
                      for violation in sheet.get("violations", [])]
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
