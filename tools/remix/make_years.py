#!/usr/bin/env python3
"""Generate the Shrine of Seven Years (Web Remix level 7): the Temple of Time's language (pale stone floors, tall
pillars, stained-glass windows, the Master Sword's pedestal, the Door of Time), and behind the pedestal one puzzle
chamber in two timelines. No items: the Master Sword's pedestal is the only place time turns (place the sword: the
child seven years ago; draw it: the adult). What the child changes, seven years age naturally.

  1. The small door. An aperture in the west wall, too small for the adult. The child crawls in, finds a stone cube
     and pushes it out through the hole into the chamber; in the future it is still there.
  2. The seven-year block. The garden's wall has fallen into a mound of rubble in the future; the adult pushes the
     cube against it and climbs over. In the past the wall stands, with a doorway only the child fits through.
  3. The growing tree. In the garden the child moves a sapling's planter between three marks; seven years later a tree
     stands there and its branch reaches whatever is near: the upper floor (from the north mark), a ledge with a
     chest (the west mark), nothing (the middle). The adult climbs its ivy.
  4. The broken staircase. The final staircase, from the upper floor up to the exit, is whole in the past and broken in
     the future, unless the child pushed the stone support under its middle. (The child reaches the upper floor by
     the east stairs, rotted away in the future.)
  5. The solution is behind you. The exit door has no handle: "Only the one who has never left may open the way."
     Through the narrow opening beside it a floor switch can be seen; only the child fits. Pressed, the door opens and
     stays open, but the reward stands too high for the child: the adult claims it.
  6. The hidden treasure. A crack in the east wall (the past) leads the child into an alcove: "A treasure buried today
     is a treasure discovered tomorrow." Lift the loose stone, drop the golden medallion (from the little room behind
     the small door) into the hole under it. Seven years later roots seal the alcove; the adult pushes them aside:
     a chest stands where the medallion was buried.

    python3 tools/remix/make_years_parts.py  # the pieces (and the plan's header) first
    python3 tools/remix/make_years.py        # writes assets/scenes/remix/years/ (committed)
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_shrine as S  # noqa: E402
from make_shrine import (L, Mat, strip, wall, flat, box, ngon, fan, floor_line, wall_line, ring_line,  # noqa: E402
                         rune_panel, eye_emblem, FLOOR, WALL, DARK, GLOW, EMBER, EYE)
import make_time as MT  # noqa: E402  (shapes: floor_geom, quad_on, ring_line_wall)
import years_plan as Y  # noqa: E402

REPO = HERE.parents[1]
OUT = REPO / "assets/scenes/remix/years"
INC = "assets/scenes/remix/years"
SCENE, ROOM = "years_scene", "years_room_0"

TEXTURES = {
    "plaza": ("years_plaza", "ci4", (64, 64)),
    "techstone": ("years_techstone", "ci4", (64, 64)),
    "techrock": ("years_techrock", "ci4", (64, 64)),
    "runes": ("years_runes", "ci4", (64, 64)),
    "glow": ("years_glow", "i8", (32, 32)),
    "eye": ("years_eye", "i8", (64, 64)),
    "water": ("years_water", "rgba16", (32, 32)),
}
EXTRA_TEXTURES = {"glass": ("years_glass", "rgba16", (32, 32)), "tri": ("years_tri", "i8", (64, 64))}

ERA = Mat("era", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x0B, scroll=True, repeat=150, clamp_t=True)
GLASS = Mat("glass", "glass", "rgba16", (32, 32), lit=False, xlu=True, prim=(255, 255, 255, 215), repeat=120)
TRI = Mat("tri", "tri", "i8", (64, 64), lit=False, xlu=True, prim=(255, 215, 110, 230))
BEAMY = Mat("sunbeam", "glow", "i8", (32, 32), lit=False, xlu=True, prim=(255, 250, 225, 70), scroll=True, repeat=400,
            clamp_t=True)

SURF_FLOOR, SURF_WALL, SURF_EXIT, SURF_VOID = range(4)
SURFACES = [("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 1),
            ("SURFACE_MATERIAL_STONE", 0, "FLOOR_PROPERTY_12")]

CH = dict(x=0, z=Y.HALL_Z1 + 360, r=340, h=380)
CH_APO = CH["r"] * math.cos(math.pi / 8)
SPAWN = (0, 330, CH["z"])
PEDESTAL_EXIT = dict(x=0, z=CH["z"] + 200, r=75, h=14)
HALL = dict(x0=-Y.HALL_X, x1=Y.HALL_X, z0=Y.Z0, z1=Y.HALL_Z1, h=Y.HALL_H)

YEARS_ACTOR = "ACTOR_EN_REMIX_YEARS"
YEARS_PEDESTAL, YEARS_PUSH, YEARS_ERA, YEARS_NARROW, YEARS_CARRY, YEARS_SECRET, YEARS_TABLET, YEARS_DOOR = range(8)


def yp(kind, arg=0):
    return f"0x{((arg & 0xFF) << 8) | kind:04X}"


def configure():
    L.OUT, L.INC, L.SCENE, L.ROOM = OUT, INC, SCENE, ROOM
    L.TEXTURES = dict(TEXTURES)
    L.ENTRIES.clear()
    L.COL_TRIS.clear()
    L.MESHES.clear()
    sx, sy, sz = Y.SPAWN_AT_PEDESTAL
    for k, v in dict(OUT=OUT, INC=INC, SCENE=SCENE, ROOM=ROOM, NAME="Shrine of Seven Years", TITLE_STEM="years_title",
                     TITLE_SYM="gYearsShrineTitleCardTex", MEMSIZE_MACRO="YEARS_SCENE_BGCHECK_MEMSIZE",
                     MUSIC="NA_BGM_TEMPLE_OF_TIME", SURFACES=SURFACES, EXITS=["ENTR_RETURN_GROTTO"], SPAWN=SPAWN,
                     HALL=HALL, CH=CH, CH_APO=CH_APO, PEDESTAL=PEDESTAL_EXIT, OBJECTS=OBJECTS, actors=actors,
                     room_defines=room_defines, EXTRA_ROOM_C=[], EXTRA_ENTRIES=[], WATERBOXES=[],
                     LIGHT_ROW=("{ { 96, 96, 104 }, { 73, 73, 73 }, { 240, 236, 225 }, { -73, -73, -73 }, "
                                "{ 120, 130, 160 }, { 46, 44, 52 }, BLEND_RATE_AND_FOG_NEAR(4, 990), 4600 },\n"),
                     EXTRA_SPAWNS=[(sx, sy, sz, 0x8000), (sx, sy, sz, 0x8000)]).items():
        setattr(S, k, v)


# ---------------------------------------------------------------- textures


def marble_palettes():
    """The Temple of Time's pale stone."""
    ramp = {"plaza": ((96, 94, 96), (236, 234, 230)), "techstone": ((110, 106, 104), (226, 222, 214)),
            "techrock": ((64, 62, 66), (170, 166, 162)), "runes": ((100, 96, 92), (230, 226, 218))}
    for key, (lo, hi) in ramp.items():
        path = OUT / f"{TEXTURES[key][0]}.ci4.png"
        img = Image.open(path)
        idx = np.array(img)
        pal = np.array(img.getpalette()[: 16 * 3], float).reshape(-1, 3)
        lum = pal.mean(1, keepdims=True) / 255.0
        lum = (lum - lum.min()) / max(lum.max() - lum.min(), 1e-6)
        new = np.array(lo) + (np.array(hi) - np.array(lo)) * lum
        if key == "runes":
            new[lum[:, 0] > 0.8] = [255, 210, 110]  # gold inlay
        L.write_indexed_png(path, idx, np.clip(new, 0, 255).round().astype(np.uint8))


