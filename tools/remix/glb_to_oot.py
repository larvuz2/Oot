#!/usr/bin/env python3
"""Convert an animated (skinned) GLB character into the Web Remix custom model object.

Writes assets/objects/object_remix_model/object_remix_model.{c,h}: a low-poly,
vertex-coloured version of the character, pre-posed at sampled frames of an
"idle" and a "walk" animation. The in-game actor (ovl_En_Remix_Model) and the
"play as" costume flip through those frames, so no N64 skeleton is needed.

    python3 tools/remix/glb_to_oot.py --idle idle.glb --walk walk.glb [--name Zombie]
    python3 tools/remix/glb_to_oot.py --character assets/remix_character/character.json

Each GLB must contain the skinned mesh and (optionally) one animation, as
produced by Meshy's rigging endpoints. A GLB without animation gives one
static frame. Requires numpy, pillow and fast-simplification.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import struct
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "assets" / "objects" / "object_remix_model"

COMPONENT_DTYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
TYPE_SIZES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

# ---------------------------------------------------------------- glTF reading


class Gltf:
    def __init__(self, data: bytes):
        magic, _, length = struct.unpack_from("<4sII", data, 0)
        if magic != b"glTF":
            raise ValueError("not a GLB file")
        off = 12
        self.json = None
        self.bin = b""
        while off < length:
            clen, ctype = struct.unpack_from("<II", data, off)
            chunk = data[off + 8 : off + 8 + clen]
            if ctype == 0x4E4F534A:
                self.json = json.loads(chunk)
            elif ctype == 0x004E4942:
                self.bin = chunk
            off += 8 + clen

    def buffer_view(self, index: int) -> bytes:
        bv = self.json["bufferViews"][index]
        start = bv.get("byteOffset", 0)
        return self.bin[start : start + bv["byteLength"]]

    def accessor(self, index: int) -> np.ndarray:
        acc = self.json["accessors"][index]
        dtype = COMPONENT_DTYPES[acc["componentType"]]
        ncomp = TYPE_SIZES[acc["type"]]
        count = acc["count"]
        bv = self.json["bufferViews"][acc["bufferView"]]
        stride = bv.get("byteStride", 0)
        raw = self.buffer_view(acc["bufferView"])
        start = acc.get("byteOffset", 0)
        itemsize = np.dtype(dtype).itemsize * ncomp
        if stride and stride != itemsize:
            rows = [np.frombuffer(raw, dtype, ncomp, start + i * stride) for i in range(count)]
            arr = np.array(rows)
        else:
            arr = np.frombuffer(raw, dtype, count * ncomp, start).reshape(count, ncomp)
        if acc.get("normalized"):
            arr = arr.astype(np.float32) / np.iinfo(dtype).max
        return arr.astype(np.float32) if dtype == np.float32 else arr

    def image(self, index: int):
        from PIL import Image

        img = self.json["images"][index]
        if "bufferView" in img:
            data = self.buffer_view(img["bufferView"])
        else:
            raise ValueError("external images are not supported")
        return Image.open(io.BytesIO(data)).convert("RGBA")


# ---------------------------------------------------------------- math


def quat_to_mat(q: np.ndarray) -> np.ndarray:
    x, y, z, w = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def trs_matrix(t, r, s) -> np.ndarray:
    m = np.eye(4)
    m[:3, :3] = quat_to_mat(np.asarray(r, float)) * np.asarray(s, float)
    m[:3, 3] = t
    return m


def node_local(node: dict):
    if "matrix" in node:
        m = np.array(node["matrix"], float).reshape(4, 4).T
        return m, None
    return None, (
        np.array(node.get("translation", [0, 0, 0]), float),
        np.array(node.get("rotation", [0, 0, 0, 1]), float),
        np.array(node.get("scale", [1, 1, 1]), float),
    )


def slerp(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    d = float(np.dot(a, b))
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        q = a + t * (b - a)
    else:
        th = math.acos(d)
        q = (math.sin((1 - t) * th) * a + math.sin(t * th) * b) / math.sin(th)
    return q / np.linalg.norm(q)


def sample_channel(times: np.ndarray, values: np.ndarray, interp: str, path: str, t: float) -> np.ndarray:
    if interp == "CUBICSPLINE":
        values = values.reshape(len(times), 3, -1)[:, 1]
    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]
    i = int(np.searchsorted(times, t) - 1)
    t0, t1 = times[i], times[i + 1]
    u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
    if interp == "STEP":
        return values[i]
    if path == "rotation":
        return slerp(values[i].astype(float), values[i + 1].astype(float), u)
    return values[i] * (1 - u) + values[i + 1] * u


# ---------------------------------------------------------------- character loading


class Character:
    """The skinned mesh of a GLB plus a way to pose it at any animation time."""

    def __init__(self, gltf: Gltf):
        self.g = gltf
        j = gltf.json
        mesh_node = next(i for i, n in enumerate(j["nodes"]) if "mesh" in n)
        self.skin = j["skins"][j["nodes"][mesh_node]["skin"]] if "skin" in j["nodes"][mesh_node] else None
        self.mesh_node = mesh_node

        positions, colors, joints, weights, tris = [], [], [], [], []
        base = 0
        for prim in j["meshes"][j["nodes"][mesh_node]["mesh"]]["primitives"]:
            attr = prim["attributes"]
            pos = gltf.accessor(attr["POSITION"]).astype(float)
            n = len(pos)
            idx = gltf.accessor(prim["indices"]).reshape(-1) if "indices" in prim else np.arange(n)
            colors.append(self._prim_colors(prim, n))
            positions.append(pos)
            if self.skin is not None and "JOINTS_0" in attr:
                joints.append(gltf.accessor(attr["JOINTS_0"]).astype(int))
                w = gltf.accessor(attr["WEIGHTS_0"]).astype(float)
                weights.append(w / np.maximum(w.sum(1, keepdims=True), 1e-9))
            tris.append(idx.reshape(-1, 3).astype(int) + base)
            base += n
        self.pos = np.concatenate(positions)
        self.col = np.concatenate(colors)
        self.tris = np.concatenate(tris)
        self.joints = np.concatenate(joints) if joints else None
        self.weights = np.concatenate(weights) if weights else None
        self.parents = {}
        for i, n in enumerate(j["nodes"]):
            for c in n.get("children", []):
                self.parents[c] = i
        if self.skin is not None:
            jc = len(self.skin["joints"])
            self.ibm = (
                gltf.accessor(self.skin["inverseBindMatrices"]).reshape(jc, 4, 4).transpose(0, 2, 1)
                if "inverseBindMatrices" in self.skin
                else np.tile(np.eye(4), (jc, 1, 1))
            )
        anims = j.get("animations") or []
        self.anim = anims[0] if anims else None
        self.duration = 0.0
        self.channels = []
        if self.anim:
            for ch in self.anim["channels"]:
                smp = self.anim["samplers"][ch["sampler"]]
                times = gltf.accessor(smp["input"]).reshape(-1).astype(float)
                vals = gltf.accessor(smp["output"]).astype(float)
                self.channels.append((ch["target"].get("node"), ch["target"]["path"], times, vals, smp.get("interpolation", "LINEAR")))
                self.duration = max(self.duration, float(times[-1]))

    def _prim_colors(self, prim: dict, n: int) -> np.ndarray:
        g = self.g
        attr = prim["attributes"]
        factor = np.array([1.0, 1.0, 1.0, 1.0])
        tex = None
        if "material" in prim:
            pbr = g.json["materials"][prim["material"]].get("pbrMetallicRoughness", {})
            factor = np.array(pbr.get("baseColorFactor", [1, 1, 1, 1]), float)
            if "baseColorTexture" in pbr and "TEXCOORD_0" in attr:
                tex = g.json["textures"][pbr["baseColorTexture"]["index"]]
        if "COLOR_0" in attr:
            c = g.accessor(attr["COLOR_0"]).astype(float)
            if c.max() > 1.0:
                c = c / 255.0
            if c.shape[1] == 3:
                c = np.concatenate([c, np.ones((n, 1))], 1)
            return c * factor
        if tex is None:
            return np.tile(factor, (n, 1))
        img = np.asarray(g.image(tex["source"]).resize((256, 256)), float) / 255.0
        uv = g.accessor(attr["TEXCOORD_0"]).astype(float)
        # Average a small neighbourhood so single texels (seams, specks) don't dominate.
        out = np.zeros((n, 4))
        for du, dv in ((0, 0), (2, 0), (-2, 0), (0, 2), (0, -2)):
            x = np.clip(((uv[:, 0] % 1.0) * 255).astype(int) + du, 0, 255)
            y = np.clip(((uv[:, 1] % 1.0) * 255).astype(int) + dv, 0, 255)
            out += img[y, x]
        return out / 5 * factor

    def global_mats(self, t: float | None) -> dict[int, np.ndarray]:
        j = self.g.json
        local = {}
        overrides: dict[int, dict] = {}
        if t is not None:
            for node, path, times, vals, interp in self.channels:
                if node is not None:
                    overrides.setdefault(node, {})[path] = sample_channel(times, vals, interp, path, t)
        for i, n in enumerate(j["nodes"]):
            m, trs = node_local(n)
            if trs is not None:
                tr, ro, sc = trs
                o = overrides.get(i, {})
                m = trs_matrix(o.get("translation", tr), o.get("rotation", ro), o.get("scale", sc))
            local[i] = m
        glob: dict[int, np.ndarray] = {}

        def get(i):
            if i not in glob:
                glob[i] = get(self.parents[i]) @ local[i] if i in self.parents else local[i]
            return glob[i]

        for i in range(len(j["nodes"])):
            get(i)
        return glob

    def pose(self, t: float | None) -> np.ndarray:
        """World-space vertex positions at animation time t (None = bind pose)."""
        glob = self.global_mats(t)
        if self.skin is None or self.joints is None:
            m = glob[self.mesh_node]
            return self.pos @ m[:3, :3].T + m[:3, 3]
        mats = np.array([glob[jn] @ self.ibm[k] for k, jn in enumerate(self.skin["joints"])])
        hom = np.concatenate([self.pos, np.ones((len(self.pos), 1))], 1)
        out = np.zeros((len(self.pos), 3))
        for k in range(4):
            m = mats[self.joints[:, k]]
            out += self.weights[:, k : k + 1] * np.einsum("nij,nj->ni", m, hom)[:, :3]
        return out

    def root_joint_xz(self, t: float | None) -> np.ndarray:
        if self.skin is None:
            return np.zeros(2)
        names = [(self.g.json["nodes"][jn].get("name") or "").lower() for jn in self.skin["joints"]]
        k = next((i for i, nm in enumerate(names) if "hip" in nm or "pelvis" in nm), 0)
        m = self.global_mats(t)[self.skin["joints"][k]]
        return m[[0, 2], 3]


# ---------------------------------------------------------------- mesh reduction


def weld(ch: Character):
    """Merge vertices that share a position (UV seams) so decimation keeps the surface closed."""
    key = np.round(ch.pos / (np.ptp(ch.pos, 0).max() * 1e-5 + 1e-12)).astype(np.int64)
    _, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.reshape(-1)
    col = np.zeros((len(first), 4))
    np.add.at(col, inverse, ch.col)
    col /= np.bincount(inverse, minlength=len(first))[:, None]
    tris = inverse[ch.tris]
    tris = tris[(tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])]
    return first, col, tris


def decimate(ch: Character, target_tris: int):
    import fast_simplification

    first, col, tris = weld(ch)
    pts = ch.pos[first]
    if len(tris) > target_tris:
        pts2, tris2 = fast_simplification.simplify(pts.astype(np.float32), tris.astype(np.int32), 1 - target_tris / len(tris))
    else:
        pts2, tris2 = pts, tris
    # Every reduced vertex borrows skinning + colour from its nearest original (welded) vertex.
    nearest = np.empty(len(pts2), int)
    for s in range(0, len(pts2), 256):
        d = ((pts2[s : s + 256, None, :] - pts[None, :, :]) ** 2).sum(-1)
        nearest[s : s + 256] = d.argmin(1)
    src = first[nearest]  # index into the original vertex arrays
    return src, col[nearest], np.asarray(tris2, int)


# ---------------------------------------------------------------- N64 output


def shade(verts: np.ndarray, tris: np.ndarray, col: np.ndarray) -> np.ndarray:
    """Bake simple directional light into vertex colours (the model is drawn unlit)."""
    fn = np.cross(verts[tris[:, 1]] - verts[tris[:, 0]], verts[tris[:, 2]] - verts[tris[:, 0]])
    vn = np.zeros_like(verts)
    for k in range(3):
        np.add.at(vn, tris[:, k], fn)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)
    light = np.array([0.35, 0.8, 0.5])
    light /= np.linalg.norm(light)
    lam = np.clip(vn @ light, 0, 1)
    return np.clip(col[:, :3] * (0.7 + 0.5 * lam[:, None]) * 1.1, 0, 1)


def batches(tris: np.ndarray, cache: int = 32):
    """Split triangles into groups that each use at most `cache` distinct vertices."""
    out = []
    cur_map: dict[int, int] = {}
    cur_tris: list[tuple[int, int, int]] = []
    for t in tris:
        new = [v for v in dict.fromkeys(t.tolist()) if v not in cur_map]
        if len(cur_map) + len(new) > cache:
            out.append((list(cur_map), cur_tris))
            cur_map, cur_tris = {}, []
            new = list(dict.fromkeys(t.tolist()))
        for v in new:
            cur_map[v] = len(cur_map)
        cur_tris.append(tuple(cur_map[v] for v in t.tolist()))
    if cur_tris:
        out.append((list(cur_map), cur_tris))
    return out


def c_ident(s: str) -> str:
    return "".join(ch for ch in s if ch.isalnum() or ch == " ")[:18].strip() or "Custom"


SOURCE_MARK = "// source-sha256: "


def source_hash(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_source_hash() -> str | None:
    """The character.json hash recorded in the generated object, if any."""
    c = OUT_DIR / "object_remix_model.c"
    if c.exists():
        for line in c.read_text().splitlines()[:5]:
            if line.startswith(SOURCE_MARK):
                return line[len(SOURCE_MARK) :].strip()
    return None


def write_object(
    frames: list[tuple[np.ndarray, np.ndarray]], tris: np.ndarray, n_idle: int, n_walk: int, name: str, height: int, source: str
) -> None:
    groups = batches(tris)
    lines = [
        "// Generated by tools/remix/glb_to_oot.py from a Character Studio model - do not edit by hand.",
        f'// Character: "{c_ident(name)}"  frames: {n_idle} idle + {n_walk} walk  triangles: {len(tris)}',
        SOURCE_MARK + source,
        "",
        '#include "object_remix_model.h"',
        '#include "gfx.h"',
        "",
    ]
    for fi, (verts, colors) in enumerate(frames):
        lines.append(f"Vtx gRemixModelFrame{fi}Vtx[] = {{")
        for vids, _ in groups:
            for v in vids:
                x, y, z = (int(round(c)) for c in verts[v])
                r, g, b = (int(round(c * 255)) for c in colors[v])
                lines.append(f"    VTX({x}, {y}, {z}, 0, 0, {r}, {g}, {b}, 255),")
        lines.append("};")
        lines.append("")
        lines.append(f"Gfx gRemixModelFrame{fi}DL[] = {{")
        lines += [
            "    gsDPPipeSync(),",
            "    gsDPSetCycleType(G_CYC_1CYCLE),",
            "    gsSPTexture(0, 0, 0, G_TX_RENDERTILE, G_OFF),",
            "    gsSPClearGeometryMode(G_LIGHTING | G_FOG | G_CULL_BOTH | G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR),",
            "    gsSPSetGeometryMode(G_SHADE | G_SHADING_SMOOTH | G_ZBUFFER | G_CULL_BACK),",
            "    gsDPSetCombineMode(G_CC_SHADE, G_CC_SHADE),",
            "    gsDPSetRenderMode(G_RM_AA_ZB_OPA_SURF, G_RM_AA_ZB_OPA_SURF2),",
        ]
        base = 0
        for vids, gtris in groups:
            lines.append(f"    gsSPVertex(&gRemixModelFrame{fi}Vtx[{base}], {len(vids)}, 0),")
            for k in range(0, len(gtris) - 1, 2):
                a, b2 = gtris[k], gtris[k + 1]
                lines.append(f"    gsSP2Triangles({a[0]}, {a[1]}, {a[2]}, 0, {b2[0]}, {b2[1]}, {b2[2]}, 0),")
            if len(gtris) % 2:
                a = gtris[-1]
                lines.append(f"    gsSP1Triangle({a[0]}, {a[1]}, {a[2]}, 0),")
            base += len(vids)
        lines += ["    gsSPEndDisplayList(),", "};", ""]
    lines.append("Gfx* gRemixModelFrameDLs[] = {")
    lines += [f"    gRemixModelFrame{fi}DL," for fi in range(len(frames))]
    lines += ["};", ""]
    lines.append(f"s16 gRemixModelInfo[REMIX_MODEL_INFO_MAX] = {{ {n_idle}, {n_walk}, {height}, 0 }};")
    lines.append("")
    (OUT_DIR / "object_remix_model.c").write_text("\n".join(lines))
    write_header()


def write_header() -> None:
    (OUT_DIR / "object_remix_model.h").write_text(
        """#ifndef OBJECT_REMIX_MODEL_H
