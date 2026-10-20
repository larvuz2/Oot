#!/usr/bin/env python3
"""Let the Ancient Plateau reuse Hyrule Field's own assets.

Run after `make setup`. Reads the extracted Hyrule Field (extracted/VERSION/assets/scenes/overworld/spot00),
finds the textures the field uses for its grass, dirt paths and cliffs (by replaying its display lists and
measuring how much floor and how much wall each texture covers), and its light settings (time of day, fog).
Converts each chosen texture to the level's format (RGBA16 32x32; textures the field tints with vertex colors
get that tint baked in) next to the header, and writes build/VERSION/assets/scenes/remix/ancient/ancient_hf.h,
which the level's sources include:

    #define ANCIENT_HF_GRASS  "assets/scenes/remix/ancient/hf_grass.rgba16.inc.c"
    #define ANCIENT_HF_DIRT   ...
    #define ANCIENT_HF_ROCK   ...
    #define ANCIENT_HF_LIGHTS "assets/scenes/overworld/spot00/<lights>.inc.c"

Without that file (no ROM), assets/scenes/remix/ancient/ancient_hf.h is used instead and the level falls back
to its own look-alike textures and lights. Nothing from the ROM is ever committed: the data is pulled in at
build time, like the rest of the game's assets.

    python3 tools/remix/link_level_assets.py --version ntsc-1.2
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
SRC = "assets/scenes/overworld/spot00"
OUT_REL = "assets/scenes/remix/ancient/ancient_hf.h"

VTX_RE = re.compile(r"VTX\(\s*(-?\w+),\s*(-?\w+),\s*(-?\w+),\s*-?\w+,\s*-?\w+,\s*(\w+),\s*(\w+),\s*(\w+),")
GEO_RE = re.compile(r"gsSP(Set|Clear|Load)GeometryMode\(([^)]*)\)")
TEXLOAD_RE = re.compile(r"gsDPLoadTextureBlock(?:_4b)?\(\s*(\w+)\s*,")
MULTI_RE = re.compile(r"gsDPLoadMultiBlock(?:_4b)?\(\s*(\w+)\s*,\s*\w+\s*,\s*(\w+)\s*,")
SETTIMG_RE = re.compile(r"gsDPSetTextureImage\([^,]+,[^,]+,[^,]+,\s*(\w+)\s*\)")
VERTEX_RE = re.compile(r"gsSPVertex\(\s*&?(\w+)(?:\[(\d+)\])?\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
TRI1_RE = re.compile(r"gsSP1Triangle\(\s*(\d+),\s*(\d+),\s*(\d+)")
TRI2_RE = re.compile(r"gsSP2Triangles\(\s*(\d+),\s*(\d+),\s*(\d+),\s*\d+,\s*(\d+),\s*(\d+),\s*(\d+)")
LIGHTS_CMD_RE = re.compile(r"SCENE_CMD_ENV_LIGHT_SETTINGS\(\s*(\w+)\s*,\s*(\w+)\s*\)")


GEO2_RE = re.compile(r"gsSPGeometryMode\(([^,]*),([^)]*)\)")
# `TYPE SYMBOL[...] = {\n#include "assets/.../file.inc.c"\n};`: how the extractor writes every resource. The file
# names do not always match the symbols, so everything is looked up through these definitions.
DEF_RE = re.compile(r'^(?:static\s+)?([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*(?:\[[^\]\n]*\]\s*)*=\s*\{?\s*\n\s*#include\s+"([^"]+)"',
                    re.M)
TEX_SIZE = (32, 32)  # the level's grass, dirt and rock materials (tools/remix/make_level.py)


def num(s):
    return int(s, 0)


class Field:
    """The extracted scene: symbol -> (C type, included file), and the text of the included files."""

    def __init__(self, ext: Path, src: Path):
        self.ext, self.src = ext, src
        self.defs = {}
        for c in sorted(src.glob("*.c")):
            if c.name.endswith(".inc.c"):
                continue
            for ctype, sym, inc in DEF_RE.findall(c.read_text()):
                self.defs[sym] = (ctype, inc)
        self._texts = {}

    def path(self, inc: str) -> Path:
        for base in (self.ext, self.src, REPO):
            if (base / inc).is_file():
                return base / inc
        return self.ext / inc

    def text(self, sym: str) -> str:
        if sym not in self._texts:
            p = self.path(self.defs[sym][1]) if sym in self.defs else None
            self._texts[sym] = p.read_text() if p is not None and p.is_file() else ""
        return self._texts[sym]

    def of_type(self, ctype: str):
        return [s for s, (t, _) in self.defs.items() if t == ctype]

    def png(self, sym: str):
        """The PNG a texture symbol is built from, or None."""
        if sym not in self.defs or not self.defs[sym][1].endswith(".inc.c"):
            return None
        p = self.path(self.defs[sym][1][: -len(".inc.c")] + ".png")
        return p if p.is_file() else None


def load_vertex_arrays(field: Field):
    """symbol -> (Nx3 positions, Nx3 colors) of every Vtx array."""
    arrays = {}
    for sym in field.of_type("Vtx"):
        rows = [[num(v) for v in m] for m in VTX_RE.findall(field.text(sym))]
        if rows:
            rows = np.array(rows, float)
            arrays[sym] = (rows[:, :3], rows[:, 3:])
    return arrays


def lighting_after(line, lit):
    m = GEO_RE.search(line)
    if m:
        has = "G_LIGHTING" in m.group(2)
        return {"Set": lit or has, "Clear": lit and not has, "Load": has}[m.group(1)]
    m = GEO2_RE.search(line)
    if m:
        return (lit and "G_LIGHTING" not in m.group(1)) or "G_LIGHTING" in m.group(2)
    return lit


def texture_usage(field: Field, arrays):
    """Replay display lists. texture symbol -> dict(count, floor area, wall area, summed vertex color, color
    weight); the color only counts where lighting is off (with lighting on, vertex colors are normals)."""
    usage = {}
    for sym in field.of_type("Gfx"):
        text = field.text(sym)
        cur = None
        lit = False
        slots = [None] * 64
        for line in text.splitlines():
            lit = lighting_after(line, lit)
            m = TEXLOAD_RE.search(line)
            if m:
                cur = m.group(1)
                continue
            m = MULTI_RE.search(line)
            if m:
                if m.group(2) in ("G_TX_RENDERTILE", "0"):
                    cur = m.group(1)
                continue
            m = SETTIMG_RE.search(line)
            if m and "G_IM_FMT" in line and "TLUT" not in m.group(1):
                cur = m.group(1)
                continue
            m = VERTEX_RE.search(line)
            if m:
                arr = arrays.get(m.group(1))
                start = int(m.group(2) or 0)
                n, v0 = int(m.group(3)), int(m.group(4))
                for k in range(n):
                    ok = arr is not None and start + k < len(arr[0]) and v0 + k < len(slots)
                    if v0 + k < len(slots):
                        slots[v0 + k] = (arr[0][start + k], arr[1][start + k]) if ok else None
                continue
            tris = []
            m = TRI2_RE.search(line)
            if m:
                g = [int(x) for x in m.groups()]
                tris = [g[:3], g[3:]]
            else:
                m = TRI1_RE.search(line)
                if m:
                    tris = [[int(x) for x in m.groups()]]
            for t in tris:
                if cur is None or any(i >= len(slots) or slots[i] is None for i in t):
                    continue
                pa, pb, pc = (slots[i][0] for i in t)
                n = np.cross(pb - pa, pc - pa)
                area = np.linalg.norm(n) / 2
                if area < 1:
                    continue
                ny = n[1] / (2 * area)
                u = usage.setdefault(cur, dict(count=0, floor=0.0, wall=0.0, color=np.zeros(3), weight=0.0))
                u["count"] += 1
                if ny > 0.75:
                    u["floor"] += area
                elif abs(ny) < 0.55:
                    u["wall"] += area
                if not lit:
                    u["color"] += sum(slots[i][1] for i in t) / 3 * area
                    u["weight"] += area
    return usage


def texture_image(field: Field, sym: str):
    """(format, RGBA image) of a texture symbol (CI textures come with their palette), or None."""
    p = field.png(sym)
    if p is None:
        return None
    return p.name.split(".")[1], Image.open(p).convert("RGBA")


def to_level_texture(fmt, img, tint):
    """RGBA uint8 array of TEX_SIZE: grey formats are tinted the way the field's vertex colors tint them."""
    if img.size != TEX_SIZE:
        resample = Image.NEAREST if img.size[0] <= TEX_SIZE[0] and img.size[1] <= TEX_SIZE[1] else Image.LANCZOS
        img = img.resize(TEX_SIZE, resample)
    a = np.array(img).astype(float)
    if fmt.startswith(("i4", "i8", "ia")) and tint is not None:
        a[..., :3] = a[..., :3] * (tint / 255.0)
    return np.clip(np.round(a), 0, 255).astype(np.uint8)


