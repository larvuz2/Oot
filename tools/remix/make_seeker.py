#!/usr/bin/env python3
"""Generate the Seeker's Shrine (Web Remix level 3): a Breath of the Wild style shrine where Link starts with
nothing but his sword and finds the tools that open the way, in chests hidden around the shrine.

On the way in the shrine takes everything else (like Eventide Island in Breath of the Wild) and gives it all back
on the way out (z_remix_level.c: RemixLevel_OnSceneStart; what is found inside stays inside, the Heart Container
at the end is kept). The trial, "The Lost Tools", only uses the game's own pieces:

  1. Empty-handed. A crystal switch sits on a pedestal out in the chasm, out of reach. Throw a pot at it: the
     fire guarding an alcove in the west wall dies down for 20 seconds. Inside: the HOVER BOOTS (and a crystal to
     get back out).
  2. The gap. The chasm's edge is a "no jumping" floor: without the boots Link just drops into the pit (stairs
     lead back up). With them he floats across to the island: the LENS OF TRUTH.
  3. The unseen. Through the Lens a zigzag bridge appears over the chasm (it is there all along, only invisible);
     and one stretch of the far wall is not a wall at all: behind it, the HOOKSHOT.
  4. The ascent. A crystal raises hookshot posts out of the ledges: pull up to the shelf, then to the balcony, then
     float across to the altar on the hover boots: the Heart Container, and the pedestal home.

Lens-only geometry and fake walls are switched by the draw config each frame (segments 0x09 and 0x0A); the circuit
lines of each tool glow once its chest is opened (segment 0x0E's table, from the chests' treasure flags).

    python3 tools/remix/make_seeker.py      # writes assets/scenes/remix/seeker/ (committed)
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_shrine as S  # noqa: E402  (the Ember Shrine's tools; pointed at this shrine below)
from make_shrine import (L, Mat, quad, strip, unit, add_col, wall, flat, box, ngon, fan, beam, floor_line,  # noqa: E402
                         wall_line, ring_line, rune_panel, eye_emblem, FLOOR, WALL, DARK, RUNES, GLOW, EMBER, EYE)

REPO = HERE.parents[1]
OUT = REPO / "assets/scenes/remix/seeker"
INC = "assets/scenes/remix/seeker"
SCENE, ROOM = "seeker_scene", "seeker_room_0"

TEXTURES = {
    "plaza": ("seeker_plaza", "ci4", (64, 64)),
    "techstone": ("seeker_techstone", "ci4", (64, 64)),
    "techrock": ("seeker_techrock", "ci4", (64, 64)),
    "runes": ("seeker_runes", "ci4", (64, 64)),
    "glow": ("seeker_glow", "i8", (32, 32)),
    "eye": ("seeker_eye", "i8", (64, 64)),
}

# Lens-only things: see-through violet (segment 0x0B), drawn only while the Lens is on (segment 0x09)
GHOST = Mat("ghost", "plaza", "ci4", (64, 64), lit=False, xlu=True, prim_seg=0x0B, repeat=300)
GHOST_LINE = Mat("ghost_line", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x0B, scroll=True, repeat=150,
                 clamp_t=True)
GHOST_EYE = Mat("ghost_eye", "eye", "i8", (64, 64), lit=False, xlu=True, prim_seg=0x0B)
# each tool's circuit lines: entries of segment 0x0E's table (dim until its chest is opened)
TOOL = [Mat(f"tool{k}", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x0E000000 + 0x18 * k, scroll=True,
            repeat=150, clamp_t=True) for k in range(3)]

SURF_FLOOR, SURF_WALL, SURF_EXIT, SURF_NOJUMP = range(4)
# 9: Link walks off edges without jumping. The player code checks the property one frame after Link leaves the
# ground, of the floor then under him: so the floors below the gaps have it too, not only the ledges.
SURFACES = [("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 0), ("SURFACE_MATERIAL_STONE", 1),
            ("SURFACE_MATERIAL_STONE", 0, "FLOOR_PROPERTY_9")]

# ---------------------------------------------------------------- the plan

HALL = dict(x0=-700, x1=700, z0=-1250, z1=1250, h=900)
CH = dict(x=0, z=1600, r=340, h=380)
CH_APO = CH["r"] * math.cos(math.pi / 8)
SPAWN = (0, 330, CH["z"])
PEDESTAL = dict(x=0, z=CH["z"] + 200, r=75, h=14)
LOW, PIT = -30, -280  # the island, the bridge and the north side are a little lower than the south hall (0)
SOUTH_Z0 = 420  # the south hall ends at the chasm here
EDGE_Z = 540  # from here to the chasm the floor is "no jumping"
NORTH_Z1 = -560  # the north side starts here
ISLAND = dict(x0=-220, x1=220, z0=40, z1=310)  # 110 from the south edge: hover boots only
CRYSTAL_PED = (430, 0, 250, 45)  # out in the chasm (x, top, z, radius), 170 from the edge: a pot throw
RAMP = dict(x0=560, x1=700, z0=-300, z1=SOUTH_Z0)  # stairs out of the pit, up to the south hall
BRIDGE = [(0, 40), (0, -90), (-280, -170), (-280, -320), (200, -400), (200, NORTH_Z1)]  # invisible, 90 wide
BRIDGE_W = 90
FIRE_ALCOVE = dict(x0=-900, z0=760, z1=960, door0=815, door1=905, door_h=160)  # in the south hall's west wall
FAKE_ALCOVE = dict(x0=-900, z0=-990, z1=-790, door0=-960, door1=-820, door_h=200)  # behind a wall that isn't
SHELF = dict(x0=200, x1=700, z0=-1250, z1=-850, top=140)  # NE shelf (170 over the north side: no climbing)
BALCONY = dict(x0=-300, x1=150, z0=-1250, z1=-1050, top=310)  # "no jumping" too
ALTAR = dict(x0=-680, x1=-410, z0=-1250, z1=-1030, top=280)  # 110 from the balcony: hover boots again
POST_A = (450, SHELF["top"], -1000)
POST_B = (40, BALCONY["top"], -1150)
POST_CRYSTAL = (330, LOW, -760)
RING = dict(x=(ALTAR["x0"] + ALTAR["x1"]) // 2, y=ALTAR["top"] + 300, z=-1140, r=110)
FLAG_FIRE, FLAG_POSTS = 1, 3
T_HOVER, T_LENS, T_HOOK, T_HEART = 1, 2, 3, 4  # chests' treasure flags


def configure():
    """Point the Plateau's and the Ember Shrine's tools at this shrine."""
    L.OUT, L.INC, L.SCENE, L.ROOM = OUT, INC, SCENE, ROOM
    L.TEXTURES = TEXTURES
    L.ENTRIES.clear()
    L.COL_TRIS.clear()
    L.MESHES.clear()
    for k, v in dict(OUT=OUT, INC=INC, SCENE=SCENE, ROOM=ROOM, NAME="Seeker's Shrine", TITLE_STEM="seeker_title",
                     TITLE_SYM="gSeekerShrineTitleCardTex", MEMSIZE_MACRO="SEEKER_SCENE_BGCHECK_MEMSIZE",
                     MUSIC="NA_BGM_SPIRIT_TEMPLE", SURFACES=SURFACES, EXITS=["ENTR_RETURN_GROTTO"], SPAWN=SPAWN,
                     HALL=HALL, CH=CH, CH_APO=CH_APO, PEDESTAL=PEDESTAL, OBJECTS=OBJECTS, actors=actors,
                     room_defines=room_defines).items():
        setattr(S, k, v)


# ---------------------------------------------------------------- the shrine


def hall_walls(e):
    """Walls all around, from the pit's floor to the ceiling, with the two alcoves' doorways in the west wall."""
    x0, x1, z0, z1, h = HALL["x0"], HALL["x1"], HALL["z0"], HALL["z1"], HALL["h"]
    wall(e, WALL, (x1, z1), (x1, z0), PIT, h, (-1, 0, 0), u0=z0)
    wall(e, WALL, (x0, z0), (x1, z0), PIT, h, (0, 0, 1))
    wall(e, WALL, (x1, z1), (S.ARCH_HALF, z1), 0, h, (0, 0, -1))
    wall(e, WALL, (-S.ARCH_HALF, z1), (x0, z1), 0, h, (0, 0, -1))
    wall(e, WALL, (S.ARCH_HALF, z1), (-S.ARCH_HALF, z1), S.ARCH_H, h, (0, 0, -1))
    # west wall: solid, but for the fire alcove's doorway and the fake wall (drawn by build_lens(), no collision)
    fa, fk = FIRE_ALCOVE, FAKE_ALCOVE
    cuts = sorted([(fk["door0"], fk["door1"], LOW, LOW + fk["door_h"]), (fa["door0"], fa["door1"], 0, fa["door_h"])])
    z = z0
    for c0, c1, y0, y1 in cuts:
        wall(e, WALL, (x0, z), (x0, c0), PIT, h, (1, 0, 0), u0=z)
        wall(e, WALL, (x0, c0), (x0, c1), y1, h, (1, 0, 0), u0=c0)
        wall(e, WALL, (x0, c0), (x0, c1), PIT, y0, (1, 0, 0), u0=c0)
        z = c1
    wall(e, WALL, (x0, z), (x0, z1), PIT, h, (1, 0, 0), u0=z)
    for x, facing in ((x0, (1, 0, 0)), (x1, (-1, 0, 0))):
        for zz in np.arange(z0 + 160, z1 - 60, 320):
            if not any(c0 - 40 < zz < c1 + 40 for c0, c1, _, _ in cuts) or x == x1:
                wall_line(e, GLOW, [(x, 220, zz), (x, h - 80, zz)], facing)
        wall_line(e, GLOW, [(x, 560, z0), (x, 560, z1)], facing)


def alcove(e, a, floor_y, fake=False):
    """A small room behind the west wall: floor, walls, ceiling."""
    x0, x1, z0, z1, h = a["x0"], HALL["x0"], a["z0"], a["z1"], floor_y + a["door_h"] + 60
    flat(e, FLOOR, x0, x1, z0, z1, floor_y)
    wall(e, WALL, (x0, z1), (x0, z0), floor_y, h, (1, 0, 0))
    wall(e, WALL, (x0, z0), (x1, z0), floor_y, h, (0, 0, 1))
    wall(e, WALL, (x1, z1), (x0, z1), floor_y, h, (0, 0, -1))
    flat(e, DARK, x0, x1, z0, z1, h, up=False, col=None)
    rune_panel(e, (x0, floor_y + 110, (z0 + z1) / 2), (1, 0, 0), 90, 90)


def build_south(e):
    """The south hall: the fire alcove, the chasm's edge (no jumping), pots to throw."""
    x0, x1 = HALL["x0"], HALL["x1"]
    flat(e, FLOOR, x0, x1, EDGE_Z, HALL["z1"], 0)
    flat(e, FLOOR, x0, RAMP["x0"], SOUTH_Z0, EDGE_Z, 0, col=SURF_NOJUMP)
    flat(e, FLOOR, RAMP["x0"], x1, RAMP["z1"], EDGE_Z, 0, col=SURF_NOJUMP)
    wall(e, WALL, (RAMP["x0"], SOUTH_Z0), (x0, SOUTH_Z0), PIT, 0, (0, 0, -1))  # the chasm's south face
    floor_line(e, EMBER, [(x0 + 10, SOUTH_Z0 + 12), (RAMP["x0"] - 10, SOUTH_Z0 + 12)], width=10)  # the edge, in orange
    alcove(e, FIRE_ALCOVE, 0)
    # tool 1's line: from the alcove's doorway to the edge
    zc = (FIRE_ALCOVE["door0"] + FIRE_ALCOVE["door1"]) / 2
    floor_line(e, TOOL[0], [(x0 - 120, zc), (x0 + 60, zc), (-200, 620), (0, SOUTH_Z0 + 40)])
    ring_line(e, TOOL[0], -820, zc, 50, 0, n=12, width=8)


