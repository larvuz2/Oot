#!/usr/bin/env python3
"""Generate the Ancient Plateau: a brand-new Ocarina of Time level for the Web Remix.

An ancient-technology biome (stone that merges with glowing Sheikah machinery):

  - a rolling field with dirt paths, ringed by a wall of mountains,
  - a raised circular plaza with glowing circuit lines and Sheikah eye emblems,
  - the Ancient Spire in the middle: a stepped pedestal, an engraved obelisk with rune panels and
    glowing slits, a floating ring that spins around a hovering crystal, and orbiting rock shards,
  - tech-rock monoliths, broken pillars and boulders, plus actors from the game (torches, Armos
    guardians, Beamos, Gossip Stones, trees, bushes, rocks, butterflies).

It is built the way the game's own levels are: one room drawn as up to 64 cullable chunks, lit
terrain that follows the time of day, 2-cycle fogged materials, CI4/RGBA16 textures, collision with
surface sounds, and animated parts driven by the scene's draw config through segments 8-0xD (see
src/code/z_remix_level.c).

Everything here is original (textures from GPT Image in tools/remix/biome_art/ancient/), so the output
is committed: assets/scenes/remix/ancient/. Run it again after changing this script:

    python3 tools/remix/make_level.py
"""

from __future__ import annotations

import math
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import town_plan  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
ART = REPO / "tools/remix/biome_art/ancient"
OUT = REPO / "assets/scenes/remix/ancient"
INC = "assets/scenes/remix/ancient"
SCENE = "ancient_scene"
ROOM = "ancient_room_0"

PLAZA_Y = 30  # plaza top
RING_Y = 1330  # height of the floating ring and crystal (z_remix_level.c reads it from the room header)
_SPAWN_R = 3300
_SPAWN_A = 0.13 * math.sin(_SPAWN_R / 650.0)  # on the south path (see path_angle)
SPAWN = (round(_SPAWN_R * math.sin(_SPAWN_A)), round(_SPAWN_R * math.cos(_SPAWN_A)))  # Link starts here, facing the Spire
SPAWN_YAW = int(math.atan2(-SPAWN[0], -SPAWN[1]) / (2 * math.pi) * 0x10000) & 0xFFFF

rng = np.random.default_rng(1998)


# ---------------------------------------------------------------- noise


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


class Perlin:
    def __init__(self, seed):
        r = np.random.default_rng(seed)
        p = r.permutation(256)
        self.p = np.concatenate([p, p])
        a = r.random(256) * 2 * np.pi
        self.g = np.stack([np.cos(a), np.sin(a)], 1)

    def __call__(self, x, z):
        x = np.asarray(x, float)
        z = np.asarray(z, float)
        xi = np.floor(x).astype(int)
        zi = np.floor(z).astype(int)
        xf, zf = x - xi, z - zi

        def grad(ix, iz, dx, dz):
            g = self.g[self.p[self.p[ix & 255] + (iz & 255)]]
            return g[..., 0] * dx + g[..., 1] * dz

        u, v = _fade(xf), _fade(zf)
        n00 = grad(xi, zi, xf, zf)
        n10 = grad(xi + 1, zi, xf - 1, zf)
        n01 = grad(xi, zi + 1, xf, zf - 1)
        n11 = grad(xi + 1, zi + 1, xf - 1, zf - 1)
        return (n00 + (n10 - n00) * u) * (1 - v) + (n01 + (n11 - n01) * u) * v


N1, N2, N3 = Perlin(11), Perlin(23), Perlin(37)


def fbm(n, x, z, octaves):
    s, a, f, norm = 0.0, 1.0, 1.0, 0.0
    for _ in range(octaves):
        s = s + a * n(x * f, z * f)
        norm += a
        a *= 0.5
        f *= 2.0
    return s / norm


def ridged(n, x, z, octaves):
    s, a, f, norm = 0.0, 1.0, 1.0, 0.0
    for _ in range(octaves):
        r = 1.0 - np.abs(n(x * f, z * f)) * 1.6
        s = s + a * np.clip(r, 0, 1) ** 2
        norm += a
        a *= 0.5
        f *= 2.1
    return s / norm


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- layout

PATH_ANGLES = [0.0, math.pi / 2, math.pi, 3 * math.pi / 2]  # +z (south), +x, -z, -x


def path_angle(k, r):
    return PATH_ANGLES[k] + 0.13 * np.sin(np.asarray(r) / 650.0 + 1.7 * k)


PATH_HALF_WIDTH = 112
_paths_poly = None


def paths_polygon():
    global _paths_poly
    if _paths_poly is None:
        from shapely.geometry import LineString
        from shapely.ops import unary_union

        lines = []
        for k in range(4):
            r_end = min(3600.0, float(mountain_start(PATH_ANGLES[k])) - 120)
            rs = np.arange(985, r_end, 70.0)
            a = path_angle(k, rs)
            lines.append(LineString(np.stack([rs * np.sin(a), rs * np.cos(a)], 1)).buffer(
                PATH_HALF_WIDTH, cap_style="round", join_style="round", quad_segs=3))
        # the town's ring road and lanes (tools/remix/town_plan.py)
        for line in town_plan.lanes() + [town_plan.ring_road()]:
            lines.append(LineString(line).buffer(town_plan.LANE_HALF, cap_style="round", join_style="round", quad_segs=3))
        _paths_poly = unary_union(lines).simplify(12, preserve_topology=True)
    return _paths_poly


TOWN_GROUND_R = 3020  # inside this (wavy) circle the ground is the town's (TOWN_GROUND), outside the field's grass
_town_poly = None


def town_polygon():
    global _town_poly
    if _town_poly is None:
        from shapely.geometry import Polygon

        pts = []
        for k in range(24):
            a = 2 * math.pi * k / 24
            r = TOWN_GROUND_R + 70 * math.sin(5 * a + 0.7)
            pts.append((math.sin(a) * r, math.cos(a) * r))
        _town_poly = Polygon(pts)
    return _town_poly


_town_streets = None


def street_dist(x, z):
    """Distance from (x, z) to the town's ring road and lanes."""
    global _town_streets
    if _town_streets is None:
        from shapely.geometry import LineString
        from shapely.ops import unary_union

        _town_streets = unary_union([LineString(line) for line in town_plan.lanes() + [town_plan.ring_road()]])
    from shapely.geometry import Point

    return max(0.0, _town_streets.distance(Point(float(x), float(z))) - town_plan.LANE_HALF)


def path_dist(x, z):
    """Approximate distance from (x, z) to the nearest of the four dirt paths."""
    x = np.asarray(x, float)
    z = np.asarray(z, float)
    r = np.hypot(x, z)
    phi = np.arctan2(x, z)
    d = np.full(r.shape, 1e9)
    for k in range(4):
        dphi = np.angle(np.exp(1j * (phi - path_angle(k, r))))
        d = np.minimum(d, r * np.abs(dphi))
    return np.where((r > 900) & (r < 3600), d, 1e9)


def height(x, z):
    x = np.asarray(x, float)
    z = np.asarray(z, float)
    r = np.hypot(x, z)
    hills = 75 * fbm(N1, x / 1500, z / 1500, 4) + 30 * fbm(N2, x / 520 + 11, z / 520 + 7, 2)
    # the town (tools/remix/town_plan.py) sits on gentle terraces: most of the hills are smoothed away there
    t0, t1 = town_plan.TOWN_FLAT_R
    town = smoothstep(t0 - 150, t0 + 100, r) * (1 - smoothstep(t1 - 100, t1 + 200, r))
    hills = hills * (1 - 0.8 * town)
    h = hills * smoothstep(1050, 1800, r)
    h = h + 170 * smoothstep(1800, 3700, r)
    pf = (1 - smoothstep(100, 280, path_dist(x, z))) * smoothstep(950, 1300, r)
    h = h - pf * 0.55 * np.maximum(hills, 0) * smoothstep(1050, 1800, r) - pf * 6
    r0 = mountain_start(np.arctan2(x, z))
    h = h + smoothstep(r0 - 900, r0, r) * 150 * np.maximum(fbm(N1, x / 700 + 3, z / 700 - 5, 3), -0.2)
    m = smoothstep(r0, r0 + 2500, r)
    peaks = 1150 + 2500 * ridged(N3, x / 2700, z / 2700, 4) ** 1.4
    h = h + m**1.6 * peaks + m * 420 * fbm(N2, x / 650, z / 650, 3)
    return h


def mountain_start(phi):
    phi = np.asarray(phi, float)
    return 3550 + 430 * fbm(N2, np.cos(phi) * 1.4 + 20, np.sin(phi) * 1.4 + 20, 3)


