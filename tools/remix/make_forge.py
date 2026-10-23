#!/usr/bin/env python3
"""Generate the Forge Shrine (Web Remix level 5): Magnesis mixed with the game's fire, torches and water, built the
way Breath of the Wild grows a puzzle: introduce a mechanic, apply it, combine it with others, then let the player
bend the rules. One new thing only, an iron fire basket (En_Remix_Magnet's MAGNET_BRAZIER): Magnesis carries it, a
burning torch sets it alight, its flame lights the wooden torches it touches (to them it is Din's Fire), water puts
it out. The shrine lends Link Magnesis.

The trial, "The Iron Flame":

  1. Introduce. The basket stands by an eternal torch, already burning. Carry it to the wooden torch by the gate:
     the gate rises.
  2. Apply. The next torch stands across a chasm Link can't cross. Float the burning basket over to it: a bridge
     rises out of the chasm.
  3. Combine. Three timed torches stand on posts in a pool, and all three must burn at once (each burns about 13
     seconds). Link can't walk while he holds something, and the basket goes out if it drops in the water: find the
     one spot on the shore that reaches all three, keep the flame above the water, be quick. The gate opens.
  4. Subvert. The last torch is far out in a chasm, beyond Magnesis's reach. Hold the basket as far out as it goes and
     fling it (B): it flies on, onto the torch's platform. The Heart Container drops by the exit.

Every room has an eternal torch to rekindle the basket, and a basket that falls into a chasm comes back to where it
last was over solid ground (no softlock). Deku sticks and fire arrows work on the torches too, the way they would in
the game: other solutions are welcome.

    python3 tools/remix/make_forge.py      # writes assets/scenes/remix/forge/ (committed)
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
OUT = REPO / "assets/scenes/remix/forge"
INC = "assets/scenes/remix/forge"
SCENE, ROOM = "forge_scene", "forge_room_0"

TEXTURES = {
    "plaza": ("forge_plaza", "ci4", (64, 64)),
    "techstone": ("forge_techstone", "ci4", (64, 64)),
    "techrock": ("forge_techrock", "ci4", (64, 64)),
    "runes": ("forge_runes", "ci4", (64, 64)),
    "glow": ("forge_glow", "i8", (32, 32)),
    "eye": ("forge_eye", "i8", (64, 64)),
    "water": ("forge_water", "rgba16", (32, 32)),
}

# each stage's circuit lines: dim until its torch is lit (segments 0x09, 0x0A, 0x0B, 0x0E: z_remix_level.c)
STAGE = [Mat(f"stage{k}", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=seg, scroll=True, repeat=150,
             clamp_t=True) for k, seg in enumerate((0x09, 0x0A, 0x0B, 0x0E))]
POOL = Mat("pool", "water", "rgba16", (32, 32), lit=False, xlu=True, prim=(120, 175, 255, 150), repeat=220)

SURF_FLOOR, SURF_WALL, SURF_EXIT, SURF_VOID = range(4)
SURFACES = [("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 1),
            ("SURFACE_MATERIAL_STONE", 0, "FLOOR_PROPERTY_12")]  # 12: falling onto it voids Link out

# ---------------------------------------------------------------- the plan (y up, north is -z)

X0, X1, H = -700, 700, 700
HALL = dict(x0=X0, x1=X1, z0=-2500, z1=1250, h=H)
CH = dict(x=0, z=1600, r=340, h=380)
CH_APO = CH["r"] * math.cos(math.pi / 8)
SPAWN = (0, 330, CH["z"])
PEDESTAL = dict(x=0, z=CH["z"] + 200, r=75, h=14)
PIT = -700
DOOR, DOOR_H = 110, 230  # doorways in the cross walls: |x| < 110, 230 high
WALLS = [(560, 600), (-380, -340), (-1380, -1340)]  # cross walls (z0, z1): 1|2, 2|3, 3|4

# 1. Introduce (z 600..1250)
ETERNAL = [(225, 900), (-400, 470), (-400, -470), (-560, -1430)]  # always burning torches, one per room
BRAZIER = (170, 900)  # 55 from the first eternal torch: it starts out burning
TORCH_1 = (170, 660)  # by the first gate, straight ahead of the basket
GATE_1 = (0, 580)
# 2. Apply (z -340..560): the chasm wall to wall, the torch on the far side, the span that rises
CHASM_2 = (-120, 380)
TORCH_2 = (320, -200)
SPAN_2 = (0, (CHASM_2[0] + CHASM_2[1]) / 2)
# 3. Combine (z -1340..-380): the pool and its three timed torches on posts
POOL_BOX = dict(x0=-460, x1=460, z0=-1180, z1=-560, floor=-220, surface=-30)
POSTS = [(-250, -700), (250, -860), (-150, -1060)]
POST_TOP, POST_R = 10, 35
SPOT_3 = (0, -480)  # the one spot on the shore that reaches all three
GATE_3 = (0, -1360)
# 4. Subvert (z -2500..-1340): the near ledge, the chasm, the far torch's platform
LEDGE_4 = (-1560, -1380)
TARGET = dict(x=0, z=-2380, r=75, lip=20)
CHEST_4 = (300, -1470)
EXIT = (-300, -1470)
RING = dict(x=EXIT[0], y=420, z=EXIT[1], r=100)

FLAG_1, FLAG_2, FLAG_3, FLAG_4 = 1, 2, 3, 4  # switch flags: the four torches (stages)
T_HEART = 1
TIMED = 3  # the pool's torches burn 50 * 3 + 110 frames (13 seconds) once lit

MAGNET_CONTROLLER, MAGNET_BRAZIER, MAGNET_GATE, MAGNET_SPAN, MAGNET_ALWAYS = 0, 6, 7, 8, 0x3F


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
    for k, v in dict(OUT=OUT, INC=INC, SCENE=SCENE, ROOM=ROOM, NAME="Forge Shrine", TITLE_STEM="forge_title",
                     TITLE_SYM="gForgeShrineTitleCardTex", MEMSIZE_MACRO="FORGE_SCENE_BGCHECK_MEMSIZE",
                     MUSIC="NA_BGM_FIRE_TEMPLE", SURFACES=SURFACES, EXITS=["ENTR_RETURN_GROTTO"], SPAWN=SPAWN,
                     HALL=HALL, CH=CH, CH_APO=CH_APO, PEDESTAL=PEDESTAL, OBJECTS=OBJECTS, actors=actors,
                     room_defines=room_defines, EXTRA_ROOM_C=[], EXTRA_ENTRIES=[],
                     WATERBOXES=[(POOL_BOX["x0"], POOL_BOX["x1"], POOL_BOX["z0"], POOL_BOX["z1"],
                                  POOL_BOX["surface"])]).items():
        setattr(S, k, v)


# ---------------------------------------------------------------- the shrine


def side_walls(e, z0, z1, y0=0):
    """The east and west walls between z0 and z1, with light strips."""
    wall(e, WALL, (X1, z1), (X1, z0), y0, H, (-1, 0, 0), u0=z0)
    wall(e, WALL, (X0, z0), (X0, z1), y0, H, (1, 0, 0), u0=z0)
    for x, facing in ((X0, (1, 0, 0)), (X1, (-1, 0, 0))):
        for zz in np.arange(z0 + 160, z1 - 60, 320):
            wall_line(e, GLOW, [(x, 240, zz), (x, H - 80, zz)], facing)
        wall_line(e, GLOW, [(x, 500, z0), (x, 500, z1)], facing)


def cross_wall(e, z0, z1, mat_line=None):
    """A wall across the hall with a doorway in the middle (both faces, the doorway's sides and top)."""
    d = DOOR
    for z, facing in ((z1, (0, 0, 1)), (z0, (0, 0, -1))):
        wall(e, WALL, (d, z), (X1, z), 0, H, facing)
        wall(e, WALL, (X0, z), (-d, z), 0, H, facing)
        wall(e, WALL, (-d, z), (d, z), DOOR_H, H, facing)
    wall(e, WALL, (d, z1), (d, z0), 0, DOOR_H, (-1, 0, 0))
    wall(e, WALL, (-d, z0), (-d, z1), 0, DOOR_H, (1, 0, 0))
    flat(e, DARK, -d, d, z0, z1, DOOR_H, up=False)
    flat(e, FLOOR, -d, d, z0, z1, 0)
    if mat_line is not None:
        wall_line(e, mat_line, [(-d - 20, 0, z1), (-d - 20, DOOR_H + 20, z1), (d + 20, DOOR_H + 20, z1),
                                (d + 20, 0, z1)], (0, 0, 1), width=10)


def chasm(e, z0, z1, mat=EMBER):
    """A void chasm wall to wall between z0 and z1 (the floor around it at 0)."""
    flat(e, DARK, X0, X1, z0, z1, PIT, col=SURF_VOID)
    for z in np.arange(z0 + 140, z1, 280):
        floor_line(e, GLOW, [(X0 + 40, z), (X1 - 40, z)], width=10, y=PIT)
    wall(e, WALL, (X0, z1), (X1, z1), PIT, 0, (0, 0, -1))  # the near (south) face
    wall(e, WALL, (X1, z0), (X0, z0), PIT, 0, (0, 0, 1))  # the far face
    side_walls(e, z0, z1, y0=PIT)
    for z in (z0 - 12, z1 + 12):
        floor_line(e, mat, [(X0 + 10, z), (X1 - 10, z)], width=10)


def ring_at(e, mat, xz, r, y=0, n=14, width=8):
    ring_line(e, mat, xz[0], xz[1], r, y, n=n, width=width)


def build_intro(e):
    """1. The arrival room: the basket by its eternal torch, the first gate and its torch."""
    z0, z1 = WALLS[0][1], HALL["z1"]
    flat(e, FLOOR, X0, X1, z0, z1, 0)
    side_walls(e, z0, z1)
    wall(e, WALL, (X1, z1), (S.ARCH_HALF, z1), 0, H, (0, 0, -1))
    wall(e, WALL, (-S.ARCH_HALF, z1), (X0, z1), 0, H, (0, 0, -1))
    wall(e, WALL, (S.ARCH_HALF, z1), (-S.ARCH_HALF, z1), S.ARCH_H, H, (0, 0, -1))
    rune_panel(e, (0, 400, z1), (0, 0, -1), 150, 150)
    cross_wall(e, *WALLS[0], STAGE[0])
    ring_at(e, GLOW, BRAZIER, 60)
    ring_at(e, STAGE[0], TORCH_1, 45)
    floor_line(e, STAGE[0], [(BRAZIER[0], BRAZIER[1] - 70), (TORCH_1[0], TORCH_1[1] + 55)], width=10)
    eye_emblem(e, EYE, (0, DOOR_H + 170, WALLS[0][1]), (0, 0, 1), 140)


def build_apply(e):
    """2. The chasm room: the far torch, the span (an actor) that rises between the ledges."""
    z0, z1 = WALLS[1][1], WALLS[0][0]
    c0, c1 = CHASM_2
    flat(e, FLOOR, X0, X1, c1, z1, 0)
    flat(e, FLOOR, X0, X1, z0, c0, 0)
    side_walls(e, c1, z1)
    side_walls(e, z0, c0)
    chasm(e, c0, c1)
    cross_wall(e, *WALLS[1], STAGE[1])
    ring_at(e, STAGE[1], TORCH_2, 45)
    floor_line(e, STAGE[1], [(TORCH_2[0], TORCH_2[1] + 50), (TORCH_2[0], c0 - 30), (SPAN_2[0] + 120, c0 - 30)], width=10)
    ring_at(e, GLOW, ETERNAL[1], 45)
    for x in (-100, 100):  # where the span comes up
        floor_line(e, STAGE[1], [(x, c1 + 30), (x, c1 + 90)], width=8)


def build_combine(e):
    """3. The pool room: the walkways round the pool, the posts and their torches, the third gate."""
    z0, z1 = WALLS[2][1], WALLS[1][0]
    p = POOL_BOX
    side_walls(e, z0, z1)
    flat(e, FLOOR, X0, X1, p["z1"], z1, 0)  # south walkway
    flat(e, FLOOR, X0, X1, z0, p["z0"], 0)  # north walkway
    flat(e, FLOOR, X0, p["x0"], p["z0"], p["z1"], 0)  # west
    flat(e, FLOOR, p["x1"], X1, p["z0"], p["z1"], 0)  # east
    # the pool: its floor, sides, the water's surface (drawn; the water itself is the scene's water box)
    flat(e, DARK, p["x0"], p["x1"], p["z0"], p["z1"], p["floor"])
    wall(e, WALL, (p["x0"], p["z1"]), (p["x1"], p["z1"]), p["floor"], 0, (0, 0, -1))
    wall(e, WALL, (p["x1"], p["z0"]), (p["x0"], p["z0"]), p["floor"], 0, (0, 0, 1))
    wall(e, WALL, (p["x1"], p["z1"]), (p["x1"], p["z0"]), p["floor"], 0, (-1, 0, 0))
    wall(e, WALL, (p["x0"], p["z0"]), (p["x0"], p["z1"]), p["floor"], 0, (1, 0, 0))
    q = [(p["x0"], p["surface"], p["z0"]), (p["x1"], p["surface"], p["z0"]), (p["x1"], p["surface"], p["z1"]),
         (p["x0"], p["surface"], p["z1"])]
    L.quad(e, POOL, q, [L.planar_uv(POOL, v) for v in q], [(255, 255, 255, 255)] * 4, (0, 1, 0))
    for x, z in POSTS:
        L.prism(e, WALL, POST_R + 4, POST_R, p["floor"], POST_TOP, 8, col=SURF_WALL, cap=True, cap_mat=DARK,
                center=(x, z))
        ring_at(e, STAGE[2], (x, z), POST_R - 6, y=POST_TOP, n=10, width=6)
    # the spot that reaches all three: a ring on the shore, lines out to the posts
    ring_at(e, STAGE[2], SPOT_3, 50, n=16, width=10)
    ring_at(e, GLOW, ETERNAL[2], 45)
    for x in (-200, 200):
        floor_line(e, EMBER, [(x, p["z1"] + 12), (x + (60 if x > 0 else -60), p["z1"] + 12)], width=8)
    floor_line(e, EMBER, [(p["x0"] + 10, p["z1"] + 12), (p["x1"] - 10, p["z1"] + 12)], width=8)
    cross_wall(e, *WALLS[2], STAGE[2])


def build_subvert(e):
    """4. The last room: the near ledge (exit ring, where the chest drops), the chasm, the far torch's platform."""
    z0, z1 = HALL["z0"], WALLS[2][0]
    l0, l1 = LEDGE_4
    flat(e, FLOOR, X0, X1, l0, l1, 0)
    side_walls(e, l0, l1)
    chasm(e, z0, l0, mat=STAGE[3])
    wall(e, WALL, (X0, z0), (X1, z0), 0, H, (0, 0, 1))
    eye_emblem(e, EYE, (0, 430, z0), (0, 0, 1), 240)
    for x in (-420, 420):
        wall_line(e, GLOW, [(x, 0, z0), (x, H - 80, z0)], (0, 0, 1))
    # the platform out in the chasm: a pillar from the pit, a low lip all round
    t = TARGET
    r, x, z = t["r"], t["x"], t["z"]
    box(e, x - r, x + r, PIT, 0, z - r, z + r, top=FLOOR)
    for (a0, a1, b0, b1) in ((x - r, x + r, z + r - 10, z + r), (x - r, x + r, z - r, z - r + 10),
                             (x - r, x - r + 10, z - r, z + r), (x + r - 10, x + r, z - r, z + r)):
        box(e, a0, a1, 0, t["lip"], b0, b1, top=DARK)
    ring_at(e, STAGE[3], (x, z), r - 25, n=16, width=8)
    # the exit: a ring of light (an exit floor), its rune ring above (build_ring)
    ex, ez = EXIT
    L.prism(e, DARK, 62, 62, 0, 6, 16, cap=False, col=SURF_WALL, center=(ex, ez))
    fan(e, FLOOR, (ex, 6, ez), ngon(ex, ez, 62, 16, 6), col=SURF_EXIT)
    ring_line(e, GLOW, ex, ez, 52, 6, n=16, width=10)
    S.beam(e, ex, ez, 50, 50, 6, H - 4, planes=2)
    ring_at(e, STAGE[3], CHEST_4, 70, n=16, width=8)
    ring_at(e, GLOW, ETERNAL[3], 45)


def build_ceiling():
    e = L.new_entry("ceiling")
    flat(e, DARK, X0, X1, HALL["z0"], HALL["z1"], H, up=False, col=None)
    for x in (-350, 0, 350):
        strip(e, GLOW, [(x, H, HALL["z0"]), (x, H, HALL["z1"])], [(0, -1, 0)] * 2, 16, lift=1.2)


def build_ring():
    e = L.new_entry("ring", matrix_seg=0x0F, sphere=((RING["x"], RING["y"], RING["z"]), RING["r"] + 40))
    r, n = RING["r"], 16
    outer, inner = ngon(0, 0, r, n, 0), ngon(0, 0, r - 22, n, 0)
    for k in range(n):
        k2 = (k + 1) % n
        p = [outer[k], outer[k2], inner[k2], inner[k]]
        for f in ((0, -1, 0), (0, 1, 0)):
            L.quad(e, RUNES, p, [(0, 0), (64, 0), (64, 20), (0, 20)], [(255, 170, 80, 255)] * 4, f)
    strip(e, STAGE[3], [tuple(p) for p in ngon(0, 0, r + 6, 24, 0)], [(0, -1, 0)] * 24, 10, lift=1.0, closed=True)


# ---------------------------------------------------------------- actors


def torch(x, z, params, y=0):
    return ("ACTOR_OBJ_SYOKUDAI", x, y, z, 0, 0, 0, params)


def actors():
    a = []
    cz = CH["z"]
    a.append(("ACTOR_EN_COW", -CH_APO + 105, 0, cz, 0, 0x4000, 0, "0"))
    for sx in (-1, 1):
        a.append(("ACTOR_OBJ_SYOKUDAI", sx * 170, 0, cz - CH_APO + 70, 0, 0, 0, "0x0400"))
    a.append(("ACTOR_EN_REMIX_MAGNET", 0, 0, 0, 0, 0, 0, magnet(MAGNET_CONTROLLER, MAGNET_ALWAYS)))  # lent Magnesis
    for x, z in ETERNAL:  # golden torches, always burning: where the basket is (re)kindled
        a.append(torch(x, z, "0x0400"))
    a.append(("ACTOR_EN_REMIX_MAGNET", BRAZIER[0], 0, BRAZIER[1], 0, 0, 0, magnet(MAGNET_BRAZIER)))
    # 1. wooden torch -> flag 1 -> the first gate rises
    a.append(torch(*TORCH_1, f"(1 << 12) | (0 << 6) | {FLAG_1}"))
    a.append(("ACTOR_EN_REMIX_MAGNET", GATE_1[0], 0, GATE_1[1], 0, 0, P.GATE[1], magnet(MAGNET_GATE, FLAG_1)))
    # 2. the far torch -> flag 2 -> the span rises out of the chasm
    a.append(torch(*TORCH_2, f"(1 << 12) | (0 << 6) | {FLAG_2}"))
    a.append(("ACTOR_EN_REMIX_MAGNET", SPAN_2[0], -400, SPAN_2[1], 0, 0, 400, magnet(MAGNET_SPAN, FLAG_2)))
    # 3. three timed torches together -> flag 3 -> the third gate
    for x, z in POSTS:
        a.append(torch(x, z, f"(1 << 12) | ({TIMED} << 6) | {FLAG_3}", y=POST_TOP))
    a.append(("ACTOR_EN_REMIX_MAGNET", GATE_3[0], 0, GATE_3[1], 0, 0, P.GATE[1], magnet(MAGNET_GATE, FLAG_3)))
    # 4. the far torch out in the chasm -> flag 4 -> the Heart Container drops by the exit
    a.append(torch(TARGET["x"], TARGET["z"], f"(1 << 12) | (0 << 6) | {FLAG_4}"))
    a.append(("ACTOR_EN_BOX", CHEST_4[0], 0, CHEST_4[1], 0, 0x8000, FLAG_4,
              f"(ENBOX_TYPE_SWITCH_FLAG_FALL_BIG << 12) | (GI_HEART_CONTAINER << 5) | {T_HEART}"))
    return a


OBJECTS = ["OBJECT_SYOKUDAI", "OBJECT_COW", "OBJECT_BOX", "OBJECT_REMIX_MAGNET"]


def room_defines():
    return ("// The four torches' switch flags (z_remix_level.c lights each stage's lines when its flag is set)\n"
            f"#define FORGE_FLAG_1 {FLAG_1}\n#define FORGE_FLAG_2 {FLAG_2}\n#define FORGE_FLAG_3 {FLAG_3}\n"
            f"#define FORGE_FLAG_4 {FLAG_4}\n"
            "// The rune ring over the exit\n"
            f"#define FORGE_RING_X {RING['x']}\n#define FORGE_RING_Y {RING['y']}\n#define FORGE_RING_Z {RING['z']}\n"
            "// Where the test boot puts Link: behind the basket, facing the first gate (z_remix_level.c)\n"
            f"#define FORGE_TEST_X {BRAZIER[0]}.0f\n#define FORGE_TEST_Z {BRAZIER[1] + 150}.0f\n\n")


def check_layout():
    """What the trial relies on (Magnesis reaches 650 from Link, the basket's flame reaches 85 + 15 round a torch,
    a running jump carries about 157, Link climbs about 110)."""
    reach, flame = 650, 100
    d = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])  # noqa: E731
    # 1: the basket starts burning (next to the eternal torch), but not next to the gate's torch
    assert d(BRAZIER, ETERNAL[0]) < 70 and d(BRAZIER, TORCH_1) > flame + 60
    assert all(d(TORCH_1, e) > flame + 40 for e in ETERNAL)
    # 2: the far torch is within reach from the near ledge, and the chasm can't be jumped
    assert d((TORCH_2[0], CHASM_2[1] + 20), TORCH_2) < reach - 20
    assert CHASM_2[1] - CHASM_2[0] > 300
    # 3: from the marked spot all three posts are within reach; from no corner of the shore can one stand by them
    assert all(d(SPOT_3, p) < reach - 30 for p in POSTS)
    p = POOL_BOX
    for x, z in POSTS:
        assert p["x0"] + 120 < x < p["x1"] - 120 and p["z0"] + 100 < z < p["z1"] - 100, "a post is too near the shore"
    for i, a in enumerate(POSTS):
        for b in POSTS[i + 1:]:
            assert d(a, b) > 2 * flame, "one pass would light two torches at once"
    assert POST_TOP - p["surface"] < 45  # (posts low: Link can't stand on them out of the water)
    # 4: the platform is out of Magnesis's reach from anywhere on the ledge, but a fling gets there
    t = TARGET
    near = LEDGE_4[0]
    assert near - (t["z"] + t["r"]) > reach - 30, "Magnesis could carry the basket all the way"
    fling = 16 * 10.7  # 16 a frame, about 10.7 frames up and back down to the same height
    assert abs((reach + fling) - (near - t["z"])) < t["r"] + 60, "a fling from the edge would not land on the platform"
    assert math.hypot(t["r"], t["r"]) < flame + 10  # a basket anywhere on it lights the torch in the middle
    print("make_forge: reaches, flames, the pool's spot and the fling checked")


def main():
    configure()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    L.make_textures()
    (OUT / "ancient_title.ia8.png").unlink(missing_ok=True)
    S.title_card("Forge Shrine")
    S.build_chamber()
    build_intro(L.new_entry("intro"))
    build_apply(L.new_entry("apply"))
    build_combine(L.new_entry("combine"))
    build_subvert(L.new_entry("subvert"))
    build_ceiling()
    build_ring()
    check_layout()
    npolys, nverts, entries, acts = S.write_sources()
    tris = sum(len(t) for e in L.ENTRIES + L.MESHES for t in e.groups.values())
    print(f"Forge Shrine: {len(entries)} room chunks, {tris} triangles, {npolys} collision polys ({nverts} vertices), "
          f"{len(acts)} actors")
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file"] + [str(p) for p in OUT.glob("*.[ch]")], cwd=REPO, check=True)


if __name__ == "__main__":
    main()
