#!/usr/bin/env python3
"""Generate object_remix_magnet: the moving pieces of the Lodestone Shrine (Web Remix level 4), for En_Remix_Magnet.

  crate   70 x 70 x 70 iron block (magnetic: presses floor switches)
  girder  340 long iron beam (magnetic: a bridge once it is laid across a gap)
  slab    the iron door slab in the north wall's doorway (magnetic)
  lift    160 x 160 platform that rides up to the balcony while its switch is held (powered, not magnetic)
  bridge  the L-shaped bridge on the chasm's pivot, turned by the crystal switches (powered, not magnetic)
  beam    the Magnesis beam (a unit tube along +z, scaled when drawn)

Each piece has a display list and (but the beam) a collision header, all in model units = game units (the actor is
drawn and collides at scale 1). Iron is textured, lit by baked vertex colours, and drawn with the environment colour
added on top: En_Remix_Magnet sets it to a pulsing magenta while a piece is aimed at or held.

    python3 tools/remix/make_magnet_parts.py     # writes assets/objects/object_remix_magnet/ (committed)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/objects/object_remix_magnet"
INC = "assets/objects/object_remix_magnet"

# piece sizes (also used by make_magnet.py for the level's layout)
CRATE = 70
GIRDER = (340, 24, 60)  # length (x), height (y), width (z)
SLAB = (250, 220, 30)  # width (x), height (y), thickness (z)
LIFT = (160, 30, 160)  # top at y = 0
BRIDGE_ARM, BRIDGE_W, BRIDGE_PAD, BRIDGE_T = 535, 120, 170, 40  # arm reach from the pivot, width, centre pad, depth

MAGENTA = (255, 60, 200)
ORANGE = (255, 150, 40)
LIGHT = np.array([0.35, 0.8, 0.5]) / np.linalg.norm([0.35, 0.8, 0.5])


# ---------------------------------------------------------------- textures


def iron_base(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.zeros((32, 32, 3)) + [66, 70, 82]
    img += rng.normal(0, 5, (32, 32, 1))
    img += np.linspace(-6, 6, 32)[None, :, None]  # brushed
    img[0, :], img[:, 0] = [105, 110, 124], [105, 110, 124]  # bevelled plate edges
    img[31, :], img[:, 31] = [34, 36, 44], [34, 36, 44]
    for cx, cy in ((4, 4), (27, 4), (4, 27), (27, 27)):  # rivets
        img[cy - 1 : cy + 2, cx - 1 : cx + 2] = [118, 122, 136]
        img[cy + 1, cx - 1 : cx + 2] = [40, 42, 50]
        img[cy, cx] = [160, 164, 176]
    return img


def circuit(img: np.ndarray, color) -> np.ndarray:
    img = img.copy()
    c = np.array(color, float)
    for a, b in ((8, 24),):
        img[a, a : b + 1] = c
        img[b, a : b + 1] = c
        img[a : b + 1, a] = c
        img[a : b + 1, b] = c
    img[15:17, 15:17] = c
    for y, x0, x1 in ((16, 0, 8), (16, 24, 32)):
        img[y, x0:x1] = c * 0.8
    img[12:21, 12] = c * 0.6
    img[12:21, 20] = c * 0.6
    return img


def write_textures():
    tex = {
        "magnet_iron": iron_base(1),
        "magnet_rune": circuit(iron_base(2), MAGENTA),
        "magnet_sun": circuit(iron_base(3), ORANGE),
    }
    for name, img in tex.items():
        Image.fromarray(np.clip(img, 0, 255).round().astype(np.uint8)).save(OUT / f"{name}.rgba16.png")
    return list(tex)


# ---------------------------------------------------------------- geometry


class Piece:
    def __init__(self, name: str):
        self.name = name
        self.tris: dict[str, list] = {}  # texture -> [(p, uv, normal) x3]
        self.col: list = []  # collision triangles

    def quad(self, tex: str, pts, normal, col=True, tile=70.0):
        pts = [np.array(p, float) for p in pts]
        n = np.array(normal, float)
        # planar UVs in the face's own axes (32 texels per `tile` units)
        ax_u = pts[1] - pts[0]
        ax_u /= np.linalg.norm(ax_u)
        ax_v = np.cross(n, ax_u)
        uv = [(float(np.dot(p - pts[0], ax_u)) / tile * 32, float(np.dot(p - pts[0], ax_v)) / tile * 32) for p in pts]
        for i, j, k in ((0, 1, 2), (0, 2, 3)):
            tri = [pts[i], pts[j], pts[k]]
            if np.dot(np.cross(tri[1] - tri[0], tri[2] - tri[0]), n) < 0:
                tri, tuv = [tri[0], tri[2], tri[1]], [uv[i], uv[k], uv[j]]
            else:
                tuv = [uv[i], uv[j], uv[k]]
            self.tris.setdefault(tex, []).append((tri, tuv, n))
            if col:
                self.col.append(tri)

    def box(self, x0, x1, y0, y1, z0, z1, top="magnet_iron", side="magnet_iron", bottom="magnet_iron", col=True):
        self.quad(top, [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0), col)
        self.quad(bottom, [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)], (0, -1, 0), col)
        st = side if isinstance(side, dict) else dict(n=side, s=side, e=side, w=side)
        self.quad(st["s"], [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1), col)
        self.quad(st["n"], [(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)], (0, 0, -1), col)
        self.quad(st["e"], [(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)], (1, 0, 0), col)
        self.quad(st["w"], [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], (-1, 0, 0), col)


def build_pieces() -> list[Piece]:
    out = []
    h = CRATE / 2
    p = Piece("Crate")
    p.box(-h, h, 0, CRATE, -h, h, top="magnet_rune", side="magnet_rune")
    out.append(p)

    gl, gh, gw = GIRDER
    p = Piece("Girder")
    p.box(-gl / 2, gl / 2, 0, gh, -gw / 2, gw / 2, top="magnet_rune")
    out.append(p)

    sw, sh, st = SLAB
    p = Piece("Slab")
    p.box(-sw / 2, sw / 2, 0, sh, -st / 2, st / 2, side=dict(n="magnet_rune", s="magnet_rune", e="magnet_iron",
                                                            w="magnet_iron"))
    out.append(p)

    lw, lt, ld = LIFT
    p = Piece("Lift")
    p.box(-lw / 2, lw / 2, -lt, 0, -ld / 2, ld / 2, top="magnet_sun")
    out.append(p)

    # the bridge: a centre pad and two arms, towards +z (south at yaw 0) and -x (west at yaw 0)
    a, w, c, t = BRIDGE_ARM, BRIDGE_W / 2, BRIDGE_PAD / 2, BRIDGE_T
    p = Piece("Bridge")
    p.box(-c, c, -t, 0, -c, c, top="magnet_sun")
    p.box(-w, w, -t, 0, c, a, top="magnet_sun")
    p.box(-a, -c, -t, 0, -w, w, top="magnet_sun")
    out.append(p)
    return out


def shade(n) -> int:
    return int(round(255 * min(1.0, 0.5 + 0.55 * max(0.0, float(np.dot(n, LIGHT))))))


def emit(pieces: list[Piece], textures: list[str]) -> str:
    sym = {t: "g" + "".join(s.capitalize() for s in t.split("_")) + "Tex" for t in textures}
    s = ["// Generated by tools/remix/make_magnet_parts.py - the Lodestone Shrine's moving pieces. Do not edit.\n",
         '#include "object_remix_magnet.h"\n#include "gfx.h"\n#include "array_count.h"\n#include "camera.h"\n\n']
    for t in textures:
        s.append(f"u64 {sym[t]}[] = {{\n#include \"{INC}/{t}.rgba16.inc.c\"\n}};\n\n")
    for p in pieces:
        vtx, dl = [], []
        dl += ["    gsDPPipeSync(),", "    gsDPSetCycleType(G_CYC_1CYCLE),",
               "    gsSPClearGeometryMode(G_LIGHTING | G_FOG | G_CULL_BOTH | G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR),",
               "    gsSPSetGeometryMode(G_SHADE | G_SHADING_SMOOTH | G_ZBUFFER | G_CULL_BACK),",
               "    gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON),", "    gsDPSetTextureLUT(G_TT_NONE),",
               "    gsDPSetCombineLERP(TEXEL0, 0, SHADE, ENVIRONMENT, 0, 0, 0, 1, TEXEL0, 0, SHADE, ENVIRONMENT, 0, 0, 0, 1),",
               "    gsDPSetRenderMode(G_RM_AA_ZB_OPA_SURF, G_RM_AA_ZB_OPA_SURF2),"]
        for tex, tris in p.tris.items():
            dl.append(f"    gsDPLoadTextureBlock({sym[tex]}, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, G_TX_NOMIRROR | G_TX_WRAP,"
                      " G_TX_NOMIRROR | G_TX_WRAP, 5, 5, G_TX_NOLOD, G_TX_NOLOD),")
            for k in range(0, len(tris), 5):  # 5 triangles (15 vertices) per load
                chunk = tris[k : k + 5]
                dl.append(f"    gsSPVertex(&g{'Magnet' + p.name}Vtx[{len(vtx)}], {3 * len(chunk)}, 0),")
                for tri, uv, n in chunk:
                    c = shade(n)
                    for q, (u, v) in zip(tri, uv):
                        vtx.append(f"    VTX({int(round(q[0]))}, {int(round(q[1]))}, {int(round(q[2]))}, "
                                   f"{int(round(u * 32))}, {int(round(v * 32))}, {c}, {c}, {c}, 255),")
                for i in range(0, len(chunk) - 1, 2):
                    dl.append(f"    gsSP2Triangles({3 * i}, {3 * i + 1}, {3 * i + 2}, 0, {3 * i + 3}, {3 * i + 4}, {3 * i + 5}, 0),")
                if len(chunk) % 2:
                    i = len(chunk) - 1
                    dl.append(f"    gsSP1Triangle({3 * i}, {3 * i + 1}, {3 * i + 2}, 0),")
        dl += ["    gsSPEndDisplayList(),"]
        s.append(f"Vtx gMagnet{p.name}Vtx[] = {{\n" + "\n".join(vtx) + "\n};\n\n")
        s.append(f"Gfx gMagnet{p.name}DL[] = {{\n" + "\n".join(dl) + "\n};\n\n")
        s.append(collision(p))
    s.append(beam())
    return "".join(s)


def collision(p: Piece) -> str:
    vid, verts, polys = {}, [], []
    for tri in p.col:
        ids = []
        for q in tri:
            key = tuple(int(round(c)) for c in q)
            if key not in vid:
                vid[key] = len(verts)
                verts.append(key)
            ids.append(vid[key])
        a, b, c = (np.array(verts[i], float) for i in ids)
        n = np.cross(b - a, c - a)
        n /= np.linalg.norm(n)
        polys.append((ids, [int(round(x * 0x7FFF)) for x in n], int(round(-np.dot(n, a)))))
    arr = np.array(verts)
    lo, hi = arr.min(0), arr.max(0)
    nm = f"gMagnet{p.name}"
    s = [f"Vec3s {nm}ColVtx[] = {{\n" + "".join(f"    {{ {v[0]}, {v[1]}, {v[2]} }},\n" for v in verts) + "};\n\n",
         f"CollisionPoly {nm}ColPolys[] = {{\n" +
         "".join(f"    {{ 0, {{ COLPOLY_VTX({i[0]}, 0), COLPOLY_VTX({i[1]}, 0), {i[2]} }}, {{ {n[0]}, {n[1]}, {n[2]} }}, {d} }},\n"
                 for i, n, d in polys) + "};\n\n",
         f"SurfaceType {nm}ColSurfaces[] = {{\n    {{ {{ SURFACETYPE0(0, 0, FLOOR_TYPE_0, 0, WALL_TYPE_0, FLOOR_PROPERTY_0, false, "
         "false), SURFACETYPE1(SURFACE_MATERIAL_STONE, FLOOR_EFFECT_0, 0, 0, false, CONVEYOR_SPEED_DISABLED, 0, false) } },\n};\n\n",
         f"CollisionHeader {nm}Col = {{\n    {{ {lo[0]}, {lo[1]}, {lo[2]} }},\n    {{ {hi[0]}, {hi[1]}, {hi[2]} }},\n"
         f"    ARRAY_COUNT({nm}ColVtx),\n    {nm}ColVtx,\n    ARRAY_COUNT({nm}ColPolys),\n    {nm}ColPolys,\n"
         f"    {nm}ColSurfaces,\n    NULL,\n    0,\n    NULL,\n}};\n\n"]
    return "".join(s)


def beam() -> str:
    """A square tube from z = 0 to z = 1000, 10 wide (drawn translucent, scaled to the distance)."""
    r, ln = 5, 1000
    corners = [(-r, -r), (r, -r), (r, r), (-r, r)]
    vtx = []
    for z in (0, ln):
        for x, y in corners:
            vtx.append(f"    VTX({x}, {y}, {z}, 0, 0, 255, 255, 255, 255),")
    tris = []
    for k in range(4):
        a, b = k, (k + 1) % 4
        tris.append(f"    gsSP2Triangles({a}, {b}, {b + 4}, 0, {a}, {b + 4}, {a + 4}, 0),")
    return ("Vtx gMagnetBeamVtx[] = {\n" + "\n".join(vtx) + "\n};\n\n"
            "Gfx gMagnetBeamDL[] = {\n    gsDPPipeSync(),\n    gsDPSetCycleType(G_CYC_1CYCLE),\n"
            "    gsSPClearGeometryMode(G_LIGHTING | G_FOG | G_CULL_BOTH | G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR),\n"
            "    gsSPSetGeometryMode(G_ZBUFFER),\n    gsSPTexture(0, 0, 0, G_TX_RENDERTILE, G_OFF),\n"
            "    gsDPSetCombineMode(G_CC_PRIMITIVE, G_CC_PRIMITIVE),\n"
            "    gsDPSetRenderMode(G_RM_ZB_CLD_SURF, G_RM_ZB_CLD_SURF2),\n"
            "    gsSPVertex(gMagnetBeamVtx, 8, 0),\n" + "\n".join(tris) + "\n    gsSPEndDisplayList(),\n};\n")


HEADER = """#ifndef OBJECT_REMIX_MAGNET_H
#define OBJECT_REMIX_MAGNET_H

