#!/usr/bin/env python3
"""Generate object_remix_abyss: the pieces of the Shrine of the Swinging Abyss (Web Remix level 9), for En_Remix_Abyss,
and the header that gives that actor the shrine's plan (tools/remix/abyss_plan.py): every moving platform's motion.

  Plat0 .. PlatN   each moving platform: a stone slab, a post with a Hookshot target plaque (its face a Hookshot
                   surface), a tower's piston under it
  Target, Cracked  the plaque's emblem (drawn glowing when it is in reach; the cracked one marks a platform that
                   breaks away under Link)
  Chain            a unit length of chain (the pendulums hang from two)
  Ring             the stone ring turning round the exit balcony, one opening in it
  Cube, Ramp, Bars, Door   the stone room: the cube (pushed), the ramp the crystal raises, the bars before the
                   Hookshot's chest, the door to the abyss

    python3 tools/remix/make_abyss_parts.py     # writes assets/objects/object_remix_abyss/ (committed)
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import abyss_plan as A
import make_years_parts as YP
from make_time_parts import Piece

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/objects/object_remix_abyss"
INC = "assets/objects/object_remix_abyss"

HOOK_SURFACE = ("{ { SURFACETYPE0(0, 0, FLOOR_TYPE_0, 0, WALL_TYPE_0, FLOOR_PROPERTY_0, false, false), "
                "SURFACETYPE1(SURFACE_MATERIAL_WOOD, FLOOR_EFFECT_0, 0, 0, true, CONVEYOR_SPEED_DISABLED, 0, false) } },\n")
HOOK = 1  # collision surface index of a Hookshot target


def stone(seed, base=(120, 116, 128), grain=0.16, line=None):
    rng = np.random.default_rng(seed)
    img = np.zeros((32, 32, 3)) + base
    img *= (1 - grain) + grain * rng.random((32, 32, 1))
    img[0, :] *= 0.7
    img[:, 0] *= 0.7
    if line is not None:
        img[3:5, 3:29] = img[27:29, 3:29] = line
    return img


def iron(seed):
    rng = np.random.default_rng(seed)
    img = np.zeros((32, 32, 3)) + [64, 60, 58]
    img += rng.normal(0, 5, (32, 32, 1))
    for y in range(4, 32, 8):
        img[y, :] = [96, 90, 84]
    return img


def target(cracked=False):
    """The Hookshot target: rings of red and gold round a dark centre (cracked: dull, split)."""
    S = 128
    im = Image.new("RGB", (S, S), (40, 32, 28))
    d = ImageDraw.Draw(im)
    cols = [(200, 150, 60), (150, 40, 34), (230, 200, 120), (150, 40, 34), (40, 30, 26)]
    if cracked:
        cols = [(120, 100, 80), (90, 60, 50), (140, 120, 100), (90, 60, 50), (40, 30, 26)]
    for k, c in enumerate(cols):
        r = S / 2 - 4 - k * 12
        d.ellipse([S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r], fill=c)
    d.polygon([(S / 2, 34), (S - 34, S / 2), (S / 2, S - 34), (34, S / 2)], outline=(240, 220, 150), width=5)
    if cracked:
        for pts in ([(20, 10), (54, 50), (48, 70), (80, 118)], [(54, 50), (100, 40)], [(48, 70), (12, 90)]):
            d.line(pts, fill=(20, 14, 10), width=6)
    return np.array(im.resize((32, 32), Image.LANCZOS)).astype(float)


def write_textures():
    tex = {
        "abyss_slab": stone(1, (128, 124, 136), line=(170, 150, 100)),
        "abyss_side": stone(2, (92, 88, 100)),
        "abyss_bronze": stone(3, (150, 112, 60), grain=0.25),
        "abyss_iron": iron(4),
        "abyss_target": target(),
        "abyss_cracked": target(True),
        "abyss_room": stone(5, (150, 140, 128)),
        "abyss_bars": iron(6),
    }
    for name, img in tex.items():
        Image.fromarray(np.clip(img, 0, 255).round().astype(np.uint8)).convert("RGBA").save(OUT / f"{name}.rgba16.png")
    return list(tex)


def slab(p, w, d, t=30, top="abyss_slab", side="abyss_side", col=True):
    """A slab from y -t to 0 (no bottom face in the collision: nothing stands under it)."""
    hw, hd = w / 2, d / 2
    p.box(-hw, hw, -t, 0, -hd, hd, mat=side, top=top, tile=64, col=False)
    if col:
        YP.colbox(p, -hw, hw, -t, 0, -hd, hd, skip=("bottom",))


def platform(i, q):
    """Platform i: slab, post and plaque (the plaque's face, at local z = plz facing +z, is the Hookshot surface)."""
    p = Piece(f"Plat{i}")
    slab(p, q["w"], q["d"])
    lx, lz = q["plaque"]
    ph = q["ph"]
    # the post behind the plaque, the plaque's frame
    p.box(lx - 14, lx + 14, 0, ph + 46, lz - 34, lz - 8, mat="abyss_bronze", tile=40, col=False)
    p.box(lx - 36, lx + 36, ph - 36, ph + 36, lz - 8, lz, mat="abyss_bronze", tile=40, col=False)
    YP.add_col(p, [((lx - 32, ph - 32, lz), (lx + 32, ph - 32, lz), (lx + 32, ph + 32, lz)),
                   ((lx - 32, ph - 32, lz), (lx + 32, ph + 32, lz), (lx - 32, ph + 32, lz))], surf=HOOK)
    if q["kind"] == A.LIFT:  # the tower's piston, down into the dark
        p.cylinder("abyss_iron", 26, 26, -760, -30, n=8, cap_top=None)
    if q["kind"] == A.ORBIT:  # an arm back towards the axis it turns round
        p.box(-10, 10, -26, -14, -q["radius"] + 60 if q["radius"] < 400 else -120, -q["d"] / 2, mat="abyss_iron",
              tile=40, col=False)
    p.surfaces_c = YP.SURFACE.format(wall=0, mat="STONE") + HOOK_SURFACE
    return p


def ring():
    r, h = A.RING["r"], A.RING["y1"] - A.RING["y0"]
    n = 16
    half_gap = A.RING["gap"] / 2 / r  # radians each side of local +z
    p = Piece("Ring")
    skip = set()
    for k in range(n):
        mid = 2 * math.pi * (k + 0.5) / n
        if abs(math.atan2(math.sin(mid), math.cos(mid))) < half_gap + math.pi / n:
            skip.add(k)  # the opening (round local +z)
    for k in range(n):
        if k in skip:
            continue
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        mid = (a0 + a1) / 2
        o0, o1 = (math.sin(a0) * r, math.cos(a0) * r), (math.sin(a1) * r, math.cos(a1) * r)
        i0, i1 = (math.sin(a0) * (r - 14), math.cos(a0) * (r - 14)), (math.sin(a1) * (r - 14), math.cos(a1) * (r - 14))
        out = (math.sin(mid), 0, math.cos(mid))
        p.quad("abyss_side", [(o0[0], 0, o0[1]), (o1[0], 0, o1[1]), (o1[0], h, o1[1]), (o0[0], h, o0[1])], out, col=True)
        p.quad("abyss_side", [(i1[0], 0, i1[1]), (i0[0], 0, i0[1]), (i0[0], h, i0[1]), (i1[0], h, i1[1])],
               (-out[0], 0, -out[2]), col=False)
        p.quad("abyss_bronze", [(o0[0], h, o0[1]), (o1[0], h, o1[1]), (i1[0], h, i1[1]), (i0[0], h, i0[1])], (0, 1, 0),
               col=False)
        p.quad("abyss_bronze", [(o0[0], 0, o0[1]), (i0[0], 0, i0[1]), (i1[0], 0, i1[1]), (o1[0], 0, o1[1])], (0, -1, 0),
               col=False)
        # the opening's faces: where a wall segment meets it
        for a, nb in ((a0, (k - 1) % n), (a1, (k + 1) % n)):
            if nb in skip:
                o, i_ = (math.sin(a) * r, math.cos(a) * r), (math.sin(a) * (r - 14), math.cos(a) * (r - 14))
                t = (math.cos(a), 0, -math.sin(a)) if nb == (k + 1) % n else (-math.cos(a), 0, math.sin(a))
                p.quad("abyss_bronze", [(o[0], 0, o[1]), (i_[0], 0, i_[1]), (i_[0], h, i_[1]), (o[0], h, o[1])], t,
                       col=False)
    return p


def build_pieces():
    out = [platform(i, q) for i, q in enumerate(A.P)]
    for name, mat in (("Target", "abyss_target"), ("Cracked", "abyss_cracked")):
        p = Piece(name)
        p.quad(mat, [(-30, -30, 0), (30, -30, 0), (30, 30, 0), (-30, 30, 0)], (0, 0, 1), col=False, tile=60)
        out.append(p)
    p = Piece("Chain")  # from the origin down one unit (scaled by the length)
    for k in range(4):
        y0, y1 = -k / 4, -(k + 1) / 4
        w = 5 if k % 2 == 0 else 3
        p.box(-w, w, y1, y0, -(8 - w), 8 - w, mat="abyss_iron", tile=40, col=False)
    out.append(p)
    out.append(ring())

    c = A.CUBE / 2
    p = Piece("Cube", dict(wall=7))  # (a push block)
    p.box(-c, c, 0, A.CUBE, -c, c, mat="abyss_room", top="abyss_slab", tile=A.CUBE)
    out.append(p)
    r = A.RAMP
    p = Piece("Ramp")  # its hinge (the south edge) at the origin, reaching north
    p.box(-r["w"] / 2, r["w"] / 2, -20, 0, -(r["z1"] - r["z0"]), 0, mat="abyss_side", top="abyss_slab", tile=60)
    out.append(p)
    b = A.BARS
    p = Piece("Bars")
    for x in np.arange(-b["w"] / 2 + 8, b["w"] / 2, 16):
        p.box(x - 3, x + 3, 0, b["h"], -3, 3, mat="abyss_bars", tile=40, col=False)
    p.box(-b["w"] / 2, b["w"] / 2, b["h"] - 12, b["h"], -5, 5, mat="abyss_bronze", tile=40, col=False)
    YP.colbox(p, -b["w"] / 2, b["w"] / 2, 0, b["h"], -6, 6)
    out.append(p)
    d = A.DOOR
    p = Piece("Door")
    p.box(-d["w"] / 2, d["w"] / 2, 0, d["h"], -10, 10, mat="abyss_room", tile=60)
    out.append(p)
    return out


def collision(p):
    text = ORIG_COLLISION(p)
    if hasattr(p, "surfaces_c"):
        nm = f"{YP.PREFIX}{p.name}"
        start = text.index(f"SurfaceType {nm}ColSurfaces[] = {{\n")
        end = text.index("};\n", start) + 3
        text = text[:start] + f"SurfaceType {nm}ColSurfaces[] = {{\n    " + p.surfaces_c + "};\n" + text[end:]
    return text


ORIG_COLLISION = YP.collision


def plan_defines():
    d = []

    def put(name, v):
        d.append(f"#define ABYSS_{name} {v}")

    def f(v):
        return f"{float(v):.1f}f"

    put("HOOK_RANGE", f(A.HOOK))
    put("FALL_Y", f(A.FALL_Y))
    put("RESPAWN_X", f(A.RESPAWN[0]))
    put("RESPAWN_Y", f(A.RESPAWN[1]))
    put("RESPAWN_Z", f(A.RESPAWN[2]))
    put("CUBE_SIZE", f(A.CUBE))
    put("CUBE_CELLS", "{ " + ", ".join("{ %d, %d }" % c for c in A.CUBE_CELLS) + " }")
    put("RAMP_X", f(A.RAMP["x"]))
    put("RAMP_Z", f(A.RAMP["z0"] + (A.RAMP["z1"] - A.RAMP["z0"]) / 2))
    put("RAMP_HINGE_Z", f(A.RAMP["z1"]))
    put("RAMP_LIFT", f(A.RAMP["lift"]))
    put("TRENCH_Y", f(-A.TRENCH["depth"]))
    put("SWITCH_X", f(A.SWITCH[0]))
    put("SWITCH_Z", f(A.SWITCH[1]))
    put("BARS_H", f(A.BARS["h"]))
    put("DOOR_H", f(A.DOOR["h"]))
    put("CRYSTAL_X", f(A.CRYSTAL[0]))
    put("CRYSTAL_Y", f(A.CRYSTAL[1]))
    put("CRYSTAL_Z", f(A.CRYSTAL[2] + 25))
    put("RING_PERIOD", A.RING["period"])
    put("CORE_X", f(A.CORE[0]))
    put("CORE_Z", f(A.CORE[1]))
    for k, v in (("RAMP", A.FLAG_RAMP), ("BARS", A.FLAG_BARS), ("CUBE_RAMP", A.FLAG_CUBE_RAMP),
                 ("CUBE_IN", A.FLAG_CUBE_IN)):
        put(f"FLAG_{k}", v)
    for k, v in (("HOOK", A.T_HOOK), ("HIDDEN", A.T_HIDDEN), ("HEART", A.T_HEART)):
        put(f"T_{k}", v)
    put("PLATS_N", len(A.P))
    rows = []
    for q in A.P:
        k = q["kind"]
        if k == A.PENDULUM:
            a = [*q["pivot"], q["length"], q["amp"], q["period"], q["phase"], q["axis"], 0]
        elif k == A.ORBIT:
            a = [q["center"][0], q["top"], q["center"][1], q["radius"], q["period"], q["phase"], 0, 0, 0]
        elif k == A.LIFT:
            a = [q["at"][0], q["at"][1], q["lo"], q["hi"], q["period"], q["phase"], 0, 0, 0]
        else:
            a = [*q["a"], *q["b"], q["move"], q["dwell"], q["phase"]]
        yaw = int(round(q["yaw"] / 360 * 0x10000)) & 0xFFFF
        if yaw >= 0x8000:
            yaw -= 0x10000
        rows.append("{ %d, %d, %d, %d, %d, %d, %d, %d, { %s } }" % (
            k, q["w"], q["d"], yaw, q["plaque"][0], q["plaque"][1], q["ph"], int(q["crumble"]),
            ", ".join(f"{float(v):.4f}f" for v in a)))
    put("PLATS", "{ " + ", ".join(rows) + " }")
    return "\n".join(d) + "\n"


HEADER = """#ifndef OBJECT_REMIX_ABYSS_H
#define OBJECT_REMIX_ABYSS_H

#include "ultra64.h"
#include "bgcheck.h"

// The Shrine of the Swinging Abyss's pieces (tools/remix/make_abyss_parts.py), drawn and moved by En_Remix_Abyss, and
// the shrine's plan (tools/remix/abyss_plan.py) in world coordinates.

// A moving platform: kind (0 pendulum, 1 orbit, 2 lift, 3 shuttle), slab size, yaw, the target plaque's place
// (local x, z, height), whether it breaks away under Link, and its motion:
//   pendulum: pivot x, y, z, length, amplitude (degrees), period, phase, swing direction (degrees)
//   orbit:    centre x, top, centre z, radius, period (negative: clockwise), phase
//   lift:     x, z, lowest top, highest top, period, phase
//   shuttle:  a x, y, z, b x, y, z, frames moving, frames waiting at each end, phase
typedef struct AbyssPlatInfo {{
    s16 kind;
    s16 w;
    s16 d;
    s16 yaw;
    s16 plaqueX;
    s16 plaqueZ;
    s16 plaqueY;
    s16 crumble;
    f32 m[9];
}} AbyssPlatInfo;

{defines}
{decls}
// (for tables in the actor's own data: the object is only reached through segment 6 by the RSP and the bgcheck)
#define ABYSS_PLAT_DLS {{ {dls} }}
#define ABYSS_PLAT_COLS {{ {cols} }}

#endif
"""


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    YP.PREFIX, YP.INC = "gAbyss", INC
    YP.collision = collision
    textures = write_textures()
    pieces = build_pieces()
    text = YP.emit(pieces, textures).replace("make_years_parts.py - the Shrine of Seven Years' pieces",
                                              "make_abyss_parts.py - the Shrine of the Swinging Abyss's pieces")
    text = text.replace('#include "object_remix_years.h"', '#include "object_remix_abyss.h"')
    (OUT / "object_remix_abyss.c").write_text(text)
    decls = "".join(f"extern Gfx gAbyss{p.name}DL[];\n" + (f"extern CollisionHeader gAbyss{p.name}Col;\n" if p.col else "")
                    for p in pieces)
    n = len(A.P)
    (OUT / "object_remix_abyss.h").write_text(HEADER.format(
        defines=plan_defines(), decls=decls, dls=", ".join(f"gAbyssPlat{i}DL" for i in range(n)),
        cols=", ".join(f"&gAbyssPlat{i}Col" for i in range(n))))
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file", str(OUT / "object_remix_abyss.c"), str(OUT / "object_remix_abyss.h")],
                       cwd=ROOT, check=True)
    print(f"Wrote {OUT.relative_to(ROOT)}: " + ", ".join(f"{p.name} {sum(len(t) for t in p.tris.values())}"
                                                        for p in pieces))
    cols = sum(len(p.col) for p in pieces if p.name.startswith("Plat") or p.name in ("Ring", "Cube", "Ramp", "Bars",
                                                                                      "Door"))
    print(f"collision triangles in the moving pieces: {cols} (the dynamic collision holds 512)")


if __name__ == "__main__":
    main()
