from __future__ import annotations

import json
import os
import sys

from . import netlist, schematic

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def schematic_path():
    return os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_sch")


def project_path():
    return os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_pro")


def generate_schematic_text():
    netlist.pin_to_net()
    tree = schematic.build(
        netlist.PARTS, netlist.NETS, set(netlist.NO_CONNECT),
        netlist.PROJECT_NAME)
    return schematic.render(tree)


#: The floor the board is written with and judged against. It is well inside
#: the fabricator's published capability, because the tight geometry here is
#: the bridge's half-millimetre pitch and the receptacle's, and both are
#: land patterns rather than routing.
DESIGN_RULES = {
    "min_clearance": 0.15,
    "min_track_width": 0.15,
    "min_via_diameter": 0.45,
    "min_via_annular_width": 0.1,
    "min_through_hole_diameter": 0.25,
    "min_hole_clearance": 0.25,
    "min_hole_to_hole": 0.25,
    "min_copper_edge_clearance": 0.3,
}


#: Two classes. Everything on this board shares one clearance requirement -
#: the highest potential anywhere is VBUS and there is no isolation barrier -
#: but the USB pair is drawn narrower and closer than the rest, because its
#: spacing is an electrical choice rather than a manufacturing minimum, and a
#: class is how that choice reaches the router and the checker.
NET_CLASSES = [
    {
        "name": "Default",
        "clearance": 0.15,
        "track_width": 0.25,
        "via_diameter": 0.6,
        "via_drill": 0.3,
    },
    {
        "name": "USB",
        "clearance": 0.15,
        "track_width": 0.25,
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "diff_pair_width": 0.25,
        "diff_pair_gap": 0.25,
    },
]

USB_NET_CLASS_MEMBERS = ("USB_DP", "USB_DM")


def project_document(root_sheet_uuid):
    classes = [dict(entry) for entry in NET_CLASSES]
    return {
        "board": {
            "design_settings": {
                "rule_severities": {
                    "missing_courtyard": "warning",
                    "track_not_centered_on_via": "warning",
                    "tuning_profile_track_geometries": "warning",
                    "footprint_filters_mismatch": "warning",
                    "footprint_type_mismatch": "warning",
                },
                "rules": dict(DESIGN_RULES),
            },
            "drc_exclusions": [],
            "layer_presets": [],
            "viewports": [],
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "erc": {
            "erc_exclusions": [],
            "meta": {"version": 0},
            "pin_map": [],
            "rule_severities": {
                "single_global_label": "warning",
                "four_way_junction": "warning",
                "simulation_model_issue": "warning",
                "footprint_filter": "warning",
            },
        },
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": netlist.PROJECT_NAME + ".kicad_pro",
                 "version": 3},
        "net_settings": {
            "classes": classes,
            "netclass_assignments": {
                name: ["USB"] for name in USB_NET_CLASS_MEMBERS},
        },
        "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[root_sheet_uuid, "Root"]],
        "text_variables": {},
    }


def write_project():
    root_uuid = str(schematic._uuid("sheet", netlist.PROJECT_NAME))
    with open(project_path(), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(project_document(root_uuid), handle, indent=2)
        handle.write("\n")
    return (project_path(),)


def write():
    text = generate_schematic_text()
    with open(schematic_path(), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return (schematic_path(),) + write_project()


if __name__ == "__main__":
    for path in write():
        sys.stdout.write(path + "\n")
