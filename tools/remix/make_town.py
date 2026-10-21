#!/usr/bin/env python3
"""Build the Ancient Plateau's town from the game's own buildings (run after `make setup`, before the build).

Takes buildings from Kakariko Village and the other towns of the extracted game (BUILDINGS below: which room
chunks, cropped to which box, which side is the front), and for each building plot of tools/remix/town_plan.py:
  - copies the building's triangles, turned to face the plaza and set on the plot's ground,
  - restyles every texture it uses into the Plateau's materials (tools/remix/restyle.py), same size and tiling,
  - copies its collision (walls, floors, roofs) the same way.
Writes, next to the level's other build-time files (build/VERSION/assets/scenes/remix/ancient/):
  ancient_town.h            macros the level's sources include (the committed empty one means "no town")
  ancient_town_room.inc.c   textures, vertices and display lists, for the room file
  ancient_town_entries.inc.c   room shape entries (one per building)
  ancient_town_col_*.inc.c  collision vertices, polygons and surface types, for the scene file
and the collision memory the bigger collision needs. Nothing from the ROM is committed.

    python3 tools/remix/make_town.py --version ntsc-1.2
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import restyle  # noqa: E402
import town_plan  # noqa: E402
from extracted_scene import Field, collision, replay  # noqa: E402

REPO = HERE.parents[1]
LEVEL = REPO / "assets/scenes/remix/ancient"
INC = "assets/scenes/remix/ancient"
SCENES = {
    "kakariko": "assets/scenes/overworld/spot01",
    "market": "assets/scenes/misc/market_day",
    "lon_lon": "assets/scenes/overworld/spot20",
    "kokiri": "assets/scenes/overworld/spot04",
    "castle": "assets/scenes/overworld/spot15",
    "lake": "assets/scenes/overworld/spot06",
    "fortress": "assets/scenes/overworld/spot12",
    "colossus": "assets/scenes/overworld/spot11",
    "zora_river": "assets/scenes/overworld/spot03",
}

# Where each source town's streets meet: a borrowed building is turned so that the side that faced this point
# faces the Spire.
TOWN_CENTERS = {"kakariko": (100, 450), "lon_lon": (0, -644), "kokiri": (200, 200), "lake": (0, 0),
                "colossus": (0, 0), "fortress": (0, 0)}
KAK_ALL = [0, 3, 4, 5, 6, 7, 8, 9, 12, 15, 16, 17, 18, 19, 2]  # Kakariko chunks, without terrain, cliffs, mountains
KOKIRI_STYLE = {"plant": "stone", "dirt": "wood"}  # the tree-stump houses become stone huts
# Textures whose material the automatic guess gets wrong (steep roofs read as walls), from make_town's log
TEXTURE_CLASSES = {
    "spot01_scene_0000E550_CITex": "roof",  # Kakariko's red roof tiles
    "spot01_scene_0001BF50_CITex": "roof",  # Kakariko's green roof tiles
    "spot01_scene_00012950_CITex": "roof",
    "spot01_scene_0000BF50_Tex": "roof",
    "spot20_scene_0000BD80_CITex": "roof",  # the ranch house's orange tiles
}


def _kak(name, x0, x1, z0, z1, y0, y1, plot):
    return dict(name=name, scene="kakariko", room="spot01_room_0", entries=KAK_ALL,
                crop=((x0, y0, z0), (x1, y1, z1)), plot=plot, drop_ground=True)


def _ll(name, entries, plot, **kw):
    return dict(name=name, scene="lon_lon", room="spot20_room_0", entries=entries, plot=plot, **kw)


def _kok(name, entry, plot):
    return dict(name=name, scene="kokiri", room="spot04_room_0", entries=[entry], plot=plot, style=KOKIRI_STYLE)


# Buildings to borrow: scene, room, room-shape chunks, the box to keep (source coordinates; None = the whole
# chunks), and the plot (index in town_plan.PLOTS: per quarter, 2 inner plots then 3 outer ones), or `at`
# (x, z, yaw) for a spot of its own. Chunk numbers and boxes come from tools/remix/survey_scenes.py.
BUILDINGS: list[dict] = [
    # the quarter on Link's right as he arrives
    # (Kakariko's houses #3, #4 and #7 lean on its hillside and have no back walls: only whole houses are used)
    _kak("kakariko_stone_house_2", -720, -280, 700, 1140, 60, 900, 0),
    _kak("kakariko_red_roof_house", -710, -145, -925, -355, 300, 1100, 1),
    _ll("lon_lon_silo", [7], 2),
    _ll("lon_lon_barn", [5], 3),
    _kak("kakariko_well", 655, 870, 405, 645, -90, 130, 4),
    # the next quarter, clockwise
    _kak("kakariko_gabled_house", -380, 250, 1380, 1830, 220, 1100, 5),
    dict(name="lake_lab", scene="lake", room="spot06_room_0", entries=[5], plot=6),
    _kok("kokiri_small_house", 3, 7),
    _ll("lon_lon_shed", [6], 8),
    dict(name="colossus_ruin_walls", scene="colossus", room="spot11_room_0", entries=[6], plot=9),
    # the far quarter
    _kak("kakariko_gabled_house_3", -380, 250, 1380, 1830, 220, 1100, 10),
    _kak("kakariko_red_roof_house_2", -710, -145, -925, -355, 300, 1100, 11),
    _kak("kakariko_shelter", 230, 375, 1545, 1815, 70, 300, 12),
    dict(name="gerudo_watchtower", scene="fortress", room="spot12_room_0", entries=[8], plot=13),
    dict(name="lake_ruins", scene="lake", room="spot06_room_0", entries=[9], plot=14),
    # the quarter on Link's left
    _ll("lon_lon_ranch_house", [3, 4], 15, crop=((950, -10, -3410), (1410, 600, -2390))),
    _kak("kakariko_stone_house", -720, -280, 700, 1140, 60, 900, 16),
    _kok("kokiri_shop", 15, 17),
    _kak("kakariko_gabled_house_2", -380, 250, 1380, 1830, 220, 1100, 18),
    _kak("kakariko_watchtower", -60, 70, -180, -55, 190, 820, 19),
    # the town gate over the south road, where Link arrives
    _ll("town_gate", [2], None, at="south_road", scale=1.6, front=0.0),
    # a second Lon Lon arch over the main street of the quarter on Link's left, between the ring road and the
    # monoliths (the Colossus's "arch" is a solid rock in the game's data, so it is not used)
    _ll("street_arch", [2], None, at=("street", 3, 1320), scale=1.2, front=0.0),
    # where Link arrives: the Desert Colossus's natural stone arch over the road (long along its z axis, so its x
    # axis follows the road), between the obelisks make_level.py lines the road with
    dict(name="entrance_arch", scene="colossus", room="spot11_room_0", entries=[11], plot=None, at=("south_road", 3110),
         scale=1.0, front=math.pi / 2),
    # Zora's River's rope bridge, in its own colors, from the floating island to the islet (town_plan.bridge_ends)
    dict(name="zora_bridge", scene="zora_river", room="spot03_room_1", entries=[9], plot=None, at="island_bridge",
         style="keep"),
]
SINK = 12  # how far buildings sit into the ground, so no gap shows on uneven terrain


def _up(p):
    n = np.cross(p[1] - p[0], p[2] - p[0])
    ln = np.linalg.norm(n)
    return n[1] / ln if ln > 0 else 0


def rot_y(v, a):
    c, s = math.cos(a), math.sin(a)
    return np.stack([v[..., 0] * c + v[..., 2] * s, v[..., 1], -v[..., 0] * s + v[..., 2] * c], -1)


# ---------------------------------------------------------------- the level's own collision (to stand on)


def own_collision():
    """Vertices, triangles and surface count of the committed level's collision (ancient_scene.c)."""
    text = (LEVEL / "ancient_scene.c").read_text()
    vblock = text[text.index("ancient_sceneCollisionVtx[]") :]
    vblock = vblock[: vblock.index("};")]
    verts = np.array([[int(a), int(b), int(c)] for a, b, c in re.findall(r"\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}", vblock)],
                     float)
    pblock = text[text.index("ancient_sceneCollisionPolys[]") :]
    pblock = pblock[: pblock.index("};")]
    tris = [(int(a), int(b), int(c)) for a, b, c in
            re.findall(r"COLPOLY_VTX\((\d+),[^)]*\), COLPOLY_VTX\((\d+),[^)]*\), (\d+)", pblock)]
    sblock = text[text.index("ancient_sceneSurfaceTypes[]") :]
    n_surf = sblock[: sblock.index("};")].count("SURFACETYPE0")
    return verts, tris, n_surf, len(tris)


