"""Routing: the search draws ordinary connectivity, nothing else.

Five nets are withheld from it. The reference is poured on both layers and
tied together on a declared grid, so which copper a return uses is a
property of the pour rather than of a search. The two data conductors are
generated: their launch geometry follows from the receptacle's own land
order, their two layer changes are forced by that order, and the rest is two
conductors held at a fixed separation over an uninterrupted plane. The two
sink terminations are generated for a blunter reason: their lands sit
between a no-connect land and the pair, in a gap the search cannot fit a
conductor through at the clearance it works to, and its answer to that was
to rip up the pair. What is left is ordinary signal and supply
connectivity, and that is what the router is for.

A candidate is judged, not trusted: it is adopted, the board is measured, and
if it does not come back clean the placed board is restored so no failing
copper stays in the tree.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew

from . import build, layout, netlist

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tooling", "PCBA_AutoDesignAndTest"))

from pcbqa import routing_record  # noqa: E402

REPO_ROOT = layout.REPO_ROOT
CANDIDATE_ROOT = os.path.join(REPO_ROOT, "candidates")
CANDIDATE_NAME = "route-current"
PROVENANCE_PATH = os.path.join(REPO_ROOT, "generated", "routing.json")

#: Nets the search may not draw, and the copper that already carries them.
RESERVED_NETS = ("GND", "USB_DP", "USB_DM", "USB_CC1", "USB_CC2")


def routed_nets():
    return tuple(sorted(name for name in netlist.NETS
                        if name not in RESERVED_NETS))


#: The router is given a wider clearance than the rule the board is judged by.
#: It takes the figure from the project's Default net class, and its diagonal
#: segments then land short of it, so the candidate is routed against a
#: project carrying this margin and judged against the authoritative one,
#: which `_adopt` restores.
ROUTER_CLEARANCE_MM = 0.30

ROUTER_OPTIONS = (
    "--track-width", str(layout.TRACK_WIDTH_MM),
    "--clearance", str(ROUTER_CLEARANCE_MM),
    "--via-size", str(layout.VIA_DIAMETER_MM),
    "--via-drill", str(layout.VIA_DRILL_MM),
    "--board-edge-clearance", "0.45",
    "--hole-to-hole-clearance", "0.3",
    "--same-net-pad-clearance", "0.3",
    "--no-power-tap-neckdown",
    # The copper this repository generates is the input file's own, and it
    # is the part of the board that had no search freedom to begin with:
    # the pair's launch, its two forced layer changes, the suppressor's
    # connections, the bridge's thermal escape and the stitching between
    # the pours. Without this the router's own cleanup passes treat that
    # copper as theirs to prune, and the first run did exactly that.
    "--keep-input-copper",
)

# The router is deterministic for a fixed input, so a bare retry explores
# nothing. Each attempt varies the net-ordering strategy instead, which is
# what actually produces a different candidate.
#: The search is repeated over the same orderings because the router is not
#: deterministic: the same board and the same ordering can come back with a
#: different set of vias, and a candidate carrying one sub-clearance item is
#: rejected rather than patched. Each repeat is a distinct candidate, and
#: every one of them is recorded whether it was accepted or not.
ATTEMPT_ORDERINGS = ("inside_out", "original", "mps") * 3
MAX_ATTEMPTS = len(ATTEMPT_ORDERINGS)

#: A track end is pulled onto a via's centre only when it already stands on
#: that via's own copper. A larger reach would move copper the clearance
#: check has already accepted; this one cannot, because the destination is
#: inside the annulus the end is already touching.
SNAP_WITHIN_VIA = True
#: The shortest track fragment the board accepts away from a pad or a via.
#: A router turning a diagonal lands it as a staircase of pieces far below
#: this; each one is a manufacturing risk rather than a connection, so the
#: pieces are collapsed into their neighbours.
MIN_SEGMENT_MM = 0.1
TOUCH_TOLERANCE_MM = 0.01


def _krt():
    from pcbqa import krt
    return krt


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _summary(text):
    for line in text.splitlines():
        if line.strip().startswith("JSON_SUMMARY_MIN:"):
            return json.loads(line.split("JSON_SUMMARY_MIN:", 1)[1])
    return {}


def _write_routing_project(path):
    """The project the router sees: the design's, with the clearance margin."""
    document = build.project_document(
        str(build.schematic._uuid("sheet", netlist.PROJECT_NAME)))
    document["board"]["design_settings"]["rules"]["min_clearance"] = \
        ROUTER_CLEARANCE_MM
    for entry in document["net_settings"]["classes"]:
        if entry["name"] == "Default":
            entry["clearance"] = ROUTER_CLEARANCE_MM
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(document, handle, indent=2)
        handle.write("\n")
    return path


