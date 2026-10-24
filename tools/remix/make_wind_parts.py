#!/usr/bin/env python3
"""Generate object_remix_wind: the pieces of the Shrine of the Upside-Down Wind (Web Remix level 8), for En_Remix_Wind,
and the header that gives that actor the shrine's plan (tools/remix/wind_plan.py).

  CubeS, CubeM, CubeL      the three iron cubes (Magnesis moves them; light, medium, heavy)
  FanFloor, FanCeiling, Blades   the two fans' housings and their blades (turned when drawn)
  Plate, Bracket           the first ceiling switch (heavy), the bracket the medium cube locks into
  Timer                    the timed switch (eight seconds of upside-down gravity)
  Ladder1, Ladder2         the ladder to the middle balcony, the final ladder (lowered from the exit platform)
  Gate, Glass              the gate before the first ladder, the glass wall of the hidden treasure's chamber
  Column                   a unit cylinder drawn translucent: the wind

    python3 tools/remix/make_wind_parts.py     # writes assets/objects/object_remix_wind/ (committed)
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

import wind_plan as W
import make_years_parts as YP
from make_time_parts import Piece

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/objects/object_remix_wind"
INC = "assets/objects/object_remix_wind"


def iron(seed, line=None):
    rng = np.random.default_rng(seed)
    img = np.zeros((32, 32, 3)) + [70, 76, 90]
    img += rng.normal(0, 5, (32, 32, 1))
    img[0, :], img[:, 0] = [112, 118, 132], [112, 118, 132]
    img[31, :], img[:, 31] = [36, 38, 46], [36, 38, 46]
    for cx, cy in ((4, 4), (27, 4), (4, 27), (27, 27)):
        img[cy - 1 : cy + 2, cx - 1 : cx + 2] = [130, 134, 148]
    if line is not None:
        c = np.array(line, float)
        img[8, 8:25] = img[24, 8:25] = c
        img[8:25, 8] = img[8:25, 24] = c
        img[15:17, 15:17] = c
    return img


def grill():
    img = np.zeros((32, 32, 3)) + [40, 44, 52]
    img[::4, :] = [120, 126, 140]
    img[:, ::8] = [100, 104, 118]
    return img


def stone(seed):
    rng = np.random.default_rng(seed)
    img = np.zeros((32, 32, 3)) + [176, 184, 196]
    img *= 0.86 + 0.14 * rng.random((32, 32, 1))
    img[0, :] *= 0.7
    img[:, 0] *= 0.7
    return img


def write_textures():
    tex = {
        "wind_iron": iron(1),
        "wind_rune": iron(2, (110, 220, 255)),
        "wind_sun": iron(3, (255, 160, 60)),
        "wind_grill": grill(),
        "wind_stone": stone(4),
        "wind_wood": YP.wood(),
    }
    for name, img in tex.items():
        Image.fromarray(np.clip(img, 0, 255).round().astype(np.uint8)).convert("RGBA").save(OUT / f"{name}.rgba16.png")
    return list(tex)


def ladder(name, h, w=W.LADDER1["w"]):
    """Rails and rungs; the front (+z) climbable (a ladder wall), the back and sides plain."""
    p = Piece(name, dict(wall=2))
    hw = w / 2
    for x in (-hw, hw - 8):
        p.box(x, x + 8, 0, h, -8, 0, mat="wind_wood", tile=40, col=False)
    for y in np.arange(20, h, 25):
        p.box(-hw + 6, hw - 6, y - 3, y + 3, -6, -2, mat="wind_wood", tile=40, col=False)
    YP.add_col(p, [((-hw, 0, 0), (hw, 0, 0), (hw, h, 0)), ((-hw, 0, 0), (hw, h, 0), (-hw, h, 0))])
    return p


def build_pieces():
    out = []
    for name, c in (("CubeS", W.CUBES[0]), ("CubeM", W.CUBES[1]), ("CubeL", W.CUBES[2])):
        s = c["size"] / 2
        p = Piece(name)
        p.box(-s, s, 0, 2 * s, -s, s, mat="wind_rune" if name != "CubeL" else "wind_sun", top="wind_rune", tile=2 * s)
        out.append(p)

    r = W.FAN_R + 15
    p = Piece("FanFloor")
    p.cylinder("wind_iron", r, r, 0, 20, n=12, col=True, cap_top="wind_grill")
    out.append(p)
    p = Piece("FanCeiling")  # hangs from the ceiling (y 0) down to its grill
    drop = W.CEIL - W.CEIL_FAN_BOTTOM
    p.cylinder("wind_iron", r, r, -drop, 0, n=12, col=True, cap_bottom="wind_grill")
    out.append(p)
    p = Piece("Blades")
    for k in range(4):
        a = k * math.pi / 2
        s, co = math.sin(a), math.cos(a)
        t0, t1 = a - 0.25, a + 0.25
        pts = [(0, 0, 0), (math.sin(t0) * (r - 10), 4, math.cos(t0) * (r - 10)),
               (math.sin(t1) * (r - 10), -4, math.cos(t1) * (r - 10))]
        p.tri("wind_iron", pts, [(0, 0), (32, 0), (32, 32)], (0, 1, 0))
        p.tri("wind_iron", [pts[0], pts[2], pts[1]], [(0, 0), (32, 32), (32, 0)], (0, -1, 0))
    p.cylinder("wind_sun", 12, 12, -6, 6, n=8, cap_top="wind_sun", cap_bottom="wind_sun")
    out.append(p)

    pl = W.PLATE
    p = Piece("Plate")
    p.box(-pl["w"] / 2, pl["w"] / 2, -pl["t"], 0, -pl["w"] / 2, pl["w"] / 2, mat="wind_iron", bottom="wind_sun", tile=110)
    out.append(p)
    p = Piece("Bracket")  # a cage of bars round where the medium cube locks (its centre at y -36 under the ceiling)
    cm = W.CUBES[1]["size"] / 2 + 4
    for sx in (-1, 1):
        for sz in (-1, 1):
            p.box(sx * cm - 4, sx * cm + 4, -2 * cm, 0, sz * cm - 4, sz * cm + 4, mat="wind_sun", tile=30, col=False)
    p.box(-cm - 4, cm + 4, -2 * cm - 6, -2 * cm, -cm - 4, -cm + 4, mat="wind_sun", tile=30, col=False)
    p.box(-cm - 4, cm + 4, -2 * cm - 6, -2 * cm, cm - 4, cm + 4, mat="wind_sun", tile=30, col=False)
    out.append(p)
    p = Piece("Timer")
    p.cylinder("wind_iron", 44, 40, 0, 12, n=12, col=True, cap_top="wind_sun")
    out.append(p)

    out.append(ladder("Ladder1", W.BALCONY["top"]))
    out.append(ladder("Ladder2", W.EXIT_PLATFORM["top"] - W.LADDER2["bottom"]))

    g = W.GATE1
    p = Piece("Gate")
    for z in np.arange(-g["w"] / 2 + 8, g["w"] / 2, 20):
        p.box(-5, 5, 0, g["h"], z - 4, z + 4, mat="wind_iron", tile=40, col=False)
    p.box(-6, 6, g["h"] - 20, g["h"], -g["w"] / 2, g["w"] / 2, mat="wind_sun", tile=40, col=False)
    YP.colbox(p, -6, 6, 0, g["h"], -g["w"] / 2, g["w"] / 2)
    out.append(p)
    gr = W.GLASS_ROOM
    gw = gr["x1"] - gr["x0"]
    p = Piece("Glass")  # along x, facing +z (towards the balcony)
    p.box(-gw / 2, gw / 2, 0, gr["ceil"] - gr["floor"], -4, 4, mat="xlu", col=False)
    for x in (-gw / 2, 0, gw / 2 - 8):
        p.box(x, x + 8, 0, gr["ceil"] - gr["floor"], -6, 6, mat="wind_iron", tile=40, col=False)
    YP.colbox(p, -gw / 2, gw / 2, 0, gr["ceil"] - gr["floor"], -6, 6)
    out.append(p)
    p = Piece("Column")
    p.cylinder("beam", 1, 1, 0, 1, n=10)
    out.append(p)
    return out


def plan_defines():
    d = []

    def put(name, v):
        d.append(f"#define WIND_{name} {v}")

    def f(v):
        return f"{float(v):.1f}f"

    put("CEIL", f(W.CEIL))
    put("COLUMN_X", f(W.COLUMN[0]))
    put("COLUMN_Z", f(W.COLUMN[1]))
    put("FAN_R", f(W.FAN_R))
    put("CEIL_FAN_BOTTOM", f(W.CEIL_FAN_BOTTOM))
    put("COLUMN_MID", f(W.COLUMN_MID))
    put("HOVER_MID", f(W.HOVER_MID))
    put("HOVER_AMP", f(W.HOVER_AMP))
    put("HOVER_PERIOD", W.HOVER_PERIOD)
    put("CUBE_SIZES", "{ " + ", ".join(f"{c['size']}.0f" for c in W.CUBES) + " }")
    put("RIDE_TOP_CHILD", f(W.RIDE_TOP["child"]))
    put("RIDE_TOP_ADULT", f(W.RIDE_TOP["adult"]))
    put("PLATE_X", f(W.PLATE["x"]))
    put("PLATE_Z", f(W.PLATE["z"]))
    put("PLATE_HALF", f(W.PLATE["w"] / 2))
    put("PLATE_BOTTOM", f(W.CEIL - W.PLATE["t"]))
    put("BRACKET_X", f(W.BRACKET[0]))
    put("BRACKET_Y", f(W.BRACKET[1]))
    put("BRACKET_Z", f(W.BRACKET[2]))
    put("TIMER_FRAMES", W.TIMER_FRAMES)
    put("GATE_DROP", f(-W.GATE1["h"] - 10))
    put("GLASS_DROP", f(-(W.GLASS_ROOM["ceil"] - W.GLASS_ROOM["floor"]) - 40))
    put("LADDER2_LIFT", f(W.LADDER2["lift"]))
    h = W.HOLE
    put("HOLE_X", f(h["x"]))
    put("HOLE_Z", f(h["z"]))
    put("HOLE_HALF", f(h["w"] / 2))
    put("GLASS_CAP", f(W.GLASS_CAP))
    for k, v in (("FANS", W.FLAG_FANS), ("P1", W.FLAG_P1), ("WEDGED", W.FLAG_WEDGED), ("BRACKET", W.FLAG_BRACKET),
                 ("LADDER", W.FLAG_LADDER), ("GLASS", W.FLAG_GLASS), ("P2", W.FLAG_P2)):
        put(f"FLAG_{k}", v)
    return "\n".join(d) + "\n"


HEADER = """#ifndef OBJECT_REMIX_WIND_H
#define OBJECT_REMIX_WIND_H

