#!/usr/bin/env python3
"""Generate the Temple of Two Truths (Web Remix level 6): one enormous round hall in sandstone, the way the Spirit
Temple's are, seen in two eras. Everything is in view from the entrance: the bottomless pit and the dais in its middle
under a hanging hourglass and its three turning rings, the golden sphere on its pedestal, ring 1 (a stone band round
the dais), four unlit torches at different heights, a waterfall flowing upwards, the basin where the sun comes
through the ceiling onto an old block, the great statue in the north wall (a locked mouth, an empty eye), the scale
by its shoulder, the clock whose hand points to CHILD or ADULT, two identical pads on the dais (blue, orange).

The Song of Time on the clock-plate in the middle of the dais takes Link between the two eras (TIME ECHO): what he
moves in the past stays moved in the present; some things grow there (a block becomes a pillar), some decay (a bridge,
a ramp), some don't change. The trial, in five phases (En_Remix_Time does the moving parts, the game's switches,
torches and chest the rest; see REMIX.md):

  I    Hookshot to the lintel over the sphere: landing on the dais sinks its pedestal and the sphere falls into the pit
       (it comes back). Strike the crystal under the pedestal (boomerang, an arrow) to lock it, then push the sphere:
       it rolls down the curved track into ring 1's cradle, the plate there starts the ring, the sphere is trapped.
  II   Four timed torches stand round the dais at different heights (8 seconds each); the ring's four openings line up
       with them at different times. Longshot onto the dais and cast Din's Fire: all four burn, the waterfall turns,
       water fills the pit and the basin, the sphere floats up in a bubble into the statue's head.
  III  The sun falls on the old block in the basin: under water, worn, far too heavy for the adult. "What cannot be
       moved today may be moved yesterday": as a child (dry basin, a small block) push it into the sunbeam; back in
       the present it has grown into a pillar under the light with a mirror on top. The mirror throws the light onto
       the walkway; turn it with the Mirror Shield onto the sun symbol above the way out: the statue's mouth opens.
  IV   Inside: a gap (longshot or hover boots), stairs, a narrow bridge to the first eye. The sphere waits above a
       grate; the hammer switch drops it onto the eye's plate: the eye lights, the way out opens, a second eye opens
       on the forehead. "You have opened the way. But have you understood the truth?" The sphere returns to its
       pedestal; the chest stays shut.
  V    As a child move the mirror block out of the drain (the water won't rise in the present). Send a Bombchu down
       the dais's side onto the crystal only a blast wakes: ring 1 turns backwards, and throws the sphere (no water
       to lift it now) onto the scale's right pan by the high platform. Hookshot up there: the floor switch drops the
       stone weight onto the left pan, the right pan lifts the sphere towards the second eye but stops short. As a
       child push a small block onto the left pan: in the present it has grown into a pillar, heavy enough to tip the
       scale all the way: the sphere rolls into the second eye, the statue awakes, the rings line up, the chest falls.

  The seed: in the past the sphere is a golden seed the child can carry. Plant it in the first eye (a ramp up the
  statue stands in the past), and in the present turn the sunlight onto it: it grows into the sphere and the eye
  opens, phases I-IV solved another way.

    python3 tools/remix/make_time_parts.py   # the pieces (and the plan's header) first
    python3 tools/remix/make_time.py         # writes assets/scenes/remix/time/ (committed)
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import shapely
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point, Polygon, box as sbox

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_shrine as S  # noqa: E402
from make_shrine import (L, Mat, strip, unit, wall, flat, box, ngon, fan, floor_line, wall_line, ring_line,  # noqa: E402
                         rune_panel, eye_emblem, FLOOR, WALL, DARK, RUNES, GLOW, EMBER, EYE)
import time_plan as T  # noqa: E402

REPO = HERE.parents[1]
OUT = REPO / "assets/scenes/remix/time"
INC = "assets/scenes/remix/time"
SCENE, ROOM = "time_scene", "time_room_0"

TEXTURES = {
    "plaza": ("time_plaza", "ci4", (64, 64)),
    "techstone": ("time_techstone", "ci4", (64, 64)),
    "techrock": ("time_techrock", "ci4", (64, 64)),
    "runes": ("time_runes", "ci4", (64, 64)),
    "glow": ("time_glow", "i8", (32, 32)),
    "eye": ("time_eye", "i8", (64, 64)),
    "water": ("time_water", "rgba16", (32, 32)),
}
EXTRA_TEXTURES = {  # drawn here (make_level's make_textures only knows the ones above)
    "clock": ("time_clock", "i8", (64, 64)),
    "child": ("time_label_child", "i8", (64, 16)),
    "adult": ("time_label_adult", "i8", (64, 16)),
    "sun": ("time_sun", "i8", (64, 64)),
}

ERA = Mat("era", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x0B, scroll=True, repeat=150, clamp_t=True)
EYE1L = Mat("eye1", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x09, scroll=True, repeat=150, clamp_t=True)
ALIVEL = Mat("alive", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x0A, scroll=True, repeat=150, clamp_t=True)
FALLS = Mat("falls", "water", "rgba16", (32, 32), lit=False, xlu=True, prim=(255, 255, 255, 190), scroll=0x0E,
            repeat=160, combine="water")
CLOCK = Mat("clock", "clock", "i8", (64, 64), lit=False, xlu=True, prim=(255, 215, 120, 235), repeat=2 * T.CLOCK_R)
CHILD = Mat("child", "child", "i8", (64, 16), lit=False, xlu=True, prim=(90, 180, 255, 255))
ADULT = Mat("adult", "adult", "i8", (64, 16), lit=False, xlu=True, prim=(255, 160, 60, 255))
SUNM = Mat("sun", "sun", "i8", (64, 64), lit=False, xlu=True, prim_seg=0x0C)
BLUE_PAD = Mat("bluepad", "glow", "i8", (32, 32), lit=False, xlu=True, prim=(90, 180, 255, 230), scroll=True, repeat=150,
               clamp_t=True)
ORANGE_PAD = Mat("orangepad", "glow", "i8", (32, 32), lit=False, xlu=True, prim=(255, 160, 60, 230), scroll=True,
                 repeat=150, clamp_t=True)

SURF_FLOOR, SURF_WALL, SURF_EXIT, SURF_VOID, SURF_HOOK = range(5)
SURFACES = [("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 1),
            ("SURFACE_MATERIAL_STONE", 0, "FLOOR_PROPERTY_12"),
            ("SURFACE_MATERIAL_STONE", 0, "FLOOR_PROPERTY_0", "true")]

R, H = T.R, T.H
CH = dict(x=0, z=1340, r=340, h=380)
CH_APO = CH["r"] * math.cos(math.pi / 8)
SPAWN = (0, 330, CH["z"])
PEDESTAL_EXIT = dict(x=0, z=CH["z"] + 200, r=75, h=14)
HALL = dict(x0=-R, x1=R, z0=-R, z1=990, h=H)  # (build_chamber's corridor starts at z1)
DOOR_HALF, DOOR_H = 110, 250
EXIT_RING_R = 62
HOOK_PILLARS = [35, 210, 325]  # phi of the hookshot pillars at the walkway's edge
HOOK_PILLAR_R, HOOK_PILLAR_W, HOOK_PILLAR_H = 625, 70, 340

TIME_ACTOR = "ACTOR_EN_REMIX_TIME"
(TIME_CONTROLLER, TIME_SPHERE, TIME_PEDESTAL, TIME_RING, TIME_ECHO, TIME_PAN, TIME_WEIGHT, TIME_BRIDGE, TIME_RAMP,
 TIME_TABLET, TIME_BLAST, TIME_DOOR) = range(12)


def tp(kind, arg=0):
    return f"0x{((arg & 0xFF) << 8) | kind:04X}"


def configure():
    L.OUT, L.INC, L.SCENE, L.ROOM = OUT, INC, SCENE, ROOM
    L.TEXTURES = dict(TEXTURES)
    L.ENTRIES.clear()
    L.COL_TRIS.clear()
    L.MESHES.clear()
    x0, x1, z0, z1 = T.WATERBOX
    for k, v in dict(OUT=OUT, INC=INC, SCENE=SCENE, ROOM=ROOM, NAME="Temple of Two Truths", TITLE_STEM="time_title",
                     TITLE_SYM="gTimeShrineTitleCardTex", MEMSIZE_MACRO="TIME_SCENE_BGCHECK_MEMSIZE",
                     MUSIC="NA_BGM_SPIRIT_TEMPLE", SURFACES=SURFACES, EXITS=["ENTR_RETURN_GROTTO"], SPAWN=SPAWN,
                     HALL=HALL, CH=CH, CH_APO=CH_APO, PEDESTAL=PEDESTAL_EXIT, OBJECTS=OBJECTS, actors=actors,
                     room_defines=room_defines, EXTRA_ROOM_C=[], EXTRA_ENTRIES=[],
                     WATERBOXES=[(x0, x1, z0, z1, T.WATER_LOW)],
                     LIGHT_ROW=("{ { 118, 96, 72 }, { 73, 73, 73 }, { 255, 228, 180 }, { -73, -73, -73 }, "
                                "{ 120, 96, 80 }, { 70, 50, 34 }, BLEND_RATE_AND_FOG_NEAR(4, 990), 4200 },\n"),
                     EXTRA_SPAWNS=[(T.BLUE_PAD[0], 0, T.BLUE_PAD[1], 0x8000),
                                   (T.ORANGE_PAD[0], 0, T.ORANGE_PAD[1], 0x8000)]).items():
        setattr(S, k, v)


# ---------------------------------------------------------------- textures


def sand_palettes():
    """The game-style stone textures, recoloured to the Spirit Temple's warm sandstone."""
    ramp = {"plaza": ((112, 82, 52), (255, 232, 186)), "techstone": ((128, 88, 54), (255, 214, 156)),
            "techrock": ((70, 50, 36), (196, 150, 104)), "runes": ((110, 80, 52), (255, 224, 172))}
    for key, (lo, hi) in ramp.items():
        stem = TEXTURES[key][0]
        path = OUT / f"{stem}.ci4.png"
        img = Image.open(path)
        idx = np.array(img)
        pal = np.array(img.getpalette()[: 16 * 3], float).reshape(-1, 3)
        lum = pal.mean(1, keepdims=True) / 255.0
        lum = (lum - lum.min()) / max(lum.max() - lum.min(), 1e-6)
        new = np.array(lo) + (np.array(hi) - np.array(lo)) * lum
        if key == "runes":  # the glyphs (brightest entries) glow turquoise, the Sheikah way
            bright = lum[:, 0] > 0.8
            new[bright] = [120, 230, 255]
        L.write_indexed_png(path, idx, np.clip(new, 0, 255).round().astype(np.uint8))