#: The router carries its own fab-capability floor and is free to escalate
#: below the nominal clearance to fit tight geometry, recording the tighter
#: value so the board is graded against it. This board is graded against its
#: own declared constraints instead, so the router is given those constraints
#: as its floor: copper it emits is then legal by the same rule the checker
#: applies, rather than legal only against a floor the router lowered.
def _write_fab_floor(path):
    floors = (("clearance", build.DESIGN_RULES["min_clearance"]),
              ("track_width", build.DESIGN_RULES["min_track_width"]),
              ("via_diameter", layout.VIA_DIAMETER_MM),
              ("via_drill", layout.VIA_DRILL_MM),
              ("hole_to_hole", build.DESIGN_RULES["min_hole_to_hole"]),
              ("board_edge", build.DESIGN_RULES["min_copper_edge_clearance"]))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# generated from the board's declared constraints\n")
        for key, value in floors:
            handle.write("%s = %s\n" % (key, value))
    return path


def _route_once(resolved, candidate, attempt, placed_pcb):
    stage_dir = os.path.join(candidate, "attempt-%02d" % attempt)
    os.makedirs(stage_dir, exist_ok=True)
    source_pcb = os.path.join(stage_dir, "source.kicad_pcb")
    shutil.copy(placed_pcb, source_pcb)
    _write_routing_project(os.path.join(stage_dir, "source.kicad_pro"))
    routed_pcb = os.path.join(stage_dir, "routed.kicad_pcb")
    floor = _write_fab_floor(os.path.join(stage_dir, "fab-floor.txt"))
    command = [sys.executable,
               os.path.join(resolved["path"], "py_router", "route.py"),
               source_pcb, "--output", routed_pcb, "--nets"] \
        + list(routed_nets()) + list(ROUTER_OPTIONS) \
        + ["--fab-overrides", floor,
           "--ordering", ATTEMPT_ORDERINGS[attempt - 1]]
    completed = subprocess.run(command, capture_output=True, text=True)
    summary = _summary(completed.stdout)
    if completed.returncode != 0:
        raise RuntimeError("routing failed: rc=%s summary=%s stderr=%s"
                           % (completed.returncode, summary,
                              completed.stderr[-2000:]))
    tidied_pcb = os.path.join(stage_dir, "tidied.kicad_pcb")
    shutil.copy(routed_pcb, tidied_pcb)
    transform = tidy(tidied_pcb, _source_via_positions(placed_pcb))
    return {
        "attempt": attempt,
        "source_sha256": digest(source_pcb),
        "accepted": False,
        "stages": [
            {"stage": "routed", "produced_by": "router",
             "sha256": digest(routed_pcb)},
            {"stage": "tidied", "produced_by": "transform",
             "sha256": digest(tidied_pcb),
             "transform": "snap a track end standing on a same-net via onto that via's centre; "
                          "pull a track end that stopped inside a same-net "
                          "pad's outline onto that pad's anchor; "
                          "drop tracks the snap collapsed to a point; "
                          "restore the declared width on any track and the "
                          "declared size on any via the search narrowed "
                          "below them; prune dangling track ends and any "
                          "via the search added and left copper on only one "
                          "layer of, never one the design source placed, "
                          "keeping any removal only while connectivity is "
                          "unchanged; refill the zones so the pours are "
                          "knocked out around the copper the router added",
             "effects": transform,
             "parameters": {"snap_within_via_annulus": SNAP_WITHIN_VIA,
                            "touch_tolerance_mm": TOUCH_TOLERANCE_MM}},
        ],
        "context": {"router_summary": summary,
                    "ordering": ATTEMPT_ORDERINGS[attempt - 1]},
        "board": tidied_pcb,
    }