def rgba16_inc(a):
    """The build's .inc.c text for an RGBA16 texture: big-endian 5551 texels, four per u64."""
    q = np.round(a[..., :3].astype(float) * 31 / 255).astype(np.uint64)
    t = (q[..., 0] << 11) | (q[..., 1] << 6) | (q[..., 2] << 1) | (a[..., 3] >= 128).astype(np.uint64)
    t = t.reshape(-1)
    words = [(int(t[i]) << 48) | (int(t[i + 1]) << 32) | (int(t[i + 2]) << 16) | int(t[i + 3]) for i in range(0, len(t), 4)]
    return "".join(f"0x{w:016X}," + ("\n" if k % 4 == 3 else " ") for k, w in enumerate(words))


def candidates(field: Field, usage):
    out = []
    for sym, u in usage.items():
        got = texture_image(field, sym)
        if got is None:
            continue
        fmt, img = got
        alpha = np.array(img)[..., 3]
        if (alpha >= 128).mean() < 0.98:  # cut-out textures (fences, leaves) cannot cover the ground
            continue
        tint = u["color"] / u["weight"] if u["weight"] > 0 else None
        tex = to_level_texture(fmt, img, tint)
        r, g, b = tex[..., :3].reshape(-1, 3).mean(0)
        out.append(dict(sym=sym, fmt=fmt, size=img.size, tex=tex, rgb=(r, g, b), floor=u["floor"], wall=u["wall"],
                        green=g > r * 1.02 and g > b * 1.15, brown=r >= g * 0.97 and g > b * 1.08))
    return out


