#!/usr/bin/env python3
"""Generate the Ember Shrine (Web Remix level 2): a Breath of the Wild style shrine in the Ancient Plateau's style,
built from the game's own puzzle pieces.

Link drops in through a hole, the way he falls into a grotto (the hole is in the Ancient Plateau, a Door_Ana grotto
entrance), into a round arrival chamber with a cow (the cow grotto's, here a shrine's), pots of arrows and the
glowing pedestal that takes him back up. Through the arch, the shrine hall and its trial, "Carry the Flame":

  1. Wake the shrine: the Sheikah eye above the arch (behind you as you come in) is an eye switch. An arrow in it
     lights the great brazier in the middle of the hall (golden torch, switch flag 1).
  2. Push: a stone block on a track by the east gallery. Pushed to the end of the track it rests on a floor switch
     (flag 2, held while the block is on it): the brazier on the east gallery lights, and the block is the step up
     to the gallery (200 high: Link climbs 100 at most).
  3. Kindle: three torches have to burn at once (wooden timed torches, flag 3: each burns 13 seconds). Arrows shot
     through a burning brazier catch fire and light what they hit. Two torches stand on the floor (shoot through
     the great brazier), one on the west gallery that nobody can reach (shoot through the east gallery's brazier,
     across the hall; a low parapet stops shots from the floor).
  4. The flame is carried: the big chest drops onto the altar (a Heart Container), and the shrine's circuit lines
     all burn orange.

The circuit lines show the way: each stage's lines (segments 0x09-0x0B) glow dim blue until its switch flag is set,
then orange (z_remix_level.c, RemixLevel_DrawConfigShrine). Fast to draw like the Plateau: few materials, each set
once per area, five room chunks, no per-copy matrices.

    python3 tools/remix/make_shrine.py      # writes assets/scenes/remix/ember/ (committed)
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_level as L  # noqa: E402  (the Plateau's geometry and display-list tools, pointed at the shrine below)
from make_level import Mat, V, quad, strip, unit, facing_tri, add_col, tex_scale, planar_uv  # noqa: E402

REPO = HERE.parents[1]
OUT = REPO / "assets/scenes/remix/ember"
INC = "assets/scenes/remix/ember"
SCENE = "ember_scene"  # (not "shrine": the game has a shrine_scene, the Temple of Time's outside)
ROOM = "ember_room_0"

L.OUT, L.INC, L.SCENE, L.ROOM = OUT, INC, SCENE, ROOM
L.HF_TEXTURES = {}
L.TEXTURES = {  # the Plateau's own art (tools/remix/biome_art/ancient), as the shrine's copies
    "plaza": ("ember_plaza", "ci4", (64, 64)),
    "techstone": ("ember_techstone", "ci4", (64, 64)),
    "techrock": ("ember_techrock", "ci4", (64, 64)),
    "runes": ("ember_runes", "ci4", (64, 64)),
    "glow": ("ember_glow", "i8", (32, 32)),
    "eye": ("ember_eye", "i8", (64, 64)),
}
ENTRIES, COL_TRIS = L.ENTRIES, L.COL_TRIS
ENTRIES.clear()
COL_TRIS.clear()
L.MESHES.clear()

FLOOR = Mat("floor", "plaza", "ci4", (64, 64), repeat=300)
WALL = Mat("wall", "techstone", "ci4", (64, 64), repeat=240)
DARK = Mat("dark", "techrock", "ci4", (64, 64), repeat=280)
RUNES = Mat("runes", "runes", "ci4", (64, 64), lit=False)
GLOW = Mat("glow", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x08, scroll=True, repeat=150, clamp_t=True)
EMBER = Mat("ember", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x0C, scroll=True, repeat=150, clamp_t=True)
STAGE = [Mat(f"stage{k}", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x08 + k, scroll=True, repeat=150,
             clamp_t=True) for k in (1, 2, 3)]  # segments 0x09-0x0B: dim until the stage's switch flag is set
EYE = Mat("eye", "eye", "i8", (64, 64), lit=False, xlu=True, prim_seg=0x0C)
BEAM = Mat("beam", "glow", "i8", (32, 32), lit=False, xlu=True, prim=(170, 215, 255, 120), scroll=True, repeat=400,
           clamp_t=True)

# Collision surface types: (material, exit index)
SURF_FLOOR, SURF_WALL, SURF_EXIT = range(3)
SURFACES = [("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 1)]
EXITS = ["ENTR_RETURN_GROTTO"]  # the pedestal: back up through the hole, where Door_Ana sent Link down

# ---------------------------------------------------------------- the plan (units: Link is ~70 tall)

HALL = dict(x0=-560, x1=560, z0=-760, z1=800, h=640)  # north (-z) is the altar, south the arch
ARCH_HALF, ARCH_H = 130, 260
CH = dict(x=0, z=1150, r=340, h=380)  # arrival chamber (octagon, vertex radius r), its drop shaft at the center
CH_APO = CH["r"] * math.cos(math.pi / 8)
SHAFT_R, SHAFT_TOP = 80, 1100
SPAWN = (0, 330, CH["z"])  # Link falls from the shaft, facing the arch
PEDESTAL = dict(x=0, z=CH["z"] + 200, r=75, h=14)  # the way back up
GAL_X, GAL_Z0, GAL_Z1, GAL_H = 340, -380, 500, 200  # galleries along both side walls (|x| >= GAL_X)
PARAPET_H = 30  # on the west gallery's edge: shots from the floor can't reach its torch
TRACK = dict(x0=240, x1=340, z0=-150, z1=260, rail=40)  # the block's track against the east gallery
PILLAR = dict(x0=240, x1=340, z0=-260, z1=-150)  # stops the block on the switch
SWITCH = (290, 0, -100)
BLOCK = (290, 0, 100)  # medium push block: 100 units (Link climbs it, then the gallery from it)
C1 = (0, 0, 0)  # great brazier (flag 1, from the eye)
C2 = (390, GAL_H, 150)  # east gallery's brazier (flag 2, from the floor switch)
TORCHES = [(-260, 0, -330), (260, 0, -330), (-500, GAL_H, 150)]  # the three to light at once (flag 3)
EYE_SWITCH = (0, 370, HALL["z1"] - 5)
ALTAR = dict(x=0, z=-600, r=170, h=120)
CHEST = (0, ALTAR["h"], -620)
FIRE_PED = dict(x0=340, x1=460, z0=-750, z1=-630, h=130)  # flame pillars flanking the altar (both sides)
RING = dict(x=0, y=430, z=ALTAR["z"], r=150)  # rune ring turning above the altar (segment 0x0F)
FLAG_EYE, FLAG_BLOCK, FLAG_KINDLE = 1, 2, 3
BY_NAME = {}


# ---------------------------------------------------------------- geometry helpers


def wall(e, mat, a, b, y0, y1, facing, col=SURF_WALL, u0=0.0):
    """Vertical quad from (x, z) a to b, y0..y1, its front along `facing`."""
    su, sv = tex_scale(mat)
    ln = math.hypot(b[0] - a[0], b[1] - a[1])
    p = [(a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1])]
    uv = [(u0 * su, -y0 * sv), ((u0 + ln) * su, -y0 * sv), ((u0 + ln) * su, -y1 * sv), (u0 * su, -y1 * sv)]
    nrm = tuple(unit(facing))
    quad(e, mat, p, uv, [nrm] * 4, facing, col)


def flat(e, mat, x0, x1, z0, z1, y, up=True, col=SURF_FLOOR):
    p = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
    nrm = (0, 1, 0) if up else (0, -1, 0)
    quad(e, mat, p, [planar_uv(mat, q) for q in p], [nrm] * 4, nrm, col)


def box(e, x0, x1, y0, y1, z0, z1, top=DARK, side=WALL, col_top=SURF_FLOOR, col_side=SURF_WALL, skip=()):
    """Outward faces of a box (no bottom). skip: sides to leave out ('n', 's', 'e', 'w')."""
    flat(e, top, x0, x1, z0, z1, y1, col=col_top)
    if "n" not in skip:
        wall(e, side, (x1, z0), (x0, z0), y0, y1, (0, 0, -1), col_side)
    if "s" not in skip:
        wall(e, side, (x0, z1), (x1, z1), y0, y1, (0, 0, 1), col_side)
    if "e" not in skip:
        wall(e, side, (x1, z1), (x1, z0), y0, y1, (1, 0, 0), col_side)
    if "w" not in skip:
        wall(e, side, (x0, z0), (x0, z1), y0, y1, (-1, 0, 0), col_side)


def ngon(cx, cz, r, n, y, phase=0.0):
    return [np.array([cx + r * math.sin(phase + 2 * math.pi * k / n), y, cz + r * math.cos(phase + 2 * math.pi * k / n)])
            for k in range(n)]


def fan(e, mat, center, ring, up=True, col=None):
    nrm = (0, 1, 0) if up else (0, -1, 0)
    c = np.asarray(center, float)
    for k in range(len(ring)):
        pts = facing_tri(c, ring[k], ring[(k + 1) % len(ring)], nrm)
        e.tri(mat, [V(q, planar_uv(mat, q), nrm if mat.lit else (255, 255, 255, 255)) for q in pts])
        if col is not None:
            add_col(*pts, col)


def annulus(e, mat, outer, inner, up=True, col=None):
    nrm = (0, 1, 0) if up else (0, -1, 0)
    n = len(outer)
    for k in range(n):
        k2 = (k + 1) % n
        p = [outer[k], outer[k2], inner[k2], inner[k]]
        quad(e, mat, p, [planar_uv(mat, q) for q in p], [nrm] * 4, nrm, col)


def tube_inward(e, mat, cx, cz, r, n, y0, y1, col=None):
    """Inside of a vertical n-gon tube (the drop shaft)."""
    ring0, ring1 = ngon(cx, cz, r, n, y0), ngon(cx, cz, r, n, y1)
    su, sv = tex_scale(mat)
    u = 0.0
    for k in range(n):
        k2 = (k + 1) % n
        inward = unit(np.array([cx, 0, cz]) - (ring0[k] + ring0[k2]) / 2 * [1, 0, 1])
        w = float(np.linalg.norm(ring0[k2] - ring0[k]))
        quad(e, mat, [ring0[k], ring0[k2], ring1[k2], ring1[k]],
             [(u * su, -y0 * sv), ((u + w) * su, -y0 * sv), ((u + w) * su, -y1 * sv), (u * su, -y1 * sv)],
             [tuple(inward)] * 4, inward, col)
        u += w


def beam(e, x, z, r0, r1, y0, y1, planes=3):
    """Shaft of light: crossed see-through planes, both faces (texture across, pulses flowing up)."""
    for k in range(planes):
        a = math.pi * k / planes
        dx, dz = math.cos(a), math.sin(a)
        p = [(x - dx * r0, y0, z - dz * r0), (x + dx * r0, y0, z + dz * r0), (x + dx * r1, y1, z + dz * r1),
             (x - dx * r1, y1, z - dz * r1)]
        h = (y1 - y0) * BEAM.size[0] / BEAM.repeat
        uv = [(0, 0), (0, 32), (h, 32), (h, 0)]
        for side in (1, -1):
            quad(e, BEAM, p, uv, [(255, 255, 255, 255)] * 4, (-dz * side, 0, dx * side))


def floor_line(e, mat, pts, width=14, y=0.0):
    strip(e, mat, [(x, y, z) for x, z in pts], [(0, 1, 0)] * len(pts), width, lift=1.2)


def wall_line(e, mat, pts, facing, width=12):
    strip(e, mat, pts, [facing] * len(pts), width, lift=1.2)


def ring_line(e, mat, cx, cz, r, y, n=24, width=12):
    pts = [(cx + r * math.sin(2 * math.pi * k / n), y, cz + r * math.cos(2 * math.pi * k / n)) for k in range(n)]
    strip(e, mat, pts, [(0, 1, 0)] * n, width, lift=1.2, closed=True)


def rune_panel(e, center, facing, w, h):
    """Glowing rune panel on a wall (unlit, its own light)."""
    f = unit(facing)
    side = unit(np.cross((0, 1, 0), f))
    c = np.asarray(center, float) + f * 1.0
    p = [c - side * w / 2 - [0, h / 2, 0], c + side * w / 2 - [0, h / 2, 0], c + side * w / 2 + [0, h / 2, 0],
         c - side * w / 2 + [0, h / 2, 0]]
    quad(e, RUNES, p, [(0, 64), (64, 64), (64, 0), (0, 0)], [(150, 215, 255, 255)] * 4, f)


def eye_emblem(e, mat, center, facing, size):
    f = unit(facing)
    side = unit(np.cross((0, 1, 0), f))
    c = np.asarray(center, float) + f * 1.5
    p = [c - side * size / 2 - [0, size / 2, 0], c + side * size / 2 - [0, size / 2, 0],
         c + side * size / 2 + [0, size / 2, 0], c - side * size / 2 + [0, size / 2, 0]]
    quad(e, mat, p, [(0, 64), (64, 64), (64, 0), (0, 0)], [(255, 255, 255, 255)] * 4, f)


# ---------------------------------------------------------------- the shrine


def build_chamber():
    """Arrival chamber: octagon, drop shaft above the middle, the pedestal back up, the cow's corner, arrow pots."""
    e = L.new_entry("chamber")
    cx, cz, r, h = CH["x"], CH["z"], CH["r"], CH["h"]
    oct0 = ngon(cx, cz, r, 8, 0, math.pi / 8)
    oct1 = ngon(cx, cz, r, 8, h, math.pi / 8)
    fan(e, FLOOR, (cx, 0, cz), oct0, col=SURF_FLOOR)
    for k in range(8):
        k2 = (k + 1) % 8
        mid = (oct0[k] + oct0[k2]) / 2
        inward = unit(np.array([cx, 0, cz]) - mid * [1, 0, 1])
        a, b = (oct0[k][0], oct0[k][2]), (oct0[k2][0], oct0[k2][2])
        if mid[2] < cz - CH_APO + 5:  # the north side: the arch to the hall (wall only above it)
            wall(e, WALL, a, b, ARCH_H, h, inward)
            continue
        wall(e, WALL, a, b, 0, h, inward)
        # a band of light around the room, rune panels between
        wall_line(e, GLOW, [(a[0] + inward[0] * 0, 205, a[1]), (b[0], 205, b[1])], inward)
        if k % 2 == 0:
            rune_panel(e, (mid[0], 110, mid[2]), inward, 90, 90)
    # ceiling with the drop hole, the shaft up to the light
    hole = ngon(cx, cz, SHAFT_R, 8, h, math.pi / 8)
    annulus(e, DARK, oct1, hole, up=False)
    tube_inward(e, DARK, cx, cz, SHAFT_R, 8, h, SHAFT_TOP)
    fan(e, GLOW, (cx, SHAFT_TOP, cz), ngon(cx, cz, SHAFT_R, 8, SHAFT_TOP, math.pi / 8), up=False)
    beam(e, cx, cz, 95, 60, 0, SHAFT_TOP - 10)
    ring_line(e, GLOW, cx, cz, 120, 0, n=16)
    # the pedestal: glowing ring, its own light shaft (stand on it to go back up)
    px, pz, pr, ph = PEDESTAL["x"], PEDESTAL["z"], PEDESTAL["r"], PEDESTAL["h"]
    L.prism(e, DARK, pr, pr, 0, ph, 16, cap=False, col=SURF_WALL, center=(px, pz))
    fan(e, FLOOR, (px, ph, pz), ngon(px, pz, pr, 16, ph), col=SURF_EXIT)
    ring_line(e, GLOW, px, pz, pr - 10, ph, n=16, width=10)
    beam(e, px, pz, 60, 60, ph, h - 4, planes=2)
    # the cow's corner (west): a stall of dark stone, a cyan eye above it
    box(e, -CH_APO + 1, -CH_APO + 40, 0, 70, cz - 110, cz - 80, skip=("w",))
    box(e, -CH_APO + 1, -CH_APO + 40, 0, 70, cz + 80, cz + 110, skip=("w",))
    eye_emblem(e, Mat("eye_c", "eye", "i8", (64, 64), lit=False, xlu=True, prim_seg=0x08), (-CH_APO, 250, cz),
               (1, 0, 0), 110)
    # the corridor through the hall's wall
    z0, z1 = HALL["z1"], cz - CH_APO
    flat(e, FLOOR, -ARCH_HALF, ARCH_HALF, z0, z1 + 2, 0)
    wall(e, WALL, (-ARCH_HALF, z1), (-ARCH_HALF, z0), 0, ARCH_H, (1, 0, 0))
    wall(e, WALL, (ARCH_HALF, z0), (ARCH_HALF, z1), 0, ARCH_H, (-1, 0, 0))
    flat(e, DARK, -ARCH_HALF, ARCH_HALF, z0, z1, ARCH_H, up=False, col=None)
    for sx in (-1, 1):
        floor_line(e, GLOW, [(sx * (ARCH_HALF - 18), z1), (sx * (ARCH_HALF - 18), z0)], width=10)


