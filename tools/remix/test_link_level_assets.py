#!/usr/bin/env python3
"""Tests for link_level_assets.py on a small stand-in for the extracted Hyrule Field (no ROM data): the
stand-in of test_make_biome.py, plus display lists that put textures on floors and walls, and 16 light settings.

    python3 tools/remix/test_link_level_assets.py               # run the checks
    python3 tools/remix/test_link_level_assets.py --fixture DIR # only write the stand-in to DIR (an extracted/VERSION)
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import link_level_assets  # noqa: E402
import test_make_biome  # noqa: E402

D = test_make_biome.D


def quad(x0, z0, x1, z1, y0=0, y1=0, color=(0x80, 0x80, 0x80)):
    """Two triangles' worth of vertices (a floor when y0 == y1, else a wall from (x0,z0) to (x1,z1))."""
    if y0 == y1:
        pts = [(x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)]  # counter-clockwise from above
    else:
        pts = [(x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0)]
    r, g, b = color
    return "".join(f"VTX({x}, {y}, {z}, 0, 0, 0x{r:02X}, 0x{g:02X}, 0x{b:02X}, 0xFF),\n" for x, y, z in pts)


def write_fixture(ext: Path):
    test_make_biome.write_fixture(ext)
    d = ext / D

    def w(name, text):
        (d / name).write_text(text)

    # floors: grass (big; its texture lives in the scene file under a file name unlike its symbol, as in the real
    # field), a cut-out bush texture (bigger, must be skipped), an I4 texture tinted brown by the vertex colors
    # (dirt), a small RGBA16 one; walls: a CI4 cliff (big, under lighting, so its "colors" are normals) and dark rock.
    vtx = {
        "hf_test_grass_vtx": quad(-3000, -3000, 3000, 3000),
        "hf_test_bush_vtx": quad(-4000, -4000, 4000, 4000, color=(0x10, 0xF0, 0x10)),
        "hf_test_dirt_vtx": quad(-500, -500, 500, 500, color=(0xC0, 0x90, 0x60)),
        "hf_test_small_vtx": quad(-100, -100, 100, 100),
        "hf_test_cliff_vtx": quad(-3000, 3000, 3000, 3000, 0, 1500, color=(0x00, 0x7F, 0x00)),
        "hf_test_rock_vtx": quad(-300, -3000, 300, -3000, 0, 300),
    }
    room_c = (d / "spot00_room_0.c").read_text()
    for k, (sym, text) in enumerate(vtx.items()):
        w(f"spot00_room_0Vtx_00{k + 5}000.inc.c", text)
        room_c += f"Vtx {sym}[4] = {{\n" + test_make_biome.inc(f"spot00_room_0Vtx_00{k + 5}000") + "};\n\n"
    (d / "spot00_room_0.c").write_text(room_c)
    rng = np.random.default_rng(5)
    grass = np.clip(np.array((60, 150, 45)) + rng.normal(0, 14, (32, 32, 1)), 0, 255).astype(np.uint8)
    Image.fromarray(np.concatenate([grass, np.full((32, 32, 1), 255, np.uint8)], -1), "RGBA").save(
        d / "spot00_scene_00013D98_Tex.rgba16.png")
    scene_c = (d / "spot00_scene.c").read_text()
    scene_c += "u64 spot00_sceneTex_013D98[] = {\n" + test_make_biome.inc("spot00_scene_00013D98_Tex.rgba16") + "};\n"
    w("spot00_scene.c", scene_c)
    tris = "gsSP2Triangles(0, 1, 2, 0, 0, 2, 3, 0),\n"
    w(
        "spot00_room_0DL_000100.inc.c",
        "gsDPPipeSync(),\ngsSPLoadGeometryMode(G_ZBUFFER | G_SHADE | G_CULL_BACK | G_FOG),\n"
        "gsDPLoadTextureBlock(spot00_sceneTex_013D98, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, G_TX_NOMIRROR | "
        "G_TX_WRAP, G_TX_NOMIRROR | G_TX_WRAP, 5, 5, G_TX_NOLOD, G_TX_NOLOD),\n"
        "gsSPVertex(hf_test_grass_vtx, 4, 0),\n" + tris +
        "gsDPLoadTextureBlock(spot00_room_0Tex_000400, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, G_TX_NOMIRROR | "
        "G_TX_WRAP, G_TX_NOMIRROR | G_TX_WRAP, 5, 5, G_TX_NOLOD, G_TX_NOLOD),\n"
        "gsSPVertex(hf_test_small_vtx, 4, 0),\n" + tris +
        "gsDPLoadTextureBlock(spot00_room_0Tex_001400, G_IM_FMT_RGBA, G_IM_SIZ_16b, 16, 16, 0, G_TX_NOMIRROR | "
        "G_TX_WRAP, G_TX_NOMIRROR | G_TX_WRAP, 4, 4, G_TX_NOLOD, G_TX_NOLOD),\n"
        "gsSPVertex(&hf_test_bush_vtx[0], 4, 4),\ngsSP2Triangles(4, 5, 6, 0, 4, 6, 7, 0),\n"
        "gsDPLoadTextureBlock_4b(spot00_room_0Tex_001600, G_IM_FMT_I, 16, 16, 0, G_TX_NOMIRROR | G_TX_WRAP, "
        "G_TX_NOMIRROR | G_TX_WRAP, 4, 4, G_TX_NOLOD, G_TX_NOLOD),\n"
        "gsSPVertex(hf_test_dirt_vtx, 4, 0),\n" + tris +
        "gsSPSetGeometryMode(G_LIGHTING),\n"
        "gsDPLoadTLUT_pal16(0, spot00_room_0TLUT_001A00),\n"
        "gsDPLoadTextureBlock_4b(spot00_room_0Tex_001800, G_IM_FMT_CI, 16, 16, 0, G_TX_NOMIRROR | G_TX_WRAP, "
        "G_TX_NOMIRROR | G_TX_WRAP, 4, 4, G_TX_NOLOD, G_TX_NOLOD),\n"
        "gsSPVertex(hf_test_cliff_vtx, 4, 0),\n" + tris +
        "gsSPClearGeometryMode(G_LIGHTING),\n"
        "gsDPLoadTextureBlock(spot00_room_0Tex_000C00, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, G_TX_NOMIRROR | "
        "G_TX_WRAP, G_TX_NOMIRROR | G_TX_WRAP, 5, 5, G_TX_NOLOD, G_TX_NOLOD),\n"
        "gsSPVertex(hf_test_rock_vtx, 4, 0),\n" + tris + "gsSPEndDisplayList(),\n",
    )

    # 16 light settings on the main header; a cutscene header with its own (that must not be picked).
    entry = ("{\n    {  70,  45,  57 },\n    {   73,   73,   73 },\n    { 180, 154, 138 },\n    {  -73,  -73,  -73 },\n"
             "    {  20,  20,  60 },\n    { 140, 120, 100 },\n    BLEND_RATE_AND_FOG_NEAR(4, 993),\n    12800,\n},\n")
    # The light list's file is named unlike its symbol, and a cutscene header has its own list.
    lights = "spot00_scene_000000B0_EnvLightSettingsList"
    w("spot00_scene_lights_main.inc.c", entry * 16)
    (d / f"{lights}.inc.c").unlink()
    w("spot00_scene_header01_LightSettings.inc.c", entry * 4)
    scene_c = (d / "spot00_scene.c").read_text().replace(f'{D}/{lights}.inc.c', f"{D}/spot00_scene_lights_main.inc.c")
    scene_c += ("EnvLightSettings spot00_scene_header01_LightSettings[4] = {\n"
                + test_make_biome.inc("spot00_scene_header01_LightSettings") + "};\n"
                "SceneCmd spot00_scene_header01Commands[] = {\n" + test_make_biome.inc("spot00_scene_header01Commands") + "};\n")
    w("spot00_scene.c", scene_c)
    w(
        "spot00_sceneCommands.inc.c",
        "SCENE_CMD_ALTERNATE_HEADER_LIST(spot00_sceneAlternateHeaders),\n"
        "SCENE_CMD_ROOM_LIST(1, spot00_sceneRoomList_0000A0),\n"
        f"SCENE_CMD_ENV_LIGHT_SETTINGS(LENGTH_{lights}, {lights}),\nSCENE_CMD_END(),\n",
    )
    w(
        "spot00_scene_header01Commands.inc.c",
        "SCENE_CMD_ENV_LIGHT_SETTINGS(4, spot00_scene_header01_LightSettings),\nSCENE_CMD_END(),\n",
    )


