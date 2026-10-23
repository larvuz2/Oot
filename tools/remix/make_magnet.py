#!/usr/bin/env python3
"""Generate the Lodestone Shrine (Web Remix level 4): a Breath of the Wild style shrine that gives Link a new rune,
MAGNESIS, and then a trial that needs it. Its moving pieces are En_Remix_Magnet actors (object_remix_magnet:
tools/remix/make_magnet_parts.py); the rune Link holds up is a fal-made model (tools/remix/make_slate.py).

The trial, "The Iron Will":

  A. The compass bridge (no Magnesis yet). A chasm fills the middle of the hall; on its pivot turns an L-shaped
     bridge that always links two neighbouring sides. Crystal switches at the edge of the south and north ledges turn
     it a quarter (south -> east -> north -> west) each time they are struck, carrying anyone standing on it. Stand
     on the bridge's tip and strike the crystal to ride it round. A floor switch on the east dock drops a chest onto
     the west dock: inside, the MAGNESIS RUNE (hold L: grab iron, move it with the stick and C buttons).
  B. Iron (Magnesis). The north side's doorway is shut by an iron slab: pull it out. In the north hall:
       - an iron crate goes up onto the floor switch on top of a pillar (Link can't climb it): while it holds the
         switch down, a lift rides up and down to the balcony;
       - the balcony's altar is across a gap: an iron girder from the floor, turned and laid across, is the bridge;
       - and an iron chest on top of a column, out of reach, can be brought down too (rupees).
     The altar: the Heart Container, and a ring of light home.

Falling into the chasm voids Link out (back to the arrival chamber); an iron piece that falls in comes back to where
it started.

    python3 tools/remix/make_magnet.py      # writes assets/scenes/remix/magnet/ (committed)
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_shrine as S  # noqa: E402  (the Ember Shrine's tools; pointed at this shrine below)
from make_shrine import (L, Mat, strip, unit, wall, flat, box, ngon, fan, floor_line, wall_line, ring_line,  # noqa: E402
                         rune_panel, eye_emblem, FLOOR, WALL, DARK, RUNES, GLOW, EMBER, EYE)
import make_magnet_parts as P  # noqa: E402  (the moving pieces' sizes)

REPO = HERE.parents[1]
OUT = REPO / "assets/scenes/remix/magnet"
INC = "assets/scenes/remix/magnet"
SCENE, ROOM = "magnet_scene", "magnet_room_0"

TEXTURES = {
    "plaza": ("magnet_plaza", "ci4", (64, 64)),
    "techstone": ("magnet_techstone", "ci4", (64, 64)),
    "techrock": ("magnet_techrock", "ci4", (64, 64)),
    "runes": ("magnet_runes", "ci4", (64, 64)),
    "glow": ("magnet_glow", "i8", (32, 32)),
    "eye": ("magnet_eye", "i8", (64, 64)),
}

# Magnesis's lines (dim until the rune is found, then magenta: segment 0x09) and the lift's (orange while it runs: 0x0A)
MAG = Mat("mag", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x09, scroll=True, repeat=150, clamp_t=True)
LIFTLINE = Mat("liftline", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x0A, scroll=True, repeat=150,
               clamp_t=True)
MAG_EYE = Mat("mag_eye", "eye", "i8", (64, 64), lit=False, xlu=True, prim_seg=0x09)

SURF_FLOOR, SURF_WALL, SURF_EXIT, SURF_VOID = range(4)
SURFACES = [("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 1),
            ("SURFACE_MATERIAL_STONE", 0, "FLOOR_PROPERTY_12")]  # 12: falling onto it voids Link out

# ---------------------------------------------------------------- the plan (y up, north is -z)

HALL = dict(x0=-800, x1=800, z0=-1350, z1=1250, h=900)
CH = dict(x=0, z=1600, r=340, h=380)
CH_APO = CH["r"] * math.cos(math.pi / 8)
SPAWN = (0, 330, CH["z"])
PEDESTAL = dict(x=0, z=CH["z"] + 200, r=75, h=14)
PIT = -700
CHASM = 560  # the chasm: |z| < 560, wall to wall; the bridge's pivot in the middle
DOCK = dict(x=560, z=200)  # the east and west docks: |x| > 560, |z| < 200
ARM, ARM_W = P.BRIDGE_ARM, P.BRIDGE_W  # the bridge's arms reach 535 from the pivot (25 short of the ledges)
CRYSTAL_S = (90, 0, CHASM + 12)  # beside the south arm's tip: struck from the ledge or from the tip
CRYSTAL_N = (-90, 0, -CHASM - 12)
SWITCH_E = (690, 0, 0)
CHEST_W = (-690, 0, 0)
WALL_N = dict(z0=-840, z1=-800, door=110, door_h=230)  # between the north ledge and the north hall
SLAB = (0, 0, -820)
PILLAR = dict(x0=240, x1=360, z0=-1110, z1=-990, top=260)  # the lift's switch on top (Link climbs ~110 at most)
BALCONY = dict(x0=20, x1=800, z0=-1350, z1=-1170, top=320)
ALTAR = dict(x0=-800, x1=-200, z0=-1350, z1=-1170, top=320)  # 220 from the balcony: the girder (340) bridges it
LIFT = (560, 2, -1087)  # 160 square: its north edge 2 short of the balcony's front; 2 over the floor (no z-fight)
COLUMN = dict(x0=-690, x1=-610, z0=-970, z1=-890, top=420)
CRATE = (-250, 0, -960)
GIRDER = (-420, 0, -1000)  # lying north-south: to be turned to bridge the gap (east-west)
EXIT = (-300, ALTAR["top"], -1260)
RING = dict(x=-520, y=ALTAR["top"] + 300, z=-1260, r=110)

FLAG_CRYSTAL_S, FLAG_CRYSTAL_N, FLAG_DROP, FLAG_LIFT = 1, 2, 3, 4  # switch flags
T_RUNE, T_HEART, T_IRON = 1, 2, 3  # chests' treasure flags

MAGNET_CONTROLLER, MAGNET_CRATE, MAGNET_GIRDER, MAGNET_SLAB, MAGNET_LIFT, MAGNET_BRIDGE = range(6)


def magnet(kind, flag=0):
    """En_Remix_Magnet params (z_en_remix_magnet.h: MAGNET_PARAMS)."""
    return f"0x{((flag & 0x3F) << 8) | kind:04X}"


def configure():
    """Point the Plateau's and the Ember Shrine's tools at this shrine."""
    L.OUT, L.INC, L.SCENE, L.ROOM = OUT, INC, SCENE, ROOM
    L.TEXTURES = TEXTURES
    L.ENTRIES.clear()
    L.COL_TRIS.clear()
    L.MESHES.clear()
    for k, v in dict(OUT=OUT, INC=INC, SCENE=SCENE, ROOM=ROOM, NAME="Lodestone Shrine", TITLE_STEM="magnet_title",
                     TITLE_SYM="gLodestoneShrineTitleCardTex", MEMSIZE_MACRO="MAGNET_SCENE_BGCHECK_MEMSIZE",
                     MUSIC="NA_BGM_FOREST_TEMPLE", SURFACES=SURFACES, EXITS=["ENTR_RETURN_GROTTO"], SPAWN=SPAWN,
                     HALL=HALL, CH=CH, CH_APO=CH_APO, PEDESTAL=PEDESTAL, OBJECTS=OBJECTS, actors=actors,
                     room_defines=room_defines, EXTRA_ROOM_C=[], EXTRA_ENTRIES=[]).items():
        setattr(S, k, v)


# ---------------------------------------------------------------- the shrine


def hall_walls(e):
    """The four walls, from the chasm's floor to the ceiling, the arch in the south wall."""
    x0, x1, z0, z1, h = HALL["x0"], HALL["x1"], HALL["z0"], HALL["z1"], HALL["h"]
    wall(e, WALL, (x1, z1), (x1, z0), PIT, h, (-1, 0, 0), u0=z0)
    wall(e, WALL, (x0, z0), (x0, z1), PIT, h, (1, 0, 0), u0=z0)
    wall(e, WALL, (x0, z0), (x1, z0), 0, h, (0, 0, 1))
    wall(e, WALL, (x1, z1), (S.ARCH_HALF, z1), 0, h, (0, 0, -1))
    wall(e, WALL, (-S.ARCH_HALF, z1), (x0, z1), 0, h, (0, 0, -1))
    wall(e, WALL, (S.ARCH_HALF, z1), (-S.ARCH_HALF, z1), S.ARCH_H, h, (0, 0, -1))
    for x, facing in ((x0, (1, 0, 0)), (x1, (-1, 0, 0))):
        for zz in np.arange(z0 + 160, z1 - 60, 320):
            wall_line(e, GLOW, [(x, 240, zz), (x, h - 80, zz)], facing)
        wall_line(e, GLOW, [(x, 600, z0), (x, 600, z1)], facing)
    wall_line(e, GLOW, [(x0, 600, z1), (x1, 600, z1)], (0, 0, -1))
    rune_panel(e, (0, 420, z1), (0, 0, -1), 150, 150)


