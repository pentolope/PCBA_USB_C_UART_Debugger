"""The board: outline, placement, pours, critical copper and silkscreen.

Board coordinates run x right and y UP from the lower-left corner, which is
the frame every dimension in this module is stated in. KiCad's own y runs
down, so the mapping is applied once, here.

The arrangement follows the signal. The receptacle is at the bottom edge and
the target header at the top, so the two connectors are on opposite ends of
the outline and neither can obstruct the other. Between them the data pair
runs straight up the middle - through its suppressor and into the bridge -
and everything else is arranged around that corridor rather than through it.

The back layer is one uninterrupted ground pour, which is the pair's
reference. The front layer is poured on ground too, but with a rule area
that keeps the pour out of a corridor either side of the pair: the impedance
and the delay this board reports come from a microstrip model, and a pour
running alongside the conductors at less than the dielectric thickness would
make that model describe a structure the board does not have.
"""
from __future__ import annotations

import json
import math
import os
import sys

from . import ksym, libraries, netlist

_TOOLKIT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tooling", "PCBA_AutoDesignAndTest")
if _TOOLKIT not in sys.path:
    sys.path.insert(0, _TOOLKIT)

from pcbqa import headless  # noqa: E402

headless.suppress_blocking_ui()

import pcbnew  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD_PATH = os.path.join(REPO_ROOT, netlist.PROJECT_NAME + ".kicad_pcb")
PLACEMENT_PATH = os.path.join(REPO_ROOT, "constraints", "placement.json")

FOOTPRINT_SEARCH_PATHS = (
    os.path.join(REPO_ROOT, "library"),
    "/usr/share/kicad/footprints",
)

ORIGIN_MM = (30.0, 80.0)

BOARD_W_MM = 20.0
BOARD_H_MM = 45.0

EDGE_WIDTH_MM = 0.1
TRACK_WIDTH_MM = 0.25
CLEARANCE_MM = 0.15
EDGE_CLEARANCE_MM = 0.3
VIA_DIAMETER_MM = 0.6
VIA_DRILL_MM = 0.3
ZONE_INSET_MM = 0.5
#: The narrowest strip of pour the fabricator will etch, and so the
#: narrowest one this board asks for. Copper thinner than this is not
#: poured at all, which is why a strip of reference between two cuts
#: narrower than this is not reference.
ZONE_MIN_WIDTH_MM = 0.2

#: Where the receptacle sits. Its own courtyard reaches 4.15 mm in front of
#: its origin, and the board is cut there, so the shell's opening is at the
#: edge and a plug meets nothing before it.
RECEPTACLE_MM = (10.0, 4.15)

#: The receptacle's own land row, and the four data lands along it. The
#: offsets are the footprint's; they are restated here because the whole
#: launch geometry below is built from them.
RECEPTACLE_LAND_Y_MM = RECEPTACLE_MM[1] + 4.045
RECEPTACLE_LAND_HALF_MM = 0.725
DATA_LAND_OFFSET_MM = {"B7": -0.75, "A6": -0.25, "A7": 0.25, "B6": 0.75}

#: The pair, from the receptacle to the bridge.
#:
#: The four data lands alternate - D-, D+, D-, D+ - so the two links that
#: join each line's pair of lands are two nets with interleaved terminals on
#: the boundary of a simply connected region. That cannot be drawn on one
#: layer, so each line takes exactly one layer change, and both take the
#: same one. The four traces leave the land row straight, clearing the
#: neighbouring lands, and only then fan apart: a 0.6 mm via cannot stand
#: beside a conductor half a millimetre away.
PAIR_CENTRE_X_MM = 10.0
#: How far north each data land goes before it turns. High enough that the
#: two sink terminations' own escape passes underneath it: their lands are
#: further out along the same row and have nowhere else to go.
LAND_ESCAPE_Y_MM = 9.7
FANOUT_Y_MM = 10.4
FANOUT_X_MM = {"B7": -1.5, "A6": -0.35, "A7": 0.35, "B6": 1.5}
LINK_Y_MM = {"USB_DM": 11.0, "USB_DP": 11.9}

#: Where the pair spreads to pass through the suppressor, which puts one
#: conductor on each of its two protected paths, and where it spreads again
#: so a probe pad can stand on each conductor without the two touching.
SUPPRESSOR_MM = (10.0, 15.6)
SPREAD_Y_MM = 13.2
PROBE_DX_MM = 1.3
PROBE_Y_MM = 19.8
PROBE_LEAD_MM = 0.9
CONVERGE_Y_MM = 21.4

#: The suppressor's reference pin sits between the two protected paths, and
#: its supply pin does too, because that is where its package puts them. The
#: reference goes straight into the plane through a via; the supply costs
#: one crossing under one conductor, taken on the back layer at a declared
#: place rather than left to a router to find.
CLAMP_GROUND_VIA_Y_MM = 13.0
CLAMP_RAIL_VIA_Y_MM = 18.0
CLAMP_RAIL_EXIT_X_MM = 13.2

#: The two sink terminations leave lands boxed between a no-connect land and
#: the pair, in a gap no search can fit a conductor through at its own
#: clearance. There is no freedom in either, so both are drawn here: north
#: out of the land, west or east clear of the pair's fan-out, and on to the
#: resistor.
CC_ESCAPE_Y_MM = 9.25
CC_LAND_OFFSET_MM = {"USB_CC1": -1.25, "USB_CC2": 1.75}
CC_RESISTOR = {"USB_CC1": "R1", "USB_CC2": "R2"}

USB_PAIR_KEEPOUT_HALF_WIDTH_MM = 2.4

#: The bridge faces its data pins south so the pair reaches them in a
#: straight line; its transmit and receive pins then face west, its reset
#: and suspend pins east, and the seven pins this board does not use north,
#: where nothing has to reach them.
BRIDGE_MM = (9.75, 24.6)
BRIDGE_THERMAL_HALF_MM = 1.45
BRIDGE_THERMAL_ESCAPE_MM = 2.30
#: The thermal land's escape is drawn at the board's minimum track width and
#: nothing wider. The corner it leaves through is bounded by the inner
#: corners of the two nearest lands, which stand 0.46 mm apart whatever the
#: thermal land's own size: only a track this narrow passes between them at
#: the board's clearance.
BRIDGE_THERMAL_ESCAPE_WIDTH_MM = 0.15
#: The ring between the thermal land and the perimeter lands is half a
#: millimetre wide. A conductor and its clearance fit in it only at the
#: board's floor, and a search that finds that out routes a signal through
#: the middle of a package - which is what the first run did. The four
#: sides of that ring are closed to tracks and vias; the corners are left
#: open because the thermal land's own escape leaves through two of them.
BRIDGE_RING_INNER_MM = 1.45
BRIDGE_RING_OUTER_MM = 1.95
#: How far along each side the closure reaches. Short of the corner, so the
#: thermal land's own two escapes leave through copper nothing forbids.
BRIDGE_RING_SPAN_MM = 1.20