def ground_height(verts, tris, x, z):
    """Highest floor of the level's own collision under (x, z)."""
    best = None
    for a, b, c in tris:
        p = verts[[a, b, c]]
        if not (min(p[:, 0]) <= x <= max(p[:, 0]) and min(p[:, 2]) <= z <= max(p[:, 2])):
            continue
        n = np.cross(p[1] - p[0], p[2] - p[0])
        if abs(n[1]) < 1e-6 or n[1] / np.linalg.norm(n) < 0.5:
            continue
        d = np.array([[p[1][0] - p[0][0], p[2][0] - p[0][0]], [p[1][2] - p[0][2], p[2][2] - p[0][2]]])
        try:
            l1, l2 = np.linalg.solve(d, [x - p[0][0], z - p[0][2]])
        except np.linalg.LinAlgError:
            continue
        if l1 < -1e-6 or l2 < -1e-6 or l1 + l2 > 1 + 1e-6:
            continue
        y = p[0][1] + l1 * (p[1][1] - p[0][1]) + l2 * (p[2][1] - p[0][1])
        best = y if best is None else max(best, y)
    return best


# ---------------------------------------------------------------- borrowing a building


class Building:
    def __init__(self, spec, field: Field, col):
        self.spec = spec
        self.tris = []  # (3x9 vertices, state)
        stats = {}
        entries = field.room_entries(spec["room"])
        for i in spec["entries"]:
            e = entries[i]
            for dl in (e["opa"], e["xlu"]):
                if dl:
                    replay(field, dl, lambda v, st: self.tris.append((v.copy(), st)), stats)
        crop = spec.get("crop")
        self.total = len(self.tris)
        if crop:
            lo, hi = np.array(crop[0], float), np.array(crop[1], float)
            self.tris = [(v, st) for v, st in self.tris if np.all((v[:, :3].mean(0) >= lo) & (v[:, :3].mean(0) <= hi))]
        if not self.tris:
            raise ValueError(f"{spec['name']}: no triangles")
        if spec.get("drop_ground"):  # big flat pieces at the bottom are the source town's ground, not the house
            base = min(float(v[:, 1].min()) for v, _ in self.tris)
            kept = []
            for v, st in self.tris:
                n = np.cross(v[1, :3] - v[0, :3], v[2, :3] - v[0, :3])
                area = np.linalg.norm(n) / 2
                if area > 30000 and n[1] / (2 * area) > 0.9 and v[:, 1].max() < base + 60:
                    continue
                kept.append((v, st))
            self.tris = kept or self.tris
        pts = np.concatenate([v[:, :3] for v, _ in self.tris])
        self.lo, self.hi = pts.min(0), pts.max(0)
        self.pivot = np.array([(self.lo[0] + self.hi[0]) / 2, self.lo[1], (self.lo[2] + self.hi[2]) / 2])
        self.scale = float(spec.get("scale", 1.0))
        self.radius = float(np.max(np.hypot(pts[:, 0] - self.pivot[0], pts[:, 2] - self.pivot[2]))) * self.scale
        if "front" in spec:
            self.front = spec["front"]
        else:  # the side that faced the source town's center
            cx, cz = TOWN_CENTERS.get(spec["scene"], (0, 0))
            self.front = math.atan2(cx - self.pivot[0], cz - self.pivot[2])
        # collision inside the same box
        self.col = []
        if col is not None:
            cv, cp, _ = col
            lo = self.lo - [8, 8, 8] if not crop else np.array(crop[0], float)
            hi = self.hi + [8, 8, 8] if not crop else np.array(crop[1], float)
            for surf, ids, flags in cp:
                if max(ids) >= len(cv):
                    continue
                c = cv[list(ids)].mean(0)
                if np.all((c >= lo) & (c <= hi)):
                    self.col.append((cv[list(ids)].copy(), surf, flags))

    def place(self, x, z, ground, face):
        """Move to the plot: the front turned toward `face` (yaw), the base on `ground`."""
        turn = face - self.front
        off = np.array([x, ground - SINK, z])

        def move(p):
            return rot_y((p - self.pivot) * self.scale, turn) + off

        tris = []
        for v, st in self.tris:
            v = v.copy()
            v[:, :3] = move(v[:, :3])
            if st["lit"]:  # normals live in the color channels
                n = np.where(v[:, 5:8] > 127, v[:, 5:8] - 256, v[:, 5:8])
                n = rot_y(n, turn)
                v[:, 5:8] = np.round(np.clip(n, -128, 127)) % 256
            tris.append((v, st))
        cols = [(move(p), surf, flags) for p, surf, flags in self.col]
        return tris, cols


