"""What KiCad's own libraries do not carry, generated from the drawings.

Almost everything this board uses - the suppressor, the receptacle, the
transistors, the passives - is a stock KiCad symbol on a stock KiCad
footprint, so the board owns no copy of it. Two things are not.

The regulator's symbol, because KiCad ships no XC6206; it is generated from
the pin assignment table in the Torex datasheet.

The bridge's land pattern, because the stock QFN-28 patterns put no paste on
the thermal land at all - the part would reflow on its perimeter pads with
its centre pad dry - and because their thermal land is wide enough to seal
the perimeter ring, leaving no way to reach it with copper. The pattern here
is generated from the bridge datasheet's own land-pattern table and its
notes, and its thermal land is sized to leave a diagonal corridor at each
corner: the ground connection is then made with copper rather than with a
via standing in a pad that receives solder.
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY_NAME = "UsbCUartDebugger"
SYMBOL_LIB_PATH = os.path.join(REPO_ROOT, "library",
                               LIBRARY_NAME + ".kicad_sym")
FOOTPRINT_DIR = os.path.join(REPO_ROOT, "library", LIBRARY_NAME + ".pretty")
SYM_LIB_TABLE = os.path.join(REPO_ROOT, "sym-lib-table")
FP_LIB_TABLE = os.path.join(REPO_ROOT, "fp-lib-table")

SYMBOL_LIB_VERSION = "20251024"
FOOTPRINT_VERSION = "20260206"
GENERATOR = "usb-c-uart-debugger-design-source"

# CP2102N data sheet Rev 1.5, table 6.2 "QFN28 PCB Land Pattern Dimensions"
# and its notes. Every dimension in that table is stated as a maximum, so
# each value below is at or under the one the table gives.
#
#   E  = 0.50        land pitch
#   X1 = 0.30 max    perimeter land width      -> 0.25
#   Y1 = 0.95 max    perimeter land length     -> 0.90
#   C1 = C2 = 4.80   land centre span          -> centres at +/- 2.40
#   X2 = Y2 = 3.35   thermal land              -> 2.90
#
# The thermal land is well under its maximum on purpose. At 3.35 it would
# leave 0.275 mm between itself and the perimeter ring, which no conductor
# and no pour can pass; at 2.90 the diagonal corridor at each corner is wide
# enough for a track at the board's own clearance, so the land is reached
# with copper instead of with a via in a pad that takes paste.
#
# Note 7 gives the stencil for the centre pad as a 2 x 2 array of 1.2 mm
# square openings on a 1.5 mm pitch, and note 6 gives 1:1 apertures for the
# perimeter lands; both are followed. Note 3 asks for a 60 um solder-mask
# clearance all round each land, which is NOT followed: at this pitch it
# would leave a 0.13 mm mask dam between neighbouring lands, and no mask-dam
# or mask-expansion capability is among this board's frozen fabricator
# evidence, so the board states no expansion of its own and leaves it to the
# process. That deviation is recorded rather than quietly taken.
BRIDGE_FOOTPRINT_NAME = "QFN-28-1EP_5x5mm_P0.5mm_CP2102N"
BRIDGE_PITCH_MM = 0.50
BRIDGE_PAD_WIDTH_MM = 0.25
BRIDGE_PAD_LENGTH_MM = 0.90
BRIDGE_PAD_CENTRE_MM = 2.40
BRIDGE_PADS_PER_SIDE = 7
BRIDGE_THERMAL_LAND_MM = 2.90
BRIDGE_THERMAL_PASTE_MM = 1.20
BRIDGE_THERMAL_PASTE_PITCH_MM = 1.50
BRIDGE_BODY_MM = 5.00
BRIDGE_COURTYARD_MARGIN_MM = 0.25
BRIDGE_DATASHEET = ("https://www.silabs.com/documents/public/data-sheets/"
                    "cp2102n-datasheet.pdf")

#: Torex XC6206 series, PIN ASSIGNMENT table: in SOT-89 the pins are VSS,
#: VIN, VOUT on 1, 2, 3. The regulator is the only source on the logic rail,
#: so its output is declared power_out and the rail needs no separate flag.
LDO_SYMBOL_NAME = "XC6206Pxx2PR"
LDO_PINS = (("1", "VSS", "power_in", "bottom"),
            ("2", "VIN", "power_in", "left"),
            ("3", "VOUT", "power_out", "right"))
LDO_DATASHEET = "https://product.torexsemi.com/system/files/series/xc6206.pdf"
LDO_FOOTPRINT = "Package_TO_SOT_SMD:SOT-89-3"
LDO_FOOTPRINT_FILTER = "SOT?89*"


def _effects():
    return ("\n\t\t\t\t(effects\n\t\t\t\t\t(font\n"
            "\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t)\n\t\t\t\t)")


def _symbol_property(key, value, index, hide):
    hidden = "\n\t\t\t(hide yes)" if hide else ""
    return ('\t\t(property "%s" "%s"\n\t\t\t(at 0 %.2f 0)%s\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
            '\t\t\t\t)\n\t\t\t)\n\t\t)'
            % (key, value, 17.78 - 2.54 * index, hidden))


def _pin_text(kind, x, y, angle, name, number):
    return ('\t\t\t(pin %s line\n\t\t\t\t(at %.2f %.2f %d)\n'
            '\t\t\t\t(length 2.54)\n'
            '\t\t\t\t(name "%s"%s\n\t\t\t\t)\n'
            '\t\t\t\t(number "%s"%s\n\t\t\t\t)\n\t\t\t)'
            % (kind, x, y, angle, name, _effects(), number, _effects()))


def _rectangle(half_x, half_y):
    return ['\t\t\t(rectangle',
            '\t\t\t\t(start %.2f %.2f)' % (-half_x, half_y),
            '\t\t\t\t(end %.2f %.2f)' % (half_x, -half_y),
            '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n'
            '\t\t\t\t\t(type default)\n\t\t\t\t)',
            '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)',
            '\t\t\t)']


def _placed_pin(entry, placed_pins, half_x, half_y):
    number, pin_name, kind, side = entry
    same_side = [item for item in placed_pins if item[3] == side]
    index = same_side.index(entry)
    span = 2.54 * (len(same_side) - 1) / 2.0
    if side == "left":
        return _pin_text(kind, -half_x - 2.54, span - 2.54 * index, 0,
                         pin_name, number)
    if side == "right":
        return _pin_text(kind, half_x + 2.54, span - 2.54 * index, 180,
                         pin_name, number)
    if side == "bottom":
        return _pin_text(kind, 2.54 * index - span, -half_y - 2.54, 90,
                         pin_name, number)
    return _pin_text(kind, 2.54 * index - span, half_y + 2.54, 270,
                     pin_name, number)


def ldo_symbol_text():
    placed = list(LDO_PINS)
    half_x, half_y = 5.08, 3.81
    lines = ['\t(symbol "%s"' % LDO_SYMBOL_NAME,
             '\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)',
             '\t\t(exclude_from_sim no)',
             '\t\t(in_bom yes)',
             '\t\t(on_board yes)',
             _symbol_property("Reference", "U", 0, False),
             _symbol_property("Value", LDO_SYMBOL_NAME, 1, False),
             _symbol_property("Footprint", LDO_FOOTPRINT, 2, True),
             _symbol_property("Datasheet", LDO_DATASHEET, 3, True),
             _symbol_property("ki_fp_filters", LDO_FOOTPRINT_FILTER, 4, True),
             '\t\t(symbol "%s_0_1"' % LDO_SYMBOL_NAME]
    lines.extend(_rectangle(half_x, half_y))
    lines.append('\t\t)')
    lines.append('\t\t(symbol "%s_1_1"' % LDO_SYMBOL_NAME)
    for entry in placed:
        lines.append(_placed_pin(entry, placed, half_x, half_y))
    lines.append('\t\t)')
    lines.append('\t)')
    return "\n".join(lines)


def symbol_library_text():
    return "\n".join([
        '(kicad_symbol_lib',
        '\t(version %s)' % SYMBOL_LIB_VERSION,
        '\t(generator "%s")' % GENERATOR,
        '\t(generator_version "10.0")',
        ldo_symbol_text(),
        ')']) + "\n"


# ---------------------------------------------------------------------------
# the bridge's land pattern


def _bridge_pad_poses():
    """Every perimeter land, counter-clockwise from the top of the left side.

    The order is KiCad's own QFN convention and the datasheet's pin
    numbering: down the left side, along the bottom, up the right side, back
    along the top.
    """
    span = BRIDGE_PITCH_MM * (BRIDGE_PADS_PER_SIDE - 1) / 2.0
    edge = BRIDGE_PAD_CENTRE_MM
    long_mm, short_mm = BRIDGE_PAD_LENGTH_MM, BRIDGE_PAD_WIDTH_MM
    poses = []
    for index in range(BRIDGE_PADS_PER_SIDE):
        step = BRIDGE_PITCH_MM * index - span
        poses.append((-edge, step, long_mm, short_mm))
    for index in range(BRIDGE_PADS_PER_SIDE):
        step = BRIDGE_PITCH_MM * index - span
        poses.append((step, edge, short_mm, long_mm))
    for index in range(BRIDGE_PADS_PER_SIDE):
        step = span - BRIDGE_PITCH_MM * index
        poses.append((edge, step, long_mm, short_mm))
    for index in range(BRIDGE_PADS_PER_SIDE):
        step = span - BRIDGE_PITCH_MM * index
        poses.append((step, -edge, short_mm, long_mm))
    return poses


def _fp_pad(number, shape, x, y, size_x, size_y, layers, extra=""):
    return ('\t(pad "%s" smd %s\n\t\t(at %.4f %.4f)\n\t\t(size %.4f %.4f)\n'
            '\t\t(layers %s)%s\n\t)'
            % (number, shape, x, y, size_x, size_y, layers, extra))


def _fp_line(layer, x0, y0, x1, y1, width):
    return ('\t(fp_line\n\t\t(start %.4f %.4f)\n\t\t(end %.4f %.4f)\n'
            '\t\t(stroke\n\t\t\t(width %.3f)\n\t\t\t(type solid)\n\t\t)\n'
            '\t\t(layer "%s")\n\t)' % (x0, y0, x1, y1, width, layer))


def _fp_rect_outline(layer, half, width):
    return "\n".join([
        _fp_line(layer, -half, -half, half, -half, width),
        _fp_line(layer, half, -half, half, half, width),
        _fp_line(layer, half, half, -half, half, width),
        _fp_line(layer, -half, half, -half, -half, width),
    ])


def bridge_footprint_text():
    half_body = BRIDGE_BODY_MM / 2.0
    half_court = BRIDGE_PAD_CENTRE_MM + BRIDGE_PAD_LENGTH_MM / 2.0 \
        + BRIDGE_COURTYARD_MARGIN_MM
    half_land = BRIDGE_THERMAL_LAND_MM / 2.0
    lines = [
        '(footprint "%s"' % BRIDGE_FOOTPRINT_NAME,
        '\t(version %s)' % FOOTPRINT_VERSION,
        '\t(generator "%s")' % GENERATOR,
        '\t(generator_version "10.0")',
        '\t(layer "F.Cu")',
        '\t(descr "QFN-28 5x5 mm, 0.5 mm pitch, from the CP2102N data sheet '
        'table 6.2 land pattern and its notes")',
        '\t(tags "qfn cp2102n")',
        '\t(attr smd)',
        '\t(property "Reference" "U"\n\t\t(at 0 %.2f 0)\n\t\t(layer "F.Fab")'
        '\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.8 0.8)\n'
        '\t\t\t\t(thickness 0.12)\n\t\t\t)\n\t\t)\n\t)' % (-half_court - 0.8),
        '\t(property "Value" "%s"\n\t\t(at 0 %.2f 0)\n\t\t(layer "F.Fab")'
        '\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 0.8 0.8)\n'
        '\t\t\t\t(thickness 0.12)\n\t\t\t)\n\t\t)\n\t)'
        % (BRIDGE_FOOTPRINT_NAME, half_court + 0.8),
    ]
    for index, (x, y, size_x, size_y) in enumerate(_bridge_pad_poses()):
        lines.append(_fp_pad(str(index + 1), "roundrect", x, y, size_x,
                             size_y, '"F.Cu" "F.Paste" "F.Mask"',
                             "\n\t\t(roundrect_rratio 0.25)"))
    # The thermal land takes copper and mask over its whole area and paste
    # only where note 7 puts it.
    lines.append(_fp_pad("29", "rect", 0.0, 0.0, BRIDGE_THERMAL_LAND_MM,
                         BRIDGE_THERMAL_LAND_MM, '"F.Cu" "F.Mask"',
                         "\n\t\t(property pad_prop_heatsink)"
                         "\n\t\t(zone_connect 2)"))
    offset = BRIDGE_THERMAL_PASTE_PITCH_MM / 2.0
    for sx in (-offset, offset):
        for sy in (-offset, offset):
            lines.append(_fp_pad("29", "rect", sx, sy,
                                 BRIDGE_THERMAL_PASTE_MM,
                                 BRIDGE_THERMAL_PASTE_MM, '"F.Paste"'))
    lines.append(_fp_rect_outline("F.Fab", half_body, 0.1))
    lines.append(_fp_rect_outline("F.CrtYd", half_court, 0.05))
    # Pin one, marked outside the land pattern so nothing prints on copper.
    mark = half_court - 0.25
    lines.append(_fp_line("F.SilkS", -mark, -mark, -mark + 0.6, -mark, 0.12))
    lines.append(_fp_line("F.SilkS", -mark, -mark, -mark, -mark + 0.6, 0.12))
    lines.append(")")
    return "\n".join(lines) + "\n"


def sym_lib_table_text():
    return ('(sym_lib_table\n\t(version 7)\n'
            '\t(lib (name "%s")(type "KiCad")'
            '(uri "${KIPRJMOD}/library/%s.kicad_sym")(options "")(descr ""))\n)\n'
            % (LIBRARY_NAME, LIBRARY_NAME))


def fp_lib_table_text():
    return ('(fp_lib_table\n\t(version 7)\n'
            '\t(lib (name "%s")(type "KiCad")'
            '(uri "${KIPRJMOD}/library/%s.pretty")(options "")(descr ""))\n)\n'
            % (LIBRARY_NAME, LIBRARY_NAME))


def artifacts():
    return {
        SYMBOL_LIB_PATH: symbol_library_text(),
        os.path.join(FOOTPRINT_DIR, BRIDGE_FOOTPRINT_NAME + ".kicad_mod"):
            bridge_footprint_text(),
        SYM_LIB_TABLE: sym_lib_table_text(),
        FP_LIB_TABLE: fp_lib_table_text(),
    }


def write():
    os.makedirs(FOOTPRINT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(SYMBOL_LIB_PATH), exist_ok=True)
    written = []
    for path, text in artifacts().items():
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        written.append(path)
    return sorted(written)


if __name__ == "__main__":
    for path in write():
        sys.stdout.write(path + "\n")