def glass_texture():
    """Stained glass: lead lines round coloured panes."""
    rng = np.random.default_rng(4)
    cols = [(60, 110, 230), (230, 60, 60), (240, 200, 60), (70, 170, 90), (150, 80, 200)]
    img = np.zeros((32, 32, 4))
    for by in range(0, 32, 8):
        for bx in range(0, 32, 8):
            c = cols[rng.integers(0, len(cols))]
            img[by:by + 8, bx:bx + 8, :3] = c
            img[by:by + 8, bx:bx + 8, 3] = 255
    img[::8, :, :3] = 30
    img[:, ::8, :3] = 30
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA")


def triforce_texture(size):
    from PIL import ImageDraw
    S_ = size * 8
    im = Image.new("L", (S_, S_), 0)
    d = ImageDraw.Draw(im)
    h = S_ * 0.42
    for cx, cy in ((S_ / 2, S_ / 2 - h / 2), (S_ / 2 - h / 2, S_ / 2 + h / 2), (S_ / 2 + h / 2, S_ / 2 + h / 2)):
        d.polygon([(cx, cy - h / 2), (cx - h / 2, cy + h / 2), (cx + h / 2, cy + h / 2)], fill=255)
    return im.resize((size, size), Image.LANCZOS)


def extra_textures():
    glass_texture().save(OUT / "years_glass.rgba16.png")
    triforce_texture(64).save(OUT / "years_tri.i8.png")
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


