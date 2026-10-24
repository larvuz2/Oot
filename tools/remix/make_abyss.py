#!/usr/bin/env python3
"""Generate the Shrine of the Swinging Abyss (Web Remix level 9): Ocarina of Time x Breath of the Wild, a Hookshot
challenge. First earn the Hookshot in a small stone room, then master it across an enormous bottomless chamber full of
moving platforms. Every moving platform has a Hookshot target, but not every target is safe to grapple.

  The stone room: the Hookshot in a chest behind bars. A floor switch in a trench opens the bars only while it is held;
  the stone cube can't be pushed across the trench (a curb). Push the cube onto the ramp, throw a stone at the crystal
  high on the north wall: the ramp rises, the cube slides over the curb into the trench onto the switch, the bars stay
  open. With the Hookshot in hand, the north door opens onto the abyss.

  The gauntlet (En_Remix_Abyss; the plan and its simulated timings in tools/remix/abyss_plan.py):
    1. the pendulum (target acquisition and timing)       2. the carousel (moving targets facing away; one cracked)
    3. the rising towers (vertical timing and range)       4. the vanishing target (a platform running into a tunnel)
    5. the crossing paths (one meeting point; or A carries Link into a wall)
    6. the clockwork storm: a swing, an elevator, a platform orbiting the central mechanism, and the last shot through
       the opening of the stone ring turning round the exit balcony. Decoys orbit too: their targets are cracked.
  A fall: half a second of black and Link is back at the start of the gauntlet, every platform back at the beginning.
  The hidden treasure: under the carousel a ledge whose target faces down; only from the first tower, low, looking up.

    python3 tools/remix/make_abyss_parts.py   # the pieces (and the plan's header) first
    python3 tools/remix/make_abyss.py         # writes assets/scenes/remix/abyss/ (committed)
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
import abyss_plan as A  # noqa: E402
import make_abyss_parts as AP  # noqa: E402  (the target's picture)

REPO = HERE.parents[1]
OUT = REPO / "assets/scenes/remix/abyss"
INC = "assets/scenes/remix/abyss"
SCENE, ROOM = "abyss_scene", "abyss_room_0"

TEXTURES = {
    "plaza": ("abyss_plaza", "ci4", (64, 64)),
    "techstone": ("abyss_techstone", "ci4", (64, 64)),
    "techrock": ("abyss_techrock", "ci4", (64, 64)),
    "runes": ("abyss_runes", "ci4", (64, 64)),
    "glow": ("abyss_glow", "i8", (32, 32)),
    "eye": ("abyss_eye", "i8", (64, 64)),
    "water": ("abyss_water", "rgba16", (32, 32)),
}
EXTRA_TEXTURES = {"target": ("abyss_target", "rgba16", (32, 32))}

TARGET = Mat("target", "target", "rgba16", (32, 32), repeat=60)
GOLD = Mat("gold", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x0B, scroll=True, repeat=150, clamp_t=True)
VOID = Mat("void", "techrock", "ci4", (64, 64), repeat=600)

SURF_FLOOR, SURF_WALL, SURF_EXIT, SURF_VOID, SURF_HOOK = range(5)
SURFACES = [("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 1),
            ("SURFACE_MATERIAL_STONE", 0, "FLOOR_PROPERTY_12"), ("SURFACE_MATERIAL_WOOD", 0, "FLOOR_PROPERTY_0", "true")]

R = A.ROOM
CH = dict(x=0, z=R["z1"] + 460, r=340, h=380)
CH_APO = CH["r"] * math.cos(math.pi / 8)
SPAWN = (0, 330, CH["z"])
PEDESTAL_EXIT = dict(x=0, z=CH["z"] + 200, r=75, h=14)
HALL = dict(x0=R["x0"], x1=R["x1"], z0=R["z0"], z1=R["z1"], h=R["h"])

ABYSS_ACTOR = "ACTOR_EN_REMIX_ABYSS"
CTRL, PLATFORM, RING, CUBE, RAMP, BARS, DOOR, EYE = range(8)


def ap(kind, arg=0):
    return f"0x{((arg & 0xFF) << 8) | kind:04X}"


def configure():
    L.OUT, L.INC, L.SCENE, L.ROOM = OUT, INC, SCENE, ROOM
    L.TEXTURES = dict(TEXTURES)
    L.ENTRIES.clear()
    L.COL_TRIS.clear()
    L.MESHES.clear()
    for k, v in dict(OUT=OUT, INC=INC, SCENE=SCENE, ROOM=ROOM, NAME="Shrine of the Swinging Abyss",
                     TITLE_STEM="abyss_title", TITLE_SYM="gAbyssShrineTitleCardTex",
                     MEMSIZE_MACRO="ABYSS_SCENE_BGCHECK_MEMSIZE", MUSIC="NA_BGM_ICE_CAVERN", SURFACES=SURFACES,
                     EXITS=["ENTR_RETURN_GROTTO"], SPAWN=SPAWN, HALL=HALL, CH=CH, CH_APO=CH_APO, PEDESTAL=PEDESTAL_EXIT,
                     OBJECTS=OBJECTS, actors=actors, room_defines=room_defines, EXTRA_ROOM_C=[], EXTRA_ENTRIES=[],
                     WATERBOXES=[],
                     LIGHT_ROW=("{ { 70, 70, 86 }, { 73, 73, 73 }, { 200, 196, 210 }, { -73, -73, -73 }, "
                                "{ 120, 100, 80 }, { 10, 12, 22 }, BLEND_RATE_AND_FOG_NEAR(4, 992), 6400 },\n"),
                     EXTRA_SPAWNS=[]).items():
        setattr(S, k, v)


# ---------------------------------------------------------------- textures


def dusk_palettes():
    """Old warm stone in the dark: sandstone greys, bronze runes."""
    ramp = {"plaza": ((70, 64, 60), (196, 184, 168)), "techstone": ((78, 72, 70), (180, 170, 158)),
            "techrock": ((30, 30, 36), (110, 104, 104)), "runes": ((80, 72, 66), (200, 188, 170))}
    for key, (lo, hi) in ramp.items():
        path = OUT / f"{TEXTURES[key][0]}.ci4.png"
        img = Image.open(path)
        idx = np.array(img)
        pal = np.array(img.getpalette()[: 16 * 3], float).reshape(-1, 3)
        lum = pal.mean(1, keepdims=True) / 255.0
        lum = (lum - lum.min()) / max(lum.max() - lum.min(), 1e-6)
        new = np.array(lo) + (np.array(hi) - np.array(lo)) * lum
        if key == "runes":
            new[lum[:, 0] > 0.8] = [255, 190, 90]
        L.write_indexed_png(path, idx, np.clip(new, 0, 255).round().astype(np.uint8))


def extra_textures():
    Image.fromarray(np.clip(AP.target(), 0, 255).round().astype(np.uint8)).convert("RGBA").save(
        OUT / "abyss_target.rgba16.png")
    L.TEXTURES.update(EXTRA_TEXTURES)


# ---------------------------------------------------------------- shapes


def wall_with_holes(e, mat, a, b, y0, y1, facing, holes, col=SURF_WALL):
    """A wall from a to b (x, z) with rectangular holes: (u0, u1, y0, y1) along it (u from a)."""
    a, b = np.array(a, float), np.array(b, float)
    length = np.linalg.norm(b - a)
    t = (b - a) / length
    us = sorted({0.0, length} | {h[0] for h in holes} | {h[1] for h in holes})
    ys = sorted({y0, y1} | {h[2] for h in holes} | {h[3] for h in holes})
    for ua, ub in zip(us, us[1:]):
        for ya, yb in zip(ys, ys[1:]):
            if any(h[0] <= ua and ub <= h[1] and h[2] <= ya and yb <= h[3] for h in holes):
                continue
            pa, pb = a + t * ua, a + t * ub
            wall(e, mat, tuple(pa), tuple(pb), ya, yb, facing, col=col, u0=ua)


def long_wall(e, mat, a, b, y0, y1, facing, step=700.0):
    """A long wall in pieces (each starts its texture over: the coordinates stay small)."""
    a, b = np.array(a, float), np.array(b, float)
    n = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
    for k in range(n):
        p, q = a + (b - a) * k / n, a + (b - a) * (k + 1) / n
        wall(e, mat, tuple(p), tuple(q), y0, y1, facing)


def block(e, x0, x1, y0, y1, z0, z1, top=FLOOR, side=WALL, bottom=True, skip=()):
    """A solid stone block (its underside a ceiling)."""
    box(e, x0, x1, y0, y1, z0, z1, top=top, side=side, skip=skip)
    if bottom:
        flat(e, DARK, x0, x1, z0, z1, y0, up=False, col=SURF_WALL)


def octagon_pillar(e, cx, cz, r, y0, y1, mat=WALL, col=SURF_WALL, n=8):
    L.prism(e, mat, r, r, y0, y1, n, cap=False, center=(cx, cz), col=col)


def target_ring(e, cx, cz, r, y, n=8):
    """Target emblems round a pillar of radius r (their faces a Hookshot surface)."""
    for k in range(n):
        a = 2 * math.pi * (k + 0.5) / n
        f = (math.sin(a), 0, math.cos(a))
        rr = r * math.cos(math.pi / n) + 1.5
        MT.quad_on(e, TARGET, (cx + f[0] * rr, y, cz + f[2] * rr), (math.cos(a), 0, -math.sin(a)), (0, 1, 0), 48, 48, f)


# ---------------------------------------------------------------- the stone room


def build_room():
    e = L.new_entry("room")
    x0, x1, z0, z1, h = R["x0"], R["x1"], R["z0"], R["z1"], R["h"]
    t, rp, cu = A.TRENCH, A.RAMP, A.CURB
    rx0, rx1 = rp["x"] - rp["w"] / 2, rp["x"] + rp["w"] / 2
    floor = sbox(x0, z0, x1, z1).difference(sbox(t["x0"], t["z0"], x1 + 1, t["z1"])).difference(
        sbox(rx0, rp["z0"], rx1, rp["z1"])).difference(sbox(rx0, cu["z0"], rx1, cu["z1"]))
    MT.floor_geom(e, FLOOR, floor, 0)
    # the trench (its switch is Obj_Switch), the ramp's recess, the curb
    d = -t["depth"]
    flat(e, FLOOR, t["x0"], x1, t["z0"], t["z1"], d)
    wall(e, WALL, (t["x0"], t["z0"]), (x1, t["z0"]), d, 0, (0, 0, 1))
    wall(e, WALL, (x1, t["z1"]), (t["x0"], t["z1"]), d, 0, (0, 0, -1))
    wall(e, WALL, (t["x0"], t["z1"]), (t["x0"], t["z0"]), d, 0, (1, 0, 0))
    flat(e, DARK, rx0, rx1, rp["z0"], rp["z1"], -22)
    wall(e, WALL, (rx0, rp["z0"]), (rx1, rp["z0"]), -22, 0, (0, 0, 1))
    wall(e, WALL, (rx1, rp["z0"]), (rx1, rp["z1"]), -22, 0, (-1, 0, 0))
    wall(e, WALL, (rx0, rp["z1"]), (rx0, rp["z0"]), -22, 0, (1, 0, 0))
    box(e, rx0, rx1, 0, cu["h"], cu["z0"], cu["z1"], top=DARK)
    wall(e, WALL, (rx0, cu["z1"]), (rx1, cu["z1"]), d, 0, (0, 0, 1))  # (the curb's face down into the trench)
    ring_line(e, EMBER, A.SWITCH[0], A.SWITCH[1], 46, d, n=12, width=6)
    # walls: north (the door to the abyss, the crystal), east, west, south (the arch, the bars' alcove)
    dw = A.DOOR
    wall_with_holes(e, WALL, (x0, z0), (x1, z0), 0, h, (0, 0, 1), [(dw["x"] - dw["w"] / 2 - x0,
                                                                   dw["x"] + dw["w"] / 2 - x0, 0, dw["h"])])
    wall(e, WALL, (x1, z1), (x1, z0), d, h, (-1, 0, 0))
    wall(e, WALL, (x0, z0), (x0, z1), 0, h, (1, 0, 0))
    al = A.ALCOVE
    holes = [(x1 - S.ARCH_HALF, x1 + S.ARCH_HALF, 0, S.ARCH_H), (x1 - al["x1"], x1 - al["x0"], 0, 160)]
    wall_with_holes(e, WALL, (x1, z1), (x0, z1), 0, h, (0, 0, -1), holes)
    flat(e, DARK, x0, x1, z0, z1, h, up=False, col=None)
    # the alcove behind the bars
    flat(e, FLOOR, al["x0"], al["x1"], al["z0"], al["z1"], 0)
    flat(e, DARK, al["x0"], al["x1"], al["z0"], al["z1"], 160, up=False, col=None)
    wall(e, WALL, (al["x1"], al["z0"]), (al["x1"], al["z1"]), 0, 160, (-1, 0, 0))
    wall(e, WALL, (al["x0"], al["z1"]), (al["x0"], al["z0"]), 0, 160, (1, 0, 0))
    wall(e, WALL, (al["x1"], al["z1"]), (al["x0"], al["z1"]), 0, 160, (0, 0, -1))
    S.beam(e, A.CHEST_HOOK[0], A.CHEST_HOOK[1], 40, 60, 0, 156, planes=2)
    # the crystal's bracket high on the north wall, the throwing spot, light lines
    cx, cy, cz = A.CRYSTAL
    box(e, cx - 30, cx + 30, cy - 46, cy - 30, z0, z0 + 40, top=DARK)
    wall_line(e, GOLD, [(cx - 50, cy - 50, z0 + 1), (cx - 50, cy + 50, z0 + 1), (cx + 50, cy + 50, z0 + 1),
                        (cx + 50, cy - 50, z0 + 1), (cx - 50, cy - 50, z0 + 1)], (0, 0, 1), width=8)
    ring_line(e, GOLD, A.THROW_SPOT[0], A.THROW_SPOT[1], 40, 0, n=16, width=6)
    floor_line(e, GLOW, [(0, z1 - 20), (0, z0 + 60)], width=10)
    for x in (x0 + 2, x1 - 2):
        f = (1, 0, 0) if x < 0 else (-1, 0, 0)
        wall_line(e, GLOW, [(x, 200, z0), (x, 200, z1)], f, width=8)
    rune_panel(e, (x0 + 1, 120, 500), (1, 0, 0), 100, 100)
    rune_panel(e, (dw["x"], dw["h"] + 60, z0 + 1), (0, 0, 1), 90, 60)


# ---------------------------------------------------------------- the abyss


def build_abyss_shell():
    e = L.new_entry("abyss_shell")
    ab = A.ABYSS
    x0, x1, z0, z1, fy, cy = ab["x0"], ab["x1"], ab["z0"], ab["z1"], ab["floor"], ab["ceil"]
    flat(e, VOID, x0, x1, z0, z1, fy, col=SURF_VOID)  # (a fall ends long before: En_Remix_Abyss)
    flat(e, DARK, x0, x1, z0, z1, cy, up=False, col=SURF_WALL)
    long_wall(e, WALL, (x0, z0), (x1, z0), fy, cy, (0, 0, 1))
    long_wall(e, WALL, (x1, z1), (x1, z0), fy, cy, (-1, 0, 0))
    long_wall(e, WALL, (x0, z0), (x0, z1), fy, cy, (1, 0, 0))
    dw = A.DOOR
    long_wall(e, WALL, (x1, z1), (dw["w"] / 2, z1), fy, cy, (0, 0, -1))
    long_wall(e, WALL, (-dw["w"] / 2, z1), (x0, z1), fy, cy, (0, 0, -1))
    wall(e, WALL, (dw["w"] / 2, z1), (-dw["w"] / 2, z1), fy, 0, (0, 0, -1))
    wall(e, WALL, (dw["w"] / 2, z1), (-dw["w"] / 2, z1), dw["h"], cy, (0, 0, -1))
    # bands of light down the walls, fading into the dark
    for y in (-200, 300, 800, 1300):
        wall_line(e, GLOW, [(x1 - 2, y, z1), (x1 - 2, y, z0)], (-1, 0, 0), width=10)
        wall_line(e, GLOW, [(x0 + 2, y, z0), (x0 + 2, y, z1)], (1, 0, 0), width=10)
    for z in np.arange(z1 - 400, z0, -600):
        for x, f in ((x0, (1, 0, 0)), (x1, (-1, 0, 0))):
            rune_panel(e, (x + f[0], 600, z), f, 140, 140)
    # the start ledge, the door's frame
    s = A.START
    block(e, s["x0"], s["x1"], s["top"] - 200, s["top"], s["z0"], s["z1"], skip=("s",))
    floor_line(e, GOLD, [(s["x0"] + 16, s["z0"] + 14), (s["x1"] - 16, s["z0"] + 14)], width=8)
    wall_line(e, GOLD, [(-dw["w"] / 2 - 14, 0, z1 - 1), (-dw["w"] / 2 - 14, dw["h"] + 14, z1 - 1),
                        (dw["w"] / 2 + 14, dw["h"] + 14, z1 - 1), (dw["w"] / 2 + 14, 0, z1 - 1)], (0, 0, -1), width=10)


def build_gauntlet():
    e = L.new_entry("gauntlet")
    # the pendulums' pivots: an iron beam each, hung from the ceiling
    for i in (A.I_P1, A.I_S6):
        px, py, pz = A.P[i]["pivot"]
        hd = A.P[i]["d"] / 2
        box(e, px - 16, px + 16, py, py + 30, pz - hd, pz + hd, top=DARK, side=DARK)
        box(e, px - 10, px + 10, py + 30, A.ABYSS["ceil"], pz - 10, pz + 10, top=DARK, side=DARK)
    # the carousel's column, the hidden ledge under it (and the flange over the ledge: its target faces down)
    cx, cz = A.CAROUSEL
    octagon_pillar(e, cx, cz, 70, A.ABYSS["floor"], A.CAROUSEL_TOP + 220)
    L.prism(e, DARK, 90, 90, A.CAROUSEL_TOP + 220, A.CAROUSEL_TOP + 250, 8, cap=True, cap_mat=DARK, center=(cx, cz),
            col=SURF_WALL)
    ring_line(e, GOLD, cx, cz, 92, A.CAROUSEL_TOP + 251, n=8, width=6)
    hd = A.HIDDEN
    hx, hz = cx + math.sin(A.HIDDEN_DIR) * hd["r"], cz + math.cos(A.HIDDEN_DIR) * hd["r"]
    q = hd["size"] / 2
    block(e, hx - q, hx + q, hd["top"] - 30, hd["top"], hz - q, hz + q)
    fl = hd["flange_y"]
    box(e, hx - q, hx + q, fl, fl + 20, hz - q, hz + q, top=DARK, side=DARK)
    flat(e, DARK, hx - q, hx + q, hz - q, hz + q, fl, up=False, col=SURF_HOOK)
    MT.quad_on(e, TARGET, (hx, fl - 1, hz), (1, 0, 0), (0, 0, 1), 56, 56, (0, -1, 0))
    for y0, y1 in ((hd["top"], fl),):  # an arm from the column out to the ledge, and posts
        ax, az = cx + math.sin(A.HIDDEN_DIR) * 80, cz + math.cos(A.HIDDEN_DIR) * 80
        for t in np.linspace(0, 1, 6):
            px_, pz_ = ax + (hx - ax) * t, az + (hz - az) * t
            box(e, px_ - 9, px_ + 9, fl + 20, fl + 34, pz_ - 9, pz_ + 9, top=DARK, side=DARK)
        for sx in (-1, 1):
            box(e, hx + sx * (q - 8) - 4, hx + sx * (q - 8) + 4, y0, y1, hz - 4, hz + 4, top=DARK, side=DARK)
    # the tunnel the shuttle runs through
    t = A.TUNNEL
    block(e, t["x0"], t["px0"], t["y0"], t["y1"], t["z0"], t["z1"])
    block(e, t["px1"], t["x1"], t["y0"], t["y1"], t["z0"], t["z1"])
    block(e, t["px0"], t["px1"], t["y0"], t["py0"], t["z0"], t["z1"])
    block(e, t["px0"], t["px1"], t["py1"], t["y1"], t["z0"], t["z1"])
    for z in (t["z0"], t["z1"]):
        f = (0, 0, -1) if z == t["z0"] else (0, 0, 1)
        wall_line(e, GOLD, [(t["px0"] - 10, t["py0"], z + f[2]), (t["px0"] - 10, t["py1"] + 10, z + f[2]),
                            (t["px1"] + 10, t["py1"] + 10, z + f[2]), (t["px1"] + 10, t["py0"], z + f[2])], f, width=8)
    # rails (seen, not touched): the shuttle's, A's and B's
    sh = A.P[A.I_SH]
    for x in (A.SHUTTLE_X - 40, A.SHUTTLE_X + 40):
        box(e, x - 5, x + 5, A.SHUTTLE_TOP - 60, A.SHUTTLE_TOP - 50, sh["b"][2] - 140, sh["a"][2] + 140, top=DARK,
            side=DARK, col_top=None, col_side=None)
    a_, b_ = A.P[A.I_A], A.P[A.I_B]
    box(e, a_["b"][0] - 80, a_["a"][0] + 80, 560 - 60, 560 - 50, -2125, -2115, top=DARK, side=DARK, col_top=None,
        col_side=None)
    box(e, -405, -395, 660 - 60, 660 - 50, b_["b"][2] - 80, b_["a"][2] + 80, top=DARK, side=DARK, col_top=None,
        col_side=None)
    # the rest ledges, the lintel A carries Link into
    for ld in (A.LEDGE4, A.LEDGE5):
        block(e, ld["x0"], ld["x1"], ld["top"] - 160, ld["top"], ld["z0"], ld["z1"])
        floor_line(e, GOLD, [(ld["x0"] + 14, (ld["z0"] + ld["z1"]) / 2), (ld["x1"] - 14, (ld["z0"] + ld["z1"]) / 2)],
                   width=6, y=ld["top"])
    li = A.LINTEL
    block(e, li["x0"], li["x1"], li["y0"], li["y1"], li["z0"], li["z1"], top=DARK)
    wall_line(e, EMBER, [(li["x1"] + 1, li["y0"] + 10, li["z0"]), (li["x1"] + 1, li["y0"] + 10, li["z1"])], (1, 0, 0),
              width=10)


def build_core():
    """The clockwork storm's central mechanism, the exit balcony on top, its pillar of targets."""
    e = L.new_entry("core")
    cx, cz = A.CORE
    b = A.BALCONY_TOP
    L.prism(e, WALL, A.CORE_R, A.CORE_R, A.ABYSS["floor"], b - 40, 16, cap=False, center=(cx, cz), col=SURF_WALL)
    L.prism(e, WALL, A.CORE_R, A.BALCONY_R, b - 40, b, 16, cap=False, center=(cx, cz), col=SURF_WALL)
    fan(e, FLOOR, (cx, b, cz), S.ngon(cx, cz, A.BALCONY_R, 16, b), col=SURF_FLOOR)
    for y in (-600, -200, 200, 600):  # the mechanism's gears: rings of light turning (scrolling)
        ring_line(e, GOLD, cx, cz, A.CORE_R + 2, y, n=16, width=14)
        strip(e, GOLD, [(cx + (A.CORE_R + 1.5) * math.sin(2 * math.pi * k / 16), y + 40,
                         cz + (A.CORE_R + 1.5) * math.cos(2 * math.pi * k / 16)) for k in range(16)],
              [(math.sin(2 * math.pi * k / 16), 0, math.cos(2 * math.pi * k / 16)) for k in range(16)], 10, lift=0.5,
              closed=True)
    pl = A.PILLAR
    octagon_pillar(e, cx, cz, pl["r"], b, pl["top"], mat=WALL, col=SURF_HOOK)
    L.prism(e, DARK, pl["r"] + 8, pl["r"] + 8, pl["top"], pl["top"] + 16, 8, cap=True, cap_mat=DARK, center=(cx, cz),
            col=SURF_WALL)
    target_ring(e, cx, cz, pl["r"], (b + pl["top"]) / 2)
    S.beam(e, cx, cz, pl["r"] + 20, pl["r"] + 60, pl["top"] + 16, A.ABYSS["ceil"] - 4, planes=2)
    # the way out: a pad of light
    ex, ey, ez = A.EXIT_PAD
    L.prism(e, DARK, 46, 46, b, b + 6, 12, cap=False, col=SURF_WALL, center=(ex, ez))
    fan(e, FLOOR, (ex, b + 6, ez), S.ngon(ex, ez, 46, 12, b + 6), col=SURF_EXIT)
    ring_line(e, GLOW, ex, ez, 38, b + 6, n=12, width=8)


