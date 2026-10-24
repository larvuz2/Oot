#!/usr/bin/env python3
"""Generate the Shrine of the Upside-Down Wind (Web Remix level 8): Ocarina of Time x Breath of the Wild, a physics
and time-travel puzzle. You build a machine that works in reverse. One chamber with two floors, the ground and the
ceiling: the exit is on the ceiling right above the entrance, and no stairs lead up.

  The pieces (En_Remix_Wind, tools/remix/make_wind_parts.py): two fans (the floor's blowing up, the ceiling's down,
  one column of wind between them), three iron cubes of different sizes and weights (Magnesis is lent), a ceiling
  switch for the heavy cube and one under the ceiling fan, a crystal that turns the wind (blue: up, orange: down), a
  timed switch that turns gravity upside down for eight seconds for every loose object (not for Link), a ladder up to
  the middle balcony, a final ladder hanging from the exit platform, and the Master Sword's pedestal (En_Remix_Years:
  place the sword to be a child, draw it to be an adult).

  1. The light cube dances in the wind and falls back when it leaves it. The heavy cube is too heavy for the wind.
  2. The timed switch: the heavy cube falls up against its ceiling switch, the gate before the first ladder opens;
     eight seconds later the cube falls and the gate closes.
  3. The medium cube into the bracket beside the switch (it falls up into it): the heavy cube is wedged against the
     switch and stays, the gate stays open. Climb to the middle balcony.
  4. The balcony's crystal turns the wind: a cube high in the column is pulled up against the ceiling fan, the second
     ceiling switch.
  5. Both switches pressed at once: the final ladder comes down from the exit platform but stops short. Ride the
     dancing cube up to it (only the child is light enough: the pedestal), climb to the exit.
  The hidden treasure: a glass chamber halfway up the wall with a narrow hole in its floor. The smallest cube under
  it, gravity upside down: it falls up through the hole against the shelf inside, its crystal lights, the glass sinks.

    python3 tools/remix/make_wind_parts.py   # the pieces (and the plan's header) first
    python3 tools/remix/make_wind.py         # writes assets/scenes/remix/wind/ (committed)
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import box as sbox

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_shrine as S  # noqa: E402
from make_shrine import (L, Mat, strip, wall, flat, box, fan, floor_line, wall_line, ring_line,  # noqa: E402
                         rune_panel, FLOOR, WALL, DARK, GLOW, EMBER)
import make_time as MT  # noqa: E402  (shapes: floor_geom, quad_on)
import wind_plan as W  # noqa: E402

REPO = HERE.parents[1]
OUT = REPO / "assets/scenes/remix/wind"
INC = "assets/scenes/remix/wind"
SCENE, ROOM = "wind_scene", "wind_room_0"

TEXTURES = {
    "plaza": ("wind_plaza", "ci4", (64, 64)),
    "techstone": ("wind_techstone", "ci4", (64, 64)),
    "techrock": ("wind_techrock", "ci4", (64, 64)),
    "runes": ("wind_runes", "ci4", (64, 64)),
    "glow": ("wind_glow", "i8", (32, 32)),
    "eye": ("wind_eye", "i8", (64, 64)),
    "water": ("wind_water", "rgba16", (32, 32)),
}

# the wind's own lines: blue while it blows up, orange once turned (z_remix_level.c, segment 0x0B)
WINDM = Mat("wind", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x0B, scroll=True, repeat=150, clamp_t=True)
IRON = Mat("iron", "techrock", "ci4", (64, 64), repeat=160)

SURF_FLOOR, SURF_WALL, SURF_EXIT = range(3)
SURFACES = [("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 1)]

CH = dict(x=0, z=W.Z1 + 360, r=340, h=380)
CH_APO = CH["r"] * math.cos(math.pi / 8)
SPAWN = (0, 330, CH["z"])
PEDESTAL_EXIT = dict(x=0, z=CH["z"] + 200, r=75, h=14)
HALL = dict(x0=W.X0, x1=W.X1, z0=W.Z0, z1=W.Z1, h=W.CEIL)
DAIS = dict(r=90, h=20)

WIND_ACTOR, YEARS_ACTOR = "ACTOR_EN_REMIX_WIND", "ACTOR_EN_REMIX_YEARS"
WIND_CTRL, WIND_CUBE, WIND_FAN, WIND_PLATE, WIND_BRACKET, WIND_TIMER, WIND_LADDER, WIND_GATE = range(8)
YEARS_PEDESTAL, YEARS_TABLET = 0, 6


def wp(kind, arg=0):
    return f"0x{((arg & 0xFF) << 8) | kind:04X}"


def configure():
    L.OUT, L.INC, L.SCENE, L.ROOM = OUT, INC, SCENE, ROOM
    L.TEXTURES = dict(TEXTURES)
    L.ENTRIES.clear()
    L.COL_TRIS.clear()
    L.MESHES.clear()
    sx, sy, sz = W.SPAWN_AT_PEDESTAL
    for k, v in dict(OUT=OUT, INC=INC, SCENE=SCENE, ROOM=ROOM, NAME="Shrine of the Upside-Down Wind",
                     TITLE_STEM="wind_title", TITLE_SYM="gWindShrineTitleCardTex", MEMSIZE_MACRO="WIND_SCENE_BGCHECK_MEMSIZE",
                     MUSIC="NA_BGM_ICE_CAVERN", SURFACES=SURFACES, EXITS=["ENTR_RETURN_GROTTO"], SPAWN=SPAWN,
                     HALL=HALL, CH=CH, CH_APO=CH_APO, PEDESTAL=PEDESTAL_EXIT, OBJECTS=OBJECTS, actors=actors,
                     room_defines=room_defines, EXTRA_ROOM_C=[], EXTRA_ENTRIES=[], WATERBOXES=[],
                     LIGHT_ROW=("{ { 92, 100, 118 }, { 73, 73, 73 }, { 225, 235, 250 }, { -73, -73, -73 }, "
                                "{ 120, 140, 175 }, { 40, 48, 64 }, BLEND_RATE_AND_FOG_NEAR(4, 990), 4800 },\n"),
                     EXTRA_SPAWNS=[(sx, sy, sz, 0x8000), (sx, sy, sz, 0x8000)]).items():
        setattr(S, k, v)


# ---------------------------------------------------------------- textures


def sky_palettes():
    """Pale blue-grey stone, an airy temple; the runes inlaid in sky blue."""
    ramp = {"plaza": ((84, 92, 104), (214, 224, 236)), "techstone": ((96, 104, 118), (206, 216, 230)),
            "techrock": ((52, 58, 70), (150, 160, 178)), "runes": ((90, 98, 112), (214, 222, 234))}
    for key, (lo, hi) in ramp.items():
        path = OUT / f"{TEXTURES[key][0]}.ci4.png"
        img = Image.open(path)
        idx = np.array(img)
        pal = np.array(img.getpalette()[: 16 * 3], float).reshape(-1, 3)
        lum = pal.mean(1, keepdims=True) / 255.0
        lum = (lum - lum.min()) / max(lum.max() - lum.min(), 1e-6)
        new = np.array(lo) + (np.array(hi) - np.array(lo)) * lum
        if key == "runes":
            new[lum[:, 0] > 0.8] = [120, 220, 255]
        L.write_indexed_png(path, idx, np.clip(new, 0, 255).round().astype(np.uint8))


# ---------------------------------------------------------------- shapes


def slab_with_hole(e, x0, x1, z0, z1, y0, y1, hole=None, skip=()):
    """A horizontal slab (top y1 walkable, underside y0 a ceiling), optionally with a square hole (x, z, w)."""
    geom = sbox(x0, z0, x1, z1)
    if hole is not None:
        hx, hz, hw = hole
        geom = geom.difference(sbox(hx - hw / 2, hz - hw / 2, hx + hw / 2, hz + hw / 2))
    MT.floor_geom(e, FLOOR, geom, y1)
    MT.floor_geom(e, DARK, geom, y0, col=SURF_WALL, up=False)
    sides = {"n": ((x1, z0), (x0, z0), (0, 0, -1)), "s": ((x0, z1), (x1, z1), (0, 0, 1)),
             "e": ((x1, z1), (x1, z0), (1, 0, 0)), "w": ((x0, z0), (x0, z1), (-1, 0, 0))}
    for k, (a, b, f) in sides.items():
        if k not in skip:
            wall(e, WALL, a, b, y0, y1, f)
    if hole is not None:
        hx, hz, hw = hole
        a, b = hx - hw / 2, hx + hw / 2
        c, d = hz - hw / 2, hz + hw / 2
        wall(e, IRON, (a, c), (b, c), y0, y1, (0, 0, 1))
        wall(e, IRON, (b, d), (a, d), y0, y1, (0, 0, -1))
        wall(e, IRON, (a, d), (a, c), y0, y1, (1, 0, 0))
        wall(e, IRON, (b, c), (b, d), y0, y1, (-1, 0, 0))


def arrow_up(e, mat, x, z, y, facing, size=60):
    """A chevron on a wall pointing up (the wind's way)."""
    f = np.array(facing, float)
    rt = np.cross((0, 1, 0), f)
    c = np.array([x, y, z]) + f * 1.5
    pts = [tuple(c - rt * size / 2 - (0, size / 3, 0)), tuple(c + (0, size / 3, 0)), tuple(c + rt * size / 2 - (0, size / 3, 0))]
    wall_line(e, mat, pts, tuple(f), width=10)


# ---------------------------------------------------------------- the chamber


def build_floor_and_ceiling():
    e = L.new_entry("floor")
    flat(e, FLOOR, W.X0, W.X1, W.Z0, W.Z1, 0)
    cx, cz = W.COLUMN
    ring_line(e, WINDM, cx, cz, W.FAN_R + 30, 0, n=24, width=10)
    ring_line(e, WINDM, cx, cz, W.FAN_R + 55, 0, n=24, width=6)
    # the marks: under the heavy cube's switch, under the bracket, under the glass room's hole, round the timer
    p = W.PLATE
    ring_line(e, EMBER, p["x"], p["z"], p["w"] / 2 + 6, 0, n=4, width=8)
    bx, _, bz = W.BRACKET
    ring_line(e, EMBER, bx, bz, 44, 0, n=4, width=6)
    ring_line(e, GLOW, W.HOLE["x"], W.HOLE["z"], W.HOLE["w"] / 2 + 4, 0, n=4, width=5)
    ring_line(e, GLOW, W.TIMER[0], W.TIMER[1], 62, 0, n=16, width=8)
    # light lines from the entrance into the room, and along it
    floor_line(e, GLOW, [(0, W.Z1 - 20), (0, 200)], width=12)
    floor_line(e, GLOW, [(0, 200), (cx + W.FAN_R + 60, 200)], width=8)
    for x in (-200, 200, 400):
        floor_line(e, GLOW, [(x, W.Z0 + 40), (x, W.Z1 - 60)], width=6)

    # the second floor: the ceiling
    c = L.new_entry("ceiling")
    flat(c, DARK, W.X0, W.X1, W.Z0, W.Z1, W.CEIL, up=False, col=SURF_WALL)
    for x in (-200, 200, 400):
        strip(c, GLOW, [(x, W.CEIL, W.Z0), (x, W.CEIL, W.Z1)], [(0, -1, 0)] * 2, 14, lift=1.2)
    S_ring = ngon_line(cx, cz, W.FAN_R + 40, W.CEIL)
    strip(c, WINDM, S_ring, [(0, -1, 0)] * len(S_ring), 10, lift=1.2, closed=True)
    # the ceiling switch's frame, the bracket's
    strip(c, EMBER, ngon_line(p["x"], p["z"], p["w"] / 2 + 14, W.CEIL, n=4), [(0, -1, 0)] * 4, 8, lift=1.2, closed=True)


def ngon_line(cx, cz, r, y, n=24):
    return [(cx + r * math.sin(2 * math.pi * k / n + math.pi / n), y, cz + r * math.cos(2 * math.pi * k / n + math.pi / n))
            for k in range(n)]


def build_walls():
    e = L.new_entry("walls")
    X0, X1, Z0, Z1, H = W.X0, W.X1, W.Z0, W.Z1, W.CEIL
    wall(e, WALL, (X0, Z0), (X1, Z0), 0, H, (0, 0, 1))
    wall(e, WALL, (X1, Z1), (X1, Z0), 0, H, (-1, 0, 0))
    wall(e, WALL, (X0, Z0), (X0, Z1), 0, H, (1, 0, 0))
    # south: the arrival arch (build_chamber's corridor comes through it)
    wall(e, WALL, (X1, Z1), (S.ARCH_HALF, Z1), 0, H, (0, 0, -1))
    wall(e, WALL, (-S.ARCH_HALF, Z1), (X0, Z1), 0, H, (0, 0, -1))
    wall(e, WALL, (S.ARCH_HALF, Z1), (-S.ARCH_HALF, Z1), S.ARCH_H, H, (0, 0, -1))
    wall_line(e, GLOW, [(-S.ARCH_HALF - 14, 0, Z1 - 2), (-S.ARCH_HALF - 14, S.ARCH_H + 14, Z1 - 2),
                        (S.ARCH_HALF + 14, S.ARCH_H + 14, Z1 - 2), (S.ARCH_HALF + 14, 0, Z1 - 2)], (0, 0, -1), width=12)
    # bands of light at both floors' heights, rune panels, chevrons pointing up (the wind's way)
    for y in (200, W.EXIT_PLATFORM["top"] + 60):
        wall_line(e, GLOW, [(X1 - 2, y, Z1), (X1 - 2, y, Z0)], (-1, 0, 0), width=10)
        wall_line(e, GLOW, [(X0, y, Z0 + 2), (X1, y, Z0 + 2)], (0, 0, 1), width=10)
    for z in (-450, -150, 150, 450):
        rune_panel(e, (X1 - 1, 380, z), (-1, 0, 0), 100, 100)
    for x in (-300, 0, 300):
        rune_panel(e, (x, 380, Z0 + 1), (0, 0, 1), 100, 100)
    for k, y in enumerate((300, 420, 540)):
        arrow_up(e, WINDM, W.COLUMN[0], Z1 - 1, y, (0, 0, -1), size=70)
    # wind lines from the floor fan up the south wall to the exit platform
    wall_line(e, WINDM, [(-160, 0, Z1 - 2), (-160, W.EXIT_PLATFORM["top"] - 40, Z1 - 2)], (0, 0, -1), width=8)
    wall_line(e, WINDM, [(160, 0, Z1 - 2), (160, W.EXIT_PLATFORM["top"] - 40, Z1 - 2)], (0, 0, -1), width=8)


def build_balcony():
    """The middle balcony (a solid block against the west wall), the jambs of its ladder's gate, the glass room
    north of it."""
    e = L.new_entry("balcony")
    b = W.BALCONY
    box(e, b["x0"], b["x1"], 0, b["top"], b["z0"], b["z1"], top=FLOOR, skip=("w",))
    floor_line(e, GLOW, [(b["x1"] - 14, b["z0"] + 20), (b["x1"] - 14, b["z1"] - 20)], width=8, y=b["top"])
    ring_line(e, WINDM, W.CRYSTAL_FANS[0], W.CRYSTAL_FANS[1], 40, b["top"], n=12, width=6)
    for z in (-250, 250):
        wall_line(e, GLOW, [(b["x1"] + 1, 30, z), (b["x1"] + 1, b["top"] - 30, z)], (1, 0, 0), width=8)
    g, l1 = W.GATE1, W.LADDER1
    for s in (-1, 1):
        z0, z1 = sorted((l1["z"] + s * g["w"] / 2, l1["z"] + s * (g["w"] / 2 + 10)))
        box(e, b["x1"], b["x1"] + 30, 0, b["top"], z0, z1, top=DARK, skip=("w",))
    wall_line(e, EMBER, [(b["x1"] + 31, 0, -g["w"] / 2 - 14), (b["x1"] + 31, b["top"] + 14, -g["w"] / 2 - 14),
                         (b["x1"] + 31, b["top"] + 14, g["w"] / 2 + 14), (b["x1"] + 31, 0, g["w"] / 2 + 14)], (1, 0, 0),
              width=8)

    # the glass room: its floor with the narrow hole (a ceiling under it), its east wall, its roof, the iron shelf
    gr, h = W.GLASS_ROOM, W.HOLE
    r = L.new_entry("glass_room")
    slab_with_hole(r, gr["x0"], gr["x1"], gr["z0"], gr["z1"], gr["floor"] - gr["t"], gr["floor"],
                   hole=(h["x"], h["z"], h["w"]), skip=("w", "n", "s"))
    wall(r, WALL, (gr["x1"], gr["z1"]), (gr["x1"], gr["z0"]), gr["floor"], gr["ceil"] + 20, (1, 0, 0))
    wall(r, WALL, (gr["x1"], gr["z0"]), (gr["x1"], gr["z1"]), gr["floor"], gr["ceil"], (-1, 0, 0))
    flat(r, DARK, gr["x0"], gr["x1"], gr["z0"], gr["z1"], gr["ceil"], up=False, col=SURF_WALL)
    flat(r, WALL, gr["x0"], gr["x1"], gr["z0"], gr["z1"], gr["ceil"] + 20, col=SURF_FLOOR)
    wall(r, WALL, (gr["x0"], gr["z1"]), (gr["x1"], gr["z1"]), gr["ceil"], gr["ceil"] + 20, (0, 0, 1))
    hx, hz = h["x"], h["z"]
    cap, cw = W.GLASS_CAP, h["w"] / 2 + 6
    box(r, hx - cw, hx + cw, cap, cap + 10, hz - cw, hz + cw, top=IRON, side=IRON)
    flat(r, IRON, hx - cw, hx + cw, hz - cw, hz + cw, cap, up=False, col=SURF_WALL)
    for sx in (-1, 1):
        box(r, hx + sx * cw - 3 - (sx > 0) * 0, hx + sx * cw + 3, cap + 10, gr["ceil"], hz - 3, hz + 3, top=IRON,
            side=IRON, col_top=None, col_side=None)
    ring_line(r, GLOW, h["x"], h["z"], h["w"] / 2 + 10, gr["floor"], n=4, width=6)
    # a frame of light round the glass (seen from the balcony)
    wall_line(r, GLOW, [(gr["x0"], gr["floor"], gr["z1"] + 1), (gr["x0"], gr["ceil"] + 10, gr["z1"] + 1),
                        (gr["x1"] + 10, gr["ceil"] + 10, gr["z1"] + 1), (gr["x1"] + 10, gr["floor"], gr["z1"] + 1)],
              (0, 0, 1), width=8)


def build_exit_platform():
    """The exit platform hanging under the ceiling right above the entrance, the way out on it."""
    e = L.new_entry("exit")
    p = W.EXIT_PLATFORM
    slab_with_hole(e, p["x0"], p["x1"], p["z0"], p["z1"], p["top"] - p["t"], p["top"], skip=("s",))
    floor_line(e, GLOW, [(p["x0"] + 20, p["z0"] + 14), (p["x1"] - 20, p["z0"] + 14)], width=8, y=p["top"])
    ex, ez = W.EXIT_RING
    r, ph = 75, 14
    L.prism(e, DARK, r, r, p["top"], p["top"] + ph, 16, cap=False, col=SURF_WALL, center=(ex, ez))
    fan(e, FLOOR, (ex, p["top"] + ph, ez), S.ngon(ex, ez, r, 16, p["top"] + ph), col=SURF_EXIT)
    ring_line(e, GLOW, ex, ez, r - 10, p["top"] + ph, n=16, width=10)
    S.beam(e, ex, ez, 60, 60, p["top"] + ph, W.CEIL - 4, planes=2)
    # under the platform: the way out shows from the floor (a ring of light right over the entrance)
    strip(e, GLOW, ngon_line(ex, ez, r, p["top"] - p["t"], n=16), [(0, -1, 0)] * 16, 10, lift=1.2, closed=True)


def build_pedestal():
    e = L.new_entry("pedestal")
    px, pz = W.PEDESTAL
    L.prism(e, WALL, DAIS["r"], DAIS["r"], 0, DAIS["h"], 16, cap=True, cap_mat=FLOOR, center=(px, pz), col=SURF_WALL)
    ring_line(e, GLOW, px, pz, DAIS["r"] - 14, DAIS["h"], n=24, width=8)
    S.beam(e, px, pz, 60, 90, DAIS["h"], W.CEIL - 4, planes=2)


# ---------------------------------------------------------------- actors


def actors():
    a = []
    cz = CH["z"]
    a.append(("ACTOR_EN_COW", -CH_APO + 105, 0, cz, 0, 0x4000, 0, "0"))
    for sx in (-1, 1):
        a.append(("ACTOR_OBJ_SYOKUDAI", sx * 170, 0, cz - CH_APO + 70, 0, 0, 0, "0x0400"))
    a.append((WIND_ACTOR, 0, 0, 0, 0, 0, 0, wp(WIND_CTRL)))
    a.append(("ACTOR_EN_REMIX_MAGNET", 0, 0, 0, 0, 0, 0, "0x3F00"))  # Magnesis, lent (MAGNET_CONTROLLER, MAGNET_ALWAYS)
    cx, cz_ = W.COLUMN
    for k, c in enumerate(W.CUBES):
        x, z = c["home"]
        a.append((WIND_ACTOR, x, 20 if (x, z) == W.COLUMN else 0, z, 0, 0, 0, wp(WIND_CUBE, k)))
    a.append((WIND_ACTOR, cx, 0, cz_, 0, 0, 0, wp(WIND_FAN, 0)))
    a.append((WIND_ACTOR, cx, W.CEIL, cz_, 0, 0, 0, wp(WIND_FAN, 1)))
    a.append((WIND_ACTOR, W.PLATE["x"], W.CEIL, W.PLATE["z"], 0, 0, 0, wp(WIND_PLATE)))
    a.append((WIND_ACTOR, W.BRACKET[0], W.CEIL, W.BRACKET[2], 0, 0, 0, wp(WIND_BRACKET)))
    a.append((WIND_ACTOR, W.TIMER[0], 0, W.TIMER[1], 0, 0, 0, wp(WIND_TIMER)))
    a.append((WIND_ACTOR, W.LADDER1["x"], 0, W.LADDER1["z"], 0, 0x4000, 0, wp(WIND_LADDER, 0)))
    a.append((WIND_ACTOR, W.LADDER2["x"], W.LADDER2["bottom"], W.LADDER2["z"], 0, 0x8000, 0, wp(WIND_LADDER, 1)))
    a.append((WIND_ACTOR, W.GATE1["x"], 0, W.GATE1["z"], 0, 0, 0, wp(WIND_GATE, 0)))
    gr = W.GLASS_ROOM
    a.append((WIND_ACTOR, (gr["x0"] + gr["x1"]) / 2, gr["floor"], gr["z1"], 0, 0, 0, wp(WIND_GATE, 1)))
    # the crystal that turns the wind (on the balcony), the glass room's crystal (on its shelf, lit by a cube)
    a.append(("ACTOR_OBJ_SWITCH", W.CRYSTAL_FANS[0], W.BALCONY["top"], W.CRYSTAL_FANS[1], 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_CRYSTAL, OBJSWITCH_SUBTYPE_TOGGLE, {W.FLAG_FANS})"))
    a.append(("ACTOR_OBJ_SWITCH", *W.CRYSTAL_GLASS, 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_CRYSTAL, OBJSWITCH_SUBTYPE_SYNC, {W.FLAG_GLASS})"))
    # the treasures: the exit platform's chest, the glass room's
    a.append(("ACTOR_EN_BOX", W.CHEST_EXIT[0], W.EXIT_PLATFORM["top"], W.CHEST_EXIT[1], 0, 0x4000, 0,
              f"(ENBOX_TYPE_BIG_DEFAULT << 12) | (GI_HEART_CONTAINER << 5) | {W.T_HEART}"))
    a.append(("ACTOR_EN_BOX", W.CHEST_GLASS[0], gr["floor"], W.CHEST_GLASS[1], 0, 0x8000, 0,
              f"(ENBOX_TYPE_SMALL << 12) | (GI_HEART_PIECE << 5) | {W.T_GLASS}"))
    # the Master Sword's pedestal, the inscriptions (En_Remix_Years' tablets 3 and 4: message_data.h 0x7FAA, 0x7FAB)
    px, pz = W.PEDESTAL
    a.append((YEARS_ACTOR, px, DAIS["h"], pz, 0, 0x8000, 0, wp(YEARS_PEDESTAL)))
    a.append((YEARS_ACTOR, 240, 0, 560, 0, 0, 0, wp(YEARS_TABLET, 3)))
    a.append((YEARS_ACTOR, W.BALCONY["x0"] + 30, W.BALCONY["top"], W.BALCONY["z0"] + 50, 0, 0, 0, wp(YEARS_TABLET, 4)))
    return a


OBJECTS = ["OBJECT_SYOKUDAI", "OBJECT_COW", "OBJECT_BOX", "OBJECT_REMIX_YEARS", "OBJECT_REMIX_MAGNET",
           "OBJECT_REMIX_WIND"]


def room_defines():
    cx, cz = W.COLUMN
    return ("// The wind's crystal flag (z_remix_level.c colours the wind's lines by it), the flags the test boots set\n"
            f"#define WIND_SHRINE_FLAG_FANS {W.FLAG_FANS}\n#define WIND_SHRINE_FLAG_LADDER {W.FLAG_LADDER}\n"
            f"#define WIND_SHRINE_FLAG_WEDGED {W.FLAG_WEDGED}\n#define WIND_SHRINE_FLAG_BRACKET {W.FLAG_BRACKET}\n"
            "// Where the test boots put Link: on the timed switch; over the column of wind (he drops onto the cube)\n"
            f"#define WIND_TEST_TIMER_X {W.TIMER[0]}.0f\n#define WIND_TEST_TIMER_Y 12.0f\n"
            f"#define WIND_TEST_TIMER_Z {W.TIMER[1]}.0f\n"
            f"#define WIND_TEST_RIDE_X {cx}.0f\n#define WIND_TEST_RIDE_Y 520.0f\n#define WIND_TEST_RIDE_Z {cz - 10}.0f\n\n")


def check_layout():
    """What the shrine relies on: the adult climbs about 100, the child about 50; a running jump carries about 157;
    Link finds a ladder about 26 above his feet."""
    adult_climb, jump = 100, 157
    b, e, l2 = W.BALCONY, W.EXIT_PLATFORM, W.LADDER2
    cx, cz = W.COLUMN
    light, medium, heavy = (c["size"] for c in W.CUBES)
    assert b["top"] > adult_climb * 2 + heavy, "the balcony could be climbed from a cube"
    # the fans: the floor fan's housing clear of the balcony, the column's cube within a hop of the balcony
    assert cx - (W.FAN_R + 15) > b["x1"], "the floor fan runs into the balcony"
    assert b["z0"] < cz < b["z1"]
    assert (cx - light / 2) - b["x1"] < jump / 2, "the dancing cube is out of reach of the balcony"
    lo, hi = W.HOVER_MID - W.HOVER_AMP, W.HOVER_MID + W.HOVER_AMP
    assert lo + light < b["top"] < hi + light, "the cube never passes the balcony's height"
    assert hi > W.COLUMN_MID > W.HOVER_MID, "the wind turned at the top of the dance must pull the cube up"
    # the ride: the child reaches the final ladder from the cube, the adult does not; nothing reaches it otherwise
    assert W.RIDE_TOP["child"] + 26 > l2["bottom"] and W.RIDE_TOP["child"] < l2["bottom"]
    assert W.RIDE_TOP["adult"] + 26 + 30 < l2["bottom"]
    assert b["top"] + 26 < l2["bottom"] - 60
    assert abs(l2["z"] - (cz + light / 2)) < 12, "the final ladder is not at the cube's edge"
    assert e["z0"] == l2["z"] and e["x0"] < l2["x"] - l2["w"] / 2
    assert W.CEIL_FAN_BOTTOM > e["top"] + 60, "the child can't walk under the ceiling fan on the platform"
    # the bracket beside the plate; the medium cube fits it, the light cube the hole, the medium not
    p = W.PLATE
    assert abs(W.BRACKET[0] - p["x"]) >= p["w"] / 2 + medium / 2
    assert abs(W.BRACKET[0] - p["x"]) - medium / 2 - heavy / 2 > 0, "the medium cube under the bracket overlaps the heavy"
    assert light / 2 - 2 < W.HOLE["w"] / 2 < medium / 2 - 2
    assert W.GLASS_ROOM["floor"] < W.GLASS_CAP < W.GLASS_ROOM["ceil"] - 40
    # the wedged heavy cube and the bracketed medium cube hang clear of the exit platform and the balcony
    print("make_wind: the balcony, the dance, the ride, the bracket and the hole checked")


def main():
    configure()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    L.make_textures()
    (OUT / "ancient_title.ia8.png").unlink(missing_ok=True)
    sky_palettes()
    S.title_card("Upside-Down Wind")
    S.build_chamber()
    build_floor_and_ceiling()
    build_walls()
    build_balcony()
    build_exit_platform()
    build_pedestal()
    check_layout()
    npolys, nverts, entries, acts = S.write_sources()
    tris = sum(len(t) for e in L.ENTRIES + L.MESHES for t in e.groups.values())
    print(f"Shrine of the Upside-Down Wind: {len(entries)} room chunks, {tris} triangles, {npolys} collision polys "
          f"({nverts} vertices), {len(acts)} actors")
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file"] + [str(p) for p in OUT.glob("*.[ch]")], cwd=REPO, check=True)


if __name__ == "__main__":
    main()