def opening_frame(e, mat, center, along, facing, w, h, depth):
    """The sides and top of a doorway cut through a wall (depth towards -facing)."""
    c, al, f = np.array(center, float), np.array(along, float), np.array(facing, float)
    for s in (-1, 1):
        p = c + al * s * w / 2
        q = p - f * depth
        wall(e, mat, (p[0], p[2]), (q[0], q[2]), 0 if center[1] == 0 else center[1], center[1] + h, tuple(-al * s))
    flat_quad = [c - al * w / 2 + (0, h, 0), c + al * w / 2 + (0, h, 0), c + al * w / 2 + (0, h, 0) - f * depth,
                 c - al * w / 2 + (0, h, 0) - f * depth]
    L.quad(e, mat, flat_quad, [L.planar_uv(mat, p) for p in flat_quad], [(0, -1, 0)] * 4, (0, -1, 0), SURF_WALL)


def window(e, x, z, facing, y0=240, y1=600, w=120):
    """A tall stained-glass window on a wall (facing into the room) with a shaft of light."""
    f = np.array(facing, float)
    along = np.cross((0, 1, 0), f)
    c = np.array([x, (y0 + y1) / 2, z]) + f * 1.5
    MT.quad_on(e, GLASS, tuple(c), tuple(along), (0, 1, 0), w, y1 - y0, tuple(f))
    top = [c - along * w / 2 + (0, (y1 - y0) / 2, 0), c + along * w / 2 + (0, (y1 - y0) / 2, 0)]
    wall_line(e, GLOW, [tuple(top[0] - (0, y1 - y0, 0)), tuple(top[0]), tuple(top[1]), tuple(top[1] - (0, y1 - y0, 0))],
              tuple(f), width=10)


def pillar(e, x, z, h, r=40):
    L.prism(e, WALL, r + 8, r + 8, 0, 30, 8, cap=True, cap_mat=FLOOR, center=(x, z), col=SURF_WALL)
    L.prism(e, WALL, r, r, 30, h - 40, 8, cap=False, center=(x, z), col=SURF_WALL)
    L.prism(e, WALL, r + 10, r + 10, h - 40, h, 8, cap=False, center=(x, z), col=SURF_WALL)


# ---------------------------------------------------------------- the hall of the Master Sword


def build_sword_hall():
    e = L.new_entry("sword_hall")
    hx, z0, z1, h = Y.HALL_X, Y.HALL_Z0, Y.HALL_Z1, Y.HALL_H
    flat(e, FLOOR, -hx, hx, z0, z1, 0)
    for x, f in ((hx, (-1, 0, 0)), (-hx, (1, 0, 0))):
        a, b = ((x, z1), (x, z0)) if x > 0 else ((x, z0), (x, z1))
        wall(e, WALL, a, b, 0, h, f)
        for z in (130, 350, 570):
            window(e, x, z, f)
        for z in (20, 240, 460, 680):
            pillar(e, x - f[0] * 50, z, h - 60, r=34)
    # the south wall (the arrival corridor comes through its arch: build_chamber), the north wall's arch
    wall(e, WALL, (hx, z1), (S.ARCH_HALF, z1), 0, h, (0, 0, -1))
    wall(e, WALL, (-S.ARCH_HALF, z1), (-hx, z1), 0, h, (0, 0, -1))
    wall(e, WALL, (S.ARCH_HALF, z1), (-S.ARCH_HALF, z1), S.ARCH_H, h, (0, 0, -1))
    wall_with_holes(e, WALL, (-hx, z0), (hx, z0), 0, h, (0, 0, 1), [(hx - Y.ARCH_X, hx + Y.ARCH_X, 0, Y.ARCH_H)])
    wall_with_holes(e, WALL, (Y.X1, z0), (Y.X0, z0), 0, Y.H, (0, 0, -1),
                    [(Y.X1 - Y.ARCH_X, Y.X1 + Y.ARCH_X, 0, Y.ARCH_H)])  # (its other face: the chamber's south wall)
    MT.quad_on(e, TRI, (0, Y.ARCH_H + 110, z0 + 2), (1, 0, 0), (0, 1, 0), 150, 150, (0, 0, 1))
    wall_line(e, GLOW, [(-Y.ARCH_X - 16, 0, z0 + 2), (-Y.ARCH_X - 16, Y.ARCH_H + 16, z0 + 2),
                        (Y.ARCH_X + 16, Y.ARCH_H + 16, z0 + 2), (Y.ARCH_X + 16, 0, z0 + 2)], (0, 0, 1), width=12)
    flat(e, DARK, -hx, hx, z0, z1, h, up=False, col=None)
    # the dais (two steps) and a shaft of light onto the pedestal
    px, pz = Y.PEDESTAL
    r, dh = Y.DAIS_R, Y.DAIS_H
    L.prism(e, WALL, r + 40, r + 40, 0, dh / 2, 16, cap=True, cap_mat=FLOOR, center=(px, pz), col=SURF_WALL)
    L.prism(e, WALL, r, r, dh / 2, dh, 16, cap=True, cap_mat=FLOOR, center=(px, pz), col=SURF_WALL)
    ring_line(e, ERA, px, pz, r - 14, dh, n=24, width=10)
    ring_line(e, GLOW, px, pz, r + 26, dh / 2, n=24, width=8)
    S.beam(e, px, pz, 70, 110, dh, h - 4, planes=2)
    # a path of light from the arrival arch to the dais, and on to the Door of Time
    floor_line(e, ERA, [(0, z1 - 20), (0, pz + r + 50)], width=14)
    floor_line(e, ERA, [(0, pz - r - 50), (0, z0 + 20)], width=14)