def measure(path):
    """What the board says about itself: violations, and what is still open."""
    report = os.path.join(CANDIDATE_ROOT, CANDIDATE_NAME, "adopted-drc.json")
    os.makedirs(os.path.dirname(report), exist_ok=True)
    completed = subprocess.run(
        ["kicad-cli", "pcb", "drc", "--output", report, "--format", "json",
         "--severity-error", "--severity-warning", path],
        capture_output=True, text=True)
    if completed.returncode != 0 and not os.path.isfile(report):
        raise RuntimeError("DRC did not run: " + completed.stderr[-2000:])
    with open(report, encoding="utf-8") as handle:
        document = json.load(handle)
    counted = document.get("violations") or []
    return {
        "errors": sum(1 for entry in counted
                      if entry.get("severity") == "error"),
        "warnings": sum(1 for entry in counted
                        if entry.get("severity") != "error"),
        "unconnected": len(document.get("unconnected_items") or []),
        "schematic_parity": len(document.get("schematic_parity") or []),
    }


def _accepts(metrics):
    """What a candidate has to be before it replaces the board in the tree.

    Everything the board's own severities call a finding, because the gate
    that judges the routed board counts warnings too: a candidate that leaves
    one is a candidate the release would reject.
    """
    return (metrics["errors"] == 0 and metrics["warnings"] == 0
            and metrics["unconnected"] == 0
            and metrics["schematic_parity"] == 0)