#: The bridge's own escapes. Its lands are half a millimetre apart, and a
#: quarter-millimetre conductor between two of them has a quarter of a
#: millimetre either side - legal on this board, and less than the margin
#: the router is given to work to, so the router reports the pin boxed in
#: and gives up. There is no search freedom in a fine-pitch escape anyway:
#: it leaves its land the one way it can, straight out, and fans to a pitch
#: a search can work at. Which pins need one is a fact about the package and
#: about which of its neighbours this board leaves unconnected.
BRIDGE_ESCAPE_PINS = ("VBUS", "RSTB", "SUSPENDB", "CTS", "RTS", "RXD", "TXD")
BRIDGE_ESCAPE_RADIAL_MM = 3.30
BRIDGE_ESCAPE_FANOUT_MM = 4.20
BRIDGE_ESCAPE_SPREAD = 1.6
HEADER_PIN1_MM = (3.65, 39.5)
HEADER_PITCH_MM = 2.54

#: Where each probe's name is printed, chosen per probe because the room
#: beside a one-millimetre pad is whatever its neighbours have left.
PROBE_LABEL_OFFSET_MM = {"TP1": (2.4, 0.0), "TP2": (-3.0, 0.0),
                         "TP3": (0.0, 1.9)}

PLACEMENT = {
    "J1": RECEPTACLE_MM + (0.0,),
    "D1": SUPPRESSOR_MM + (90.0,),
    "U1": BRIDGE_MM + (90.0,),
    "J2": HEADER_PIN1_MM + (90.0,),

    # the receptacle's own network: the two sink terminations beside the
    # lands they belong to, the sense divider up the east side, and the
    # bypass and its probe up the west
    "R1": (6.40, 10.80, 180.0),
    "R2": (13.60, 10.80, 0.0),
    "R4": (16.80, 11.00, 90.0),
    "R5": (16.80, 14.40, 90.0),
    "C1": (3.20, 12.80, 0.0),
    # the hundred nanofarads that belongs to the suppressor's own rail pin
    # rather than to the regulator's input, so it sits where that pin's
    # conductor comes out rather than beside the bulk on the far side
    "C2": (13.20, 20.00, 90.0),
    "TP1": (2.20, 16.40, 0.0),

    # the bridge's own bypass: a hundred nanofarads at each supply pin and
    # the bulk beyond it, all east of the pair's corridor
    "C8": (14.00, 17.00, 0.0),
    "C7": (17.40, 17.00, 0.0),
    "C6": (15.80, 20.60, 0.0),
    "C5": (16.60, 22.60, 0.0),

    # the regulator and the rail it makes, up the west side
    "U2": (3.60, 20.40, 180.0),
    "C3": (3.20, 25.20, 0.0),
    "C4": (3.20, 27.20, 0.0),

    # rail bulk north of the bridge, which is what a target plugged in live
    # shares charge with
    "C9": (4.50, 29.30, 0.0),
    "C10": (8.00, 29.30, 0.0),
    "C11": (4.50, 32.00, 0.0),
    "R3": (8.00, 32.00, 0.0),

    # the target-supply switch, its driver and the two resistors that hold
    # it off, up the east side
    "Q1": (16.00, 26.00, 0.0),
    "Q2": (16.00, 29.80, 0.0),
    "Q3": (11.80, 29.70, 0.0),
    "R6": (19.00, 29.80, 90.0),
    "R7": (19.00, 26.00, 90.0),

    "TP2": (18.60, 19.00, 0.0),
    "TP3": (2.20, 34.60, 0.0),

    # the four series elements, each below the header pin it feeds
    "R11": (6.19, 35.50, 90.0),
    "R8": (11.27, 35.50, 90.0),
    "R9": (13.81, 35.50, 90.0),
    "R10": (16.35, 35.50, 90.0),
}


#: Parts a placement search may not move, and why. The connectors and the
#: probes are the board's mechanical and service contract; the suppressor's
#: position is the requirement that it sits between the receptacle and
#: everything downstream; the bridge anchors the pair.
LOCKED_REFERENCES = tuple(sorted(
    [reference for reference in netlist.PARTS
     if reference[0] in ("J",) and reference[1:].isdigit()]
    + [reference for reference in netlist.PARTS
       if reference.startswith("TP")]
    + ["D1", "U1"]))

#: The probe pads on the pair are points on it, not spurs off it: the
#: conductor enters one side and leaves the other through the pad's own
#: anchor, so nothing hangs and nothing is left touching a pad only at its
#: edge. The pair spreads to reach them, because two pads a millimetre
#: across cannot stand on two conductors half a millimetre apart.


def _pair_probe_pose(net):
    sign = -1.0 if net == "USB_DP" else 1.0
    return (PAIR_CENTRE_X_MM + sign * PROBE_DX_MM, PROBE_Y_MM, 0.0)


def seed_placement():
    placed = dict(PLACEMENT)
    placed["TP4"] = _pair_probe_pose("USB_DP")
    placed["TP5"] = _pair_probe_pose("USB_DM")
    return placed


def accepted_placement():
    """The placement a search accepted, if one has been recorded."""
    if not os.path.isfile(PLACEMENT_PATH):
        return {}
    with open(PLACEMENT_PATH, encoding="utf-8") as handle:
        document = json.load(handle)
    return {reference: tuple(pose)
            for reference, pose in document["placement"].items()
            if reference not in LOCKED_REFERENCES}


def fixed_placements():
    placed = seed_placement()
    for reference, pose in accepted_placement().items():
        if reference not in placed:
            raise KeyError("accepted placement names an unknown part: "
                           + reference)
        placed[reference] = pose
    missing = sorted(reference for reference, part in netlist.PARTS.items()
                     if part["footprint"] and reference not in placed)
    if missing:
        raise KeyError("no placement for " + ", ".join(missing))
    return placed