#define OBJECT_REMIX_MODEL_H

#include "ultra64.h"

// The custom 3D model used by ovl_En_Remix_Model and the "play as" costume.
// Either the hand-made crystal or a Character Studio model converted by
// tools/remix/glb_to_oot.py: one display list per animation frame, idle frames first.

typedef enum RemixModelInfo {
    REMIX_MODEL_INFO_IDLE_FRAMES, // frames of the idle animation (at least 1)
    REMIX_MODEL_INFO_WALK_FRAMES, // frames of the walk cycle that follow the idle frames (0 = a static prop)
    REMIX_MODEL_INFO_HEIGHT,      // model height in model units (drawn at scale 0.01)
    REMIX_MODEL_INFO_RESERVED,
    REMIX_MODEL_INFO_MAX
} RemixModelInfo;

extern Gfx* gRemixModelFrameDLs[];
extern s16 gRemixModelInfo[REMIX_MODEL_INFO_MAX];

#endif
"""
    )


def format_output() -> None:
    """Match the repo's clang-format style (tools/check_format.py checks assets/ too)."""
    import shutil
    import subprocess

    exe = shutil.which("clang-format-14") or shutil.which("clang-format")
    if exe is None:
        print("warning: clang-format-14 not found; run ./format.py on assets/objects/object_remix_model", file=sys.stderr)
        return
    files = [str(OUT_DIR / "object_remix_model.c"), str(OUT_DIR / "object_remix_model.h")]
    subprocess.run([exe, "-i", "--style=file"] + files, check=True, cwd=ROOT)