def build_south(e):
    """The south ledge: its edge in orange, the south crystal's ring, pots."""
    x0, x1 = HALL["x0"], HALL["x1"]
    flat(e, FLOOR, x0, x1, CHASM, HALL["z1"], 0)
    wall(e, WALL, (x1, CHASM), (x0, CHASM), PIT, 0, (0, 0, -1))
    floor_line(e, EMBER, [(x0 + 10, CHASM + 12), (-ARM_W / 2 - 20, CHASM + 12)], width=10)
    floor_line(e, EMBER, [(ARM_W / 2 + 20, CHASM + 12), (x1 - 10, CHASM + 12)], width=10)
    cx, _, cz = CRYSTAL_S
    ring_line(e, GLOW, cx, cz + 10, 34, 0, n=12, width=8)
    # a compass on the floor: the bridge's four stops
    for k, (dx, dz) in enumerate(((0, 1), (1, 0), (0, -1), (-1, 0))):
        floor_line(e, GLOW, [(dx * 30, 900 + dz * 30), (dx * 90, 900 + dz * 90)], width=10)
    ring_line(e, GLOW, 0, 900, 110, 0, n=20, width=8)
    ring_line(e, GLOW, 0, 900, 40, 0, n=12, width=6)


def build_chasm(e):
    """The chasm: its floor far below (voids Link out), the docks, the pivot's pillar."""
    x0, x1 = HALL["x0"], HALL["x1"]
    flat(e, DARK, x0, x1, -CHASM, CHASM, PIT, col=SURF_VOID)
    for z in np.arange(-CHASM + 140, CHASM, 280):
        floor_line(e, GLOW, [(x0 + 40, z), (x1 - 40, z)], width=10, y=PIT)
    # the docks: east (the switch that drops the chest), west (where it lands)
    for sx in (1, -1):
        xa, xb = (DOCK["x"], x1) if sx > 0 else (x0, -DOCK["x"])
        box(e, xa, xb, PIT, 0, -DOCK["z"], DOCK["z"], top=FLOOR, skip=("e",) if sx > 0 else ("w",))
        edge = DOCK["x"] * sx - sx * 12
        floor_line(e, EMBER, [(edge, -DOCK["z"] + 10), (edge, DOCK["z"] - 10)], width=10)
        for z in (-DOCK["z"] + 60, DOCK["z"] - 60):
            rune_panel(e, (DOCK["x"] * sx, -90, z), (-sx, 0, 0), 70, 70)
    ring_line(e, GLOW, SWITCH_E[0], SWITCH_E[2], 60, 0, n=12, width=8)
    ring_line(e, MAG, CHEST_W[0], CHEST_W[2], 75, 0, n=16, width=10)  # the rune's chest lands here
    ring_line(e, MAG, CHEST_W[0], CHEST_W[2], 95, 0, n=16, width=6)
    # the pivot: a pillar up to just under the bridge (40 deep), lit bands
    L.prism(e, WALL, 120, 95, PIT, -P.BRIDGE_T - 2, 8, col=SURF_WALL, cap=True, cap_mat=DARK, center=(0, 0))
    for y in (-200, -400):
        ring_line(e, GLOW, 0, 0, 112 - (y + 700) * 25 / 660, y, n=16, width=10)