def to_board(x_mm, y_mm):
    return (ORIGIN_MM[0] + x_mm, ORIGIN_MM[1] - y_mm)


def _point(x_mm, y_mm):
    bx, by = to_board(x_mm, y_mm)
    return pcbnew.VECTOR2I(pcbnew.FromMM(bx), pcbnew.FromMM(by))


def _footprint_dir(footprint):
    library, _, name = footprint.partition(":")
    for base in FOOTPRINT_SEARCH_PATHS:
        candidate = os.path.join(base, library + ".pretty")
        if os.path.isfile(os.path.join(candidate, name + ".kicad_mod")):
            return candidate, name
    raise FileNotFoundError(footprint)


_PIN_NAMES = {}


def _pin_name(lib_id, number):
    if lib_id not in _PIN_NAMES:
        library = ksym.Library(netlist.SYMBOL_LIBRARY_PATHS)
        _PIN_NAMES[lib_id] = {
            key: pins[0].name for key, pins in library.pins(lib_id).items()}
    return _PIN_NAMES[lib_id].get(number, "")


def _floating_net(board, reference, number):
    lib_id = netlist.PARTS[reference]["lib_id"]
    name = "unconnected-(%s-%s-Pad%s)" % (
        reference, _pin_name(lib_id, number).replace("/", "{slash}"), number)
    existing = board.GetNetInfo().GetNetItem(name)
    if existing is not None and existing.GetNetCode() != 0:
        return existing
    net = pcbnew.NETINFO_ITEM(board, name)
    _NET_RECORDS.append(net)
    board.Add(net)
    return net


def _load(board, reference, part, x, y, rotation, pin_net):
    library_dir, name = _footprint_dir(part["footprint"])
    footprint = pcbnew.FootprintLoad(library_dir, name)
    if footprint is None:
        raise RuntimeError("could not load " + part["footprint"])
    library = part["footprint"].partition(":")[0]
    footprint.SetFPID(pcbnew.LIB_ID(library, name))
    footprint.SetPosition(_point(x, y))
    footprint.SetOrientationDegrees(rotation)
    footprint.SetReference(reference)
    footprint.SetValue(part["value"])
    footprint.Reference().SetLayer(pcbnew.F_Fab)
    footprint.Value().SetLayer(pcbnew.F_Fab)
    for key, value in (("MPN", part["mpn"]), ("LCSC", part["lcsc"]),
                       ("Manufacturer", part["manufacturer"])):
        if not value:
            continue
        footprint.SetField(key, value)
        for field in footprint.GetFields():
            if field.GetName() == key:
                field.SetLayer(pcbnew.F_Fab)
                field.SetVisible(False)
    if not part["in_bom"]:
        footprint.SetExcludedFromBOM(True)
    if reference in LOCKED_REFERENCES:
        footprint.SetLocked(True)
    for pad in footprint.Pads():
        number = pad.GetNumber()
        if not number:
            continue
        net_name = pin_net.get("%s.%s" % (reference, number))
        if net_name:
            pad.SetNet(_net(board, net_name))
        else:
            pad.SetNet(_floating_net(board, reference, number))
    board.Add(_own(footprint))
    return footprint


#: Every net record this module creates, kept for as long as the process
#: runs. Adding a net to a board is supposed to hand the board its
#: ownership, but the binding leaves the Python wrapper owning it too: drop
#: the last reference and the record is freed while the board still points
#: at it, and the next thing to be written into that memory becomes the net
#: a via belongs to. One stitch between the two ground pours was saved on
#: the supply that way.
_NET_RECORDS = []

#: And every other item this module hands to a board, for the same reason.
#: `BOARD::Add` is supposed to take ownership; the binding leaves the Python
#: wrapper owning it as well, so the moment the last reference goes the item
#: is freed under the board. Whatever is written into that memory next
#: becomes what the board writes out - which is how one stitch between the
#: two ground pours came back saved on the supply net.
_ITEMS = []


def _own(item):
    _ITEMS.append(item)
    return item


def _create_nets(board):
    _NET_CACHE.clear()
    for name in sorted(netlist.NETS):
        record = pcbnew.NETINFO_ITEM(board, name)
        _NET_RECORDS.append(record)
        board.Add(record)


#: One wrapper per net, looked up once and then reused. Every lookup
#: returns a fresh Python object over a record the board owns, and the
#: binding lets those objects own it too: a lookup whose wrapper is
#: collected takes the board's record with it, and the next record created
#: lands in the same memory. That is how one stitch between the two ground
#: pours came back written on the supply net.
_NET_CACHE = {}


def _net(board, name):
    """The board's own record for a net name, looked up once."""
    if name not in _NET_CACHE:
        net = board.GetNetInfo().GetNetItem(name)
        if net is None or net.GetNetCode() == 0:
            raise KeyError("the board carries no net named " + name)
        _NET_CACHE[name] = net
    return _NET_CACHE[name]


def _design_settings(board):
    board.SetCopperLayerCount(2)
    settings = board.GetDesignSettings()
    settings.m_TrackMinWidth = pcbnew.FromMM(0.15)
    settings.m_ViasMinSize = pcbnew.FromMM(0.45)
    settings.m_MinThroughDrill = pcbnew.FromMM(0.25)
    settings.m_CopperEdgeClearance = pcbnew.FromMM(EDGE_CLEARANCE_MM)
    settings.m_HoleClearance = pcbnew.FromMM(0.25)
    settings.m_HoleToHoleMin = pcbnew.FromMM(0.25)
    settings.m_ViasMinAnnularWidth = pcbnew.FromMM(0.1)
    settings.m_MinClearance = pcbnew.FromMM(CLEARANCE_MM)
    default_class = settings.m_NetSettings.GetDefaultNetclass()
    default_class.SetClearance(pcbnew.FromMM(CLEARANCE_MM))
    default_class.SetTrackWidth(pcbnew.FromMM(TRACK_WIDTH_MM))
    default_class.SetViaDiameter(pcbnew.FromMM(VIA_DIAMETER_MM))
    default_class.SetViaDrill(pcbnew.FromMM(VIA_DRILL_MM))


