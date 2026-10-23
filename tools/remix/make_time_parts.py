#!/usr/bin/env python3
"""Generate object_remix_time: the moving pieces of the Temple of Two Truths (Web Remix level 6), for En_Remix_Time,
and the header that gives that actor the shrine's plan (tools/remix/time_plan.py).

  Sphere, Seed, Bubble     the golden sphere (adult era), the golden seed it was (child era), the bubble it floats in
  Pedestal                 the sphere's pedestal (sinks into the dais)
  Ring                     ring 1: the rotating stone band, four openings, the cradle on its inner face
  Block, BlockDecayed      the echo blocks: small in the past; sunk and worn in the present...
  Pillar, Mirror           ...or grown into a pillar (the mirror block's carries a mirror)
  PanL, PanR, Chain, Weight the scale and the stone weight
  Bridge, BridgeRuin       the child era's bridge to the dais; what is left of it in the adult era
  Ramp, RampRuin           the child era's ramp up the statue to the first eye; its ruin
  Jaw, Door                the statue's mouth; the way-out door under the sun symbol
  Tablet, Crystal, Grate   inscriptions, the blast-only crystal, the grate over the first eye's plate
  Hourglass, HourglassGlass, DecoRingA/B/C, Hand, Lid, Water
                           the decor En_Remix_Time's controller draws: the hourglass and its three rings, the clock's
                           hand, the stone lid on the second eye, the water filling the pit
  Beam, Disc               a unit light shaft (along +y) and a unit glowing disc, drawn translucent and scaled

Model units are game units (drawn at scale 1, but Beam, Disc and Chain). Opaque parts are textured, shaded by baked
vertex colours, with the environment colour added (the actor makes a piece glow with it).

    python3 tools/remix/make_time_parts.py     # writes assets/objects/object_remix_time/ (committed)
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import time_plan as T

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/objects/object_remix_time"
INC = "assets/objects/object_remix_time"
LIGHT = np.array([0.35, 0.8, 0.5]) / np.linalg.norm([0.35, 0.8, 0.5])

SAND = (226, 196, 150)
GOLD = (255, 205, 70)
BLUE = (90, 170, 255)
ORANGE = (255, 150, 50)


# ---------------------------------------------------------------- textures (32 x 32 RGBA16)


def sand_base(seed, tint=(1.0, 1.0, 1.0)):
    rng = np.random.default_rng(seed)
    img = np.zeros((32, 32, 3)) + SAND
    img *= 0.88 + 0.12 * rng.random((32, 32, 1))
    for y in (0, 15, 16, 31):  # block courses
        img[y, :] *= 0.72
    img[:16, 0] *= 0.72
    img[16:, 16] *= 0.72
    return img * np.array(tint)


def glyph(img, color):
    img = img.copy()
    c = np.array(color, float)
    d = Image.new("L", (32, 32), 0)
    g = ImageDraw.Draw(d)
    g.ellipse([9, 9, 23, 23], outline=255, width=2)  # a sun: ring, rays
    for k in range(8):
        a = k * math.pi / 4
        g.line([(16 + 9 * math.cos(a), 16 + 9 * math.sin(a)), (16 + 14 * math.cos(a), 16 + 14 * math.sin(a))],
               fill=255, width=2)
    m = np.array(d)[..., None] / 255.0
    return img * (1 - m) + c * m


def gold():
    y = np.arange(32)[:, None, None]
    x = np.arange(32)[None, :, None]
    sheen = 0.75 + 0.35 * np.cos((x + y) / 32 * 2 * math.pi) ** 2
    return np.zeros((32, 32, 3)) + np.array(GOLD) * sheen


def moss():
    rng = np.random.default_rng(9)
    img = sand_base(4, (0.8, 0.85, 0.7))
    blot = rng.random((32, 32)) > 0.62
    img[blot] = img[blot] * 0.5 + np.array([70, 110, 60]) * 0.5
    return img


def mirror():
    y = np.arange(32)[:, None, None]
    x = np.arange(32)[None, :, None]
    return np.zeros((32, 32, 3)) + np.array([200, 225, 255]) * (0.8 + 0.25 * np.exp(-(((x - y) / 5.0) ** 2)))


def dark():
    rng = np.random.default_rng(6)
    img = np.zeros((32, 32, 3)) + [92, 80, 70]
    img *= 0.85 + 0.15 * rng.random((32, 32, 1))
    img[0, :] *= 0.6
    img[:, 0] *= 0.6
    return img


def write_textures():
    tex = {
        "time_sand": sand_base(1),
        "time_rune": glyph(sand_base(2), (90, 200, 255)),
        "time_sun": glyph(sand_base(3), (255, 170, 60)),
        "time_gold": gold(),
        "time_moss": moss(),
        "time_mirror": mirror(),
        "time_dark": dark(),
    }
    for name, img in tex.items():
        Image.fromarray(np.clip(img, 0, 255).round().astype(np.uint8)).convert("RGBA").save(OUT / f"{name}.rgba16.png")
    return list(tex)


# ---------------------------------------------------------------- geometry

KIND = {"xlu": "xlu", "beam": "beam"}  # material name -> kind (else an opaque texture)


class Piece:
    def __init__(self, name, surf=None):
        self.name = name
        self.tris: dict[str, list] = {}  # material -> [(points, uvs, normal, colour)]
        self.col: list = []
        self.surf = surf or {}  # collision surface: wall type, hookshot

    def tri(self, mat, pts, uv, n, color=(255, 255, 255), col=False):
        pts = [np.array(p, float) for p in pts]
        n = np.array(n, float)
        if np.dot(np.cross(pts[1] - pts[0], pts[2] - pts[0]), n) < 0:
            pts, uv = [pts[0], pts[2], pts[1]], [uv[0], uv[2], uv[1]]
        self.tris.setdefault(mat, []).append((pts, uv, n, color))
        if col:
            self.col.append(pts)

    def quad(self, mat, pts, normal, col=True, tile=64.0, color=(255, 255, 255)):
        pts = [np.array(p, float) for p in pts]
        n = np.array(normal, float)
        ax_u = pts[1] - pts[0]
        ax_u /= max(np.linalg.norm(ax_u), 1e-6)
        ax_v = np.cross(n / max(np.linalg.norm(n), 1e-6), ax_u)
        uv = [(float(np.dot(p - pts[0], ax_u)) / tile * 32, float(np.dot(p - pts[0], ax_v)) / tile * 32) for p in pts]
        for i, j, k in ((0, 1, 2), (0, 2, 3)):
            self.tri(mat, [pts[i], pts[j], pts[k]], [uv[i], uv[j], uv[k]], n, color, col)

    def box(self, x0, x1, y0, y1, z0, z1, mat="time_sand", top=None, bottom=None, col=True, tile=64.0,
            color=(255, 255, 255), skip=()):
        top, bottom = top or mat, bottom or mat
        faces = {
            "top": (top, [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
            "bottom": (bottom, [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)], (0, -1, 0)),
            "s": (mat, [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
            "n": (mat, [(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)], (0, 0, -1)),
            "e": (mat, [(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)], (1, 0, 0)),
            "w": (mat, [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], (-1, 0, 0)),
        }
        for k, (m, p, n) in faces.items():
            if k not in skip:
                self.quad(m, p, n, col, tile, color)

    def cylinder(self, mat, r0, r1, y0, y1, n=12, col=False, cap_top=None, cap_bottom=None, tile=64.0,
                 color=(255, 255, 255), inward=False):
        ring = [(math.sin(2 * math.pi * k / n), math.cos(2 * math.pi * k / n)) for k in range(n)]
        for k in range(n):
            (sa, ca), (sb, cb) = ring[k], ring[(k + 1) % n]
            p = [(sa * r0, y0, ca * r0), (sb * r0, y0, cb * r0), (sb * r1, y1, cb * r1), (sa * r1, y1, ca * r1)]
            out = np.array([(sa + sb) / 2, (r0 - r1) / max(y1 - y0, 1e-6), (ca + cb) / 2])
            self.quad(mat, p, -out if inward else out, col, tile, color)
        for cap, y, r, up in ((cap_top, y1, r1, 1), (cap_bottom, y0, r0, -1)):
            if cap:
                for k in range(n):
                    (sa, ca), (sb, cb) = ring[k], ring[(k + 1) % n]
                    pts = [(0, y, 0), (sa * r, y, ca * r), (sb * r, y, cb * r)]
                    uv = [(16 + p[0] / tile * 32, 16 + p[2] / tile * 32) for p in pts]
                    self.tri(cap, pts, uv, (0, up, 0), color, col)

    def sphere(self, mat, r, nu=12, nv=8, scale=(1, 1, 1), center=(0, 0, 0), color=(255, 255, 255)):
        def p(i, j):
            th, ph = math.pi * j / nv, 2 * math.pi * i / nu
            v = np.array([math.sin(th) * math.sin(ph), math.cos(th), math.sin(th) * math.cos(ph)])
            return v * r * np.array(scale) + center, v

        for j in range(nv):
            for i in range(nu):
                (a, na), (b, nb), (c, nc), (d, nd) = p(i, j), p(i + 1, j), p(i + 1, j + 1), p(i, j + 1)
                uv = [(i * 32 / nu * 2, j * 32 / nv), ((i + 1) * 32 / nu * 2, j * 32 / nv),
                      ((i + 1) * 32 / nu * 2, (j + 1) * 32 / nv), (i * 32 / nu * 2, (j + 1) * 32 / nv)]
                n = (na + nb + nc + nd) / 4
                if j > 0:
                    self.tri(mat, [a, b, c], [uv[0], uv[1], uv[2]], n, color)
                if j < nv - 1:
                    self.tri(mat, [a, c, d], [uv[0], uv[2], uv[3]], n, color)


def build_pieces():
    out = []
    p = Piece("Sphere")
    p.sphere("time_gold", T.SPHERE_R)
    out.append(p)

    p = Piece("Seed")
    p.sphere("time_gold", 8, 8, 6, scale=(1, 1.35, 1), center=(0, 11, 0))
    for a in (0.0, math.pi):  # two leaves of the sprout
        s, c = math.sin(a), math.cos(a)
        tip = (s * 14, 30, c * 14)
        p.tri("time_moss", [(0, 22, 0), (s * 3 + c * 4, 26, c * 3 - s * 4), tip], [(0, 0), (8, 0), (4, 16)],
              (c, 0.3, -s), color=(120, 255, 120))
        p.tri("time_moss", [(0, 22, 0), tip, (s * 3 - c * 4, 26, c * 3 + s * 4)], [(0, 0), (4, 16), (8, 0)],
              (-c, 0.3, s), color=(120, 255, 120))
    out.append(p)

    p = Piece("Bubble")
    p.sphere("xlu", 46, 12, 8)
    out.append(p)

    p = Piece("Pedestal")
    p.cylinder("time_sand", T.PEDESTAL_R, T.PEDESTAL_R, -340, T.PEDESTAL_TOP - 10, n=10, col=True)
    p.cylinder("time_gold", T.PEDESTAL_R, T.PEDESTAL_R + 6, T.PEDESTAL_TOP - 10, T.PEDESTAL_TOP, n=10, col=True,
               cap_top="time_sun")
    out.append(p)

    out.append(build_ring())

    s = 30
    p = Piece("Block", dict(wall=7))
    p.box(-s, s, 0, 2 * s, -s, s, mat="time_sun", top="time_rune", tile=60)
    out.append(p)
    p = Piece("BlockDecayed", dict(wall=7))
    p.box(-32, 32, 0, 40, -32, 32, mat="time_moss", tile=60, color=(170, 190, 160))
    out.append(p)
    p = Piece("Pillar")
    p.box(-45, 45, 0, 180, -45, 45, mat="time_sun", top="time_sand", tile=90)
    p.box(-52, 52, 0, 20, -52, 52, mat="time_sand", col=False)
    out.append(p)
    p = Piece("Mirror")  # on top of the pillar: a gold frame, the glass tilted towards the light spot
    p.box(-34, 34, 0, 10, -34, 34, mat="time_gold", col=False)
    tilt = [(-30, 12, -30), (30, 12, -30), (30, 40, 30), (-30, 40, 30)]
    p.quad("time_mirror", [tilt[3], tilt[2], tilt[1], tilt[0]], (0, 0.9, -0.45), col=False, tile=64)
    p.quad("time_gold", tilt, (0, -0.9, 0.45), col=False)
    out.append(p)

    for name, size in (("PanL", T.PAN_L_SIZE), ("PanR", T.PAN_R_SIZE)):
        h = size / 2
        p = Piece(name)
        p.box(-h, h, -20, 0, -h, h, mat="time_dark", top="time_sun", tile=size)
        for x in (-h + 6, h - 6):  # the rim
            p.box(x - 4, x + 4, 0, 10, -h, h, mat="time_gold", col=False)
        out.append(p)
    p = Piece("Chain")  # 100 high along +y (drawn scaled to the length)
    for k in range(5):
        y = k * 20
        p.box(-3, 3, y, y + 16, -6, 6, mat="time_dark", col=False) if k % 2 else \
            p.box(-6, 6, y, y + 16, -3, 3, mat="time_dark", col=False)
    out.append(p)
    w = T.WEIGHT_SIZE / 2
    p = Piece("Weight")
    p.box(-w, w, 0, 2 * w, -w, w, mat="time_dark", top="time_sun", tile=100)
    p.cylinder("time_gold", 14, 14, 2 * w, 2 * w + 16, n=8, cap_top="time_gold")
    out.append(p)

    bl = T.PIT_R - T.DAIS_R
    hw = T.BRIDGE_W / 2
    p = Piece("Bridge")
    p.box(-hw, hw, -30, 0, 0, bl, mat="time_sand", top="time_rune", tile=100)
    for z in np.arange(30, bl, 80):
        for x in (-hw + 6, hw - 6):
            p.box(x - 5, x + 5, 0, 40, z - 5, z + 5, mat="time_gold", col=False)
    out.append(p)
    p = Piece("BridgeRuin")
    p.box(-hw, hw - 30, -30, 0, 0, 45, mat="time_moss", col=False, color=(180, 180, 170))
    p.box(-hw + 20, hw, -30, 0, bl - 50, bl, mat="time_moss", col=False, color=(180, 180, 170))
    out.append(p)

    out.append(build_ramp(ruin=False))
    out.append(build_ramp(ruin=True))

    m = T.MOUTH
    p = Piece("Jaw")
    p.box(m["x0"], m["x1"], 0, m["y1"], -20, 20, mat="time_sand", tile=80)
    for k in range(6):  # teeth
        x = m["x0"] + 20 + k * (m["x1"] - m["x0"] - 40) / 5
        p.box(x - 12, x + 12, m["y1"] - 50, m["y1"] - 5, 20, 26, mat="time_gold", col=False)
    out.append(p)
    p = Piece("Door")
    p.box(-110, 110, 0, 250, -15, 15, mat="time_sun", tile=110)
    out.append(p)
    p = Piece("Tablet")
    p.box(-45, 45, 0, 110, -8, 8, mat="time_rune", top="time_sand", tile=90)
    p.box(-55, 55, 0, 14, -14, 14, mat="time_sand", col=False)
    out.append(p)
    p = Piece("Crystal")
    v = [(0, 22, 0), (0, -22, 0), (16, 0, 0), (-16, 0, 0), (0, 0, 16), (0, 0, -16)]
    for top in (0, 1):
        for a, b in ((2, 4), (4, 3), (3, 5), (5, 2)):
            pts = [v[top], v[a], v[b]]
            n = np.mean(pts, 0)
            p.tri("xlu", pts, [(0, 0), (32, 0), (16, 32)], n)
    out.append(p)
    g = T.GRATE
    p = Piece("Grate")
    for k in range(6):
        x = -g["w"] / 2 + 8 + k * (g["w"] - 16) / 5
        p.box(x - 4, x + 4, -8, 0, -g["d"] / 2, g["d"] / 2, mat="time_dark", col=False)
    p.box(-g["w"] / 2, g["w"] / 2, -8, 0, -g["d"] / 2, -g["d"] / 2 + 8, mat="time_dark", col=False)
    p.box(-g["w"] / 2, g["w"] / 2, -8, 0, g["d"] / 2 - 8, g["d"] / 2, mat="time_dark", col=False)
    out.append(p)

    out += build_hourglass()
    for name, r in (("DecoRingA", 170), ("DecoRingB", 215), ("DecoRingC", 260)):
        p = Piece(name)
        n = 20
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            for rr, y, up in ((r, 8, 1), (r, -8, -1)):
                pts = [(math.sin(a0) * (rr - 14), y, math.cos(a0) * (rr - 14)),
                       (math.sin(a1) * (rr - 14), y, math.cos(a1) * (rr - 14)),
                       (math.sin(a1) * rr, y, math.cos(a1) * rr), (math.sin(a0) * rr, y, math.cos(a0) * rr)]
                p.quad("time_rune" if k % 2 else "time_sand", pts, (0, up, 0), col=False, tile=40)
            for rr, out_ in ((r, 1), (r - 14, -1)):
                pts = [(math.sin(a0) * rr, -8, math.cos(a0) * rr), (math.sin(a1) * rr, -8, math.cos(a1) * rr),
                       (math.sin(a1) * rr, 8, math.cos(a1) * rr), (math.sin(a0) * rr, 8, math.cos(a0) * rr)]
                mid = (a0 + a1) / 2
                p.quad("time_gold", pts, (math.sin(mid) * out_, 0, math.cos(mid) * out_), col=False, tile=40)
        out.append(p)

    p = Piece("Hand")  # the clock's hand: an arrow up +y, facing +z
    hw = 12
    pts = [(-hw, -20, 4), (hw, -20, 4), (hw, T.CLOCK_R - 50, 4), (-hw, T.CLOCK_R - 50, 4)]
    p.quad("time_gold", pts, (0, 0, 1), col=False)
    p.tri("time_gold", [(-30, T.CLOCK_R - 50, 4), (30, T.CLOCK_R - 50, 4), (0, T.CLOCK_R - 10, 4)],
          [(0, 0), (32, 0), (16, 32)], (0, 0, 1))
    p.cylinder("time_gold", 22, 22, 0, 8, n=10, cap_top="time_gold")  # the hub (along y: turned to face out)
    out.append(p)

    p = Piece("Lid")  # the stone lid over the second eye, facing +z
    n = 12
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        pts = [(0, 0, 14), (math.sin(a0) * T.EYE_R, math.cos(a0) * T.EYE_R, 4),
               (math.sin(a1) * T.EYE_R, math.cos(a1) * T.EYE_R, 4)]
        p.tri("time_sand", pts, [(16, 16), (16 + 16 * math.sin(a0), 16 + 16 * math.cos(a0)),
                                 (16 + 16 * math.sin(a1), 16 + 16 * math.cos(a1))], (0, 0, 1))
    out.append(p)

    p = Piece("Water")  # the pit's water (a disc) and the basin's, at y = 0 (drawn at the water's height)
    n = 24
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p.tri("xlu", [(0, 0, 0), (math.sin(a0) * T.PIT_R, 0, math.cos(a0) * T.PIT_R),
                      (math.sin(a1) * T.PIT_R, 0, math.cos(a1) * T.PIT_R)], [(0, 0)] * 3, (0, 1, 0))
    b = T.BASIN
    p.quad("xlu", [(T.PIT_R - 30, 0, b["z0"]), (b["x1"], 0, b["z0"]), (b["x1"], 0, b["z1"]), (T.PIT_R - 30, 0, b["z1"])],
           (0, 1, 0), col=False)
    out.append(p)

    p = Piece("Beam")  # radius 1, from y 0 to 1
    p.cylinder("beam", 1, 1, 0, 1, n=8)
    out.append(p)
    p = Piece("Disc")
    n = 16
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p.tri("beam", [(0, 0, 0), (math.sin(a0), 0, math.cos(a0)), (math.sin(a1), 0, math.cos(a1))],
              [(0, 0)] * 3, (0, 1, 0))
    out.append(p)
    return out


def build_ring():
    p = Piece("Ring", dict(hook=False))
    step = 4
    open_ = set()
    for c in T.OPENINGS:
        for a in range(c - T.OPENING_W // 2, c + T.OPENING_W // 2, step):
            open_.add(a % 360)
    r0, r1, y0, y1 = T.RING_R0, T.RING_R1, T.RING_Y0, T.RING_Y1
    for a in range(0, 360, step):
        if a in open_:
            continue
        t0, t1 = math.radians(a), math.radians(a + step)
        s0, c0, s1, c1 = math.sin(t0), math.cos(t0), math.sin(t1), math.cos(t1)
        mid = math.radians(a + step / 2)
        band = "time_rune" if (a // step) % 6 == 0 else "time_sand"
        for r, out_ in ((r1, 1), (r0, -1)):
            pts = [(s0 * r, y0, c0 * r), (s1 * r, y0, c1 * r), (s1 * r, y1, c1 * r), (s0 * r, y1, c0 * r)]
            p.quad(band, pts, (math.sin(mid) * out_, 0, math.cos(mid) * out_), col=True, tile=110)
        p.quad("time_gold", [(s0 * r0, y1, c0 * r0), (s1 * r0, y1, c1 * r0), (s1 * r1, y1, c1 * r1),
                             (s0 * r1, y1, c0 * r1)], (0, 1, 0), col=False)
        p.quad("time_dark", [(s0 * r1, y0, c0 * r1), (s1 * r1, y0, c1 * r1), (s1 * r0, y0, c1 * r0),
                             (s0 * r0, y0, c0 * r0)], (0, -1, 0), col=False)
        a1 = (a + step) % 360
        for edge, nxt in ((a, (a - step) % 360), (a1, a1)):
            if nxt in open_:  # the opening's sides
                t = math.radians(edge)
                s, c = math.sin(t), math.cos(t)
                side = (c, 0, -s) if edge == a else (-c, 0, s)
                p.quad("time_sand", [(s * r0, y0, c * r0), (s * r1, y0, c * r1), (s * r1, y1, c * r1),
                                     (s * r0, y1, c * r0)], side, col=True)
    # the cradle: a shelf on the inner face, a gold plate the sphere sits on
    t = math.radians(T.CRADLE_PHI)
    s, c = math.sin(t), math.cos(t)
    cx, cz = s * T.CRADLE_R, c * T.CRADLE_R
    q = Piece("tmp")
    q.box(-40, 40, T.CRADLE_Y - 30, T.CRADLE_Y, -34, 34, mat="time_sand", top="time_sun", col=False)
    q.box(-40, -30, T.CRADLE_Y, T.CRADLE_Y + 24, -34, 34, mat="time_gold", col=False)  # the lip that traps it
    q.box(30, 40, T.CRADLE_Y, T.CRADLE_Y + 24, -34, 34, mat="time_gold", col=False)
    # turn the shelf so its local +x points outwards (towards the band)
    for mat, tris in q.tris.items():
        for pts, uv, n, color in tris:
            def rot(v):
                return np.array([v[0] * s - v[2] * c, v[1], v[0] * c + v[2] * s])
            p.tris.setdefault(mat, []).append(([rot(v) + [cx, 0, cz] for v in pts], uv, rot(n), color))
    return p


def build_ramp(ruin):
    r = T.RAMP
    hw = r["w"] / 2
    length = r["z1"] - r["z0"]  # negative: towards -z
    p = Piece("RampRuin" if ruin else "Ramp")
    steps = 13
    for k in range(steps if not ruin else 3):
        z0, z1 = length * k / steps, length * (k + 1) / steps
        top = T.UPPER * (k + 1) / steps
        mat = "time_moss" if ruin else ("time_rune" if k % 4 == 0 else "time_sand")
        p.box(-hw, hw - (25 if ruin and k == 2 else 0), top - 20, top, z1, z0, mat=mat, col=False, tile=60,
              color=(180, 180, 170) if ruin else (255, 255, 255))
    if not ruin:
        for x in (-hw - 8, hw):  # side walls (gold edge)
            p.quad("time_gold", [(x, T.UPPER * 1 / steps, 0), (x, T.UPPER + 10, length), (x + 8, T.UPPER + 10, length),
                                 (x + 8, T.UPPER / steps, 0)], (0, 1, 0), col=False)
        # collision: one slope, Link walks it (37 degrees)
        a, b = (-hw, 0, 0), (hw, 0, 0)
        c, d = (hw, T.UPPER, length), (-hw, T.UPPER, length)
        p.col += [[np.array(v, float) for v in t] for t in ((a, b, c), (a, c, d))]
        for x, nx in ((-hw, -1), (hw, 1)):  # its sides (so the slope is a solid wedge)
            tri = [np.array(v, float) for v in ((x, 0, 0), (x, T.UPPER, length), (x, 0, length))]
            if np.dot(np.cross(tri[1] - tri[0], tri[2] - tri[0]), (nx, 0, 0)) < 0:
                tri = [tri[0], tri[2], tri[1]]
            p.col.append(tri)
        # fix the slope's facing (up)
        p.col = [t if np.cross(t[1] - t[0], t[2] - t[0])[1] >= 0 or abs(np.cross(t[1] - t[0], t[2] - t[0])[1]) < 1e-6
                 else [t[0], t[2], t[1]] for t in p.col]
    return p


def build_hourglass():
    frame = Piece("Hourglass")
    glass = Piece("HourglassGlass")
    h, r = 130, 70
    for y in (-h, h):  # gold caps
        frame.cylinder("time_gold", r + 12, r + 12, y - 10 if y > 0 else y, y + 10 if y < 0 else y + 10, n=10,
                       cap_top="time_gold", cap_bottom="time_gold")
    for k in range(3):  # posts
        a = 2 * math.pi * k / 3
        x, z = math.sin(a) * (r + 4), math.cos(a) * (r + 4)
        frame.box(x - 5, x + 5, -h, h, z - 5, z + 5, mat="time_gold", col=False)
    frame.cylinder("time_sand", 40, 4, -h + 10, -40, n=10, cap_bottom="time_sand", color=(255, 220, 160))  # sand below
    frame.cylinder("time_sand", 4, 30, 50, h - 30, n=10, cap_top="time_sand", color=(255, 220, 160))  # sand above
    glass.cylinder("xlu", r, 8, -h + 10, 0, n=12)
    glass.cylinder("xlu", 8, r, 0, h - 10, n=12)
    return [frame, glass]


def shade(n, color):
    s = min(1.0, 0.5 + 0.55 * max(0.0, float(np.dot(n / max(np.linalg.norm(n), 1e-6), LIGHT))))
    return tuple(int(round(c * s)) for c in color)


SETUP = ["    gsDPPipeSync(),", "    gsDPSetCycleType(G_CYC_1CYCLE),",
         "    gsSPClearGeometryMode(G_LIGHTING | G_FOG | G_CULL_BOTH | G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR),"]


def material(mat, sym):
    if mat == "xlu":  # untextured, the primitive colour (and alpha) times the shade
        return SETUP + ["    gsSPSetGeometryMode(G_SHADE | G_SHADING_SMOOTH | G_ZBUFFER | G_CULL_BACK),",
                        "    gsSPTexture(0, 0, 0, G_TX_RENDERTILE, G_OFF),",
                        "    gsDPSetCombineLERP(PRIMITIVE, 0, SHADE, 0, 0, 0, 0, PRIMITIVE, PRIMITIVE, 0, SHADE, 0, 0, 0, 0, "
                        "PRIMITIVE),",
                        "    gsDPSetRenderMode(G_RM_ZB_XLU_SURF, G_RM_ZB_XLU_SURF2),"]
    if mat == "beam":  # flat glow, both faces, no depth writes
        return SETUP + ["    gsSPSetGeometryMode(G_ZBUFFER),", "    gsSPTexture(0, 0, 0, G_TX_RENDERTILE, G_OFF),",
                        "    gsDPSetCombineMode(G_CC_PRIMITIVE, G_CC_PRIMITIVE),",
                        "    gsDPSetRenderMode(G_RM_ZB_CLD_SURF, G_RM_ZB_CLD_SURF2),"]
    return SETUP + ["    gsSPSetGeometryMode(G_SHADE | G_SHADING_SMOOTH | G_ZBUFFER | G_CULL_BACK),",
                    "    gsSPTexture(0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON),", "    gsDPSetTextureLUT(G_TT_NONE),",
                    "    gsDPSetCombineLERP(TEXEL0, 0, SHADE, ENVIRONMENT, 0, 0, 0, 1, TEXEL0, 0, SHADE, ENVIRONMENT, 0, 0, 0, 1),",
                    "    gsDPSetRenderMode(G_RM_AA_ZB_OPA_SURF, G_RM_AA_ZB_OPA_SURF2),",
                    f"    gsDPLoadTextureBlock({sym[mat]}, G_IM_FMT_RGBA, G_IM_SIZ_16b, 32, 32, 0, G_TX_NOMIRROR | G_TX_WRAP,"
                    " G_TX_NOMIRROR | G_TX_WRAP, 5, 5, G_TX_NOLOD, G_TX_NOLOD),"]


def emit(pieces, textures):
    sym = {t: "g" + "".join(s.capitalize() for s in t.split("_")) + "Tex" for t in textures}
    s = ["// Generated by tools/remix/make_time_parts.py - the Temple of Two Truths' pieces. Do not edit.\n",
         '#include "object_remix_time.h"\n#include "gfx.h"\n#include "array_count.h"\n#include "camera.h"\n\n']
    for t in textures:
        s.append(f"u64 {sym[t]}[] = {{\n#include \"{INC}/{t}.rgba16.inc.c\"\n}};\n\n")
    for p in pieces:
        vtx, dl = [], []
        last_kind = None
        for mat, tris in p.tris.items():
            kind = KIND.get(mat, "opa")
            if kind != "opa" or last_kind != "opa" or True:
                dl += material(mat, sym)
            last_kind = kind
            for k in range(0, len(tris), 5):  # 5 triangles (15 vertices) a load
                chunk = tris[k : k + 5]
                dl.append(f"    gsSPVertex(&gTime{p.name}Vtx[{len(vtx)}], {3 * len(chunk)}, 0),")
                for pts, uv, n, color in chunk:
                    c = shade(n, color) if kind != "beam" else (255, 255, 255)
                    for q, (u, v) in zip(pts, uv):
                        vtx.append(f"    VTX({int(round(q[0]))}, {int(round(q[1]))}, {int(round(q[2]))}, "
                                   f"{int(round(u * 32))}, {int(round(v * 32))}, {c[0]}, {c[1]}, {c[2]}, 255),")
                for i in range(0, len(chunk) - 1, 2):
                    dl.append(f"    gsSP2Triangles({3 * i}, {3 * i + 1}, {3 * i + 2}, 0, {3 * i + 3}, {3 * i + 4}, "
                              f"{3 * i + 5}, 0),")
                if len(chunk) % 2:
                    i = len(chunk) - 1
                    dl.append(f"    gsSP1Triangle({3 * i}, {3 * i + 1}, {3 * i + 2}, 0),")
        dl.append("    gsSPEndDisplayList(),")
        s.append(f"Vtx gTime{p.name}Vtx[] = {{\n" + "\n".join(vtx) + "\n};\n\n")
        s.append(f"Gfx gTime{p.name}DL[] = {{\n" + "\n".join(dl) + "\n};\n\n")
        if p.col:
            s.append(collision(p))
    return "".join(s)


def collision(p):
    vid, verts, polys = {}, [], []
    for tri in p.col:
        ids = []
        for q in tri:
            key = tuple(int(round(c)) for c in q)
            if key not in vid:
                vid[key] = len(verts)
                verts.append(key)
            ids.append(vid[key])
        if len(set(ids)) < 3:
            continue
        a, b, c = (np.array(verts[i], float) for i in ids)
        n = np.cross(b - a, c - a)
        if np.linalg.norm(n) < 1e-6:
            continue
        n /= np.linalg.norm(n)
        polys.append((ids, [int(round(x * 0x7FFF)) for x in n], int(round(-np.dot(n, a)))))
    arr = np.array(verts)
    lo, hi = arr.min(0), arr.max(0)
    nm = f"gTime{p.name}"
    wall = p.surf.get("wall", 0)
    hook = "true" if p.surf.get("hook") else "false"
    return "".join([
        f"Vec3s {nm}ColVtx[] = {{\n" + "".join(f"    {{ {v[0]}, {v[1]}, {v[2]} }},\n" for v in verts) + "};\n\n",
        f"CollisionPoly {nm}ColPolys[] = {{\n" +
        "".join(f"    {{ 0, {{ COLPOLY_VTX({i[0]}, 0), COLPOLY_VTX({i[1]}, 0), {i[2]} }}, {{ {n[0]}, {n[1]}, {n[2]} }}, {d} }},\n"
                for i, n, d in polys) + "};\n\n",
        f"SurfaceType {nm}ColSurfaces[] = {{\n    {{ {{ SURFACETYPE0(0, 0, FLOOR_TYPE_0, 0, WALL_TYPE_{wall}, FLOOR_PROPERTY_0, "
        f"false, false), SURFACETYPE1(SURFACE_MATERIAL_STONE, FLOOR_EFFECT_0, 0, 0, {hook}, CONVEYOR_SPEED_DISABLED, 0, "
        "false) } },\n};\n\n",
        f"CollisionHeader {nm}Col = {{\n    {{ {lo[0]}, {lo[1]}, {lo[2]} }},\n    {{ {hi[0]}, {hi[1]}, {hi[2]} }},\n"
        f"    ARRAY_COUNT({nm}ColVtx),\n    {nm}ColVtx,\n    ARRAY_COUNT({nm}ColPolys),\n    {nm}ColPolys,\n"
        f"    {nm}ColSurfaces,\n    NULL,\n    0,\n    NULL,\n}};\n\n"])


def plan_defines():
    """The plan, for En_Remix_Time (world coordinates)."""
    d = []

    def put(name, v):
        d.append(f"#define TIME_{name} {v}")

    put("DAIS_R", f"{T.DAIS_R}.0f")
    put("PLATE_R", f"{T.PLATE_R}.0f")
    put("PIT_R", f"{T.PIT_R}.0f")
    put("PEDESTAL_X", f"{T.PEDESTAL[0]}.0f")
    put("PEDESTAL_Z", f"{T.PEDESTAL[1]}.0f")
    put("PEDESTAL_TOP", f"{T.PEDESTAL_TOP}.0f")
    put("SPHERE_R", f"{T.SPHERE_R}.0f")
    put("CRADLE_PHI", f"0x{int(T.CRADLE_PHI / 360 * 65536) & 0xFFFF:04X}")
    put("CRADLE_R", f"{T.CRADLE_R}.0f")
    put("CRADLE_Y", f"{T.CRADLE_Y}.0f")
    put("LAUNCH_PHI", f"0x{int(T.LAUNCH_PHI / 360 * 65536) & 0xFFFF:04X}")
    put("RING_SPEED", T.RING_SPEED)
    put("WATER_HIGH", f"{T.WATER_HIGH}.0f")
    put("WATER_LOW", f"{T.WATER_LOW}.0f")
    for k, (x, z) in enumerate(T.MIRROR_CELLS):
        put(f"MIRROR_CELL{k}_X", f"{x}.0f")
        put(f"MIRROR_CELL{k}_Z", f"{z}.0f")
    for k, (x, z) in enumerate(T.BAL_CELLS):
        put(f"BAL_CELL{k}_X", f"{x}.0f")
        put(f"BAL_CELL{k}_Z", f"{z}.0f")
    put("BASIN_FLOOR", f"{T.BASIN['floor']}.0f")
    put("SPOT_X", f"{T.SPOT[0]}.0f")
    put("SPOT_Z", f"{T.SPOT[1]}.0f")
    put("SPOT_R", f"{T.SPOT_R}.0f")
    put("CEILING", f"{T.H}.0f")
    put("SUN_SYMBOL_X", f"{T.SUN_SYMBOL[0]}.0f")
    put("SUN_SYMBOL_Y", f"{T.SUN_SYMBOL[1]}.0f")
    put("SUN_SYMBOL_Z", f"{T.SUN_SYMBOL[2]}.0f")
    put("FACE_Z", f"{T.FACE_Z}.0f")
    put("EYE1_X", f"{T.EYE1[0]}.0f")
    put("EYE1_Y", f"{T.EYE1[1]}.0f")
    put("EYE2_X", f"{T.EYE2[0]}.0f")
    put("EYE2_Y", f"{T.EYE2[1]}.0f")
    put("UPPER", f"{T.UPPER}.0f")
    put("SOCKET_PLATE_X", f"{T.SOCKET_PLATE[0]}.0f")
    put("SOCKET_PLATE_Z", f"{T.SOCKET_PLATE[1]}.0f")
    put("HEAD_X", f"{T.HEAD_SPHERE[0]}.0f")
    put("HEAD_Y", f"{T.HEAD_SPHERE[1]}.0f")
    put("HEAD_Z", f"{T.HEAD_SPHERE[2]}.0f")
    put("GRATE_Y", f"{T.SOCKET['ceil']}.0f")
    put("PAN_R_X", f"{T.PAN_R[0]}.0f")
    put("PAN_R_Z", f"{T.PAN_R[1]}.0f")
    put("PAN_R_TOP", f"{T.PAN_R[2]}.0f")
    put("PAN_L_X", f"{T.PAN_L[0]}.0f")
    put("PAN_L_Z", f"{T.PAN_L[1]}.0f")
    put("WEIGHT_X", f"{T.WEIGHT[0]}.0f")
    put("WEIGHT_Y", f"{T.WEIGHT[1]}.0f")
    put("WEIGHT_Z", f"{T.WEIGHT[2]}.0f")
    put("WEIGHT_SIZE", f"{T.WEIGHT_SIZE}.0f")
    put("TILT_WEIGHT", f"{T.TILT_WEIGHT}.0f")
    put("TILT_PILLAR", f"{T.TILT_PILLAR}.0f")
    put("HOURGLASS_X", f"{T.HOURGLASS[0]}.0f")
    put("HOURGLASS_Y", f"{T.HOURGLASS[1]}.0f")
    put("HOURGLASS_Z", f"{T.HOURGLASS[2]}.0f")
    put("CLOCK_X", f"{T.CLOCK[0]}.0f")
    put("CLOCK_Y", f"{T.CLOCK[1]}.0f")
    put("CLOCK_Z", f"{T.CLOCK[2]}.0f")
    put("EXIT_X", f"{T.EXIT_DOOR[0]}.0f")
    put("FLAG_LOCK", T.FLAG_LOCK)
    put("FLAG_PLATE", T.FLAG_PLATE)
    put("FLAG_TORCHES", T.FLAG_TORCHES)
    put("FLAG_MOUTH", T.FLAG_MOUTH)
    put("FLAG_HAMMER", T.FLAG_HAMMER)
    put("FLAG_EYE1", T.FLAG_EYE1)
    put("FLAG_REVERSE", T.FLAG_REVERSE)
    put("FLAG_WEIGHT", T.FLAG_WEIGHT)
    put("FLAG_ALIVE", T.FLAG_ALIVE)
    put("FLAG_STAGE", f"0x{T.FLAG_STAGE:02X}")
    put("FLAG_MIRROR_CELL", f"0x{T.FLAG_MIRROR_CELL:02X}")
    put("FLAG_BAL_CELL", f"0x{T.FLAG_BAL_CELL:02X}")
    pts = T.track_points()
    put("TRACK_N", len(pts))
    d.append("#define TIME_TRACK_POINTS { " + ", ".join(f"{{ {x:.0f}, {y:.0f}, {z:.0f} }}" for x, y, z in pts) + " }")
    return "\n".join(d) + "\n"


HEADER = """#ifndef OBJECT_REMIX_TIME_H
#define OBJECT_REMIX_TIME_H

#include "ultra64.h"
#include "bgcheck.h"

// The Temple of Two Truths' pieces (tools/remix/make_time_parts.py), drawn and moved by En_Remix_Time, and the
// shrine's plan (tools/remix/time_plan.py) in world coordinates.

{defines}
{decls}
#endif
"""


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    textures = write_textures()
    pieces = build_pieces()
    (OUT / "object_remix_time.c").write_text(emit(pieces, textures))
    decls = "".join(f"extern Gfx gTime{p.name}DL[];\n" + (f"extern CollisionHeader gTime{p.name}Col;\n" if p.col else "")
                    for p in pieces)
    (OUT / "object_remix_time.h").write_text(HEADER.format(defines=plan_defines(), decls=decls))
    fmt = shutil.which("clang-format-14") or shutil.which("clang-format")
    if fmt:
        subprocess.run([fmt, "-i", "--style=file", str(OUT / "object_remix_time.c"), str(OUT / "object_remix_time.h")],
                       cwd=ROOT, check=True)
    print(f"Wrote {OUT.relative_to(ROOT)}: " + ", ".join(f"{p.name} {sum(len(t) for t in p.tris.values())}"
                                                        for p in pieces))


if __name__ == "__main__":
    main()