def text_texture(text, w, h):
    SS = 4
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(h * 0.8) * SS)
    big = Image.new("L", (w * SS, h * SS), 0)
    d = ImageDraw.Draw(big)
    bb = d.textbbox((0, 0), text, font=font)
    d.text(((w * SS - (bb[2] - bb[0])) / 2 - bb[0], (h * SS - (bb[3] - bb[1])) / 2 - bb[1]), text, font=font, fill=255)
    return big.resize((w, h), Image.LANCZOS)


def clock_texture(size):
    SS = 8
    S_ = size * SS
    img = Image.new("L", (S_, S_), 0)
    d = ImageDraw.Draw(img)
    c = S_ / 2
    d.ellipse([S_ * 0.03, S_ * 0.03, S_ * 0.97, S_ * 0.97], outline=255, width=int(S_ * 0.05))
    d.ellipse([S_ * 0.14, S_ * 0.14, S_ * 0.86, S_ * 0.86], outline=160, width=int(S_ * 0.015))
    for k in range(12):
        a = 2 * math.pi * k / 12
        r0, r1 = S_ * (0.33 if k % 3 == 0 else 0.37), S_ * 0.42
        d.line([(c + r0 * math.sin(a), c - r0 * math.cos(a)), (c + r1 * math.sin(a), c - r1 * math.cos(a))],
               fill=255, width=int(S_ * (0.04 if k % 3 == 0 else 0.02)))
    d.ellipse([c - S_ * 0.08, c - S_ * 0.08, c + S_ * 0.08, c + S_ * 0.08], outline=200, width=int(S_ * 0.02))
    return img.resize((size, size), Image.LANCZOS)


def sun_texture(size):
    SS = 8
    S_ = size * SS
    img = Image.new("L", (S_, S_), 0)
    d = ImageDraw.Draw(img)
    c = S_ / 2
    d.ellipse([c - S_ * 0.2, c - S_ * 0.2, c + S_ * 0.2, c + S_ * 0.2], fill=255)
    for k in range(12):
        a = 2 * math.pi * k / 12
        pts = [(c + S_ * 0.26 * math.sin(a - 0.12), c - S_ * 0.26 * math.cos(a - 0.12)),
               (c + S_ * 0.46 * math.sin(a), c - S_ * 0.46 * math.cos(a)),
               (c + S_ * 0.26 * math.sin(a + 0.12), c - S_ * 0.26 * math.cos(a + 0.12))]
        d.polygon(pts, fill=255)
    return img.resize((size, size), Image.LANCZOS)


def extra_textures():
    clock_texture(64).save(OUT / "time_clock.i8.png")
    text_texture("CHILD", 64, 16).save(OUT / "time_label_child.i8.png")
    text_texture("ADULT", 64, 16).save(OUT / "time_label_adult.i8.png")
    sun_texture(64).save(OUT / "time_sun.i8.png")
    L.TEXTURES.update(EXTRA_TEXTURES)


# ---------------------------------------------------------------- shapes


def polar(phi, r):
    return T.polar(phi, r)