def _add_outline(board):
    corners = [(0.0, 0.0), (BOARD_W_MM, 0.0), (BOARD_W_MM, BOARD_H_MM),
               (0.0, BOARD_H_MM)]
    closed = corners + [corners[0]]
    for start, end in zip(closed, closed[1:]):
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
        shape.SetStart(_point(*start))
        shape.SetEnd(_point(*end))
        shape.SetLayer(pcbnew.Edge_Cuts)
        shape.SetWidth(pcbnew.FromMM(EDGE_WIDTH_MM))
        board.Add(_own(shape))


def _rectangle_zone(board, corners, layers):
    zone = pcbnew.ZONE(board)
    layer_set = pcbnew.LSET()
    for layer in layers:
        layer_set.addLayer(layer)
    zone.SetLayerSet(layer_set)
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in corners:
        bx, by = to_board(x, y)
        outline.Append(pcbnew.FromMM(bx), pcbnew.FromMM(by))
    return zone


def _pour(board, net, corners, layers, priority=0):
    zone = _rectangle_zone(board, corners, layers)
    zone.SetNet(net)
    zone.SetAssignedPriority(priority)
    zone.SetLocalClearance(pcbnew.FromMM(CLEARANCE_MM))
    zone.SetMinThickness(pcbnew.FromMM(ZONE_MIN_WIDTH_MM))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    zone.SetThermalReliefGap(pcbnew.FromMM(0.3))
    zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.4))
    board.Add(_own(zone))
    return zone


def pair_corridor_mm():
    """The band the front pour is kept out of, and why it is that wide.

    The pair's impedance and delay are reported from a microstrip model,
    whose reference is the plane below. Front-layer copper running alongside
    at less than the dielectric thickness would couple to the conductors
    more strongly than that plane does, and the reported numbers would then
    describe a structure this board does not have. The corridor is therefore
    wider than the dielectric is thick.
    """
    half = USB_PAIR_KEEPOUT_HALF_WIDTH_MM
    return (PAIR_CENTRE_X_MM - half, max(LINK_Y_MM.values()) + 0.6,
            PAIR_CENTRE_X_MM + half, CONVERGE_Y_MM + 0.2)


def _rule_area(board, corners, layers, fills=False, tracks=False,
               vias=False):
    zone = _rectangle_zone(board, corners, layers)
    zone.SetIsRuleArea(True)
    zone.SetDoNotAllowZoneFills(fills)
    zone.SetDoNotAllowTracks(tracks)
    zone.SetDoNotAllowVias(vias)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    board.Add(_own(zone))
    return zone


def bridge_ring_areas_mm():
    """The four sides of the bridge's land ring, as rectangles."""
    x, y, _rotation = fixed_placements()["U1"]
    inner, outer = BRIDGE_RING_INNER_MM, BRIDGE_RING_OUTER_MM
    span = BRIDGE_RING_SPAN_MM
    return [
        (x - span, y + inner, x + span, y + outer),
        (x - span, y - outer, x + span, y - inner),
        (x - outer, y - span, x - inner, y + span),
        (x + inner, y - span, x + outer, y + span),
    ]


def unreferenced_budgets_mm():
    """How much of each conductor runs with no reference, and from what.

    Not a tolerance and not a measurement: the sum of the interruptions the
    design source itself puts in the way, priced from this board's own
    conductor width, via diameter, clearance and minimum pour width. A
    routed board that measures more than this has something in it that the
    design source did not put there.

    On the front layer, over the plane, each conductor meets:

    * the other line's orientation link, which the receptacle's land order
      forces onto the back layer and across this conductor;
    * the suppressor's rail conductor, which its package puts between the
      two protected paths;
    * its own layer change, whose barrel and clearance take the plane out
      from under the very copper that lands on it;

    and, beside each of those, one strip of plane that can come out
    narrower than the fabricator will etch and so is not poured at all.

    On the back layer, the orientation link runs under the receptacle's
    launch, where the four fan-out conductors and their clearances leave no
    front area wide enough to pour. The whole link, plus the clearance the
    front copper is held off by at each end, is unreferenced.
    """
    cuts = ((TRACK_WIDTH_MM + 2 * CLEARANCE_MM),      # the other line's link
            (TRACK_WIDTH_MM + 2 * CLEARANCE_MM),      # the suppressor's rail
            (VIA_DIAMETER_MM + 2 * CLEARANCE_MM))     # the conductor's own via
    front = sum(cut + ZONE_MIN_WIDTH_MM for cut in cuts)
    back = max(abs(FANOUT_X_MM[netlist.USB_C_PAIR_TERMINALS[net]]
                   - FANOUT_X_MM[netlist.USB_C_FLIPPED_TERMINALS[net]])
               for net in netlist.USB_C_PAIR_TERMINALS) + 2 * CLEARANCE_MM
    return front, back


def pair_plane_region_mm():
    """The whole area over the plane that belongs to the pair.

    Nothing this board generates for its own convenience — a stitch, a
    spare via — goes here, on either layer. What the reference under the
    pair is missing has to stay a property of the design source.
    """
    half = USB_PAIR_KEEPOUT_HALF_WIDTH_MM
    return (PAIR_CENTRE_X_MM - half, RECEPTACLE_LAND_Y_MM - 1.0,
            PAIR_CENTRE_X_MM + half, CONVERGE_Y_MM + 0.2)


def plane_keepout_bands_mm():
    """Where nothing may be drawn on the plane under the pair.

    The plane under the pair is closed to back-layer conductors for the
    whole run, from the receptacle lands to the point the pair converges on
    the bridge, except in the three rows the design source itself crosses
    it: one for each orientation link, which the receptacle's land order
    forces, and one for the suppressor's rail conductor, which its package
    forces. Everything else the search might have put under the pair would
    be a slot in the reference, and this board's reported impedance and
    delay would then describe a structure it does not have. Those three
    rows, and nothing else, are what the manifest's reference-continuity
    budget pays for.
    """
    x0, _, x1, _ = pair_plane_region_mm()
    windows = []
    for y in sorted(list(LINK_Y_MM.values()) + [CLAMP_RAIL_VIA_Y_MM]):
        low, high = y - 0.6, y + 0.6
        if windows and low <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(windows[-1][1], high))
        else:
            windows.append((low, high))
    bands, y = [], RECEPTACLE_LAND_Y_MM - 1.0
    for low, high in windows:
        if low > y:
            bands.append((x0, y, x1, low))
        y = max(y, high)
    if CONVERGE_Y_MM + 0.2 > y:
        bands.append((x0, y, x1, CONVERGE_Y_MM + 0.2))
    return bands


