#!/usr/bin/env python3
"""Make a restyled copy of Hyrule Field (a "biome") for the Web Remix.

Run after `make setup`. It copies the extracted Hyrule Field scene
(extracted/VERSION/assets/scenes/overworld/spot00) to
extracted/VERSION/assets/scenes/remix/<biome>/ and restyles the copy:

  - opaque grass textures are replaced by the biome's ground tile, dark rocky ones by its rock tile
    (tools/remix/biome_art/<biome>/, made with GPT Image);
  - every other texture, palette and vertex color goes through a color mapping (green -> snow,
    brown/grey -> frosty blue-grey; water, signs and bright colors are kept);
  - the scene's light settings get icy ambient light and fog.

Rooms, collision, spawns and exits are untouched, so the game can load the copy in place of Hyrule Field
(see RemixBiome_OverrideScene in src/code/z_remix_menu.c). Once the copy exists the Makefile builds it in
(REMIX_HAS_TUNDRA=1, spec/remix_scenes.inc).

The copy stays in extracted/ (git-ignored) like all data that comes from the ROM. On any error nothing is
left behind, so the ROM is simply built without the biome.

    python3 tools/remix/make_biome.py --version ntsc-1.2
"""

from __future__ import annotations

import argparse
import re
import shutil
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]

SRC_SCENE = "spot00"
SRC_DIR = f"assets/scenes/overworld/{SRC_SCENE}"

BIOMES = {
    "tundra": {
        "title": "Frozen Tundra",
        # Fog/ambient target color and how strongly light settings move toward it.
        "fog": (200, 215, 238),
        "fog_amount": 0.75,
        "light_amount": 0.45,
        "fog_near_delta": -6,
    },
}

CI_FORMATS = {"ci4", "ci8"}
RGBA_FORMATS = {"rgba16", "rgba32"}
GRAY_FORMATS = {"i4", "i8", "ia4", "ia8", "ia16"}


# ---------------------------------------------------------------- color mapping


