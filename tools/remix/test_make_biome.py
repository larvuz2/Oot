#!/usr/bin/env python3
"""Tests for make_biome.py on a small stand-in for the extracted Hyrule Field (same file layout and C
formats as tools/assets/extract writes; no ROM data).

    python3 tools/remix/test_make_biome.py               # run the checks
    python3 tools/remix/test_make_biome.py --fixture DIR # only write the stand-in to DIR (an extracted/VERSION)
"""

import argparse
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_biome  # noqa: E402

D = "assets/scenes/overworld/spot00"


def inc(name):
    return f'#include "{D}/{name}.inc.c"\n'


def write_fixture(ext: Path):
    d = ext / D
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1)

    def w(name, text):
        (d / name).write_text(text)

    # --- scene
    w(
        "spot00_scene.h",
        "#ifndef SPOT00_SCENE_H\n#define SPOT00_SCENE_H\n\n"
        '#include "environment.h"\n#include "romfile.h"\n#include "scene.h"\n#include "ultra64.h"\n\n'
        "extern SceneCmd spot00_sceneCommands[];\n"
        "extern RomFile spot00_sceneRoomList_0000A0[];\n"
        "#define LENGTH_spot00_scene_000000B0_EnvLightSettingsList 2\n"
        "extern EnvLightSettings spot00_scene_000000B0_EnvLightSettingsList[LENGTH_spot00_scene_000000B0_EnvLightSettingsList];\n"
        "\n#endif\n",
    )
    w(
        "spot00_scene.c",
        '#include "spot00_scene.h"\n#include "spot00_room_0.h"\n\n#include "segment_symbols.h"\n\n'
        "SceneCmd spot00_sceneCommands[] = {\n" + inc("spot00_sceneCommands") + "};\n\n"
        "RomFile spot00_sceneRoomList_0000A0[] = {\n" + inc("spot00_sceneRoomList_0000A0") + "};\n\n"
        "EnvLightSettings spot00_scene_000000B0_EnvLightSettingsList[LENGTH_spot00_scene_000000B0_EnvLightSettingsList] = {\n"
        + inc("spot00_scene_000000B0_EnvLightSettingsList")
        + "};\n",
    )
    w(
        "spot00_sceneCommands.inc.c",
        "SCENE_CMD_ROOM_LIST(1, spot00_sceneRoomList_0000A0),\n"
        "SCENE_CMD_ENV_LIGHT_SETTINGS(LENGTH_spot00_scene_000000B0_EnvLightSettingsList, spot00_scene_000000B0_EnvLightSettingsList),\n"
        "SCENE_CMD_END(),\n",
    )
    w("spot00_sceneRoomList_0000A0.inc.c", "ROM_FILE(spot00_room_0),\n")
    w(
        "spot00_scene_000000B0_EnvLightSettingsList.inc.c",
        "{\n    {  70,  45,  57 },\n    {   73,   73,   73 },\n    { 180, 154, 138 },\n    {  -73,  -73,  -73 },\n"
        "    {  20,  20,  60 },\n    { 140, 120, 100 },\n    BLEND_RATE_AND_FOG_NEAR(4, 993),\n    12800,\n},\n"
        "{\n    { 105,  90,  90 },\n    {   73,   73,   73 },\n    { 255, 255, 240 },\n    {  -73,  -73,  -73 },\n"
        "    {  50,  50,  90 },\n    { 100, 100, 120 },\n    BLEND_RATE_AND_FOG_NEAR(4, 996),\n    12800,\n},\n",
    )

    # --- room
    w(
        "spot00_room_0.h",
        "#ifndef SPOT00_ROOM_0_H\n#define SPOT00_ROOM_0_H\n\n#include \"gfx.h\"\n#include \"scene.h\"\n#include \"ultra64.h\"\n\n"
        "extern SceneCmd spot00_room_0Commands[];\n"
        "extern Gfx spot00_room_0DL_000100[];\n"
        "extern Vtx spot00_room_0Vtx_000200[3];\n"
        "extern Vtx spot00_room_0Vtx_000300[3];\n"
        "extern u64 spot00_room_0Tex_000400[];\n"
        "extern u64 spot00_room_0Tex_000C00[];\n"
        "extern u64 spot00_room_0Tex_001400[];\n"
        "extern u64 spot00_room_0Tex_001600[];\n"
        "extern u64 spot00_room_0Tex_001700[];\n"
        "extern u64 spot00_room_0Tex_001700TLUT[];\n"
        "extern u64 spot00_room_0Tex_001800[];\n"
        "extern u64 spot00_room_0Tex_001900[];\n"
        "extern u64 spot00_room_0TLUT_001A00[];\n"
        "\n#endif\n",
    )
    tex = [
        ("spot00_room_0Tex_000400", "rgba16"),
        ("spot00_room_0Tex_000C00", "rgba16"),
        ("spot00_room_0Tex_001400", "rgba16"),
        ("spot00_room_0Tex_001600", "i4"),
        ("spot00_room_0Tex_001700", "ci4"),
        ("spot00_room_0Tex_001700", "tlut.rgba16"),
        ("spot00_room_0Tex_001800", "ci4.tlut_spot00_room_0TLUT_001A00"),
        ("spot00_room_0Tex_001900", "ci4.tlut_spot00_room_0TLUT_001A00"),
        ("spot00_room_0TLUT_001A00", "tlut.rgba16"),
    ]
    body = '#include "spot00_room_0.h"\n\n'
    body += "SceneCmd spot00_room_0Commands[] = {\n" + inc("spot00_room_0Commands") + "};\n\n"
    body += "Gfx spot00_room_0DL_000100[] = {\n" + inc("spot00_room_0DL_000100") + "};\n\n"
    body += "Vtx spot00_room_0Vtx_000200[3] = {\n" + inc("spot00_room_0Vtx_000200") + "};\n\n"
    body += "Vtx spot00_room_0Vtx_000300[3] = {\n" + inc("spot00_room_0Vtx_000300") + "};\n\n"
    for name, fmt in tex:
        sym = name + ("TLUT" if fmt == "tlut.rgba16" and "Tex" in name else "")
        body += f"u64 {sym}[] = {{\n" + inc(f"{name}.{fmt}") + "};\n\n"
    w("spot00_room_0.c", body)
    w("spot00_room_0Commands.inc.c", "SCENE_CMD_END(),\n")
    w(
        "spot00_room_0DL_000100.inc.c",
        "gsSPVertex(spot00_room_0Vtx_000200, 3, 0),\ngsSP1Triangle(0, 1, 2, 0),\n"
        "gsSPSetGeometryMode(G_LIGHTING),\ngsSPVertex(spot00_room_0Vtx_000300, 3, 0),\n"
        "gsSP1Triangle(0, 1, 2, 0),\ngsSPEndDisplayList(),\n",
    )
    w(
        "spot00_room_0Vtx_000200.inc.c",
        "VTX(  -100,      0,   -100,  0x0000,  0x0000, 0x40, 0xA0, 0x30, 0xFF),\n"
        "VTX(   100,      0,   -100,  0x0400, -0x0400, 0x8C, 0x64, 0x3C, 0xFF),\n"
        "VTX(     0,      0,    100,  0x0200,  0x0400, 0x30, 0x60, 0xD0, 0x80),\n",
    )
    w(
        "spot00_room_0Vtx_000300.inc.c",
        "VTX(  -100,     50,   -100,  0x0000,  0x0000, 0x00, 0x7F, 0x00, 0xFF),\n"
        "VTX(   100,     50,   -100,  0x0000,  0x0000, 0x00, 0x7F, 0x00, 0xFF),\n"
        "VTX(     0,     50,    100,  0x0000,  0x0000, 0x00, 0x7F, 0x00, 0xFF),\n",
    )

    # --- textures
    def rgba(path, base, noise, alpha=None, size=(32, 32)):
        a = np.clip(np.array(base) + rng.normal(0, noise, (size[1], size[0], 1)), 0, 255).astype(np.uint8)
        al = np.full((size[1], size[0], 1), 255, np.uint8) if alpha is None else alpha
        Image.fromarray(np.concatenate([a, al], axis=-1), "RGBA").save(d / path)

    rgba("spot00_room_0Tex_000400.rgba16.png", (70, 140, 50), 12)  # grass
    rgba("spot00_room_0Tex_000C00.rgba16.png", (95, 75, 55), 40)  # dark rock
    bush_alpha = np.where(rng.random((16, 16, 1)) > 0.5, 255, 0).astype(np.uint8)
    rgba("spot00_room_0Tex_001400.rgba16.png", (60, 130, 40), 10, bush_alpha, (16, 16))
    Image.fromarray(rng.integers(0, 256, (16, 16), dtype=np.uint8), "L").save(d / "spot00_room_0Tex_001600.i4.png")

    def ci(path, pal, trns=None):
        img = Image.fromarray(rng.integers(0, len(pal), (16, 16), dtype=np.uint8), "P")
        img.putpalette([c for rgb in pal for c in rgb])
        kw = {"transparency": bytes(trns)} if trns is not None else {}
        img.save(d / path, bits=8, **kw)  # the extractor writes 8-bit indexed PNGs

    pal = [(int(20 + 12 * i), int(90 + 8 * i), int(30 + 5 * i)) for i in range(16)]
    ci("spot00_room_0Tex_001700.ci4.png", pal, [0] + [255] * 15)
    pal2 = [(int(120 + 6 * i), int(90 + 5 * i), int(60 + 3 * i)) for i in range(16)]
    ci("spot00_room_0Tex_001800.ci4.tlut_spot00_room_0TLUT_001A00.png", pal2)
    ci("spot00_room_0Tex_001900.ci4.tlut_spot00_room_0TLUT_001A00.png", pal2)


