#!/usr/bin/env python3
"""Generate object_remix_years: the pieces of the Shrine of Seven Years (Web Remix level 7), for En_Remix_Years, and
the header that gives that actor the shrine's plan (tools/remix/years_plan.py).

  Pedestal, Sword          the Master Sword's pedestal, and the sword (drawn in it in the past)
  Cube                     the small stone cube (pushed by both ages: a stone block stays a stone block)
  Planter, Tree            the sapling's planter (the past) and the tree it has grown into (the future): a trunk with
                           a climbable face, a branch at the upper floor's height
  Support                  the stone support (pushed under the final staircase in the past)
  StairsFull, StairsBroken the final staircase: whole, or with its middle fallen
  EastStairs, EastStairsRuin   the past's stairs up to the upper floor, and what is left of them
  GardenWall, Rubble       the garden's south wall with its child-sized doorway (past), the mound it fell into (future)
  CrackWall, Roots         the cracked wall of the secret alcove (past), the roots that seal it (future)
  Medallion, LooseStone, Cavity, Door, Tablet, Narrow
                           the golden medallion, the loose stone and the hole under it, the massive exit door,
                           inscriptions, and an invisible block for openings too small for the adult

Model units are game units (drawn at scale 1). Opaque parts are textured, shaded by baked vertex colours, with the
environment colour added (the actor makes a piece glow with it).

    python3 tools/remix/make_years_parts.py     # writes assets/objects/object_remix_years/ (committed)
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import years_plan as Y
from make_time_parts import Piece, shade, SETUP, KIND

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/objects/object_remix_years"
INC = "assets/objects/object_remix_years"
PREFIX = "gYears"


# ---------------------------------------------------------------- textures (32 x 32 RGBA16)


def stone(seed, base=(205, 200, 190)):
    rng = np.random.default_rng(seed)
    img = np.zeros((32, 32, 3)) + base
    img *= 0.86 + 0.14 * rng.random((32, 32, 1))
    for y in (0, 31):
        img[y, :] *= 0.7
    img[:, 0] *= 0.7
    img[:, 31] *= 0.8
    return img


def triforce(img, color):
    img = img.copy()
    d = Image.new("L", (32, 32), 0)
    g = ImageDraw.Draw(d)
    for (cx, cy) in ((16, 9), (10, 20), (22, 20)):
        g.polygon([(cx, cy - 5), (cx - 6, cy + 5), (cx + 6, cy + 5)], fill=255)
    m = np.array(d)[..., None] / 255.0
    return img * (1 - m) + np.array(color, float) * m


def bark():
    rng = np.random.default_rng(7)
    img = np.zeros((32, 32, 3)) + [104, 74, 46]
    x = np.arange(32)[None, :, None]
    img *= 0.8 + 0.2 * np.sin(x / 32 * 2 * math.pi * 3) ** 2
    img *= 0.9 + 0.1 * rng.random((32, 32, 1))
    for k in range(5):  # ivy on the bark: the climbable face
        y0 = rng.integers(0, 32)
        img[y0 : y0 + 3, rng.integers(0, 28) :][:, :5] = [70, 130, 60]
    return img


def leaves():
    rng = np.random.default_rng(8)
    img = np.zeros((32, 32, 3)) + [70, 140, 60]
    img *= 0.7 + 0.4 * rng.random((32, 32, 1))
    return img


def wood():
    y = np.arange(32)[:, None, None]
    img = np.zeros((32, 32, 3)) + [150, 104, 60]
    img *= 0.85 + 0.15 * np.sin(y / 32 * 2 * math.pi * 4) ** 2
    img[0, :] *= 0.6
    img[:, 0] *= 0.6
    return img


def roots():
    rng = np.random.default_rng(12)
    img = np.zeros((32, 32, 3)) + [60, 44, 30]
    for k in range(9):
        x = rng.integers(0, 32)
        for y in range(32):
            x = (x + rng.integers(-1, 2)) % 32
            img[y, x] = [128, 92, 58]
            img[y, (x + 1) % 32] = [104, 76, 48]
    for k in range(20):
        img[rng.integers(0, 32), rng.integers(0, 32)] = [70, 120, 50]
    return img


def gold():
    y = np.arange(32)[:, None, None]
    x = np.arange(32)[None, :, None]
    return np.zeros((32, 32, 3)) + np.array([255, 205, 70]) * (0.75 + 0.35 * np.cos((x + y) / 32 * 2 * math.pi) ** 2)


def steel():
    y = np.arange(32)[:, None, None]
    x = np.arange(32)[None, :, None]
    return np.zeros((32, 32, 3)) + np.array([205, 215, 230]) * (0.8 + 0.25 * np.exp(-(((x - y) / 6.0) ** 2)))


def write_textures():
    tex = {
        "years_stone": stone(1),
        "years_old": stone(2, (150, 146, 136)),
        "years_tri": triforce(stone(3), (255, 205, 80)),
        "years_bark": bark(),
        "years_leaves": leaves(),
        "years_wood": wood(),
        "years_roots": roots(),
        "years_gold": gold(),
        "years_steel": steel(),
        "years_blue": np.zeros((32, 32, 3)) + [60, 70, 170],
        "years_soil": stone(9, (90, 64, 40)),
    }
    for name, img in tex.items():
        Image.fromarray(np.clip(img, 0, 255).round().astype(np.uint8)).convert("RGBA").save(OUT / f"{name}.rgba16.png")
    return list(tex)


# ---------------------------------------------------------------- geometry

CLIMB = 1  # collision surface index: the tree's climbable face


def colbox(p, x0, x1, y0, y1, z0, z1, surf=0, skip=()):
    """Collision only: a closed box (its faces with `surf`)."""
    q = Piece("tmp")
    q.box(x0, x1, y0, y1, z0, z1, skip=skip)
    p.colmap = getattr(p, "colmap", {})
    for tri in q.col:
        p.col.append(tri)
        p.colmap[id(tri)] = surf


def add_col(p, tris, surf=0):
    p.colmap = getattr(p, "colmap", {})
    for tri in tris:
        t = [np.array(v, float) for v in tri]
        p.col.append(t)
        p.colmap[id(t)] = surf


def stairs(p, steps, x0, x1, z0, z1, y0, rise, slab, skip=(), col=True, mat="years_stone"):
    run = (x1 - x0) / steps
    for k in range(steps):
        if k in skip:
            continue
        top = y0 + rise * (k + 1)
        xa = x0 + run * k
        p.box(xa, xa + run, top - slab, top, z0, z1, mat=mat, top="years_tri" if k % 3 == 1 else "years_stone",
              tile=80, col=col)


def build_pieces():
    out = []
    p = Piece("Pedestal")
    p.box(-55, 55, 0, 36, -40, 40, mat="years_stone", top="years_stone", tile=80)
    p.box(-40, 40, 36, 66, -28, 28, mat="years_tri", top="years_tri", tile=60)
    out.append(p)

    p = Piece("Sword")  # stands on its point at y 0 (sunk into the pedestal: drawn from its top)
    p.box(-4, 4, -20, 64, -1.5, 1.5, mat="years_steel", tile=20, col=False)
    p.tri("years_steel", [(-4, 64, 0), (4, 64, 0), (0, 74, 0)], [(0, 0), (8, 0), (4, 8)], (0, 0, 1))
    p.box(-24, 24, 64, 71, -4, 4, mat="years_blue", tile=20, col=False)  # the crossguard
    for sx in (-1, 1):
        p.box(sx * 18 - 4, sx * 18 + 4, 71, 80, -4, 4, mat="years_blue", tile=20, col=False)
    p.box(-3, 3, 71, 99, -3, 3, mat="years_blue", tile=20, col=False)  # the grip
    p.box(-6, 6, 99, 107, -5, 5, mat="years_gold", tile=20, col=False)  # the pommel
    p.box(-2.5, 2.5, 66, 74, -4.5, 4.5, mat="years_gold", tile=20, col=False)  # the gem's setting
    out.append(p)

    c = Y.CUBE / 2
    p = Piece("Cube", dict(wall=7))
    p.box(-c, c, 0, Y.CUBE, -c, c, mat="years_old", top="years_tri", tile=60)
    out.append(p)

    h = Y.PLANTER / 2
    p = Piece("Planter", dict(wall=7))
    p.box(-h, h, 0, 46, -h, h, mat="years_wood", top="years_soil", tile=80)
    p.box(-3, 3, 46, 80, -3, 3, mat="years_bark", tile=30, col=False)  # the sapling
    for a in range(4):
        t = a * math.pi / 2
        s, co = math.sin(t), math.cos(t)
        p.tri("years_leaves", [(0, 76, 0), (s * 16, 86, co * 16), (s * 6 + co * 6, 92, co * 6 - s * 6)],
              [(0, 0), (16, 0), (8, 16)], (s, 0.6, co))
        p.tri("years_leaves", [(0, 76, 0), (s * 6 + co * 6, 92, co * 6 - s * 6), (s * 16, 86, co * 16)],
              [(0, 0), (8, 16), (16, 0)], (-s, -0.6, -co))
    out.append(p)

    # the grown tree: trunk (its south face, +z, is climbable: ivy), a branch north at the upper floor's height
    t = 35
    p = Piece("Tree")
    p.box(-t, t, 0, Y.TREE_H - 20, -t, t, mat="years_bark", top="years_bark", tile=70, col=False)
    p.box(-t - 10, t + 10, Y.UPPER_Y - 22, Y.UPPER_Y, -t - 70, t + 5, mat="years_bark", top="years_wood", tile=70,
          col=False)
    for k in range(6):  # the crown
        a = k * math.pi / 3
        cx, cz = math.sin(a) * 70, math.cos(a) * 70
        p.sphere("years_leaves", 75, 8, 6, scale=(1, 0.7, 1), center=(cx, Y.TREE_H + 70, cz))
    p.sphere("years_leaves", 90, 8, 6, scale=(1, 0.8, 1), center=(0, Y.TREE_H + 120, 0))
    # collision: the trunk up to the upper floor's height (its top walkable), its ivy face, the branch north of it
    colbox(p, -t, t, 0, Y.UPPER_Y, -t, t, surf=0, skip=("s",))
    add_col(p, [((-t, 0, t), (t, 0, t), (t, Y.UPPER_Y, t)), ((-t, 0, t), (t, Y.UPPER_Y, t), (-t, Y.UPPER_Y, t))],
            surf=CLIMB)
    colbox(p, -t - 10, t + 10, Y.UPPER_Y - 22, Y.UPPER_Y, -t - 70, -t, skip=("s",))
    out.append(p)

    sw = Y.SUPPORT_W / 2
    p = Piece("Support", dict(wall=7))
    p.box(-sw, sw, 0, Y.SUPPORT_H, -sw, sw, mat="years_old", top="years_stone", tile=70)
    for y in (18, Y.SUPPORT_H - 18):
        p.box(-sw - 4, sw + 4, y - 6, y + 6, -sw - 4, sw + 4, mat="years_stone", tile=40, col=False)
    out.append(p)

    s = Y.STAIRS
    rise = (Y.LANDING["top"] - Y.UPPER_Y) / s["steps"]
    hz = (s["z1"] - s["z0"]) / 2
    for name, skip, mat in (("StairsFull", (), "years_stone"), ("StairsBroken", Y.BROKEN_STEPS, "years_old")):
        p = Piece(name)
        stairs(p, s["steps"], 0, s["x1"] - s["x0"], -hz, hz, 0, rise, s["slab"], skip=skip, mat=mat, col=False)
        run = (s["x1"] - s["x0"]) / s["steps"]
        parts = [(0, s["steps"])] if not skip else [(0, skip[0]), (skip[-1] + 1, s["steps"])]
        for k0, k1 in parts:  # walked as a slope (the steps are only drawn)
            xa, xb = run * k0, run * k1
            ya, yb = rise * k0 + rise / 2, rise * k1 + rise / 2
            add_col(p, [((xa, ya, hz), (xb, yb, hz), (xb, yb, -hz)), ((xa, ya, hz), (xb, yb, -hz), (xa, ya, -hz))])
            if k1 == s["steps"]:
                add_col(p, [((xb, yb, hz), (xb + 10, rise * k1, hz), (xb + 10, rise * k1, -hz)),
                            ((xb, yb, hz), (xb + 10, rise * k1, -hz), (xb, yb, -hz))])
        if skip:  # broken edges hanging down
            run = (s["x1"] - s["x0"]) / s["steps"]
            for k in (skip[0] - 1, skip[-1] + 1):
                xa = run * k
                top = rise * (k + 1)
                p.box(xa + run * 0.3, xa + run * 0.8, top - s["slab"] - 30, top - s["slab"], -hz + 10, hz - 10,
                      mat="years_old", tile=40, col=False)
        out.append(p)

    e = Y.EAST_STAIRS
    hw = (e["x1"] - e["x0"]) / 2
    length = e["z1"] - e["z0"]  # (negative: north)
    for name, ruin in (("EastStairs", False), ("EastStairsRuin", True)):
        p = Piece(name)
        n = e["steps"]
        for k in range(n if not ruin else 4):
            za, zb = length * k / n, length * (k + 1) / n
            top = Y.UPPER_Y * (k + 1) / n
            p.box(-hw, hw - (40 if ruin and k == 3 else 0), 0, top, zb, za, mat="years_old" if ruin else "years_stone",
                  top="years_stone", tile=80, col=False, color=(170, 170, 160) if ruin else (255, 255, 255))
        if not ruin:  # walk it as a slope
            a, b = (-hw, 0, 0), (hw, 0, 0)
            c_, d = (hw, Y.UPPER_Y, length), (-hw, Y.UPPER_Y, length)
            add_col(p, [(a, b, c_), (a, c_, d)])
            add_col(p, [((-hw, 0, 0), (-hw, Y.UPPER_Y, length), (-hw, 0, length)),
                        ((hw, 0, 0), (hw, 0, length), (hw, Y.UPPER_Y, length))])
        out.append(p)

    # the garden's south wall (local x along the wall, centred on its doorway; z its thickness)
    g, gd = Y.GARDEN, Y.GARDEN_DOOR
    half = (g["x1"] - g["x0"]) / 2
    off = gd["x"] - (g["x0"] + g["x1"]) / 2  # the doorway's offset from the wall's middle
    p = Piece("GardenWall")
    for xa, xb, ya, yb in ((-half - off, -gd["w"] / 2, 0, Y.UPPER_Y), (gd["w"] / 2, half - off, 0, Y.UPPER_Y),
                           (-gd["w"] / 2, gd["w"] / 2, gd["h"], Y.UPPER_Y)):
        p.box(xa, xb, ya, yb, -15, 15, mat="years_stone", top="years_stone", tile=100)
    out.append(p)
    r = Y.RUBBLE
    p = Piece("Rubble")
    rz = (r["z1"] - r["z0"]) / 2
    rng = np.random.default_rng(3)
    p.box(-half - off, half - off, 0, r["h"], -rz, rz, mat="years_old", top="years_old", tile=60)
    p.box(-60, 60, 0, r["step_h"], -rz - 40, -rz, mat="years_old", top="years_old", tile=60)  # (inside: a step)
    for k in range(9):  # broken blocks lying about
        x = rng.uniform(-half - off + 30, half - off - 30)
        y = r["h"] + rng.uniform(-10, 10)
        p.box(x - 25, x + 25, y - 15, y + 15, -20, 20, mat="years_old", tile=40, col=False, color=(190, 185, 175))
    out.append(p)

    # the secret alcove's opening (local x along the wall, z its thickness; turned to the east wall when drawn)
    cr = Y.CRACK
    p = Piece("CrackWall")
    w2, c2 = cr["w"] / 2, cr["crack_w"] / 2
    p.box(-w2, -c2, 0, cr["h"], -10, 10, mat="years_stone", tile=80)
    p.box(c2, w2, 0, cr["h"], -10, 10, mat="years_stone", tile=80)
    p.box(-c2, c2, cr["crack_h"], cr["h"], -10, 10, mat="years_stone", tile=80)
    for k in range(5):  # the crack, zig-zagging up from the hole
        p.box(-3 + (k % 2) * 6, 3 + (k % 2) * 6, cr["crack_h"] + k * 26, cr["crack_h"] + k * 26 + 28, 10, 11,
              mat="years_soil", tile=20, col=False)
    out.append(p)
    p = Piece("Roots", dict(wall=7))
    p.box(-w2, w2, 0, cr["h"], -15, 15, mat="years_roots", top="years_roots", tile=60)
    out.append(p)

    p = Piece("Medallion")
    p.cylinder("years_gold", 14, 14, 0, 4, n=12, cap_top="years_tri", cap_bottom="years_gold")
    out.append(p)
    p = Piece("LooseStone", dict(wall=0))
    p.box(-25, 25, 0, 16, -25, 25, mat="years_old", top="years_old", tile=50, col=False)
    out.append(p)
    p = Piece("Cavity")
    p.box(-22, 22, -1, 0.5, -22, 22, mat="years_soil", top="years_soil", tile=40, col=False, color=(60, 50, 40))
    out.append(p)

    d = Y.DOOR
    p = Piece("Door")
    w = (d["x1"] - d["x0"]) / 2
    p.box(-w, w, 0, d["y1"], -20, 20, mat="years_stone", top="years_stone", tile=110)
    p.quad("years_tri", [(-60, 140, 21), (60, 140, 21), (60, 260, 21), (-60, 260, 21)], (0, 0, 1), col=False, tile=120)
    p.box(-w, w, d["y1"] - 30, d["y1"], 20, 28, mat="years_gold", tile=60, col=False)
    out.append(p)
    p = Piece("Tablet")
    p.box(-45, 45, 0, 110, -8, 8, mat="years_tri", top="years_stone", tile=90)
    p.box(-55, 55, 0, 14, -14, 14, mat="years_stone", col=False)
    out.append(p)
    p = Piece("Narrow")
    colbox(p, -35, 35, 0, 64, -35, 35)
    out.append(p)
    return out


SURFACE = ("{{ {{ SURFACETYPE0(0, 0, FLOOR_TYPE_0, 0, WALL_TYPE_{wall}, FLOOR_PROPERTY_0, false, false), "
           "SURFACETYPE1(SURFACE_MATERIAL_{mat}, FLOOR_EFFECT_0, 0, 0, false, CONVEYOR_SPEED_DISABLED, 0, false) }} }},\n")


def collision(p):
    colmap = getattr(p, "colmap", {})
    vid, verts, polys = {}, [], []
    for tri in p.col:
        si = colmap.get(id(tri), 0)
        ids = []
        for q in tri:
            key = tuple(int(round(c)) for c in q)
            if key not in vid:
                vid[key] = len(verts)
                verts.append(key)
            ids.append(vid[key])
        if len(set(ids)) < 3:
            continue
        a, b, c = (np.array(verts[i], float) for i in ids)
        n = np.cross(b - a, c - a)
        if np.linalg.norm(n) < 1e-6:
            continue
        n /= np.linalg.norm(n)
        polys.append((si, ids, [int(round(x * 0x7FFF)) for x in n], int(round(-np.dot(n, a)))))
    arr = np.array(verts)
    lo, hi = arr.min(0), arr.max(0)
    nm = f"{PREFIX}{p.name}"
    wall = p.surf.get("wall", 0)
    surfaces = SURFACE.format(wall=wall, mat="STONE")
    if p.name == "Tree":
        surfaces = SURFACE.format(wall=0, mat="WOOD") + SURFACE.format(wall=4, mat="WOOD")
    return "".join([
        f"Vec3s {nm}ColVtx[] = {{\n" + "".join(f"    {{ {v[0]}, {v[1]}, {v[2]} }},\n" for v in verts) + "};\n\n",
        f"CollisionPoly {nm}ColPolys[] = {{\n" +
        "".join(f"    {{ {si}, {{ COLPOLY_VTX({i[0]}, 0), COLPOLY_VTX({i[1]}, 0), {i[2]} }}, "
                f"{{ {n[0]}, {n[1]}, {n[2]} }}, {d} }},\n" for si, i, n, d in polys) + "};\n\n",
        f"SurfaceType {nm}ColSurfaces[] = {{\n    " + surfaces + "};\n\n",
        f"CollisionHeader {nm}Col = {{\n    {{ {lo[0]}, {lo[1]}, {lo[2]} }},\n    {{ {hi[0]}, {hi[1]}, {hi[2]} }},\n"
        f"    ARRAY_COUNT({nm}ColVtx),\n    {nm}ColVtx,\n    ARRAY_COUNT({nm}ColPolys),\n    {nm}ColPolys,\n"
        f"    {nm}ColSurfaces,\n    NULL,\n    0,\n    NULL,\n}};\n\n"])


def material(mat, sym):
    if mat in KIND:
        from make_time_parts import material as tm
        return tm(mat, sym)
    return SETUP + ["    gsSPSetGeometryMode(G_SHADE | G_SHADING_SMOOTH | G_ZBUFFER | G_CULL_BACK),",
                    "    gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON),", "    gsDPSetTextureLUT(G_TT_NONE),",
                    "    gsDPSetCombineLERP(TEXEL0, 0, SHADE, ENVIRONMENT, 0, 0, 0, 1, TEXEL0, 0, SHADE, ENVIRONMENT, 0, 0, 0, 1),",
                    "    gsDPSetRenderMode(G_RM_AA_ZB_OPA_SURF, G_RM_AA_ZB_OPA_SURF2),",
                    f"    gsDPLoadTextureBlock({sym[mat]}, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, G_TX_NOMIRROR | G_TX_WRAP,"
                    " G_TX_NOMIRROR | G_TX_WRAP, 5, 5, G_TX_NOLOD, G_TX_NOLOD),"]


def emit(pieces, textures):
    sym = {t: "g" + "".join(s.capitalize() for s in t.split("_")) + "Tex" for t in textures}
    s = ["// Generated by tools/remix/make_years_parts.py - the Shrine of Seven Years' pieces. Do not edit.\n",
         '#include "object_remix_years.h"\n#include "gfx.h"\n#include "array_count.h"\n#include "camera.h"\n\n']
    for t in textures:
        s.append(f"u64 {sym[t]}[] = {{\n#include \"{INC}/{t}.rgba16.inc.c\"\n}};\n\n")
    for p in pieces:
        vtx, dl = [], []
        for mat, tris in p.tris.items():
            kind = KIND.get(mat, "opa")
            dl += material(mat, sym)
            for k in range(0, len(tris), 5):
                chunk = tris[k : k + 5]
                dl.append(f"    gsSPVertex(&{PREFIX}{p.name}Vtx[{len(vtx)}], {3 * len(chunk)}, 0),")
                for pts, uv, n, color in chunk:
                    c = shade(n, color) if kind != "beam" else (255, 255, 255)
                    for q, (u, v) in zip(pts, uv):
                        vtx.append(f"    VTX({int(round(q[0]))}, {int(round(q[1]))}, {int(round(q[2]))}, "
                                   f"{int(round(u * 32))}, {int(round(v * 32))}, {c[0]}, {c[1]}, {c[2]}, 255),")
                for i in range(0, len(chunk) - 1, 2):
                    dl.append(f"    gsSP2Triangles({3 * i}, {3 * i + 1}, {3 * i + 2}, 0, {3 * i + 3}, {3 * i + 4}, "
                              f"{3 * i + 5}, 0),")
                if len(chunk) % 2:
                    i = len(chunk) - 1
                    dl.append(f"    gsSP1Triangle({3 * i}, {3 * i + 1}, {3 * i + 2}, 0),")
        dl.append("    gsSPEndDisplayList(),")
        if vtx:
            s.append(f"Vtx {PREFIX}{p.name}Vtx[] = {{\n" + "\n".join(vtx) + "\n};\n\n")
        s.append(f"Gfx {PREFIX}{p.name}DL[] = {{\n" + "\n".join(dl) + "\n};\n\n")
        if p.col:
            s.append(collision(p))
    return "".join(s)


def plan_defines():
    d = []

    def put(name, v):
        d.append(f"#define YEARS_{name} {v}")

    def f(v):
        return f"{float(v):.1f}f"

    put("PEDESTAL_X", f(Y.PEDESTAL[0]))
    put("PEDESTAL_Z", f(Y.PEDESTAL[1]))
    put("DAIS_H", f(Y.DAIS_H))
    put("CUBE_N", len(Y.CUBE_CELLS))
    put("CUBE_CELLS", "{ " + ", ".join(f"{{ {x}, {z} }}" for x, z in Y.CUBE_CELLS) + " }")
    put("PLANTER_N", len(Y.PLANTER_CELLS))
    put("PLANTER_CELLS", "{ " + ", ".join(f"{{ {x}, {z} }}" for x, z in Y.PLANTER_CELLS) + " }")
    put("PLANTER_START", Y.PLANTER_START)
    put("SUPPORT_N", len(Y.SUPPORT_CELLS))
    put("SUPPORT_CELLS", "{ " + ", ".join(f"{{ {x}, {z} }}" for x, z in Y.SUPPORT_CELLS) + " }")
    put("UPPER_Y", f(Y.UPPER_Y))
    put("CAVITY_X", f(Y.CAVITY[0]))
    put("CAVITY_Z", f(Y.CAVITY[1]))
    put("DOOR_H", f(Y.DOOR["y1"]))
    put("FLAG_DOOR", Y.FLAG_DOOR)
    put("FLAG_MEDALLION", Y.FLAG_MEDALLION)
    put("FLAG_ROOTS", Y.FLAG_ROOTS)
    put("FLAG_CUBE", f"0x{Y.FLAG_CUBE:02X}")
    put("FLAG_PLANTER", f"0x{Y.FLAG_PLANTER:02X}")
    put("FLAG_SUPPORT", f"0x{Y.FLAG_SUPPORT:02X}")
    put("T_SECRET", Y.T_SECRET)
    return "\n".join(d) + "\n"


HEADER = """#ifndef OBJECT_REMIX_YEARS_H
#define OBJECT_REMIX_YEARS_H

#include "ultra64.h"
#include "bgcheck.h"

// The Shrine of Seven Years' pieces (tools/remix/make_years_parts.py), drawn and moved by En_Remix_Years, and the
// shrine's plan (tools/remix/years_plan.py) in world coordinates.

{defines}
{decls}
#endif
"""


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    textures = write_textures()
    pieces = build_pieces()
    (OUT / "object_remix_years.c").write_text(emit(pieces, textures))
    decls = "".join(f"extern Gfx {PREFIX}{p.name}DL[];\n" + (f"extern CollisionHeader {PREFIX}{p.name}Col;\n"
                                                             if p.col else "") for p in pieces)
    (OUT / "object_remix_years.h").write_text(HEADER.format(defines=plan_defines(), decls=decls))
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file", str(OUT / "object_remix_years.c"), str(OUT / "object_remix_years.h")],
                       cwd=ROOT, check=True)
    print(f"Wrote {OUT.relative_to(ROOT)}: " + ", ".join(f"{p.name} {sum(len(t) for t in p.tris.values())}"
                                                        for p in pieces))


if __name__ == "__main__":
    main()
