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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extracted_scene import Field, commands, expr, lighting_after, num, parse_vertex  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SRC = "assets/scenes/overworld/spot00"
OUT_REL = "assets/scenes/remix/ancient/ancient_hf.h"

VTX_RE = re.compile(r"VTX\(\s*(-?\w+),\s*(-?\w+),\s*(-?\w+),\s*-?\w+,\s*-?\w+,\s*(\w+),\s*(\w+),\s*(\w+),")
TEXLOAD_RE = re.compile(r"gsDPLoadTextureBlock(?:_4b)?\(\s*(\w+)\s*,")
MULTI_RE = re.compile(r"gsDPLoadMultiBlock(?:_4b)?\(\s*(\w+)\s*,\s*\w+\s*,\s*(\w+)\s*,")
SETTIMG_RE = re.compile(r"gsDPSetTextureImage\([^,]+,[^,]+,[^,]+,\s*(\w+)\s*\)")
VERTEX_RE = re.compile(r"gsSPVertex\((.*)\)")
TRI1_RE = re.compile(r"gsSP1Triangle\(\s*(\d+),\s*(\d+),\s*(\d+)")
TRI2_RE = re.compile(r"gsSP2Triangles\(\s*(\d+),\s*(\d+),\s*(\d+),\s*\d+,\s*(\d+),\s*(\d+),\s*(\d+)")
LIGHTS_CMD_RE = re.compile(r"SCENE_CMD_ENV_LIGHT_SETTINGS\(([^\n]*),[ \t]*&?\(?[ \t]*(\w+)[^,\n]*\)")


TEX_SIZE = (32, 32)  # the level's grass, dirt and rock materials (tools/remix/make_level.py)


def load_vertex_arrays(field: Field):
    """symbol -> (Nx3 positions, Nx3 colors) of every Vtx array."""
    arrays = {}
    for sym in field.of_type("Vtx"):
        rows = [[num(v) for v in m] for m in VTX_RE.findall(field.text(sym))]
        if rows:
            rows = np.array(rows, float)
            arrays[sym] = (rows[:, :3], rows[:, 3:])
    return arrays


PRIM_RE = re.compile(r"gsDPSetPrimColor\(\s*[^,]+,\s*[^,]+,\s*([^,]+),\s*([^,]+),\s*([^,]+),")
QUAD_RE = re.compile(r"gsSP1Quadrangle\(\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)")
CALL_RE = re.compile(r"gsSP(DisplayList|BranchList)\(\s*&?(\w+)\s*\)")
MACRO_RE = re.compile(r"\b(gs[A-Z]\w*)\(")
class Replay:
    """RSP/RDP state while walking display lists: the current texture, lighting, the vertex buffer."""

    def __init__(self):
        self.cur = None
        self.lit = False
        self.prim = None  # primitive color: the field colors its grey (I/IA) textures with it
        self.slots = [None] * 64