def decode_rgba16_inc(text):
    words = [int(x, 16) for x in re.findall(r"0x([0-9A-F]{16})", text)]
    t = np.array([(w >> s) & 0xFFFF for w in words for s in (48, 32, 16, 0)], np.uint32)
    rgb = np.stack([(t >> 11) & 31, (t >> 6) & 31, (t >> 1) & 31], -1)
    return rgb.reshape(32, 32, 3), (t & 1).reshape(32, 32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", type=Path)
    args = ap.parse_args()
    if args.fixture:
        write_fixture(args.fixture)
        print(f"stand-in Hyrule Field (with textured floors/walls and 16 lights) written to {args.fixture}")
        return

    failures = []

    def check(name, ok):
        print(("ok   " if ok else "FAIL ") + name)
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ext = tmp / "extracted"
        write_fixture(ext)
        out = tmp / "build" / link_level_assets.OUT_REL
        p = subprocess.run([sys.executable, str(HERE / "link_level_assets.py"), "--extracted", str(ext), "--out", str(out)],
                           capture_output=True, text=True)
        print(p.stdout + p.stderr)
        check("runs", p.returncode == 0)
        h = out.read_text() if out.exists() else ""
        inc = "assets/scenes/remix/ancient"
        check("grass, dirt and rock linked", all(f'#define ANCIENT_HF_{r} "{inc}/hf_{r.lower()}.rgba16.inc.c"' in h
                                                  for r in ("GRASS", "DIRT", "ROCK")))
        check("main header's light settings linked",
              f'#define ANCIENT_HF_LIGHTS "{D}/spot00_scene_lights_main.inc.c"' in h)
        check("grass is the big green floor, not the bigger cut-out bush", "grass = spot00_sceneTex_013D98" in p.stdout)
        check("dirt is the I4 texture tinted by its vertex colors", "dirt = spot00_room_0Tex_001600" in p.stdout)
        check("rock is the CI4 cliff covering the most wall", "rock = spot00_room_0Tex_001800" in p.stdout)

        g = out.parent / "hf_grass.rgba16.inc.c"
        if g.exists():
            rgb, a = decode_rgba16_inc(g.read_text())
            src = np.array(Image.open(ext / D / "spot00_scene_00013D98_Tex.rgba16.png").convert("RGBA")).astype(int)
            check("grass converted texel for texel (RGBA16 32x32, opaque)",
                  np.abs(rgb * 255 / 31 - src[..., :3]).max() <= 4.2 and a.all())
        dirt = out.parent / "hf_dirt.rgba16.inc.c"
        if dirt.exists():
            rgb, _ = decode_rgba16_inc(dirt.read_text())
            r, gg, b = rgb.reshape(-1, 3).mean(0)
            check("dirt keeps the vertex-color tint (brown)", r > gg > b)
        rock = out.parent / "hf_rock.rgba16.inc.c"
        if rock.exists():
            rgb, _ = decode_rgba16_inc(rock.read_text())
            src = np.array(Image.open(next((ext / D).glob("spot00_room_0Tex_001800.*.png"))).convert("RGB")).astype(int)
            big = np.kron(src, np.ones((2, 2, 1), int))  # 16x16 -> 32x32, nearest
            check("CI4 rock resolved through its palette and scaled up 2x", np.abs(rgb * 255 / 31 - big).max() <= 4.2)

        # No Hyrule Field: exit 1, and no header (the level then uses its own textures).
        out2 = tmp / "none" / "ancient_hf.h"
        p = subprocess.run([sys.executable, str(HERE / "link_level_assets.py"), "--extracted", str(tmp / "missing"),
                            "--out", str(out2)], capture_output=True, text=True)
        check("without the field: exit 1, nothing written", p.returncode == 1 and not out2.exists())

    print("all passed" if not failures else f"{len(failures)} failed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
