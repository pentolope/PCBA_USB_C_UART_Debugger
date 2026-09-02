"""The board's manifest, generated from the design source rather than typed.

The manifest is what the validator reads: which files are the design, which
gates are mandatory, what the connectors carry, what the stackup is, which
electrical paths are measured and against what. Every one of those is
already stated somewhere in this repository - in the netlist, in the layout,
in the fabrication selection - and a manifest typed by hand is a second copy
of all of it that can drift from the first.

So it is generated. The pin maps come from the netlist's own connector
contract, the constraint floor from the design settings the board file is
written with, the timing interfaces from the pair's own terminals and
budgets, and the simulation stages from the scenarios that exist.
"""
from __future__ import annotations

import json
import os
import sys

from . import build, layout, netlist, simulation

MANIFEST_PATH = os.path.join(layout.REPO_ROOT, "board", "manifest.json")

RELEASE_PROFILE_ID = "jlcpcb-2layer-assembled"

MANDATORY_GATES = (
    "ARCH.CONTENTS",
    "ARCH.PROVENANCE",
    "BOM.NATIVE_PARITY",
    "CONTRACT.CONNECTOR",
    "CONTRACT.PLACEMENT",
    "CPL.NATIVE_PARITY",
    "DRC.AUTHORITATIVE",
    "DRC.CONSTRAINT_FLOOR",
    "DRC.NO_SUPPRESSED_RULES",
    "ERC.AUTHORITATIVE",
    "NET.TOPOLOGY",
    "PROV.REPORT_FRESHNESS",
    "PROV.TIMING_MODELS",
    "ROUTE.GEOMETRY_HYGIENE",
    "ROUTE.PROVENANCE",
    "ROUTE.TINY_SEGMENTS",
    "SIM.SCENARIOS",
    "SIM.STAGE_COVERAGE",
    "STACK.GERBER_PARITY",
    "STACK.NATIVE_VS_MANIFEST",
    "STACK.PHYSICAL",
    "TIMING.INTERCONNECT_DELAY",
    "TIMING.INTERCONNECT_SKEW",
    "TIMING.PATH_INTEGRITY",
    "VIA.ANNULUS_MASK_OVERLAP",
    "VIA.IN_PAD_CONTACT",
    "VIA.MASK_CLEARANCE_TARGET",
)

#: Gates that judge the design itself rather than the fabrication artifacts.
#: The artifacts are generated FROM the board a search has not finished
#: choosing, so gates over those would reject every candidate.
ACCEPTANCE_GATES = (
    "ERC.AUTHORITATIVE",
    "DRC.AUTHORITATIVE",
    "DRC.NO_SUPPRESSED_RULES",
    "DRC.CONSTRAINT_FLOOR",
    "NET.TOPOLOGY",
    "ROUTE.GEOMETRY_HYGIENE",
    "ROUTE.TINY_SEGMENTS",
    "ROUTE.PROVENANCE",
    "CONTRACT.PLACEMENT",
    "CONTRACT.CONNECTOR",
    "STACK.NATIVE_VS_MANIFEST",
    "STACK.PHYSICAL",
    "TIMING.PATH_INTEGRITY",
    "TIMING.INTERCONNECT_DELAY",
    "TIMING.INTERCONNECT_SKEW",
    "VIA.ANNULUS_MASK_OVERLAP",
    "VIA.IN_PAD_CONTACT",
    "SIM.SCENARIOS",
    "SIM.STAGE_COVERAGE",
)

REQUIRED_EVIDENCE = (
    "evidence/index.json",
    "fab/physical_inputs.json",
    "fab/selection.json",
    "generated/requirements.json",
    "generated/routing.json",
)

CONNECTOR_IDS = {"J1": "usb_receptacle", "J2": "target_header"}

#: The receptacle's lands are not on one pitch - the drawing spaces the
#: supply and reference lands differently from the signal ones - so no pitch
#: is declared for it. Declaring one would be declaring a number the drawing
#: does not state.
CONNECTOR_GRID = {"J2": {"required_rows": 1, "required_pitch_mm": 2.54}}