def build_north(e):
    """The north ledge and the wall shut by the iron slab."""
    x0, x1 = HALL["x0"], HALL["x1"]
    w = WALL_N
    flat(e, FLOOR, x0, x1, w["z1"], -CHASM, 0)
    wall(e, WALL, (x0, -CHASM), (x1, -CHASM), PIT, 0, (0, 0, 1))
    floor_line(e, EMBER, [(x0 + 10, -CHASM - 12), (-ARM_W / 2 - 20, -CHASM - 12)], width=10)
    floor_line(e, EMBER, [(ARM_W / 2 + 20, -CHASM - 12), (x1 - 10, -CHASM - 12)], width=10)
    cx, _, cz = CRYSTAL_N
    ring_line(e, GLOW, cx, cz - 10, 34, 0, n=12, width=8)
    # the dividing wall (both faces), its doorway (the slab stands in it), Magnesis's lines leading to it
    h, d, dh = HALL["h"], w["door"], w["door_h"]
    for z, facing in ((w["z1"], (0, 0, 1)), (w["z0"], (0, 0, -1))):
        a, b = ((x1, z), (d, z)) if facing[2] < 0 else ((d, z), (x1, z))
        wall(e, WALL, a, b, 0, h, facing)
        a, b = ((-d, z), (x0, z)) if facing[2] < 0 else ((x0, z), (-d, z))
        wall(e, WALL, a, b, 0, h, facing)
        a, b = ((d, z), (-d, z)) if facing[2] < 0 else ((-d, z), (d, z))
        wall(e, WALL, a, b, dh, h, facing)
    wall(e, WALL, (d, w["z1"]), (d, w["z0"]), 0, dh, (-1, 0, 0))
    wall(e, WALL, (-d, w["z0"]), (-d, w["z1"]), 0, dh, (1, 0, 0))
    flat(e, DARK, -d, d, w["z0"], w["z1"], dh, up=False)
    flat(e, FLOOR, -d, d, w["z0"], w["z1"], 0)
    eye_emblem(e, MAG_EYE, (0, dh + 140, w["z1"]), (0, 0, 1), 150)
    wall_line(e, MAG, [(-d - 20, 0, w["z1"]), (-d - 20, dh + 20, w["z1"]), (d + 20, dh + 20, w["z1"]),
                       (d + 20, 0, w["z1"])], (0, 0, 1), width=10)
    floor_line(e, MAG, [(-d - 20, w["z1"] + 10), (-300, -650), (-300, -CHASM - 40)], width=10)
    for x in (-500, 500):
        rune_panel(e, (x, 160, w["z1"]), (0, 0, 1), 110, 110)