# ---------------------------------------------------------------- the puzzle chamber


def build_chamber_floor():
    e = L.new_entry("floor")
    flat(e, FLOOR, Y.X0, Y.X1, Y.Z0, Y.Z1, 0)
    for x in np.arange(Y.X0 + 200, Y.X1, 200):
        floor_line(e, GLOW, [(x, Y.Z1 - 30), (x, Y.UPPER_Z + 30)], width=6)
    # the ceiling
    flat(e, DARK, Y.X0, Y.X1, Y.Z0, Y.Z1, Y.H, up=False, col=None)
    for x in (-400, 0, 400):
        strip(e, GLOW, [(x, Y.H, Y.Z0), (x, Y.H, Y.Z1)], [(0, -1, 0)] * 2, 14, lift=1.2)
    # the marks: the cube's way, the planter's three places, the support's places
    for (x, z) in Y.CUBE_CELLS[2:]:
        ring_line(e, ERA, x, z, 40, 0, n=4, width=6)
    for k, (x, z) in enumerate(Y.PLANTER_CELLS):
        ring_line(e, EMBER if k != 1 else ERA, x, z, 56, 0, n=12, width=8)
    for k, (x, z) in enumerate(Y.SUPPORT_CELLS):
        ring_line(e, EMBER if k == len(Y.SUPPORT_CELLS) - 1 else ERA, x, z, 46, Y.UPPER_Y, n=4, width=6)


def build_chamber_walls():
    e = L.new_entry("walls")
    X0, X1, Z0, Z1, H = Y.X0, Y.X1, Y.Z0, Y.Z1, Y.H
    ap, cr, d, sl, lz = Y.APERTURE, Y.CRACK, Y.DOOR, Y.SLIT, Y.LANDING
    # west: the small aperture to the little room
    wall_with_holes(e, WALL, (X0, Z0), (X0, Z1), 0, H, (1, 0, 0),
                    [(ap["z"] - ap["w"] / 2 - Z0, ap["z"] + ap["w"] / 2 - Z0, 0, ap["h"])])
    # east: the alcove's opening (the past's cracked wall, the future's roots, fill it)
    wall_with_holes(e, WALL, (X1, Z1), (X1, Z0), 0, H, (-1, 0, 0),
                    [(Z1 - cr["z"] - cr["w"] / 2, Z1 - cr["z"] + cr["w"] / 2, 0, cr["h"])])
    # north: the exit door and the narrow opening beside it, up on the landing
    wall_with_holes(e, WALL, (X1, Z0), (X0, Z0), 0, H, (0, 0, 1),
                    [(X1 - d["x1"], X1 - d["x0"], lz["top"], lz["top"] + d["y1"]),
                     (X1 - sl["x1"], X1 - sl["x0"], lz["top"], lz["top"] + sl["h"])])
    for z in np.arange(Z0 + 150, Z1 - 100, 300):
        for x, f in ((X0, (1, 0, 0)), (X1, (-1, 0, 0))):
            if abs(z - cr["z"]) < 140 or abs(z - ap["z"]) < 120:
                continue
            pillar(e, x + f[0] * 45, z, H - 80, r=36)
    for z in (-650, -1150):
        window(e, X0, z, (1, 0, 0), y0=420, y1=860, w=140)
        window(e, X1, z, (-1, 0, 0), y0=420, y1=860, w=140)
    window(e, -300, Z0, (0, 0, 1), y0=520, y1=900, w=160)
    MT.quad_on(e, TRI, ((d["x0"] + d["x1"]) / 2, lz["top"] + d["y1"] + 90, Z0 + 2), (1, 0, 0), (0, 1, 0), 120, 120,
               (0, 0, 1))
    wall_line(e, ERA, [(d["x0"] - 14, lz["top"], Z0 + 2), (d["x0"] - 14, lz["top"] + d["y1"] + 14, Z0 + 2),
                       (d["x1"] + 14, lz["top"] + d["y1"] + 14, Z0 + 2), (d["x1"] + 14, lz["top"], Z0 + 2)], (0, 0, 1),
              width=12)
    wall_line(e, GLOW, [(X0 + 2, 300, Z0), (X0 + 2, 300, Z1)], (1, 0, 0), width=10)
    wall_line(e, GLOW, [(X1 - 2, 300, Z1), (X1 - 2, 300, Z0)], (-1, 0, 0), width=10)