def build_pit(e):
    """The chasm: its floor, the stairs back up, the crystal's pedestal, the island and the north side's faces."""
    x0, x1 = HALL["x0"], HALL["x1"]
    # (also "no jumping": the player code reads the property of the floor under Link a frame after he steps off an
    # edge, which by then is the floor far below it)
    flat(e, DARK, x0, x1, NORTH_Z1, SOUTH_Z0, PIT, col=SURF_NOJUMP)
    for z in np.arange(NORTH_Z1 + 120, SOUTH_Z0, 240):
        floor_line(e, GLOW, [(x0 + 40, z), (RAMP["x0"] - 40, z)], width=10, y=PIT)
    r = RAMP  # stairs as a ramp (Link walks up slopes this gentle)
    p = [(r["x0"], PIT, r["z0"]), (r["x1"], PIT, r["z0"]), (r["x1"], 0, r["z1"]), (r["x0"], 0, r["z1"])]
    up = unit(np.cross(np.subtract(p[1], p[0]), np.subtract(p[3], p[0])))
    up = up if up[1] > 0 else -up
    quad(e, FLOOR, p, [L.planar_uv(FLOOR, q) for q in p], [tuple(up)] * 4, up, SURF_FLOOR)
    side = [np.array([r["x0"], PIT, r["z0"]]), np.array([r["x0"], PIT, r["z1"]]), np.array([r["x0"], 0, r["z1"]])]
    t = S.facing_tri(*side, (-1, 0, 0))
    e.tri(WALL, [L.V(q, (q[2] * 64 / 240, -q[1] * 64 / 240), (-1, 0, 0)) for q in t])
    add_col(*t, SURF_WALL)
    floor_line(e, GLOW, [(r["x0"] + 20, r["z0"] + 10), (r["x0"] + 20, r["z1"] - 10)], width=8, y=0)
    # the crystal's pedestal
    cx, top, cz, cr = CRYSTAL_PED
    L.prism(e, WALL, cr, cr, PIT, top, 12, cap=True, cap_mat=DARK, col=SURF_WALL, center=(cx, cz))
    ring_line(e, GLOW, cx, cz, cr - 8, top, n=12, width=8)
    # the island (its top: build_middle) and the north side's face
    i = ISLAND
    box(e, i["x0"], i["x1"], PIT, LOW, i["z0"], i["z1"], top=FLOOR)
    wall(e, WALL, (x0, NORTH_Z1), (x1, NORTH_Z1), PIT, LOW, (0, 0, 1))