def pick(cands):
    """Grass: the green texture covering the most floor. Dirt: the brown one covering the most floor. Rock: the
    texture covering the most wall."""
    out = {}
    grass = [c for c in cands if c["green"] and c["floor"] > 0]
    if grass:
        out["GRASS"] = max(grass, key=lambda c: c["floor"])
    dirt = [c for c in cands if c["brown"] and c["floor"] > 0 and c is not out.get("GRASS")]
    if dirt:
        out["DIRT"] = max(dirt, key=lambda c: c["floor"])
    rock = [c for c in cands if c["wall"] > 0 and not any(c is v for v in out.values())]
    if rock:
        out["ROCK"] = max(rock, key=lambda c: c["wall"])
    return out


def find_lights(field: Field):
    """(symbol, include path, entries) of the light settings of the scene's main header: the commands list with
    the alternate headers (the others are for cutscenes), else the first one found."""
    best = None
    for cmds in field.of_type("SceneCmd"):
        text = field.text(cmds)
        for m in LIGHTS_CMD_RE.finditer(text):
            sym = m.group(2)
            if sym not in field.defs:
                continue
            score = ("SCENE_CMD_ALTERNATE_HEADER_LIST" in text, "ROOM_LIST" in text)
            if best is None or score > best[0]:
                best = (score, sym)
    if best is None:
        return None
    sym = best[1]
    return sym, field.defs[sym][1], field.text(sym).count("BLEND_RATE_AND_FOG_NEAR(")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="ntsc-1.2")
    ap.add_argument("--extracted", type=Path)
    ap.add_argument("--out", type=Path, help="header to write (default build/VERSION/" + OUT_REL + ")")
    args = ap.parse_args()
    ext = args.extracted or REPO / "extracted" / args.version
    out = args.out or REPO / "build" / args.version / OUT_REL
    src = ext / SRC
    if not (src / "spot00_scene.c").is_file():
        print(f"link_level_assets: {src} not found (run `make setup` first); the level keeps its own textures")
        sys.exit(1)

    field = Field(ext, src)
    usage = texture_usage(field, load_vertex_arrays(field))
    print(f"link_level_assets: {len(field.defs)} definitions, {len(field.of_type('Gfx'))} display lists, "
          f"{len(usage)} textures drawn on triangles")
    chosen = pick(candidates(field, usage))
    if not usage:  # show what the display lists look like, to fix the parser
        for sym in field.of_type("Gfx")[:3]:
            sample = [ln for ln in field.text(sym).splitlines() if "Tex" in ln or "Vertex" in ln or "Tri" in ln][:6]
            print(f"link_level_assets: {sym} ({field.defs[sym][1]}): " + " | ".join(sample))
    lights = find_lights(field)

    lines = ["// Generated by tools/remix/link_level_assets.py from the extracted Hyrule Field. Do not edit.",
             "#ifndef ANCIENT_HF_H", "#define ANCIENT_HF_H", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    for role in ("GRASS", "DIRT", "ROCK"):
        c = chosen.get(role)
        if c:
            name = f"hf_{role.lower()}.rgba16.inc.c"
            (out.parent / name).write_text(rgba16_inc(c["tex"]))
            lines.append(f'#define ANCIENT_HF_{role} "{Path(OUT_REL).parent.as_posix()}/{name}"')
            print(f"link_level_assets: {role.lower()} = {c['sym']} ({c['fmt']} {c['size'][0]}x{c['size'][1]}, floor "
                  f"{c['floor'] / 1e6:.2f}M, wall {c['wall'] / 1e6:.2f}M units², color {tuple(int(v) for v in c['rgb'])})")
        else:
            print(f"link_level_assets: no {role.lower()} texture found; keeping the level's own")
    if lights and lights[2] >= 16:
        lines.append(f'#define ANCIENT_HF_LIGHTS "{lights[1]}"')
        print(f"link_level_assets: light settings = {lights[0]} ({lights[2]} entries)")
    else:
        print(f"link_level_assets: no usable light settings ({lights}); keeping the level's own")
    lines += ["", "#endif", ""]
    out.write_text("\n".join(lines))
    print(f"link_level_assets: wrote {out}")


if __name__ == "__main__":
    main()