def build_north_hall(e):
    """Beyond the slab: the pillar with the lift's switch, the balcony and the altar, the iron chest's column."""
    x0, x1, z0 = HALL["x0"], HALL["x1"], HALL["z0"]
    w = WALL_N
    flat(e, FLOOR, x0, x1, z0, w["z0"], 0)
    p, b, a, c = PILLAR, BALCONY, ALTAR, COLUMN
    box(e, p["x0"], p["x1"], 0, p["top"], p["z0"], p["z1"])
    box(e, b["x0"], b["x1"], 0, b["top"], b["z0"], b["z1"], skip=("n", "e"))
    box(e, a["x0"], a["x1"], 0, a["top"], a["z0"], a["z1"], skip=("n", "w"))
    box(e, c["x0"], c["x1"], 0, c["top"], c["z0"], c["z1"])
    # the lift's lines: round the pillar, up its face, along the floor to the lift, up the balcony's face
    pcx, pcz = (p["x0"] + p["x1"]) / 2, (p["z0"] + p["z1"]) / 2
    ring_line(e, LIFTLINE, pcx, pcz, 95, 0, n=16, width=10)
    wall_line(e, LIFTLINE, [(pcx, 0, p["z1"]), (pcx, p["top"], p["z1"])], (0, 0, 1), width=10)
    floor_line(e, LIFTLINE, [(p["x1"] + 30, pcz), (LIFT[0] - 100, pcz), (LIFT[0] - 100, LIFT[2])], width=10)
    wall_line(e, LIFTLINE, [(LIFT[0] - 100, 0, b["z1"]), (LIFT[0] - 100, b["top"], b["z1"])], (0, 0, 1), width=10)
    # Magnesis's lines: the crate's and the girder's spots, the column, the gap
    ring_line(e, MAG, CRATE[0], CRATE[2], 70, 0, n=14, width=8)
    floor_line(e, MAG, [(GIRDER[0] - 50, GIRDER[2] + 190), (GIRDER[0] - 50, GIRDER[2] - 140)], width=8)
    floor_line(e, MAG, [(GIRDER[0] + 50, GIRDER[2] + 190), (GIRDER[0] + 50, GIRDER[2] - 140)], width=8)
    ccx, ccz = (c["x0"] + c["x1"]) / 2, (c["z0"] + c["z1"]) / 2
    wall_line(e, MAG, [(ccx, 0, c["z1"]), (ccx, c["top"], c["z1"])], (0, 0, 1), width=10)
    for x in (a["x1"], b["x0"]):
        facing = (1, 0, 0) if x == a["x1"] else (-1, 0, 0)
        wall_line(e, MAG, [(x, b["top"] - 14, b["z1"]), (x, b["top"] - 14, b["z0"])], facing, width=10)
    floor_line(e, EMBER, [(b["x0"] + 10, b["z1"] - 10), (b["x1"] - 10, b["z1"] - 10)], width=8, y=b["top"])
    floor_line(e, EMBER, [(a["x0"] + 10, a["z1"] - 10), (a["x1"] - 10, a["z1"] - 10)], width=8, y=a["top"])
    # the altar: the eye over it, the ring of light home (an exit), its ring of runes above (build_ring)
    eye_emblem(e, EYE, (RING["x"], a["top"] + 260, z0), (0, 0, 1), 200)
    ex, ey, ez = EXIT
    L.prism(e, DARK, 62, 62, ey, ey + 6, 16, cap=False, col=SURF_WALL, center=(ex, ez))
    fan(e, FLOOR, (ex, ey + 6, ez), ngon(ex, ez, 62, 16, ey + 6), col=SURF_EXIT)
    ring_line(e, GLOW, ex, ez, 52, ey + 6, n=16, width=10)
    S.beam(e, ex, ez, 50, 50, ey + 6, HALL["h"] - 4, planes=2)
    for x in (-600, -200, 200, 600):
        wall_line(e, GLOW, [(x, b["top"], z0), (x, HALL["h"] - 80, z0)], (0, 0, 1))
    wall_line(e, GLOW, [(x0, 600, z0), (x1, 600, z0)], (0, 0, 1))