def _add_keepout(board):
    x0, y0, x1, y1 = pair_corridor_mm()
    _rule_area(board, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
               (pcbnew.F_Cu,), fills=True)
    for bx0, by0, bx1, by1 in plane_keepout_bands_mm():
        # Tracks only. A via on the reference itself is the suppressor's own
        # way down to the plane and takes nothing out of it; a via on any
        # other net has to arrive on a track, and no track may be here.
        _rule_area(board, [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)],
                   (pcbnew.B_Cu,), tracks=True)
    for x0, y0, x1, y1 in bridge_ring_areas_mm():
        _rule_area(board, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                   (pcbnew.F_Cu, pcbnew.B_Cu), tracks=True, vias=True)


def _add_pours(board):
    inset = ZONE_INSET_MM
    corners = [(inset, inset), (BOARD_W_MM - inset, inset),
               (BOARD_W_MM - inset, BOARD_H_MM - inset),
               (inset, BOARD_H_MM - inset)]
    # A fill area the routed copper cuts off from every stitch and every pad
    # is not a return path; it is a floating plate the size of whatever is
    # left. Both pours drop those rather than keep them.
    for layer in (pcbnew.B_Cu, pcbnew.F_Cu):
        pour = _pour(board, _net(board, "GND"), corners, (layer,))
        pour.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)


def _add_track(board, start, end, layer, net, width_mm):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetLayer(layer)
    track.SetNet(net)
    track.SetWidth(pcbnew.FromMM(width_mm))
    board.Add(_own(track))
    return track


def _polyline(board, points, layer, net, width_mm):
    for first, second in zip(points, points[1:]):
        if first == second:
            continue
        _add_track(board, _point(*first), _point(*second), layer, net,
                   width_mm)


def _add_via(board, x_mm, y_mm, net, diameter_mm=VIA_DIAMETER_MM,
             drill_mm=VIA_DRILL_MM):
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(_point(x_mm, y_mm))
    via.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(diameter_mm))
    via.SetDrill(pcbnew.FromMM(drill_mm))
    via.SetNet(net)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(_own(via))
    return via


def _pad(footprints, reference, number):
    for pad in footprints[reference].Pads():
        if pad.GetNumber() == number:
            return pad
    raise KeyError("%s has no pad %s" % (reference, number))


def _pad_mm(footprints, reference, number):
    position = _pad(footprints, reference, number).GetPosition()
    return (pcbnew.ToMM(position.x) - ORIGIN_MM[0],
            ORIGIN_MM[1] - pcbnew.ToMM(position.y))


# ---------------------------------------------------------------------------
# the pair

def _route_pair(board, footprints):
    """The pair, from the receptacle lands to the bridge.

    Generated rather than searched, because there is no search freedom in
    it: the launch geometry follows from the receptacle's own land order,
    the two layer changes are forced by that order, and everything after
    them is two conductors held at a fixed separation over an uninterrupted
    plane.
    """
    centre = PAIR_CENTRE_X_MM
    land_y = RECEPTACLE_LAND_Y_MM
    escape_y = LAND_ESCAPE_Y_MM

    # 1. every land leaves its row straight, past its neighbours, and only
    #    then fans to where a via can stand beside a conductor
    for land, offset in sorted(DATA_LAND_OFFSET_MM.items()):
        net_name = "USB_DP" if land in ("A6", "B6") else "USB_DM"
        _polyline(board, [(centre + offset, land_y),
                          (centre + offset, escape_y),
                          (centre + FANOUT_X_MM[land], FANOUT_Y_MM)],
                  pcbnew.F_Cu, _net(board, net_name), TRACK_WIDTH_MM)

    # 2. the two orientation links, each one layer change on the back
    for net_name, land in sorted(netlist.USB_C_FLIPPED_TERMINALS.items()):
        link_y = LINK_Y_MM[net_name]
        from_x = centre + FANOUT_X_MM[land]
        main_land = netlist.USB_C_PAIR_TERMINALS[net_name]
        to_x = centre + FANOUT_X_MM[main_land]
        _polyline(board, [(from_x, FANOUT_Y_MM), (from_x, link_y)],
                  pcbnew.F_Cu, _net(board, net_name), TRACK_WIDTH_MM)
        _add_via(board, from_x, link_y, _net(board, net_name))
        _polyline(board, [(from_x, link_y), (to_x, link_y)],
                  pcbnew.B_Cu, _net(board, net_name), TRACK_WIDTH_MM)
        _add_via(board, to_x, link_y, _net(board, net_name))

    # 3. the pair itself: up from the main lands, out to the suppressor's
    #    two protected paths, through it, out again to the probes, and in to
    #    the bridge
    for net_name, land in sorted(netlist.USB_C_PAIR_TERMINALS.items()):
        sign = -1.0 if net_name == "USB_DP" else 1.0
        main_x = centre + FANOUT_X_MM[land]
        probe_x = centre + sign * PROBE_DX_MM
        # Where this conductor meets the suppressor is the suppressor's
        # own geometry, read off its pads rather than restated here: the
        # conductor has to arrive at the pad centre, and a figure that
        # merely agrees with the footprint today would not.
        south_pad, north_pad = sorted(
            (_pad_mm(footprints, "D1", pin.split(".")[1])
             for pin in netlist.NETS[net_name] if pin.startswith("D1.")),
            key=lambda point: point[1])
        path_x = south_pad[0]
        bridge_pad = _pad_mm(
            footprints, "U1",
            netlist.BRIDGE_PINS["DP" if net_name == "USB_DP" else "DM"])
        # The vertices at the link via and at the suppressor's first pad
        # bend nothing: they are there so both land where two conductors
        # meet end to end, rather than part-way along one. Copper landing
        # part-way along a conductor leaves the meeting point ambiguous over
        # the width of the overlap, and that ambiguity is what a length
        # measurement has to carry as its error bar.
        _polyline(board, [
            (main_x, FANOUT_Y_MM),
            (main_x, LINK_Y_MM[net_name]),
            (main_x, SPREAD_Y_MM - 0.8),
            (path_x, SPREAD_Y_MM),
            (path_x, south_pad[1]),
            (path_x, north_pad[1]),
            (path_x, PROBE_Y_MM - PROBE_LEAD_MM),
            (probe_x, PROBE_Y_MM),
        ], pcbnew.F_Cu, _net(board, net_name), TRACK_WIDTH_MM)
        _polyline(board, [
            (probe_x, PROBE_Y_MM),
            (probe_x, CONVERGE_Y_MM - 1.0),
            (bridge_pad[0], CONVERGE_Y_MM),
            (bridge_pad[0], bridge_pad[1]),
        ], pcbnew.F_Cu, _net(board, net_name), TRACK_WIDTH_MM)

    # 4. the suppressor's own connections: its reference pin straight down
    #    into the plane, and its supply pin out to the east across one
    #    conductor, on the back, at a place this module chooses rather than
    #    a router
    ground_pad = _pad_mm(footprints, "D1", "2")
    _polyline(board, [(ground_pad[0], ground_pad[1]),
                      (ground_pad[0], CLAMP_GROUND_VIA_Y_MM)],
              pcbnew.F_Cu, _net(board, "GND"), TRACK_WIDTH_MM)
    _add_via(board, ground_pad[0], CLAMP_GROUND_VIA_Y_MM, _net(board, "GND"))

    rail_pad = _pad_mm(footprints, "D1", "5")
    bypass_pad = _pad_mm(footprints, "C2", "1")
    _polyline(board, [(rail_pad[0], rail_pad[1]),
                      (rail_pad[0], CLAMP_RAIL_VIA_Y_MM)],
              pcbnew.F_Cu, _net(board, "VBUS"), TRACK_WIDTH_MM)
    _add_via(board, rail_pad[0], CLAMP_RAIL_VIA_Y_MM, _net(board, "VBUS"))
    _polyline(board, [(rail_pad[0], CLAMP_RAIL_VIA_Y_MM),
                      (CLAMP_RAIL_EXIT_X_MM, CLAMP_RAIL_VIA_Y_MM)],
              pcbnew.B_Cu, _net(board, "VBUS"), TRACK_WIDTH_MM)
    _add_via(board, CLAMP_RAIL_EXIT_X_MM, CLAMP_RAIL_VIA_Y_MM, _net(board, "VBUS"))
    _polyline(board, [(CLAMP_RAIL_EXIT_X_MM, CLAMP_RAIL_VIA_Y_MM),
                      (bypass_pad[0], bypass_pad[1])],
              pcbnew.F_Cu, _net(board, "VBUS"), TRACK_WIDTH_MM)


