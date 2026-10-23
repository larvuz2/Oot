#!/usr/bin/env python3
"""Convert the fal-made Magnesis Rune (a slate with a magnet on its face) into a small "get item" object.

Writes assets/objects/object_remix_slate/: a low-poly copy of the model with its face baked into one small texture
(the model is a slab, so a straight front-on projection covers it: the sides just stretch the border's colours).
Link holds it up when he opens the Magnesis chest (GI_REMIX_MAGNESIS, drawn by GID_REMIX_MAGNESIS in z_draw.c).
The player loads get-item objects into an 8 KB buffer, so this must stay well under that.

How the model was made (fal, see web/js/studio-pipeline.js for the same endpoints):
  1. openai/gpt-image-2.5/flare/text-to-image: "a small handheld ancient stone tablet ... dark slate-grey stone with
     glowing orange Sheikah engravings ... a large glowing magenta horseshoe magnet symbol", white background
  2. meshy/v7.1/image-to-3d on that image (target_polycount 1500, textured)

    python3 tools/remix/make_slate.py model.glb [--triangles 180] [--preview out.png]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from glb_to_oot import Character, Gltf, batches, shade  # noqa: E402

ROOT = HERE.parents[1]
OUT_DIR = ROOT / "assets" / "objects" / "object_remix_slate"
TEX_W, TEX_H = 32, 48
HEIGHT = 110.0  # model units (get-item models are drawn at scale 0.2: about 22 units in Link's hands)


def bake_front(ch: Character, gltf: Gltf, w: int, h: int, front: int) -> np.ndarray:
    """Orthographic render of the textured model seen from +z (front=1) or -z (front=-1): an h x w x 3 image."""
    j = gltf.json
    prim = j["meshes"][0]["primitives"][0]
    uv = gltf.accessor(prim["attributes"]["TEXCOORD_0"]).astype(float)
    tex_index = j["materials"][prim["material"]]["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    img = np.asarray(gltf.image(j["textures"][tex_index]["source"]).convert("RGB"), float) / 255.0
    th, tw = img.shape[:2]
    p = ch.pose(None)
    lo, hi = p.min(0), p.max(0)
    sx = (p[:, 0] - lo[0]) / (hi[0] - lo[0]) * w
    if front < 0:
        sx = w - sx
    sy = (hi[1] - p[:, 1]) / (hi[1] - lo[1]) * h
    depth = p[:, 2] * front
    out = np.zeros((h, w, 3))
    zbuf = np.full((h, w), -1e9)
    for t in ch.tris:
        x, y, z = sx[t], sy[t], depth[t]
        x0, x1 = int(max(0, np.floor(x.min()))), int(min(w - 1, np.ceil(x.max())))
        y0, y1 = int(max(0, np.floor(y.min()))), int(min(h - 1, np.ceil(y.max())))
        den = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(den) < 1e-9 or x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / den
        b = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / den
        c = 1 - a - b
        inside = (a >= -1e-4) & (b >= -1e-4) & (c >= -1e-4)
        zz = a * z[0] + b * z[1] + c * z[2]
        sub = zbuf[y0 : y1 + 1, x0 : x1 + 1]
        win = inside & (zz > sub)
        if not win.any():
            continue
        u = a * uv[t[0], 0] + b * uv[t[1], 0] + c * uv[t[2], 0]
        v = a * uv[t[0], 1] + b * uv[t[1], 1] + c * uv[t[2], 1]
        px = np.clip(((u % 1.0) * tw).astype(int), 0, tw - 1)
        py = np.clip(((v % 1.0) * th).astype(int), 0, th - 1)
        sub[win] = zz[win]
        out[y0 : y1 + 1, x0 : x1 + 1][win] = img[py[win], px[win]]
    # fill the background (corners outside the rounded slab) with the nearest border colour
    empty = zbuf < -1e8
    if empty.any() and (~empty).any():
        ys, xs = np.nonzero(~empty)
        for yy, xx in zip(*np.nonzero(empty)):
            k = np.argmin((ys - yy) ** 2 + (xs - xx) ** 2)
            out[yy, xx] = out[ys[k], xs[k]]
    return out


def downsample(img: np.ndarray, w: int, h: int) -> np.ndarray:
    fy, fx = img.shape[0] // h, img.shape[1] // w
    return img[: h * fy, : w * fx].reshape(h, fy, w, fx, 3).mean((1, 3))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("glb")
    ap.add_argument("--triangles", type=int, default=180)
    ap.add_argument("--preview", help="also save the baked face (scaled up) here")
    args = ap.parse_args()

    import fast_simplification
    from PIL import Image

    gltf = Gltf(Path(args.glb).read_bytes())
    ch = Character(gltf)

    # the face with the most magenta is the front
    faces = [bake_front(ch, gltf, TEX_W * 8, TEX_H * 8, f) for f in (1, -1)]
    pink = [float(((f[..., 0] > 0.7) & (f[..., 2] > 0.4) & (f[..., 1] < 0.45)).sum()) for f in faces]
    front = 1 if pink[0] >= pink[1] else -1
    tex = downsample(faces[0 if front > 0 else 1], TEX_W, TEX_H)
    # punch up the glow a little: N64 filtering and the dark slate otherwise mute it
    tex = np.clip((tex - 0.5) * 1.15 + 0.5 + 0.03, 0, 1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Image.fromarray((tex * 255).round().astype(np.uint8)).save(OUT_DIR / "remix_slate.rgba16.png")
    if args.preview:
        Image.fromarray((tex * 255).round().astype(np.uint8)).resize((TEX_W * 8, TEX_H * 8), Image.NEAREST).save(args.preview)

    # simplify (weld UV seams first so the slab stays closed)
    p = ch.pose(None)
    key = np.round(p / (np.ptp(p, 0).max() * 1e-5)).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    tris = inv.reshape(-1)[ch.tris]
    tris = tris[(tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])]
    pts = p[first].astype(np.float32)
    pts2, tris2 = fast_simplification.simplify(pts, tris.astype(np.int32), max(0.0, 1 - args.triangles / len(tris)))
    pts2, tris2 = np.asarray(pts2, float), np.asarray(tris2, int)
    if front < 0:  # turn the model so its face looks down +z (towards the camera when Link holds it up)
        pts2[:, [0, 2]] *= -1

    lo, hi = pts2.min(0), pts2.max(0)
    scale = HEIGHT / (hi[1] - lo[1])
    verts = (pts2 - [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2]) * scale
    vlo, vhi = verts.min(0), verts.max(0)
    s = (verts[:, 0] - vlo[0]) / (vhi[0] - vlo[0]) * TEX_W
    t = (vhi[1] - verts[:, 1]) / (vhi[1] - vlo[1]) * TEX_H
    s = np.clip(s, 0.5, TEX_W - 0.5)
    t = np.clip(t, 0.5, TEX_H - 0.5)
    light = shade(verts, tris2, np.ones((len(verts), 4)))

    groups = batches(tris2)
    lines = [
        "// Generated by tools/remix/make_slate.py from the fal-made Magnesis Rune model - do not edit by hand.",
        "",
        '#include "object_remix_slate.h"',
        '#include "gfx.h"',
        "",
        "u64 gRemixSlateTex[] = {",
        '#include "assets/objects/object_remix_slate/remix_slate.rgba16.inc.c"',
        "};",
        "",
        "Vtx gRemixSlateVtx[] = {",
    ]
    for vids, _ in groups:
        for v in vids:
            x, y, z = (int(round(c)) for c in verts[v])
            r = g = b = int(round(min(1.0, light[v, 0]) * 255))
            lines.append(f"    VTX({x}, {y}, {z}, {int(round(s[v] * 32))}, {int(round(t[v] * 32))}, {r}, {g}, {b}, 255),")
    lines += [
        "};",
        "",
        "Gfx gRemixSlateDL[] = {",
        "    gsDPPipeSync(),",
        "    gsDPSetCycleType(G_CYC_1CYCLE),",
        "    gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON),",
        "    gsSPClearGeometryMode(G_LIGHTING | G_FOG | G_CULL_BOTH | G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR),",
        "    gsSPSetGeometryMode(G_SHADE | G_SHADING_SMOOTH | G_ZBUFFER | G_CULL_BACK),",
        "    gsDPSetTextureLUT(G_TT_NONE),",
        f"    gsDPLoadTextureBlock(gRemixSlateTex, G_IM_FMT_RGBA, G_IM_SIZ_16b, {TEX_W}, {TEX_H}, 0, G_TX_NOMIRROR | G_TX_CLAMP,",
        "                         G_TX_NOMIRROR | G_TX_CLAMP, G_TX_NOMASK, G_TX_NOMASK, G_TX_NOLOD, G_TX_NOLOD),",
        "    gsDPSetCombineMode(G_CC_MODULATEIDECALA, G_CC_MODULATEIDECALA),",
        "    gsDPSetRenderMode(G_RM_AA_ZB_OPA_SURF, G_RM_AA_ZB_OPA_SURF2),",
    ]
    base = 0
    for vids, gtris in groups:
        lines.append(f"    gsSPVertex(&gRemixSlateVtx[{base}], {len(vids)}, 0),")
        for k in range(0, len(gtris) - 1, 2):
            a, b2 = gtris[k], gtris[k + 1]
            lines.append(f"    gsSP2Triangles({a[0]}, {a[1]}, {a[2]}, 0, {b2[0]}, {b2[1]}, {b2[2]}, 0),")
        if len(gtris) % 2:
            a = gtris[-1]
            lines.append(f"    gsSP1Triangle({a[0]}, {a[1]}, {a[2]}, 0),")
        base += len(vids)
    lines += ["    gsSPEndDisplayList(),", "};", ""]
    (OUT_DIR / "object_remix_slate.c").write_text("\n".join(lines))
    (OUT_DIR / "object_remix_slate.h").write_text(
        """#ifndef OBJECT_REMIX_SLATE_H
#define OBJECT_REMIX_SLATE_H

#include "ultra64.h"

// The Magnesis Rune (tools/remix/make_slate.py): the item Link holds up when he finds Magnesis.

extern u64 gRemixSlateTex[];
extern Vtx gRemixSlateVtx[];
extern Gfx gRemixSlateDL[];

#endif
"""
    )
    import shutil
    import subprocess

    exe = shutil.which("clang-format-14") or shutil.which("clang-format")
    if exe:
        subprocess.run([exe, "-i", "--style=file", str(OUT_DIR / "object_remix_slate.c"), str(OUT_DIR / "object_remix_slate.h")],
                       check=True, cwd=ROOT)
    else:
        print("warning: clang-format-14 not found; run ./format.py on assets/objects/object_remix_slate", file=sys.stderr)
    size = TEX_W * TEX_H * 2 + base * 16 + sum(1 for ln in lines if ln.startswith("    gs")) * 8 + 16
    print(f"Wrote {OUT_DIR.relative_to(ROOT)}: {len(tris2)} triangles, {base} vertices, about {size} bytes (front {front:+d})")


if __name__ == "__main__":
    main()
