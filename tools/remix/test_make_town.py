#!/usr/bin/env python3
"""Tests for make_town.py on a small stand-in for an extracted town scene (no ROM data): a house (walls, a roof,
windows the scene swaps in at draw time, collision) standing on ground that must be left behind.

    python3 tools/remix/test_make_town.py                 # run the checks
    python3 tools/remix/test_make_town.py --build VERSION # write the town into build/VERSION (to compile it)
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
D = "assets/scenes/overworld/spot01"


def inc(name):
    return f'#include "{D}/{name}.inc.c"\n'


def write_fixture(ext: Path):
    d = ext / D
    d.mkdir(parents=True, exist_ok=True)

    def w(name, text):
        (d / name).write_text(text)

    def vtx(pts, col=(200, 200, 200)):
        return "".join(f"VTX({x}, {y}, {z}, {s}, {t}, 0x{col[0]:02X}, 0x{col[1]:02X}, 0x{col[2]:02X}, 0xFF),\n"
                       for x, y, z, s, t in pts)

    # a 400x300x400 house at (1000, 100, 1000) with a pyramid roof, and a big ground square around it
    x0, x1, z0, z1, y0, y1 = 800, 1200, 800, 1200, 100, 400
    house = [(x0, y0, z0, 0, 0), (x1, y0, z0, 1024, 0), (x1, y1, z0, 1024, 1024), (x0, y1, z0, 0, 1024),
             (x1, y0, z1, 0, 0), (x0, y0, z1, 1024, 0), (x0, y1, z1, 1024, 1024), (x1, y1, z1, 0, 1024),
             (1000, 600, 1000, 512, 0)]
    ground = [(-2000, 100, -2000, 0, 0), (-2000, 100, 3000, 0, 8192), (3000, 100, 3000, 8192, 8192),
              (3000, 100, -2000, 8192, 0)]
    w("spot01_room_0Vtx_000100.inc.c", vtx(house))
    w("spot01_room_0Vtx_000200.inc.c", vtx(ground, (90, 160, 60)))
    w("spot01_room_0DL_000300.inc.c",
      "gsDPPipeSync(),\ngsSPLoadGeometryMode(G_ZBUFFER | G_SHADE | G_CULL_BACK | G_FOG),\n"
      "gsDPLoadTextureBlock(spot01_scene_00012B50_Tex, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, G_TX_NOMIRROR | G_TX_WRAP, "
      "G_TX_NOMIRROR | G_TX_WRAP, 5, 5, G_TX_NOLOD, G_TX_NOLOD),\n"
      "gsSPVertex(&spot01_room_0Vtx_000100[0], 9, 0),\n"
      "gsSP2Triangles(0, 2, 1, 0, 0, 3, 2, 0),\ngsSP2Triangles(4, 6, 5, 0, 4, 7, 6, 0),\n"
      "gsDPLoadTLUT_pal16(0, spot01_scene_0000B550_TLUT),\n"
      "gsDPLoadTextureBlock_4b(spot01_scene_0000C550_CITex, G_IM_FMT_CI, 64, 64, 0, G_TX_MIRROR | G_TX_WRAP, "
      "G_TX_NOMIRROR | G_TX_WRAP, 6, 6, 1, 1),\n"
      "gsSP2Triangles(3, 8, 2, 0, 6, 8, 7, 0),\n"
      "gsDPLoadTextureBlock(0x08000000, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 64, 0, G_TX_NOMIRROR | G_TX_CLAMP, "
      "G_TX_NOMIRROR | G_TX_CLAMP, 5, 6, G_TX_NOLOD, G_TX_NOLOD),\n"
      "gsSP1Triangle(1, 7, 4, 0),\ngsSPEndDisplayList(),\n")
    w("spot01_room_0DL_000400.inc.c",
      "gsDPLoadTextureBlock(spot01_scene_00019350_Tex, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, G_TX_NOMIRROR | G_TX_WRAP, "
      "G_TX_NOMIRROR | G_TX_WRAP, 5, 5, G_TX_NOLOD, G_TX_NOLOD),\n"
      "gsSPVertex(spot01_room_0Vtx_000200, 4, 0),\ngsSP1Quadrangle(0, 1, 2, 3, 0),\ngsSPEndDisplayList(),\n")
    w("spot01_room_0RoomShapeCullableEntry_000500.inc.c",
      "{\n    { 1000, 350, 1000 }, /* center */\n    420,\n    spot01_room_0DL_000300,\n    NULL,\n},\n"
      "{ { 500, 100, 500 }, 3600, spot01_room_0DL_000400, NULL },\n")
    w("spot01_room_0.c", '#include "spot01_room_0.h"\n\n'
      "RoomShapeCullableEntry spot01_room_0RoomShapeCullableEntry_000500[2] = {\n"
      + inc("spot01_room_0RoomShapeCullableEntry_000500") + "};\n\n"
      "Gfx spot01_room_0DL_000300[] = {\n" + inc("spot01_room_0DL_000300") + "};\n\n"
      "Gfx spot01_room_0DL_000400[] = {\n" + inc("spot01_room_0DL_000400") + "};\n\n"
      "Vtx spot01_room_0Vtx_000100[9] = {\n" + inc("spot01_room_0Vtx_000100") + "};\n\n"
      "Vtx spot01_room_0Vtx_000200[4] = {\n" + inc("spot01_room_0Vtx_000200") + "};\n")
    rng = np.random.default_rng(3)

    def rgba(path, base, noise, size=(32, 32)):
        a = np.clip(np.array(base) + rng.normal(0, noise, (size[1], size[0], 1)), 0, 255).astype(np.uint8)
        Image.fromarray(np.concatenate([a, np.full((size[1], size[0], 1), 255, np.uint8)], -1), "RGBA").save(d / path)

    rgba("spot01_scene_00012B50_Tex.rgba16.png", (225, 220, 205), 14)  # white plaster wall
    rgba("spot01_scene_00019350_Tex.rgba16.png", (80, 150, 60), 10)  # grass
    idx = rng.integers(0, 16, (64, 64), dtype=np.uint8)
    pal = [(int(30 + 8 * i), int(110 + 6 * i), int(70 + 4 * i)) for i in range(16)]  # green roof tiles
    im = Image.fromarray(idx, "P")
    im.putpalette([c for rgb in pal for c in rgb] + [0] * (768 - 48))
    im.save(d / "spot01_scene_0000C550_CITex.ci4.tlut_spot01_scene_0000B550_TLUT.png")
    # collision: the house walls (4 quads) and the ground
    cv = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1),
          (-2000, 100, -2000), (-2000, 100, 3000), (3000, 100, 3000), (3000, 100, -2000)]
    polys = [(1, (0, 2, 1)), (1, (0, 3, 2)), (1, (4, 6, 5)), (1, (4, 7, 6)), (0, (8, 9, 10)), (0, (8, 10, 11))]
    w("spot01_sceneCollisionHeader_vtx.inc.c", "".join(f"{{ {a}, {b}, {c} }},\n" for a, b, c in cv))
    w("spot01_sceneCollisionHeader_polys.inc.c", "".join(
        f"{{\n    /* type */ {t},\n    {{\n        COLPOLY_VTX({i[0]}, COLPOLY_IGNORE_NONE),\n        COLPOLY_VTX({i[1]}, 0),\n"
        f"        {i[2]},\n    }},\n    {{ COLPOLY_SNORMAL(0.0), COLPOLY_SNORMAL(1.0), COLPOLY_SNORMAL(0.0) }},\n    0,\n}},\n"
        for t, i in polys))
    surf = ("{\n    SURFACETYPE0(\n        /* bgCamIndex */ CAM,\n        /* exitIndex */ EXIT,\n        FLOOR_TYPE_0,\n"
            "        /* unk18 */ 0,\n        WALL_TYPE_0,\n        FLOOR_PROPERTY_0,\n        /* isSoft */ false,\n"
            "        /* isHorseBlocked */ false\n    ),\n    SURFACETYPE1(\n        MAT,\n        FLOOR_EFFECT_0,\n"
            "        /* lightSetting */ 5,\n        /* echo */ 0,\n        /* canHookshot */ false,\n"
            "        CONVEYOR_SPEED_DISABLED,\n        CONVEYOR_DIRECTION_FROM_BINANG(0x0000),\n        /* unk27 */ false\n    ),\n},\n")

    def fill(cam, exit_, mat):
        return surf.replace("CAM", str(cam)).replace("EXIT", str(exit_)).replace("MAT", mat)

    w("spot01_sceneCollisionHeader_surfaces.inc.c", fill(2, 3, "SURFACE_MATERIAL_DIRT") + fill(1, 0, "SURFACE_MATERIAL_WOOD"))
    w("spot01_sceneCollisionHeader.inc.c",
      "{ -2000, 100, -2000 },\n{ 3000, 600, 3000 },\n12,\nspot01_sceneCollisionHeader_vtx,\n6,\n"
      "spot01_sceneCollisionHeader_polys,\nspot01_sceneCollisionHeader_surfaces,\nNULL,\n0,\nNULL,\n")
    w("spot01_scene.c", '#include "spot01_scene.h"\n\n'
      "Vec3s spot01_sceneCollisionHeader_vtx[] = {\n" + inc("spot01_sceneCollisionHeader_vtx") + "};\n\n"
      "CollisionPoly spot01_sceneCollisionHeader_polys[] = {\n" + inc("spot01_sceneCollisionHeader_polys") + "};\n\n"
      "SurfaceType spot01_sceneCollisionHeader_surfaces[] = {\n" + inc("spot01_sceneCollisionHeader_surfaces") + "};\n\n"
      "CollisionHeader spot01_sceneCollisionHeader = {\n" + inc("spot01_sceneCollisionHeader") + "};\n\n"
      "u64 spot01_scene_00012B50_Tex[] = {\n" + inc("spot01_scene_00012B50_Tex.rgba16") + "};\n\n"
      "u64 spot01_scene_00019350_Tex[] = {\n" + inc("spot01_scene_00019350_Tex.rgba16") + "};\n\n"
      "u64 spot01_scene_0000C550_CITex[] = {\n"
      + inc("spot01_scene_0000C550_CITex.ci4.tlut_spot01_scene_0000B550_TLUT") + "};\n\n")


PLAN = dict(buildings=[
    dict(name="test_house", scene="kakariko", room="spot01_room_0", entries=[0, 1],
         crop=[[780, 60, 780], [1220, 700, 1220]], plot=0, drop_ground=True),
    dict(name="test_gate", scene="kakariko", room="spot01_room_0", entries=[0], plot=None, at="south_road",
         scale=0.5, front=0.0),
])


def run(ext: Path, out: Path):
    plan = out.parent / "plan.json"
    out.mkdir(parents=True, exist_ok=True)
    plan.write_text(json.dumps(PLAN))
    return subprocess.run([sys.executable, str(HERE / "make_town.py"), "--extracted", str(ext), "--out", str(out),
                           "--plan", str(plan)], capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", help="write the stand-in town into build/VERSION (then compile the level)")
    args = ap.parse_args()
    if args.build:
        with tempfile.TemporaryDirectory() as tmp:
            write_fixture(Path(tmp))
            p = run(Path(tmp), REPO / "build" / args.build / "assets/scenes/remix/ancient")
            print(p.stdout + p.stderr)
            sys.exit(p.returncode)

    failures = []

    def check(name, ok):
        print(("ok   " if ok else "FAIL ") + name)
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        write_fixture(tmp / "ext")
        out = tmp / "out"
        p = run(tmp / "ext", out)
        print(p.stdout + p.stderr)
        check("runs", p.returncode == 0)
        h = (out / "ancient_town.h").read_text() if (out / "ancient_town.h").exists() else ""
        check("header names every part", all(f"#define ANCIENT_TOWN_{k}" in h for k in
                                             ("ROOM", "ENTRIES", "COL_VTX", "COL_POLYS", "COL_SURFACES", "BGCHECK_MEMSIZE")))
        room = (out / "ancient_town_room.inc.c").read_text() if (out / "ancient_town_room.inc.c").exists() else ""
        check("two buildings, one room entry each", (out / "ancient_town_entries.inc.c").exists()
              and len((out / "ancient_town_entries.inc.c").read_text().strip().splitlines()) == 2)
        verts = [tuple(int(v) for v in m) for m in re.findall(r"VTX\((-?\d+), (-?\d+), (-?\d+),", room)]
        check("the ground the house stood on is left behind (no 5000-wide pieces)",
              verts and max(abs(a - b) for a, b in zip(max(verts), min(verts))) < 4000)
        check("three restyled textures (wall, roof, window), all CI4 with a palette",
              room.count("u64 ancient_town_tex_") == 3 and room.count("u64 ancient_town_tlut_") == 3
              and "gsDPLoadTextureBlock_4b(ancient_town_tex_" in room)
        check("tiling kept (mirror, shift)", "G_TX_MIRROR | G_TX_WRAP, G_TX_NOMIRROR | G_TX_WRAP, 6, 6, 1, 1" in room)
        check("no raw segment address copied", "0x08000000" not in room)
        polys = (out / "ancient_town_col_polys.inc.c").read_text() if (out / "ancient_town_col_polys.inc.c").exists() else ""
        check("collision copied for the house walls only (4 per building)", polys.count("COLPOLY_VTX(") == 2 * 8)
        surf = (out / "ancient_town_col_surfaces.inc.c").read_text() if (out / "ancient_town_col_surfaces.inc.c").exists() else ""
        check("surface types copied without camera, exit or light setting",
              "SURFACE_MATERIAL_WOOD" in surf and re.search(r"SURFACETYPE0\(0, 0,", surf) is not None
              and "SURFACETYPE1(SURFACE_MATERIAL_WOOD, FLOOR_EFFECT_0, 0," in surf)
        check("collision memory computed", re.search(r"BGCHECK_MEMSIZE 0x[0-9A-F]+", h) is not None)
        log = p.stdout
        check("wall texture became Sheikah stone (plaster)", re.search(r"00012B50_Tex -> \S+ \(plaster", log) is not None)

        p = subprocess.run([sys.executable, str(HERE / "make_town.py"), "--extracted", str(tmp / "missing"), "--out",
                            str(tmp / "none")], capture_output=True, text=True)
        check("without the game's files: exit 1, no header", p.returncode == 1 and not (tmp / "none" / "ancient_town.h").exists())

    print("all passed" if not failures else f"{len(failures)} failed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