def build_upper():
    """The upper floor, the exit landing, the reward room behind the door, the columns under the upper floor."""
    e = L.new_entry("upper")
    uz, uy = Y.UPPER_Z, Y.UPPER_Y
    box(e, Y.X0, Y.X1, uy - 30, uy, Y.Z0, uz, top=FLOOR, skip=("n",))
    floor_line(e, GLOW, [(Y.X0 + 20, uz + 14), (Y.X1 - 20, uz + 14)], width=8, y=uy)
    for x in (-150, 350):
        pillar(e, x, uz + 40, uy - 30, r=34)
    lz = Y.LANDING
    box(e, lz["x0"], lz["x1"], uy, lz["top"], lz["z0"], lz["z1"], top=FLOOR, skip=("n", "e"))
    floor_line(e, ERA, [(lz["x0"] + 20, lz["z1"] - 16), (lz["x1"] - 20, lz["z1"] - 16)], width=8, y=lz["top"])
    # the reward room
    r = Y.REWARD
    flat(e, FLOOR, r["x0"], r["x1"], r["z0"], r["z1"], lz["top"])
    flat(e, DARK, r["x0"], r["x1"], r["z0"], r["z1"], r["ceil"], up=False, col=None)
    wall(e, WALL, (r["x1"], r["z1"]), (r["x1"], r["z0"]), lz["top"], r["ceil"], (-1, 0, 0))
    wall(e, WALL, (r["x0"], r["z0"]), (r["x0"], r["z1"]), lz["top"], r["ceil"], (1, 0, 0))
    wall(e, WALL, (r["x0"], r["z0"]), (r["x1"], r["z0"]), lz["top"], r["ceil"], (0, 0, 1))
    d, sl = Y.DOOR, Y.SLIT
    wall_with_holes(e, WALL, (r["x0"], r["z1"]), (r["x1"], r["z1"]), lz["top"], r["ceil"], (0, 0, -1),
                    [(d["x0"] - r["x0"], d["x1"] - r["x0"], lz["top"], lz["top"] + d["y1"]),
                     (sl["x0"] - r["x0"], sl["x1"] - r["x0"], lz["top"], lz["top"] + sl["h"])])
    pl = Y.PLINTH
    box(e, pl["x"] - pl["w"] / 2, pl["x"] + pl["w"] / 2, lz["top"], lz["top"] + pl["h"], r["z0"] + 20, r["z0"] + 220,
        top=FLOOR)
    window(e, pl["x"], r["z0"], (0, 0, 1), y0=lz["top"] + 130, y1=r["ceil"] - 30, w=120)
    S.beam(e, pl["x"], r["z0"] + 120, 60, 90, lz["top"] + pl["h"], r["ceil"] - 4, planes=2)
    ring_line(e, EMBER, Y.FLOOR_SWITCH[0], Y.FLOOR_SWITCH[1], 44, lz["top"], n=12, width=6)
    # the west ledge (the tree's other branch)
    wl = Y.WEST_LEDGE
    box(e, wl["x0"], wl["x1"], wl["top"] - 30, wl["top"], wl["z0"], wl["z1"], top=FLOOR, skip=("w",))