def floor_geom(e, mat, geom, y, col=SURF_FLOOR, up=True, cell=260):
    """A floor (or ceiling) of any shape: cut into cells (moderate triangles), each piece triangulated."""
    minx, minz, maxx, maxz = geom.bounds
    facing = (0, 1, 0) if up else (0, -1, 0)
    for cx in np.arange(math.floor(minx / cell) * cell, maxx, cell):
        for cz in np.arange(math.floor(minz / cell) * cell, maxz, cell):
            piece = geom.intersection(sbox(cx, cz, cx + cell, cz + cell))
            if piece.is_empty or piece.area < 1:
                continue
            parts = [piece] if piece.geom_type == "Polygon" else [g for g in getattr(piece, "geoms", []) if
                                                                   g.geom_type == "Polygon"]
            for part in parts:
                for tri in shapely.constrained_delaunay_triangles(part).geoms:
                    pts = [np.array([x, y, z]) for x, z in list(tri.exterior.coords)[:3]]
                    if np.linalg.norm(np.cross(pts[1] - pts[0], pts[2] - pts[0])) < 1e-3:
                        continue
                    p = L.facing_tri(*pts, facing)
                    e.tri(mat, [L.V(q, L.planar_uv(mat, q), facing if mat.lit else (255, 255, 255, 255)) for q in p])
                    if col is not None:
                        L.add_col(*p, col, facing=facing)