def connector_positions(reference):
    """Every terminal the connector's symbol brings out, connected or not.

    The count the contract states is the land pattern's, so a terminal this
    board leaves unconnected still counts: it is a position on the part.
    """
    from . import ksym
    library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
    return len(library.pins(netlist.PARTS[reference]["lib_id"]))


def connector_contracts():
    """One contract per connector, from the netlist's own function map."""
    pin_net = netlist.pin_to_net()
    contracts = []
    for reference in sorted(netlist.CONNECTOR_FUNCTION_NETS,
                            key=lambda name: int(name[1:])):
        pins = {}
        for pin_ref, net in pin_net.items():
            owner, _, number = pin_ref.partition(".")
            if owner == reference:
                pins[number] = net
        contract = {
            "id": CONNECTOR_IDS[reference],
            "reference": reference,
            "required_positions": connector_positions(reference),
            "required_side": "front",
            "population": {"dnp": False, "exclude_from_bom": False},
            "pin_map": {number: pins[number] for number in sorted(pins)},
        }
        contract.update(CONNECTOR_GRID.get(reference, {}))
        contracts.append(contract)
    return contracts


def placement_rules():
    """Groups the board must contain, counted rather than located."""
    return [
        {"id": "CONNECTORS", "reference_regex": r"^J[12]$", "count": 2},
        {"id": "PROBES", "reference_regex": r"^TP[1-5]$", "count": 5},
        {"id": "SUPPLY_SWITCH", "reference_regex": r"^Q[123]$", "count": 3},
        {"id": "SIGNAL_SERIES",
         "reference_regex": r"^R(8|9|10|11)$", "count": 4},
        {"id": "BRIDGE_BYPASS",
         "reference_regex": r"^C[5-8]$", "count": 4},
        {"id": "RAIL_BULK", "reference_regex": r"^C(9|10|11)$", "count": 3},
    ]


def net_topology_rules():
    """The one route whose topology is a requirement rather than a result.

    Each data conductor takes exactly the layer changes the receptacle's own
    land order forces on it and no more, and it takes them on the two layers
    this board has. The count is the budget the design source declares; the
    gate measures the copper.
    """
    return [{
        "id": "USB_DATA_PAIR",
        "net_regex": r"^USB_D[PM]$",
        "source_pad_regex": r"^J1\.A[67]$",
        "load_pad_regex": r"^U1\.[45]$",
        "max_vias_per_net": netlist.USB_PAIR_VIA_BUDGET_PER_NET,
        "permitted_layers": ["F.Cu", "B.Cu"],
    }]


def stackup_expected():
    """What each copper layer is for. Both are poured on the reference: the
    back one is the pair's plane and the front one is everything else's
    return, and the two are tied together on a declared grid."""
    return [{"role": "plane", "plane_net": "GND"},
            {"role": "plane", "plane_net": "GND"}]