def png_chunks(path):
    import struct

    data = path.read_bytes()
    pos, out = 8, {}
    while pos < len(data):
        (n,) = struct.unpack(">I", data[pos : pos + 4])
        out.setdefault(data[pos + 4 : pos + 8], []).append(data[pos + 8 : pos + 8 + n])
        pos += 12 + n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", type=Path)
    args = ap.parse_args()
    if args.fixture:
        write_fixture(args.fixture)
        return

    fails = 0

    def check(name, ok):
        nonlocal fails
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
        fails += not ok

    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as t:
        ext = Path(t)
        write_fixture(ext)
        src = ext / D
        before = {p.name: p.read_bytes() for p in src.iterdir()}
        log = make_biome.make_biome(ext, "tundra", repo / "tools/remix/biome_art/tundra")
        out = ext / "assets/scenes/remix/tundra"
        check("source left untouched", before == {p.name: p.read_bytes() for p in src.iterdir()})
        check("copy made, no temp dir", out.is_dir() and not (out.parent / "tundra.tmp").exists())
        check("main files renamed", all((out / f).is_file() for f in ("tundra_scene.c", "tundra_scene.h", "tundra_room_0.c", "tundra_room_0.h")))
        sc = (out / "tundra_scene.c").read_text()
        check("includes point at copy", '#include "tundra_room_0.h"' in sc and "remix/tundra/spot00_sceneCommands.inc.c" in sc and "overworld" not in sc)
        check("symbols renamed", "SceneCmd Tundra_spot00_sceneCommands[]" in sc and "extern Gfx Tundra_spot00_room_0DL_000100[]" in (out / "tundra_room_0.h").read_text())
        check("room list points at copy", (out / "spot00_sceneRoomList_0000A0.inc.c").read_text().strip() == "ROM_FILE(tundra_room_0),")
        dl = (out / "spot00_room_0DL_000100.inc.c").read_text()
        check("DL refs renamed", "gsSPVertex(Tundra_spot00_room_0Vtx_000200, 3, 0)" in dl)
        v = (out / "spot00_room_0Vtx_000200.inc.c").read_text()
        check("unlit vertex colors recolored, positions/UVs/alpha kept", "0x40, 0xA0, 0x30" not in v and "-0x0400" in v and v.count("VTX(") == 3 and re.search(r", 0x80\)", v))
        check("lit vertex normals untouched", (out / "spot00_room_0Vtx_000300.inc.c").read_bytes() == before["spot00_room_0Vtx_000300.inc.c"])
        li = (out / "spot00_scene_000000B0_EnvLightSettingsList.inc.c").read_text()
        check("light dirs kept, fog made icy", "{   73,   73,   73 }" in li and "{ 140, 120, 100 }" not in li and "BLEND_RATE_AND_FOG_NEAR(4, 987)" in li)
        fog = [tuple(map(int, m)) for m in re.findall(r"\{\s*(\d+),\s*(\d+),\s*(\d+)\s*\}", li)][5]
        check("fog is bluish", fog[2] > fog[0])
        g = np.array(Image.open(out / "spot00_room_0Tex_000400.rgba16.png").convert("RGB"), float).mean(axis=(0, 1))
        check("grass texture -> snow tile", g.min() > 170 and g[2] >= g[1] >= g[0] - 5)
        check("rock texture -> rock tile", any("000C00" in l and "rock tile" in l for l in log))
        b = np.array(Image.open(out / "spot00_room_0Tex_001400.rgba16.png"))
        b0 = np.array(Image.open(src / "spot00_room_0Tex_001400.rgba16.png"))
        check("cut-out texture keeps alpha", (b[..., 3] == b0[..., 3]).all() and any("001400" in l and "recolored" in l for l in log))
        c0, c1 = png_chunks(src / "spot00_room_0Tex_001700.ci4.png"), png_chunks(out / "spot00_room_0Tex_001700.ci4.png")
        check("ci palette recolored, indices + tRNS kept", c0[b"PLTE"] != c1[b"PLTE"] and len(c0[b"PLTE"][0]) == len(c1[b"PLTE"][0]) and c0[b"IDAT"] == c1[b"IDAT"] and c0[b"tRNS"] == c1[b"tRNS"])
        s1 = png_chunks(out / "spot00_room_0Tex_001800.ci4.tlut_spot00_room_0TLUT_001A00.png")[b"PLTE"]
        s2 = png_chunks(out / "spot00_room_0Tex_001900.ci4.tlut_spot00_room_0TLUT_001A00.png")[b"PLTE"]
        check("shared palettes stay identical", s1 == s2)
        Image.open(out / "spot00_room_0Tex_001700.ci4.png").load()
        check("i4 texture still grayscale", Image.open(out / "spot00_room_0Tex_001600.i4.png").mode == "L")

        # A broken source leaves nothing behind.
        (src / "spot00_scene.c").unlink()
        try:
            make_biome.make_biome(ext, "tundra", repo / "tools/remix/biome_art/tundra")
            check("missing scene raises", False)
        except FileNotFoundError:
            check("missing scene raises, old copy removed", not out.exists())

    if fails:
        print(f"{fails} check(s) failed")
        sys.exit(1)
    print("All make_biome checks passed")


if __name__ == "__main__":
    main()