def build_middle(e):
    """The island's circuit (tool 2's line runs from its chest to the bridge's start)."""
    i = ISLAND
    ring_line(e, TOOL[1], 0, 150, 55, LOW, n=14, width=8)
    floor_line(e, TOOL[1], [(0, 95), (0, i["z0"] + 6)], width=10, y=LOW)
    floor_line(e, EMBER, [(i["x0"] + 10, i["z1"] - 10), (i["x1"] - 10, i["z1"] - 10)], width=8, y=LOW)


def build_north(e):
    """The north side: the shelf and the balcony (hookshot), the altar (hover boots again), the fake wall's alcove."""
    x0, x1, z0 = HALL["x0"], HALL["x1"], HALL["z0"]
    flat(e, FLOOR, x0, x1, z0, NORTH_Z1, LOW, col=SURF_NOJUMP)  # under the balcony's gap too (see build_pit)
    alcove(e, FAKE_ALCOVE, LOW)
    s, b, a = SHELF, BALCONY, ALTAR
    box(e, s["x0"], s["x1"], LOW, s["top"], s["z0"], s["z1"], skip=("e", "n"))
    box(e, b["x0"], b["x1"], LOW, b["top"], b["z0"], b["z1"], skip=("n",), col_top=SURF_NOJUMP)
    box(e, a["x0"], a["x1"], LOW, a["top"], a["z0"], a["z1"], skip=("w", "n"))
    floor_line(e, EMBER, [(b["x0"] + 10, b["z1"] - 10), (b["x0"] + 10, b["z0"] + 10)], width=8, y=b["top"])
    # tool 3's line: out of the fake alcove (it runs into the "wall": a hint), past the crystal, up the shelf
    zc = (FAKE_ALCOVE["door0"] + FAKE_ALCOVE["door1"]) / 2
    floor_line(e, TOOL[2], [(x0 - 120, zc), (x0 + 80, zc), (POST_CRYSTAL[0] - 60, POST_CRYSTAL[2]),
                            (POST_A[0], s["z1"] + 10)], y=LOW)
    ring_line(e, TOOL[2], POST_CRYSTAL[0], POST_CRYSTAL[2], 55, LOW, n=12, width=8)
    wall_line(e, TOOL[2], [(POST_A[0], LOW, s["z1"]), (POST_A[0], s["top"], s["z1"])], (0, 0, 1))
    # the altar: eye over it, its ring of light
    eye_emblem(e, EYE, ((a["x0"] + a["x1"]) / 2, a["top"] + 230, z0), (0, 0, 1), 220)
    ring_line(e, GLOW, RING["x"], -1140, 80, a["top"], n=16, width=10)
    for x in (-420, 0, 420):
        wall_line(e, GLOW, [(x, 0, z0), (x, HALL["h"] - 80, z0)], (0, 0, 1))