def _hsv(rgb: np.ndarray):
    """rgb float array (..., 3) in 0-255 -> hue degrees, saturation 0-1, luminance 0-255."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    d = mx - mn
    sat = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0.0)
    dd = np.maximum(d, 1e-6)
    hue = np.where(
        mx == r,
        ((g - b) / dd) % 6,
        np.where(mx == g, (b - r) / dd + 2, (r - g) / dd + 4),
    ) * 60.0
    hue = np.where(d == 0, 0.0, hue)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return hue, sat, lum


def _lerp(a, b, t):
    return a + (b - a) * t


_SNOW_SHADOW = np.array([118.0, 138.0, 176.0])
_SNOW_LIGHT = np.array([244.0, 248.0, 255.0])
# Frost gradient (luminance -> color) for dirt and rock.
_FROST_STOPS = [
    (0.00, (34.0, 42.0, 62.0)),
    (0.35, (92.0, 108.0, 136.0)),
    (0.62, (168.0, 184.0, 206.0)),
    (1.00, (246.0, 249.0, 255.0)),
]


def _frost(t: np.ndarray) -> np.ndarray:
    out = np.zeros(t.shape + (3,))
    for (t0, c0), (t1, c1) in zip(_FROST_STOPS, _FROST_STOPS[1:]):
        m = (t >= t0) & (t <= t1)
        u = ((t - t0) / (t1 - t0))[..., None]
        out = np.where(m[..., None], _lerp(np.array(c0), np.array(c1), u), out)
    return out


def winter_colors(rgb: np.ndarray) -> np.ndarray:
    """Map colors (..., 3) uint8/float to their tundra version. Pure per-color function, so textures that
    share a palette stay consistent."""
    rgb = rgb.astype(np.float64)
    hue, sat, lum = _hsv(rgb)
    t = lum / 255.0
    out = rgb.copy()

    neutral = sat < 0.12
    green = (~neutral) & (hue >= 62) & (hue < 170)
    warm = (~neutral) & ((hue < 62) | (hue >= 330)) & (sat < 0.78)
    # blue/cyan (water, sky), purple and vivid warm colors (signs, flowers, fire) are kept.

    cool_grey = np.stack([lum * 0.92 + 8, lum * 0.97 + 10, lum * 1.04 + 18], axis=-1)
    out = np.where(neutral[..., None], _lerp(rgb, cool_grey, 0.6), out)

    snow = _lerp(_SNOW_SHADOW, _SNOW_LIGHT, np.clip(t * 1.3 + 0.12, 0, 1)[..., None])
    out = np.where(green[..., None], snow, out)

    out = np.where(warm[..., None], _lerp(rgb, _frost(np.clip(t * 1.08, 0, 1)), 0.88), out)
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def cool_light(rgb, amount):
    """Move a light color toward an icy blue-grey of the same brightness."""
    c = np.array(rgb, dtype=np.float64)
    lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
    target = np.array([lum * 0.88, lum * 0.97, min(255.0, lum * 1.12 + 10)])
    return tuple(int(v) for v in np.clip(np.rint(_lerp(c, target, amount)), 0, 255))


def icy_fog(rgb, fog, amount):
    c = np.array(rgb, dtype=np.float64)
    lum = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
    # Keep night fog dark: scale the icy color by the original brightness.
    scale = float(np.clip(lum / 255.0 * 1.6, 0.22, 1.0))
    target = np.array(fog, dtype=np.float64) * scale
    return tuple(int(v) for v in np.clip(np.rint(_lerp(c, target, amount)), 0, 255))


# ---------------------------------------------------------------- textures


def png_rewrite_palette(path: Path, fn) -> int:
    """Rewrite the PLTE chunk of an indexed PNG in place (indices, tRNS and everything else untouched).
    Returns the number of palette entries."""
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    out = bytearray(data[:8])
    pos = 8
    n = 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if ctype == b"PLTE":
            pal = np.frombuffer(body, dtype=np.uint8).reshape(-1, 3)
            n = len(pal)
            body = fn(pal).astype(np.uint8).tobytes()
            assert len(body) == length
        out += struct.pack(">I", length) + ctype + body
        out += struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF)
        pos += 12 + length
    path.write_bytes(bytes(out))
    return n


def _resize_tile(tile: Image.Image, w: int, h: int) -> Image.Image:
    # Stretch (not crop) so the tile stays seamless when the game repeats it.
    return tile.resize((w, h), Image.LANCZOS)


def restyle_texture(path: Path, tiles: dict, log: list) -> str:
    parts = path.name.split(".")
    if len(parts) < 3:
        return "skip"
    fmt = parts[1]
    if fmt in CI_FORMATS:
        img = Image.open(path)
        if img.mode != "P":
            log.append(f"  {path.name}: ci texture is not an indexed PNG ({img.mode}), kept")
            return "kept"
        n = png_rewrite_palette(path, winter_colors)
        log.append(f"  {path.name}: {fmt} {img.size[0]}x{img.size[1]} palette({n}) recolored")
        return "palette"

    img = Image.open(path)
    w, h = img.size
    if fmt in RGBA_FORMATS:
        rgba = np.array(img.convert("RGBA"))
        rgb = rgba[..., :3].astype(np.float64)
        alpha = rgba[..., 3]
        opaque = alpha >= 128
        hue, sat, lum = _hsv(rgb)
        o = opaque.mean()
        vis = opaque if opaque.any() else np.ones_like(opaque)
        mean_rgb = rgb[vis].mean(axis=0)
        mh, ms, ml = _hsv(mean_rgb[None, :])
        mh, ms, ml = float(mh[0]), float(ms[0]), float(ml[0])
        lum_std = float(lum[vis].std())
        green = 62 <= mh < 170 and ms >= 0.15
        warm_or_grey = (ms < 0.12) or ((mh < 62 or mh >= 330) and ms < 0.78)
        stats = f"{fmt} {w}x{h} mean=({mean_rgb[0]:.0f},{mean_rgb[1]:.0f},{mean_rgb[2]:.0f}) std={lum_std:.0f} opaque={o:.2f}"

        if o > 0.98 and min(w, h) >= 16 and green and "ground" in tiles:
            out = np.array(_resize_tile(tiles["ground"], w, h).convert("RGBA"))
            out[..., 3] = 255
            decision = "ground tile"
        elif o > 0.98 and min(w, h) >= 32 and warm_or_grey and ml < 125 and lum_std > 28 and "rock" in tiles:
            out = np.array(_resize_tile(tiles["rock"], w, h).convert("RGBA"))
            out[..., 3] = 255
            decision = "rock tile"
        else:
            out = rgba.copy()
            out[..., :3] = winter_colors(rgba[..., :3])
            decision = "recolored"
        Image.fromarray(out, "RGBA").save(path)
        log.append(f"  {path.name}: {stats} -> {decision}")
        return decision

    if fmt in GRAY_FORMATS:
        has_alpha = img.mode in ("LA", "RGBA", "PA")
        la = np.array(img.convert("LA"))
        # Intensity textures are tinted by vertex colors (recolored separately): just soften the darks.
        la[..., 0] = np.clip(np.rint(36 + la[..., 0].astype(np.float64) * 0.86), 0, 255).astype(np.uint8)
        Image.fromarray(la, "LA").convert("LA" if has_alpha else "L").save(path)
        log.append(f"  {path.name}: {fmt} {w}x{h} brightened")
        return "brightened"

    log.append(f"  {path.name}: unknown format {fmt!r}, kept")
    return "kept"


# ---------------------------------------------------------------- C sources

VTX_RE = re.compile(
    r"VTX\(\s*(-?\w+),\s*(-?\w+),\s*(-?\w+),\s*(-?\w+),\s*(-?\w+),\s*(\w+),\s*(\w+),\s*(\w+),\s*(\w+)\s*\)"
)
# Top-level definitions in the scene/room .c files (catches ones the headers don't declare, like the
# extractor's `u8 spot00_scene_zeros_0123F4[12] = { 0 };` padding).
DEFINITION_RE = re.compile(r"^(?:static\s+)?[A-Za-z_][\w \t\*]*?\b([A-Za-z_]\w*)\s*(?:\[[^\]\n]*\]\s*)*=", re.M)
EXTERN_RE = re.compile(r"^\s*extern\s+[^;=]*?\b([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*;", re.M)
IDENT_RE = re.compile(r"\b[A-Za-z_]\w*\b")
GSVTX_RE = re.compile(r"gsSPVertex\(\s*&?\s*\(?\s*([A-Za-z_]\w*)")
TRIPLE_RE = re.compile(r"\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}")
FOGNEAR_RE = re.compile(r"BLEND_RATE_AND_FOG_NEAR\(\s*(\d+),\s*(\d+)\s*\)")


def lit_vertex_arrays(texts: dict) -> set:
    """Vertex arrays drawn while G_LIGHTING is on hold normals, not colors: find them so they are left alone."""
    lit = set()
    for text in texts.values():
        if "gsSP" not in text or "G_LIGHTING" not in text:
            continue
        lighting = False
        for line in text.splitlines():
            if "GeometryMode" in line:
                if "gsSPSetGeometryMode" in line and "G_LIGHTING" in line:
                    lighting = True
                elif "gsSPClearGeometryMode" in line and "G_LIGHTING" in line:
                    lighting = False
                elif "gsSPLoadGeometryMode" in line:
                    lighting = "G_LIGHTING" in line
                elif "gsSPGeometryMode" in line:
                    inner = line[line.index("(") + 1 :]
                    clear, _, setm = inner.partition(",")
                    if "G_LIGHTING" in setm:
                        lighting = True
                    elif "G_LIGHTING" in clear:
                        lighting = False
            m = GSVTX_RE.search(line)
            if m and lighting:
                lit.add(m.group(1))
    return lit


def recolor_vertices(text: str) -> tuple[str, int]:
    def num(s):
        return int(s, 0)

    matches = list(VTX_RE.finditer(text))
    if not matches:
        return text, 0
    cols = np.array([[num(m.group(6)), num(m.group(7)), num(m.group(8))] for m in matches], dtype=np.uint8)
    new = winter_colors(cols)
    out = []
    last = 0
    for m, c in zip(matches, new):
        out.append(text[last : m.start(6)])
        out.append(f"0x{c[0]:02X}, 0x{c[1]:02X}, 0x{c[2]:02X}")
        last = m.end(8)
    out.append(text[last:])
    return "".join(out), len(matches)


def restyle_lights(text: str, cfg: dict) -> tuple[str, int]:
    """EnvLightSettings: per entry 6 triples (ambient, dir1, color1, dir2, color2, fog), then fog near, zFar."""
    triples = list(TRIPLE_RE.finditer(text))
    if len(triples) % 6 != 0 or not triples:
        raise ValueError(f"unexpected light settings layout ({len(triples)} color/dir triples)")
    out = []
    last = 0
    for i, m in enumerate(triples):
        role = i % 6
        rgb = tuple(int(m.group(k)) for k in (1, 2, 3))
        if role in (0, 2, 4):
            rgb = cool_light(rgb, cfg["light_amount"])
        elif role == 5:
            rgb = icy_fog(rgb, cfg["fog"], cfg["fog_amount"])
        else:
            continue  # light directions
        out.append(text[last : m.start()])
        out.append("{ " + f"{rgb[0]:3}, {rgb[1]:3}, {rgb[2]:3}" + " }")
        last = m.end()
    out.append(text[last:])
    text = "".join(out)

    def fog_near(m):
        near = int(m.group(2))
        if near >= 900:
            near = max(900, near + cfg["fog_near_delta"])
        return f"BLEND_RATE_AND_FOG_NEAR({m.group(1)}, {near})"

    text = FOGNEAR_RE.sub(fog_near, text)
    return text, len(triples) // 6


def rename_sources(texts: dict, biome: str, symbols: set) -> dict:
    """Give every global symbol a unique name and point includes and room files at the copy."""
    prefix = biome.capitalize() + "_"
    src_inc = f"{SRC_DIR}/"
    dst_inc = f"assets/scenes/remix/{biome}/"

    def rename_line(line: str) -> str:
        if line.lstrip().startswith("#include"):
            line = line.replace(src_inc, dst_inc)
            return re.sub(rf'\b{SRC_SCENE}_(scene|room_\d+)\.h"', rf'{biome}_\1.h"', line)
        line = re.sub(rf"ROM_FILE\(\s*{SRC_SCENE}_(scene|room_\d+)\s*\)", rf"ROM_FILE({biome}_\1)", line)
        return IDENT_RE.sub(lambda m: prefix + m.group(0) if m.group(0) in symbols else m.group(0), line)

    return {name: "".join(rename_line(l) for l in text.splitlines(keepends=True)) for name, text in texts.items()}


# ---------------------------------------------------------------- main


def make_biome(extracted: Path, biome: str, tiles_dir: Path) -> list:
    cfg = BIOMES[biome]
    src = extracted / SRC_DIR
    dst = extracted / "assets/scenes/remix" / biome
    tmp = dst.with_name(dst.name + ".tmp")
    log = [f"{cfg['title']}: copying {src} -> {dst}"]
    # Never leave a stale copy behind: the Makefile builds whatever is in dst.
    shutil.rmtree(dst, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)

    if not (src / f"{SRC_SCENE}_scene.c").is_file():
        raise FileNotFoundError(f"{src}/{SRC_SCENE}_scene.c not found (run `make setup` first)")
    rooms = sorted(p.name for p in src.iterdir() if re.fullmatch(rf"{SRC_SCENE}_room_\d+\.c", p.name))
    if rooms != [f"{SRC_SCENE}_room_0.c"]:
        # spec/remix_scenes.inc lists exactly one room.
        raise ValueError(f"expected one room, found {rooms}")

    tiles = {}
    for kind in ("ground", "rock"):
        p = tiles_dir / f"{kind}.png"
        if p.is_file():
            tiles[kind] = Image.open(p).convert("RGB")

    try:
        shutil.copytree(src, tmp)
        for stem in (f"{SRC_SCENE}_scene", f"{SRC_SCENE}_room_0"):
            for ext in (".c", ".h"):
                (tmp / f"{stem}{ext}").rename(tmp / f"{stem.replace(SRC_SCENE, biome, 1)}{ext}")

        text_files = sorted(p for p in tmp.iterdir() if p.name.endswith((".c", ".h")))
        texts = {p.name: p.read_text() for p in text_files}

        symbols = set()
        for name, text in texts.items():
            if name.endswith(".h"):
                symbols.update(EXTERN_RE.findall(text))
            elif not name.endswith(".inc.c"):
                symbols.update(DEFINITION_RE.findall(text))
        if not symbols:
            raise ValueError("no symbols found in the scene headers")

        # Analyse before renaming: DLs refer to vertex arrays by their original names.
        lit = lit_vertex_arrays(texts)
        n_vtx = n_arrays = n_lit = n_lights = 0
        for name in list(texts):
            text = texts[name]
            if "VTX(" in text:
                stem = name.split(".")[0]
                if stem in lit:
                    n_lit += 1
                    continue
                texts[name], n = recolor_vertices(text)
                n_vtx += n
                n_arrays += 1
            if "BLEND_RATE_AND_FOG_NEAR(" in text and "{" in text:
                texts[name], n = restyle_lights(texts[name], cfg)
                n_lights += n
        if n_lights == 0:
            raise ValueError("no light settings found")
        log.append(f"vertex colors: {n_vtx} vertices in {n_arrays} arrays recolored, {n_lit} lit arrays kept")
        log.append(f"light settings: {n_lights} entries made icy")

        texts = rename_sources(texts, biome, symbols)
        log.append(f"renamed {len(symbols)} symbols")
        for name, text in texts.items():
            (tmp / name).write_text(text)

        counts: dict = {}
        tex_log: list = []
        for png in sorted(tmp.glob("*.png")):
            d = restyle_texture(png, tiles, tex_log)
            counts[d] = counts.get(d, 0) + 1
        log.append("textures: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
        log.extend(tex_log)

        tmp.rename(dst)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(dst, ignore_errors=True)
        raise
    return log


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="ntsc-1.2", help="game version (extracted/VERSION)")
    ap.add_argument("--extracted", type=Path, help="extracted directory (default extracted/VERSION)")
    ap.add_argument("--biome", default="tundra", choices=sorted(BIOMES))
    ap.add_argument("--tiles", type=Path, help="tile images directory (default tools/remix/biome_art/BIOME)")
    args = ap.parse_args()

    extracted = args.extracted or REPO / "extracted" / args.version
    tiles = args.tiles or REPO / "tools/remix/biome_art" / args.biome
    try:
        log = make_biome(extracted, args.biome, tiles)
    except Exception as e:
        print(f"make_biome: {args.biome} not built: {e}", file=sys.stderr)
        sys.exit(1)
    print("\n".join(log))


if __name__ == "__main__":
    main()
