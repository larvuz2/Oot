#!/usr/bin/env python3
"""How much work a room asks of the emulator every frame, to compare the Ancient Plateau with the game's own areas.

Walks each room-shape entry's display lists (following calls into other lists) and counts what an HLE emulator
does for them: vertices transformed, triangles, texture loads, render-mode changes (each one ends a batch of
triangles on the host GPU), matrix loads. Everything in the room is counted (the game culls entries outside the
view, so a frame draws part of it). Actors are not counted, only listed.

    python3 tools/remix/frame_cost.py --version ntsc-1.2           # the Plateau (built) and some of the game's areas
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from extracted_scene import Field, commands, parse_vertex  # noqa: E402

AREAS = {
    "Hyrule Field": "assets/scenes/overworld/spot00",
    "Kakariko Village": "assets/scenes/overworld/spot01",
    "Kokiri Forest": "assets/scenes/overworld/spot04",
    "Lon Lon Ranch": "assets/scenes/overworld/spot20",
    "Lake Hylia": "assets/scenes/overworld/spot06",
}
KEEP = ["assets/objects/gameplay_field_keep", "assets/objects/gameplay_keep"]
GFX_RE = re.compile(r"\bGfx\s+(\w+)\s*\[[^\]]*\]\s*=\s*\{(.*?)\n\};", re.S)
INCLUDE_RE = re.compile(r'#include\s+"([^"]+)"')
STATE = ("gsDPSetOtherMode", "gsDPSetRenderMode", "gsDPSetCombine", "gsSPLoadGeometryMode", "gsSPSetGeometryMode",
         "gsSPClearGeometryMode", "gsSPGeometryMode")


class Lists:
    """Display lists by symbol, from C files (bodies may #include other files) and extracted folders."""

    def __init__(self, roots):
        self.roots = roots
        self.body = {}

    def add_c(self, path: Path):
        text = path.read_text(errors="replace")
        for m in INCLUDE_RE.finditer(text):  # included C (the town, the glowing bush)
            p = self.find(m.group(1))
            if p and p.suffix == ".c" and not p.name.endswith(".rgba16.inc.c") and "Gfx " in p.read_text(errors="replace")[:20000]:
                self.add_c(p)
        for name, body in GFX_RE.findall(text):
            inc = INCLUDE_RE.search(body)
            self.body[name] = (self.find(inc.group(1)).read_text() if inc and self.find(inc.group(1)) else body)

    def add_field(self, field: Field):
        for sym in field.of_type("Gfx"):
            self.body.setdefault(sym, field.text(sym))

    def find(self, rel):
        for r in self.roots:
            if (r / rel).is_file():
                return r / rel
        return None


def walk(lists: Lists, sym, cost, depth=0):
    if depth > 12 or sym not in lists.body:
        if depth > 0 and sym not in lists.body:
            cost["unknown calls"] = cost.get("unknown calls", 0) + 1
        return
    for line in commands(lists.body[sym]):
        name = line[: line.index("(")]
        args = line[line.index("(") + 1 : -1]
        if name in ("gsSPDisplayList", "gsSPBranchList"):
            walk(lists, args.strip().lstrip("&"), cost, depth + 1)
            if name == "gsSPBranchList":
                return
        elif name == "gsSPVertex":
            v = parse_vertex(args)
            cost["vertices"] += v[2] if v else 0
        elif name == "gsSP2Triangles":
            cost["triangles"] += 2
        elif name in ("gsSP1Triangle",):
            cost["triangles"] += 1
        elif name == "gsSP1Quadrangle":
            cost["triangles"] += 2
        elif name.startswith(("gsDPLoadTextureBlock", "gsDPLoadMultiBlock", "gsDPLoadTLUT")):
            cost["texture loads"] += 1
        elif name.startswith(STATE):
            cost["state changes"] += 1
        elif name == "gsSPMatrix":
            cost["matrices"] += 1


def cost_of(lists, entries):
    cost = dict(entries=len(entries), vertices=0, triangles=0, **{"texture loads": 0, "state changes": 0, "matrices": 0})
    for opa, xlu in entries:
        for dl in (opa, xlu):
            if dl and dl != "NULL":
                walk(lists, dl, cost)
    return cost


def own_entries(room_c: Path, town_entries: Path | None):
    text = room_c.read_text()
    block = text.split("RoomShapeEntries[] = {", 1)[1].split("};", 1)[0]
    if town_entries and town_entries.is_file():
        block += town_entries.read_text()
    return re.findall(r"\{\s*\{[^}]*\},\s*\d+,\s*(\w+),\s*(\w+)\s*\}", block)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="ntsc-1.2")
    args = ap.parse_args()
    ext = REPO / "extracted" / args.version
    build = REPO / "build" / args.version
    roots = [build, REPO, ext]
    rows = []

    keep = Lists(roots)
    for k in KEEP:
        if (ext / k).is_dir():
            keep.add_field(Field(ext, ext / k))

    lists = Lists(roots)
    lists.body.update(keep.body)
    lists.add_c(REPO / "assets/scenes/remix/ancient/ancient_room_0.c")
    town = build / "assets/scenes/remix/ancient/ancient_town_room.inc.c"
    if town.is_file():
        lists.add_c(town)
    glow = build / "assets/scenes/remix/ancient/glow_bush.inc.c"
    if glow.is_file():
        lists.add_c(glow)
    entries = own_entries(REPO / "assets/scenes/remix/ancient/ancient_room_0.c",
                          build / "assets/scenes/remix/ancient/ancient_town_entries.inc.c")
    rows.append(("Ancient Plateau (whole room)", cost_of(lists, entries)))
    decor = [(o, x) for o, x in entries if "decor" in o]
    rows.append(("  of which: bushes, flowers, stones", cost_of(lists, decor)))
    town_e = [(o, x) for o, x in entries if "town" in o]
    rows.append(("  of which: town buildings", cost_of(lists, town_e)))
    terrain = [(o, x) for o, x in entries if "terrain" in o]
    rows.append(("  of which: terrain", cost_of(lists, terrain)))

    for name, rel in AREAS.items():
        if not (ext / rel).is_dir():
            continue
        field = Field(ext, ext / rel)
        lists = Lists(roots)
        lists.body.update(keep.body)
        lists.add_field(field)
        for room in field.rooms():
            ents = [(e["opa"], e["xlu"]) for e in field.room_entries(room)]
            rows.append((f"{name} ({room})", cost_of(lists, ents)))

    keys = ["entries", "vertices", "triangles", "texture loads", "state changes", "matrices", "unknown calls"]
    print("frame-cost: " + " | ".join(["area"] + keys))
    for name, c in rows:
        print("frame-cost: " + " | ".join([name] + [str(c.get(k, 0)) for k in keys]))


if __name__ == "__main__":
    main()