def _route_cc(board, footprints):
    """The two sink terminations, out of lands nothing else can leave."""
    for net_name, offset in sorted(CC_LAND_OFFSET_MM.items()):
        land = (PAIR_CENTRE_X_MM + offset, RECEPTACLE_LAND_Y_MM)
        pad = _pad_mm(footprints, CC_RESISTOR[net_name], "1")
        _polyline(board, [(land[0], land[1]),
                          (land[0], CC_ESCAPE_Y_MM),
                          (pad[0], CC_ESCAPE_Y_MM),
                          (pad[0], pad[1])],
                  pcbnew.F_Cu, _net(board, net_name), TRACK_WIDTH_MM)


def bridge_escape_geometry():
    """Each escaping land, as the two points its conductor runs through."""
    x, y, _rotation = fixed_placements()["U1"]
    geometry = {}
    for function in BRIDGE_ESCAPE_PINS:
        number = netlist.BRIDGE_PINS[function]
        index = int(number) - 1
        side, position = divmod(index, libraries.BRIDGE_PADS_PER_SIDE)
        span = libraries.BRIDGE_PITCH_MM * (
            libraries.BRIDGE_PADS_PER_SIDE - 1) / 2.0
        along = libraries.BRIDGE_PITCH_MM * position - span
        # Sides in pad order, as unit vectors in the board frame after the
        # bridge's own rotation: south, east, north, west.
        outward = [(0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)][side]
        transverse = [(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)][side]
        first = (x + outward[0] * BRIDGE_ESCAPE_RADIAL_MM
                 + transverse[0] * along,
                 y + outward[1] * BRIDGE_ESCAPE_RADIAL_MM
                 + transverse[1] * along)
        second = (x + outward[0] * BRIDGE_ESCAPE_FANOUT_MM
                  + transverse[0] * along * BRIDGE_ESCAPE_SPREAD,
                  y + outward[1] * BRIDGE_ESCAPE_FANOUT_MM
                  + transverse[1] * along * BRIDGE_ESCAPE_SPREAD)
        geometry[function] = (number, first, second)
    return geometry


def _route_bridge_escapes(board, footprints):
    pin_net = netlist.pin_to_net()
    for function, (number, first, second) in sorted(
            bridge_escape_geometry().items()):
        net = _net(board, pin_net["U1." + number])
        pad = _pad_mm(footprints, "U1", number)
        _polyline(board, [pad, first, second], pcbnew.F_Cu, net,
                  TRACK_WIDTH_MM)
        del function


def _route_thermal_land(board, footprints):
    """The bridge's thermal land, out to the plane at two corners.

    The land is the datasheet's, narrowed until a corridor opens at each
    corner; a track leaves through two opposite ones and ends on a via, so
    the land reaches both planes without a via standing in a pad that takes
    paste.
    """
    x, y, _rotation = fixed_placements()["U1"]
    half = BRIDGE_THERMAL_HALF_MM
    reach = BRIDGE_THERMAL_ESCAPE_MM
    for sx, sy in ((-1.0, -1.0), (1.0, 1.0)):
        _polyline(board, [(x + sx * half, y + sy * half),
                          (x + sx * reach, y + sy * reach)],
                  pcbnew.F_Cu, _net(board, "GND"),
                  BRIDGE_THERMAL_ESCAPE_WIDTH_MM)
        _add_via(board, x + sx * reach, y + sy * reach, _net(board, "GND"))


# ---------------------------------------------------------------------------
# ground

#: How far apart the stitches between the two ground pours are placed, and
#: how far a stitch has to stay from anything it is not part of. The grid is
#: a declared figure rather than a searched one: what matters is that the
#: front pour and the plane are tied often enough that no island of front
#: copper is left to find its own way back, and a four-millimetre grid over
#: a board this size is far more often than the shortest wavelength in play
#: would ask for.
STITCH_GRID_MM = 3.5
STITCH_KEEP_OUT_MM = 0.35