def _write_record(placed_pcb, attempts, accepted, krt, resolved):
    record = {
        "kind": routing_record.KIND,
        "source_sha256": digest(placed_pcb),
        "attempts": attempts,
        "accepted_attempt": accepted["attempt"] if accepted else None,
        "adopted_sha256": (digest(layout.BOARD_PATH) if accepted else None),
        "context": {
            "router": krt.provenance(resolved["path"], sys.executable),
            "resolution": resolved,
            "routed_nets": list(routed_nets()),
            "reserved_nets": list(RESERVED_NETS),
            "options": list(ROUTER_OPTIONS),
            "acceptance": "a candidate is adopted only when a fresh DRC over "
                          "the adopted board reports no violation, nothing "
                          "unconnected and no disagreement with the "
                          "schematic",
            "reproducibility": "the router is not bit-reproducible; "
                               "candidates are generated until one is "
                               "accepted and every attempt is recorded here",
        },
    }
    routing_record.validate(record)
    os.makedirs(os.path.dirname(PROVENANCE_PATH), exist_ok=True)
    with open(PROVENANCE_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    return record


def _adopt(candidate_board):
    """Install a candidate, then rewrite everything derived from the board.

    The router writes its own project file beside the candidate - loosening a
    track width, pinning an edge clearance, silencing severities - so the
    authoritative project is regenerated from the design source rather than
    inherited from whatever the search left behind.
    """
    shutil.copy(candidate_board, layout.BOARD_PATH)
    build.write_project()


def run():
    krt = _krt()
    resolved = krt.resolve()
    candidate = os.path.join(CANDIDATE_ROOT, CANDIDATE_NAME)
    shutil.rmtree(candidate, ignore_errors=True)
    os.makedirs(candidate, exist_ok=True)
    layout.write()
    placed_pcb = os.path.join(candidate, "placed.kicad_pcb")
    shutil.copy(layout.BOARD_PATH, placed_pcb)

    attempts = []
    accepted = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = _route_once(resolved, candidate, attempt, placed_pcb)
        entry = {key: value for key, value in result.items() if key != "board"}
        _adopt(result["board"])
        metrics = measure(layout.BOARD_PATH)
        entry["context"]["adopted_metrics"] = metrics
        entry["accepted"] = _accepts(metrics)
        _write_record(placed_pcb, attempts + [entry],
                      entry if entry["accepted"] else None, krt, resolved)
        attempts.append(entry)
        if entry["accepted"]:
            accepted = entry
            break

    if accepted is None:
        _adopt(placed_pcb)
        _write_record(placed_pcb, attempts, None, krt, resolved)
        raise RuntimeError(
            "no routing candidate was accepted in %d attempts; the placed, "
            "unrouted board has been restored so no failing copper stays in "
            "the tree" % MAX_ATTEMPTS)
    return layout.BOARD_PATH, PROVENANCE_PATH


def _endpoints(track):
    return (track.GetStart(), track.GetEnd())


def _supported(point, track, board, vias, tracks, epsilon):
    for via in vias:
        if via.GetNetCode() != track.GetNetCode():
            continue
        if not via.IsOnLayer(track.GetLayer()):
            continue
        centre = via.GetPosition()
        if math.hypot(point.x - centre.x, point.y - centre.y) <= epsilon:
            return True
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetCode() != track.GetNetCode():
                continue
            # A pad only holds a track end up on a layer it is actually on:
            # an SMD pad on the far side is not a connection, and treating it
            # as one used to leave the end dangling for the checker to find.
            if not pad.IsOnLayer(track.GetLayer()):
                continue
            if pad.HitTest(point, 0):
                return True
    for other in tracks:
        if other.m_Uuid.AsString() == track.m_Uuid.AsString():
            continue
        if other.GetNetCode() != track.GetNetCode():
            continue
        if other.Type() == pcbnew.PCB_VIA_T:
            continue
        if other.GetLayer() != track.GetLayer():
            continue
        if other.HitTest(point, int(epsilon)):
            return True
    return False


def _entry_geometry(track, board, vias):
    """True when an end of the track sits on a via or in a pad: copper that
    short is how a route enters one, not a route in its own right."""
    for point in _endpoints(track):
        for via in vias:
            centre = via.GetPosition()
            if math.hypot(point.x - centre.x, point.y - centre.y) \
                    <= via.GetWidth(pcbnew.F_Cu) / 2:
                return True
        for footprint in board.GetFootprints():
            for pad in footprint.Pads():
                if pad.IsOnLayer(track.GetLayer()) and pad.HitTest(point, 0):
                    return True
    return False


def _absorption(fragment, board, vias, tracks, epsilon):
    """The one neighbour a fragment can be folded into, or None.

    A fold is only offered where exactly one same-net track on the same layer
    meets the fragment at that end and no via or pad stands there, so a
    junction and a terminal are both left alone."""
    for point, other in ((fragment.GetStart(), fragment.GetEnd()),
                         (fragment.GetEnd(), fragment.GetStart())):
        for via in vias:
            centre = via.GetPosition()
            if math.hypot(point.x - centre.x, point.y - centre.y) <= epsilon:
                break
        else:
            touching = []
            for candidate in tracks:
                if candidate.m_Uuid.AsString() == fragment.m_Uuid.AsString():
                    continue
                if candidate.GetNetCode() != fragment.GetNetCode():
                    continue
                if candidate.GetLayer() != fragment.GetLayer():
                    continue
                for get, set_ in ((candidate.GetStart, candidate.SetStart),
                                  (candidate.GetEnd, candidate.SetEnd)):
                    end = get()
                    if math.hypot(end.x - point.x, end.y - point.y) <= epsilon:
                        touching.append((candidate, set_, end))
            if len(touching) == 1:
                candidate, set_, end = touching[0]
                return (fragment, candidate, set_, end, other)
    return None


def _unconnected(board):
    """How many connections the board is still missing.

    Rebuilt each time it is asked for, because every caller has just changed
    the copper. KiCad's binding hands the connectivity back as a shared
    pointer that SWIG sometimes leaves unwrapped, so the unwrapped form is
    called through the class when the attribute is not on the instance - the
    same C++ method either way.
    """
    board.BuildConnectivity()
    data = board.GetConnectivity()
    if hasattr(data, "GetUnconnectedCount"):
        return data.GetUnconnectedCount(True)
    return pcbnew.CONNECTIVITY_DATA.GetUnconnectedCount(data, True)


def _vias(board):
    return [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]


def _segments(board):
    return [t for t in board.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]


def _snap_to_vias(path):
    """A track end standing on a same-net via's copper goes to its centre."""
    board = pcbnew.LoadBoard(path)
    epsilon = pcbnew.FromMM(TOUCH_TOLERANCE_MM)
    snapped = 0
    for _ in range(4):
        vias = _vias(board)
        moved = 0
        for track in _segments(board):
            for get, set_ in ((track.GetStart, track.SetStart),
                              (track.GetEnd, track.SetEnd)):
                point = get()
                for via in vias:
                    if via.GetNetCode() != track.GetNetCode():
                        continue
                    centre = via.GetPosition()
                    distance = math.hypot(point.x - centre.x,
                                          point.y - centre.y)
                    if epsilon < distance <= via.GetWidth(pcbnew.F_Cu) / 2:
                        set_(centre)
                        moved += 1
                        break
        snapped += moved
        if not moved:
            break
    pcbnew.SaveBoard(path, board)
    return {"endpoints_snapped": snapped}


def _snap_to_pads(path):
    """A track end inside a pad's outline but off the shape the pad presents
    - the cut corner of a rounded rectangle - reads as connected to the
    board's connectivity and as a bare end to anything that asks what copper
    touches it. It is pulled to the pad anchor, the one point on a pad every
    reader agrees is on it."""
    board = pcbnew.LoadBoard(path)
    epsilon = pcbnew.FromMM(TOUCH_TOLERANCE_MM)
    vias, tracks = _vias(board), _segments(board)
    snapped = 0
    for track in tracks:
        for get, set_ in ((track.GetStart, track.SetStart),
                          (track.GetEnd, track.SetEnd)):
            point = get()
            if _supported(point, track, board, vias, tracks, epsilon):
                continue
            for footprint in board.GetFootprints():
                for pad in footprint.Pads():
                    if pad.GetNetCode() != track.GetNetCode():
                        continue
                    if not pad.IsOnLayer(track.GetLayer()):
                        continue
                    if not pad.GetBoundingBox().Contains(point):
                        continue
                    set_(pad.GetPosition())
                    snapped += 1
                    break
                else:
                    continue
                break
    pcbnew.SaveBoard(path, board)
    return {"endpoints_snapped_to_pads": snapped}


#: Removing an item from a board hands its ownership to Python. Letting the
#: last reference go while the board still holds pointers into it is what
#: turns the binding's own board object into an unwrapped pointer a dozen
#: operations later, so every removal is held until the board is written.
_DETACHED = []


def _detach(board, item):
    board.Remove(item)
    _DETACHED.append(item)


def _drop_degenerate(path):
    """Snapping can leave a track whose two ends became the same point. It
    connects nothing and DRC reports it crossing whatever it lies on."""
    board = pcbnew.LoadBoard(path)
    removed = 0
    for track in _segments(board):
        if track.GetLength() == 0:
            _detach(board, track)
            removed += 1
    pcbnew.SaveBoard(path, board)
    return {"collapsed_tracks_removed": removed}


def _absorb_fragments(path):
    """The router cuts a corner with a chamfer a few tens of microns long.
    Copper that short is below anything the fab resolves and reads as a
    fragment rather than as a route, so each one is folded into the
    neighbour it meets - only where a single neighbour meets it away from
    any pad or via, so a junction is never collapsed, and only while
    connectivity is unchanged."""
    keep = set()
    absorbed = 0
    while True:
        board = pcbnew.LoadBoard(path)
        baseline = _unconnected(board)
        vias, tracks = _vias(board), _segments(board)
        move = None
        for track in tracks:
            if track.m_Uuid.AsString() in keep:
                continue
            if track.GetLength() >= pcbnew.FromMM(MIN_SEGMENT_MM):
                continue
            if _entry_geometry(track, board, vias):
                continue
            move = _absorption(track, board, vias, tracks,
                               pcbnew.FromMM(TOUCH_TOLERANCE_MM))
            if move is not None:
                break
            keep.add(track.m_Uuid.AsString())
        if move is None:
            return {"fragments_absorbed": absorbed}
        fragment, _neighbour, setter, _previous, target = move
        uuid = fragment.m_Uuid.AsString()
        setter(target)
        _detach(board, fragment)
        if _unconnected(board) > baseline:
            keep.add(uuid)
            continue
        pcbnew.SaveBoard(path, board)
        absorbed += 1


def _restore_declared_geometry(path):
    """The search falls back to a five-mil track and a narrowed via where it
    cannot fit what it was given. Both are below what this board declares,
    so both are brought back to the declared figure - the track to the floor
    rather than to the net class's width, because widening to a preference
    would move copper the clearance check has already accepted."""
    board = pcbnew.LoadBoard(path)
    floor = pcbnew.FromMM(build.DESIGN_RULES["min_track_width"])
    widened = 0
    for track in _segments(board):
        if track.GetWidth() >= floor:
            continue
        track.SetWidth(floor)
        widened += 1
    resized = 0
    for item in _vias(board):
        if item.GetWidth(pcbnew.F_Cu) >= pcbnew.FromMM(layout.VIA_DIAMETER_MM) \
                and item.GetDrill() >= pcbnew.FromMM(layout.VIA_DRILL_MM):
            continue
        item.SetWidth(pcbnew.F_Cu, pcbnew.FromMM(layout.VIA_DIAMETER_MM))
        item.SetDrill(pcbnew.FromMM(layout.VIA_DRILL_MM))
        resized += 1
    pcbnew.SaveBoard(path, board)
    return {"narrow_tracks_widened": widened,
            "undersized_vias_restored": resized}


def _trim_dangling_ends(path):
    """Shorten a track whose end hangs past where something joined it.

    The design source draws the bridge's escapes out to a fanout pitch a
    search can work at, and the search joins one wherever it likes along
    it. What is left past that point is copper connecting nothing. It is
    not pruned - removing the track would take the pad's only connection
    with it - so the end is pulled back to the furthest point on the track
    that something else actually touches.
    """
    trimmed = 0
    seen = set()
    while True:
        board = pcbnew.LoadBoard(path)
        baseline = _unconnected(board)
        epsilon = pcbnew.FromMM(TOUCH_TOLERANCE_MM)
        vias, tracks = _vias(board), _segments(board)
        move = None
        for track in tracks:
            key = track.m_Uuid.AsString()
            if key in seen:
                continue
            for get, set_ in ((track.GetStart, track.SetStart),
                              (track.GetEnd, track.SetEnd)):
                point = get()
                if _supported(point, track, board, vias, tracks, epsilon):
                    continue
                other = track.GetEnd() if get is track.GetStart \
                    else track.GetStart()
                joint = _furthest_joint(track, other, board, vias, tracks,
                                        epsilon)
                if joint is not None:
                    move = (track, key, set_, point, joint)
                    break
            if move is not None:
                break
            seen.add(key)
        if move is None:
            return {"dangling_ends_trimmed": trimmed}
        track, key, set_, previous, joint = move
        set_(joint)
        if _unconnected(board) > baseline:
            set_(previous)
            seen.add(key)
            continue
        seen.add(key)
        pcbnew.SaveBoard(path, board)
        trimmed += 1


def _furthest_joint(track, anchor, board, vias, tracks, epsilon):
    """The point on a track nearest its loose end that something touches."""
    start, end = track.GetStart(), track.GetEnd()
    length = math.hypot(end.x - start.x, end.y - start.y)
    if length <= epsilon:
        return None
    best = None
    candidates = [via.GetPosition() for via in vias
                  if via.GetNetCode() == track.GetNetCode()]
    for other in tracks:
        if other.m_Uuid.AsString() == track.m_Uuid.AsString():
            continue
        if other.GetNetCode() != track.GetNetCode():
            continue
        if other.GetLayer() != track.GetLayer():
            continue
        candidates.extend(_endpoints(other))
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetCode() != track.GetNetCode():
                continue
            if pad.IsOnLayer(track.GetLayer()):
                candidates.append(pad.GetPosition())
    for point in candidates:
        if not track.HitTest(point, int(epsilon)):
            continue
        distance = math.hypot(point.x - anchor.x, point.y - anchor.y)
        if distance <= epsilon or distance >= length - epsilon:
            continue
        if best is None or distance > best[0]:
            best = (distance, point)
    return None if best is None else best[1]


def _prune_dangling(path):
    """Remove what the router left unattached. A track whose removal would
    break the net is kept and skipped rather than ending the pass, because
    one such track used to hide every dangling end behind it."""
    keep = set()
    removed = 0
    while True:
        board = pcbnew.LoadBoard(path)
        baseline = _unconnected(board)
        epsilon = pcbnew.FromMM(TOUCH_TOLERANCE_MM)
        vias, tracks = _vias(board), _segments(board)
        victim = None
        for track in tracks:
            if track.m_Uuid.AsString() in keep:
                continue
            if all(_supported(point, track, board, vias, tracks, epsilon)
                   for point in _endpoints(track)):
                continue
            victim = track
            break
        if victim is None:
            return {"dangling_tracks_removed": removed}
        uuid = victim.m_Uuid.AsString()
        _detach(board, victim)
        if _unconnected(board) > baseline:
            keep.add(uuid)
            continue
        pcbnew.SaveBoard(path, board)
        removed += 1


def _source_via_positions(placed_pcb):
    """Where the design source's own vias are.

    The placed board is exactly the copper this repository generates, so its
    vias are the ones a search may not touch: the two orientation links, the
    suppressor's own connections, the bridge's thermal escapes and the grid
    that ties the two ground pours together. A stitch has no track on it by
    construction, so without this set a pass that pruned vias with nothing
    attached would prune every one of them.
    """
    board = pcbnew.LoadBoard(placed_pcb)
    return {(round(pcbnew.ToMM(via.GetPosition().x), 4),
             round(pcbnew.ToMM(via.GetPosition().y), 4))
            for via in _vias(board)}


def _prune_router_vias(path, source_vias):
    """Remove a via the search added and then left with copper on one layer.

    A via the design source placed is never a candidate, whatever is on it.
    A via the search added is one only when removing it costs no connection,
    which is what the trial answers.
    """
    keep = set()
    removed = 0
    while True:
        board = pcbnew.LoadBoard(path)
        baseline = _unconnected(board)
        epsilon = pcbnew.FromMM(TOUCH_TOLERANCE_MM)
        segments = _segments(board)
        victim = None
        for via in _vias(board):
            key = (round(pcbnew.ToMM(via.GetPosition().x), 4),
                   round(pcbnew.ToMM(via.GetPosition().y), 4))
            if key in source_vias or key in keep:
                continue
            layers = set()
            for track in segments:
                if track.GetNetCode() != via.GetNetCode():
                    continue
                for point in _endpoints(track):
                    if math.hypot(point.x - via.GetPosition().x,
                                  point.y - via.GetPosition().y) <= epsilon:
                        layers.add(track.GetLayer())
            if len(layers) >= 2:
                continue
            victim = (via, key)
            break
        if victim is None:
            return {"router_vias_removed": removed}
        via, key = victim
        _detach(board, via)
        if _unconnected(board) > baseline:
            keep.add(key)
            continue
        pcbnew.SaveBoard(path, board)
        removed += 1


def _refill(path):
    """The router adds copper the pours were not knocked out around, so the
    fill is recomputed rather than left describing earlier copper."""
    board = pcbnew.LoadBoard(path)
    layout.fill_zones(board)
    pcbnew.SaveBoard(path, board)
    return {"zones_refilled": len(list(board.Zones()))}


#: Each transform reloads the board it works on and saves it again.
#:
#: Not for tidiness: KiCad's Python bindings degrade after enough removals
#: and re-additions on one board object, and hand back the board itself as
#: an unwrapped pointer that nothing can iterate. A transform that reloads
#: cannot accumulate that state, and the trial-and-revert passes keep what
#: they have decided in a set of UUIDs, which survive a save and a load.
TRANSFORMS = (_snap_to_vias, _snap_to_pads, _drop_degenerate,
              _absorb_fragments, _restore_declared_geometry,
              _trim_dangling_ends, _prune_dangling, _refill)


def tidy(path, source_vias=frozenset()):
    effects = {}
    for transform in TRANSFORMS:
        if transform is _prune_dangling:
            effects.update(_prune_router_vias(path, source_vias))
        effects.update(transform(path))
    return effects


if __name__ == "__main__":
    for path in run():
        sys.stdout.write(path + "\n")