def texture_usage(field: Field, arrays, stats=None):
    """Replay the display lists, following calls between them (a texture loaded in one list is drawn by the
    lists it calls). texture symbol -> dict(count, floor area, wall area, summed vertex color, color weight); the
    color only counts where lighting is off (with lighting on, vertex colors are normals)."""
    stats = stats if stats is not None else {}
    dls = field.of_type("Gfx")
    called = set()
    for sym in dls:
        called.update(m.group(2) for m in CALL_RE.finditer(field.text(sym)))
    roots = [d for d in dls if d not in called] or dls
    usage = {}

    def count(key, n=1):
        stats[key] = stats.get(key, 0) + n

    def run(sym, st, depth):
        if depth > 12:
            return
        for line in commands(field.text(sym)):
            for mac in MACRO_RE.findall(line)[:1]:
                stats.setdefault("macros", {})[mac] = stats.setdefault("macros", {}).get(mac, 0) + 1
            st.lit = lighting_after(line, st.lit)
            m = CALL_RE.search(line)
            if m:
                if m.group(2) in field.defs:
                    run(m.group(2), st, depth + 1)
                else:
                    count("calls to unknown lists")
                if m.group(1) == "BranchList":
                    return
                continue
            m = PRIM_RE.search(line)
            if m:
                st.prim = np.array([expr(m.group(i)) for i in (1, 2, 3)], float)
                continue
            m = TEXLOAD_RE.search(line)
            if m:
                st.cur = m.group(1)
                count("texture loads")
                continue
            m = MULTI_RE.search(line)
            if m:
                if m.group(2) in ("G_TX_RENDERTILE", "0"):
                    st.cur = m.group(1)
                    count("texture loads")
                continue
            m = SETTIMG_RE.search(line)
            if m and "G_IM_FMT" in line and "TLUT" not in m.group(1):
                st.cur = m.group(1)
                count("texture loads")
                continue
            m = VERTEX_RE.search(line)
            if m:
                v = parse_vertex(m.group(1))
                if v is None:
                    count("vertex loads not understood")
                    stats.setdefault("samples", []).append(line.strip()[:120])
                    st.slots = [None] * 64
                    continue
                vsym, start, n, v0 = v
                arr = arrays.get(vsym)
                count("vertex loads")
                if arr is None:
                    count("vertex loads from unknown arrays")
                    stats.setdefault("samples", []).append(line.strip()[:120])
                for k in range(n):
                    if v0 + k < len(st.slots):
                        ok = arr is not None and start + k < len(arr[0])
                        st.slots[v0 + k] = (arr[0][start + k], arr[1][start + k]) if ok else None
                continue
            tris = []
            m = TRI2_RE.search(line)
            if m:
                g = [int(x) for x in m.groups()]
                tris = [g[:3], g[3:]]
            elif (m := QUAD_RE.search(line)) is not None:
                q = [int(x) for x in m.groups()]
                tris = [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
            elif (m := TRI1_RE.search(line)) is not None:
                tris = [[int(x) for x in m.groups()]]
            for t in tris:
                count("triangles")
                if st.cur is None:
                    count("triangles with no texture")
                    continue
                if any(i >= len(st.slots) or st.slots[i] is None for i in t):
                    count("triangles with unknown vertices")
                    continue
                pa, pb, pc = (st.slots[i][0] for i in t)
                n = np.cross(pb - pa, pc - pa)
                area = np.linalg.norm(n) / 2
                if area < 1:
                    continue
                ny = n[1] / (2 * area)
                u = usage.setdefault(st.cur, dict(count=0, floor=0.0, wall=0.0, color=np.zeros(3), weight=0.0,
                                                  prim=np.zeros(3), prim_weight=0.0))
                if st.prim is not None:
                    u["prim"] += st.prim * area
                    u["prim_weight"] += area
                u["count"] += 1
                if ny > 0.75:
                    u["floor"] += area
                elif abs(ny) < 0.55:
                    u["wall"] += area
                if not st.lit:
                    u["color"] += sum(st.slots[i][1] for i in t) / 3 * area
                    u["weight"] += area

    for root in roots:
        run(root, Replay(), 0)
    stats["root lists"] = len(roots)
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
        if fmt.startswith(("i4", "i8", "ia")):
            # Grey textures get their color when drawn: from the primitive color, else from vertex colors.
            if u["prim_weight"] > 0:
                tint = u["prim"] / u["prim_weight"] * (tint / 255.0 if tint is not None else 1.0)
            if tint is None:
                continue  # its real color is unknown: grey would not look like the field
        tex = to_level_texture(fmt, img, tint)
        r, g, b = tex[..., :3].reshape(-1, 3).mean(0)
        out.append(dict(sym=sym, fmt=fmt, size=img.size, tex=tex, rgb=(r, g, b), floor=u["floor"], wall=u["wall"],
                        green=g > r * 1.02 and g > b * 1.15, brown=r >= g * 0.97 and g > b * 1.08))
    return out


def pick(cands):
    """Grass: the green texture covering the most floor. Dirt: the brown one covering the most floor. Rock: the
    texture covering the most wall. Color textures come first: the field uses grey (I/IA) ones mostly as blend
    masks and detail layers, which look wrong on their own (dark bands), so they only stand in when no color
    texture fits."""
    color = [c for c in cands if not c["fmt"].startswith(("i4", "i8", "ia"))]
    out = {}

    def choose(role, ok, key):
        for pool in (color, cands):
            found = [c for c in pool if ok(c) and not any(c is v for v in out.values())]
            if found:
                out[role] = max(found, key=key)
                return

    choose("GRASS", lambda c: c["green"] and c["floor"] > 0, lambda c: c["floor"])
    choose("DIRT", lambda c: c["brown"] and c["floor"] > 0, lambda c: c["floor"])
    choose("ROCK", lambda c: c["wall"] > 0, lambda c: c["wall"])
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


# Ground for the town and water for the island's waterfall, from other scenes: (macro, scene folder, symbol, else the
# scene's n-th texture by floor area). Sizes are changed to the level's 32x32.
BORROWED = [
    ("ANCIENT_TOWN_GROUND", "assets/scenes/overworld/spot10", "spot10_scene_0000F430_Tex", 2),  # Lost Woods: mossy stones
    ("ANCIENT_ZORA_WATER", "assets/scenes/overworld/spot03", "spot03_scene_00008D58_Tex", 1),  # Zora's River's water
]


def floor_textures(field: Field):
    """Texture symbols of a scene by the floor area they cover, most first."""
    from extracted_scene import replay

    area = {}
    for room in field.rooms():
        for e in field.room_entries(room):
            for dl in (e["opa"], e["xlu"]):
                if not dl:
                    continue

                def on_tri(v, st):
                    if not st["tex"] or st["tex"].startswith("seg:"):
                        return
                    p = v[:, :3]
                    n = np.cross(p[1] - p[0], p[2] - p[0])
                    a = np.linalg.norm(n) / 2
                    if a >= 1 and n[1] / (2 * a) > 0.75:
                        area[st["tex"]] = area.get(st["tex"], 0.0) + a

                replay(field, dl, on_tri, {})
    return [s for s, _ in sorted(area.items(), key=lambda kv: -kv[1])]


def borrow_textures(ext: Path, out_dir: Path, lines: list):
    for macro, rel, sym, rank in BORROWED:
        src = ext / rel
        if not src.is_dir():
            print(f"link_level_assets: {rel} not found; {macro} keeps the level's own")
            continue
        field = Field(ext, src)
        got = field.texture(sym) if sym in field.defs else None
        used = sym
        if got is None:
            ranked = [t for t in floor_textures(field) if field.texture(t) is not None]
            if len(ranked) <= rank:
                print(f"link_level_assets: no texture for {macro}")
                continue
            used = ranked[rank]
            got = field.texture(used)
        fmt, img = got
        if img.size != TEX_SIZE:
            img = img.resize(TEX_SIZE, Image.LANCZOS)
        a = np.array(img.convert("RGBA"))
        a[..., 3] = 255
        name = macro.lower().replace("ancient_", "") + ".rgba16.inc.c"
        (out_dir / name).write_text(rgba16_inc(a))
        lines.append(f'#define {macro} "{Path(OUT_REL).parent.as_posix()}/{name}"')
        print(f"link_level_assets: {macro} = {used} ({fmt}, mean color {tuple(int(v) for v in a[..., :3].reshape(-1, 3).mean(0))})")


# The scenery models (town_plan.DECOR_SOURCES), each split in two so that hundreds of copies share one material:
# a setup list (texture, render mode) drawn once per group and a geometry list drawn per copy. The bush is also
# copied with its texture recolored to glow Sheikah blue.
BUSH_DIR = "assets/objects/gameplay_field_keep"
GLOW = ((24, 120, 150), (80, 215, 240), (210, 255, 255))  # dark, mid, light: bright, it glows
GEOMETRY_CMDS = ("gsSPVertex", "gsSP1Triangle", "gsSP2Triangles", "gsSP1Quadrangle", "gsSPEndDisplayList", "gsDPPipeSync",
                 "gsSPCullDisplayList")
IDENT_RE = re.compile(r"\b[A-Za-z_]\w*\b")


def glow_model(field: Field, sym: str, name: str):
    """(text, setup cmds, geometry cmds) of a copy of the model with its texture recolored to glow, unlit."""
    from extracted_scene import replay

    tris = []
    replay(field, sym, lambda v, st: tris.append((v.copy(), st)), {})
    if not tris:
        return None
    groups = {}
    for v, st in tris:
        groups.setdefault((st["tex"], st["tile"], st["scale"]), []).append(v)
    texts, vtx, setup, geom = [], [], [], []
    setup += ["gsDPPipeSync()",
              "gsDPSetOtherMode(G_AD_NOISE | G_CD_MAGICSQ | G_CK_NONE | G_TC_FILT | G_TF_BILERP | G_TT_NONE | G_TL_TILE | "
              "G_TD_CLAMP | G_TP_PERSP | G_CYC_2CYCLE | G_PM_NPRIMITIVE, G_AC_NONE | G_ZS_PIXEL | G_RM_FOG_SHADE_A | "
              "G_RM_AA_ZB_TEX_EDGE2)",
              # unlit, so it glows the same day and night; both sides of the leaves
              "gsSPLoadGeometryMode(G_ZBUFFER | G_SHADE | G_FOG | G_SHADING_SMOOTH)",
              "gsDPSetCombineLERP(TEXEL0, 0, SHADE, 0, 0, 0, 0, TEXEL0, COMBINED, 0, PRIMITIVE, 0, 0, 0, 0, COMBINED)",
              "gsDPSetPrimColor(0, 0, 255, 255, 255, 255)"]
    for gi, ((tex, tile, scale), vs) in enumerate(groups.items()):
        got = field.texture(tex) if tex and not tex.startswith("seg:") else None
        if got is None:
            return None
        fmt, img = got
        a = np.array(img.convert("RGBA")).astype(float)
        lum = (a[..., 0] * 0.3 + a[..., 1] * 0.59 + a[..., 2] * 0.11) / 255
        opaque = a[..., 3] >= 128
        if opaque.any():
            lo, hi = np.percentile(lum[opaque], 3), np.percentile(lum[opaque], 97)
            lum = np.clip((lum - lo) / max(hi - lo, 0.05), 0, 1)
        dark, mid, light = (np.array(c, float) for c in GLOW)
        t = lum[..., None]
        rgb = np.where(t < 0.5, dark + (mid - dark) * t * 2, mid + (light - mid) * (t * 2 - 1))
        out = np.concatenate([rgb, a[..., 3:4]], -1).round().clip(0, 255).astype(np.uint8)
        w, h = img.size
        texts.append(f"u64 {name}_tex_{gi}[] = {{\n{rgba16_inc(out)}}};\n")
        tile = tile or ("G_TX_NOMIRROR | G_TX_WRAP", "G_TX_NOMIRROR | G_TX_WRAP", str(int(np.log2(w))), str(int(np.log2(h))),
                        "G_TX_NOLOD", "G_TX_NOLOD")
        sc = scale or (0xFFFF, 0xFFFF)
        mat = [f"gsSPTexture(0x{sc[0]:04X}, 0x{sc[1]:04X}, 0, G_TX_RENDERTILE, G_ON)",
               f"gsDPLoadTextureBlock({name}_tex_{gi}, G_IM_FMT_RGBA, G_IM_SIZ_16b, {w}, {h}, 0, " + ", ".join(tile) + ")"]
        (setup if len(groups) == 1 else geom).extend(mat)  # one texture: loaded once per group of copies
        ys = np.concatenate([v[:, 1] for v in vs])
        y0, y1 = float(ys.min()), float(ys.max())
        for k in range(0, len(vs), 10):  # 10 triangles = 30 vertices per load (fits the 32-vertex buffer)
            chunk = vs[k:k + 10]
            base = len(vtx)
            for v in chunk:
                for row in v:
                    b = 0.8 + 0.2 * (row[1] - y0) / max(y1 - y0, 1)  # brighter toward the top
                    c = int(round(255 * b))
                    vtx.append(f"    VTX({int(row[0])}, {int(row[1])}, {int(row[2])}, {int(row[3])}, {int(row[4])}, "
                               f"0x{c:02X}, 0x{c:02X}, 0x{c:02X}, 0xFF),")
            geom.append(f"gsSPVertex(&{name}_vtx[{base}], {3 * len(chunk)}, 0)")
            for i in range(0, len(chunk) - 1, 2):
                geom.append(f"gsSP2Triangles({3 * i}, {3 * i + 1}, {3 * i + 2}, 0, {3 * i + 3}, {3 * i + 4}, {3 * i + 5}, 0)")
            if len(chunk) % 2:
                i = len(chunk) - 1
                geom.append(f"gsSP1Triangle({3 * i}, {3 * i + 1}, {3 * i + 2}, 0)")
    text = "".join(texts) + f"Vtx {name}_vtx[] = {{\n" + "\n".join(vtx) + "\n};\n"
    print(f"link_level_assets: {name}: {sym} recolored to glow, {len(tris)} triangles, {len(groups)} texture(s)")
    return text, setup, geom


def split_model(field: Field, sym: str, name: str):
    """(externs, setup cmds, geometry cmds) of the game's model split where its geometry starts (the same data, by
    reference), or None when it changes material after that (then it is drawn whole)."""
    from extracted_scene import commands

    cmds = commands(field.text(sym))
    first = next((i for i, c in enumerate(cmds) if c.startswith("gsSPVertex")), None)
    if first is None:
        return None
    pre = [c for c in cmds[:first] if not c.startswith("gsSPEndDisplayList")]
    post = [c for c in cmds[first:] if not c.startswith("gsSPEndDisplayList")]
    if any(not c.startswith(GEOMETRY_CMDS) for c in post) or any(c.startswith(("gsSPDisplayList", "gsSPBranchList")) for c in pre):
        print(f"link_level_assets: {name}: {sym} changes material inside its geometry; drawn whole")
        return None
    words = {w for c in pre + post for w in IDENT_RE.findall(c)}
    used = sorted(w for w in words if w in field.defs and w != sym)
    externs = "".join(f"extern {field.defs[w][0]} {w}[];\n" for w in used)
    # texture sizes by name (gFieldBushTex_WIDTH): the object's header defines them; here they come from the image
    for w in sorted(words):
        m = re.fullmatch(r"(\w+)_(WIDTH|HEIGHT)", w)
        tex = field.texture(m.group(1)) if m and m.group(1) in field.defs else None
        if m and tex is None:
            print(f"link_level_assets: {name}: no size for {w}; drawn whole")
            return None
        if m:
            size = tex[1].size[0 if m.group(2) == "WIDTH" else 1]
            externs += f"#ifndef {w}\n#define {w} {size}\n#endif\n"
    print(f"link_level_assets: {name}: {sym} split: {len(pre)} setup commands, {len(post)} geometry commands")
    return externs, pre, post


def decor_models(ext: Path, out_dir: Path, lines: list):
    import town_plan

    src = ext / BUSH_DIR
    if not src.is_dir():
        print(f"link_level_assets: {BUSH_DIR} not found; the scenery is drawn the plain way")
        return
    field = Field(ext, src)
    body = ["// Generated by tools/remix/link_level_assets.py: the scenery models, each as a setup list and a geometry",
            "// list (make_level.py draws the setup once per group of copies), from gameplay_field_keep.",
            "Gfx ancient_decor_none[] = { gsSPEndDisplayList() };"]
    defines = []
    for kind, (sym, _, glow) in town_plan.DECOR_SOURCES.items():
        name = f"ancient_decor_{kind}"
        macro = f"ANCIENT_DECOR_{kind.upper()}"
        got = None
        if sym in field.defs:
            if glow:
                g = glow_model(field, sym, name)
                got = (g[0], g[1], g[2]) if g else None
            else:
                got = split_model(field, sym, name)
        if got is None:  # drawn whole, as the game does
            body.append(f"extern Gfx {sym}[];")
            defines += [f"#define {macro}_SETUP ancient_decor_none", f"#define {macro}_GEOM {sym}"]
            continue
        text, setup, geom = got
        body.append(text)
        body.append(f"Gfx {name}_setup[] = {{\n" + "".join(f"    {c},\n" for c in setup) + "    gsSPEndDisplayList(),\n};")
        body.append(f"Gfx {name}_geom[] = {{\n" + "".join(f"    {c},\n" for c in geom) + "    gsSPEndDisplayList(),\n};")
        defines += [f"#define {macro}_SETUP {name}_setup", f"#define {macro}_GEOM {name}_geom"]
    (out_dir / "decor_models.inc.c").write_text("\n".join(body + defines) + "\n")
    lines.append(f'#define ANCIENT_DECOR_MODELS "{Path(OUT_REL).parent.as_posix()}/decor_models.inc.c"')


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
    stats = {}
    arrays = load_vertex_arrays(field)
    usage = texture_usage(field, arrays, stats)
    types = {}
    for t, _ in field.defs.values():
        types[t] = types.get(t, 0) + 1
    macros = stats.pop("macros", {})
    samples = stats.pop("samples", [])
    print(f"link_level_assets: definitions by type: {types}; {len(arrays)} vertex arrays read")
    print(f"link_level_assets: replay: {stats}; {len(usage)} textures drawn on triangles")
    for line in samples[:3]:
        print(f"link_level_assets:   e.g. {line}")
    print("link_level_assets: display list commands: "
          + ", ".join(f"{k} {v}" for k, v in sorted(macros.items(), key=lambda kv: -kv[1])))
    cands = candidates(field, usage)
    for c in sorted(cands, key=lambda c: -(c["floor"] + c["wall"]))[:12]:
        print(f"link_level_assets:   {c['sym']}: {c['fmt']} {c['size'][0]}x{c['size'][1]} floor {c['floor'] / 1e6:.2f}M "
              f"wall {c['wall'] / 1e6:.2f}M color {tuple(int(v) for v in c['rgb'])}")
    skipped = [s for s in usage if field.png(s) is None]
    if skipped:
        print(f"link_level_assets: {len(skipped)} drawn textures without a PNG: {skipped[:6]}")
    chosen = pick(cands)
    lights = find_lights(field)
    n_cmds = len(field.of_type("SceneCmd"))
    n_light_cmds = sum(len(LIGHTS_CMD_RE.findall(field.text(c))) for c in field.of_type("SceneCmd"))
    if not n_light_cmds:
        for c in field.of_type("SceneCmd")[:2]:
            lines = [ln.strip()[:100] for ln in field.text(c).splitlines() if "LIGHT" in ln]
            print(f"link_level_assets:   {c} ({field.defs[c][1]}, {len(field.text(c))} chars): {lines[:2]}")
    print(f"link_level_assets: {n_cmds} command lists, {n_light_cmds} light settings commands, "
          f"{len(field.of_type('EnvLightSettings'))} light lists defined")

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
        lines.append(f"#define ANCIENT_HF_LIGHTS_COUNT {lights[2]}")
        print(f"link_level_assets: light settings = {lights[0]} ({lights[2]} entries)")
    else:
        print(f"link_level_assets: no usable light settings ({lights}); keeping the level's own")
    borrow_textures(ext, out.parent, lines)
    decor_models(ext, out.parent, lines)
    lines += ["", "#endif", ""]
    out.write_text("\n".join(lines))
    print(f"link_level_assets: wrote {out}")


if __name__ == "__main__":
    main()