#include "ultra64.h"
#include "bgcheck.h"

// The Shrine of the Upside-Down Wind's pieces (tools/remix/make_wind_parts.py), drawn and moved by En_Remix_Wind, and
// the shrine's plan (tools/remix/wind_plan.py) in world coordinates.

{defines}
{decls}
#endif
"""


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    YP.PREFIX, YP.INC = "gWind", INC
    textures = write_textures()
    pieces = build_pieces()
    text = YP.emit(pieces, textures).replace("make_years_parts.py - the Shrine of Seven Years' pieces",
                                              "make_wind_parts.py - the Shrine of the Upside-Down Wind's pieces")
    text = text.replace('#include "object_remix_years.h"', '#include "object_remix_wind.h"')
    (OUT / "object_remix_wind.c").write_text(text)
    decls = "".join(f"extern Gfx gWind{p.name}DL[];\n" + (f"extern CollisionHeader gWind{p.name}Col;\n" if p.col else "")
                    for p in pieces)
    (OUT / "object_remix_wind.h").write_text(HEADER.format(defines=plan_defines(), decls=decls))
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file", str(OUT / "object_remix_wind.c"), str(OUT / "object_remix_wind.h")],
                       cwd=ROOT, check=True)
    print(f"Wrote {OUT.relative_to(ROOT)}: " + ", ".join(f"{p.name} {sum(len(t) for t in p.tris.values())}"
                                                        for p in pieces))


if __name__ == "__main__":
    main()