def build_hall():
    """The hall: walls with light strips, the galleries, the block's track, the great brazier's ring, the circuit
    lines of the three stages."""
    south = L.new_entry("hall_south")
    north = L.new_entry("hall_north")
    x0, x1, z0, z1, h = HALL["x0"], HALL["x1"], HALL["z0"], HALL["z1"], HALL["h"]
    zm = 0
    for e, za, zb in ((north, z0, zm), (south, zm, z1)):
        flat(e, FLOOR, x0, x1, za, zb, 0)
        wall(e, WALL, (x1, zb), (x1, za), 0, h, (-1, 0, 0), u0=za)  # east wall faces west
        wall(e, WALL, (x0, za), (x0, zb), 0, h, (1, 0, 0), u0=za)
        for x in (x0, x1):  # vertical light strips, a band under the cornice
            facing = (1, 0, 0) if x == x0 else (-1, 0, 0)
            for z in np.arange(za + 140, zb - 60, 280):
                wall_line(e, GLOW, [(x, GAL_H + 20, z), (x, h - 60, z)], facing)
            wall_line(e, GLOW, [(x, 470, za), (x, 470, zb)], facing)
    # north wall: the great Sheikah eye over the altar, light strips
    wall(north, WALL, (x0, z0), (x1, z0), 0, h, (0, 0, 1))
    eye_emblem(north, EYE, (0, 400, z0), (0, 0, 1), 280)
    for x in (-420, -250, 250, 420):
        wall_line(north, GLOW, [(x, 0, z0), (x, h - 60, z0)], (0, 0, 1))
    wall_line(north, GLOW, [(x0, 470, z0), (x1, 470, z0)], (0, 0, 1))
    # south wall with the arch; the eye switch hangs above it (an actor)
    wall(south, WALL, (x1, z1), (ARCH_HALF, z1), 0, h, (0, 0, -1))
    wall(south, WALL, (-ARCH_HALF, z1), (x0, z1), 0, h, (0, 0, -1))
    wall(south, WALL, (ARCH_HALF, z1), (-ARCH_HALF, z1), ARCH_H, h, (0, 0, -1))
    wall_line(south, GLOW, [(x0, 470, z1), (x1, 470, z1)], (0, 0, -1))
    rune_panel(south, (0, 370, z1), (0, 0, -1), 150, 150)  # behind the eye switch

    # galleries: the east one is reached from the block, the west one (with its parapet) by nobody
    for sx, e in ((1, south), (-1, south)):
        gx0, gx1 = (GAL_X, x1) if sx > 0 else (x0, -GAL_X)
        box(e, gx0, gx1, 0, GAL_H, GAL_Z0, GAL_Z1, skip=("e",) if sx > 0 else ("w",))
        edge = GAL_X * sx
        mat = STAGE[1] if sx > 0 else GLOW
        floor_line(e, mat, [(edge - sx * 10, GAL_Z1), (edge - sx * 10, GAL_Z0)], width=12, y=GAL_H)
        wall_line(e, mat, [(edge, GAL_H - 14, GAL_Z1), (edge, GAL_H - 14, GAL_Z0)], (sx * -1, 0, 0))
        for z in np.arange(GAL_Z0 + 90, GAL_Z1, 220):
            rune_panel(e, (edge, 100, z), (-sx, 0, 0), 70, 70)
    box(south, -GAL_X - 12, -GAL_X, GAL_H, GAL_H + PARAPET_H, GAL_Z0, GAL_Z1, top=WALL, skip=("w",))

    # the block's track: a low rail on the west and south, the pillar at the north end, the switch
    t = TRACK
    box(south, t["x0"] - 20, t["x0"], 0, t["rail"], t["z0"], t["z1"] + 20, top=WALL)
    box(south, t["x0"] - 20, t["x1"], 0, t["rail"], t["z1"], t["z1"] + 20, top=WALL, skip=("e",))
    floor_line(south, STAGE[1], [(t["x0"] - 10, t["z1"] + 10), (t["x0"] - 10, t["z0"])], width=8, y=t["rail"])
    p = PILLAR
    box(south, p["x0"], p["x1"], 0, GAL_H, p["z0"], p["z1"], skip=("e",))
    # stage 2 lines: switch -> up the gallery face -> along the top -> the brazier
    sx_, _, sz_ = SWITCH
    wall_line(south, STAGE[1], [(GAL_X, 0, sz_ + 70), (GAL_X, GAL_H, sz_ + 70)], (-1, 0, 0))
    floor_line(south, STAGE[1], [(GAL_X + 20, sz_ + 70), (GAL_X + 20, C2[2] - 50), (C2[0], C2[2] - 50)], y=GAL_H)
    ring_line(south, STAGE[1], C2[0], C2[2], 45, GAL_H, n=12, width=10)
    ring_line(south, STAGE[1], sx_, sz_, 62, 0, n=12, width=8)

    # stage 1: the great brazier's ring, lines from below the eye switch (around the arch) to it
    ring_line(south, STAGE[0], C1[0], C1[2], 70, 0, n=20)
    ring_line(south, STAGE[0], C1[0], C1[2], 95, 0, n=20, width=8)
    for sx in (-1, 1):
        wall_line(south, STAGE[0], [(sx * 30, 330, z1), (sx * 30, ARCH_H + 14, z1), (sx * (ARCH_HALF + 30), ARCH_H + 14, z1),
                                    (sx * (ARCH_HALF + 30), 0, z1)], (0, 0, -1), width=10)
        floor_line(south, STAGE[0], [(sx * (ARCH_HALF + 30), z1), (sx * (ARCH_HALF + 30), 300), (sx * 70, 70)])

    # stage 3: from each torch to the altar, the altar's rings
    for tx, ty, tz in TORCHES:
        if ty == 0:
            d = unit(np.array([tx - ALTAR["x"], 0, tz - ALTAR["z"]]))
            edge = (ALTAR["x"] + d[0] * (ALTAR["r"] + 6), ALTAR["z"] + d[2] * (ALTAR["r"] + 6))
            floor_line(north, STAGE[2], [(tx - d[0] * 40, tz - d[2] * 40), edge])
            ring_line(north, STAGE[2], tx, tz, 40, 0, n=12, width=8)
    tx, ty, tz = TORCHES[2]
    ring_line(south, STAGE[2], tx, tz, 40, GAL_H, n=12, width=8)
    floor_line(south, STAGE[2], [(tx, tz - 45), (tx, GAL_Z0 + 20), (-GAL_X - 30, GAL_Z0 + 20)], y=GAL_H)
    wall_line(north, STAGE[2], [(-GAL_X - 40, GAL_H, GAL_Z0), (-GAL_X - 40, 0, GAL_Z0)], (0, 0, -1))
    floor_line(north, STAGE[2], [(-GAL_X - 40, GAL_Z0 - 10), (-ALTAR["r"] - 30, ALTAR["z"])])
    floor_line(north, STAGE[2], [(ALTAR["r"] + 30, ALTAR["z"]), (GAL_X + 40, GAL_Z0 - 10)])

    # ceiling: dark stone with a cross of light
    top = L.new_entry("ceiling")
    flat(top, DARK, x0, x1, z0, z1, h, up=False, col=None)
    for x in (-280, 0, 280):
        strip(top, GLOW, [(x, h, z0), (x, h, z1)], [(0, -1, 0)] * 2, 16, lift=1.2)
    strip(top, GLOW, [(x0, h, ALTAR["z"]), (x1, h, ALTAR["z"])], [(0, -1, 0)] * 2, 16, lift=1.2)
    strip(top, GLOW, [(x0, h, 300), (x1, h, 300)], [(0, -1, 0)] * 2, 16, lift=1.2)