# ---------------------------------------------------------------- main


def fetch(src: str, tmp: Path) -> bytes:
    if src.startswith("http://") or src.startswith("https://"):
        dst = tmp / (str(abs(hash(src))) + ".glb")
        urllib.request.urlretrieve(src, dst)
        return dst.read_bytes()
    return Path(src).read_bytes()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--character", help="character.json written by the Character Studio")
    ap.add_argument("--idle", help="GLB (path or URL) with the idle animation")
    ap.add_argument("--walk", help="GLB (path or URL) with the walk animation")
    ap.add_argument("--name", default="Custom")
    ap.add_argument("--triangles", type=int, default=450)
    ap.add_argument("--idle-frames", type=int, default=3)
    ap.add_argument("--walk-frames", type=int, default=8)
    ap.add_argument("--height", type=float, default=50.0, help="height in game units (adult Link is about 50)")
    ap.add_argument("--if-changed", action="store_true", help="skip if the object was already made from this character.json")
    args = ap.parse_args()

    source = "manual"
    if args.character:
        source = source_hash(Path(args.character))
        if args.if_changed and current_source_hash() == source:
            print("Custom model is already up to date with", args.character)
            return
        spec = json.loads(Path(args.character).read_text())
        args.idle = spec.get("idleGlb") or spec.get("riggedGlb")
        args.walk = spec.get("walkGlb")
        args.name = spec.get("name", args.name)
    if not args.idle:
        sys.exit("error: need --idle (or --character)")

    with tempfile.TemporaryDirectory() as tmp:
        idle = Character(Gltf(fetch(args.idle, Path(tmp))))
        walk = Character(Gltf(fetch(args.walk, Path(tmp)))) if args.walk else None

    src, col, tris = decimate(idle, args.triangles)

    def frames_of(ch: Character, n: int) -> list[np.ndarray]:
        if ch.anim is None or ch.duration <= 0:
            return [ch.pose(None)[src]]
        out = []
        for k in range(n):
            t = ch.duration * k / n
            p = ch.pose(t)
            p[:, [0, 2]] -= ch.root_joint_xz(t)  # keep the character in place (no root motion)
            out.append(p[src])
        return out

    idle_frames = frames_of(idle, args.idle_frames)
    walk_frames = frames_of(walk, args.walk_frames) if walk is not None else []
    if walk is not None and len(walk.pos) != len(idle.pos):
        sys.exit("error: idle and walk GLBs have different meshes")

    # Normalise: feet on y=0, centred, scaled to the requested height (model units = game units * 100).
    allp = np.concatenate(idle_frames + walk_frames)
    ref = idle_frames[0]
    scale = args.height * 100.0 / max(float(np.ptp(ref[:, 1])), 1e-6)
    offset = np.array([-(ref[:, 0].max() + ref[:, 0].min()) / 2, -allp[:, 1].min(), -(ref[:, 2].max() + ref[:, 2].min()) / 2])
    frames = []
    for p in idle_frames + walk_frames:
        v = (p + offset) * scale
        if np.abs(v).max() > 32000:
            sys.exit("error: model too large for N64 vertex coordinates")
        frames.append((v, shade(v, tris, col)))

    write_object(frames, tris, len(idle_frames), len(walk_frames), args.name, int(round(args.height * 100)), source)
    format_output()
    print(f"Wrote {OUT_DIR.relative_to(ROOT)}: {len(tris)} triangles, {len(idle_frames)} idle + {len(walk_frames)} walk frames")


if __name__ == "__main__":
    main()