def build_garden():
    """The garden's east wall (its south wall is an actor: it falls in seven years) and its ivy."""
    e = L.new_entry("garden")
    g = Y.GARDEN
    gx = g["x1"]
    for f, a, b in (((1, 0, 0), (gx, g["z0"]), (gx, g["z1"])), ((-1, 0, 0), (gx, g["z1"]), (gx, g["z0"]))):
        wall(e, WALL, a, b, 0, Y.UPPER_Y, f)
    wall(e, WALL, (gx, Y.Z0), (gx, g["z0"]), 0, Y.UPPER_Y - 30, (-1, 0, 0))
    wall(e, WALL, (gx, g["z0"]), (gx, Y.Z0), 0, Y.UPPER_Y - 30, (1, 0, 0))
    flat(e, WALL, gx - 15, gx + 15, g["z0"], g["z1"], Y.UPPER_Y, col=SURF_WALL)
    for z in np.arange(g["z0"] + 100, g["z1"], 160):
        wall_line(e, EMBER, [(gx + 2, 40, z), (gx + 2, Y.UPPER_Y - 40, z)], (1, 0, 0), width=8)


def build_side_rooms():
    """The little room behind the small door, the alcove behind the crack."""
    e = L.new_entry("rooms")
    c, ap = Y.CRAWL_ROOM, Y.APERTURE
    flat(e, FLOOR, c["x0"], c["x1"], c["z0"], c["z1"], 0)
    flat(e, DARK, c["x0"], c["x1"], c["z0"], c["z1"], c["ceil"], up=False, col=None)
    wall(e, WALL, (c["x0"], c["z0"]), (c["x0"], c["z1"]), 0, c["ceil"], (1, 0, 0))
    wall(e, WALL, (c["x1"], c["z0"]), (c["x0"], c["z0"]), 0, c["ceil"], (0, 0, 1))
    wall(e, WALL, (c["x0"], c["z1"]), (c["x1"], c["z1"]), 0, c["ceil"], (0, 0, -1))
    wall_with_holes(e, WALL, (c["x1"], c["z1"]), (c["x1"], c["z0"]), 0, c["ceil"], (-1, 0, 0),
                    [(c["z1"] - ap["z"] - ap["w"] / 2, c["z1"] - ap["z"] + ap["w"] / 2, 0, ap["h"])])
    flat(e, DARK, c["x1"] - 1, c["x1"] + 1, ap["z"] - ap["w"] / 2, ap["z"] + ap["w"] / 2, ap["h"], up=False)
    ring_line(e, ERA, Y.MEDALLION[0], Y.MEDALLION[1], 26, 0, n=10, width=6)
    a, cr = Y.ALCOVE, Y.CRACK
    flat(e, FLOOR, a["x0"], a["x1"], a["z0"], a["z1"], 0)
    flat(e, DARK, a["x0"], a["x1"], a["z0"], a["z1"], a["ceil"], up=False, col=None)
    wall(e, WALL, (a["x1"], a["z1"]), (a["x1"], a["z0"]), 0, a["ceil"], (-1, 0, 0))
    wall(e, WALL, (a["x0"], a["z0"]), (a["x1"], a["z0"]), 0, a["ceil"], (0, 0, 1))
    wall(e, WALL, (a["x1"], a["z1"]), (a["x0"], a["z1"]), 0, a["ceil"], (0, 0, -1))
    wall_with_holes(e, WALL, (a["x0"], a["z0"]), (a["x0"], a["z1"]), 0, a["ceil"], (1, 0, 0),
                    [(cr["z"] - cr["w"] / 2 - a["z0"], cr["z"] + cr["w"] / 2 - a["z0"], 0, cr["h"])])
    ring_line(e, EMBER, Y.CAVITY[0], Y.CAVITY[1], 34, 0, n=4, width=6)


# ---------------------------------------------------------------- actors