def build_ceiling():
    e = L.new_entry("ceiling")
    x0, x1, z0, z1, h = HALL["x0"], HALL["x1"], HALL["z0"], HALL["z1"], HALL["h"]
    flat(e, DARK, x0, x1, z0, z1, h, up=False, col=None)
    for x in (-400, 0, 400):
        strip(e, GLOW, [(x, h, z0), (x, h, z1)], [(0, -1, 0)] * 2, 16, lift=1.2)
    for z in (-1000, -300, 300, 900):
        strip(e, GLOW, [(x0, h, z), (x1, h, z)], [(0, -1, 0)] * 2, 16, lift=1.2)


def build_ring():
    e = L.new_entry("ring", matrix_seg=0x0F, sphere=((RING["x"], RING["y"], RING["z"]), RING["r"] + 40))
    r, n = RING["r"], 16
    outer, inner = ngon(0, 0, r, n, 0), ngon(0, 0, r - 22, n, 0)
    for k in range(n):
        k2 = (k + 1) % n
        p = [outer[k], outer[k2], inner[k2], inner[k]]
        for f in ((0, -1, 0), (0, 1, 0)):
            L.quad(e, RUNES, p, [(0, 0), (64, 0), (64, 20), (0, 20)], [(255, 120, 230, 255)] * 4, f)
    strip(e, MAG, [tuple(p) for p in ngon(0, 0, r + 6, 24, 0)], [(0, -1, 0)] * 24, 10, lift=1.0, closed=True)


# ---------------------------------------------------------------- actors