def _obstacles(board):
    """Every pad and via, as a centre and a radius a stitch must clear."""
    found = []
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            size = pad.GetSize()
            found.append((pad.GetPosition(),
                          math.hypot(size.x, size.y) / 2.0))
    for item in board.GetTracks():
        if item.Type() == pcbnew.PCB_VIA_T:
            found.append((item.GetPosition(),
                          item.GetWidth(pcbnew.F_Cu) / 2.0))
        else:
            for point in (item.GetStart(), item.GetEnd()):
                found.append((point, item.GetWidth() / 2.0))
    return found


def stitch_positions(board):
    """Where the two ground pours are tied together.

    A regular grid, minus every position that would stand too close to
    something else and minus the pair's own area, which nothing but the
    pair and its own suppressor is allowed into.
    """
    obstacles = _obstacles(board)
    keep_out = pcbnew.FromMM(VIA_DIAMETER_MM / 2.0 + STITCH_KEEP_OUT_MM)
    x0, y0, x1, y1 = pair_plane_region_mm()
    margin = VIA_DIAMETER_MM / 2.0 + EDGE_CLEARANCE_MM + ZONE_INSET_MM
    placed = []
    steps_x = int((BOARD_W_MM - 2 * margin) // STITCH_GRID_MM) + 1
    steps_y = int((BOARD_H_MM - 2 * margin) // STITCH_GRID_MM) + 1
    span_x = STITCH_GRID_MM * (steps_x - 1)
    span_y = STITCH_GRID_MM * (steps_y - 1)
    for ix in range(steps_x):
        for iy in range(steps_y):
            x_mm = (BOARD_W_MM - span_x) / 2.0 + STITCH_GRID_MM * ix
            y_mm = (BOARD_H_MM - span_y) / 2.0 + STITCH_GRID_MM * iy
            if x0 <= x_mm <= x1 and y0 <= y_mm <= y1:
                continue
            centre = pcbnew.VECTOR2I(
                pcbnew.FromMM(ORIGIN_MM[0] + x_mm),
                pcbnew.FromMM(ORIGIN_MM[1] - y_mm))
            if any(math.hypot(centre.x - point.x, centre.y - point.y)
                   < radius + keep_out for point, radius in obstacles):
                continue
            placed.append((x_mm, y_mm))
    return placed


#: How far a pad on the reference may be from a stitch before it gets one
#: of its own. A pad the routed copper cuts off from the grid is left on an
#: island of front pour with nothing to reach the plane through.
STITCH_PAD_REACH_MM = 2.5


def _segment_clear(start, end, obstacles, keep_out):
    """Whether a straight run between two points clears everything."""
    for point, radius in obstacles:
        dx, dy = end.x - start.x, end.y - start.y
        length2 = dx * dx + dy * dy
        if length2 == 0:
            continue
        t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length2
        t = max(0.0, min(1.0, t))
        near_x, near_y = start.x + t * dx, start.y + t * dy
        if math.hypot(near_x - point.x, near_y - point.y) < radius + keep_out:
            return False
    return True


def _stitch_pad(board, pad, net):
    """Put a via beside one pad and bond it, or say it could not."""
    position = pad.GetPosition()
    size = pad.GetSize()
    obstacles = [(point, radius) for point, radius in _obstacles(board)
                 if math.hypot(point.x - position.x, point.y - position.y)
                 > max(size.x, size.y) / 4.0]
    keep_out = pcbnew.FromMM(VIA_DIAMETER_MM / 2.0 + STITCH_KEEP_OUT_MM)
    x0, y0, x1, y1 = pair_plane_region_mm()
    half = (pcbnew.ToMM(size.x) / 2.0, pcbnew.ToMM(size.y) / 2.0)
    for axis in ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)):
        reach = (abs(axis[0]) * half[0] + abs(axis[1]) * half[1]
                 + VIA_DIAMETER_MM / 2.0 + STITCH_KEEP_OUT_MM)
        for extra in (0.0, 0.5, 1.0):
            centre = pcbnew.VECTOR2I(
                int(position.x + pcbnew.FromMM(axis[0] * (reach + extra))),
                int(position.y + pcbnew.FromMM(axis[1] * (reach + extra))))
            x_mm = pcbnew.ToMM(centre.x) - ORIGIN_MM[0]
            y_mm = ORIGIN_MM[1] - pcbnew.ToMM(centre.y)
            margin = VIA_DIAMETER_MM / 2.0 + EDGE_CLEARANCE_MM + ZONE_INSET_MM
            if not (margin <= x_mm <= BOARD_W_MM - margin
                    and margin <= y_mm <= BOARD_H_MM - margin):
                continue
            if x0 <= x_mm <= x1 and y0 <= y_mm <= y1:
                continue
            if any(math.hypot(centre.x - point.x, centre.y - point.y)
                   < radius + keep_out for point, radius in obstacles):
                continue
            if not _segment_clear(position, centre, obstacles, keep_out):
                continue
            _add_via(board, x_mm, y_mm, net)
            _add_track(board, position, centre, pcbnew.F_Cu, net,
                       TRACK_WIDTH_MM)
            return True
    return False


def _stitch_pads(board):
    """Every surface pad on the reference reaches the plane.

    The grid alone is not enough: routed copper cuts the front pour into
    areas, and a pad that ends up on one with no stitch in it has nothing
    to return through. Each such pad gets its own.
    """
    net = _net(board, "GND")
    reach = pcbnew.FromMM(STITCH_PAD_REACH_MM)
    for footprint in sorted(board.GetFootprints(),
                            key=lambda item: item.GetReference()):
        for pad in footprint.Pads():
            if pad.GetNetname() != "GND":
                continue
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            position = pad.GetPosition()
            near = [item for item in board.GetTracks()
                    if item.Type() == pcbnew.PCB_VIA_T
                    and item.GetNetCode() == net.GetNetCode()
                    and math.hypot(item.GetPosition().x - position.x,
                                   item.GetPosition().y - position.y) < reach]
            if near:
                continue
            _stitch_pad(board, pad, net)