def timing_document():
    """The pair, as electrical paths the toolkit measures on the copper.

    Four paths rather than two: a USB 2.0 plug populates only its A-side
    data contacts, so a flipped plug lands on the receptacle's B contacts
    instead. Each orientation is its own pair, and each is length-matched in
    its own group.
    """
    paths = []
    for net, terminal in sorted(netlist.USB_C_PAIR_TERMINALS.items()):
        paths.append({
            "id": "%s_from_%s" % (net.lower(), terminal.lower()),
            "steps": [{"kind": "copper", "net": net,
                       "from": r"^J1\.%s$" % terminal,
                       "to": r"^U1\.%s$" % netlist.BRIDGE_PINS[net[-2:]]}],
        })
    for net, terminal in sorted(netlist.USB_C_FLIPPED_TERMINALS.items()):
        paths.append({
            "id": "%s_from_%s" % (net.lower(), terminal.lower()),
            "steps": [{"kind": "copper", "net": net,
                       "from": r"^J1\.%s$" % terminal,
                       "to": r"^U1\.%s$" % netlist.BRIDGE_PINS[net[-2:]]}],
        })
    delay_ps_per_mm = netlist.USB_PAIR_DELAY_PS_PER_MM
    front_budget, back_budget = layout.unreferenced_budgets_mm()
    return {
        "models": {"physical_stackup": "fab/physical_inputs.json"},
        "physical_stackup": {
            "reference_nets": ["GND"],
            "supplement": "fab/physical_inputs.json",
            "require_complete": False,
        },
        "propagation": {
            "model": "hammerstad",
            "via_delay_model": {
                "model": "geometric",
                "justification":
                    "the two layer changes each conductor takes are through "
                    "the whole 1.6 mm board, and a transit that long is not "
                    "nothing beside a pair this short",
            },
            "reference_discontinuity": [
                {
                    "treatment": "assume_continuous",
                    "reference_layers": ["B.Cu"],
                    "signal_layers": ["F.Cu"],
                    "paths": r"^usb_d",
                    "up_to_mm": front_budget,
                    "justification":
                        "the receptacle brings each data line out on two "
                        "terminals whose order along the land row is D-, "
                        "D+, D-, D+, so the two links that join each line's "
                        "pair of terminals are non-planar and one of them "
                        "must cross the other conductor on the back layer. "
                        "What interrupts the plane under a front conductor "
                        "is that crossing, the suppressor's rail conductor, "
                        "the conductor's own layer change and one "
                        "unpourable strip between two of them - priced from "
                        "this board's own track width, via diameter, "
                        "clearance and minimum pour width, and nothing "
                        "else: the plane under the pair is closed to every "
                        "other conductor and the front pour is kept out of "
                        "the pair's corridor. Each is a fraction of a "
                        "millimetre against a %.0f mm run whose whole "
                        "length is lumped at this interface's edge rate, so "
                        "carrying the model across them changes no "
                        "conclusion this board draws"
                        % netlist.USB_PAIR_LENGTH_BUDGET_MM,
                },
                {
                    "treatment": "assume_continuous",
                    "reference_layers": ["F.Cu"],
                    "signal_layers": ["B.Cu"],
                    "paths": r"^usb_d",
                    "up_to_mm": back_budget,
                    "justification":
                        "the orientation link runs on the plane layer under "
                        "the receptacle's launch, where the four fan-out "
                        "conductors and their clearances leave no front "
                        "area wide enough to pour, so the link has no "
                        "reference above it for its whole span. The budget "
                        "is that span and the clearance the front copper is "
                        "held off by at each end. Its return is the front "
                        "copper of the launch itself; at %.0f ps of transit "
                        "against a %.0f ps path budget, no plausible error "
                        "in that transit changes a conclusion"
                        % (back_budget * netlist.USB_PAIR_DELAY_PS_PER_MM,
                           netlist.USB_PAIR_LENGTH_BUDGET_MM
                           * netlist.USB_PAIR_DELAY_PS_PER_MM),
                },
            ],
        },
        "interfaces": {
            "usb_data": {
                "description": "the full-speed pair, receptacle to bridge, "
                               "for both orientations of the plug",
                "expected_path_count": 4,
                "max_unreferenced_mm": front_budget + back_budget,
                "limits": {
                    "max_delay_ps": (netlist.USB_PAIR_LENGTH_BUDGET_MM
                                     * delay_ps_per_mm),
                },
                "routes": {"paths": paths},
                "groups": {
                    "plug_a_side": {
                        "description": "the pair a plug in one orientation "
                                       "presents",
                        "paths": r"^usb_d[pm]_from_a[67]$",
                        "max_length_spread_mm":
                            netlist.USB_PAIR_SKEW_BUDGET_MM,
                        "max_skew_ps": (netlist.USB_PAIR_SKEW_BUDGET_MM
                                        * delay_ps_per_mm),
                    },
                    "plug_b_side": {
                        "description": "the same pair with the plug turned "
                                       "over",
                        "paths": r"^usb_d[pm]_from_b[67]$",
                        "max_length_spread_mm":
                            netlist.USB_PAIR_SKEW_BUDGET_MM,
                        "max_skew_ps": (netlist.USB_PAIR_SKEW_BUDGET_MM
                                        * delay_ps_per_mm),
                    },
                },
            },
        },
    }


def simulation_stages():
    return {"pre_layout": ["sim/" + name for name in sorted(
        simulation.documents())]}