def normal_at(x, z, e=20.0):
    dx = (height(x + e, z) - height(x - e, z)) / (2 * e)
    dz = (height(x, z + e) - height(x, z - e)) / (2 * e)
    n = np.stack([-dx, np.ones_like(dx), -dz], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


# ---------------------------------------------------------------- materials


class Mat:
    def __init__(self, name, tex=None, fmt=None, size=(32, 32), lit=True, xlu=False, prim=(255, 255, 255, 255),
                 prim_seg=None, scroll=False, repeat=200.0, clamp_t=False, combine=None):
        self.combine = combine
        self.name, self.tex, self.fmt, self.size = name, tex, fmt, size
        self.lit, self.xlu, self.prim, self.prim_seg = lit, xlu, prim, prim_seg
        self.scroll, self.repeat, self.clamp_t = scroll, repeat, clamp_t


GRASS = Mat("grass", "grass", "rgba16", (32, 32), repeat=150)
DIRT = Mat("dirt", "dirt", "rgba16", (32, 32), repeat=150)
TOWN_GROUND = Mat("town_ground", "town_ground", "rgba16", (32, 32), repeat=170)
ROCK = Mat("rock", "rock", "rgba16", (32, 32), repeat=330)
PLAZA = Mat("plaza", "plaza", "ci4", (64, 64), repeat=380)
TECH = Mat("tech", "techstone", "ci4", (64, 64), repeat=200)
TECHROCK = Mat("techrock", "techrock", "ci4", (64, 64), repeat=240)
RUNES = Mat("runes", "runes", "ci4", (64, 64), lit=False)
CRYSTAL = Mat("crystal", None, lit=False)
GLOW_CYAN = Mat("glow_cyan", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x08, scroll=True, repeat=150,
                clamp_t=True)
GLOW_ORANGE = Mat("glow_orange", "glow", "i8", (32, 32), lit=False, xlu=True, prim_seg=0x0C, scroll=True,
                  repeat=150, clamp_t=True)
EYE = Mat("eye", "eye", "i8", (64, 64), lit=False, xlu=True, prim_seg=0x0C)
EYE_CYAN = Mat("eye_cyan", "eye", "i8", (64, 64), lit=False, xlu=True, prim_seg=0x08)
# Zora's River's water when the ROM's assets are there (else a look-alike), scrolled by segment 0x0E
WATER = Mat("water", "water", "rgba16", (32, 32), lit=False, xlu=True, prim=(255, 255, 255, 170), scroll=0x0E, repeat=160,
            combine="water")

# Textures that come from Hyrule Field itself when the ROM's assets are there (tools/remix/link_level_assets.py
# writes ancient_hf.h at build time); the files here are look-alike fallbacks for builds without a ROM.
HF_TEXTURES = {"grass": "ANCIENT_HF_GRASS", "dirt": "ANCIENT_HF_DIRT", "rock": "ANCIENT_HF_ROCK",
               "town_ground": "ANCIENT_TOWN_GROUND", "water": "ANCIENT_ZORA_WATER"}

TEXTURES = {  # key: (file stem, format, size)
    "grass": ("ancient_grass", "rgba16", (32, 32)),
    "dirt": ("ancient_dirt", "rgba16", (32, 32)),
    "town_ground": ("ancient_town_ground", "rgba16", (32, 32)),
    "water": ("ancient_water", "rgba16", (32, 32)),
    "rock": ("ancient_rock", "rgba16", (32, 32)),
    "plaza": ("ancient_plaza", "ci4", (64, 64)),
    "techstone": ("ancient_techstone", "ci4", (64, 64)),
    "techrock": ("ancient_techrock", "ci4", (64, 64)),
    "runes": ("ancient_runes", "ci4", (64, 64)),
    "glow": ("ancient_glow", "i8", (32, 32)),
    "eye": ("ancient_eye", "i8", (64, 64)),
}

# Surface types (collision): index -> (material, canHookshot, isHorseBlocked)
SURF_GRASS, SURF_DIRT, SURF_STONE, SURF_TECH, SURF_WALL = range(5)
SURFACES = [
    ("SURFACE_MATERIAL_GRASS", 0, 0),
    ("SURFACE_MATERIAL_DIRT", 0, 0),
    ("SURFACE_MATERIAL_STONE", 0, 0),
    ("SURFACE_MATERIAL_STONE", 1, 0),
    ("SURFACE_MATERIAL_STONE", 0, 1),
]


# ---------------------------------------------------------------- geometry containers


class Entry:
    """One cullable room-shape entry: an opaque and a translucent display list."""

    def __init__(self, name, matrix_seg=None, sphere=None):
        self.name = name
        self.matrix_seg = matrix_seg
        self.sphere = sphere  # (center, radius) override, for animated parts
        self.groups = {}  # Mat -> list of triangles; triangle = 3 vertices (pos, uv, nc)
        self.instances = []  # (shared mesh Entry, x, y, z, yaw, scale xz, scale y): drawn with a matrix each

    def tri(self, mat, verts):
        self.groups.setdefault(mat, []).append(verts)

    def positions(self):
        return [v[0] for tris in self.groups.values() for t in tris for v in t]


ENTRIES: list[Entry] = []
MESHES: list[Entry] = []  # shared models drawn by instances (no room entry of their own)
INST_MTX = []  # the instances' matrices, in emit order


def new_mesh(name):
    e = Entry(name)
    MESHES.append(e)
    return e


def inst_transform(inst):
    """Function moving a point of the shared mesh to where the instance puts it."""
    _, x, y, z, yaw, sxz, sy = inst
    c, s_ = math.cos(yaw), math.sin(yaw)

    def f(p):
        q = np.asarray(p, float) * [sxz, sy, sxz]
        return np.array([q[0] * c + q[2] * s_ + x, q[1] + y, -q[0] * s_ + q[2] * c + z])
    return f
COL_TRIS = []  # (p0, p1, p2, surface, flags)


def new_entry(name, **kw):
    e = Entry(name, **kw)
    ENTRIES.append(e)
    return e


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def facing_tri(p0, p1, p2, facing):
    """Order the triangle so its front face (counter-clockwise) points along `facing`."""
    n = np.cross(np.subtract(p1, p0), np.subtract(p2, p0))
    return (p0, p2, p1) if np.dot(n, facing) < 0 else (p0, p1, p2)


def add_col(p0, p1, p2, surf, flags=0, facing=None):
    if facing is not None:
        p0, p1, p2 = facing_tri(p0, p1, p2, facing)
    COL_TRIS.append((tuple(p0), tuple(p1), tuple(p2), surf, flags))


def V(p, uv, nc):
    return (tuple(float(c) for c in p), (float(uv[0]), float(uv[1])), tuple(nc))


def quad(entry, mat, p, uv, nc, facing, col=None):
    """p, uv, nc: 4 corners in order around the quad."""
    a, b, c, d = range(4)
    for i0, i1, i2 in ((a, b, c), (a, c, d)):
        verts = [V(p[i], uv[i], nc[i]) for i in (i0, i1, i2)]
        n = np.cross(np.subtract(verts[1][0], verts[0][0]), np.subtract(verts[2][0], verts[0][0]))
        if np.dot(n, facing) < 0:
            verts = [verts[0], verts[2], verts[1]]
        entry.tri(mat, verts)
    if col is not None:
        add_col(p[a], p[b], p[c], col, facing=facing)
        add_col(p[a], p[c], p[d], col, facing=facing)


def tex_scale(mat):
    w, h = mat.size
    return w / mat.repeat, h / mat.repeat


def planar_uv(mat, p):
    su, sv = tex_scale(mat)
    return (p[0] * su, p[2] * sv)


# ---------------------------------------------------------------- terrain

GRID_HALF = 7200
GRID_N = 30
CHUNKS = 6


_GRID = {}


def mesh_height(x, z):
    """Height of the triangulated terrain (what Link actually stands on), not the smooth function."""
    xs, Y = _GRID["xs"], _GRID["Y"]
    step = xs[1] - xs[0]
    i = min(max(int((x - xs[0]) // step), 0), GRID_N - 1)
    j = min(max(int((z - xs[0]) // step), 0), GRID_N - 1)
    u, v = (x - xs[i]) / step, (z - xs[j]) / step
    h00, h10, h11, h01 = Y[j, i], Y[j, i + 1], Y[j + 1, i + 1], Y[j + 1, i]
    if abs(h00 - h11) < abs(h10 - h01):  # split along (0,0)-(1,1), as build_terrain does
        return float(h00 + (h10 - h00) * u + (h11 - h10) * v if u >= v else h00 + (h11 - h01) * u + (h01 - h00) * v)
    if u + v <= 1:  # split along (1,0)-(0,1)
        return float(h00 + (h10 - h00) * u + (h01 - h00) * v)
    return float(h11 + (h01 - h11) * (1 - u) + (h10 - h11) * (1 - v))


def build_terrain():
    xs = np.linspace(-GRID_HALF, GRID_HALF, GRID_N + 1)
    X, Z = np.meshgrid(xs, xs, indexing="xy")
    Y = height(X, Z)
    _GRID["xs"], _GRID["Y"] = xs, Y
    Nrm = normal_at(X, Z)
    per = GRID_N // CHUNKS + (1 if GRID_N % CHUNKS else 0)
    chunks = {}
    for j in range(GRID_N):
        for i in range(GRID_N):
            cx, cz = (xs[i] + xs[i + 1]) / 2, (xs[j] + xs[j + 1]) / 2
            rc = math.hypot(cx, cz)
            if max(math.hypot(xs[a], xs[b]) for a in (i, i + 1) for b in (j, j + 1)) < PLAZA_R - 40:
                continue  # all of it hidden under the plaza (a cell that reaches past its edge stays: no holes)
            if min(math.hypot(xs[a], xs[b]) for a in (i, i + 1) for b in (j, j + 1)) > 7700:
                continue  # far corners, always behind the mountains
            key = (i // per, j // per)
            if key not in chunks:
                chunks[key] = new_entry(f"terrain_{key[0]}_{key[1]}")
            e = chunks[key]
            idx = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            # Split along the diagonal that follows the terrain better.
            d1 = abs(Y[j, i] - Y[j + 1, i + 1])
            d2 = abs(Y[j, i + 1] - Y[j + 1, i])
            tris = [(0, 2, 1), (0, 3, 2)] if d1 < d2 else [(0, 3, 1), (1, 3, 2)]
            for t in tris:
                pts = [np.array([X[idx[k][1], idx[k][0]], Y[idx[k][1], idx[k][0]], Z[idx[k][1], idx[k][0]]]) for k in t]
                nrm = [Nrm[idx[k][1], idx[k][0]] for k in t]
                fn = unit(np.cross(pts[1] - pts[0], pts[2] - pts[0]))
                if fn[1] < 0:
                    pts = [pts[0], pts[2], pts[1]]
                    nrm = [nrm[0], nrm[2], nrm[1]]
                    fn = -fn
                cen = sum(pts) / 3
                r = math.hypot(cen[0], cen[2])
                slope = 1 - fn[1]
                pd = float(path_dist(cen[0], cen[2]))
                if slope > 0.34 or (r > 3650 and slope > 0.24):
                    mat = ROCK
                else:
                    mat = GRASS
                if mat is ROCK:
                    # project on the plane the face looks at most
                    ax = int(np.argmax(np.abs(fn)))
                    su, sv = tex_scale(ROCK)
                    if ax == 1:
                        uvs = [(p[0] * su, p[2] * sv) for p in pts]
                    elif ax == 0:
                        uvs = [(p[2] * su, -p[1] * sv) for p in pts]
                    else:
                        uvs = [(p[0] * su, -p[1] * sv) for p in pts]
                else:
                    uvs = [planar_uv(mat, p) for p in pts]
                on_path = False
                if mat is GRASS and (pd < 400 or 600 < rc < TOWN_GROUND_R + 400):
                    on_path = cut_paths(e, pts, nrm)
                else:
                    e.tri(mat, [V(pts[k], uvs[k], nrm[k]) for k in range(3)])
                if r < 4500:
                    surf = SURF_DIRT if on_path else SURF_STONE if mat is ROCK else SURF_GRASS
                    add_col(pts[0], pts[1], pts[2], surf)


def cut_paths(e, pts, nrm):
    """Split a grass triangle along the path edges: dirt inside the paths, grass outside. Heights and normals
    are interpolated on the original triangle, so the path is part of the ground (no decal, no flicker).
    Returns True when the triangle is mostly path."""
    import shapely
    from shapely.geometry import Polygon

    tri2 = Polygon([(p[0], p[2]) for p in pts])
    paths = paths_polygon()
    town = town_polygon()
    if not tri2.intersects(paths) and (tri2.within(town) or not tri2.intersects(town)):
        mat = TOWN_GROUND if tri2.within(town) else GRASS
        e.tri(mat, [V(pts[k], planar_uv(mat, pts[k]), nrm[k]) for k in range(3)])
        return False
    a2 = np.array([[p[0], p[2]] for p in pts])
    den = np.linalg.det(np.array([a2[1] - a2[0], a2[2] - a2[0]]).T)

    def lift(x, z):
        l1, l2 = np.linalg.solve(np.array([a2[1] - a2[0], a2[2] - a2[0]]).T, np.array([x, z]) - a2[0])
        w = np.array([1 - l1 - l2, l1, l2])
        y = float(sum(w[k] * pts[k][1] for k in range(3)))
        n = unit(sum(w[k] * np.asarray(nrm[k]) for k in range(3)))
        return np.array([x, y, z]), tuple(n)

    inside = tri2.intersection(paths)
    outside = tri2.difference(paths)
    for geom, mat in ((inside, DIRT), (outside.intersection(town), TOWN_GROUND), (outside.difference(town), GRASS)):
        if geom.is_empty:
            continue
        for t in shapely.constrained_delaunay_triangles(geom).geoms:
            if t.area < 4:
                continue
            c = list(t.exterior.coords)[:3]
            q = [lift(x, z) for x, z in c]
            ps = facing_tri(q[0][0], q[1][0], q[2][0], (0, 1, 0))
            ns = {tuple(p): n for p, n in q}
            e.tri(mat, [V(p, planar_uv(mat, p), ns[tuple(p)]) for p in ps])
    return inside.area > tri2.area * 0.5 and abs(den) > 0


# ---------------------------------------------------------------- shapes


def ring_pts(radius, y, n, phase=0.0):
    return [np.array([radius * math.sin(phase + 2 * math.pi * k / n), y, radius * math.cos(phase + 2 * math.pi * k / n)])
            for k in range(n)]


def prism(entry, mat, radius_bot, radius_top, y0, y1, n, phase=0.0, col=None, cap=True, cap_mat=None, center=(0, 0),
          top_jag=None, wall_v0=0.0):
    """Flat-shaded n-gon prism/frustum with outward faces (lit)."""
    cx, cz = center
    bot = [p + np.array([cx, 0, cz]) for p in ring_pts(radius_bot, y0, n, phase)]
    top = [p + np.array([cx, 0, cz]) for p in ring_pts(radius_top, y1, n, phase)]
    if top_jag is not None:
        for k in range(n):
            top[k][1] += top_jag[k]
    su, sv = tex_scale(mat)
    u = 0.0
    for k in range(n):
        k2 = (k + 1) % n
        out = unit(((bot[k] + bot[k2]) / 2 - np.array([cx, 0.0, cz])) * [1, 0, 1])
        w = np.linalg.norm(bot[k2] - bot[k])
        nrm = tuple(out)
        quad(entry, mat, [bot[k], bot[k2], top[k2], top[k]],
             [(u * su, (wall_v0 - bot[k][1]) * sv), ((u + w) * su, (wall_v0 - bot[k2][1]) * sv),
              ((u + w) * su, (wall_v0 - top[k2][1]) * sv), (u * su, (wall_v0 - top[k][1]) * sv)],
             [nrm] * 4, out, col)
        u += w
    if cap:
        cm = cap_mat or mat
        c = np.array([cx, max(t[1] for t in top), cz])
        for k in range(n):
            k2 = (k + 1) % n
            pts = facing_tri(c, top[k], top[k2], (0, 1, 0))
            fn = unit(np.cross(pts[1] - pts[0], pts[2] - pts[0]))
            entry.tri(cm, [V(q, planar_uv(cm, q), tuple(fn)) for q in pts])
            if col is not None:
                add_col(c, top[k], top[k2], col, facing=(0, 1, 0))
    return bot, top


def strip(entry, mat, pts, normals, width, lift=1.5, closed=False):
    """Glow strip along a polyline (pts), on surfaces with the given normals. u runs along, t across."""
    pts = [np.asarray(p, float) for p in pts]
    normals = [unit(n) for n in normals]
    if closed:
        pts = pts + [pts[0]]
        normals = normals + [normals[0]]
    m = len(pts)
    su = mat.size[0] / mat.repeat
    left, right, us = [], [], []
    u = 0.0
    for i in range(m):
        if i == 0:
            t = pts[1] - pts[0] if not closed else (pts[1] - pts[-2])
        elif i == m - 1:
            t = pts[-1] - pts[-2] if not closed else (pts[1] - pts[-2])
        else:
            t = (pts[i + 1] - pts[i]) / max(np.linalg.norm(pts[i + 1] - pts[i]), 1e-6) + \
                (pts[i] - pts[i - 1]) / max(np.linalg.norm(pts[i] - pts[i - 1]), 1e-6)
        side = unit(np.cross(unit(t), normals[i]))
        p = pts[i] + normals[i] * lift
        left.append(p - side * width / 2)
        right.append(p + side * width / 2)
        if i > 0:
            u += np.linalg.norm(pts[i] - pts[i - 1])
        us.append(u * su)
    for i in range(m - 1):
        n = normals[i]
        quad(entry, mat, [left[i], right[i], right[i + 1], left[i + 1]],
             [(us[i], 0), (us[i], 32), (us[i + 1], 32), (us[i + 1], 0)], [(255, 255, 255, 255)] * 4, n)


def noisy_rock(entry, mat, center, radius, squash=1.0, seed=0, sink=0.25, col=None, glow_ring=False, detail=1, flat=None):
    """Icosphere boulder with smooth normals, half buried."""
    t = (1 + 5**0.5) / 2
    vs = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
          (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    fs = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
          (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
          (8, 6, 7), (9, 8, 1)]
    vs = [unit(v) for v in vs]
    cache = {}

    def mid(a, b):
        key = (min(a, b), max(a, b))
        if key not in cache:
            cache[key] = len(vs)
            vs.append(unit((vs[a] + vs[b]) / 2))
        return cache[key]

    for _ in range(detail):
        nf = []
        for a, b, c in fs:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        fs = nf
    # make every face wind outward (counter-clockwise seen from outside)
    fs = [(a, b, c) if np.dot(np.cross(vs[b] - vs[a], vs[c] - vs[a]), vs[a] + vs[b] + vs[c]) > 0 else (a, c, b)
          for a, b, c in fs]
    r = np.random.default_rng(seed)
    pn = Perlin(seed + 100)
    pos = []
    for v in vs:
        d = 1 + 0.22 * float(pn(v[0] * 1.7 + v[2], v[1] * 1.7 - v[2])) + 0.08 * (r.random() - 0.5)
        p = v * d * radius
        p[1] *= squash
        if flat is not None:  # cut flat on one side (dir, distance from the center)
            fd, fdist = np.asarray(flat[0], float), flat[1]
            over = float(np.dot(p, fd)) - fdist
            if over > 0:
                p = p - fd * over
        pos.append(np.array(center) + p - np.array([0, radius * squash * sink, 0]))
    vn = [np.zeros(3) for _ in pos]
    for a, b, c in fs:
        fn = np.cross(pos[b] - pos[a], pos[c] - pos[a])
        for k in (a, b, c):
            vn[k] += fn
    vn = [unit(n) for n in vn]
    su, sv = tex_scale(mat)
    for a, b, c in fs:
        pts = [pos[a], pos[b], pos[c]]
        if sink > 0 and max(p[1] for p in pts) < height(pts[0][0], pts[0][2]) - 5:
            continue  # fully underground
        fn = unit(np.cross(pts[1] - pts[0], pts[2] - pts[0]))
        ax = int(np.argmax(np.abs(fn)))
        if ax == 1:
            uvs = [(p[0] * su, p[2] * sv) for p in pts]
        elif ax == 0:
            uvs = [(p[2] * su, -p[1] * sv) for p in pts]
        else:
            uvs = [(p[0] * su, -p[1] * sv) for p in pts]
        entry.tri(mat, [V(pts[k], uvs[k], tuple(vn[(a, b, c)[k]])) for k in range(3)])
    if col is not None:
        cy = center[1]
        prism_col(center, radius * 0.82, cy - radius, cy + radius * squash * (1 - sink) * 0.9, 8, col)


def prism_col(center, radius, y0, y1, n, surf):
    cx, _, cz = center
    bot = [p + np.array([cx, 0, cz]) for p in ring_pts(radius, y0, n)]
    top = [p + np.array([cx, 0, cz]) for p in ring_pts(radius, y1, n)]
    c = np.array([cx, y1, cz])
    for k in range(n):
        k2 = (k + 1) % n
        out = unit(((bot[k] + bot[k2]) / 2 - np.array([cx, y0, cz])) * [1, 0, 1])
        add_col(bot[k], bot[k2], top[k2], surf, facing=out)
        add_col(bot[k], top[k2], top[k], surf, facing=out)
        add_col(c, top[k], top[k2], surf, facing=(0, 1, 0))


# ---------------------------------------------------------------- plaza


PLAZA_R = 900
STAIR_W = 320


def build_plaza():
    e = new_entry("plaza")
    y = PLAZA_Y
    n = 40
    radii = [270, 440, 620, 820, PLAZA_R]
    up = (0, 1, 0)
    for ri in range(len(radii) - 1):
        r0, r1 = radii[ri], radii[ri + 1]
        mat = TECH if r0 >= 820 else PLAZA
        a = ring_pts(r0, y, n)
        b = ring_pts(r1, y, n)
        for k in range(n):
            k2 = (k + 1) % n
            pts = [a[k], b[k], b[k2], a[k2]]
            quad(e, mat, pts, [planar_uv(mat, p) for p in pts], [up] * 4, up, SURF_STONE)
    # skirt
    a = ring_pts(PLAZA_R, y, n)
    b = ring_pts(PLAZA_R, -90, n)
    su, sv = tex_scale(TECH)
    for k in range(n):
        k2 = (k + 1) % n
        out = unit(((a[k] + a[k2]) / 2) * [1, 0, 1])
        u0 = k * 2 * math.pi * PLAZA_R / n
        u1 = u0 + 2 * math.pi * PLAZA_R / n
        quad(e, TECH, [b[k], b[k2], a[k2], a[k]],
             [(u0 * su, 120 * sv), (u1 * su, 120 * sv), (u1 * su, 0), (u0 * su, 0)], [tuple(out)] * 4, out, SURF_STONE)
    # stairs at the four paths
    for k in range(4):
        ang = PATH_ANGLES[k]
        fwd = np.array([math.sin(ang), 0, math.cos(ang)])
        side = np.array([math.cos(ang), 0, -math.sin(ang)])
        steps = [(20, 880, 940), (10, 940, 1000)]
        for top, d0, d1 in steps:
            c0, c1 = fwd * d0, fwd * d1
            hw = STAIR_W / 2
            p = [c0 - side * hw, c1 - side * hw, c1 + side * hw, c0 + side * hw]
            tp = [q + np.array([0, top, 0]) for q in p]
            quad(e, PLAZA, tp, [planar_uv(PLAZA, q) for q in tp], [up] * 4, up, SURF_STONE)
            bp = [q + np.array([0, -40, 0]) for q in p]
            # riser (front), sides
            for (i0, i1) in ((1, 2), (0, 1), (3, 2)):
                facing = fwd if (i0, i1) == (1, 2) else (-side if i0 == 0 else side)
                pts = [bp[i0], bp[i1], tp[i1], tp[i0]]
                w = np.linalg.norm(pts[1] - pts[0])
                quad(e, TECH, pts, [(0, (top + 40) * sv), (w * su, (top + 40) * sv), (w * su, 0), (0, 0)],
                     [tuple(facing)] * 4, facing, SURF_STONE)
    # glowing circuits
    for rr in (330, 560, 790):
        pts = ring_pts(rr, y, 64)
        strip(e, GLOW_CYAN, pts, [up] * 64, 30, lift=2.0, closed=True)
    for k in range(8):
        a0 = math.pi / 8 + k * math.pi / 4
        d = np.array([math.sin(a0), 0, math.cos(a0)])
        s = np.array([math.cos(a0), 0, -math.sin(a0)]) * (1 if k % 2 else -1)
        poly = [d * 330, d * 450, d * 520 + s * 60, d * 640 + s * 60, d * 700, d * 790]
        poly = [p + np.array([0, y, 0]) for p in poly]
        strip(e, GLOW_CYAN, poly, [up] * len(poly), 22, lift=2.2)
        # node pad where the trace meets the middle ring
        pad = d * 560 + s * 60 * (0 if k % 2 == 0 else 0) + np.array([0, y, 0])
        strip(e, GLOW_CYAN, [pad - d * 18, pad + d * 18], [up, up], 36, lift=2.4)
    # Sheikah eyes between the stairs and the traces, facing outward
    for k in range(4):
        ang = PATH_ANGLES[k]
        fwd = np.array([math.sin(ang), 0, math.cos(ang)])
        side = np.array([math.cos(ang), 0, -math.sin(ang)])
        c = fwd * 675 + np.array([0, y + 2.6, 0])
        h = 62
        pts = [c - side * h + fwd * h, c + side * h + fwd * h, c + side * h - fwd * h, c - side * h - fwd * h]
        quad(e, EYE, pts, [(0, 0), (64, 0), (64, 64), (0, 64)], [(255, 255, 255, 255)] * 4, up)


# ---------------------------------------------------------------- the Ancient Spire


def build_monument():
    e = new_entry("spire")
    up = (0, 1, 0)
    tiers = [(300, 30, 70), (225, 70, 110), (155, 110, 150)]
    for r, y0, y1 in tiers:
        prism(e, TECH, r, r, y0, y1, 8, phase=math.pi / 8, col=SURF_TECH, cap=True, cap_mat=PLAZA)
        # glowing band around the riser
        pts = [p for p in ring_pts(r / math.cos(math.pi / 8), (y0 + y1) / 2, 8, math.pi / 8)]
        nrm = [unit(p * [1, 0, 1]) for p in pts]
        mids = []
        mn = []
        for k in range(8):
            a, b = pts[k], pts[(k + 1) % 8]
            for t in (0.0, 0.5):
                q = a + (b - a) * t
                mids.append(q)
                mn.append(unit(((a + b) / 2) * [1, 0, 1]))
        strip(e, GLOW_ORANGE, mids, mn, 9, lift=1.2, closed=True)
    # obelisk
    y0, y1 = 150, 1020
    rb, rt = 112, 70
    bot, top = prism(e, TECH, rb, rt, y0, y1, 8, phase=math.pi / 8, col=SURF_TECH, cap=False)
    for k in range(8):
        k2 = (k + 1) % 8
        out = unit(((bot[k] + bot[k2]) / 2) * [1, 0, 1])
        fb0, fb1, ft0, ft1 = bot[k], bot[k2], top[k], top[k2]

        def at(s, h):  # point on the face: s across (0..1), h height (0..1)
            p0 = fb0 + (ft0 - fb0) * h
            p1 = fb1 + (ft1 - fb1) * h
            return p0 + (p1 - p0) * s

        if k % 2 == 0:
            # rune panels (two stacked squares), slightly proud of the face, self-lit
            for (h0, h1) in ((0.20, 0.31), (0.31, 0.42)):
                pts = [at(0.1, h0), at(0.9, h0), at(0.9, h1), at(0.1, h1)]
                pts = [p + out * 1.8 for p in pts]
                quad(e, RUNES, pts, [(0, 64), (64, 64), (64, 0), (0, 0)], [(255, 255, 255, 255)] * 4, out)
        else:
            line = [at(0.5, h) for h in np.linspace(0.05, 0.97, 8)]
            strip(e, GLOW_ORANGE, line, [out] * len(line), 12, lift=1.4)
    # collar and pointed cap
    prism(e, TECH, 90, 90, 1020, 1058, 8, phase=math.pi / 8, col=SURF_TECH, cap=False)
    # underside of the collar (visible from the plaza)
    under_o = ring_pts(90, 1020, 8, math.pi / 8)
    under_i = ring_pts(rt, 1020, 8, math.pi / 8)
    down = (0, -1, 0)
    for k in range(8):
        k2 = (k + 1) % 8
        pts = [under_i[k], under_o[k], under_o[k2], under_i[k2]]
        quad(e, TECH, pts, [planar_uv(TECH, q) for q in pts], [down] * 4, down)
    collar_top = ring_pts(90, 1058, 8, math.pi / 8)
    apex = np.array([0, 1195, 0])
    su, sv = tex_scale(TECH)
    for k in range(8):
        a, b = collar_top[k], collar_top[(k + 1) % 8]
        fn = unit(np.cross(b - a, apex - a))
        if np.dot(fn, (a + b) / 2 * [1, 0, 1]) < 0:
            fn = -fn
        tri = facing_tri(a, b, apex, fn)
        w = np.linalg.norm(b - a)
        e.tri(TECH, [V(tri[0], (0, 0), tuple(fn)), V(tri[1], (w * su, 0), tuple(fn)), V(tri[2], (w * su / 2, 110 * sv), tuple(fn))])
        add_col(a, b, apex, SURF_TECH, facing=fn)


def build_floating():
    """The spinning ring (segment 9), hovering crystal (segment 0xB) and orbiting shards (segment 0xA)."""
    ring = new_entry("ring", matrix_seg=0x09, sphere=((0, RING_Y, 0), 290))
    n = 36
    ri, ro, hh = 168, 214, 14
    su, sv = tex_scale(TECH)
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = 2 * math.pi * (k + 1) / n
        d0 = np.array([math.sin(a0), 0, math.cos(a0)])
        d1 = np.array([math.sin(a1), 0, math.cos(a1)])
        u0 = ro * a0 * su
        u1 = ro * a1 * su
        up = np.array([0, 1, 0])
        quad(ring, TECH, [d0 * ri + up * hh, d0 * ro + up * hh, d1 * ro + up * hh, d1 * ri + up * hh],
             [(u0, 0), (u0, 42 * sv), (u1, 42 * sv), (u1, 0)], [tuple(up)] * 4, up)
        quad(ring, TECH, [d0 * ri - up * hh, d0 * ro - up * hh, d1 * ro - up * hh, d1 * ri - up * hh],
             [(u0, 0), (u0, 42 * sv), (u1, 42 * sv), (u1, 0)], [tuple(-up)] * 4, -up)
        outn = unit((d0 + d1) / 2)
        quad(ring, TECH, [d0 * ro - up * hh, d1 * ro - up * hh, d1 * ro + up * hh, d0 * ro + up * hh],
             [(u0, 26 * sv), (u1, 26 * sv), (u1, 0), (u0, 0)], [tuple(outn)] * 4, outn)
        quad(ring, TECH, [d0 * ri - up * hh, d1 * ri - up * hh, d1 * ri + up * hh, d0 * ri + up * hh],
             [(u0, 26 * sv), (u1, 26 * sv), (u1, 0), (u0, 0)], [tuple(-outn)] * 4, -outn)
    pts = [np.array([math.sin(2 * math.pi * k / 64), 0, math.cos(2 * math.pi * k / 64)]) * ro for k in range(64)]
    strip(ring, GLOW_CYAN, pts, [unit(p) for p in pts], 10, lift=1.2, closed=True)
    pts = [np.array([math.sin(2 * math.pi * k / 64), 0, math.cos(2 * math.pi * k / 64)]) * 191 + [0, hh, 0]
           for k in range(64)]
    strip(ring, GLOW_CYAN, pts, [(0, 1, 0)] * 64, 9, lift=1.0, closed=True)

    crystal = new_entry("crystal", matrix_seg=0x0B, sphere=((0, RING_Y, 0), 140))
    top, bot = np.array([0, 88, 0]), np.array([0, -74, 0])
    mid = [np.array([math.sin(k * math.pi / 3) * 44, 0, math.cos(k * math.pi / 3) * 44]) for k in range(6)]
    cols = [(150, 255, 255, 255), (60, 200, 255, 255), (20, 120, 220, 255)]
    for k in range(6):
        a, b = mid[k], mid[(k + 1) % 6]
        out = unit((a + b) / 2)
        for apex, ca in ((top, cols[0]), (bot, cols[2])):
            fn = unit(np.cross(b - a, apex - a))
            if np.dot(fn, out + (apex / 100)) < 0:
                fn = -fn
            tri = facing_tri(a, b, apex, fn)
            crystal.tri(CRYSTAL, [V(tri[0], (0, 0), cols[1]), V(tri[1], (0, 0), cols[1]), V(tri[2], (0, 0), ca)])

    shards = new_entry("shards", matrix_seg=0x0A, sphere=((0, 650, 0), 560))
    for k in range(6):
        a = k * math.pi / 3 + 0.3
        c = (math.sin(a) * 380, 470 + 70 * ((k * 37) % 5), math.cos(a) * 380)
        noisy_rock(shards, TECHROCK, c, 40 + 7 * (k % 3), squash=1.3, seed=200 + k, sink=0.0, detail=0)
    # bigger rocks drifting high over the town, on the same slow turn
    sky = new_entry("sky_rocks", matrix_seg=0x0A, sphere=((0, 1000, 0), 2600))
    for k in range(10):
        a = k * math.pi / 5 + 0.15 + 0.2 * (k % 2)
        rr = 1550 + 240 * ((k * 3) % 4)
        sc = 0.55 + 0.2 * (k % 3)
        sky.instances.append((float_rock_mesh(), math.sin(a) * rr, 960 + 90 * ((k * 5) % 4), math.cos(a) * rr, a * 2.3,
                              sc, sc * 1.3))


# ---------------------------------------------------------------- monoliths, pillars, boulders


def build_monoliths():
    es = [new_entry("monoliths_a"), new_entry("monoliths_b")]
    for k in range(8):
        a = math.pi / 8 + k * math.pi / 4
        r = 1290
        cx, cz = math.sin(a) * r, math.cos(a) * r
        gy = float(height(cx, cz))
        H = 230 + 55 * (k % 3)
        R = 78 + 10 * ((k * 5) % 3)
        e = es[k % 2]
        n = 7
        rings = 4
        pn = Perlin(300 + k)
        prev = None
        su, sv = tex_scale(TECHROCK)
        layers = []
        for j in range(rings + 1):
            t = j / rings
            y = gy - 30 + (H + 30) * t
            rr = R * (1 - 0.38 * t**1.3)
            lay = []
            for q in range(n):
                ang = 2 * math.pi * q / n + 0.4 * k
                d = 1 + 0.18 * float(pn(math.cos(ang) * 2 + j * 0.7, math.sin(ang) * 2 - j * 0.5))
                lay.append(np.array([cx + math.sin(ang) * rr * d, y + (12 * float(pn(q, j)) if j == rings else 0),
                                     cz + math.cos(ang) * rr * d]))
            layers.append(lay)
        top_c = np.array([cx, layers[-1][0][1] + 22, cz])
        for j in range(rings):
            for q in range(n):
                q2 = (q + 1) % n
                p = [layers[j][q], layers[j][q2], layers[j + 1][q2], layers[j + 1][q]]
                out = unit(((p[0] + p[1]) / 2 - np.array([cx, 0, cz])) * [1, 0, 1])
                ns = [tuple(unit((p[i] - np.array([cx, p[i][1], cz])) * [1, 0.3, 1])) for i in range(4)]
                uu = [q / n * 2 * math.pi * R * su, q2 / n * 2 * math.pi * R * su if q2 else 2 * math.pi * R * su]
                quad(e, TECHROCK, p, [(uu[0], -p[0][1] * sv), (uu[1], -p[1][1] * sv), (uu[1], -p[2][1] * sv),
                                      (uu[0], -p[3][1] * sv)], ns, out)
        for q in range(n):
            q2 = (q + 1) % n
            a1, b1 = layers[-1][q], layers[-1][q2]
            fn = unit(np.cross(b1 - a1, top_c - a1))
            if fn[1] < 0:
                fn = -fn
            tri = facing_tri(a1, b1, top_c, fn)
            e.tri(TECHROCK, [V(p, planar_uv(TECHROCK, p), tuple(fn)) for p in tri])
        prism_col((cx, gy, cz), R * 0.85, gy - 30, gy + H, 8, SURF_TECH)
        # glowing ring on the ground around the base
        pts = []
        nrm = []
        for q in range(40):
            ang = 2 * math.pi * q / 40
            px, pz = cx + math.sin(ang) * (R + 46), cz + math.cos(ang) * (R + 46)
            pts.append(np.array([px, float(height(px, pz)), pz]))
            nrm.append(tuple(normal_at(px, pz)))
        strip(e, GLOW_CYAN, pts, nrm, 16, lift=3.0, closed=True)


def build_pillars():
    es = {k: new_entry(f"pillars_{k}") for k in range(4)}
    for k in range(4):
        for i, (r, s, off) in enumerate(((2900, 1, 420),)):  # (the inner ones gave way to the town)
            sidek = 1
            ang = float(path_angle(k, r))
            fwd = np.array([math.sin(ang), 0, math.cos(ang)])
            side = np.array([math.cos(ang), 0, -math.sin(ang)])
            s = s if k % 2 == 0 else -s
            c = fwd * r + side * s * off
            if town_plan.near_plot(c[0], c[2], 120):
                continue  # a house stands here
            # keep the view from Link's start point to the Spire clear
            to_c = np.array([c[0] - SPAWN[0], c[2] - SPAWN[1]])
            to_spire = np.array([-SPAWN[0], -SPAWN[1]], float)
            ang_off = abs(math.atan2(to_spire[0] * to_c[1] - to_spire[1] * to_c[0], float(np.dot(to_spire, to_c))))
            if ang_off < math.radians(9) and np.linalg.norm(to_c) < np.linalg.norm(to_spire):
                continue
            if True:
                gy = float(height(c[0], c[2]))
                H = 150 + 70 * ((k * 3 + i) % 3) + (40 if s == sidek else -30)
                jag = [float(v) for v in 26 * (rng.random(8) - 0.3)]
                jag = [j if q % 2 else -abs(j) for q, j in enumerate(jag)]
                prism(es[k], PLAZA, 44, 38, gy - 25, gy + H, 8, phase=0.2 * k, col=SURF_TECH, cap=True, cap_mat=TECH,
                      center=(c[0], c[2]), top_jag=jag)
                pts = [p + np.array([c[0], 0, c[2]]) for p in ring_pts(40.5, gy + H - 42, 8, 0.2 * k)]
                pts2, nr = [], []
                for q in range(8):
                    a1, b1 = pts[q], pts[(q + 1) % 8]
                    for t in (0.0, 0.5):
                        pts2.append(a1 + (b1 - a1) * t)
                        nr.append(unit(((a1 + b1) / 2 - np.array([c[0], 0, c[2]])) * [1, 0, 1]))
                strip(es[k], GLOW_ORANGE, pts2, nr, 9, lift=1.2, closed=True)


# ---------------------------------------------------------------- the sky: island, stepping rocks, waterfall, eye rock

ISLAND, ISLET = town_plan.ISLAND, town_plan.ISLET
ROCK_R = 62  # stepping rocks: top radius
HOP_GAP, HOP_DROP = 46, 8  # Link jumps by himself when he runs off an edge over a drop
CLIMB_UP, CLIMB_OVERLAP = 68, 26  # a 59-79 unit ledge is his "step up" climb (z_player.c, ageProperties)
COL_DEPTH = 120  # collision walls reach this far below a rock's top (so the ledge below "sees" them)


def float_rock(e, cx, cz, top, rad, depth, seed, top_mat=None, n=7, band=30, col=True, rough=0.1):
    """A floating rock: a flat top (grass) on a band of rock, and a jagged point hanging underneath.
    Collision: the top and walls COL_DEPTH deep. Returns the top ring (for decoration)."""
    r = np.random.default_rng(seed)
    top_mat = top_mat or GRASS
    ph = r.random() * 2 * math.pi
    radii = [rad * (1 + rough * (r.random() - 0.5) * 2) for _ in range(n)]
    ring = lambda rr, y, k_off=0.0: [np.array([cx + math.sin(ph + 2 * math.pi * (k + k_off) / n) * rr[k],
                                               y, cz + math.cos(ph + 2 * math.pi * (k + k_off) / n) * rr[k]])
                                     for k in range(n)]
    top_ring = ring(radii, top)
    band_ring = ring(radii, top - band)
    mid_ring = ring([q * 0.62 for q in radii], top - band - depth * 0.42, 0.5)
    tip = np.array([cx + (r.random() - 0.5) * rad * 0.3, top - band - depth, cz + (r.random() - 0.5) * rad * 0.3])
    su, sv = tex_scale(ROCK)
    c_top = np.array([cx, top, cz])
    for k in range(n):
        k2 = (k + 1) % n
        out = unit(((top_ring[k] + top_ring[k2]) / 2 - c_top) * [1, 0, 1])
        w = float(np.linalg.norm(top_ring[k2] - top_ring[k]))
        quad(e, ROCK, [band_ring[k], band_ring[k2], top_ring[k2], top_ring[k]],
             [(0, band * sv), (w * su, band * sv), (w * su, 0), (0, 0)], [tuple(out)] * 4, out)
        # the cap
        tri = facing_tri(c_top, top_ring[k], top_ring[k2], (0, 1, 0))
        e.tri(top_mat, [V(q, planar_uv(top_mat, q), (0, 1, 0)) for q in tri])
        # underneath: band -> middle ring -> tip
        for a, b, c in ((band_ring[k], band_ring[k2], mid_ring[k]), (band_ring[k2], mid_ring[k2], mid_ring[k]),
                        (mid_ring[k], mid_ring[k2], tip)):
            fn = unit(np.cross(b - a, c - a))
            ctr = (a + b + c) / 3
            if np.dot(fn, ctr - np.array([cx, ctr[1] + rad, cz])) < 0:
                fn = -fn
            t3 = facing_tri(a, b, c, fn)
            e.tri(ROCK, [V(q, (q[0] * su + q[2] * su * 0.5, -q[1] * sv), tuple(unit(fn + (q - c_top) * [1, 0, 1] / max(rad, 1) * 0.6)))
                         for q in t3])
        if col:
            add_col(c_top, top_ring[k], top_ring[k2], SURF_GRASS if top_mat in (GRASS, TOWN_GROUND) else SURF_STONE,
                    facing=(0, 1, 0))
            lo0, lo1 = top_ring[k] - [0, COL_DEPTH, 0], top_ring[k2] - [0, COL_DEPTH, 0]
            add_col(lo0, lo1, top_ring[k2], SURF_STONE, facing=out)
            add_col(lo0, top_ring[k2], top_ring[k], SURF_STONE, facing=out)
    return top_ring


def stepping_rocks():
    """The floating rocks that lead from the field up to the island: (x, z, top). Pairs of a hop across a small gap
    (a little lower) and a climb up a ledge, spiralling around the island; the last one touches the island's rim,
    one more climb below its top. Every climb is 41-79 units (Link climbs those by himself, z_player.c)."""
    ix, iz = ISLAND["x"], ISLAND["z"]
    face = math.atan2(-ix, -iz)  # the waterfall's side: start away from it, turning away from the islet
    phi = face + math.radians(70)
    end_r = ISLAND["r"] + ROCK_R - CLIMB_OVERLAP
    start_r = ISLAND["r"] + 330
    x, z = ix + math.sin(phi) * start_r, iz + math.cos(phi) * start_r
    first = float(mesh_height(x, z)) + 66
    goal = ISLAND["top"] - CLIMB_UP
    pairs = math.ceil((goal - first) / (CLIMB_UP - HOP_DROP))
    climb = (goal - first) / pairs + HOP_DROP
    assert 45 <= climb <= 76, climb
    rocks = [(x, z, first)]
    top = first
    for k in range(2 * pairs):
        hop = k % 2 == 0
        dist = 2 * ROCK_R + (HOP_GAP if hop else -CLIMB_OVERLAP)
        top = top - HOP_DROP if hop else top + climb
        rr = start_r + (end_r - start_r) * (k + 1) / (2 * pairs)
        lo_, hi_ = 0.0, 1.5  # turn around the island until the next rock is `dist` away
        for _ in range(40):
            mid = (lo_ + hi_) / 2
            if math.hypot(ix + math.sin(phi + mid) * rr - x, iz + math.cos(phi + mid) * rr - z) < dist:
                lo_ = mid
            else:
                hi_ = mid
        phi += hi_
        x, z = ix + math.sin(phi) * rr, iz + math.cos(phi) * rr
        rocks.append((x, z, top))
    return rocks


def waterfall_spot():
    """(rim point (x, y, z), outward direction (dx, dz)): where the island's stream pours over the edge, toward the Spire."""
    ix, iz = ISLAND["x"], ISLAND["z"]
    d = unit(np.array([-ix, 0, -iz]))
    rim = np.array([ix, ISLAND["top"], iz]) + d * (ISLAND["r"] * 0.97)
    return rim, d


def pool_center():
    """The pool on the field under the waterfall (its foam spreads up to 260 out from the foot)."""
    rim, d = waterfall_spot()
    p = rim + d * 150
    return float(p[0]), float(p[2])


POOL_R = 260


def build_sky():
    e = new_entry("island")
    float_rock(e, ISLAND["x"], ISLAND["z"], ISLAND["top"], ISLAND["r"], 560, 901, n=12, band=95, rough=0.06)
    float_rock(e, ISLET["x"], ISLET["z"], ISLET["top"], ISLET["r"], 300, 902, n=8, band=60, rough=0.08)
    up = np.array([0.0, 1.0, 0.0])
    # the waterfall over the island's edge is Zora's River's own (Bg_Spot03_Taki, placed in actors()); it pours
    # into a pool of Zora's River's water on the field
    px, pz = pool_center()
    gy = float(mesh_height(px, pz))
    surf = gy + 12
    # the pool: a low stone rim (Link steps over it) and the water
    n = 18
    outer = [np.array([px + math.sin(2 * math.pi * k / n) * POOL_R, 0, pz + math.cos(2 * math.pi * k / n) * POOL_R]) for k in range(n)]
    inner = [np.array([px + math.sin(2 * math.pi * k / n) * (POOL_R - 34), 0, pz + math.cos(2 * math.pi * k / n) * (POOL_R - 34)])
             for k in range(n)]
    rim_y = surf + 4
    for k in range(n):
        k2 = (k + 1) % n
        o0, o1 = outer[k] + [0, rim_y, 0], outer[k2] + [0, rim_y, 0]
        i0, i1 = inner[k] + [0, rim_y, 0], inner[k2] + [0, rim_y, 0]
        ob0 = outer[k] + [0, float(mesh_height(outer[k][0], outer[k][2])) - 12, 0]
        ob1 = outer[k2] + [0, float(mesh_height(outer[k2][0], outer[k2][2])) - 12, 0]
        ib0, ib1 = inner[k] + [0, gy - 20, 0], inner[k2] + [0, gy - 20, 0]
        out = unit(((o0 + o1) / 2 - np.array([px, rim_y, pz])) * [1, 0, 1])
        quad(e, ROCK, [o0, o1, i1, i0], [planar_uv(ROCK, q) for q in (o0, o1, i1, i0)], [tuple(up)] * 4, up, SURF_STONE)
        wq = float(np.linalg.norm(o1 - o0))
        quad(e, ROCK, [ob0, ob1, o1, o0], [(0, 30 * tex_scale(ROCK)[1]), (wq * tex_scale(ROCK)[0], 30 * tex_scale(ROCK)[1]),
                                          (wq * tex_scale(ROCK)[0], 0), (0, 0)], [tuple(out)] * 4, out)
        quad(e, ROCK, [ib0, ib1, i1, i0], [(0, 30 * tex_scale(ROCK)[1]), (wq * tex_scale(ROCK)[0], 30 * tex_scale(ROCK)[1]),
                                          (wq * tex_scale(ROCK)[0], 0), (0, 0)], [tuple(-out)] * 4, -out)
        wt = facing_tri(i0 + [0, surf - rim_y, 0], i1 + [0, surf - rim_y, 0], np.array([px, surf, pz]), up)
        e.tri(WATER, [V(q, planar_uv(WATER, q), (200, 235, 255, 255)) for q in wt])
    WATERBOXES.append((px, surf, pz, (POOL_R - 34) * 0.7))
    # floor of the pool (the field's grass is under the water anyway; this keeps the bottom stone)
    # rocks circling the island (segment 0x0F: z_remix_level.c turns them around its center)
    orbit = new_entry("island_orbit", matrix_seg=0x0F, sphere=((ISLAND["x"], ISLAND["top"], ISLAND["z"]), 950))
    for k in range(9):
        a = 2 * math.pi * k / 9 + 0.4
        rr = 540 + 120 * ((k * 5) % 3)
        cy = -260 + 90 * ((k * 7) % 6)
        sc = 0.32 + 0.12 * (k % 3)
        orbit.instances.append((float_rock_mesh(), math.sin(a) * rr, cy, math.cos(a) * rr, a * 3.1, sc, sc * 1.2))
    # the stepping rocks: the shared rock, and collision that matches its top
    steps = new_entry("sky_steps")
    mesh, ring = float_rock_mesh(), _ROCK_MESH[1]
    for i, (x, z, top) in enumerate(stepping_rocks()):
        inst = (mesh, x, top, z, 0.7 * i, ROCK_R / 100, 0.9 + 0.25 * (i % 3))
        steps.instances.append(inst)
        f = inst_transform(inst)
        tr = [f(p) for p in ring]
        c_top = np.array([x, top, z])
        for k in range(len(tr)):
            k2 = (k + 1) % len(tr)
            out = unit(((tr[k] + tr[k2]) / 2 - c_top) * [1, 0, 1])
            add_col(c_top, tr[k], tr[k2], SURF_GRASS, facing=(0, 1, 0))
            lo0, lo1 = tr[k] - [0, COL_DEPTH, 0], tr[k2] - [0, COL_DEPTH, 0]
            add_col(lo0, lo1, tr[k2], SURF_STONE, facing=out)
            add_col(lo0, tr[k2], tr[k], SURF_STONE, facing=out)


_ROCK_MESH = []


def float_rock_mesh():
    """The shared floating rock (top radius 100, top at 0): stepping rocks, rocks circling the island and drifting
    over the town are all this one model, each with its own matrix."""
    if not _ROCK_MESH:
        m = new_mesh("float_rock")
        ring = float_rock(m, 0.0, 0.0, 0.0, 100.0, 150.0, 700, n=6, band=30, col=False, rough=0.12)
        _ROCK_MESH[:] = [m, ring]
    return _ROCK_MESH[0]


WATERBOXES = []  # (x, surface y, z, half size)


def build_entrance():
    """Where Link arrives: an avenue of Sheikah obelisks along the south road and a giant rock with a glowing
    eye watching over it (the Colossus's stone arch spans the road: tools/remix/make_town.py)."""
    e = new_entry("entrance")
    for r in (3000, 3170, 3340, 3510):
        ang = float(path_angle(0, r))
        fwd = np.array([math.sin(ang), 0, math.cos(ang)])
        side = np.array([math.cos(ang), 0, -math.sin(ang)])
        for sgn in (-1, 1):
            c = fwd * r + side * sgn * 205
            gy = float(mesh_height(c[0], c[2]))
            H = 250 if r < 3400 else 200
            bot, top = prism(e, PLAZA, 30, 22, gy - 20, gy + H, 4, phase=ang + math.pi / 4, col=SURF_TECH, cap=False,
                             center=(c[0], c[2]))
            apex = np.array([c[0], gy + H + 46, c[2]])
            for k in range(4):
                a1, b1 = top[k], top[(k + 1) % 4]
                fn = unit(np.cross(b1 - a1, apex - a1))
                if np.dot(fn, ((a1 + b1) / 2 - np.array([c[0], 0, c[2]])) * [1, 0, 1]) < 0:
                    fn = -fn
                t3 = facing_tri(a1, b1, apex, fn)
                e.tri(TECH, [V(q, (0, 0), tuple(fn)) for q in t3])
            outs = [unit(((bot[k] + bot[(k + 1) % 4]) / 2 - np.array([c[0], 0, c[2]])) * [1, 0, 1]) for k in range(4)]
            k = int(np.argmax([float(np.dot(o, -side * sgn)) for o in outs]))  # a glowing line up the face to the road
            a1, b1, a2, b2 = bot[k], bot[(k + 1) % 4], top[k], top[(k + 1) % 4]
            line = [(a1 + b1) / 2 + ((a2 + b2) / 2 - (a1 + b1) / 2) * t for t in (0.15, 0.55, 0.95)]
            strip(e, GLOW_CYAN, line, [outs[k]] * 3, 9, lift=1.2)
    # the giant eye rock beside the road, its eye turned to where Link arrives
    ang = float(path_angle(0, 3260))
    side = np.array([math.cos(ang), 0, -math.sin(ang)])
    c = np.array([math.sin(ang) * 3260, 0, math.cos(ang) * 3260]) + side * 640
    gy = float(mesh_height(c[0], c[2]))
    R = 240
    center = np.array([c[0], gy + R * 0.55, c[2]])
    look = unit(np.array([SPAWN[0] - c[0], 0, SPAWN[1] - c[2]]) + side * -0.0)
    look = unit(look + np.array([0, 0.12, 0]))
    noisy_rock(e, TECHROCK, center, R, squash=1.05, seed=77, sink=0.2, detail=1, flat=(look, R * 0.78))
    face_c = center + look * (R * 0.78 + 2.5)
    fs = unit(np.cross(look, (0, 1, 0)))
    fu = unit(np.cross(fs, look))
    h = R * 0.5
    quad(e, EYE_CYAN, [face_c - fs * h + fu * h, face_c + fs * h + fu * h, face_c + fs * h - fu * h, face_c - fs * h - fu * h],
         [(0, 0), (64, 0), (64, 64), (0, 64)], [(255, 255, 255, 255)] * 4, look)
    ringp = [face_c + look * 0.5 + (fs * math.cos(t) + fu * math.sin(t)) * R * 0.62 for t in np.linspace(0, 2 * math.pi, 25)[:-1]]
    strip(e, GLOW_CYAN, ringp, [tuple(look)] * len(ringp), 12, lift=0.5, closed=True)
    prism_col(tuple(center), R * 0.85, gy - 40, gy + R * 1.3, 10, SURF_TECH)


def build_boundary():
    """Invisible wall that keeps Link out of the mountains (ignored by the camera)."""
    n, r = 48, 4300
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = 2 * math.pi * (k + 1) / n
        p0 = np.array([math.sin(a0) * r, -800, math.cos(a0) * r])
        p1 = np.array([math.sin(a1) * r, -800, math.cos(a1) * r])
        q0, q1 = p0 + [0, 4800, 0], p1 + [0, 4800, 0]
        inward = -unit((p0 + p1) * [1, 0, 1])
        add_col(p0, p1, q1, SURF_WALL, flags=1, facing=inward)
        add_col(p0, q1, q0, SURF_WALL, flags=1, facing=inward)


# ---------------------------------------------------------------- actors


def actors():
    out = []

    def add(actor, x, y, z, ry, params, rx=0, rz=0):
        out.append((actor, int(round(x)), int(round(y)), int(round(z)), rx, int(ry) & 0xFFFF, rz, params))

    def yaw_to(x, z, tx, tz):
        return int(math.atan2(tx - x, tz - z) / (2 * math.pi) * 0x10000)

    # golden torches flanking each staircase, always lit
    for k in range(4):
        for s in (-1, 1):
            a = PATH_ANGLES[k] + s * 0.205
            x, z = math.sin(a) * 845, math.cos(a) * 845
            add("ACTOR_OBJ_SYOKUDAI", x, PLAZA_Y, z, 0, "0x043F")
    # Gossip Stones guarding the Spire's south steps
    for s in (-1, 1):
        add("ACTOR_EN_GS", s * 200, PLAZA_Y, 370, 0, "0x3F05")
    # trees, bushes and butterflies in the field (its rocks are static scenery: build_decor)
    for i, (x, z) in enumerate(field_spots()):
        y = mesh_height(x, z)
        if i < 20:
            add("ACTOR_EN_WOOD02", x, y, z, int(rng.random() * 0x10000), "0xFF05" if i % 3 else "0xFF00")
        elif i >= 59:
            add("ACTOR_EN_BUTTE", x, y + 60, z, 0, "0x0000")
    # lanterns where each quarter's main street leaves the ring road
    for q in range(4):
        mid = math.pi / 4 + q * math.pi / 2
        for s in (-1, 1):
            a = mid + s * 0.095
            r = town_plan.RING_ROAD_R + 120
            x, z = math.sin(a) * r, math.cos(a) * r
            add("ACTOR_OBJ_SYOKUDAI", x, mesh_height(x, z), z, 0, "0x043F")
    # torches by the obelisks where Link arrives
    for r in (3000, 3340):
        ang = float(path_angle(0, r))
        for sgn in (-1, 1):
            x = math.sin(ang) * r + math.cos(ang) * sgn * 150
            z = math.cos(ang) * r - math.sin(ang) * sgn * 150
            add("ACTOR_OBJ_SYOKUDAI", x, mesh_height(x, z), z, 0, "0x043F")
    island_actors(add, yaw_to)
    # a Heart Piece on the islet beyond the floating island (collectible flag 0x14)
    add("ACTOR_EN_ITEM00", ISLET["x"], ISLET["top"] + 20, ISLET["z"], 0, "((0x14 << 8) | ITEM00_HEART_PIECE)")
    town_people(add, yaw_to)
    return out


def island_actors(add, yaw_to):
    """The floating island's actors, all from the game: a big chest with Biggoron's Sword, Hyrule Field's trees,
    Zora's River's waterfall pouring over the edge and a Zora in the pool below."""
    ix, iz, top = ISLAND["x"], ISLAND["z"], ISLAND["top"]
    steps = stepping_rocks()
    lx, lz, _ = steps[-1]
    arrive = math.atan2(lx - ix, lz - iz)  # where Link climbs onto the island
    # the chest in the middle, opening toward where Link arrives (chest flag 1)
    cx, cz = ix - math.sin(arrive) * 40, iz - math.cos(arrive) * 40
    add("ACTOR_EN_BOX", cx, top, cz, int(arrive / (2 * math.pi) * 0x10000),
        "((ENBOX_TYPE_BIG_DEFAULT << 12) | (GI_SWORD_BIGGORON << 5) | 1)")
    # Hyrule Field's trees under the island, and on it behind the chest
    rim, d = waterfall_spot()
    for k, da in enumerate((1.6, 2.4, 3.9, 4.7)):
        tx = ix + math.sin(math.atan2(d[0], d[2]) + da) * (ISLAND["r"] + 500)
        tz = iz + math.cos(math.atan2(d[0], d[2]) + da) * (ISLAND["r"] + 500)
        add("ACTOR_EN_WOOD02", tx, mesh_height(tx, tz), tz, int(k * 0x3000), "0xFF05" if k % 2 else "0xFF00")
    for k, da in enumerate((2.5, 3.6)):
        tx, tz = ix + math.sin(arrive + da) * ISLAND["r"] * 0.55, iz + math.cos(arrive + da) * ISLAND["r"] * 0.55
        add("ACTOR_EN_WOOD02", tx, top, tz, int(k * 0x5000), "0xFF00" if k == 0 else "0xFF05")
    # Zora's River's waterfall over the island's edge (switch flag 0x3E is never set, so it never parts). Its model
    # is a curtain 835 tall and 400 wide in its YZ plane, 80 deep along +X, with the splash foam spreading
    # toward -X from its foot: -X points where the water pours (away from the island).
    rim, d = waterfall_spot()
    wx, wy, wz = taki_origin()
    yaw = int(round(math.atan2(d[2], -d[0]) / (2 * math.pi) * 0x10000)) & 0xFFFF
    add("ACTOR_BG_SPOT03_TAKI", wx, wy, wz, yaw, "0x003E")
    # a Zora in the pool it falls into
    px, pz = pool_center()
    zx, zz = px + d[0] * 60 + d[2] * 70, pz + d[2] * 60 - d[0] * 70
    add("ACTOR_EN_ZO", zx, mesh_height(zx, zz), zz, yaw_to(zx, zz, wx, wz), "0x0000")


def view_defines():
    """Where the test boots put Link (src/code/z_remix_level.c, tools/remix/smoke_test.py): on the island where
    the stepping rocks arrive, facing the chest; and on the field in front of the pool, facing the waterfall."""
    ix, iz, top = ISLAND["x"], ISLAND["z"], ISLAND["top"]
    lx, lz, _ = stepping_rocks()[-1]
    a = math.atan2(lx - ix, lz - iz)
    vx, vz = ix + math.sin(a) * ISLAND["r"] * 0.8, iz + math.cos(a) * ISLAND["r"] * 0.8
    vyaw = int(math.atan2(ix - vx, iz - vz) / (2 * math.pi) * 0x10000) & 0xFFFF
    px, pz = pool_center()
    rim, d = waterfall_spot()
    qx, qz = px + d[0] * (POOL_R + 260), pz + d[2] * (POOL_R + 260)
    qyaw = int(math.atan2(px - qx, pz - qz) / (2 * math.pi) * 0x10000) & 0xFFFF
    return (f"// Where the test boots put Link (z_remix_level.c)\n"
            f"#define ANCIENT_VIEW_ISLAND_X {vx:.1f}f\n#define ANCIENT_VIEW_ISLAND_Y {top + 2:.1f}f\n"
            f"#define ANCIENT_VIEW_ISLAND_Z {vz:.1f}f\n#define ANCIENT_VIEW_ISLAND_YAW 0x{vyaw:04X}\n"
            f"#define ANCIENT_VIEW_POOL_X {qx:.1f}f\n#define ANCIENT_VIEW_POOL_Y {float(mesh_height(qx, qz)) + 2:.1f}f\n"
            f"#define ANCIENT_VIEW_POOL_Z {qz:.1f}f\n#define ANCIENT_VIEW_POOL_YAW 0x{qyaw:04X}\n")


TAKI_HEIGHT = 835.1  # Zora's River's waterfall (object_spot03_object, drawn at scale 0.1)


def taki_origin():
    """Foot of the waterfall: just outside the island's rim, its top at the island's top."""
    rim, d = waterfall_spot()
    return float(rim[0] + d[0] * 15), float(ISLAND["top"] - TAKI_HEIGHT), float(rim[2] + d[2] * 15)


OBJECTS = ["OBJECT_SYOKUDAI", "OBJECT_GS", "OBJECT_WOOD02",
           # the town's people and animals (town_people)
           "OBJECT_OS_ANIME", "OBJECT_BOJ", "OBJECT_AHG", "OBJECT_DOG",
           "OBJECT_TSUBO",
           # the floating island: the big chest, Zora's River's waterfall, a Zora (island_actors)
           "OBJECT_BOX", "OBJECT_SPOT03_OBJECT", "OBJECT_ZO"]
# With gameplay_keep, field_keep and Link these take about 893 KB of the scene's 900 KB object space
# (REMIX_ANCIENT_OBJECT_SPACE, include/remix_level.h); the rest of the play heap is actor memory for the town.

TOWN_PATH_R = town_plan.RING_ROAD_R  # the ring road around the plaza (dogs and strollers follow it)


def town_path():
    pts = []
    for k in range(16):
        a = 2 * math.pi * k / 16 + math.pi / 16
        x, z = math.sin(a) * TOWN_PATH_R, math.cos(a) * TOWN_PATH_R
        pts.append((round(x), round(mesh_height(x, z)), round(z)))
    return pts


_SPOTS = []


def field_spots():
    """Spots in the field for trees, bushes, rocks and butterflies (off the paths, streets and house plots)."""
    if not _SPOTS:
        prng = np.random.default_rng(77)
        tries = 0
        while len(_SPOTS) < 66 and tries < 8000:
            tries += 1
            r = 1500 + prng.random() * 2100
            a = prng.random() * 2 * math.pi
            x, z = math.sin(a) * r, math.cos(a) * r
            if float(path_dist(x, z)) < 220 or math.hypot(x - SPAWN[0], z - SPAWN[1]) < 300:
                continue
            if town_plan.near_plot(x, z, 160) or street_dist(x, z) < 110:
                continue
            if any(math.hypot(x - fx, z - fz) < 170 for fx, fz in _SPOTS):
                continue
            if float(normal_at(x, z)[1]) < 0.85:
                continue
            _SPOTS.append((x, z))
    return _SPOTS


# Static scenery drawn with the game's own models from gameplay_field_keep (always loaded here, segment 5).
# Base models: (display list, scale the game's actors draw them at).
DECOR_KINDS = {
    # the bush, recolored to glow Sheikah blue at build time (link_level_assets.py); without the ROM's assets
    # ANCIENT_GLOW_BUSH_DL is the game's own bush
    "bush": ("ANCIENT_GLOW_BUSH_DL", 0.4),
    "pebble": ("gFieldKakeraDL", 0.1),
    "rock": ("gSilverRockDL", 0.4),
    "flower": ("gHanaDL", 0.01),
    "green_bush": ("gFieldBushDL", 0.4),  # the game's bush as it is (the floating island)
}
# Groups of models drawn with one matrix (so hundreds of bushes cost little memory): (kind, dx, dz, size, yaw)
PATTERNS = {
    "bush": [("bush", 0, 0, 1.1, 0.0)],
    "bush_row": [("bush", -84, 5, 0.95, 0.3), ("bush", -28, -6, 1.1, 1.9), ("bush", 28, 7, 1.0, 4.1), ("bush", 84, -4, 0.9, 5.2)],
    "bush_clump": [("bush", 0, 0, 1.2, 0.0), ("bush", 36, 24, 0.85, 2.0), ("bush", -32, 28, 0.9, 4.0), ("bush", 8, -34, 0.8, 5.0)],
    "flower_bed": [("flower", 0, 0, 1.0, 0.0), ("flower", 24, 15, 1.0, 1.0), ("flower", -22, 17, 1.0, 2.0), ("flower", 6, -24, 1.0, 3.0)],
    "pebbles": [("pebble", 0, 0, 1.3, 0.0), ("pebble", 28, 11, 0.8, 1.5), ("pebble", -13, 26, 1.0, 3.0)],
    "rock": [("rock", 0, 0, 1.0, 0.0)],
    "green_row": [("green_bush", -84, 5, 0.95, 0.3), ("green_bush", -28, -6, 1.1, 1.9), ("green_bush", 28, 7, 1.0, 4.1),
                  ("green_bush", 84, -4, 0.9, 5.2)],
    "green_clump": [("green_bush", 0, 0, 1.2, 0.0), ("green_bush", 36, 24, 0.85, 2.0), ("green_bush", -32, 28, 0.9, 4.0),
                    ("green_bush", 8, -34, 0.8, 5.0), ("flower", 50, -20, 1.0, 1.0), ("flower", -46, -18, 1.0, 2.5)],
}
PATTERN_R = {"bush": 32, "bush_row": 112, "bush_clump": 60, "flower_bed": 40, "pebbles": 40, "rock": 50, "green_row": 112,
             "green_clump": 70}
DECOR = []  # (pattern, x, y, z, yaw radians, size)


def build_decor():
    """Glowing bushes, flower beds and rocks around the houses, along every street and road, in the field and
    on the floating island."""
    drng = np.random.default_rng(31)
    px, pz = pool_center()
    ang_in = float(path_angle(0, 3260))
    eye_c = np.array([math.sin(ang_in) * 3260 + math.cos(ang_in) * 640, math.cos(ang_in) * 3260 - math.sin(ang_in) * 640])

    def free(pat, x, z, street_gap=8):
        rad = PATTERN_R[pat]
        if float(path_dist(x, z)) < 112 + rad * 0.7 or street_dist(x, z) < street_gap:
            return False
        if any(math.hypot(x - p["x"], z - p["z"]) < p["r"] + 10 for p in town_plan.PLOTS):
            return False
        if math.hypot(x - px, z - pz) < POOL_R + rad or math.hypot(x - eye_c[0], z - eye_c[1]) < 300 + rad:
            return False
        if math.hypot(x - SPAWN[0], z - SPAWN[1]) < 160 or math.hypot(x, z) < 980:
            return False
        return all(math.hypot(x - d[1], z - d[3]) >= rad + PATTERN_R[d[0]] * 0.8 for d in DECOR)

    def put(pat, x, z, yaw=None, size=1.0, y=None, check=True):
        if check and not free(pat, x, z):
            return False
        yaw = drng.random() * 2 * math.pi if yaw is None else yaw
        DECOR.append((pat, x, mesh_height(x, z) if y is None else y, z, yaw, size))
        return True

    for p in town_plan.PLOTS:
        face = p["face"]
        x0, z0, r = p["x"], p["z"], p["r"]
        # a hedge along the back, clumps at the back corners, flower beds by the front corners, stones
        for k in (-1, 0, 1):
            a = face + math.pi + k * 0.42
            put("bush_row", x0 + math.sin(a) * (r + 60), z0 + math.cos(a) * (r + 60), yaw=a + math.pi / 2)
        for sgn in (-1, 1):
            a = face + math.pi + sgn * 1.25
            put("bush_clump", x0 + math.sin(a) * (r + 55), z0 + math.cos(a) * (r + 55))
            a = face + sgn * 0.72
            put("flower_bed", x0 + math.sin(a) * (r * 0.8 + 40), z0 + math.cos(a) * (r * 0.8 + 40))
        a = drng.random() * 2 * math.pi
        put("pebbles", x0 + math.sin(a) * (r + 40), z0 + math.cos(a) * (r + 40))
        if p["ring"] == "outer":
            a = face + math.pi + drng.normal(0, 0.5)
            if put("rock", x0 + math.sin(a) * (r + 150), z0 + math.cos(a) * (r + 150), size=0.9 + drng.random() * 0.3):
                x, y, z = DECOR[-1][1:4]
                prism_col((x, y, z), 46, y - 20, y + 60, 8, SURF_STONE)
    # hedges of glowing bushes along both sides of every street, flowers between
    for line in town_plan.lanes():
        for (x0, z0), (x1, z1) in zip(line[:-1], line[1:]):
            ln = math.hypot(x1 - x0, z1 - z0)
            if ln < 1:
                continue
            ux, uz = (x1 - x0) / ln, (z1 - z0) / ln
            n = int(ln // 250)
            for k in range(n):
                t = (k + 0.5) / max(n, 1)
                cx, cz = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
                for sgn in (-1, 1):
                    off = town_plan.LANE_HALF + 46
                    put("bush_row" if k % 3 != 2 else "flower_bed", cx + uz * sgn * off, cz - ux * sgn * off,
                        yaw=math.atan2(ux, uz) + math.pi / 2)
    # the ring road's outer edge
    for k in range(40):
        a = 2 * math.pi * (k + 0.5) / 40
        rr = town_plan.RING_ROAD_R + town_plan.LANE_HALF + 70
        put("bush_row" if k % 2 else "bush_clump", math.sin(a) * rr, math.cos(a) * rr, yaw=a + math.pi / 2)
    # the four roads, both sides, in and out of town
    for kp in range(4):
        for r in np.arange(1250, 3700, 230):
            ang = float(path_angle(kp, r))
            for sgn in (-1, 1):
                off = PATH_HALF_WIDTH + 90
                x = math.sin(ang) * r + math.cos(ang) * sgn * off
                z = math.cos(ang) * r - math.sin(ang) * sgn * off
                if kp == 0 and 2950 < r < 3560:
                    continue  # the obelisks line the road there
                put("bush_clump" if int(r / 230) % 2 else "bush_row", x, z, yaw=ang + math.pi / 2)
    # the field: clumps where Hyrule Field's bushes were, its rocks
    for i, (x, z) in enumerate(field_spots()):
        if 20 <= i < 38:
            put("bush_clump", x, z, size=1.0 + drng.random() * 0.3)
        elif 38 <= i < 59:
            if i < 52:
                put("pebbles", x, z, size=1.0 + drng.random() * 0.5)
            elif put("rock", x, z, size=0.9 + drng.random() * 0.4):
                xx, y, zz = DECOR[-1][1:4]
                prism_col((xx, y, zz), 46, y - 20, y + 60, 8, SURF_STONE)
    # the floating island and the islet: the game's own green bushes, flowers and stones around the edge (the chest
    # and trees stand in the middle: island_actors())
    rim, d = waterfall_spot()
    wf = math.atan2(d[0], d[2])
    for k in range(12):
        a = wf + 0.45 + k * (2 * math.pi - 0.9) / 11
        rr = ISLAND["r"] * (0.8 if k % 2 else 0.62)
        put(("green_clump", "green_row", "pebbles", "green_clump")[k % 4], ISLAND["x"] + math.sin(a) * rr,
            ISLAND["z"] + math.cos(a) * rr, yaw=a + math.pi / 2, y=ISLAND["top"], check=False)
    for k in range(4):
        a = k * math.pi / 2 + 0.6
        put("green_clump", ISLET["x"] + math.sin(a) * ISLET["r"] * 0.62, ISLET["z"] + math.cos(a) * ISLET["r"] * 0.62,
            y=ISLET["top"], check=False, size=0.85)


def decor_mtx(x, y, z, yaw, scale, scale_y=None):
    """The 16 words of an N64 Mtx (s15.16, integer parts then fractions) for scale, turn about Y, move."""
    c, s_ = math.cos(yaw) * scale, math.sin(yaw) * scale
    mf = [[c, 0, -s_, 0], [0, scale if scale_y is None else scale_y, 0, 0], [s_, 0, c, 0], [x, y, z, 1]]
    fixed = [int(round(mf[i][j] * 65536)) & 0xFFFFFFFF for i in range(4) for j in range(4)]
    ints = [(v >> 16) & 0xFFFF for v in fixed]
    fracs = [v & 0xFFFF for v in fixed]
    return [(ints[k] << 16) | ints[k + 1] for k in range(0, 16, 2)] + [(fracs[k] << 16) | fracs[k + 1] for k in range(0, 16, 2)]


def mtx_text(m):
    return "    { { " + ", ".join("{ " + ", ".join(f"0x{w:08X}" for w in m[r * 4:(r + 1) * 4]) + " }" for r in range(4)) + " } },\n"


DECOR_SETUP = ["gsDPPipeSync()", "gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON)",
               "gsDPSetCombineMode(G_CC_MODULATEIDECALA, G_CC_MODULATEIA_PRIM2)",
               "gsDPSetOtherMode(G_AD_NOTPATTERN | G_CD_MAGICSQ | G_CK_NONE | G_TC_FILT | G_TF_BILERP | G_TT_NONE | G_TL_TILE | "
               "G_TD_CLAMP | G_TP_PERSP | G_CYC_2CYCLE | G_PM_NPRIMITIVE, G_AC_NONE | G_ZS_PIXEL | G_RM_FOG_SHADE_A | G_RM_AA_ZB_OPA_SURF2)",
               "gsSPLoadGeometryMode(G_ZBUFFER | G_SHADE | G_CULL_BACK | G_FOG | G_LIGHTING | G_SHADING_SMOOTH)",
               "gsDPSetPrimColor(0, 0, 255, 255, 255, 255)"]  # SETUPDL_25, as the actors draw them


def emit_decor():
    """Matrices, display lists (each group once, then one per quarter placing them) and room entries for DECOR."""
    lines, entries, decl = [], [], []
    if not DECOR:
        return lines, entries, decl
    used = sorted({d[0] for d in DECOR}, key=list(PATTERNS).index)
    lines.append("// static scenery: the game's own bush, flower and rock models (gameplay_field_keep, segment 5)\n" +
                 "".join(f"extern Gfx {sym}[];\n" for sym, _ in DECOR_KINDS.values() if sym.startswith("g")) + "\n")
    pmtx, pdl = [], []
    for pat in used:
        cmds = []
        for kind, dx, dz, size, yaw in PATTERNS[pat]:
            pmtx.append(decor_mtx(dx, 0, dz, yaw, DECOR_KINDS[kind][1] * size))
            cmds += [f"gsSPMatrix(&{ROOM}DecorPatternMtx[{len(pmtx) - 1}], G_MTX_PUSH | G_MTX_MUL | G_MTX_MODELVIEW)",
                     f"gsSPDisplayList({DECOR_KINDS[kind][0]})", "gsSPPopMatrix(G_MTX_MODELVIEW)"]
        pdl.append(f"Gfx {ROOM}DL_decor_{pat}[] = {{\n" + "".join(f"    {c},\n" for c in cmds) + "    gsSPEndDisplayList(),\n};\n\n")
    lines.append(f"Mtx {ROOM}DecorPatternMtx[{len(pmtx)}] = {{\n" + "".join(mtx_text(m) for m in pmtx) + "};\n\n")
    lines.append(f"Mtx {ROOM}DecorMtx[{len(DECOR)}] = {{\n" + "".join(
        mtx_text(decor_mtx(d[1], d[2], d[3], d[4], d[5])) for d in DECOR) + "};\n\n")
    lines += pdl
    for q in range(4):
        idx = [i for i, d in enumerate(DECOR)
               if int(((math.atan2(d[1], d[3]) % (2 * math.pi)) // (math.pi / 2))) == q]
        if not idx:
            continue
        cmds = []
        # the field keep's models first (they share one setup), then the bushes (the glowing one sets its own)
        for pat in sorted(used, key=lambda p_: PATTERNS[p_][0][0] == "bush"):
            items = [i for i in idx if DECOR[i][0] == pat]
            if not items:
                continue
            cmds += DECOR_SETUP
            for i in items:
                cmds += [f"gsSPMatrix(&{ROOM}DecorMtx[{i}], G_MTX_PUSH | G_MTX_MUL | G_MTX_MODELVIEW)",
                         f"gsSPDisplayList({ROOM}DL_decor_{pat})", "gsSPPopMatrix(G_MTX_MODELVIEW)"]
        name = f"{ROOM}DL_decor_{q}"
        lines.append(f"Gfx {name}[] = {{\n" + "".join(f"    {c},\n" for c in cmds) + "    gsSPEndDisplayList(),\n};\n\n")
        pts = np.array([[DECOR[i][1], DECOR[i][2], DECOR[i][3]] for i in idx])
        c = (pts.min(0) + pts.max(0)) / 2
        rad = float(np.max(np.linalg.norm(pts - c, axis=1))) + 160
        entries.append((tuple(int(round(v)) for v in c), int(math.ceil(rad)), name, "NULL"))
        decl.append(f"extern Gfx {name}[];")
    return lines, entries, decl


def town_people(add, yaw_to):
    """The townspeople and animals (see tools/remix/town_plan.py for the buildings). Params from the actors' code:
    En_Hy townspeople have no gravity, so they stand exactly on the ground; path index 0 is town_path()."""

    def hy(kind, x, z, y=None, face=None, path=0xF):
        y = mesh_height(x, z) if y is None else y
        add("ACTOR_EN_HY", x, y, z, yaw_to(x, z, *(face or (0, 0))), f"({kind} | ({path} << 7))")

    def at(r, deg):
        a = math.radians(deg)
        return math.sin(a) * r, math.cos(a) * r

    # on the plaza, around the Spire (between the Armos at 45-degree points and the stairs at the paths)
    # two men chatting (the Market's haggling pair needs a 43 KB object: that memory went to the scenery)
    x, z = at(720, 20)
    x2, z2 = at(720, 30)
    hy("ENHY_TYPE_MAN_1_BOWL_CUT_GREEN_SHIRT", x, z, y=PLAZA_Y, face=(x2, z2))
    hy("ENHY_TYPE_MAN_2_BALD", x2, z2, y=PLAZA_Y, face=(x, z))
    hy("ENHY_TYPE_MAN_1_BOWL_CUT_PURPLE_SHIRT", *at(720, 200), y=PLAZA_Y)
    hy("ENHY_TYPE_BEGGAR", *at(720, 250), y=PLAZA_Y)  # sits; buys bottled fish, bugs and blue fire
    hy("ENHY_TYPE_MAN_1_BEARD", *at(720, 292), y=PLAZA_Y)
    hy("ENHY_TYPE_MAN_2_MUSTACHE_RED_SHIRT", *at(720, 338), y=PLAZA_Y)
    # strolling around the plaza, and the town's two dogs
    hy("ENHY_TYPE_MAN_2_BALD", *at(TOWN_PATH_R, 11.25), path=0)
    for k, params in enumerate(("0x0000", "0x0101")):  # dog ids 1 and 2, path 0, cream and brown
        x, z = at(TOWN_PATH_R, 101.25 + 180 * k)
        add("ACTOR_EN_DOG", x, mesh_height(x, z) + 5, z, 0, params)
    # in front of the houses, talking toward the plaza
    for (kind, plot) in (("ENHY_TYPE_MAN_2_MUSTACHE_BLUE_SHIRT", 0), ("ENHY_TYPE_MAN_1_SHAVED_BLACK_SHIRT", 1),
                         ("ENHY_TYPE_MAN_2_ALT_MUSTACHE", 5), ("ENHY_TYPE_MAN_1_SHAVED_GREEN_SHIRT", 6),
                         ("ENHY_TYPE_MAN_2_MUSTACHE_WHITE_SHIRT", 10), ("ENHY_TYPE_MAN_2_BEARD", 16)):
        p = town_plan.PLOTS[plot]
        d = p["r"] + 90
        x, z = p["x"] + math.sin(p["face"]) * d, p["z"] + math.cos(p["face"]) * d
        hy(kind, x, z)
    # pots with rupees inside the houses (each with its own collectible flag, so every one pays once)
    flag = 1
    for plot in (0, 1, 5, 6, 15):
        p = town_plan.PLOTS[plot]
        for k, item in enumerate(("ITEM00_RUPEE_BLUE", "ITEM00_RUPEE_RED" if plot in (1, 15) else "ITEM00_RUPEE_GREEN")):
            a = p["face"] + math.pi / 2 + k * math.pi
            x, z = p["x"] + math.sin(a) * 70, p["z"] + math.cos(a) * 70
            add("ACTOR_OBJ_TSUBO", x, mesh_height(x, z), z, 0, f"(0x0100 | {item} | ({flag} << 9))")
            flag += 1


# ---------------------------------------------------------------- textures


def write_indexed_png(path, idx, palette, trns=None):
    """8-bit indexed PNG (what build_from_png expects for CI textures)."""
    h, w = idx.shape
    raw = b"".join(b"\x00" + bytes(row) for row in idx.astype(np.uint8))

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0))
    png += chunk(b"PLTE", bytes(int(c) for rgb in palette for c in rgb))
    if trns is not None:
        png += chunk(b"tRNS", bytes(trns))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def make_textures():
    for key, (stem, fmt, (w, h)) in TEXTURES.items():
        if key == "glow":
            img = glow_texture(w, h)
            Image.fromarray(img, "L").save(OUT / f"{stem}.i8.png")
            continue
        if key == "eye":
            Image.fromarray(eye_texture(w), "L").save(OUT / f"{stem}.i8.png")
            continue
        if key == "water":
            Image.fromarray(water_texture(w, h), "RGBA").save(OUT / f"{stem}.rgba16.png")
            continue
        if key == "town_ground":  # stand-in for the game texture link_level_assets.py picks: darker, mossier grass
            g = np.array(Image.open(ART / "grass.png").convert("RGB").resize((w, h), Image.LANCZOS)).astype(float)
            lum = g.mean(-1, keepdims=True)
            g = (lum + (g - lum) * 0.55) * np.array([0.72, 0.8, 0.82])
            Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert("RGBA").save(OUT / f"{stem}.rgba16.png")
            continue
        src = Image.open(ART / f"{key}.png").convert("RGB").resize((w, h), Image.LANCZOS)
        if key == "grass":  # a touch less saturated, closer to the game's fields
            g = np.array(src).astype(float)
            lum = g.mean(-1, keepdims=True)
            src = Image.fromarray(np.clip((lum + (g - lum) * 0.82) * 0.96, 0, 255).astype(np.uint8))
        if fmt == "rgba16":
            src.convert("RGBA").save(OUT / f"{stem}.rgba16.png")
        else:
            q = src.quantize(16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
            pal = np.array(q.getpalette()[: 16 * 3], dtype=np.uint8).reshape(-1, 3)
            if len(pal) < 16:
                pal = np.vstack([pal, np.zeros((16 - len(pal), 3), np.uint8)])
            write_indexed_png(OUT / f"{stem}.ci4.png", np.array(q), pal)
    title_card()


def glow_texture(w, h):
    t = np.arange(h)[:, None] + 0.5
    u = np.arange(w)[None, :] + 0.5
    c = h / 2
    across = 1.0 * np.exp(-(((t - c) / 2.4) ** 2)) + 0.42 * np.exp(-(((t - c) / 7.0) ** 2))
    along = 0.58 + 0.42 * np.exp(-(((u - 6) / 3.2) ** 2)) + 0.42 * np.exp(-(((u - 6 - w) / 3.2) ** 2))
    v = np.clip(across * along, 0, 1)
    return np.round(v * 255).astype(np.uint8)


def water_texture(w, h):
    """Falling water: streaks along t (the waterfall scrolls it down), light foam on blue-green."""
    r = np.random.default_rng(5)
    u = np.arange(w)[None, :]
    t = np.arange(h)[:, None]
    streaks = np.zeros((h, w))
    for _ in range(9):
        c, wd, ph = r.random() * w, 0.8 + r.random() * 1.6, r.random() * 2 * np.pi
        d = np.minimum(np.abs(u - c), w - np.abs(u - c))
        streaks += np.exp(-((d / wd) ** 2)) * (0.6 + 0.4 * np.sin(2 * np.pi * t / h * 2 + ph))
    v = np.clip(0.35 + 0.5 * streaks / streaks.max(), 0, 1)
    rgb = np.stack([60 + 170 * v, 130 + 120 * v, 160 + 95 * v], -1)
    a = np.full((h, w, 1), 255.0)
    return np.clip(np.concatenate([rgb, a], -1), 0, 255).astype(np.uint8)


def eye_texture(size):
    """The Sheikah eye: an eye with three lashes and a tear, drawn big then shrunk."""
    S = 512
    img = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(img)
    cx, cy = S / 2, S * 0.47
    ew, eh = S * 0.38, S * 0.2
    top = [(cx + ew * math.cos(a), cy - eh * math.sin(a)) for a in np.linspace(0, math.pi, 40)]
    bot = [(cx - ew * math.cos(a), cy + eh * 0.9 * math.sin(a)) for a in np.linspace(0, math.pi, 40)]
    d.line(top + bot + [top[0]], fill=255, width=26, joint="curve")
    d.ellipse([cx - S * 0.1, cy - S * 0.1, cx + S * 0.1, cy + S * 0.1], fill=255)
    for a in (-0.55, 0.0, 0.55):
        x0, y0 = cx + math.sin(a) * eh * 1.25, cy - eh * 1.15
        x1, y1 = cx + math.sin(a) * eh * 2.1, cy - eh * 2.05
        d.line([(x0, y0), (x1, y1)], fill=255, width=24)
    tx, ty = cx, cy + eh * 1.35
    d.polygon([(tx, ty), (tx - S * 0.06, ty + S * 0.13), (tx + S * 0.06, ty + S * 0.13)], fill=255)
    d.ellipse([tx - S * 0.06, ty + S * 0.08, tx + S * 0.06, ty + S * 0.2], fill=255)
    return np.array(img.resize((size, size), Image.LANCZOS))


def title_card():
    """'Ancient Plateau' place-name card (IA8 144x24), like the game's own."""
    W, H, SS = 144, 24, 4
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 17 * SS)
    text = "Ancient Plateau"
    big = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(big)
    bbox = d.textbbox((0, 0), text, font=font)
    x = (W * SS - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = (H * SS - (bbox[3] - bbox[1])) / 2 - bbox[1]
    d.text((x, y), text, font=font, fill=255)
    mask = np.array(big.resize((W, H), Image.LANCZOS)).astype(float) / 255
    # shadow: the mask blurred and offset, drawn dark under the white letters
    shadow = np.zeros_like(mask)
    shadow[1:, 1:] = mask[:-1, :-1]
    shadow = np.maximum(shadow, mask)
    alpha = np.clip(np.maximum(mask, shadow * 0.8), 0, 1)
    inten = np.where(alpha > 0, mask / np.maximum(alpha, 1e-6), 0)
    la = np.stack([np.round(inten * 255), np.round(alpha * 255)], -1).astype(np.uint8)
    Image.fromarray(la, "LA").save(OUT / "ancient_title.ia8.png")


# ---------------------------------------------------------------- display lists


def s8(v):
    return int(max(-127, min(127, round(v * 127)))) & 0xFF


def batch_triangles(tris, mat):
    """Split triangles into F3DEX2 loads of at most 32 vertices, with UVs kept small per load."""
    w, h = mat.size if mat.tex else (32, 32)
    batches = []
    cur, keys, off = [], {}, None
    for t in tris:
        uvs = [v[1] for v in t]
        if off is None:
            off = (math.floor(min(u for u, _ in uvs) / w) * w, math.floor(min(v for _, v in uvs) / h) * h)
        fits = all(abs(u - off[0]) < 900 and abs(v - off[1]) < 900 for u, v in uvs)
        new = [v for v in t if v not in keys]
        if not fits or len(keys) + len(set(new)) > 32:
            batches.append((cur, list(keys), off))
            cur, keys = [], {}
            off = (math.floor(min(u for u, _ in uvs) / w) * w, math.floor(min(v for _, v in uvs) / h) * h)
        for v in t:
            if v not in keys:
                keys[v] = len(keys)
        cur.append(tuple(keys[v] for v in t))
    if cur:
        batches.append((cur, list(keys), off))
    return batches


def material_setup(mat):
    g = []
    lit = mat.lit
    geo = "G_ZBUFFER | G_SHADE | G_CULL_BACK | G_FOG | G_SHADING_SMOOTH" + (" | G_LIGHTING" if lit else "")
    tt = "G_TT_RGBA16" if (mat.fmt == "ci4") else "G_TT_NONE"
    rm = "G_RM_AA_ZB_XLU_SURF2" if mat.xlu else "G_RM_AA_ZB_OPA_SURF2"
    g.append("gsDPPipeSync()")
    g.append(f"gsDPSetOtherMode(G_AD_NOISE | G_CD_MAGICSQ | G_CK_NONE | G_TC_FILT | G_TF_BILERP | {tt} | G_TL_TILE | "
             f"G_TD_CLAMP | G_TP_PERSP | G_CYC_2CYCLE | G_PM_NPRIMITIVE, G_AC_NONE | G_ZS_PIXEL | G_RM_FOG_SHADE_A | {rm})")
    g.append(f"gsSPLoadGeometryMode({geo})")
    if mat.combine == "water":  # texture times vertex color, see-through by the primitive alpha
        g.append("gsDPSetCombineLERP(TEXEL0, 0, SHADE, 0, 0, 0, 0, PRIMITIVE, 0, 0, 0, COMBINED, 0, 0, 0, COMBINED)")
    elif mat.xlu:
        g.append("gsDPSetCombineLERP(0, 0, 0, PRIMITIVE, TEXEL0, 0, PRIMITIVE, 0, 0, 0, 0, COMBINED, 0, 0, 0, COMBINED)")
    elif mat.tex:
        g.append("gsDPSetCombineLERP(TEXEL0, 0, SHADE, 0, 0, 0, 0, 1, COMBINED, 0, PRIMITIVE, 0, 0, 0, 0, 1)")
    else:
        g.append("gsDPSetCombineLERP(0, 0, 0, SHADE, 0, 0, 0, 1, COMBINED, 0, PRIMITIVE, 0, 0, 0, 0, 1)")
    if mat.tex:
        stem, fmt, (w, h) = TEXTURES[mat.tex]
        g.append("gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON)")
        ms, mt = int(math.log2(w)), int(math.log2(h))
        cmt = "G_TX_NOMIRROR | G_TX_CLAMP" if mat.clamp_t else "G_TX_NOMIRROR | G_TX_WRAP"
        sym = tex_symbol(mat.tex)
        if fmt == "ci4":
            g.append(f"gsDPLoadTLUT_pal16(0, {tlut_symbol(mat.tex)})")
            g.append(f"gsDPLoadTextureBlock_4b({sym}, G_IM_FMT_CI, {w}, {h}, 0, G_TX_NOMIRROR | G_TX_WRAP, {cmt}, "
                     f"{ms}, {mt}, G_TX_NOLOD, G_TX_NOLOD)")
        else:
            imfmt, siz = {"rgba16": ("G_IM_FMT_RGBA", "G_IM_SIZ_16b"), "i8": ("G_IM_FMT_I", "G_IM_SIZ_8b")}[fmt]
            g.append(f"gsDPLoadTextureBlock({sym}, {imfmt}, {siz}, {w}, {h}, 0, G_TX_NOMIRROR | G_TX_WRAP, {cmt}, "
                     f"{ms}, {mt}, G_TX_NOLOD, G_TX_NOLOD)")
        if mat.scroll:
            g.append(f"gsSPDisplayList(0x{0x0D if mat.scroll is True else mat.scroll:02X}000000)")
    else:
        g.append("gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_OFF)")
    if mat.prim_seg is not None:
        g.append(f"gsSPDisplayList(0x{mat.prim_seg:02X}000000)")
    else:
        r, gg, b, a = mat.prim
        g.append(f"gsDPSetPrimColor(0, 0, {r}, {gg}, {b}, {a})")
    return g


def tex_symbol(key):
    return f"{ROOM}Tex_{key}"


def tlut_symbol(key):
    return f"{ROOM}TLUT_{key}"


def emit_room():
    vtx_out, dl_out, entries_out = [], [], []
    decl = []
    INST_MTX.clear()
    for e in MESHES + ENTRIES:
        dls = {}
        for xlu in (False, True):
            groups = [(m, t) for m, t in e.groups.items() if m.xlu == xlu]
            if not groups and (xlu or not e.instances):
                continue
            vname = f"{ROOM}Vtx_{e.name}_{'xlu' if xlu else 'opa'}"
            dname = f"{ROOM}DL_{e.name}_{'xlu' if xlu else 'opa'}"
            verts, cmds = [], []
            if e.matrix_seg is not None:
                cmds.append(f"gsSPMatrix(0x{e.matrix_seg:02X}000000, G_MTX_PUSH | G_MTX_MUL | G_MTX_MODELVIEW)")
            for mat, tris in groups:
                cmds += material_setup(mat)
                for btris, bverts, off in batch_triangles(tris, mat):
                    start = len(verts)
                    for (p, uv, nc) in bverts:
                        s = int(round((uv[0] - off[0]) * 32))
                        t = int(round((uv[1] - off[1]) * 32))
                        if mat.lit:
                            c = (s8(nc[0]), s8(nc[1]), s8(nc[2]), 255)
                        else:
                            c = tuple(int(x) for x in nc)
                        verts.append((int(round(p[0])), int(round(p[1])), int(round(p[2])), s, t) + c)
                    cmds.append(f"gsSPVertex(&{vname}[{start}], {len(bverts)}, 0)")
                    for i in range(0, len(btris), 2):
                        a = btris[i]
                        if i + 1 < len(btris):
                            b = btris[i + 1]
                            cmds.append(f"gsSP2Triangles({a[0]}, {a[1]}, {a[2]}, 0, {b[0]}, {b[1]}, {b[2]}, 0)")
                        else:
                            cmds.append(f"gsSP1Triangle({a[0]}, {a[1]}, {a[2]}, 0)")
            if not xlu:
                for inst in e.instances:
                    INST_MTX.append(decor_mtx(inst[1], inst[2], inst[3], inst[4], inst[5], inst[6]))
                    cmds += [f"gsSPMatrix(&{ROOM}InstMtx[{len(INST_MTX) - 1}], G_MTX_PUSH | G_MTX_MUL | G_MTX_MODELVIEW)",
                             f"gsSPDisplayList({ROOM}DL_{inst[0].name}_opa)", "gsSPPopMatrix(G_MTX_MODELVIEW)"]
            if e.matrix_seg is not None:
                cmds.append("gsSPPopMatrix(G_MTX_MODELVIEW)")
            cmds.append("gsSPEndDisplayList()")
            for v in verts:
                assert all(-32768 <= c <= 32767 for c in v[:5]), (e.name, v)
            if verts:
                vtx_out.append(f"Vtx {vname}[{len(verts)}] = {{\n" +
                               "".join(f"    VTX({v[0]}, {v[1]}, {v[2]}, {v[3]}, {v[4]}, 0x{v[5]:02X}, 0x{v[6]:02X}, 0x{v[7]:02X}, 0x{v[8]:02X}),\n"
                                       for v in verts) + "};\n")
                decl.append(f"extern Vtx {vname}[{len(verts)}];")
            dl_out.append(f"Gfx {dname}[] = {{\n" + "".join(f"    {c},\n" for c in cmds) + "};\n")
            decl.append(f"extern Gfx {dname}[];")
            dls[xlu] = dname
        if e in MESHES:
            continue
        if e.sphere:
            center, radius = e.sphere
        else:
            pts = e.positions()
            for inst in e.instances:
                f = inst_transform(inst)
                pts = pts + [f(p) for p in inst[0].positions()]
            pts = np.array(pts)
            lo, hi = pts.min(0), pts.max(0)
            center = (lo + hi) / 2
            radius = float(np.max(np.linalg.norm(pts - center, axis=1)))
        entries_out.append((tuple(int(round(c)) for c in center), int(math.ceil(radius)) + 8,
                            dls.get(False, "NULL"), dls.get(True, "NULL")))
    assert len(entries_out) <= 64, len(entries_out)
    if INST_MTX:
        vtx_out.insert(0, f"Mtx {ROOM}InstMtx[{len(INST_MTX)}] = {{\n" + "".join(mtx_text(m) for m in INST_MTX) + "};\n")
    return vtx_out, dl_out, entries_out, decl


def emit_collision():
    vid = {}
    verts = []
    polys = []
    for p0, p1, p2, surf, flags in COL_TRIS:
        ids = []
        q = []
        for p in (p0, p1, p2):
            key = tuple(int(round(c)) for c in p)
            if key not in vid:
                vid[key] = len(verts)
                verts.append(key)
            ids.append(vid[key])
            q.append(np.array(key, float))
        n = np.cross(q[1] - q[0], q[2] - q[0])
        ln = np.linalg.norm(n)
        if ln < 1e-3 or len(set(ids)) < 3:
            continue
        n = n / ln
        dist = int(round(-np.dot(n, q[0])))
        polys.append((surf, ids, [int(round(c * 0x7FFF)) for c in n], dist, flags))
    assert len(verts) < 0x2000, len(verts)
    arr = np.array(verts)
    return verts, polys, arr.min(0), arr.max(0)


def tri_box_overlap(tri, bmin, bmax):
    """Separating-axis test: does the triangle touch the box?"""
    c = (bmin + bmax) / 2
    h = (bmax - bmin) / 2
    v = tri - c
    e = [v[1] - v[0], v[2] - v[1], v[0] - v[2]]
    axes = [np.array(a, float) for a in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    n = np.cross(e[0], e[1])
    tests = axes + [n] + [np.cross(a, ed) for a in axes for ed in e]
    for ax in tests:
        if not ax.any():
            continue
        p = v @ ax
        r = np.abs(ax) @ h
        if p.min() > r or p.max() < -r:
            return False
    return True


def bgcheck_memsize(verts, polys, lo, hi):
    """Collision memory this scene needs (see BgCheck_Allocate): fixed part plus one SSNode per poly per
    subdivision its bounding box touches (an upper bound on what the game allocates)."""
    amt = (16, 4, 16)
    length = []
    for a in range(3):
        ln = max(int((hi[a] - lo[a]) / amt[a]) + 1, 150)
        length.append(ln)
    nodes = 0
    for _, ids, _, _, _ in polys:
        pts = np.array([verts[i] for i in ids], float)
        mn, mx = pts.min(0) - 50, pts.max(0) + 50
        rng_ = []
        for a in range(3):
            s0 = min(max(int((mn[a] - lo[a]) / length[a]), 0), amt[a] - 1)
            s1 = min(max(int((mx[a] - lo[a]) / length[a]), 0), amt[a] - 1)
            rng_.append(range(s0, s1 + 1))
        for sx in rng_[0]:
            for sy in rng_[1]:
                for sz in rng_[2]:
                    bmin = np.array([lo[0] + sx * length[0], lo[1] + sy * length[1], lo[2] + sz * length[2]]) - 50
                    bmax = bmin + np.array(length) + 100
                    if tri_box_overlap(pts, bmin, bmax):
                        nodes += 1
    fixed = 16 * 4 * 16 * 6 + len(polys) + 1000 * 4 + 512 * 16 + 512 * 6 + 0x2000
    return (int(fixed + nodes * 4 * 1.12) + 0x800 + 0xFF) & ~0xFF, nodes


def write_sources():
    vtx_out, dl_out, entries, decl = emit_room()
    decor_lines, decor_entries, decor_decl = emit_decor()
    entries = entries + decor_entries
    decl = decl + decor_decl
    assert len(entries) <= 64 - 6, f"{len(entries)} room entries: the town needs up to 6 of the 64"
    acts = actors()
    hdr = "// Generated by tools/remix/make_level.py - the Ancient Plateau (Web Remix). Do not edit.\n"

    # ----- room
    tex_decl, tex_defs = [], []
    for key, (stem, fmt, size) in TEXTURES.items():
        if fmt == "ci4":
            tex_decl.append(f"extern u64 {tlut_symbol(key)}[];")
            tex_defs.append(f"u64 {tlut_symbol(key)}[] = {{\n#include \"{INC}/{stem}.tlut.rgba16.inc.c\"\n}};\n")
        tex_decl.append(f"extern u64 {tex_symbol(key)}[];")
        own = f'#include "{INC}/{stem}.{fmt}.inc.c"'
        if key in HF_TEXTURES:
            m = HF_TEXTURES[key]
            tex_defs.append(f"u64 {tex_symbol(key)}[] = {{\n#ifdef {m}\n#include {m}\n#else\n{own}\n#endif\n}};\n")
        else:
            tex_defs.append(f"u64 {tex_symbol(key)}[] = {{\n{own}\n}};\n")
    room_h = (hdr + f"#ifndef {ROOM.upper()}_H\n#define {ROOM.upper()}_H\n\n#include \"ultra64.h\"\n#include \"scene.h\"\n"
              f"#include \"room.h\"\n\nextern SceneCmd {ROOM}Commands[];\nextern s16 {ROOM}ObjectList[];\n"
              f"extern ActorEntry {ROOM}ActorList[];\nextern RoomShapeCullable {ROOM}RoomShape;\n"
              f"extern RoomShapeCullableEntry {ROOM}RoomShapeEntries[];\n\n"
              f"// Height of the Spire's floating ring and crystal (animated by z_remix_level.c)\n"
              f"#define ANCIENT_RING_Y {RING_Y}\n"
              f"// Center of the floating island (its circling rocks turn around it)\n"
              f"#define ANCIENT_ISLAND_X {round(ISLAND['x'])}\n#define ANCIENT_ISLAND_Y {ISLAND['top']}\n"
              f"#define ANCIENT_ISLAND_Z {round(ISLAND['z'])}\n"
              + view_defines() + "\n" + "\n".join(tex_decl) + "\n" + "\n".join(decl) +
              "\n\n#endif\n")
    lines = [hdr, f'#include "{ROOM}.h"\n#include "{INC}/ancient_hf.h"\n#include "{INC}/ancient_town.h"\n', '#include "actor.h"\n#include "array_count.h"\n#include "gfx.h"\n#include "object.h"\n'
             '#include "room.h"\n#include "scene.h"\n#include "sequence.h"\n#include "actor_profile.h"\n'
             '#include "src/overlays/actors/ovl_En_Ishi/z_en_ishi.h"\n'
             '#include "src/overlays/actors/ovl_En_Hy/z_en_hy.h"\n#include "z_en_item00.h"\n'
             '#include "src/overlays/actors/ovl_En_Box/z_en_box.h"\n'
             '#include "item.h"\n\n']
    lines.append("#ifndef ANCIENT_TOWN_ACTOR_COUNT\n#define ANCIENT_TOWN_ACTOR_COUNT 0\n#endif\n\n")
    lines.append(f"SceneCmd {ROOM}Commands[] = {{\n"
                 "    SCENE_CMD_ECHO_SETTINGS(0),\n"
                 "    SCENE_CMD_ROOM_BEHAVIOR(ROOM_TYPE_NORMAL, ROOM_ENV_DEFAULT, false, false),\n"
                 "    SCENE_CMD_SKYBOX_DISABLES(false, false),\n"
                 "    SCENE_CMD_TIME_SETTINGS(0xFF, 0xFF, 10),\n"
                 f"    SCENE_CMD_ROOM_SHAPE(&{ROOM}RoomShape),\n"
                 f"    SCENE_CMD_OBJECT_LIST({len(OBJECTS)}, {ROOM}ObjectList),\n"
                 f"    SCENE_CMD_ACTOR_LIST({len(acts)} + ANCIENT_TOWN_ACTOR_COUNT, {ROOM}ActorList),\n"
                 "    SCENE_CMD_END(),\n};\n\n")
    lines.append(f"s16 {ROOM}ObjectList[] = {{\n" + "".join(f"    {o},\n" for o in OBJECTS) + "};\n\n")
    lines.append(f"ActorEntry {ROOM}ActorList[] = {{\n" +
                 "".join(f"    {{ {a[0]}, {{ {a[1]}, {a[2]}, {a[3]} }}, {{ {a[4]}, 0x{a[5]:04X}, {a[6]} }}, {a[7]} }},\n"
                         for a in acts) +
                 "#ifdef ANCIENT_TOWN_ACTORS  // placed on the borrowed buildings (tools/remix/make_town.py)\n"
                 "#include ANCIENT_TOWN_ACTORS\n#endif\n};\n\n")
    # The town's buildings, borrowed from the game's towns at build time (tools/remix/make_town.py)
    lines.append("#ifdef ANCIENT_TOWN_ROOM\n#include ANCIENT_TOWN_ROOM\n#endif\n\n")
    lines.append("// The game's bush recolored to glow (tools/remix/link_level_assets.py), else the bush itself\n"
                 "#ifdef ANCIENT_GLOW_BUSH\n#include ANCIENT_GLOW_BUSH\n#else\nextern Gfx gFieldBushDL[];\n"
                 "#define ANCIENT_GLOW_BUSH_DL gFieldBushDL\n#endif\n\n")
    lines += decor_lines
    lines.append(f"RoomShapeCullableEntry {ROOM}RoomShapeEntries[] = {{\n" +
                 "".join(f"    {{ {{ {c[0]}, {c[1]}, {c[2]} }}, {r}, {o}, {x} }},\n" for c, r, o, x in entries) +
                 "#ifdef ANCIENT_TOWN_ENTRIES\n#include ANCIENT_TOWN_ENTRIES\n#endif\n};\n\n")
    lines.append(f"RoomShapeCullable {ROOM}RoomShape = {{\n    {{ ROOM_SHAPE_TYPE_CULLABLE }},\n"
                 f"    ARRAY_COUNT({ROOM}RoomShapeEntries),\n    {ROOM}RoomShapeEntries,\n"
                 f"    {ROOM}RoomShapeEntries + ARRAY_COUNT({ROOM}RoomShapeEntries),\n}};\n\n")
    lines += [t + "\n" for t in tex_defs]
    lines += [v + "\n" for v in vtx_out]
    lines += [d + "\n" for d in dl_out]
    (OUT / f"{ROOM}.h").write_text(room_h)
    (OUT / "ancient_hf.h").write_text(
        hdr + "// Builds without the ROM's assets use this empty version: the level then uses its own look-alike textures and\n"
        "// lights. With a ROM, tools/remix/link_level_assets.py writes build/VERSION/assets/scenes/remix/ancient/ancient_hf.h\n"
        "// (found first on the include path), which points them at Hyrule Field's own.\n"
        "#ifndef ANCIENT_HF_H\n#define ANCIENT_HF_H\n#endif\n")
    (OUT / "ancient_town.h").write_text(
        hdr + "// Builds without the ROM's assets use this empty version: no town buildings. With a ROM,\n"
        "// tools/remix/make_town.py writes build/VERSION/assets/scenes/remix/ancient/ancient_town.h (found first on the\n"
        "// include path) with the buildings it borrows from the game's towns.\n"
        "#ifndef ANCIENT_TOWN_H\n#define ANCIENT_TOWN_H\n#endif\n")
    (OUT / f"{ROOM}.c").write_text("".join(lines))

    # ----- scene
    verts, polys, lo, hi = emit_collision()
    memsize, nodes = bgcheck_memsize(verts, polys, lo, hi)
    sx, sz = SPAWN
    sy = int(math.ceil(mesh_height(sx, sz))) + 2
    scene_h = (hdr + f"#ifndef {SCENE.upper()}_H\n#define {SCENE.upper()}_H\n\n#include \"ultra64.h\"\n#include \"scene.h\"\n"
               f"#include \"bgcheck.h\"\n#include \"romfile.h\"\n#include \"path.h\"\n\nextern SceneCmd {SCENE}Commands[];\n"
               f"extern CollisionHeader {SCENE}CollisionHeader;\nextern RomFile {SCENE}RoomList[];\n"
               f"extern Spawn {SCENE}SpawnList[];\nextern ActorEntry {SCENE}PlayerEntryList[];\n"
               f"extern Path {SCENE}PathList[];\n"
               f"extern EnvLightSettings {SCENE}LightSettings[];\n\n"
               f"// Collision memory for BgCheck_Allocate ({len(polys)} polys, {nodes} lookup nodes)\n"
               f"#include \"{INC}/ancient_town.h\"\n#ifdef ANCIENT_TOWN_BGCHECK_MEMSIZE  // the town's collision needs more\n"
               "#define ANCIENT_SCENE_BGCHECK_MEMSIZE ANCIENT_TOWN_BGCHECK_MEMSIZE\n#else\n"
               f"#define ANCIENT_SCENE_BGCHECK_MEMSIZE 0x{memsize:X}\n#endif\n\n#endif\n")
    s = [hdr, f'#include "{SCENE}.h"\n#include "{ROOM}.h"\n#include "{INC}/ancient_hf.h"\n#include "{INC}/ancient_town.h"\n', '#include "array_count.h"\n#include "actor.h"\n#include "actor_profile.h"\n#include "camera.h"\n'
         '#include "environment.h"\n#include "object.h"\n#include "player.h"\n#include "save.h"\n#include "segment_symbols.h"\n'
         '#include "sequence.h"\n#include "skybox.h"\n#include "path.h"\n\n']
    # The commands must come first: the game reads them from the start of the scene file.
    s.append("// Hyrule Field's light settings when the ROM's assets are linked in (tools/remix/link_level_assets.py)\n"
             "#ifdef ANCIENT_HF_LIGHTS\n#define ANCIENT_LIGHTS_COUNT ANCIENT_HF_LIGHTS_COUNT\n#else\n"
             f"#define ANCIENT_LIGHTS_COUNT {LIGHTS_OWN}\n#endif\n\n")
    s.append(f"SceneCmd {SCENE}Commands[] = {{\n"
             "    SCENE_CMD_SOUND_SETTINGS(0, NATURE_ID_KOKIRI_REGION, NA_BGM_SHEIK),\n"
             f"    SCENE_CMD_ROOM_LIST(1, {SCENE}RoomList),\n"
             "    SCENE_CMD_MISC_SETTINGS(SCENE_CAM_TYPE_DEFAULT, WORLD_MAP_AREA_HYRULE_FIELD),\n"
             f"    SCENE_CMD_COL_HEADER(&{SCENE}CollisionHeader),\n"
             f"    SCENE_CMD_SPAWN_LIST({SCENE}SpawnList),\n"
             "    SCENE_CMD_SPECIAL_FILES(NAVI_QUEST_HINTS_OVERWORLD, OBJECT_GAMEPLAY_FIELD_KEEP),\n"
             f"    SCENE_CMD_PATH_LIST({SCENE}PathList),\n"
             f"    SCENE_CMD_PLAYER_ENTRY_LIST(1, {SCENE}PlayerEntryList),\n"
             "    SCENE_CMD_SKYBOX_SETTINGS(SKYBOX_NORMAL_SKY, 0, LIGHT_MODE_TIME),\n"
             f"    SCENE_CMD_ENV_LIGHT_SETTINGS(ANCIENT_LIGHTS_COUNT, {SCENE}LightSettings),\n"
             "    SCENE_CMD_END(),\n};\n\n")
    s.append(f"RomFile {SCENE}RoomList[] = {{\n    ROM_FILE({ROOM}),\n}};\n\n")
    path = town_path()
    s.append(f"// the walk around the plaza (path 0: the dogs and a stroller follow it)\nVec3s {SCENE}PathPoints0[] = {{\n"
             + "".join(f"    {{ {x}, {y}, {z} }},\n" for x, y, z in path) + "};\n\n"
             f"Path {SCENE}PathList[] = {{\n    {{ ARRAY_COUNT({SCENE}PathPoints0), {SCENE}PathPoints0 }},\n}};\n\n")
    s.append(f"Spawn {SCENE}SpawnList[] = {{\n    {{ 0, 0 }},\n}};\n\n")
    s.append(f"ActorEntry {SCENE}PlayerEntryList[] = {{\n    {{ ACTOR_PLAYER, {{ {sx}, {sy}, {sz} }}, {{ 0, 0x{SPAWN_YAW:04X}, 0 }}, "
             "PLAYER_PARAMS(PLAYER_START_MODE_MOVE_FORWARD_SLOW, PLAYER_START_BG_CAM_DEFAULT) },\n};\n\n")
    s.append(light_settings())
    # (the town's collision, borrowed at build time, is appended to each array: tools/remix/make_town.py)
    s.append(f"Vec3s {SCENE}CollisionVtx[] = {{\n" + "".join(f"    {{ {v[0]}, {v[1]}, {v[2]} }},\n" for v in verts) +
             "#ifdef ANCIENT_TOWN_COL_VTX\n#include ANCIENT_TOWN_COL_VTX\n#endif\n};\n\n")
    s.append(f"CollisionPoly {SCENE}CollisionPolys[] = {{\n" +
             "".join(f"    {{ {surf}, {{ COLPOLY_VTX({ids[0]}, {('COLPOLY_IGNORE_CAMERA' if flags else '0')}), COLPOLY_VTX({ids[1]}, 0), "
                     f"{ids[2]} }}, {{ {n[0]}, {n[1]}, {n[2]} }}, {dist} }},\n"
                     for surf, ids, n, dist, flags in polys) +
             "#ifdef ANCIENT_TOWN_COL_POLYS\n#include ANCIENT_TOWN_COL_POLYS\n#endif\n};\n\n")
    s.append(f"SurfaceType {SCENE}SurfaceTypes[] = {{\n" +
             "".join(f"    {{ {{ SURFACETYPE0(0, 0, FLOOR_TYPE_0, 0, WALL_TYPE_0, FLOOR_PROPERTY_0, false, {hb}), "
                     f"SURFACETYPE1({m}, FLOOR_EFFECT_0, 0, 0, {hk}, CONVEYOR_SPEED_DISABLED, 0, false) }} }},\n"
                     for m, hk, hb in SURFACES) +
             "#ifdef ANCIENT_TOWN_COL_SURFACES\n#include ANCIENT_TOWN_COL_SURFACES\n#endif\n};\n\n")
    s.append(f"BgCamInfo {SCENE}BgCamList[] = {{\n    {{ CAM_SET_NORMAL0, 0, NULL }},\n}};\n\n")
    s.append(f"// the pool under the island's waterfall\nWaterBox {SCENE}WaterBoxes[] = {{\n" + "".join(
        f"    {{ {int(round(x - h))}, {int(round(y))}, {int(round(z - h))}, {int(round(2 * h))}, {int(round(2 * h))}, "
        "WATERBOX_PROPERTIES(0, WATERBOX_LIGHT_INDEX_NONE, 0x3F, false) },\n" for x, y, z, h in WATERBOXES) + "};\n\n")
    s.append(f"CollisionHeader {SCENE}CollisionHeader = {{\n    {{ {lo[0]}, {lo[1]}, {lo[2]} }},\n    {{ {hi[0]}, {hi[1]}, {hi[2]} }},\n"
             f"    ARRAY_COUNT({SCENE}CollisionVtx),\n    {SCENE}CollisionVtx,\n    ARRAY_COUNT({SCENE}CollisionPolys),\n"
             f"    {SCENE}CollisionPolys,\n"
             f"    {SCENE}SurfaceTypes,\n    {SCENE}BgCamList,\n    ARRAY_COUNT({SCENE}WaterBoxes),\n    {SCENE}WaterBoxes,\n}};\n")
    (OUT / f"{SCENE}.h").write_text(scene_h)
    (OUT / f"{SCENE}.c").write_text("".join(s))

    # ----- title card (one copy per language)
    (OUT / "ancient_title.c").write_text(
        hdr + '#include "ultra64.h"\n#include "versions.h"\n\n'
        "// Place name card, IA8 144x24: Japanese/English on NTSC, English/German/French on PAL.\n"
        "u64 gAncientPlateauTitleCardTex[] = {\n"
        f'#include "{INC}/ancient_title.ia8.inc.c"\n'
        f'#include "{INC}/ancient_title.ia8.inc.c"\n'
        "#if OOT_PAL\n"
        f'#include "{INC}/ancient_title.ia8.inc.c"\n'
        "#endif\n};\n")
    print(f"collision memory 0x{memsize:X} ({memsize // 1024} KB, default 115 KB)")
    return len(polys), len(verts), entries, acts


LIGHTS_OWN = 16  # the level's own light settings: 4 times of day x 4 weather configs


def light_settings():
    # ambient, light1 dir, light1 color, light2 dir, light2 color, fog, fogNear, zFar
    day = [
        ((92, 78, 92), (255, 196, 150), (60, 66, 120), (188, 150, 150), 991),  # dawn
        ((108, 108, 116), (255, 248, 232), (70, 76, 118), (170, 198, 218), 993),  # day
        ((100, 72, 84), (255, 152, 96), (66, 60, 120), (196, 124, 104), 991),  # dusk
        ((44, 50, 82), (66, 78, 132), (28, 30, 66), (24, 30, 58), 986),  # night
    ]
    rows = []
    for cfg in range(4):  # time configs used by weather (clear, cloudy, rain...): darker and greyer
        k = [1.0, 0.82, 0.7, 0.62][cfg]
        for amb, l1, l2, fog, near in day:
            g = lambda c: tuple(int(min(255, (v * k + (sum(c) / 3) * (1 - k)) * (1 if cfg == 0 else 0.92))) for v in c)
            rows.append((g(amb), g(l1), g(l2), g(fog), near))
    out = (f"// Hyrule Field's own light settings (time of day, fog) when the ROM's assets are there\n"
           f"EnvLightSettings {SCENE}LightSettings[ANCIENT_LIGHTS_COUNT] = {{\n#ifdef ANCIENT_HF_LIGHTS\n"
           "#include ANCIENT_HF_LIGHTS\n#else\n")
    for amb, l1, l2, fog, near in rows:
        out += (f"    {{ {{ {amb[0]}, {amb[1]}, {amb[2]} }}, {{ 73, 73, 73 }}, {{ {l1[0]}, {l1[1]}, {l1[2]} }}, "
                f"{{ -73, -73, -73 }}, {{ {l2[0]}, {l2[1]}, {l2[2]} }}, {{ {fog[0]}, {fog[1]}, {fog[2]} }}, "
                f"BLEND_RATE_AND_FOG_NEAR(4, {near}), 12800 }},\n")
    return out + "#endif\n};\n\n"


def export_preview(path):
    """Geometry dump for tools/remix/preview_level.html (a three.js look at the level outside the game).
    Animated parts are shown at a fixed pose."""
    import json

    poses = {
        0x09: lambda p: rot_z(np.array(p), 0.18) + [0, RING_Y, 0],
        0x0A: lambda p: np.array(p),
        0x0B: lambda p: np.array(p) + [0, RING_Y, 0],
        0x0F: lambda p: np.array(p) + [ISLAND["x"], ISLAND["top"], ISLAND["z"]],
    }
    meshes = []
    for e in ENTRIES:
        groups = {m: list(t) for m, t in e.groups.items()}
        for inst in e.instances:
            f = inst_transform(inst)
            for m, tris in inst[0].groups.items():
                groups.setdefault(m, []).extend([[(tuple(f(v[0])), v[1], v[2]) for v in t] for t in tris])
        for mat, tris in groups.items():
            pos, uv, nc = [], [], []
            w, h = mat.size if mat.tex else (32, 32)
            for t in tris:
                for p_, uv_, nc_ in t:
                    q = poses[e.matrix_seg](p_) if e.matrix_seg else p_
                    pos += [round(float(c), 1) for c in q]
                    uv += [round(uv_[0] / w, 4), round(uv_[1] / h, 4)]
                    nc += [round(float(c), 3) for c in nc_] if mat.lit else [round(c / 255, 3) for c in nc_[:3]]
            tex = TEXTURES[mat.tex] if mat.tex else None
            meshes.append({
                "entry": e.name, "mat": mat.name, "lit": mat.lit, "xlu": mat.xlu,
                "tex": f"{tex[0]}.{tex[1]}.png" if tex else None,
                "prim": list(mat.prim), "glow": {0x08: "cyan", 0x0C: "orange"}.get(mat.prim_seg),
                "clampT": mat.clamp_t, "pos": pos, "uv": uv, "nc": nc,
            })
    Path(path).write_text(json.dumps({"meshes": meshes, "spawn": [SPAWN[0], float(height(*SPAWN)), SPAWN[1]],
                                      "actors": actors_cache}))


def rot_z(p, a):
    c, s_ = math.cos(a), math.sin(a)
    return np.array([p[0] * c - p[1] * s_, p[0] * s_ + p[1] * c, p[2]])


actors_cache = []


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    make_textures()
    build_terrain()
    build_plaza()
    build_monument()
    build_floating()
    build_monoliths()
    build_pillars()
    build_sky()
    build_entrance()
    build_boundary()
    build_decor()
    npolys, nverts, entries, acts = write_sources()
    actors_cache[:] = [[a[0], a[1], a[2], a[3]] for a in acts] + [[f"DECOR_{d[0].upper()}", d[1], d[2], d[3]] for d in DECOR]
    tris = sum(len(t) for e in ENTRIES for t in e.groups.values())
    print(f"Ancient Plateau: {len(ENTRIES)} room chunks, {tris} triangles, {npolys} collision polys ({nverts} vertices), "
          f"{len(acts)} actors")
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file"] + [str(p) for p in OUT.glob("*.[ch]")], cwd=REPO, check=True)


if __name__ == "__main__":
    import sys

    main()
    if "--preview" in sys.argv:
        export_preview(sys.argv[sys.argv.index("--preview") + 1])