def build_lens():
    """What the Lens shows (the bridge) and what it takes away (the fake wall): shared models drawn through the
    draw config's switches, with room entries of their own."""
    reveal = L.new_mesh("reveal")  # drawn while the Lens is on (segment 0x09)
    hw = BRIDGE_W / 2
    for (ax, az), (bx, bz) in zip(BRIDGE[:-1], BRIDGE[1:]):
        d = unit(np.array([bx - ax, 0, bz - az]))
        n = np.array([-d[2], 0, d[0]])
        a, b = np.array([ax, 0, az]) - d * hw, np.array([bx, 0, bz]) + d * hw
        corners = [a - n * hw, b - n * hw, b + n * hw, a + n * hw]
        top = [(c[0], LOW, c[2]) for c in corners]
        quad(reveal, GHOST, top, [L.planar_uv(GHOST, q) for q in top], [(255, 255, 255, 255)] * 4, (0, 1, 0),
             SURF_FLOOR)
        for i in range(4):  # the slab's sides (collision too: Link can't walk off without falling)
            p, q = corners[i], corners[(i + 1) % 4]
            out = unit((p + q) / 2 - (a + b) / 2)
            add_col((p[0], LOW - 30, p[2]), (q[0], LOW - 30, q[2]), (q[0], LOW, q[2]), SURF_WALL, facing=out)
            add_col((p[0], LOW - 30, p[2]), (q[0], LOW, q[2]), (p[0], LOW, p[2]), SURF_WALL, facing=out)
        for s_ in (-1, 1):
            strip(reveal, GHOST_LINE, [tuple(a + n * s_ * (hw - 8) + [0, LOW, 0]), tuple(b + n * s_ * (hw - 8) + [0, LOW, 0])],
                  [(0, 1, 0)] * 2, 10, lift=1.5)
    zc = (FAKE_ALCOVE["door0"] + FAKE_ALCOVE["door1"]) / 2
    eye_emblem(reveal, GHOST_EYE, (HALL["x0"], LOW + FAKE_ALCOVE["door_h"] + 90, zc), (1, 0, 0), 120)

    fake = L.new_mesh("fake")  # drawn while the Lens is off (segment 0x0A): no collision
    fa = FAKE_ALCOVE
    p = [(HALL["x0"], LOW, fa["door0"]), (HALL["x0"], LOW, fa["door1"]), (HALL["x0"], LOW + fa["door_h"], fa["door1"]),
         (HALL["x0"], LOW + fa["door_h"], fa["door0"])]
    su, sv = L.tex_scale(WALL)
    quad(fake, WALL, p, [(q[2] * su, -q[1] * sv) for q in p], [(1, 0, 0)] * 4, (1, 0, 0))

    def sphere(mesh):
        pts = np.array(mesh.positions())
        c = (pts.min(0) + pts.max(0)) / 2
        return tuple(int(round(v)) for v in c), int(math.ceil(np.max(np.linalg.norm(pts - c, axis=1)))) + 8

    rc, rr = sphere(reveal)
    fc, fr = sphere(fake)
    S.EXTRA_ROOM_C = [
        f"// What the Lens of Truth shows (segment 0x09) and takes away (0x0A): z_remix_level.c switches them\n"
        f"Gfx {ROOM}DL_reveal_call[] = {{\n    gsSPDisplayList(0x09000000),\n    gsSPEndDisplayList(),\n}};\n",
        f"Gfx {ROOM}DL_fake_call[] = {{\n    gsSPDisplayList(0x0A000000),\n    gsSPEndDisplayList(),\n}};\n",
    ]
    S.EXTRA_ENTRIES = [(rc, rr, "NULL", f"{ROOM}DL_reveal_call"), (fc, fr, f"{ROOM}DL_fake_call", "NULL")]