def fit_bridge(b, a, c):
    """Turn, scale and move a borrowed bridge so its deck (the planks: its upward-facing triangles) runs from a to c
    ((x, y, z) each), and keep only the collision of the deck. Returns the plot and the height for Building.place."""
    deck = [v[:, :3] for v, _ in b.tris if _up(v[:, :3]) > 0.7]
    pts = np.concatenate(deck) if deck else np.concatenate([v[:, :3] for v, _ in b.tris])
    xz = pts[:, [0, 2]]
    mean = xz.mean(0)
    _, _, vt = np.linalg.svd(xz - mean)
    axis, side = vt[0], vt[1]
    t = (xz - mean) @ axis
    w = (xz - mean) @ side
    length = float(t.max() - t.min())
    ends = (t < t.min() + 0.15 * length) | (t > t.max() - 0.15 * length)
    mid = mean + axis * (t.max() + t.min()) / 2
    b.pivot = np.array([mid[0], float(np.median(pts[ends, 1])), mid[1]])
    b.front = math.atan2(axis[0], axis[1])
    dx, dz = c[0] - a[0], c[2] - a[2]
    b.scale = math.hypot(dx, dz) / length
    kept = []
    for p, surf, flags in b.col:
        q = p.mean(0)
        tq, wq = (q[[0, 2]] - mean) @ axis, (q[[0, 2]] - mean) @ side
        if t.min() - 20 <= tq <= t.max() + 20 and w.min() - 40 <= wq <= w.max() + 40 and \
                pts[:, 1].min() - 60 <= q[1] <= pts[:, 1].max() + 60:
            kept.append((p, surf, flags))
    b.col = kept
    # the deck and its ropes only (the river banks' railings at its ends would hang in the air)
    def on_deck(v):
        q = v[:, :3].mean(0)
        tq, wq = (q[[0, 2]] - mean) @ axis, (q[[0, 2]] - mean) @ side
        return t.min() - 20 <= tq <= t.max() + 20 and w.min() - 40 <= wq <= w.max() + 40
    b.tris = [(v, st) for v, st in b.tris if on_deck(v)] or b.tris
    plot = dict(x=(a[0] + c[0]) / 2, z=(a[2] + c[2]) / 2, face=math.atan2(dx, dz))
    print(f"make_town: bridge deck {length:.0f} long and {float(w.max() - w.min()):.0f} wide, scaled by {b.scale:.2f}, "
          f"{len(kept)} collision polys kept")
    return plot, (a[1] + c[1]) / 2 + SINK


# ---------------------------------------------------------------- textures