def document():
    project = netlist.PROJECT_NAME
    classes = {entry["name"]: {key: value
                               for key, value in entry.items()
                               if key != "name"}
               for entry in build.NET_CLASSES}
    return {
        "schema_version": 2,
        "board_id": project,
        "constraint_version": "layout-stage-2026-09-02",
        "project_root": "..",
        "tools": {"kicad_cli": "kicad-cli"},
        "sources": {
            "schematic": project + ".kicad_sch",
            "project": project + ".kicad_pro",
            "pcb": project + ".kicad_pcb",
        },
        "board_origin_mm": [0.0, 0.0],
        "documentation_globs": ["BRIEF.md"],
        "checks": {
            "erc": {"extra_flags": []},
            "drc": {
                "extra_flags": [],
                "forbidden_severities": ["ignore"],
                "permitted_ignored_rules": [],
                "constraint_floor": {
                    "rules": dict(build.DESIGN_RULES),
                    "net_classes": classes,
                },
            },
        },
        "waivers": [],
        "geometry_profile": {
            "version": "geom-1",
            "tolerances": {
                "waiver_location_mm": {"value": 0.001, "units": "mm"},
                "polygon_chord_error_mm": {"value": 0.001, "units": "mm"},
                "contact_mm": {"value": 1e-06, "units": "mm"},
                "coordinate_match_mm": {"value": 0.002, "units": "mm"},
                "rotation_match_deg": {"value": 0.1, "units": "deg"},
                "dimension_match_mm": {"value": 0.002, "units": "mm"},
                "clearance_match_mm": {"value": 0.01, "units": "mm"},
                "layer_symmetric_difference_mm2": {"value": 0.05,
                                                   "units": "mm2"},
            },
        },
        "stackup": {"expected": stackup_expected()},
        "placement_rules": placement_rules(),
        "net_topology": {"rules": net_topology_rules()},
        "timing": timing_document(),
        "routing": {
            "min_segment_mm": 0.1,
            "short_segment_justification": {"allow_pad_or_via_entry": True},
            "hygiene": {"forbid_duplicate_geometry": True,
                        "forbid_net_crossings": True,
                        "forbid_dangling": True},
            "provenance": "generated/routing.json",
            "acceptance_gates": list(ACCEPTANCE_GATES),
        },
        "via_mask": {
            "pad_contact": {"populated_pad_attributes": ["SMD"],
                            "require_paste": True},
            "metric": "annulus_to_opening_mm",
            "contact_semantics":
                "annulus_contacts counts zero-distance tangency as contact; "
                "annulus_strict_overlaps counts positive shared area only",
            "mask_dam_rule": "contact",
            "design_target_mm": 0.15,
        },
        "artifacts": {
            "gerber_dir": "generated/release/gerbers",
            "bom": "generated/release/bom.csv",
            "cpl": "generated/release/cpl.csv",
            "fabrication_manifest": "generated/release/fabrication.json",
            "validation_report": "generated/release/validation.json",
            "position_tolerance_mm": 0.01,
            "cpl_fields": {"designator": "Ref", "x": "PosX", "y": "PosY",
                           "side": "Side", "rotation": "Rot"},
            "cpl_origin": {"frame": "absolute page origin",
                           "offset_mm": [0.0, 0.0]},
            "gerber_export_flags": [
                "--layers",
                "F.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,"
                "Edge.Cuts",
                "--no-protel-ext", "--use-drill-file-origin",
                "--subtract-soldermask"],
            "reports_dir": "generated/release/reports",
        },
        "archive": {
            "zip": "generated/release/%s-fabrication.zip" % project,
            "allow": [
                {"file_function": "Copper,L1,Top", "require_payload": True,
                 "min_count": 1},
                {"file_function": "Copper,L2,Bot", "require_payload": True,
                 "min_count": 1},
                {"file_function": "Soldermask,Top", "require_payload": True,
                 "min_count": 1},
                {"file_function": "Soldermask,Bot", "require_payload": True,
                 "min_count": 1},
                {"file_function": "Legend,Top", "require_payload": True,
                 "min_count": 1},
                {"file_function": "Legend,Bot", "require_payload": False,
                 "min_count": 1},
                {"file_function": "Paste,Top", "require_payload": True,
                 "min_count": 1},
                {"file_function": "Profile,NP", "require_payload": True,
                 "min_count": 1},
                {"file_function": "Drill/plated", "require_payload": True,
                 "min_count": 1},
                {"file_function": "Drill/nonplated", "require_payload": True,
                 "min_count": 1},
                {"file_function": "JobFile", "require_payload": True,
                 "min_count": 1},
            ],
        },
        "assembly": {
            "schematic_fields": ["LCSC", "MPN", "Manufacturer"],
            "required_part_fields": ["LCSC"],
            "bom_fields": {"designators": "Designator", "value": "Comment",
                           "footprint": "Footprint", "quantity": "Quantity",
                           "LCSC": "LCSC Part #"},
            "schematic_export": {
                "fields": ["Reference", "Value", "Footprint", "${DNP}",
                           "${EXCLUDE_FROM_BOM}", "LCSC", "MPN",
                           "Manufacturer"],
                "labels": ["Reference", "Value", "Footprint", "DNP",
                           "ExcludeFromBOM", "LCSC", "MPN", "Manufacturer"],
                "flags": [],
                "reference_label": "Reference",
                "value_label": "Value",
                "footprint_label": "Footprint",
                "dnp_label": "DNP",
                "exclude_label": "ExcludeFromBOM",
                "true_tokens": ["1", "true", "yes", "x", "dnp"],
            },
            "compared_part_fields": ["LCSC", "MPN", "Manufacturer"],
        },
        "release_generation": {
            "lock_file_globs": ["*.lck", "~*.lck", ".#*", "*-lock",
                                "*.kicad_prl-lock"],
            "erc": {"output": "erc.json"},
            "drc": {"output": "drc.json"},
            "drill": {"flags": ["--format", "excellon",
                                "--excellon-separate-th", "--drill-origin",
                                "plot"]},
            "bom": {
                "output": "bom.csv",
                "fields": ["${QUANTITY}", "Reference", "Value", "Footprint",
                           "LCSC"],
                "labels": ["Quantity", "Designator", "Comment", "Footprint",
                           "LCSC Part #"],
                "group_by": ["Value", "Footprint", "LCSC"],
                "flags": ["--exclude-dnp", "--ref-range-delimiter", ""],
                "field_map": {"designators": "Designator", "value": "Comment",
                              "footprint": "Footprint",
                              "quantity": "Quantity",
                              "LCSC": "LCSC Part #"},
            },
            "cpl": {
                "output": "cpl.csv",
                "flags": ["--format", "csv", "--units", "mm", "--side",
                          "both", "--exclude-dnp"],
                "field_map": {"designator": "Ref", "x": "PosX", "y": "PosY",
                              "side": "Side", "rotation": "Rot"},
                "origin": {"frame": "absolute page origin",
                           "offset_mm": [0.0, 0.0]},
            },
            "archive": {"zip": "%s-fabrication.zip" % project},
        },
        "reports": {
            "files": ["generated/release/reports/erc.json",
                      "generated/release/reports/drc.json"],
            "source_field": "source",
            "date_field": "date",
            "require_source_hash": True,
            "tolerance_seconds": 0,
            "source_closure": ["*.kicad_sch", "*.kicad_pcb", "*.kicad_pro",
                               "*.kicad_dru", "constraints/*.json",
                               "sim/*.json", "fab/*.json",
                               "components/*.json", "evidence/index.json"],
            "source_hash_field": "source_sha256",
            "closure_field": "source_closure_sha256",
        },
        "fixture": {"attributes_file": ".gitattributes"},
        "release_profile": {
            "id": RELEASE_PROFILE_ID,
            "mandatory_gates": list(MANDATORY_GATES),
            "required_evidence": list(REQUIRED_EVIDENCE),
        },
        "simulation": {
            "stages": simulation_stages(),
            "required_stages": ["pre_layout"],
        },
        "connector_gender_tokens": {
            "receptacle": ["receptacle", "socket", "female"],
            "plug": ["plug", "header", "male"],
        },
        "connector_contracts": connector_contracts(),
    }


def write():
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return MANIFEST_PATH


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