def build_ceiling():
    e = L.new_entry("ceiling")
    x0, x1, z0, z1, h = HALL["x0"], HALL["x1"], HALL["z0"], HALL["z1"], HALL["h"]
    flat(e, DARK, x0, x1, z0, z1, h, up=False, col=None)
    for x in (-350, 0, 350):
        strip(e, GLOW, [(x, h, z0), (x, h, z1)], [(0, -1, 0)] * 2, 16, lift=1.2)
    for z in (-900, -300, 300, 900):
        strip(e, GLOW, [(x0, h, z), (x1, h, z)], [(0, -1, 0)] * 2, 16, lift=1.2)


def build_ring():
    e = L.new_entry("ring", matrix_seg=0x0F, sphere=((RING["x"], RING["y"], RING["z"]), RING["r"] + 40))
    r, n = RING["r"], 16
    outer, inner = ngon(0, 0, r, n, 0), ngon(0, 0, r - 22, n, 0)
    for k in range(n):
        k2 = (k + 1) % n
        p = [outer[k], outer[k2], inner[k2], inner[k]]
        for f in ((0, -1, 0), (0, 1, 0)):
            quad(e, RUNES, p, [(0, 0), (64, 0), (64, 20), (0, 20)], [(160, 120, 255, 255)] * 4, f)
    strip(e, GLOW, [tuple(p) for p in ngon(0, 0, r + 6, 24, 0)], [(0, -1, 0)] * 24, 10, lift=1.0, closed=True)