def actors():
    a = []
    cz = CH["z"]
    a.append(("ACTOR_EN_COW", -CH_APO + 105, 0, cz, 0, 0x4000, 0, "0"))
    for sx in (-1, 1):
        a.append(("ACTOR_OBJ_SYOKUDAI", sx * 170, 0, cz - CH_APO + 70, 0, 0, 0, "0x0400"))
    px, pz = Y.PEDESTAL
    a.append((YEARS_ACTOR, px, Y.DAIS_H, pz, 0, 0, 0, yp(YEARS_PEDESTAL)))
    a.append((YEARS_ACTOR, *Y.CUBE_CELLS[0][:1], 0, Y.CUBE_CELLS[0][1], 0, 0, 0, yp(YEARS_PUSH, 0)))
    a.append((YEARS_ACTOR, Y.PLANTER_CELLS[1][0], 0, Y.PLANTER_CELLS[1][1], 0, 0, 0, yp(YEARS_PUSH, 1)))
    a.append((YEARS_ACTOR, Y.SUPPORT_CELLS[0][0], Y.UPPER_Y, Y.SUPPORT_CELLS[0][1], 0, 0, 0, yp(YEARS_PUSH, 2)))
    a.append((YEARS_ACTOR, Y.GARDEN_DOOR["x"], 0, (Y.RUBBLE["z0"] + Y.RUBBLE["z1"]) / 2, 0, 0, 0, yp(YEARS_ERA, 0)))
    e = Y.EAST_STAIRS
    a.append((YEARS_ACTOR, (e["x0"] + e["x1"]) / 2, 0, e["z0"], 0, 0, 0, yp(YEARS_ERA, 1)))
    a.append((YEARS_ACTOR, Y.X1, 0, Y.CRACK["z"], 0, 0x4000, 0, yp(YEARS_ERA, 2)))
    s = Y.STAIRS
    a.append((YEARS_ACTOR, s["x0"], Y.UPPER_Y, (s["z0"] + s["z1"]) / 2, 0, 0, 0, yp(YEARS_ERA, 3)))
    a.append((YEARS_ACTOR, Y.X0, 0, Y.APERTURE["z"], 0, 0, 0, yp(YEARS_NARROW)))
    a.append((YEARS_ACTOR, (Y.SLIT["x0"] + Y.SLIT["x1"]) / 2, Y.LANDING["top"], Y.Z0, 0, 0, 0, yp(YEARS_NARROW)))
    a.append((YEARS_ACTOR, Y.MEDALLION[0], 0, Y.MEDALLION[1], 0, 0, 0, yp(YEARS_CARRY, 0)))
    a.append((YEARS_ACTOR, Y.CAVITY[0], 0, Y.CAVITY[1], 0, 0, 0, yp(YEARS_CARRY, 1)))
    a.append((YEARS_ACTOR, Y.CAVITY[0], 0, Y.CAVITY[1], 0, 0x4000, 0, yp(YEARS_SECRET)))
    a.append((YEARS_ACTOR, 250, 0, 520, 0, 0, 0, yp(YEARS_TABLET, 0)))  # the entrance: how time turns here
    a.append((YEARS_ACTOR, Y.LANDING["x0"] + 45, Y.LANDING["top"], -1710, 0, 0x4000, 0, yp(YEARS_TABLET, 1)))
    a.append((YEARS_ACTOR, Y.ALCOVE["x1"] - 22, 0, Y.CAVITY[1] + 60, 0, 0xC000, 0, yp(YEARS_TABLET, 2)))
    d = Y.DOOR
    a.append((YEARS_ACTOR, (d["x0"] + d["x1"]) / 2, Y.LANDING["top"], Y.Z0, 0, 0, 0, yp(YEARS_DOOR)))
    a.append(("ACTOR_OBJ_SWITCH", Y.FLOOR_SWITCH[0], Y.LANDING["top"], Y.FLOOR_SWITCH[1], 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_FLOOR, OBJSWITCH_SUBTYPE_ONCE, {Y.FLAG_DOOR})"))
    pl = Y.PLINTH
    a.append(("ACTOR_EN_BOX", pl["x"], Y.LANDING["top"] + pl["h"], Y.REWARD["z0"] + 80, 0, 0x8000, 0,
              f"(ENBOX_TYPE_BIG_DEFAULT << 12) | (GI_HEART_CONTAINER << 5) | {Y.T_HEART}"))
    wl = Y.WEST_LEDGE
    a.append(("ACTOR_EN_BOX", (wl["x0"] + wl["x1"]) / 2, wl["top"], (wl["z0"] + wl["z1"]) / 2, 0, 0xC000, 0,
              f"(ENBOX_TYPE_SMALL << 12) | (GI_RUPEE_RED << 5) | {Y.T_LEDGE}"))
    return a


OBJECTS = ["OBJECT_SYOKUDAI", "OBJECT_COW", "OBJECT_BOX", "OBJECT_REMIX_YEARS"]


def room_defines():
    s = Y.STAIRS
    return ("// Where the future test boot puts Link: on the upper floor, before the final staircase (z_remix_level.c)\n"
            f"#define YEARS_TEST_UPPER_X {s['x0'] - 160}.0f\n#define YEARS_TEST_UPPER_Y {Y.UPPER_Y}.0f\n"
            f"#define YEARS_TEST_UPPER_Z {(s['z0'] + s['z1']) / 2:.0f}.0f\n"
            "// Switch flags the test boot sets (the planter by the upper floor, the support under the stairs, the cube\n"
            "// against the rubble, the door open): each place is stored as its cell + 1\n"
            f"#define YEARS_SHRINE_FLAG_DOOR {Y.FLAG_DOOR}\n#define YEARS_SHRINE_FLAG_CUBE 0x{Y.FLAG_CUBE:02X}\n"
            f"#define YEARS_SHRINE_FLAG_PLANTER 0x{Y.FLAG_PLANTER:02X}\n"
            f"#define YEARS_SHRINE_FLAG_SUPPORT 0x{Y.FLAG_SUPPORT:02X}\n"
            f"#define YEARS_SHRINE_CUBE_LAST {len(Y.CUBE_CELLS)}\n#define YEARS_SHRINE_PLANTER_NORTH {len(Y.PLANTER_CELLS)}\n"
            f"#define YEARS_SHRINE_SUPPORT_UNDER {len(Y.SUPPORT_CELLS)}\n\n")


def check_layout():
    """What the shrine relies on: the adult climbs about 100, the child about 50 (a cube's height), a running jump
    carries about 157; the adult is 56 tall, the child 40 (the openings are 64: the adult is kept out by a block)."""
    adult_climb, child_climb, jump = 100, 50, 157
    assert Y.RUBBLE["h"] > adult_climb + 30, "the adult could climb the rubble without the cube"
    assert Y.RUBBLE["h"] - Y.CUBE <= adult_climb, "the cube is too low a step"
    assert Y.RUBBLE["step_h"] <= adult_climb and Y.RUBBLE["h"] - Y.RUBBLE["step_h"] <= adult_climb
    assert Y.PLINTH["h"] > child_climb + 20 and Y.PLINTH["h"] <= adult_climb
    assert Y.UPPER_Y > adult_climb * 2, "the upper floor could be climbed"
    run = (Y.STAIRS["x1"] - Y.STAIRS["x0"]) / Y.STAIRS["steps"]
    assert run * len(Y.BROKEN_STEPS) > jump + 10, "the broken stairs could be jumped"
    sx, sz = Y.SUPPORT_CELLS[-1]
    k = (sx - Y.STAIRS["x0"]) / run
    assert Y.BROKEN_STEPS[0] <= k <= Y.BROKEN_STEPS[-1] + 1, "the support isn't under the broken part"
    assert Y.STAIRS["z0"] < sz < Y.STAIRS["z1"]
    # the cube's way: through the aperture (cube narrower than the hole), then against the rubble
    assert Y.CUBE < Y.APERTURE["w"] - 6 and Y.CUBE < Y.APERTURE["h"]
    assert Y.CUBE_CELLS[1][0] == Y.X0
    assert Y.RUBBLE["z1"] < Y.CUBE_CELLS[-1][1] - Y.CUBE / 2 < Y.RUBBLE["z1"] + 10
    # the tree's branch (60 out from the trunk's 35) reaches the upper floor from the north mark only
    reach = 35 + 70
    nx, nz = Y.PLANTER_CELLS[2]
    assert nz - reach < Y.UPPER_Z, "the tree by the upper floor doesn't reach it"
    for x, z in Y.PLANTER_CELLS[:2]:
        assert z - reach > Y.UPPER_Z + 40
    wx, wz = Y.PLANTER_CELLS[0]
    assert wx - reach < Y.WEST_LEDGE["x1"] and Y.WEST_LEDGE["z0"] < wz < Y.WEST_LEDGE["z1"]
    print("make_years: the rubble, the cube, the plinth, the broken stairs and the tree's branches checked")


def main():
    configure()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    L.make_textures()
    (OUT / "ancient_title.ia8.png").unlink(missing_ok=True)
    marble_palettes()
    extra_textures()
    S.title_card("Shrine of Seven Years")
    S.build_chamber()
    build_sword_hall()
    build_chamber_floor()
    build_chamber_walls()
    build_upper()
    build_garden()
    build_side_rooms()
    check_layout()
    npolys, nverts, entries, acts = S.write_sources()
    tris = sum(len(t) for e in L.ENTRIES + L.MESHES for t in e.groups.values())
    print(f"Shrine of Seven Years: {len(entries)} room chunks, {tris} triangles, {npolys} collision polys "
          f"({nverts} vertices), {len(acts)} actors")
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file"] + [str(p) for p in OUT.glob("*.[ch]")], cwd=REPO, check=True)


if __name__ == "__main__":
    main()