def actors():
    a = []
    cz = CH["z"]
    a.append(("ACTOR_EN_COW", -CH_APO + 105, 0, cz, 0, 0x4000, 0, "0"))  # the cow grotto's cow again
    for sx in (-1, 1):
        a.append(("ACTOR_OBJ_SYOKUDAI", sx * 170, 0, cz - CH_APO + 70, 0, 0, 0, "0x0400"))
    # Magnesis (given by the rune's chest; it can lift the iron chest too: home.rot.z)
    a.append(("ACTOR_EN_REMIX_MAGNET", 0, 0, 0, 0, 0, T_IRON, magnet(MAGNET_CONTROLLER, T_RUNE)))
    # A. the compass bridge, its crystals, the dock switch and the rune's chest
    a.append(("ACTOR_EN_REMIX_MAGNET", 0, 0, 0, 0, 0, FLAG_CRYSTAL_N, magnet(MAGNET_BRIDGE, FLAG_CRYSTAL_S)))
    for (x, y, z), flag in ((CRYSTAL_S, FLAG_CRYSTAL_S), (CRYSTAL_N, FLAG_CRYSTAL_N)):
        a.append(("ACTOR_OBJ_SWITCH", x, y, z, 0, 0, 0,
                  f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_CRYSTAL, OBJSWITCH_SUBTYPE_TOGGLE, {flag})"))
    a.append(("ACTOR_OBJ_SWITCH", *SWITCH_E, 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_FLOOR, OBJSWITCH_SUBTYPE_ONCE, {FLAG_DROP})"))
    a.append(("ACTOR_EN_BOX", *CHEST_W, 0, 0x4000, FLAG_DROP,
              f"(ENBOX_TYPE_SWITCH_FLAG_FALL_BIG << 12) | (GI_REMIX_MAGNESIS << 5) | {T_RUNE}"))
    for k, (x, z) in enumerate([(-600, 1000), (-660, 880), (600, 1000), (660, 880)]):
        a.append(("ACTOR_OBJ_TSUBO", x, 0, z, 0, 0, 0, "ITEM00_RECOVERY_HEART" if k % 2 == 0 else "0x3F"))
    for x in (-500, 500):
        a.append(("ACTOR_OBJ_SYOKUDAI", x, 0, CHASM + 60, 0, 0, 0, "0x0400"))
        a.append(("ACTOR_OBJ_SYOKUDAI", x, 0, -CHASM - 60, 0, 0, 0, "0x0400"))
    # B. the slab in the doorway, the crate and the pillar's switch, the lift, the girder, the iron chest
    a.append(("ACTOR_EN_REMIX_MAGNET", *SLAB, 0, 0, 0, magnet(MAGNET_SLAB)))
    a.append(("ACTOR_EN_REMIX_MAGNET", *CRATE, 0, 0x2000, 0, magnet(MAGNET_CRATE)))
    p = PILLAR
    a.append(("ACTOR_OBJ_SWITCH", (p["x0"] + p["x1"]) // 2, p["top"], (p["z0"] + p["z1"]) // 2, 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_FLOOR, OBJSWITCH_SUBTYPE_HOLD, {FLAG_LIFT})"))
    a.append(("ACTOR_EN_REMIX_MAGNET", *LIFT, 0, 0, BALCONY["top"] - LIFT[1], magnet(MAGNET_LIFT, FLAG_LIFT)))
    a.append(("ACTOR_EN_REMIX_MAGNET", *GIRDER, 0, 0x4000, 0, magnet(MAGNET_GIRDER)))
    c = COLUMN
    a.append(("ACTOR_EN_BOX", (c["x0"] + c["x1"]) // 2, c["top"], (c["z0"] + c["z1"]) // 2, 0, 0, 0,
              f"(ENBOX_TYPE_SMALL << 12) | (GI_RUPEE_GOLD << 5) | {T_IRON}"))
    al = ALTAR
    a.append(("ACTOR_EN_BOX", RING["x"], al["top"], -1280, 0, 0, 0,
              f"(ENBOX_TYPE_BIG_DEFAULT << 12) | (GI_HEART_CONTAINER << 5) | {T_HEART}"))
    for x in (-500, 300):
        a.append(("ACTOR_OBJ_SYOKUDAI", x, 0, WALL_N["z0"] - 60, 0, 0, 0, "0x0400"))
    return a


OBJECTS = ["OBJECT_SYOKUDAI", "OBJECT_COW", "OBJECT_BOX", "OBJECT_REMIX_MAGNET"]


def room_defines():
    return ("// The trial's flags (z_remix_level.c: Magnesis's lines glow once the rune is found, the lift's while it runs)\n"
            f"#define MAGNET_TREASURE_RUNE {T_RUNE}\n#define MAGNET_FLAG_LIFT {FLAG_LIFT}\n#define MAGNET_FLAG_DROP {FLAG_DROP}\n"
            "// Where the test boots put Link: facing the iron slab, in front of the rune's chest (z_remix_level.c)\n"
            f"#define MAGNET_TEST_SLAB_X {SLAB[0]}.0f\n#define MAGNET_TEST_SLAB_Z {SLAB[2] + 170}.0f\n"
            f"#define MAGNET_TEST_CHEST_X {CHEST_W[0] + 45}.0f\n#define MAGNET_TEST_CHEST_Z {CHEST_W[2]}.0f\n"
            "// The rune ring over the altar\n"
            f"#define MAGNET_RING_X {RING['x']}\n#define MAGNET_RING_Y {RING['y']}\n#define MAGNET_RING_Z {RING['z']}\n\n")


def check_layout():
    """What the trial relies on: the bridge's arms meet the ledges without touching them as they sweep, the crystals
    are within a sword's reach of the arms' tips but clear of their sweep, nothing can be jumped, Link can't climb what
    Magnesis has to carry things onto, the girder bridges the altar's gap on both ends."""
    corner = math.hypot(ARM, ARM_W / 2)
    assert ARM < CHASM - 15 and corner < CHASM, "the arms would touch the ledges"
    assert ARM < DOCK["x"] - 15, "the arms would touch the docks"
    for cx, _, cz in (CRYSTAL_S, CRYSTAL_N):
        assert math.hypot(cx, cz) - 22 > corner, "a crystal is in the bridge's way"
        tip = (math.copysign(ARM_W / 2 - 12, cx), math.copysign(ARM - 10, cz))
        assert math.hypot(cx - tip[0], cz - tip[1]) < 70, "a crystal is out of reach from the tip"
    # gaps no running jump crosses (about 157 at most)
    assert DOCK["x"] - ARM_W / 2 > 300 and CHASM - DOCK["z"] > 300
    gap = BALCONY["x0"] - ALTAR["x1"]
    assert 180 <= gap <= P.GIRDER[0] - 100, gap  # girder ends rest 40+ inside each ledge
    samples = P.GIRDER[0] / 2 - 15
    assert samples > gap / 2 + 30, "the girder's end samples would miss the ledges"
    for top in (PILLAR["top"], BALCONY["top"], COLUMN["top"]):
        assert top - P.CRATE - P.GIRDER[1] > 140, "Link could climb up from the crate"
    assert BALCONY["z1"] - (LIFT[2] - P.LIFT[2] / 2) < 6, "the lift is too far from the balcony"
    print("make_magnet: bridge, crystals, gaps and heights checked")


def main():
    configure()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    L.make_textures()
    (OUT / "ancient_title.ia8.png").unlink(missing_ok=True)
    S.title_card("Lodestone Shrine")
    S.build_chamber()
    hall = L.new_entry("south")
    hall_walls(hall)
    build_south(hall)
    build_chasm(L.new_entry("chasm"))
    build_north(L.new_entry("north"))
    build_north_hall(L.new_entry("north_hall"))
    build_ceiling()
    build_ring()
    check_layout()
    npolys, nverts, entries, acts = S.write_sources()
    tris = sum(len(t) for e in L.ENTRIES + L.MESHES for t in e.groups.values())
    print(f"Lodestone Shrine: {len(entries)} room chunks, {tris} triangles, {npolys} collision polys ({nverts} vertices), "
          f"{len(acts)} actors")
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file"] + [str(p) for p in OUT.glob("*.[ch]")], cwd=REPO, check=True)


if __name__ == "__main__":
    main()