#include "ultra64.h"
#include "bgcheck.h"

// The Lodestone Shrine's moving pieces (tools/remix/make_magnet_parts.py), drawn and moved by En_Remix_Magnet.

#define MAGNET_CRATE_SIZE {crate}
#define MAGNET_GIRDER_LENGTH {gl}
#define MAGNET_GIRDER_HEIGHT {gh}
#define MAGNET_GIRDER_WIDTH {gw}
#define MAGNET_SLAB_WIDTH {sw}
#define MAGNET_SLAB_HEIGHT {sh}
#define MAGNET_SLAB_THICKNESS {st}
#define MAGNET_LIFT_SIZE {lw}
#define MAGNET_BEAM_LENGTH 1000

{decls}
#endif
"""


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    textures = write_textures()
    pieces = build_pieces()
    (OUT / "object_remix_magnet.c").write_text(emit(pieces, textures))
    decls = "".join(f"extern Gfx gMagnet{p.name}DL[];\nextern CollisionHeader gMagnet{p.name}Col;\n" for p in pieces)
    decls += "extern Gfx gMagnetBeamDL[];\n"
    (OUT / "object_remix_magnet.h").write_text(HEADER.format(crate=CRATE, gl=GIRDER[0], gh=GIRDER[1], gw=GIRDER[2],
                                                             sw=SLAB[0], sh=SLAB[1], st=SLAB[2], lw=LIFT[0], decls=decls))
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file", str(OUT / "object_remix_magnet.c"), str(OUT / "object_remix_magnet.h")],
                       cwd=ROOT, check=True)
    print(f"Wrote {OUT.relative_to(ROOT)}: " + ", ".join(f"{p.name} {sum(len(t) for t in p.tris.values())} tris"
                                                        for p in pieces))


if __name__ == "__main__":
    main()