class Textures:
    """Restyled copies of the borrowed textures, one per (scene, symbol)."""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.items = {}  # key -> dict(sym, fmt, w, h, tlut, cls)

    def get(self, field: Field, scene: str, st, usage, style=None):
        key = (scene, st["tex"], style if isinstance(style, str) else tuple(sorted((style or {}).items())))
        if key in self.items:
            return self.items[key]
        w, h = st["size"] or (32, 32)
        if st["tex"].startswith("seg:"):  # a texture the scene swaps in at draw time (e.g. Kakariko's windows)
            img = np.zeros((h, w, 4), np.uint8)
            yy, xx = np.mgrid[0:h, 0:w]
            frame = (xx % max(w // 2, 1) < 2) | (yy % max(h // 2, 1) < 2) | (xx < 2) | (yy < 2)
            img[...] = (200, 200, 200, 255)
            img[frame] = (60, 60, 60, 255)
            fmt_src, has_alpha, name = "rgba16", False, "window"
        else:
            got = field.texture(st["tex"])
            if got is None:
                raise ValueError(f"texture {st['tex']} not found")
            fmt_src, im = got
            img = np.array(im)
            has_alpha = bool((img[..., 3] < 128).any())
            name = st["tex"]
            if fmt_src.startswith(("i4", "i8", "ia")) and st.get("prim"):
                img[..., :3] = (img[..., :3].astype(float) * np.array(st["prim"][:3]) / 255).astype(np.uint8)
            h, w = img.shape[:2]
        mean = img[..., :3][img[..., 3] >= 128].mean(0) if (img[..., 3] >= 128).any() else np.zeros(3)
        cls = restyle.classify(mean, fmt_src, usage, has_alpha, name)
        if style == "keep":  # in its own colors
            cls = "original"
        else:
            cls = (style or {}).get(cls, cls)
            cls = TEXTURE_CLASSES.get(st["tex"], cls)
        new = restyle.restyle(img, cls, seed=len(self.items))
        n = len(self.items)
        sym = f"ancient_town_tex_{n}"
        # 16 colors are plenty for a gradient-mapped texture, at a quarter of RGBA16's memory
        fmt, tlut = "ci4", f"ancient_town_tlut_{n}"
        text, pal = ci4_inc(new)
        (self.out_dir / f"ancient_town_tlut_{n}.inc.c").write_text(pal)
        (self.out_dir / f"ancient_town_tex_{n}.inc.c").write_text(text)
        item = dict(sym=sym, fmt=fmt, w=w, h=h, tlut=tlut, cls=cls, alpha=has_alpha, src=st["tex"], rgba=new)
        self.items[key] = item
        return item


def rgba16_words(a: np.ndarray):
    q = np.round(a[..., :3].astype(float) * 31 / 255).astype(np.uint64)
    t = ((q[..., 0] << 11) | (q[..., 1] << 6) | (q[..., 2] << 1) | (a[..., 3] >= 128).astype(np.uint64)).reshape(-1)
    return t


def pack_u64(halfwords) -> str:
    hw = list(halfwords) + [0] * (-len(halfwords) % 4)
    words = [(int(hw[i]) << 48) | (int(hw[i + 1]) << 32) | (int(hw[i + 2]) << 16) | int(hw[i + 3]) for i in range(0, len(hw), 4)]
    return "".join(f"0x{w:016X}," + ("\n" if k % 4 == 3 else " ") for k, w in enumerate(words)) + "\n"


def rgba16_inc(a: np.ndarray) -> str:
    return pack_u64(rgba16_words(a))


def ci4_inc(a: np.ndarray):
    """(texture text, palette text) of a 16-color version (color 0 transparent when the texture has holes)."""
    from PIL import Image

    alpha = a[..., 3] >= 128
    holes = bool((~alpha).any())
    img = Image.fromarray(a[..., :3])
    q = img.quantize(colors=15 if holes else 16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    idx = np.array(q).astype(np.int64) + (1 if holes else 0)
    pal = np.array(q.getpalette()[: 3 * (15 if holes else 16)], float).reshape(-1, 3)
    if holes:
        idx[~alpha] = 0
        pal = np.vstack([[0, 0, 0], pal])
    pal = np.vstack([pal, np.zeros((16 - len(pal), 3))])
    pal_rgba = np.concatenate([pal, np.full((16, 1), 255.0)], 1)
    if holes:
        pal_rgba[0, 3] = 0
    flat = idx.reshape(-1)
    bytes_ = [(int(flat[i]) << 4) | int(flat[i + 1]) for i in range(0, len(flat), 2)]
    halfwords = [(bytes_[i] << 8) | bytes_[i + 1] for i in range(0, len(bytes_), 2)]
    return pack_u64(halfwords), pack_u64(rgba16_words(pal_rgba.reshape(16, 1, 4)))


# ---------------------------------------------------------------- display lists


def material(tex, st):
    """Display list commands setting up a borrowed material, Plateau style (fog, two cycles)."""
    lit = st["lit"]
    if st["xlu"]:
        rm, ac = "G_RM_AA_ZB_XLU_SURF2", "G_AC_NONE"
        cc = "gsDPSetCombineLERP(TEXEL0, 0, SHADE, 0, 0, 0, 0, TEXEL0, COMBINED, 0, PRIMITIVE, 0, 0, 0, 0, COMBINED)"
    elif tex and tex["alpha"]:
        rm, ac = "G_RM_AA_ZB_TEX_EDGE2", "G_AC_NONE"
        cc = "gsDPSetCombineLERP(TEXEL0, 0, SHADE, 0, 0, 0, 0, TEXEL0, COMBINED, 0, PRIMITIVE, 0, 0, 0, 0, COMBINED)"
    else:
        rm, ac = "G_RM_AA_ZB_OPA_SURF2", "G_AC_NONE"
        cc = "gsDPSetCombineLERP(TEXEL0, 0, SHADE, 0, 0, 0, 0, 1, COMBINED, 0, PRIMITIVE, 0, 0, 0, 0, 1)"
    tt = "G_TT_RGBA16" if tex and tex["fmt"] == "ci4" else "G_TT_NONE"
    geo = "G_ZBUFFER | G_SHADE | G_CULL_BACK | G_FOG | G_SHADING_SMOOTH" + (" | G_LIGHTING" if lit else "")
    g = ["gsDPPipeSync()",
         f"gsDPSetOtherMode(G_AD_NOISE | G_CD_MAGICSQ | G_CK_NONE | G_TC_FILT | G_TF_BILERP | {tt} | G_TL_TILE | "
         f"G_TD_CLAMP | G_TP_PERSP | G_CYC_2CYCLE | G_PM_NPRIMITIVE, {ac} | G_ZS_PIXEL | G_RM_FOG_SHADE_A | {rm})",
         f"gsSPLoadGeometryMode({geo})", cc, "gsDPSetPrimColor(0, 0, 255, 255, 255, 255)"]
    if tex:
        sc = st.get("scale") or (0xFFFF, 0xFFFF)
        g.append(f"gsSPTexture(0x{sc[0]:04X}, 0x{sc[1]:04X}, 0, G_TX_RENDERTILE, G_ON)")
        tile = st.get("tile") or ("G_TX_NOMIRROR | G_TX_WRAP", "G_TX_NOMIRROR | G_TX_WRAP",
                                  str(int(math.log2(tex["w"]))), str(int(math.log2(tex["h"]))), "G_TX_NOLOD", "G_TX_NOLOD")
        cms, cmt, ms, mt, ss, sh = tile
        if tex["fmt"] == "ci4":
            g.append(f"gsDPLoadTLUT_pal16(0, {tex['tlut']})")
            g.append(f"gsDPLoadTextureBlock_4b({tex['sym']}, G_IM_FMT_CI, {tex['w']}, {tex['h']}, 0, {cms}, {cmt}, "
                     f"{ms}, {mt}, {ss}, {sh})")
        else:
            g.append(f"gsDPLoadTextureBlock({tex['sym']}, G_IM_FMT_RGBA, G_IM_SIZ_16b, {tex['w']}, {tex['h']}, 0, "
                     f"{cms}, {cmt}, {ms}, {mt}, {ss}, {sh})")
    else:
        g.append("gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_OFF)")
    return g


def batches(tris):
    """Split triangles into vertex loads of at most 32 (shared vertices reused within a load)."""
    out, cur, index = [], [], {}
    faces = []
    for v in tris:
        keys = [tuple(int(round(x)) for x in row) for row in v]
        new = [k for k in dict.fromkeys(keys) if k not in index]
        if len(cur) + len(new) > 32:
            out.append((cur, faces))
            cur, index, faces = [], {}, []
            new = list(dict.fromkeys(keys))
        for k in new:
            index[k] = len(cur)
            cur.append(k)
        faces.append([index[k] for k in keys])
    if faces:
        out.append((cur, faces))
    return out


def s16(v):
    return int(max(-32768, min(32767, round(v))))


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="ntsc-1.2")
    ap.add_argument("--extracted", type=Path)
    ap.add_argument("--out", type=Path, help="folder to write to (default build/VERSION/" + INC + ")")
    ap.add_argument("--plan", type=Path, help="JSON list of buildings to use instead of BUILDINGS (tests)")
    ap.add_argument("--preview", type=Path, help="also render pictures of the town to this folder (needs node + playwright)")
    args = ap.parse_args()
    ext = args.extracted or REPO / "extracted" / args.version
    out = args.out or REPO / "build" / args.version / INC
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("ancient_town*"):
        f.unlink()

    global BUILDINGS, SCENES
    if args.plan:
        import json

        plan = json.loads(args.plan.read_text())
        BUILDINGS, SCENES = plan["buildings"], {**SCENES, **plan.get("scenes", {})}
    own_v, own_t, n_surf, n_polys = own_collision()
    fields, cols = {}, {}
    textures = Textures(out)
    room_lines, entry_lines, cvtx, cpoly, csurf = [], [], [], [], []
    groups_out = {}
    surf_map = {}
    cvtx_index = {}
    placed = 0
    preview = []
    actors = []  # actors that need the buildings (e.g. the man on a roof)
    for spec in BUILDINGS:
        if spec.get("plot") is not None:
            plot = town_plan.PLOTS[spec["plot"]]
        elif spec["at"] == "island_bridge":
            plot = None  # placed once the bridge is read (its length and direction)
        elif spec["at"] == "south_road" or spec["at"][0] == "south_road":  # across the road Link arrives on
            import make_level

            r = 2860.0 if spec["at"] == "south_road" else float(spec["at"][1])
            a = float(make_level.path_angle(0, r))
            da = float(make_level.path_angle(0, r + 10)) - a
            heading = math.atan2(math.sin(a) + r * math.cos(a) * da / 10, math.cos(a) - r * math.sin(a) * da / 10)
            plot = dict(x=r * math.sin(a), z=r * math.cos(a), face=heading + math.pi)
        elif spec["at"][0] == "street":  # across a quarter's main street, facing the plaza
            _, q, r = spec["at"]
            mid = math.pi / 4 + q * math.pi / 2
            plot = dict(x=math.sin(mid) * r, z=math.cos(mid) * r, face=mid + math.pi, quarter=q)
        else:
            x, z, yaw = spec["at"]
            plot = dict(x=x, z=z, face=yaw)
        scene = spec["scene"]
        if scene not in fields:
            src = ext / SCENES[scene]
            if not src.is_dir():
                print(f"make_town: {src} not found (run `make setup` first)")
                sys.exit(1)
            fields[scene] = Field(ext, src)
            cols[scene] = collision(fields[scene])
        field = fields[scene]
        try:
            b = Building(spec, field, cols[scene])
        except (ValueError, IndexError) as e:
            print(f"make_town: skipping {spec['name']}: {e}")
            continue
        if plot is None:
            plot, gy = fit_bridge(b, *town_plan.bridge_ends())
        else:
            ground = [ground_height(own_v, own_t, plot["x"] + dx, plot["z"] + dz)
                      for dx, dz in ((0, 0), (b.radius * 0.6, 0), (-b.radius * 0.6, 0), (0, b.radius * 0.6), (0, -b.radius * 0.6))]
            ground = [g for g in ground if g is not None]
            gy = min(ground) if ground else 0.0
        tris, colp = b.place(plot["x"], plot["z"], gy, plot["face"])

        # usage of each texture by this building, to classify it
        usage = {}
        for v, st in tris:
            if not st["tex"]:
                continue
            n = np.cross(v[1, :3] - v[0, :3], v[2, :3] - v[0, :3])
            area = np.linalg.norm(n) / 2
            ny = n[1] / (2 * area) if area > 0 else 0
            u = usage.setdefault(st["tex"], dict(floor=0.0, wall=0.0, roof=0.0))
            u["floor" if ny > 0.75 else "wall" if abs(ny) < 0.55 else "roof"] += area

        # group by material, emit
        groups = {}
        for v, st in tris:
            tex = textures.get(field, scene, st, usage.get(st["tex"], {}), spec.get("style")) if st["tex"] else None
            key = (tex["sym"] if tex else None, st["lit"], st["xlu"], st.get("tile"), st.get("scale"))
            groups.setdefault(key, (tex, st, []))[2].append(v)
        name = f"ancient_town_{placed}"
        vtx_rows, dl_opa, dl_xlu = [], [], []
        for (tsym, lit, xlu, _, _), (tex, st, vs) in groups.items():
            dl = dl_xlu if xlu else dl_opa
            dl += material(tex, st)
            for verts, faces in batches(vs):
                base = len(vtx_rows)
                vtx_rows += verts
                dl.append(f"gsSPVertex(&{name}_vtx[{base}], {len(verts)}, 0)")
                for k in range(0, len(faces) - 1, 2):
                    a, c = faces[k], faces[k + 1]
                    dl.append(f"gsSP2Triangles({a[0]}, {a[1]}, {a[2]}, 0, {c[0]}, {c[1]}, {c[2]}, 0)")
                if len(faces) % 2:
                    a = faces[-1]
                    dl.append(f"gsSP1Triangle({a[0]}, {a[1]}, {a[2]}, 0)")
        room_lines.append(f"Vtx {name}_vtx[] = {{\n" + "".join(
            f"    VTX({s16(r[0])}, {s16(r[1])}, {s16(r[2])}, {s16(r[3])}, {s16(r[4])}, 0x{int(r[5]) & 0xFF:02X}, "
            f"0x{int(r[6]) & 0xFF:02X}, 0x{int(r[7]) & 0xFF:02X}, 0x{int(r[8]) & 0xFF:02X}),\n" for r in vtx_rows) + "};\n\n")
        for suffix, dl in (("opa", dl_opa), ("xlu", dl_xlu)):
            if dl:
                room_lines.append(f"Gfx {name}_{suffix}[] = {{\n" + "".join(f"    {c},\n" for c in dl)
                                  + "    gsSPEndDisplayList(),\n};\n\n")
        # One room-shape entry per quarter of the town (and one for the rest): the room can have at most 64,
        # and Room_DrawCullable keeps the visible ones in a 64-slot buffer on the stack (src/code/z_room.c).
        group = groups_out.setdefault(plot.get("quarter", "other"), dict(pts=[], opa=[], xlu=[]))
        group["pts"].append(np.concatenate([v[:, :3] for v, _ in tris]))
        if dl_opa:
            group["opa"].append(name + "_opa")
        if dl_xlu:
            group["xlu"].append(name + "_xlu")

        # collision
        for p, surf, flags in colp:
            key = (scene, surf)
            if key not in surf_map:
                s0, s1 = cols[scene][2][surf] if surf < len(cols[scene][2]) else (None, None)
                if s0 is None:
                    continue
                s0 = ["0", "0"] + s0[2:]  # no camera or exit from the source scene
                s1 = s1[:2] + ["0"] + s1[3:]  # no light setting from the source scene
                surf_map[key] = n_surf + len(csurf)
                csurf.append(f"    {{ {{ SURFACETYPE0({', '.join(s0)}), SURFACETYPE1({', '.join(s1)}) }} }},\n")
            n = np.cross(p[1] - p[0], p[2] - p[0])
            ln = np.linalg.norm(n)
            if ln < 1e-3:
                continue
            n = n / ln
            ids = []
            for q in p:  # shared vertices: each one is stored once
                k = tuple(s16(x) for x in q)
                if k not in cvtx_index:
                    cvtx_index[k] = len(cvtx)
                    cvtx.append(q)
                ids.append(len(own_v) + cvtx_index[k])
            dist = -int(round(float(np.dot(n, p[0]))))
            fl = flags if flags.strip() not in ("", "0") else "0"
            cpoly.append(f"    {{ {surf_map[key]}, {{ COLPOLY_VTX({ids[0]}, {fl}), COLPOLY_VTX({ids[1]}, 0), {ids[2]} }}, "
                         f"{{ COLPOLY_SNORMAL({n[0]:.6f}), COLPOLY_SNORMAL({n[1]:.6f}), COLPOLY_SNORMAL({n[2]:.6f}) }}, {dist} }},\n")
        if spec.get("roof_actor") and not actors:
            roofs = [p for p, _, _ in colp if _up(p) > 0.6 and p[:, 1].mean() > gy + 150]
            if roofs:
                top = max(roofs, key=lambda p: p[:, 1].mean())
                c = top.mean(0)
                yaw = int(math.atan2(-c[0], -c[2]) / (2 * math.pi) * 0x10000) & 0xFFFF
                print(f"make_town: {spec['roof_actor']} on the roof of {spec['name']} at ({c[0]:.0f}, {c[1]:.0f}, {c[2]:.0f})")
                actors.append(f"    {{ {spec['roof_actor']}, {{ {s16(c[0])}, {s16(c[1] + 4)}, {s16(c[2])} }}, "
                              f"{{ 0, 0x{yaw:04X}, 0 }}, 0x0000 }},\n")
        preview.append(dict(name=spec["name"], tris=[(v, tex["sym"] if (tex := (textures.get(field, scene, st, usage.get(
            st["tex"], {}), spec.get("style")) if st["tex"] else None)) else None, st["lit"], st["xlu"]) for v, st in tris]))
        per_tex = {}
        for _, st in b.tris:
            per_tex[st["tex"]] = per_tex.get(st["tex"], 0) + 1
        print(f"make_town:   {spec['name']} triangles by texture: " +
              ", ".join(f"{(t or 'none').replace('_scene_', ':').replace('spot', 's')} {n}" for t, n in per_tex.items()))
        print(f"make_town: {spec['name']} ({scene}, {len(b.tris)} of {b.total} triangles, {len(b.col)} collision) on plot "
              f"({plot['x']}, {plot['z']}) at y {gy:.0f}")
        placed += 1

    if not placed:
        print("make_town: no building placed; the level keeps its plain plaza")
        sys.exit(1)
    for k, (key, g) in enumerate(groups_out.items()):
        pts = np.concatenate(g["pts"])
        c = (pts.min(0) + pts.max(0)) / 2
        rad = float(np.max(np.linalg.norm(pts - c, axis=1)))
        names = {}
        for suffix in ("opa", "xlu"):
            if g[suffix]:
                names[suffix] = f"ancient_town_group_{k}_{suffix}"
                room_lines.append(f"Gfx {names[suffix]}[] = {{\n" + "".join(f"    gsSPDisplayList({d}),\n" for d in g[suffix])
                                  + "    gsSPEndDisplayList(),\n};\n\n")
        entry_lines.append(f"    {{ {{ {s16(c[0])}, {s16(c[1])}, {s16(c[2])} }}, {int(rad) + 1}, "
                           f"{names.get('opa', 'NULL')}, {names.get('xlu', 'NULL')} }},\n")
    own_entries = (LEVEL / "ancient_room_0.c").read_text().split("RoomShapeEntries[] = {", 1)[1].split("};", 1)[0].count("{ {")
    if own_entries + len(entry_lines) > 64:
        print(f"make_town: {own_entries} + {len(entry_lines)} room entries is more than the 64 a room can have")
        sys.exit(1)

    # textures first (the display lists refer to them)
    tex_lines = []
    for t in textures.items.values():
        if t["tlut"]:
            tex_lines.append(f"u64 {t['tlut']}[] = {{\n#include \"{INC}/{t['tlut']}.inc.c\"\n}};\n\n")
        tex_lines.append(f"u64 {t['sym']}[] = {{\n#include \"{INC}/{t['sym']}.inc.c\"\n}};\n\n")
    (out / "ancient_town_room.inc.c").write_text("// Generated by tools/remix/make_town.py. Do not edit.\n"
                                                 + "".join(tex_lines) + "".join(room_lines))
    (out / "ancient_town_entries.inc.c").write_text("".join(entry_lines))
    (out / "ancient_town_col_vtx.inc.c").write_text("".join(f"    {{ {s16(q[0])}, {s16(q[1])}, {s16(q[2])} }},\n" for q in cvtx))
    (out / "ancient_town_col_polys.inc.c").write_text("".join(cpoly))
    (out / "ancient_town_col_surfaces.inc.c").write_text("".join(csurf))
    (out / "ancient_town_actors.inc.c").write_text("".join(actors))

    memsize = town_memsize(own_v, own_t, cvtx, cpoly)
    (out / "ancient_town.h").write_text(
        "// Generated by tools/remix/make_town.py from the extracted game. Do not edit.\n"
        "#ifndef ANCIENT_TOWN_H\n#define ANCIENT_TOWN_H\n\n"
        f'#define ANCIENT_TOWN_ROOM "{INC}/ancient_town_room.inc.c"\n'
        f'#define ANCIENT_TOWN_ENTRIES "{INC}/ancient_town_entries.inc.c"\n'
        f'#define ANCIENT_TOWN_COL_VTX "{INC}/ancient_town_col_vtx.inc.c"\n'
        f'#define ANCIENT_TOWN_COL_POLYS "{INC}/ancient_town_col_polys.inc.c"\n'
        f'#define ANCIENT_TOWN_COL_SURFACES "{INC}/ancient_town_col_surfaces.inc.c"\n'
        f"#define ANCIENT_TOWN_BGCHECK_MEMSIZE 0x{memsize:X}\n"
        f'#define ANCIENT_TOWN_ACTORS "{INC}/ancient_town_actors.inc.c"\n'
        f"#define ANCIENT_TOWN_ACTOR_COUNT {len(actors)}\n\n#endif\n")
    sizes = {k: len(v) for k, v in (("textures", textures.items), ("collision polys", cpoly))}
    print(f"make_town: {placed} buildings, {sizes}, collision memory 0x{memsize:X}; wrote {out}")
    for t in textures.items.values():
        print(f"make_town:   {t['src']} -> {t['sym']} ({t['cls']}, {t['fmt']} {t['w']}x{t['h']})")
    if args.preview:
        render_preview(preview, textures, args.preview)


def render_preview(buildings, textures, dest: Path):
    """Pictures of the town (map, overview, each building) with tools/remix/survey_view.html: the buildings as
    placed, with their restyled textures. Pictures only; the geometry stays in a temporary folder."""
    import base64
    import io
    import json
    import shutil
    import subprocess
    import tempfile

    from PIL import Image

    import survey_scenes

    dest.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="town-"))
    texdata = {}
    for t in textures.items.values():
        img = Image.fromarray(t["rgba"], "RGBA")
        buf = io.BytesIO()
        img.save(buf, "PNG")
        texdata[t["sym"]] = dict(fmt=t["fmt"], w=t["w"], h=t["h"],
                                 url="data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
    entries = []
    for i, b in enumerate(buildings):
        groups = {}
        for v, sym, lit, xlu in b["tris"]:
            g = groups.setdefault((sym, lit, xlu), dict(pos=[], st=[], col=[]))
            g["pos"].append(v[:, :3])
            g["st"].append(v[:, 3:5])
            g["col"].append(v[:, 5:9])
        pts = np.concatenate([v[:, :3] for v, *_ in b["tris"]])
        entries.append(dict(index=i, center=None, radius=None,
                            measure=dict(tris=len(b["tris"]), lo=pts.min(0).tolist(), hi=pts.max(0).tolist(), floor=0, wall=0, roof=0),
                            groups=[dict(tex=k[0], lit=k[1], xlu=k[2], pos=np.concatenate(g["pos"]).reshape(-1).round(1).tolist(),
                                         st=np.concatenate(g["st"]).reshape(-1).tolist(),
                                         col=np.concatenate(g["col"]).reshape(-1).astype(int).tolist()) for k, g in groups.items()]))
    (work / "town.json").write_text(json.dumps(dict(scene="town", room="town", entries=entries, textures=texdata)))
    shutil.copy(HERE / "survey_view.html", work / "index.html")
    plan = [dict(file="town.json", entry="all", mode="top", out="town-map.png"),
            dict(file="town.json", entry="all", mode="iso", out="town-overview.png")]
    plan += [dict(file="town.json", entry=i, mode="iso", out=f"town-b{i:02d}.png") for i in range(len(entries))]
    (work / "plan.json").write_text(json.dumps(plan))
    shots = work / "shots"
    shots.mkdir()
    p = subprocess.run(["node", str(HERE / "survey_render.mjs"), str(work), str(shots)], capture_output=True, text=True)
    print(p.stdout[-500:], p.stderr[-500:])
    for f in ("town-map.png", "town-overview.png"):
        if (shots / f).exists():
            shutil.copy(shots / f, dest / f)
    survey_scenes.contact_sheet([shots / f"town-b{i:02d}.png" for i in range(len(entries))],
                                [f"{b['name']}\n{len(b['tris'])} tris" for b in buildings], dest / "town-buildings.png")
    shutil.rmtree(work, ignore_errors=True)


def town_memsize(own_v, own_t, cvtx, cpoly):
    """Collision memory for the level with the town, estimated like make_level.py does for the level alone."""
    import make_level

    verts = [tuple(int(x) for x in v) for v in own_v] + [tuple(s16(x) for x in q) for q in cvtx]
    polys = [(0, t, (0, 0, 0), 0, 0) for t in own_t]
    for line in cpoly:
        ids = [int(x) for x in re.findall(r"COLPOLY_VTX\((\d+)", line)] + [int(re.search(r"\), (\d+) \}", line).group(1))]
        polys.append((0, tuple(ids), (0, 0, 0), 0, 0))
    hdr = (LEVEL / "ancient_scene.c").read_text()
    m = re.search(r"CollisionHeader ancient_sceneCollisionHeader = \{\s*\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\},\s*"
                  r"\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}", hdr)
    lo, hi = [int(m.group(i)) for i in (1, 2, 3)], [int(m.group(i)) for i in (4, 5, 6)]
    size, _ = make_level.bgcheck_memsize(verts, polys, lo, hi)
    return size


if __name__ == "__main__":
    main()