def build_altar():
    """The altar at the north end: round dais with stairs, rune ring, flame pillars on either side."""
    e = BY_NAME["hall_north"]
    ax, az, ar, ah = ALTAR["x"], ALTAR["z"], ALTAR["r"], ALTAR["h"]
    L.prism(e, WALL, ar, ar, 0, ah, 16, cap=False, col=SURF_WALL, center=(ax, az))
    top = ngon(ax, az, ar, 16, ah)
    inner = ngon(ax, az, ar - 40, 16, ah)
    annulus(e, DARK, top, inner, col=SURF_FLOOR)
    fan(e, FLOOR, (ax, ah, az), inner, col=SURF_FLOOR)
    ring_line(e, STAGE[2], ax, az, ar - 20, ah, n=24, width=12)
    ring_line(e, STAGE[2], ax, az, 70, ah, n=16, width=8)
    for k in range(4):  # rune panels on the dais' sides
        a = math.pi / 4 + k * math.pi / 2
        n_ = np.array([math.sin(a), 0, math.cos(a)])
        rune_panel(e, (ax + n_[0] * (ar - 1), 60, az + n_[2] * (ar - 1)), n_, 60, 60)
    # stairs (south)
    front = az + ar * math.cos(math.pi / 16) - 4
    for i in (1, 2, 3):
        box(e, -90, 90, 0, 30 * i, front - 40, front + 30 * (4 - i), top=FLOOR)
    floor_line(e, GLOW, [(-80, front + 92), (80, front + 92)], width=8, y=30)
    # flame pillars (the game's fire walls, burning for good) on pedestals
    for sx in (-1, 1):
        f = FIRE_PED
        xa, xb = (f["x0"], f["x1"]) if sx > 0 else (-f["x1"], -f["x0"])
        box(e, xa, xb, 0, f["h"], f["z0"], f["z1"])
        wall_line(e, EMBER, [((xa + xb) / 2 - 40, f["h"] - 12, f["z1"]), ((xa + xb) / 2 + 40, f["h"] - 12, f["z1"])],
                  (0, 0, 1), width=10)


