"""The one symbol KiCad's own libraries do not carry, and the library tables.

Everything else this board uses - the bridge, the suppressor, the receptacle,
the transistors, the passives - is a stock KiCad symbol on a stock KiCad
footprint, so the board owns no copy of it. The regulator is the exception:
KiCad ships no XC6206 symbol, so one is generated here from the pin
assignment table in the Torex datasheet.
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY_NAME = "UsbCUartDebugger"
SYMBOL_LIB_PATH = os.path.join(REPO_ROOT, "library",
                               LIBRARY_NAME + ".kicad_sym")
SYM_LIB_TABLE = os.path.join(REPO_ROOT, "sym-lib-table")
FP_LIB_TABLE = os.path.join(REPO_ROOT, "fp-lib-table")

SYMBOL_LIB_VERSION = "20251024"
GENERATOR = "usb-c-uart-debugger-design-source"

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


def sym_lib_table_text():
    return ('(sym_lib_table\n\t(version 7)\n'
            '\t(lib (name "%s")(type "KiCad")'
            '(uri "${KIPRJMOD}/library/%s.kicad_sym")(options "")(descr ""))\n)\n'
            % (LIBRARY_NAME, LIBRARY_NAME))


def fp_lib_table_text():
    """No board-owned footprints, but the table has to exist and be empty
    rather than absent: an absent table makes KiCad fall back to whatever the
    machine happens to have configured."""
    return '(fp_lib_table\n\t(version 7)\n)\n'


def artifacts():
    return {
        SYMBOL_LIB_PATH: symbol_library_text(),
        SYM_LIB_TABLE: sym_lib_table_text(),
        FP_LIB_TABLE: fp_lib_table_text(),
    }


def write():
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