def _stitch_grounds(board):
    """Tie the front pour to the plane on a declared grid.

    Every pad on the reference is inside the front pour, so nothing has to
    be taken to the plane pad by pad; what the stitches do is keep the two
    pours one conductor rather than two.
    """
    for x_mm, y_mm in stitch_positions(board):
        _add_via(board, x_mm, y_mm, _net(board, "GND"))


def fill_zones(board):
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    return board


def build(with_copper=True):
    board = pcbnew.CreateEmptyBoard()
    _design_settings(board)
    _create_nets(board)
    pin_net = netlist.pin_to_net()

    footprints = {}
    placed = fixed_placements()
    for reference, (x, y, rotation) in sorted(placed.items()):
        part = netlist.PARTS[reference]
        if not part["footprint"]:
            continue
        footprints[reference] = _load(
            board, reference, part, x, y, rotation, pin_net)

    _add_outline(board)
    _add_keepout(board)
    if with_copper:
        _add_pours(board)
        _route_pair(board, footprints)
        _route_cc(board, footprints)
        _route_bridge_escapes(board, footprints)
        _route_thermal_land(board, footprints)
        _stitch_grounds(board)
        _stitch_pads(board)
    _add_silkscreen(board, footprints)
    return board, footprints


# ---------------------------------------------------------------------------
# silkscreen

SILK_LAYER = pcbnew.F_SilkS
#: KiCad refuses text below 0.8 mm, so nothing here is smaller.
SILK_TEXT_MM = 1.0
SILK_SMALL_MM = 0.8
SILK_THICKNESS_MM = 0.15


def _text(board, value, x, y, size_mm=SILK_TEXT_MM, layer=None, angle=0.0):
    item = pcbnew.PCB_TEXT(board)
    item.SetText(value)
    item.SetPosition(_point(x, y))
    item.SetLayer(SILK_LAYER if layer is None else layer)
    item.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size_mm),
                                     pcbnew.FromMM(size_mm)))
    item.SetTextThickness(pcbnew.FromMM(SILK_THICKNESS_MM))
    item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    if angle:
        item.SetTextAngleDegrees(angle)
    board.Add(_own(item))
    return item


def header_labels():
    """What goes beside each header pin, from the header's own function map."""
    return {pin: label for pin, (label, _net)
            in netlist.TARGET_HEADER_PINS.items()}


def probe_labels():
    """Which probe carries which net, from the netlist rather than a list."""
    pin_net = netlist.pin_to_net()
    return {reference: pin_net["%s.1" % reference]
            for reference in netlist.PARTS if reference.startswith("TP")}


def rating_text():
    """What the board is marked with, from what it claims."""
    return "3V3 OUT %d mA MAX" % round(1e3 * netlist.TARGET_SUPPLY_BUDGET_A)


def point_of_view_text():
    """Whose transmit is on pin 4, said on the board rather than only in a
    document nobody has when they are wiring one."""
    return "TX RX = ADAPTER"


def _add_silkscreen(board, footprints):
    placed = fixed_placements()
    x1, y1, _rot = placed["J2"]
    for pin, label in sorted(header_labels().items()):
        _text(board, label, x1 + HEADER_PITCH_MM * (pin - 1), y1 + 1.9,
              size_mm=SILK_SMALL_MM)
    # Pin one is marked by a square land in the footprint and by a name the
    # eye finds before it counts pins.
    _text(board, "1", x1 - 1.7, y1 + 1.9, size_mm=SILK_SMALL_MM)
    _text(board, point_of_view_text(), BOARD_W_MM / 2.0, y1 + 3.1,
          size_mm=SILK_SMALL_MM)
    _text(board, rating_text(), BOARD_W_MM / 2.0, y1 + 4.3,
          size_mm=SILK_SMALL_MM)
    for reference, net in sorted(probe_labels().items()):
        x, y, _ = placed[reference]
        if reference not in PROBE_LABEL_OFFSET_MM:
            continue
        dx, dy = PROBE_LABEL_OFFSET_MM[reference]
        _text(board, net, x + dx, y + dy, size_mm=SILK_SMALL_MM)
    for reference, net in (("TP4", "D+"), ("TP5", "D-")):
        x, y, _ = placed[reference]
        _text(board, net, x, y - 1.6, size_mm=SILK_SMALL_MM)


def via_nets():
    """Every via this module places, as position and net.

    Recorded so that what was written can be checked against what was
    meant. It is not a formality: a via written out on the wrong net is
    a short or an open that nothing upstream of the board file would
    catch, and one appeared during this board's development.
    """
    board, _ = build()
    return {(round(pcbnew.ToMM(via.GetPosition().x) - ORIGIN_MM[0], 3),
             round(ORIGIN_MM[1] - pcbnew.ToMM(via.GetPosition().y), 3)):
            via.GetNetname()
            for via in board.GetTracks()
            if via.Type() == pcbnew.PCB_VIA_T}


def _verify(path, intended):
    """Every via in the written board carries the net it was given."""
    written = pcbnew.LoadBoard(path)
    wrong = []
    for via in written.GetTracks():
        if via.Type() != pcbnew.PCB_VIA_T:
            continue
        key = (round(pcbnew.ToMM(via.GetPosition().x) - ORIGIN_MM[0], 3),
               round(ORIGIN_MM[1] - pcbnew.ToMM(via.GetPosition().y), 3))
        if intended.get(key) != via.GetNetname():
            wrong.append((key, intended.get(key), via.GetNetname()))
    if wrong:
        raise RuntimeError(
            "the written board disagrees with the design source about "
            "%d via net(s): %s" % (len(wrong), wrong))


def write(path=None):
    """Write the board, then rewrite the project it belongs to."""
    from . import build as _build
    board, _ = build()
    intended = {(round(pcbnew.ToMM(via.GetPosition().x) - ORIGIN_MM[0], 3),
                 round(ORIGIN_MM[1] - pcbnew.ToMM(via.GetPosition().y), 3)):
                via.GetNetname()
                for via in board.GetTracks()
                if via.Type() == pcbnew.PCB_VIA_T}
    fill_zones(board)
    target = BOARD_PATH if path is None else path
    pcbnew.SaveBoard(target, board)
    _verify(target, intended)
    if path is None:
        _build.write_project()
    return target


def write_placement_board(path):
    board, _ = build(with_copper=False)
    pcbnew.SaveBoard(path, board)
    return path


if __name__ == "__main__":
    sys.stdout.write(write() + "\n")