def build_ring():
    """Rune ring turning above the altar (drawn with segment 0x0F's matrix: z_remix_level.c)."""
    e = L.new_entry("ring", matrix_seg=0x0F, sphere=((RING["x"], RING["y"], RING["z"]), RING["r"] + 40))
    r, n = RING["r"], 16
    outer = ngon(0, 0, r, n, 0)
    inner = ngon(0, 0, r - 26, n, 0)
    for k in range(n):  # flat band of runes, seen from below
        k2 = (k + 1) % n
        p = [outer[k], outer[k2], inner[k2], inner[k]]
        quad(e, RUNES, p, [(0, 0), (64, 0), (64, 20), (0, 20)], [(255, 180, 90, 255)] * 4, (0, -1, 0))
        quad(e, RUNES, p, [(0, 0), (64, 0), (64, 20), (0, 20)], [(255, 180, 90, 255)] * 4, (0, 1, 0))
    strip(e, STAGE[2], [tuple(p) for p in ngon(0, 0, r + 6, 24, 0)], [(0, -1, 0)] * 24, 10, lift=1.0, closed=True)


# ---------------------------------------------------------------- actors


def yaw(rad):
    return int(round(rad / (2 * math.pi) * 0x10000)) & 0xFFFF


def actors():
    """(actor id, x, y, z, rot x, rot y, rot z, params)"""
    a = []
    cz = CH["z"]
    a.append(("ACTOR_EN_COW", -CH_APO + 105, 0, cz, 0, 0x4000, 0, "0"))  # the cow grotto's cow, facing the room
    for k, (x, z) in enumerate([(230, cz - 70), (250, cz + 40), (215, cz + 150), (130, cz + 240)]):
        a.append(("ACTOR_OBJ_TSUBO", x, 0, z, 0, 0, 0, "ITEM00_ARROWS_MEDIUM"))  # dungeon pots: 10 arrows each
    for sx in (-1, 1):  # always-burning golden torches by the arch (decoration)
        a.append(("ACTOR_OBJ_SYOKUDAI", sx * 170, 0, cz - CH_APO + 70, 0, 0, 0, "0x0400"))
    a.append(("ACTOR_OBJ_SWITCH", EYE_SWITCH[0], EYE_SWITCH[1], EYE_SWITCH[2], 0, 0x8000, 0,
              f"OBJSWITCH_PARAMS_EYE(OBJSWITCH_SUBTYPE_ONCE, {FLAG_EYE}, false)"))
    a.append(("ACTOR_OBJ_SYOKUDAI", *C1, 0, 0, 0, f"(0 << 12) | (1 << 6) | {FLAG_EYE}"))  # golden, lit by flag 1
    a.append(("ACTOR_OBJ_SWITCH", *SWITCH, 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_FLOOR, OBJSWITCH_SUBTYPE_HOLD, {FLAG_BLOCK})"))
    a.append(("ACTOR_OBJ_OSHIHIKI", *BLOCK, 0, 0, 0, "0xFF00 | PUSHBLOCK_MEDIUM_START_ON"))  # no switch flag
    a.append(("ACTOR_OBJ_SYOKUDAI", *C2, 0, 0, 0, f"(0 << 12) | (1 << 6) | {FLAG_BLOCK}"))  # golden, lit by flag 2
    for x, y, z in TORCHES:  # wooden timed torches: all three lit within 50 * 3 + 110 frames sets flag 3
        a.append(("ACTOR_OBJ_SYOKUDAI", x, y, z, 0, 0, 0, f"(1 << 12) | (3 << 6) | {FLAG_KINDLE}"))
    a.append(("ACTOR_EN_BOX", *CHEST, 0, 0, FLAG_KINDLE,
              "(ENBOX_TYPE_SWITCH_FLAG_FALL_BIG << 12) | (GI_HEART_CONTAINER << 5) | 0x01"))
    for sx in (-1, 1):  # flame pillars: fire walls waiting for a switch flag nobody sets (0x3E), so burning for good
        x = sx * (FIRE_PED["x0"] + FIRE_PED["x1"]) / 2
        a.append(("ACTOR_BG_HIDAN_CURTAIN", int(x), FIRE_PED["h"], (FIRE_PED["z0"] + FIRE_PED["z1"]) // 2, 0, 0, 0,
                  "(1 << 12) | (0x1E << 6) | 0x3E"))
    return a


OBJECTS = ["OBJECT_SYOKUDAI", "OBJECT_COW", "OBJECT_BOX"]  # (switches, block and pots: gameplay_dangeon_keep)


# ---------------------------------------------------------------- shot lines


def check_shots():
    """The trial's arrows: from a standing spot through a brazier's flame to each torch's flame, nothing in between
    (the hall's boxes), and the west torch out of reach from the floor (parapet)."""
    boxes = [  # (x0, x1, y0, y1, z0, z1) solid things an arrow could hit
        (GAL_X, HALL["x1"], 0, GAL_H, GAL_Z0, GAL_Z1), (HALL["x0"], -GAL_X, 0, GAL_H, GAL_Z0, GAL_Z1),
        (-GAL_X - 12, -GAL_X, GAL_H, GAL_H + PARAPET_H, GAL_Z0, GAL_Z1),
        (PILLAR["x0"], PILLAR["x1"], 0, GAL_H, PILLAR["z0"], PILLAR["z1"]),
    ]

    def blocked(p, q):
        p, q = np.asarray(p, float), np.asarray(q, float)
        for b in boxes:
            lo, hi = np.array([b[0], b[2], b[4]]), np.array([b[1], b[3], b[5]])
            d = q - p
            t0, t1 = 0.0, 1.0
            for i in range(3):
                if abs(d[i]) < 1e-9:
                    if p[i] < lo[i] or p[i] > hi[i]:
                        break
                    continue
                a, c = (lo[i] - p[i]) / d[i], (hi[i] - p[i]) / d[i]
                t0, t1 = max(t0, min(a, c)), min(t1, max(a, c))
            else:
                if t0 <= t1:
                    return True
        return False

    flame = 67  # middle of a torch's flame above its base (Obj_Syokudai: 45 to 90)
    bow = 55  # about where Link's arrows start
    plans = [((-1, 0, 1), C1, TORCHES[1]), ((1, 0, 1), C1, TORCHES[0])]
    for _, via, target in plans:
        v = np.array([via[0], via[1] + flame, via[2]])
        t = np.array([target[0], target[1] + flame, target[2]])
        d = unit((v - t) * [1, 0, 1])
        stand = v + d * 350
        stand[1] = via[1] + bow
        assert not blocked(stand, t), f"the shot through {via} to {target} is blocked"
    # the gallery shot: from the east gallery through its brazier, across the hall
    v = np.array([C2[0], GAL_H + flame, C2[2]])
    t = np.array([TORCHES[2][0], TORCHES[2][1] + flame, TORCHES[2][2]])
    stand = v + unit(v - t) * 90
    stand[1] = GAL_H + bow
    assert not blocked(stand, t), "the gallery shot is blocked"
    # from the floor, through any flame down there (the great brazier, or a floor torch once lit), the west
    # gallery's torch is behind the gallery's edge and parapet, however close to the flame Link stands
    for src in (C1, TORCHES[0], TORCHES[1]):
        s_ = np.array([src[0], src[1] + flame, src[2]])
        away = unit((s_ - t) * [1, 0, 1])
        side = np.array([-away[2], 0, away[0]])
        for d in (25, 40, 60, 90, 150, 300):
            for lat in (-12, 0, 12):
                stand = s_ + away * d + side * lat
                stand[1] = bow
                frac = d / (d + np.linalg.norm((t - s_) * [1, 0, 1]))
                at_flame = bow + (t[1] - bow) * frac
                if 45 <= at_flame - src[1] <= 90:
                    assert blocked(stand, t), f"the west torch can be lit from the floor through {src} at {stand}"
    print("make_shrine: shots checked (two through the great brazier, one across from the east gallery)")


# ---------------------------------------------------------------- output


# What write_sources() writes, set per shrine (tools/remix/make_seeker.py sets its own before calling it)
NAME = "Ember Shrine"
TITLE_STEM, TITLE_SYM = "ember_title", "gEmberShrineTitleCardTex"
MEMSIZE_MACRO = "EMBER_SCENE_BGCHECK_MEMSIZE"
MUSIC = "NA_BGM_ICE_CAVERN"
EXTRA_ROOM_C = []  # more C after the display lists (lists that call segments, for room entries of their own)
EXTRA_ENTRIES = []  # more room entries: (center, radius, opa list, xlu list)
WATERBOXES = []  # (x0, x1, z0, z1, surface y): water (tools/remix/make_forge.py's pool)
LIGHT_ROW = None  # another light setting (tools/remix/make_time.py: warm, sunlit sandstone)
EXTRA_SPAWNS = []  # more places Link can come in: (x, y, z, yaw) (tools/remix/make_time.py's pads)


def room_defines():
    return ("// The trial's switch flags (z_remix_level.c lights each stage's circuit lines when its flag is set)\n"
            f"#define SHRINE_FLAG_EYE {FLAG_EYE}\n#define SHRINE_FLAG_BLOCK {FLAG_BLOCK}\n#define SHRINE_FLAG_KINDLE {FLAG_KINDLE}\n"
            "// The rune ring over the altar (turned by z_remix_level.c)\n"
            f"#define SHRINE_RING_X {RING['x']}\n#define SHRINE_RING_Y {RING['y']}\n#define SHRINE_RING_Z {RING['z']}\n\n")


def title_card(text="Ember Shrine"):
    W, H, SS = 144, 24, 4
    size = 17 * SS
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", size)
    while True:  # shrink long names to fit the card
        bbox = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= (W - 6) * SS or size <= 10 * SS:
            break
        size -= SS
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", size)
    big = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(big)
    bbox = d.textbbox((0, 0), text, font=font)
    d.text(((W * SS - (bbox[2] - bbox[0])) / 2 - bbox[0], (H * SS - (bbox[3] - bbox[1])) / 2 - bbox[1]), text,
           font=font, fill=255)
    mask = np.array(big.resize((W, H), Image.LANCZOS)).astype(float) / 255
    shadow = np.zeros_like(mask)
    shadow[1:, 1:] = mask[:-1, :-1]
    alpha = np.clip(np.maximum(mask, np.maximum(shadow, mask) * 0.8), 0, 1)
    inten = np.where(alpha > 0, mask / np.maximum(alpha, 1e-6), 0)
    Image.fromarray(np.stack([np.round(inten * 255), np.round(alpha * 255)], -1).astype(np.uint8), "LA").save(
        OUT / f"{TITLE_STEM}.ia8.png")


def light_settings():
    """Inside, one dim blue light setting (the glow lines and the torches do the rest), dark blue fog."""
    row = LIGHT_ROW or ("{ { 66, 72, 98 }, { 73, 73, 73 }, { 150, 164, 200 }, { -73, -73, -73 }, { 84, 66, 50 }, "
                        "{ 14, 18, 32 }, BLEND_RATE_AND_FOG_NEAR(4, 990), 3600 },\n")
    return f"EnvLightSettings {SCENE}LightSettings[] = {{\n" + "    " + row * 1 + "    " + row + "    " + row + "    " + row + "};\n\n"


def write_sources():
    vtx_out, dl_out, entries, decl = L.emit_room()
    entries = entries + EXTRA_ENTRIES
    acts = actors()
    hdr = f"// Generated by tools/remix/{Path(sys.argv[0]).name} - the {NAME} (Web Remix). Do not edit.\n"
    tex_decl, tex_defs = [], []
    for key, (stem, fmt, size) in L.TEXTURES.items():
        if fmt == "ci4":
            tex_decl.append(f"extern u64 {L.tlut_symbol(key)}[];")
            tex_defs.append(f"u64 {L.tlut_symbol(key)}[] = {{\n#include \"{INC}/{stem}.tlut.rgba16.inc.c\"\n}};\n")
        tex_decl.append(f"extern u64 {L.tex_symbol(key)}[];")
        tex_defs.append(f"u64 {L.tex_symbol(key)}[] = {{\n#include \"{INC}/{stem}.{fmt}.inc.c\"\n}};\n")
    room_h = (hdr + f"#ifndef {ROOM.upper()}_H\n#define {ROOM.upper()}_H\n\n#include \"ultra64.h\"\n#include \"scene.h\"\n"
              f"#include \"room.h\"\n\nextern SceneCmd {ROOM}Commands[];\nextern s16 {ROOM}ObjectList[];\n"
              f"extern ActorEntry {ROOM}ActorList[];\nextern RoomShapeCullable {ROOM}RoomShape;\n"
              f"extern RoomShapeCullableEntry {ROOM}RoomShapeEntries[];\n\n"
              + room_defines() + "\n".join(tex_decl) + "\n" + "\n".join(decl) + "\n\n#endif\n")
    lines = [hdr, f'#include "{ROOM}.h"\n', '#include "actor.h"\n#include "array_count.h"\n#include "gfx.h"\n#include "object.h"\n'
             '#include "room.h"\n#include "scene.h"\n#include "sequence.h"\n#include "actor_profile.h"\n#include "item.h"\n'
             '#include "z_en_item00.h"\n#include "src/overlays/actors/ovl_En_Box/z_en_box.h"\n'
             '#include "src/overlays/actors/ovl_Obj_Switch/z_obj_switch.h"\n'
             '#include "src/overlays/actors/ovl_Obj_Oshihiki/z_obj_oshihiki.h"\n\n']
    lines.append(f"SceneCmd {ROOM}Commands[] = {{\n"
                 "    SCENE_CMD_ECHO_SETTINGS(12),\n"
                 "    SCENE_CMD_ROOM_BEHAVIOR(ROOM_TYPE_DUNGEON, ROOM_ENV_DEFAULT, false, false),\n"
                 "    SCENE_CMD_SKYBOX_DISABLES(true, true),\n"
                 "    SCENE_CMD_TIME_SETTINGS(0xFF, 0xFF, 0),\n"
                 f"    SCENE_CMD_ROOM_SHAPE(&{ROOM}RoomShape),\n"
                 f"    SCENE_CMD_OBJECT_LIST({len(OBJECTS)}, {ROOM}ObjectList),\n"
                 f"    SCENE_CMD_ACTOR_LIST({len(acts)}, {ROOM}ActorList),\n"
                 "    SCENE_CMD_END(),\n};\n\n")
    lines.append(f"s16 {ROOM}ObjectList[] = {{\n" + "".join(f"    {o},\n" for o in OBJECTS) + "};\n\n")
    lines.append(f"ActorEntry {ROOM}ActorList[] = {{\n" + "".join(
        f"    {{ {i}, {{ {int(round(x))}, {int(round(y))}, {int(round(z))} }}, {{ {rx}, 0x{ry:04X}, {rz} }}, {p} }},\n"
        for i, x, y, z, rx, ry, rz, p in acts) + "};\n\n")
    lines.append(f"RoomShapeCullableEntry {ROOM}RoomShapeEntries[] = {{\n" +
                 "".join(f"    {{ {{ {c[0]}, {c[1]}, {c[2]} }}, {r}, {o}, {x} }},\n" for c, r, o, x in entries) + "};\n\n")
    lines.append(f"RoomShapeCullable {ROOM}RoomShape = {{\n    {{ ROOM_SHAPE_TYPE_CULLABLE }},\n"
                 f"    ARRAY_COUNT({ROOM}RoomShapeEntries),\n    {ROOM}RoomShapeEntries,\n"
                 f"    {ROOM}RoomShapeEntries + ARRAY_COUNT({ROOM}RoomShapeEntries),\n}};\n\n")
    lines += [t + "\n" for t in tex_defs]
    lines += [v + "\n" for v in vtx_out]
    lines += [d + "\n" for d in dl_out]
    lines += [c + "\n" for c in EXTRA_ROOM_C]
    (OUT / f"{ROOM}.h").write_text(room_h)
    (OUT / f"{ROOM}.c").write_text("".join(lines))

    verts, polys, lo, hi = L.emit_collision()
    memsize, nodes = L.bgcheck_memsize(verts, polys, lo, hi)
    scene_h = (hdr + f"#ifndef {SCENE.upper()}_H\n#define {SCENE.upper()}_H\n\n#include \"ultra64.h\"\n#include \"scene.h\"\n"
               f"#include \"bgcheck.h\"\n#include \"romfile.h\"\n\nextern SceneCmd {SCENE}Commands[];\n"
               f"extern CollisionHeader {SCENE}CollisionHeader;\nextern RomFile {SCENE}RoomList[];\n"
               f"extern Spawn {SCENE}SpawnList[];\nextern ActorEntry {SCENE}PlayerEntryList[];\n"
               f"extern s16 {SCENE}ExitList[];\nextern EnvLightSettings {SCENE}LightSettings[];\n\n"
               f"// Collision memory for BgCheck_Allocate ({len(polys)} polys, {nodes} lookup nodes)\n"
               f"#define {MEMSIZE_MACRO} 0x{memsize:X}\n\n#endif\n")
    s = [hdr, f'#include "{SCENE}.h"\n#include "{ROOM}.h"\n', '#include "array_count.h"\n#include "actor.h"\n#include "actor_profile.h"\n'
         '#include "camera.h"\n#include "environment.h"\n#include "object.h"\n#include "player.h"\n#include "save.h"\n'
         '#include "segment_symbols.h"\n#include "sequence.h"\n#include "skybox.h"\n\n']
    s.append(f"SceneCmd {SCENE}Commands[] = {{\n"
             f"    SCENE_CMD_SOUND_SETTINGS(0, NATURE_ID_NONE, {MUSIC}),\n"
             f"    SCENE_CMD_ROOM_LIST(1, {SCENE}RoomList),\n"
             "    SCENE_CMD_MISC_SETTINGS(SCENE_CAM_TYPE_DEFAULT, WORLD_MAP_AREA_HYRULE_FIELD),\n"
             f"    SCENE_CMD_COL_HEADER(&{SCENE}CollisionHeader),\n"
             f"    SCENE_CMD_SPAWN_LIST({SCENE}SpawnList),\n"
             "    SCENE_CMD_SPECIAL_FILES(NAVI_QUEST_HINTS_NONE, OBJECT_GAMEPLAY_DANGEON_KEEP),\n"
             f"    SCENE_CMD_PLAYER_ENTRY_LIST({1 + len(EXTRA_SPAWNS)}, {SCENE}PlayerEntryList),\n"
             "    SCENE_CMD_SKYBOX_SETTINGS(SKYBOX_NONE, 0, LIGHT_MODE_SETTINGS),\n"
             f"    SCENE_CMD_EXIT_LIST({SCENE}ExitList),\n"
             f"    SCENE_CMD_ENV_LIGHT_SETTINGS(4, {SCENE}LightSettings),\n"
             "    SCENE_CMD_END(),\n};\n\n")
    s.append(f"RomFile {SCENE}RoomList[] = {{\n    ROM_FILE({ROOM}),\n}};\n\n")
    spawns = [(SPAWN[0], SPAWN[1], SPAWN[2], 0x8000)] + EXTRA_SPAWNS
    s.append(f"Spawn {SCENE}SpawnList[] = {{\n" + "".join(f"    {{ {k}, 0 }},\n" for k in range(len(spawns))) + "};\n\n")
    s.append(f"// Link drops in from the shaft, as into a grotto, facing the arch\nActorEntry {SCENE}PlayerEntryList[] = {{\n" +
             "".join(f"    {{ ACTOR_PLAYER, {{ {x}, {y}, {z} }}, {{ 0, 0x{yaw:04X}, 0 }}, "
                     "PLAYER_PARAMS(PLAYER_START_MODE_IDLE, PLAYER_START_BG_CAM_DEFAULT) },\n" for x, y, z, yaw in spawns) +
             "};\n\n")
    s.append(f"s16 {SCENE}ExitList[] = {{\n" + "".join(f"    {x},\n" for x in EXITS) + "};\n\n")
    s.append(light_settings())
    s.append(f"Vec3s {SCENE}CollisionVtx[] = {{\n" + "".join(f"    {{ {v[0]}, {v[1]}, {v[2]} }},\n" for v in verts) + "};\n\n")
    s.append(f"CollisionPoly {SCENE}CollisionPolys[] = {{\n" +
             "".join(f"    {{ {surf}, {{ COLPOLY_VTX({ids[0]}, 0), COLPOLY_VTX({ids[1]}, 0), {ids[2]} }}, "
                     f"{{ {n[0]}, {n[1]}, {n[2]} }}, {dist} }},\n" for surf, ids, n, dist, flags in polys) + "};\n\n")
    s.append(f"SurfaceType {SCENE}SurfaceTypes[] = {{\n" +
             "".join(f"    {{ {{ SURFACETYPE0(0, {sf[1]}, FLOOR_TYPE_0, 0, WALL_TYPE_0, "
                     f"{sf[2] if len(sf) > 2 else 'FLOOR_PROPERTY_0'}, false, false), "
                     f"SURFACETYPE1({sf[0]}, FLOOR_EFFECT_0, 0, 0, {sf[3] if len(sf) > 3 else 'false'}, "
                     "CONVEYOR_SPEED_DISABLED, 0, false) } },\n"
                     for sf in SURFACES) + "};\n\n")
    s.append(f"BgCamInfo {SCENE}BgCamList[] = {{\n    {{ CAM_SET_DUNGEON0, 0, NULL }},\n}};\n\n")
    water = ("0,\n    NULL", "")
    if WATERBOXES:
        water = (f"ARRAY_COUNT({SCENE}WaterBoxes),\n    {SCENE}WaterBoxes",
                 f"WaterBox {SCENE}WaterBoxes[] = {{\n" + "".join(
                     f"    {{ {x0}, {y}, {z0}, {x1 - x0}, {z1 - z0}, WATERBOX_PROPERTIES(0, 0, WATERBOX_ROOM_ALL, false) }},\n"
                     for x0, x1, z0, z1, y in WATERBOXES) + "};\n\n")
    s.append(water[1])
    s.append(f"CollisionHeader {SCENE}CollisionHeader = {{\n    {{ {lo[0]}, {lo[1]}, {lo[2]} }},\n    {{ {hi[0]}, {hi[1]}, {hi[2]} }},\n"
             f"    ARRAY_COUNT({SCENE}CollisionVtx),\n    {SCENE}CollisionVtx,\n    ARRAY_COUNT({SCENE}CollisionPolys),\n"
             f"    {SCENE}CollisionPolys,\n    {SCENE}SurfaceTypes,\n    {SCENE}BgCamList,\n    {water[0]},\n}};\n")
    (OUT / f"{SCENE}.h").write_text(scene_h)
    (OUT / f"{SCENE}.c").write_text("".join(s))
    (OUT / f"{TITLE_STEM}.c").write_text(
        hdr + '#include "ultra64.h"\n#include "versions.h"\n\n'
        "// Place name card, IA8 144x24: Japanese/English on NTSC, English/German/French on PAL.\n"
        f"u64 {TITLE_SYM}[] = {{\n"
        f'#include "{INC}/{TITLE_STEM}.ia8.inc.c"\n#include "{INC}/{TITLE_STEM}.ia8.inc.c"\n'
        f'#if OOT_PAL\n#include "{INC}/{TITLE_STEM}.ia8.inc.c"\n#endif\n}};\n')
    print(f"collision memory 0x{memsize:X} ({memsize // 1024} KB)")
    return len(polys), len(verts), entries, acts


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    keep = dict(L.TEXTURES)
    L.make_textures()  # (also writes the Plateau's title card under its name: replaced below)
    (OUT / "ancient_title.ia8.png").unlink(missing_ok=True)
    assert dict(L.TEXTURES) == keep
    title_card()
    build_chamber()
    build_hall()
    BY_NAME.update({e.name: e for e in ENTRIES})
    build_altar()
    build_ring()
    check_shots()
    npolys, nverts, entries, acts = write_sources()
    tris = sum(len(t) for e in ENTRIES for t in e.groups.values())
    mats = sum(len(e.groups) for e in ENTRIES)
    print(f"Ember Shrine: {len(ENTRIES)} room chunks, {tris} triangles, {mats} material groups, {npolys} collision "
          f"polys ({nverts} vertices), {len(acts)} actors")
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file"] + [str(p) for p in OUT.glob("*.[ch]")], cwd=REPO, check=True)


if __name__ == "__main__":
    main()