def disc(cx, cz, r, n=48):
    return Point(cx, cz).buffer(r, quad_segs=n // 4)


def arc_wall(e, mat, r, phi0, phi1, y0, y1, inward=True, col=SURF_WALL, step=5.0):
    """A curved wall on the circle of radius r between two angles (degrees)."""
    n = max(1, int(math.ceil(abs(phi1 - phi0) / step)))
    for k in range(n):
        a0 = phi0 + (phi1 - phi0) * k / n
        a1 = phi0 + (phi1 - phi0) * (k + 1) / n
        p0, p1 = polar(a0, r), polar(a1, r)
        mid = polar((a0 + a1) / 2, 1)
        facing = (-mid[0], 0, -mid[1]) if inward else (mid[0], 0, mid[1])
        wall(e, mat, p0, p1, y0, y1, facing, col=col, u0=r * math.radians(a0))


def arc_line(e, mat, r, phi0, phi1, y, width=10, step=5.0, inward=True):
    n = max(1, int(math.ceil(abs(phi1 - phi0) / step)))
    pts, nrm = [], []
    for k in range(n + 1):
        a = phi0 + (phi1 - phi0) * k / n
        x, z = polar(a, r)
        m = polar(a, 1)
        pts.append((x, y, z))
        nrm.append((-m[0], 0, -m[1]) if inward else (m[0], 0, m[1]))
    strip(e, mat, pts, nrm, width, lift=1.5)


def quad_on(e, mat, center, right, up, w, h, facing, col=None, uv=None):
    c, r_, u = np.array(center, float), np.array(right, float), np.array(up, float)
    p = [c - r_ * w / 2 - u * h / 2, c + r_ * w / 2 - u * h / 2, c + r_ * w / 2 + u * h / 2, c - r_ * w / 2 + u * h / 2]
    tw, th = mat.size
    uv = uv or [(0, th), (tw, th), (tw, 0), (0, 0)]
    L.quad(e, mat, p, uv, [(255, 255, 255, 255)] * 4 if not mat.lit else [tuple(facing)] * 4, facing, col)


# ---------------------------------------------------------------- the hall


def hole_shapes():
    b = T.BASIN
    pl = T.PAN_L
    s = T.PAN_L_SIZE / 2 + 2
    return [sbox(b["x0"], b["z0"], b["x1"], b["z1"]), sbox(pl[0] - s, pl[1] - s, pl[0] + s, pl[1] + s)]


def build_walkway():
    e = L.new_entry("walkway")
    ring = disc(0, 0, R, 96).difference(disc(0, 0, T.PIT_R, 96))
    for h in hole_shapes():
        ring = ring.difference(h)
    floor_geom(e, FLOOR, ring, 0)
    # the pit's wall, the void far below
    arc_wall(e, DARK, T.PIT_R, 0, 360, T.PIT_Y, 0, inward=True, step=7.5)
    v = L.new_entry("void")
    floor_geom(v, DARK, disc(0, 0, T.PIT_R, 48), T.PIT_Y, col=SURF_VOID)
    for r in (T.PIT_R - 60, T.PIT_R - 200, T.PIT_R - 330):
        ring_line(v, GLOW, 0, 0, r, T.PIT_Y + 2, n=32, width=12)
    # the walkway's lines: the era's colour along the pit's edge, cyan towards the wall
    arc_line(e, ERA, T.PIT_R + 22, 0, 360, 0, width=12, step=6)
    arc_line(e, GLOW, R - 60, 0, 360, 0, width=8, step=6)
    for phi in range(0, 360, 30):
        a, b = polar(phi, T.PIT_R + 40), polar(phi, R - 80)
        if 60 <= phi <= 120 or 150 <= phi <= 210:
            continue  # (the basin, the statue)
        floor_line(e, GLOW, [a, b], width=8)
    # the pan's shaft (the left pan sinks into it)
    pl, s = T.PAN_L, T.PAN_L_SIZE / 2 + 2
    for (a, b, f) in (((pl[0] - s, pl[1] + s), (pl[0] + s, pl[1] + s), (0, 0, -1)),
                      ((pl[0] + s, pl[1] - s), (pl[0] - s, pl[1] - s), (0, 0, 1)),
                      ((pl[0] + s, pl[1] + s), (pl[0] + s, pl[1] - s), (-1, 0, 0)),
                      ((pl[0] - s, pl[1] - s), (pl[0] - s, pl[1] + s), (1, 0, 0))):
        wall(e, DARK, a, b, -420, 0, f)
    flat(e, DARK, pl[0] - s, pl[0] + s, pl[1] - s, pl[1] + s, -420)
    ring_line(e, EMBER, pl[0], pl[1], s + 14, 0, n=4, width=8)
    # hookshot pillars at the walkway's edge (the way back from the dais)
    hw = HOOK_PILLAR_W / 2
    for phi in HOOK_PILLARS:
        x, z = polar(phi, HOOK_PILLAR_R)
        box(e, x - hw, x + hw, 0, HOOK_PILLAR_H, z - hw, z + hw, top=WALL, col_top=SURF_HOOK, col_side=SURF_HOOK)
        for f, (rx, rz) in (((0, 0, 1), (1, 0)), ((0, 0, -1), (-1, 0)), ((1, 0, 0), (0, -1)), ((-1, 0, 0), (0, 1))):
            quad_on(e, EYE, (x + f[0] * (hw + 0.5), HOOK_PILLAR_H - 60, z + f[2] * (hw + 0.5)), (rx, 0, rz), (0, 1, 0),
                    56, 56, f)
    # the second echo block's place
    ring_line(e, ERA, T.BAL_CELLS[0][0], T.BAL_CELLS[0][1], 48, 0, n=4, width=6)


def wall_openings():
    """Angle ranges (degrees) where the round wall has an opening: (phi0, phi1, height of the opening)."""
    arch = math.degrees(math.asin(S.ARCH_HALF / R))
    door = math.degrees(math.asin(DOOR_HALF / R))
    face = math.degrees(math.atan2(T.FACE_X, -T.FACE_Z))
    return [(-arch, arch, S.ARCH_H), (270 - door, 270 + door, DOOR_H), (180 - face, 180 + face, H)]


def build_round_wall():
    e = L.new_entry("wall")
    opens = wall_openings()
    cuts = sorted({a % 360 for o in opens for a in o[:2]} | {0.0})
    # walk round the circle from the arch's east edge
    angles = [opens[0][1]]
    for o in sorted(opens[1:]):
        angles += [o[0], o[1]]
    angles.append(360 + opens[0][0])
    spans = list(zip(angles[0::2], angles[1::2]))  # solid wall between openings
    for a0, a1 in spans:
        arc_wall(e, WALL, R, a0, a1, 0, H)
    for a0, a1, h in opens[:2]:  # over the arch and the door
        arc_wall(e, WALL, R, a0, a1, h, H, step=20)
    # pilasters round the wall, light strips between, a band of runes
    for phi in range(15, 360, 30):
        if near_opening(phi, opens, 8):
            continue
        x, z = polar(phi, R - 25)
        m = polar(phi, 1)
        p = L.prism(e, WALL, 34, 30, 0, H - 120, 4, phase=math.radians(phi + 45), cap=False, center=(x, z),
                    col=SURF_WALL)
        wall_line(e, GLOW, [(x - m[0] * 32, 120, z - m[1] * 32), (x - m[0] * 32, H - 160, z - m[1] * 32)],
                  (-m[0], 0, -m[1]), width=10)
    for a0, a1 in spans:
        arc_line(e, ERA, R - 2, a0, a1, 520, width=14)
        arc_line(e, GLOW, R - 2, a0, a1, 860, width=8)
    for phi in range(0, 360, 45):
        if near_opening(phi + 15, opens, 12):
            continue
        x, z = polar(phi + 15, R - 3)
        m = polar(phi + 15, 1)
        rune_panel(e, (x, 300, z), (-m[0], 0, -m[1]), 110, 110)


def near_opening(phi, opens, margin):
    return any(o[0] - margin < a < o[1] + margin for o in opens for a in (phi % 360, phi % 360 - 360))


def build_dais():
    e = L.new_entry("dais")
    L.prism(e, WALL, T.DAIS_R, T.DAIS_R, T.PIT_Y, 0, 32, cap=False, col=SURF_WALL)
    top = disc(0, 0, T.DAIS_R, 32)
    floor_geom(e, FLOOR, top, 0)
    # the clock-plate, the era's rings round it, the two pads
    quad_on(e, CLOCK, (0, 1.5, 0), (1, 0, 0), (0, 0, -1), 2 * T.PLATE_R, 2 * T.PLATE_R, (0, 1, 0))
    ring_line(e, ERA, 0, 0, T.PLATE_R + 12, 0, n=24, width=10)
    ring_line(e, GLOW, 0, 0, T.DAIS_R - 16, 0, n=32, width=8)
    ring_line(e, BLUE_PAD, T.BLUE_PAD[0], T.BLUE_PAD[1], T.PAD_R, 0, n=16, width=12)
    ring_line(e, ORANGE_PAD, T.ORANGE_PAD[0], T.ORANGE_PAD[1], T.PAD_R, 0, n=16, width=12)
    for pad, mat in ((T.BLUE_PAD, BLUE_PAD), (T.ORANGE_PAD, ORANGE_PAD)):
        ring_line(e, mat, pad[0], pad[1], T.PAD_R - 16, 0, n=12, width=6)
    # the lintel over the sphere's pedestal: hookshot it
    li = T.LINTEL
    for sx in (-1, 1):
        x = sx * li["x"]
        box(e, x - li["post"], x + li["post"], 0, li["y0"], li["z"] - li["post"], li["z"] + li["post"])
    box(e, -li["x"] - 20, li["x"] + 20, li["y0"], li["y1"], li["z"] - 18, li["z"] + 18, top=WALL,
        col_top=SURF_HOOK, col_side=SURF_HOOK)
    for f in (1, -1):
        quad_on(e, EYE, (0, (li["y0"] + li["y1"]) / 2, li["z"] + f * 19.5), (f, 0, 0), (0, 1, 0), 44, 44, (0, 0, f))
    # the curved track from the pedestal down to the cradle (ring 1 at rest)
    pts = T.track_points()
    rail, bed = [], []
    for k, (x, y, z) in enumerate(pts):
        bed.append((x, y - T.SPHERE_R, z))
    nrm = [(0, 1, 0)] * len(bed)
    strip(e, Mat("trackbed", "techrock", "ci4", (64, 64), repeat=200), bed, nrm, 46, lift=0.5)
    for side in (-1, 1):
        rpts = []
        for k in range(len(bed)):
            a = np.array(bed[max(k - 1, 0)])
            b = np.array(bed[min(k + 1, len(bed) - 1)])
            t = unit(b - a)
            sv = unit(np.cross(t, (0, 1, 0))) * side * 24
            rpts.append(tuple(np.array(bed[k]) + sv + (0, 10, 0)))
        strip(e, ERA, rpts, nrm, 8, lift=0.5)
    # what holds the track up
    for k in (4, 8, 11):
        x, y, z = bed[k]
        L.prism(e, DARK, 8, 8, T.PIT_Y, y - 2, 6, cap=True, center=(x, z))
    # the four torches' pillars (the torches are Obj_Syokudai on top)
    for phi, base in T.TORCHES:
        x, z = polar(phi, T.TORCH_R)
        L.prism(e, WALL, 34, 28, T.PIT_Y, base, 8, cap=True, cap_mat=DARK, center=(x, z), col=SURF_WALL)
        ring_line(e, EMBER, x, z, 24, base, n=10, width=6)


def build_basin():
    e = L.new_entry("basin")
    b = T.BASIN
    x0, x1, z0, z1, fl = b["x0"], b["x1"], b["z0"], b["z1"], b["floor"]
    (s1x0, s1x1, s1y), (s2x0, s2x1, s2y) = T.BASIN_STEPS
    flat(e, DARK, x0, s2x0, z0, z1, fl)
    box(e, s2x0, s2x1, fl, s2y, z0, z1, top=FLOOR, skip=("e", "n", "s"))
    box(e, s1x0, s1x1, fl, s1y, z0, z1, top=FLOOR, skip=("e", "n", "s"))
    wall(e, WALL, (x0, z0), (x0, z1), fl, 0, (1, 0, 0))  # west (towards the pit)
    wall(e, WALL, (x1, z1), (x1, z0), s1y, 0, (-1, 0, 0))  # east, over the top step
    wall(e, WALL, (x0, z1), (x1, z1), fl, 0, (0, 0, -1))  # south
    wall(e, WALL, (x1, z0), (x0, z0), fl, 0, (0, 0, 1))  # north
    # the drain (the block's first place), where the sun falls (its second), the third
    dx, dz = T.MIRROR_CELLS[0]
    for k in range(-2, 3):
        floor_line(e, DARK, [(dx + k * 12, dz - 34), (dx + k * 12, dz + 34)], width=5, y=fl)
    ring_line(e, EMBER, T.SUN[0], T.SUN[1], 50, fl, n=16, width=8)
    ring_line(e, ERA, T.MIRROR_CELLS[2][0], T.MIRROR_CELLS[2][1], 44, fl, n=4, width=6)
    for (x, z) in T.MIRROR_CELLS:
        pass
    floor_line(e, ERA, [(x0 + 30, T.MIRROR_CELLS[0][1]), (x0 + 30, T.MIRROR_CELLS[2][1])], width=6, y=fl)
    # the sun's spot on the walkway (glows when the mirror throws light there: En_Remix_Time draws it)
    ring_line(e, EMBER, T.SPOT[0], T.SPOT[1], T.SPOT_R + 10, 0, n=16, width=6)
    # the waterfall: flows up the wall (down once the torches have burned)
    phi0, phi1 = T.WATERFALL_PHI - 5.7, T.WATERFALL_PHI + 5.7
    n = 4
    for k in range(n):
        a0, a1 = phi0 + (phi1 - phi0) * k / n, phi0 + (phi1 - phi0) * (k + 1) / n
        p0, p1 = polar(a0, R - 6), polar(a1, R - 6)
        m = polar((a0 + a1) / 2, 1)
        u0, u1 = k / n * 32, (k + 1) / n * 32
        q = [(p0[0], 0, p0[1]), (p1[0], 0, p1[1]), (p1[0], H, p1[1]), (p0[0], H, p0[1])]
        L.quad(e, FALLS, q, [(u0, 0), (u1, 0), (u1, -H / 160 * 32), (u0, -H / 160 * 32)], [(255, 255, 255, 255)] * 4,
               (-m[0], 0, -m[1]))
    fx, fz = polar(T.WATERFALL_PHI, R - 70)
    L.prism(e, WALL, 120, 120, 0, 18, 12, cap=False, center=(fx, fz), col=SURF_WALL)
    fan(e, FALLS, (fx, 14, fz), ngon(fx, fz, 118, 12, 14), col=None)


def build_clock_and_sun():
    e = L.new_entry("clock")
    cx, cy, cz = T.CLOCK
    quad_on(e, CLOCK, (cx - 2, cy, cz), (0, 0, 1), (0, 1, 0), 2 * T.CLOCK_R, 2 * T.CLOCK_R, (-1, 0, 0))
    quad_on(e, CHILD, (cx - 2, cy + T.CLOCK_R + 40, cz - 120), (0, 0, 1), (0, 1, 0), 150, 38, (-1, 0, 0))
    quad_on(e, ADULT, (cx - 2, cy + T.CLOCK_R + 40, cz + 120), (0, 0, 1), (0, 1, 0), 150, 38, (-1, 0, 0))
    ring_line_wall(e, ERA, (cx - 3, cy, cz), T.CLOCK_R + 14, (-1, 0, 0))
    # the sun symbol over the way out (west)
    sx, sy, sz = T.SUN_SYMBOL
    quad_on(e, SUNM, (sx + 2, sy, sz), (0, 0, -1), (0, 1, 0), 160, 160, (1, 0, 0))
    # the door's frame and the alcove behind it, the exit ring
    a = T.EXIT_ALCOVE
    flat(e, FLOOR, a["x0"], a["x1"] + 8, -DOOR_HALF, DOOR_HALF, 0)
    flat(e, DARK, a["x0"], a["x1"] + 8, -DOOR_HALF, DOOR_HALF, 300, up=False, col=None)
    wall(e, WALL, (a["x0"], -DOOR_HALF), (a["x1"] + 8, -DOOR_HALF), 0, 300, (0, 0, 1))
    wall(e, WALL, (a["x1"] + 8, DOOR_HALF), (a["x0"], DOOR_HALF), 0, 300, (0, 0, -1))
    wall(e, WALL, (a["x0"], DOOR_HALF), (a["x0"], -DOOR_HALF), 0, 300, (1, 0, 0))
    ex, ez = T.EXIT_RING
    L.prism(e, DARK, EXIT_RING_R, EXIT_RING_R, 0, 6, 16, cap=False, col=SURF_WALL, center=(ex, ez))
    fan(e, FLOOR, (ex, 6, ez), ngon(ex, ez, EXIT_RING_R, 16, 6), col=SURF_EXIT)
    ring_line(e, GLOW, ex, ez, EXIT_RING_R - 10, 6, n=16, width=10)
    S.beam(e, ex, ez, 50, 50, 6, 296, planes=2)
    wall_line(e, EYE1L, [(-R + 4, 0, -DOOR_HALF - 16), (-R + 4, DOOR_H + 16, -DOOR_HALF - 16),
                         (-R + 4, DOOR_H + 16, DOOR_HALF + 16), (-R + 4, 0, DOOR_HALF + 16)], (1, 0, 0), width=12)


def ring_line_wall(e, mat, center, r, facing, n=32):
    c = np.array(center, float)
    f = np.array(facing, float)
    u = np.array([0, 1, 0], float)
    rt = np.cross(u, f)
    pts = [tuple(c + rt * r * math.sin(2 * math.pi * k / n) + u * r * math.cos(2 * math.pi * k / n)) for k in range(n)]
    strip(e, mat, pts, [tuple(f)] * n, 10, lift=1.0, closed=True)


def build_statue():
    """The statue's face (the north chord), its mouth and eyes, the high platform on its shoulder."""
    e = L.new_entry("statue")
    fz, fx = T.FACE_Z, T.FACE_X
    m, w1, (e2x, e2y) = T.MOUTH, T.EYE1_WIN, T.EYE2
    er = T.EYE_R
    xs = sorted({-fx, fx, m["x0"], m["x1"], w1["x0"], w1["x1"], e2x - er, e2x + er})
    ys = sorted({0, H, m["y1"], w1["y0"], w1["y1"], e2y - er, e2y + er})
    holes = [(m["x0"], m["x1"], 0, m["y1"]), (w1["x0"], w1["x1"], w1["y0"], w1["y1"]),
             (e2x - er, e2x + er, e2y - er, e2y + er)]
    for xa, xb in zip(xs, xs[1:]):
        for ya, yb in zip(ys, ys[1:]):
            if any(h[0] <= xa and xb <= h[1] and h[2] <= ya and yb <= h[3] for h in holes):
                continue
            wall(e, WALL, (xa, fz), (xb, fz), ya, yb, (0, 0, 1), u0=xa)
    # the second eye's socket (shallow: the sphere rests in it; a stone lid covers it until the first eye is lit)
    d = 50
    flat(e, DARK, e2x - er, e2x + er, fz - d, fz, e2y - er)
    flat(e, DARK, e2x - er, e2x + er, fz - d, fz, e2y + er, up=False)
    wall(e, DARK, (e2x - er, fz - d), (e2x - er, fz), e2y - er, e2y + er, (1, 0, 0))
    wall(e, DARK, (e2x + er, fz), (e2x + er, fz - d), e2y - er, e2y + er, (-1, 0, 0))
    wall(e, DARK, (e2x + er, fz - d), (e2x - er, fz - d), e2y - er, e2y + er, (0, 0, 1))
    # the face: brows, nose, cheekbones, the eye rings
    box(e, -330, -110, w1["y1"] + 40, w1["y1"] + 75, fz, fz + 40, top=WALL)
    box(e, 110, 330, w1["y1"] + 40, w1["y1"] + 75, fz, fz + 40, top=WALL)
    L.prism(e, WALL, 60, 20, m["y1"] + 10, w1["y1"] + 30, 3, phase=math.pi, center=(0, fz + 12), cap=True,
            col=SURF_WALL)
    box(e, -fx + 20, -300, 160, 200, fz, fz + 30, top=WALL)
    for cx, cy in ((T.EYE1[0], T.EYE1[1]), (-T.EYE1[0], T.EYE1[1])):
        ring_line_wall(e, EYE1L if cx < 0 else GLOW, (cx, cy, fz + 2), 82, (0, 0, 1), n=24)
    ring_line_wall(e, ALIVEL, (e2x, e2y, fz + 2), er + 16, (0, 0, 1), n=24)
    eye_emblem(e, EYE, (T.EYE1[0] * -1, T.EYE1[1], fz + 3), (0, 0, 1), 120)  # the blind right eye: an emblem
    for x in (-fx + 30, fx - 30):
        wall_line(e, GLOW, [(x, 0, fz + 2), (x, H - 100, fz + 2)], (0, 0, 1), width=12)
    wall_line(e, ALIVEL, [(m["x0"] - 18, 0, fz + 2), (m["x0"] - 18, m["y1"] + 18, fz + 2),
                          (m["x1"] + 18, m["y1"] + 18, fz + 2), (m["x1"] + 18, 0, fz + 2)], (0, 0, 1), width=12)
    # the window's sill and sides (the first eye's chamber is behind)
    hi = T.HIGH
    box(e, hi["x0"], hi["x1"], hi["top"] - 40, hi["top"], hi["z0"], hi["z1"], top=FLOOR)
    for x in (hi["x0"] + 20, hi["x1"] - 20):
        L.prism(e, DARK, 10, 10, 0, hi["top"] - 40, 6, center=(x, hi["z1"] - 20), cap=False, col=SURF_WALL)
    ring_line(e, EMBER, T.WEIGHT_SWITCH[0], T.WEIGHT_SWITCH[1], 44, hi["top"], n=12, width=6)
    # hookshot targets: above the high platform
    hx, hy = T.HIGH_TARGET
    box(e, hx - 50, hx + 50, hy - 50, hy + 50, fz, fz + 10, top=WALL, col_top=SURF_HOOK, col_side=SURF_HOOK)
    quad_on(e, EYE, (hx, hy, fz + 11), (1, 0, 0), (0, 1, 0), 90, 90, (0, 0, 1))
    # the right pan's track up the face
    floor_line_wall = [(T.PAN_R[0], T.PAN_R[2], fz + 2), (T.PAN_R[0], T.EYE2[1], fz + 2)]
    wall_line(e, ALIVEL, floor_line_wall, (0, 0, 1), width=10)


def build_interior():
    """Inside the statue: the corridor from the mouth, the gap, the landing, the stairs, the gallery, the narrow
    bridge, the first eye's chamber (its plate, the grate, the head above where the sphere waits)."""
    e = L.new_entry("interior")
    fz = T.FACE_Z
    c, g, la, st, so = T.CORRIDOR, T.GAP, T.LANDING, T.STAIRS, T.SOCKET
    top, up = 640, T.UPPER
    m = T.MOUTH
    # the corridor
    flat(e, FLOOR, m["x0"], m["x1"], c["z0"], c["z1"], 0)
    flat(e, DARK, m["x0"], m["x1"], c["z0"], c["z1"], m["y1"], up=False, col=None)
    wall(e, WALL, (m["x0"], c["z0"]), (m["x0"], c["z1"]), 0, m["y1"], (1, 0, 0))
    wall(e, WALL, (m["x1"], c["z1"]), (m["x1"], c["z0"]), 0, m["y1"], (-1, 0, 0))
    floor_line(e, ALIVEL, [(0, c["z1"] - 10), (0, c["z0"] + 10)], width=10)
    # the gap room and the landing: one box of walls
    x0, x1 = g["x0"], g["x1"]
    flat(e, DARK, x0, x1, g["z0"], g["z1"], g["floor"], col=SURF_VOID)
    flat(e, FLOOR, x0, x1, la["z0"], la["z1"], 0)
    wall(e, WALL, (x0, la["z1"]), (x1, la["z1"]), g["floor"], 0, (0, 0, 1))  # the landing's edge
    wall(e, WALL, (x1, g["z1"]), (x1, la["z0"]), g["floor"], top, (-1, 0, 0))
    wall(e, WALL, (x0, la["z0"]), (x0, g["z1"]), g["floor"], top, (1, 0, 0))
    wall(e, WALL, (x1, la["z0"]), (x0, la["z0"]), 0, top, (0, 0, 1))
    # the south wall of the gap room, with the corridor's and the bridge's doorways
    nb = T.NARROW
    zw = g["z1"]
    bx0, bx1 = nb["x0"] - 20, nb["x1"] + 20
    for xa, xb, ya, yb in ((x0, bx0, g["floor"], top), (bx1, m["x0"], g["floor"], top), (m["x1"], x1, g["floor"], top),
                           (bx0, bx1, g["floor"], up), (bx0, bx1, up + 110, top), (m["x0"], m["x1"], g["floor"], 0),
                           (m["x0"], m["x1"], m["y1"], top)):
        wall(e, WALL, (xb, zw), (xa, zw), ya, yb, (0, 0, -1))
    flat(e, DARK, x0, x1, g["z0"] - 300, g["z1"], top, up=False, col=None)
    # the far target (longshot across the gap)
    tx, ty, tz = T.FAR_TARGET
    box(e, tx - 50, tx + 50, ty - 50, ty + 50, tz, tz + 10, top=WALL, col_top=SURF_HOOK, col_side=SURF_HOOK)
    quad_on(e, EYE, (tx, ty, tz + 11), (1, 0, 0), (0, 1, 0), 90, 90, (0, 0, 1))
    # the stairs along the north wall, the gallery, the narrow bridge
    n = st["steps"]
    run = (st["x1"] - st["x0"]) / n
    for k in range(n):
        xa = st["x0"] + k * run
        box(e, xa, xa + run, 0, st["top"] * (k + 1) / n, st["z0"], st["z1"], top=FLOOR if k % 2 else WALL)
    ue, uc = T.U_EAST, T.U_CROSS
    box(e, ue["x0"], ue["x1"], up - 20, up, ue["z0"], ue["z1"], top=FLOOR)
    box(e, uc["x0"], uc["x1"], up - 20, up, uc["z0"], uc["z1"], top=FLOOR)
    box(e, nb["x0"], nb["x1"], up - 20, up, nb["z0"], zw, top=FLOOR)
    floor_line(e, EYE1L, [((nb["x0"] + nb["x1"]) / 2, nb["z0"]), ((nb["x0"] + nb["x1"]) / 2, zw)], width=6, y=up)
    floor_line(e, ALIVEL, [(uc["x0"] + 20, (uc["z0"] + uc["z1"]) / 2), (uc["x1"] - 20, (uc["z0"] + uc["z1"]) / 2)],
               width=8, y=up)
    # the first eye's chamber
    sx0, sx1, sz0, sz1, ceil = so["x0"], so["x1"], zw, so["z1"], so["ceil"]
    box(e, sx0, sx1, 0, up, sz0, sz1, top=FLOOR)
    wall(e, WALL, (sx0, sz0), (sx0, sz1), up, ceil + 200, (1, 0, 0))
    wall(e, WALL, (sx1, sz1), (sx1, sz0), up, ceil + 200, (-1, 0, 0))
    for xa, xb, ya, yb in ((sx0, bx0, up, ceil + 200), (bx1, sx1, up, ceil + 200), (bx0, bx1, up + 110, ceil + 200)):
        wall(e, WALL, (xa, sz0), (xb, sz0), ya, yb, (0, 0, 1))
    gr = T.GRATE
    gx0, gx1, gz0, gz1 = gr["x"] - gr["w"] / 2, gr["x"] + gr["w"] / 2, gr["z"] - gr["d"] / 2, gr["z"] + gr["d"] / 2
    ceiling = sbox(sx0, sz0, sx1, sz1).difference(sbox(gx0, gz0, gx1, gz1))
    floor_geom(e, DARK, ceiling, ceil, col=SURF_WALL, up=False)
    for (a, b, f) in (((gx0, gz1), (gx1, gz1), (0, 0, -1)), ((gx1, gz0), (gx0, gz0), (0, 0, 1)),
                      ((gx1, gz1), (gx1, gz0), (-1, 0, 0)), ((gx0, gz0), (gx0, gz1), (1, 0, 0))):
        wall(e, DARK, a, b, ceil, ceil + 30, f)
    flat(e, DARK, sx0, sx1, sz0, sz1, ceil + 200, up=False, col=None)
    flat(e, DARK, gx0, gx1, gz0, gz1, ceil + 30, col=None)  # the head's floor behind the grate
    px, pz = T.SOCKET_PLATE
    ring_line(e, EYE1L, px, pz, 34, up, n=16, width=8)
    ring_line(e, EMBER, T.HAMMER_SWITCH[0], T.HAMMER_SWITCH[1], 40, up, n=12, width=6)
    for z in np.arange(la["z0"] + 100, g["z1"], 250):
        wall_line(e, GLOW, [(x0 + 2, 60, z), (x0 + 2, top - 60, z)], (1, 0, 0), width=10)
        wall_line(e, GLOW, [(x1 - 2, 60, z), (x1 - 2, top - 60, z)], (-1, 0, 0), width=10)


def build_ceiling():
    e = L.new_entry("ceiling")
    sun = disc(T.SUN[0], T.SUN[1], 62, 16)
    floor_geom(e, DARK, disc(0, 0, R, 96).difference(sun), H, up=False, col=None, cell=400)
    S.tube_inward(e, DARK, T.SUN[0], T.SUN[1], 62, 12, H, H + 220)
    fan(e, Mat("sky", "glow", "i8", (32, 32), lit=False, xlu=True, prim=(255, 245, 200, 255)), (T.SUN[0], H + 220,
        T.SUN[1]), ngon(T.SUN[0], T.SUN[1], 62, 12, H + 220), up=False)
    for r in (360, 700):
        ring_line(e, GLOW, 0, 0, r, H, n=40, width=10)
    # the hourglass's chain
    strip(e, Mat("chain", "techrock", "ci4", (64, 64), repeat=60), [(0, T.HOURGLASS[1] + 150, 0), (0, H, 0)],
          [(0, 0, 1)] * 2, 10, lift=0.0)
    strip(e, Mat("chain2", "techrock", "ci4", (64, 64), repeat=60), [(0, T.HOURGLASS[1] + 150, 0), (0, H, 0)],
          [(1, 0, 0)] * 2, 10, lift=0.0)


# ---------------------------------------------------------------- actors


def actors():
    a = []
    cz = CH["z"]
    a.append(("ACTOR_EN_COW", -CH_APO + 105, 0, cz, 0, 0x4000, 0, "0"))
    for sx in (-1, 1):
        a.append(("ACTOR_OBJ_SYOKUDAI", sx * 170, 0, cz - CH_APO + 70, 0, 0, 0, "0x0400"))
    a.append((TIME_ACTOR, 0, 0, 0, 0, 0, 0, tp(TIME_CONTROLLER)))
    px, pz = T.PEDESTAL
    a.append((TIME_ACTOR, px, 0, pz, 0, 0, 0, tp(TIME_PEDESTAL)))
    a.append((TIME_ACTOR, px, T.PEDESTAL_TOP + T.SPHERE_R, pz, 0, 0, 0, tp(TIME_SPHERE)))
    a.append((TIME_ACTOR, 0, 0, 0, 0, 0, 0, tp(TIME_RING)))
    a.append((TIME_ACTOR, T.MIRROR_CELLS[0][0], T.BASIN["floor"], T.MIRROR_CELLS[0][1], 0, 0, 0, tp(TIME_ECHO, 0)))
    a.append((TIME_ACTOR, T.BAL_CELLS[0][0], 0, T.BAL_CELLS[0][1], 0, 0, 0, tp(TIME_ECHO, 1)))
    a.append((TIME_ACTOR, T.PAN_L[0], T.PAN_L[2], T.PAN_L[1], 0, 0, 0, tp(TIME_PAN, 0)))
    a.append((TIME_ACTOR, T.PAN_R[0], T.PAN_R[2], T.PAN_R[1], 0, 0, 0, tp(TIME_PAN, 1)))
    a.append((TIME_ACTOR, *T.WEIGHT, 0, 0, 0, tp(TIME_WEIGHT)))
    a.append((TIME_ACTOR, 0, 0, T.DAIS_R, 0, 0, 0, tp(TIME_BRIDGE)))
    a.append((TIME_ACTOR, T.RAMP["x"], 0, T.RAMP["z0"], 0, 0, 0, tp(TIME_RAMP)))
    a.append((TIME_ACTOR, 170, 0, 820, 0, 0, 0, tp(TIME_TABLET, 0)))  # the entrance: what the temple is
    a.append((TIME_ACTOR, T.SUN[0], 0, T.BASIN["z1"] + 70, 0, 0x8000, 0, tp(TIME_TABLET, 1)))  # by the basin
    a.append((TIME_ACTOR, T.SOCKET["x0"] + 25, T.UPPER, -975, 0, 0x4000, 0, tp(TIME_TABLET, 2)))  # the first eye
    a.append((TIME_ACTOR, -135, 0, -95, 0, 0, 0, tp(TIME_TABLET, 3)))  # the seed, by the pedestal
    a.append((TIME_ACTOR, *T.BLAST_CRYSTAL, 0, 0, 0, tp(TIME_BLAST)))
    a.append((TIME_ACTOR, 0, 0, T.FACE_Z, 0, 0, 0, tp(TIME_DOOR, T.FLAG_MOUTH)))  # the jaw (rot.z 0)
    a.append((TIME_ACTOR, T.EXIT_DOOR[0], 0, T.EXIT_DOOR[1], 0, 0x4000, 1, tp(TIME_DOOR, T.FLAG_EYE1)))  # the way out
    # the game's own pieces
    a.append(("ACTOR_OBJ_SWITCH", *T.LOCK_CRYSTAL, 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_CRYSTAL_TARGETABLE, OBJSWITCH_SUBTYPE_ONCE, {T.FLAG_LOCK})"))
    a.append(("ACTOR_OBJ_SWITCH", T.HAMMER_SWITCH[0], T.UPPER, T.HAMMER_SWITCH[1], 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_FLOOR_RUSTY, OBJSWITCH_SUBTYPE_ONCE, {T.FLAG_HAMMER})"))
    a.append(("ACTOR_OBJ_SWITCH", T.WEIGHT_SWITCH[0], T.HIGH["top"], T.WEIGHT_SWITCH[1], 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_FLOOR, OBJSWITCH_SUBTYPE_ONCE, {T.FLAG_WEIGHT})"))
    for phi, base in T.TORCHES:
        x, z = polar(phi, T.TORCH_R)
        a.append(("ACTOR_OBJ_SYOKUDAI", x, base, z, 0, 0, 0, f"(1 << 12) | ({T.TORCH_COUNT} << 6) | {T.FLAG_TORCHES}"))
    a.append(("ACTOR_EN_BOX", 0, 0, 115, 0, 0x8000, T.FLAG_ALIVE,
              f"(ENBOX_TYPE_SWITCH_FLAG_FALL_BIG << 12) | (GI_HEART_CONTAINER << 5) | {T.T_CHEST}"))
    return a


OBJECTS = ["OBJECT_SYOKUDAI", "OBJECT_COW", "OBJECT_BOX", "OBJECT_REMIX_TIME"]


def sun_test_yaw():
    dx = T.SUN_SYMBOL[0] - T.SPOT[0]
    dz = T.SUN_SYMBOL[2] - T.SPOT[1]
    return int(round(math.atan2(dx, dz) / math.pi * 0x8000)) & 0xFFFF


def room_defines():
    return ("// Switch flags z_remix_level.c reads (the full plan is in object_remix_time.h)\n"
            f"#define TIME_SHRINE_FLAG_TORCHES {T.FLAG_TORCHES}\n#define TIME_SHRINE_FLAG_EYE1 {T.FLAG_EYE1}\n"
            f"#define TIME_SHRINE_FLAG_ALIVE {T.FLAG_ALIVE}\n#define TIME_SHRINE_FLAG_MIRROR_CELL 0x{T.FLAG_MIRROR_CELL:02X}\n"
            "// Where the sunlight test boot puts Link: on the spot, facing the sun symbol (z_remix_level.c)\n"
            f"#define TIME_TEST_SUN_X {T.SPOT[0]}.0f\n#define TIME_TEST_SUN_Z {T.SPOT[1]}.0f\n"
            f"#define TIME_TEST_SUN_YAW 0x{sun_test_yaw():04X}\n\n")


def check_layout():
    """What the trial relies on: the longshot reaches 780 (the hookshot 390), Din's Fire about 330 at its widest, a
    running jump carries about 157, Link climbs about 110 (a child about 50)."""
    longshot, hookshot, dins, jump = 780, 390, 330, 157
    d2 = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])  # noqa: E731
    d3 = lambda a, b: math.dist(a, b)  # noqa: E731
    li = T.LINTEL
    # I: the lintel over the sphere, from the south walkway's edge (through ring 1's south opening)
    assert d3((0, 40, T.PIT_R + 10), (0, (li["y0"] + li["y1"]) / 2, li["z"] + 18)) < longshot - 20
    assert T.PIT_R - T.DAIS_R > 2 * jump, "the pit could be jumped"
    # ...and back out to the hookshot pillars from the dais's edge
    for phi in HOOK_PILLARS:
        px, pz = polar(phi, HOOK_PILLAR_R)
        assert d3(polar(phi, T.DAIS_R) + (0,), (px, pz, 0)) < longshot - 50
    # II: Din's Fire from the clock-plate reaches all four torches, from the walkway none
    for phi, base in T.TORCHES:
        x, z = polar(phi, T.TORCH_R)
        assert math.hypot(x, z) < dins - 15 and abs(base + 60) < 200
        assert T.PIT_R - T.TORCH_R > 220, "Din's Fire from the walkway's edge would reach a torch"
    # the torches stand inside the ring, between it and the dais
    assert T.DAIS_R + 60 < T.TORCH_R < T.RING_R0 - 60
    # III: the light spot is on the walkway, the sun symbol and the first eye are well apart as seen from it
    assert T.PIT_R + 50 < math.hypot(*T.SPOT) < R - 50
    a1 = math.atan2(T.SUN_SYMBOL[0] - T.SPOT[0], T.SUN_SYMBOL[2] - T.SPOT[1])
    a2 = math.atan2(T.SOCKET_PLATE[0] - T.SPOT[0], T.SOCKET_PLATE[1] - T.SPOT[1])
    assert abs(math.degrees(a1 - a2)) > 25
    # IV: the gap needs the longshot (or hover boots), the far target is within reach from the corridor's end
    assert T.GAP["z1"] - T.GAP["z0"] > jump + 60
    assert d3((0, 40, T.GAP["z1"]), T.FAR_TARGET) < longshot - 50
    # V: the high platform's target from the walkway below, the scale reaches the second eye with both weights
    hx, hy = T.HIGH_TARGET
    assert d3((hx, 40, T.FACE_Z + 380), (hx, hy, T.FACE_Z)) < longshot - 50
    assert T.PAN_R[2] + T.TILT_WEIGHT < T.EYE2[1] < T.PAN_R[2] + T.TILT_WEIGHT + T.TILT_PILLAR + 1
    assert T.HIGH["top"] - 0 > 110, "the high platform could be climbed"
    # the child's ramp is walkable (under 40 degrees)
    assert math.degrees(math.atan2(T.UPPER, T.RAMP["z0"] - T.RAMP["z1"])) < 40
    print("make_time: reaches, Din's Fire, the light, the gap and the scale checked")


def main():
    configure()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    L.make_textures()
    (OUT / "ancient_title.ia8.png").unlink(missing_ok=True)
    sand_palettes()
    extra_textures()
    S.title_card("Temple of Two Truths")
    S.build_chamber()
    build_walkway()
    build_round_wall()
    build_dais()
    build_basin()
    build_clock_and_sun()
    build_statue()
    build_interior()
    build_ceiling()
    check_layout()
    npolys, nverts, entries, acts = S.write_sources()
    tris = sum(len(t) for e in L.ENTRIES + L.MESHES for t in e.groups.values())
    print(f"Temple of Two Truths: {len(entries)} room chunks, {tris} triangles, {npolys} collision polys "
          f"({nverts} vertices), {len(acts)} actors")
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file"] + [str(p) for p in OUT.glob("*.[ch]")], cwd=REPO, check=True)


if __name__ == "__main__":
    main()