# ---------------------------------------------------------------- actors


def actors():
    a = []
    cz = CH["z"]
    a.append(("ACTOR_EN_COW", -CH_APO + 105, 0, cz, 0, 0x4000, 0, "0"))  # the cow grotto's cow again
    for sx in (-1, 1):
        a.append(("ACTOR_OBJ_SYOKUDAI", sx * 170, 0, cz - CH_APO + 70, 0, 0, 0, "0x0400"))
    # 1. pots to throw at the crystal out in the chasm (it can be locked on to), the fire in the alcove's doorway
    for k, (x, z) in enumerate([(250, 600), (330, 640), (420, 610), (510, 650), (300, 760), (470, 780)]):
        a.append(("ACTOR_OBJ_TSUBO", x, 0, z, 0, 0, 0, "ITEM00_RECOVERY_HEART" if k % 3 == 0 else "0x3F"))
    cx, top, cz_, _ = CRYSTAL_PED
    a.append(("ACTOR_OBJ_SWITCH", cx, top, cz_, 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_CRYSTAL_TARGETABLE, OBJSWITCH_SUBTYPE_SYNC, {FLAG_FIRE})"))
    fa = FIRE_ALCOVE
    zc = (fa["door0"] + fa["door1"]) // 2
    a.append(("ACTOR_BG_HIDAN_CURTAIN", HALL["x0"] + 6, 0, zc, 0, 0, 0, f"(2 << 12) | (0x1E << 6) | {FLAG_FIRE}"))
    a.append(("ACTOR_OBJ_SWITCH", fa["x0"] + 40, 0, fa["z0"] + 40, 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_CRYSTAL, OBJSWITCH_SUBTYPE_SYNC, {FLAG_FIRE})"))  # to get back out
    a.append(("ACTOR_EN_BOX", -820, 0, zc, 0, 0x4000, 0, f"(ENBOX_TYPE_BIG_DEFAULT << 12) | (GI_BOOTS_HOVER << 5) | {T_HOVER}"))
    # 2. the island: the Lens, magic for it
    a.append(("ACTOR_EN_BOX", 0, LOW, 150, 0, 0, 0, f"(ENBOX_TYPE_BIG_DEFAULT << 12) | (GI_LENS_OF_TRUTH << 5) | {T_LENS}"))
    for x in (-150, 150):
        a.append(("ACTOR_OBJ_TSUBO", x, LOW, 230, 0, 0, 0, "ITEM00_MAGIC_LARGE"))
    # 3. behind the fake wall: the Hookshot; magic pots at the bridge's end
    fk = FAKE_ALCOVE
    a.append(("ACTOR_EN_BOX", -820, LOW, (fk["door0"] + fk["door1"]) // 2, 0, 0x4000, 0,
              f"(ENBOX_TYPE_BIG_DEFAULT << 12) | (GI_HOOKSHOT << 5) | {T_HOOK}"))
    for x in (110, 290):
        a.append(("ACTOR_OBJ_TSUBO", x, LOW, NORTH_Z1 - 70, 0, 0, 0, "ITEM00_MAGIC_SMALL"))
    # 4. the crystal raising the hookshot posts out of the shelf and the balcony; the altar
    a.append(("ACTOR_OBJ_SWITCH", *POST_CRYSTAL, 0, 0, 0,
              f"OBJSWITCH_PARAMS(OBJSWITCH_TYPE_CRYSTAL, OBJSWITCH_SUBTYPE_ONCE, {FLAG_POSTS})"))
    for x, y, z in (POST_A, POST_B):
        a.append(("ACTOR_OBJ_HSBLOCK", x, y, z, 0, 0, 0, f"({FLAG_POSTS} << 8) | 1"))
    al = ALTAR
    a.append(("ACTOR_EN_BOX", al["x0"] + 150, al["top"], -1150, 0, 0x4000, 0,
              f"(ENBOX_TYPE_BIG_DEFAULT << 12) | (GI_HEART_CONTAINER << 5) | {T_HEART}"))
    for z in (al["z1"] - 30, al["z0"] + 30):
        a.append(("ACTOR_OBJ_SYOKUDAI", al["x1"] - 30, al["top"], z, 0, 0, 0, "0x0400"))
    for x in (-500, 0, 500):
        a.append(("ACTOR_OBJ_SYOKUDAI", x, LOW, NORTH_Z1 - 30, 0, 0, 0, "0x0400"))
    return a


OBJECTS = ["OBJECT_SYOKUDAI", "OBJECT_COW", "OBJECT_BOX", "OBJECT_D_HSBLOCK"]


def room_defines():
    return ("// The chests' treasure flags: each tool's circuit lines glow once it is found (z_remix_level.c)\n"
            f"#define SEEKER_TREASURE_HOVER {T_HOVER}\n#define SEEKER_TREASURE_LENS {T_LENS}\n"
            f"#define SEEKER_TREASURE_HOOK {T_HOOK}\n"
            "// The rune ring over the altar\n"
            f"#define SEEKER_RING_X {RING['x']}\n#define SEEKER_RING_Y {RING['y']}\n#define SEEKER_RING_Z {RING['z']}\n"
            "// Room entries that call the Lens's switches (segments 0x09 and 0x0A)\n"
            f"extern Gfx {ROOM}DL_reveal_call[];\nextern Gfx {ROOM}DL_fake_call[];\n\n")


def check_reach():
    """The hookshot (260 long, from about 50 above Link's feet) reaches each post from where Link stands; the hover
    gaps are what the boots cross (19 frames at up to 5.5 a frame, then falling 30) and no jump can."""
    reach = 245
    for stand, post in (((POST_A[0], LOW, SHELF["z1"] + 50), POST_A), ((SHELF["x0"] + 40, SHELF["top"], POST_B[2]), POST_B)):
        d = math.dist((stand[0], stand[1] + 50, stand[2]), (post[0], post[1] + 20, post[2]))
        assert d <= reach, f"hookshot post at {post} is {d:.0f} from {stand}"
    for gap in (SOUTH_Z0 - ISLAND["z1"], BALCONY["x0"] - ALTAR["x1"]):
        assert 90 <= gap <= 115, gap
    assert ISLAND["z0"] - BRIDGE[0][1] == 0 and BRIDGE[-1][1] == NORTH_Z1
    assert SHELF["top"] - LOW > 140 and BALCONY["top"] - SHELF["top"] > 140  # (Link climbs 111 at most)
    print("make_seeker: hookshot reaches and hover gaps checked")


def main():
    configure()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    L.make_textures()
    (OUT / "ancient_title.ia8.png").unlink(missing_ok=True)
    S.title_card("Seeker's Shrine")
    S.build_chamber()
    hall = L.new_entry("south")
    hall_walls(hall)
    build_south(hall)
    build_pit(L.new_entry("pit"))
    build_middle(L.new_entry("middle"))
    build_north(L.new_entry("north"))
    build_ceiling()
    build_ring()
    build_lens()
    check_reach()
    npolys, nverts, entries, acts = S.write_sources()
    tris = sum(len(t) for e in L.ENTRIES + L.MESHES for t in e.groups.values())
    print(f"Seeker's Shrine: {len(entries)} room chunks, {tris} triangles, {npolys} collision polys ({nverts} vertices), "
          f"{len(acts)} actors")
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file"] + [str(p) for p in OUT.glob("*.[ch]")], cwd=REPO, check=True)


if __name__ == "__main__":
    main()