# ---------------------------------------------------------------- actors


def actors():
    a = []
    cz = CH["z"]
    a.append(("ACTOR_EN_COW", -CH_APO + 105, 0, cz, 0, 0x4000, 0, "0"))
    for sx in (-1, 1):
        a.append(("ACTOR_OBJ_SYOKUDAI", sx * 170, 0, cz - CH_APO + 70, 0, 0, 0, "0x0400"))
    a.append((ABYSS_ACTOR, 0, 0, 0, 0, 0, 0, ap(CTRL)))
    # the stone room
    c0 = A.CUBE_CELLS[0]
    a.append((ABYSS_ACTOR, c0[0], 0, c0[1], 0, 0, 0, ap(CUBE)))
    a.append((ABYSS_ACTOR, A.RAMP["x"], 0, A.RAMP["z1"], 0, 0, 0, ap(RAMP)))
    a.append((ABYSS_ACTOR, A.BARS["x"], 0, A.BARS["z"], 0, 0, 0, ap(BARS)))
    a.append((ABYSS_ACTOR, A.DOOR["x"], 0, A.ROOM["z0"], 0, 0, 0, ap(DOOR)))
    cx, cy, cz_ = A.CRYSTAL
    a.append((ABYSS_ACTOR, cx, cy, cz_ + 25, 0, 0, 0, ap(EYE)))
    a.append(("ACTOR_OBJ_SWITCH", cx, cy - 30, cz_ + 22, 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_CRYSTAL, OBJSWITCH_SUBTYPE_SYNC, {A.FLAG_RAMP})"))
    a.append(("ACTOR_OBJ_SWITCH", A.SWITCH[0], -A.TRENCH["depth"], A.SWITCH[1], 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_FLOOR, OBJSWITCH_SUBTYPE_HOLD, {A.FLAG_BARS})"))
    for x, z in A.ROCKS:
        a.append(("ACTOR_EN_ISHI", x, 0, z, 0, 0, 0, "0x0000"))
    a.append(("ACTOR_EN_BOX", A.CHEST_HOOK[0], 0, A.CHEST_HOOK[1], 0, 0, 0,
              f"(ENBOX_TYPE_BIG_DEFAULT << 12) | (GI_HOOKSHOT << 5) | {A.T_HOOK}"))
    # the gauntlet: the platforms (each places itself), the ring, the treasures
    for i in range(len(A.P)):
        x, y, z, _ = A.pos(A.P[i], 0)
        a.append((ABYSS_ACTOR, x, y, z, 0, 0, 0, ap(PLATFORM, i)))
    a.append((ABYSS_ACTOR, A.CORE[0], A.RING["y0"], A.CORE[1], 0, 0, 0, ap(RING)))
    hx, hz = A.CHEST_HIDDEN
    yaw = int((A.HIDDEN_DIR + math.pi) / (2 * math.pi) * 0x10000) & 0xFFFF
    a.append(("ACTOR_EN_BOX", hx, A.HIDDEN["top"], hz, 0, yaw, 0,
              f"(ENBOX_TYPE_SMALL << 12) | (GI_HEART_PIECE << 5) | {A.T_HIDDEN}"))
    a.append(("ACTOR_EN_BOX", A.CHEST_HEART[0], A.BALCONY_TOP, A.CHEST_HEART[1], 0, 0x8000, 0,
              f"(ENBOX_TYPE_BIG_DEFAULT << 12) | (GI_HEART_CONTAINER << 5) | {A.T_HEART}"))
    return a


OBJECTS = ["OBJECT_SYOKUDAI", "OBJECT_COW", "OBJECT_BOX", "OBJECT_REMIX_ABYSS", "OBJECT_GAMEPLAY_FIELD_KEEP"]


def room_defines():
    x0, y0, z0, _ = A.pos(A.P[A.I_C[0]], 8)
    ex, ez = A.P[A.I_E]["at"]
    tx, tz = A.THROW_SPOT
    return ("// The flags the test boots set, where they put Link (z_remix_level.c): at the throwing spot facing the\n"
            "// crystal (a stone before him, the cube on the ramp); on the start ledge with the Hookshot; dropped onto a\n"
            "// carousel platform; dropped onto the clockwork storm's elevator\n"
            f"#define ABYSS_SHRINE_FLAG_CUBE_RAMP {A.FLAG_CUBE_RAMP}\n#define ABYSS_SHRINE_T_HOOK {A.T_HOOK}\n"
            f"#define ABYSS_TEST_PUZZLE_X {tx}.0f\n#define ABYSS_TEST_PUZZLE_Z {tz}.0f\n"
            f"#define ABYSS_TEST_START_X {A.RESPAWN[0]}.0f\n#define ABYSS_TEST_START_Y {A.RESPAWN[1]}.0f\n"
            f"#define ABYSS_TEST_START_Z {A.RESPAWN[2]}.0f\n"
            f"#define ABYSS_TEST_RIDE_X {x0:.1f}f\n#define ABYSS_TEST_RIDE_Y {y0 + 80:.1f}f\n#define ABYSS_TEST_RIDE_Z {z0:.1f}f\n"
            f"#define ABYSS_TEST_FINAL_X {ex}.0f\n#define ABYSS_TEST_FINAL_Y 1030.0f\n#define ABYSS_TEST_FINAL_Z {ez}.0f\n\n")


def check_layout():
    """The stone room's puzzle, the hidden target seen only from below, the timings (abyss_plan.check)."""
    for line in A.check():
        print("  " + line)
    # the crystal: too high for the sword (the adult reaches about 110 with a jump), within a throw's arc
    assert A.CRYSTAL[1] - 30 > 110
    tx, tz = A.THROW_SPOT
    d = tz - A.CRYSTAL[2]
    assert 60 < d < 140, "the throwing spot isn't where a stone's arc meets the crystal"
    # the cube: across the trench only by the ramp (the curb is higher than nothing)
    assert A.CURB["h"] >= 25 and A.RAMP["lift"] > A.CURB["h"]
    assert A.CUBE_CELLS[1][1] + A.CUBE / 2 <= A.RAMP["z1"]
    # the hidden target: from tower 1 at its lowest, looking up; never from above
    t1 = A.P[A.I_T[0]]
    cx, cz = A.CAROUSEL
    hx, hz = cx + math.sin(A.HIDDEN_DIR) * A.HIDDEN["r"], cz + math.cos(A.HIDDEN_DIR) * A.HIDDEN["r"]
    tx_, tz_ = t1["at"]
    dist = math.hypot(math.hypot(hx - tx_, hz - tz_) - A.HIDDEN["size"] / 2, A.HIDDEN["flange_y"] - (t1["lo"] + A.CHEST_Y))
    assert dist < A.HOOK, f"the hidden target is out of reach from tower 1 ({dist:.0f})"
    assert t1["lo"] + A.CHEST_Y < A.HIDDEN["flange_y"] - 40
    assert A.CAROUSEL_TOP - 30 > A.HIDDEN["flange_y"] + 60, "the carousel runs into the flange"
    print("make_abyss: the stone room, the hidden target and every grapple's timing checked")


def main():
    configure()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    L.make_textures()
    (OUT / "ancient_title.ia8.png").unlink(missing_ok=True)
    dusk_palettes()
    extra_textures()
    S.title_card("Swinging Abyss")
    S.build_chamber()
    build_room()
    build_abyss_shell()
    build_gauntlet()
    build_core()
    check_layout()
    npolys, nverts, entries, acts = S.write_sources()
    tris = sum(len(t) for e in L.ENTRIES + L.MESHES for t in e.groups.values())
    print(f"Shrine of the Swinging Abyss: {len(entries)} room chunks, {tris} triangles, {npolys} collision polys "
          f"({nverts} vertices), {len(acts)} actors")
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file"] + [str(p) for p in OUT.glob("*.[ch]")], cwd=REPO, check=True)


if __name__ == "__main__":
    main()
