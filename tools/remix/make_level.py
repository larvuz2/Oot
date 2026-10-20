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
        _paths_poly = unary_union(lines).simplify(12, preserve_topology=True)
    return _paths_poly


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
                 prim_seg=None, scroll=False, repeat=200.0, clamp_t=False):
        self.name, self.tex, self.fmt, self.size = name, tex, fmt, size
        self.lit, self.xlu, self.prim, self.prim_seg = lit, xlu, prim, prim_seg
        self.scroll, self.repeat, self.clamp_t = scroll, repeat, clamp_t


GRASS = Mat("grass", "grass", "rgba16", (32, 32), repeat=150)
DIRT = Mat("dirt", "dirt", "rgba16", (32, 32), repeat=150)
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

# Textures that come from Hyrule Field itself when the ROM's assets are there (tools/remix/link_level_assets.py
# writes ancient_hf.h at build time); the files here are look-alike fallbacks for builds without a ROM.
HF_TEXTURES = {"grass": "ANCIENT_HF_GRASS", "dirt": "ANCIENT_HF_DIRT", "rock": "ANCIENT_HF_ROCK"}

TEXTURES = {  # key: (file stem, format, size)
    "grass": ("ancient_grass", "rgba16", (32, 32)),
    "dirt": ("ancient_dirt", "rgba16", (32, 32)),
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

    def tri(self, mat, verts):
        self.groups.setdefault(mat, []).append(verts)

    def positions(self):
        return [v[0] for tris in self.groups.values() for t in tris for v in t]


ENTRIES: list[Entry] = []
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
            if rc < 760:
                continue  # hidden under the plaza
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
                if mat is GRASS and pd < 400:
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
    if not tri2.intersects(paths):
        e.tri(GRASS, [V(pts[k], planar_uv(GRASS, pts[k]), nrm[k]) for k in range(3)])
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
    for geom, mat in ((inside, DIRT), (outside, GRASS)):
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


def noisy_rock(entry, mat, center, radius, squash=1.0, seed=0, sink=0.25, col=None, glow_ring=False, detail=1):
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
        if max(p[1] for p in pts) < height(pts[0][0], pts[0][2]) - 5:
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
        for i, (r, s, off) in enumerate(((1700, 1, 250), (2250, -1, 270), (2900, 1, 420))):
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
    # dormant guardians: two Armos statues that wake up, two that only sleep
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        x, z = math.sin(a) * 600, math.cos(a) * 600
        add("ACTOR_EN_AM", x, PLAZA_Y, z, yaw_to(0, 0, x, z), "ARMOS_ENEMY" if k % 2 == 0 else "ARMOS_STATUE")
    # Gossip Stones guarding the Spire's south steps
    for s in (-1, 1):
        add("ACTOR_EN_GS", s * 200, PLAZA_Y, 370, 0, "0x3F05")
    # Beamos watchtowers on the hills
    for a in (0.72, 0.72 + math.pi, 2.45):
        x, z = math.sin(a) * 2500, math.cos(a) * 2500
        if float(path_dist(x, z)) < 400:
            a += 0.35
            x, z = math.sin(a) * 2500, math.cos(a) * 2500
        add("ACTOR_EN_VM", x, mesh_height(x, z), z, 0, "0x1400")
    # trees, bushes, rocks and butterflies in the field
    free = []
    tries = 0
    while len(free) < 66 and tries < 6000:
        tries += 1
        r = 1500 + rng.random() * 2100
        a = rng.random() * 2 * math.pi
        x, z = math.sin(a) * r, math.cos(a) * r
        if float(path_dist(x, z)) < 220 or math.hypot(x - SPAWN[0], z - SPAWN[1]) < 300:
            continue
        if town_plan.near_plot(x, z, 140):
            continue
        if any(math.hypot(x - fx, z - fz) < 170 for fx, fz in free):
            continue
        if float(normal_at(x, z)[1]) < 0.85:
            continue
        free.append((x, z))
    # the same props as Hyrule Field: its trees, bushes, liftable rocks, silver boulders and bomb boulders
    for i, (x, z) in enumerate(free):
        y = mesh_height(x, z)
        if i < 20:
            add("ACTOR_EN_WOOD02", x, y, z, int(rng.random() * 0x10000), "0xFF05" if i % 3 else "0xFF00")
        elif i < 38:
            add("ACTOR_EN_KUSA", x, y, z, 0, "0x0000")
        elif i < 52:
            add("ACTOR_EN_ISHI", x, y, z, 0, "ROCK_SMALL")
        elif i < 56:
            add("ACTOR_EN_ISHI", x, y, z, int(rng.random() * 0x10000), "ROCK_LARGE")
        elif i < 59:
            add("ACTOR_EN_ISHI", x, y, z, 0, "ROCK_SMALL")
        else:
            add("ACTOR_EN_BUTTE", x, y + 60, z, 0, "0x0000")
    town_people(add, yaw_to)
    return out


OBJECTS = ["OBJECT_SYOKUDAI", "OBJECT_AM", "OBJECT_GS", "OBJECT_VM", "OBJECT_WOOD02",
           # the town's people and animals (town_people)
           "OBJECT_OS_ANIME", "OBJECT_BOJ", "OBJECT_AHG", "OBJECT_BBA", "OBJECT_CNE", "OBJECT_MU", "OBJECT_DOG",
           "OBJECT_NIW", "OBJECT_COW", "OBJECT_ANI", "OBJECT_TSUBO"]
# (with gameplay_keep, field_keep and Link that is 19, every object slot there is: include/object.h)

TOWN_PATH_R = 1110  # the walk around the plaza, between its edge and the monoliths (dogs and strollers follow it)


def town_path():
    pts = []
    for k in range(16):
        a = 2 * math.pi * k / 16 + math.pi / 16
        x, z = math.sin(a) * TOWN_PATH_R, math.cos(a) * TOWN_PATH_R
        pts.append((round(x), round(mesh_height(x, z)), round(z)))
    return pts


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
    x, z = at(720, 20)
    add("ACTOR_EN_MU", x, PLAZA_Y, z, yaw_to(x, z, *at(720, 30)), "0")  # a haggling pair
    x2, z2 = at(720, 30)
    add("ACTOR_EN_MU", x2, PLAZA_Y, z2, yaw_to(x2, z2, x, z), "1")
    x, z = at(700, 112)
    add("ACTOR_EN_TG", x, PLAZA_Y, z, 0, "0")  # the dancing couple
    hy("ENHY_TYPE_OLD_WOMAN", *at(720, 200), y=PLAZA_Y)
    hy("ENHY_TYPE_YOUNG_WOMAN_BROWN_HAIR", *at(720, 250), y=PLAZA_Y)
    hy("ENHY_TYPE_MAN_1_BEARD", *at(720, 292), y=PLAZA_Y)
    hy("ENHY_TYPE_MAN_2_MUSTACHE_RED_SHIRT", *at(720, 338), y=PLAZA_Y)
    # strolling around the plaza, and the town's two dogs
    hy("ENHY_TYPE_MAN_2_BALD", *at(TOWN_PATH_R, 11.25), path=0)
    for k, params in enumerate(("0x0000", "0x0101")):  # dog ids 1 and 2, path 0, cream and brown
        x, z = at(TOWN_PATH_R, 101.25 + 180 * k)
        add("ACTOR_EN_DOG", x, mesh_height(x, z) + 5, z, 0, params)
    # in front of the houses, talking toward the plaza
    for (kind, plot) in (("ENHY_TYPE_MAN_2_MUSTACHE_BLUE_SHIRT", 0), ("ENHY_TYPE_YOUNG_WOMAN_ORANGE_HAIR", 1),
                         ("ENHY_TYPE_MAN_2_ALT_MUSTACHE", 5), ("ENHY_TYPE_MAN_1_SHAVED_GREEN_SHIRT", 6),
                         ("ENHY_TYPE_MAN_2_MUSTACHE_WHITE_SHIRT", 10), ("ENHY_TYPE_MAN_2_BEARD", 16)):
        p = town_plan.PLOTS[plot]
        d = p["r"] + 90
        x, z = p["x"] + math.sin(p["face"]) * d, p["z"] + math.cos(p["face"]) * d
        hy(kind, x, z)
    # cuccos around the barn and the houses, and a cow in the barn
    for k in range(7):
        p = town_plan.PLOTS[(2, 3, 4, 8, 13, 17, 18)[k]]
        a = p["face"] + 1.9 + 0.5 * k
        x, z = p["x"] + math.sin(a) * (p["r"] + 70), p["z"] + math.cos(a) * (p["r"] + 70)
        add("ACTOR_EN_NIW", x, mesh_height(x, z) + 10, z, int(rng.random() * 0x10000), "0x0000")
    p = town_plan.PLOTS[3]
    add("ACTOR_EN_COW", p["x"], mesh_height(p["x"], p["z"]), p["z"], yaw_to(p["x"], p["z"], 0, 0), "0x0000")
    # pots with rupees inside the houses (each with its own collectible flag, so every one pays once)
    flag = 1
    for plot in (0, 1, 5, 6, 10, 15, 16):
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
    if mat.xlu:
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
            g.append("gsSPDisplayList(0x0D000000)")
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
    for e in ENTRIES:
        dls = {}
        for xlu in (False, True):
            groups = [(m, t) for m, t in e.groups.items() if m.xlu == xlu]
            if not groups:
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
            if e.matrix_seg is not None:
                cmds.append("gsSPPopMatrix(G_MTX_MODELVIEW)")
            cmds.append("gsSPEndDisplayList()")
            for v in verts:
                assert all(-32768 <= c <= 32767 for c in v[:5]), (e.name, v)
            vtx_out.append(f"Vtx {vname}[{len(verts)}] = {{\n" +
                           "".join(f"    VTX({v[0]}, {v[1]}, {v[2]}, {v[3]}, {v[4]}, 0x{v[5]:02X}, 0x{v[6]:02X}, 0x{v[7]:02X}, 0x{v[8]:02X}),\n"
                                   for v in verts) + "};\n")
            dl_out.append(f"Gfx {dname}[] = {{\n" + "".join(f"    {c},\n" for c in cmds) + "};\n")
            decl.append(f"extern Vtx {vname}[{len(verts)}];")
            decl.append(f"extern Gfx {dname}[];")
            dls[xlu] = dname
        if e.sphere:
            center, radius = e.sphere
        else:
            pts = np.array(e.positions())
            lo, hi = pts.min(0), pts.max(0)
            center = (lo + hi) / 2
            radius = float(np.max(np.linalg.norm(pts - center, axis=1)))
        entries_out.append((tuple(int(round(c)) for c in center), int(math.ceil(radius)) + 8,
                            dls.get(False, "NULL"), dls.get(True, "NULL")))
    assert len(entries_out) <= 64, len(entries_out)
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
              f"#define ANCIENT_RING_Y {RING_Y}\n\n" + "\n".join(tex_decl) + "\n" + "\n".join(decl) +
              "\n\n#endif\n")
    lines = [hdr, f'#include "{ROOM}.h"\n#include "{INC}/ancient_hf.h"\n#include "{INC}/ancient_town.h"\n', '#include "actor.h"\n#include "array_count.h"\n#include "gfx.h"\n#include "object.h"\n'
             '#include "room.h"\n#include "scene.h"\n#include "sequence.h"\n#include "actor_profile.h"\n'
             '#include "src/overlays/actors/ovl_En_Am/z_en_am.h"\n#include "src/overlays/actors/ovl_En_Ishi/z_en_ishi.h"\n'
             '#include "src/overlays/actors/ovl_En_Hy/z_en_hy.h"\n#include "z_en_item00.h"\n\n']
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
    s.append(f"CollisionHeader {SCENE}CollisionHeader = {{\n    {{ {lo[0]}, {lo[1]}, {lo[2]} }},\n    {{ {hi[0]}, {hi[1]}, {hi[2]} }},\n"
             f"    ARRAY_COUNT({SCENE}CollisionVtx),\n    {SCENE}CollisionVtx,\n    ARRAY_COUNT({SCENE}CollisionPolys),\n"
             f"    {SCENE}CollisionPolys,\n"
             f"    {SCENE}SurfaceTypes,\n    {SCENE}BgCamList,\n    0,\n    NULL,\n}};\n")
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
    }
    meshes = []
    for e in ENTRIES:
        for mat, tris in e.groups.items():
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
    build_boundary()
    npolys, nverts, entries, acts = write_sources()
    actors_cache[:] = [[a[0], a[1], a[2], a[3]] for a in acts]
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
