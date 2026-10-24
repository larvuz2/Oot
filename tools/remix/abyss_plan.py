"""The plan of the Shrine of the Swinging Abyss (Web Remix level 9), shared by make_abyss.py (the rooms) and
make_abyss_parts.py (the pieces, and the header En_Remix_Abyss reads its coordinates and motions from).

A small stone room (earn the Hookshot) and, through its north door, one enormous bottomless chamber of moving
platforms. y up, north is -z; the arrival chamber is south of the stone room. Times are in game frames (20 a second).

    python3 tools/remix/abyss_plan.py     # simulates the platforms and checks every intended grapple
"""

from __future__ import annotations

import math

HOOK = 240  # what the Hookshot reaches comfortably (it flies 13 frames x 20 units); Z-targeting locks on within 240
CHEST_Y = 45  # Link's chest above his feet, where he aims from
FALL_Y = -400  # below this Link has fallen into the abyss: back to the start of the gauntlet

# ---------------------------------------------------------------- the stone room (the Hookshot's chest)

ROOM = dict(x0=-300, x1=300, z0=200, z1=800, h=300)
DOOR = dict(x=0, w=120, h=170)  # in the north wall: opens once the Hookshot is in hand
CUBE = 60  # the stone cube
CUBE_CELLS = [(230, 400), (230, 570)]  # where it starts, on the ramp (pushed south)
RAMP = dict(x=230, z0=520, z1=620, w=110, lift=40)  # a stone slab; the crystal raises its north end
CURB = dict(z0=620, z1=640, h=30)  # between the ramp and the trench: the cube can't be pushed over it
TRENCH = dict(x0=150, x1=310, z0=640, z1=740, depth=60)
SWITCH = (230, 690)  # the floor switch at the trench's bottom (held while something stands on it)
ALCOVE = dict(x0=170, x1=290, z0=800, z1=900)  # behind the bars, in the south wall
BARS = dict(x=230, z=800, w=120, h=150)
CHEST_HOOK = (230, 860)
CRYSTAL = (-180, 170, 200)  # high on the north wall (its centre); a thrown stone lights it
THROW_SPOT = (-180, 300)  # marked on the floor: about where a throw meets the crystal
ROCKS = [(-180, 265), (-230, 330), (-130, 330), (-260, 260)]

# ---------------------------------------------------------------- the abyss

ABYSS = dict(x0=-950, x1=950, z0=-3800, z1=200, floor=-1100, ceil=1500)
START = dict(x0=-160, x1=160, z0=-60, z1=200, top=0)  # the ledge through the door
RESPAWN = (0, 0, -20)  # where a fall brings Link back (facing north): near the edge, the pendulum in reach

# platform kinds
PENDULUM, ORBIT, LIFT, SHUTTLE = range(4)

# Every platform: a stone slab (w x d, its top at the position) with a Hookshot target (a plaque on a post, facing
# the platform's local +z turned by `yaw`; for an orbit, outwards). crumble: an unsafe target, the slab breaks away
# a moment after Link lands on it (and comes back later).
P = []


def plat(name, kind, w=150, d=150, yaw=0.0, plaque=(0, 0), ph=70, crumble=False, **m):
    P.append(dict(name=name, kind=kind, w=w, d=d, yaw=yaw, plaque=plaque, ph=ph, crumble=crumble, **m))
    return len(P) - 1


# 1. the pendulum: swings slowly left and right in front of the start ledge
I_P1 = plat("pendulum", PENDULUM, w=160, d=160, pivot=(0, 700, -220), length=640, amp=34, period=240, phase=0.0,
            axis=0.0)
# 2. the carousel: four platforms round a stone column; their targets face outwards (one is cracked)
CAROUSEL = (-680, -520)
CAROUSEL_TOP, CAROUSEL_R = 240, 220
I_C = [plat(f"carousel{k}", ORBIT, w=140, d=140, center=CAROUSEL, radius=CAROUSEL_R, top=CAROUSEL_TOP, period=320,
            phase=0.5625 + k * 0.25, crumble=(k == 2)) for k in range(4)]  # (one comes round each westward swing)
# 3. the rising towers: three narrow platforms moving up and down at their own speeds
I_T = [plat("tower1", LIFT, w=100, d=100, at=(-560, -920), lo=-60, hi=420, period=220, phase=0.0),
       plat("tower2", LIFT, w=100, d=100, at=(-380, -1050), lo=150, hi=600, period=160, phase=0.3),
       plat("tower3", LIFT, w=100, d=100, at=(-200, -1130), lo=300, hi=700, period=300, phase=0.45)]
# 4. the vanishing target: a long platform runs north through a stone tunnel and back
SHUTTLE_X, SHUTTLE_TOP = 30, 560
I_SH = plat("shuttle", SHUTTLE, w=260, d=140, a=(SHUTTLE_X, SHUTTLE_TOP, -1200), b=(SHUTTLE_X, SHUTTLE_TOP, -1800),
            move=100, dwell=50, phase=0.0, plaque=(90, 0), yaw=-90.0)  # (long along z; its target faces west)
TUNNEL = dict(x0=-140, x1=200, z0=-1600, z1=-1350, y0=380, y1=860, px0=-60, px1=120, py0=520, py1=780)
LEDGE4 = dict(x0=-60, x1=120, z0=-2050, z1=-1935, top=560)
# 5. the crossing paths: A along x, B (higher) along z; their paths cross over one point
I_A = plat("crossA", SHUTTLE, w=150, d=150, a=(0, 560, -2120), b=(-760, 560, -2120), move=240, dwell=40, phase=0.0,
           yaw=180.0)
I_B = plat("crossB", SHUTTLE, w=150, d=150, a=(-400, 660, -2270), b=(-400, 660, -2610), move=200, dwell=80,
           phase=0.3)  # (its south end just north of A's path, higher: A passes under its target)
LINTEL = dict(x0=-820, x1=-640, z0=-2210, z1=-2030, y0=590, y1=900)  # A carries Link into it
LEDGE5 = dict(x0=-480, x1=-320, z0=-2800, z1=-2690, top=700)  # (a step up from B)
# 6. the clockwork storm: six platforms round the central mechanism; the exit on top, inside a turning ring
CORE = (0, -3350)
CORE_R, BALCONY_R, BALCONY_TOP = 160, 200, 1000
PILLAR = dict(r=70, top=1160)  # the final target: every face of the pillar in the balcony's middle
RING = dict(r=230, y0=900, y1=1150, gap=100, period=-240)  # turning the other way; one opening
EXIT_PAD = (0, BALCONY_TOP, CORE[1] + 140)
CHEST_HEART = (-110, CORE[1] + 90)
I_S6 = plat("swing", PENDULUM, w=160, d=160, pivot=(-300, 1300, -2950), length=520, amp=30, period=200, phase=0.0,
            axis=0.0)
I_E = plat("elevator", LIFT, w=100, d=100, at=(-560, -3150), lo=700, hi=950, period=210, phase=0.1, yaw=0.0)
I_R = plat("rotor", ORBIT, w=150, d=160, center=CORE, radius=330, top=960, period=420, phase=0.62, plaque=(0, 40))
I_O = [plat("orbit1", ORBIT, w=140, d=140, center=CORE, radius=470, top=600, period=-300, phase=0.1, crumble=True),
       plat("orbit2", ORBIT, w=140, d=140, center=CORE, radius=520, top=350, period=420, phase=0.4, crumble=True),
       plat("orbit3", ORBIT, w=140, d=140, center=CORE, radius=300, top=700, period=-260, phase=0.75, crumble=True)]

# the hidden treasure: a ledge under the carousel, the target on the underside of the flange over it
HIDDEN_DIR = math.atan2(-560 - CAROUSEL[0], -920 - CAROUSEL[1])  # from the column towards tower 1
HIDDEN = dict(r=255, top=0, size=110, flange_y=110)
CHEST_HIDDEN = (CAROUSEL[0] + math.sin(HIDDEN_DIR) * (HIDDEN["r"] + 20),
                CAROUSEL[1] + math.cos(HIDDEN_DIR) * (HIDDEN["r"] + 20))

# switch flags (the room), treasure flags
FLAG_RAMP, FLAG_BARS, FLAG_CUBE_RAMP, FLAG_CUBE_IN = 1, 2, 3, 4
T_HOOK, T_HIDDEN, T_HEART = 1, 2, 3


# ---------------------------------------------------------------- motion (the same as z_en_remix_abyss.c)


def pos(p, t):
    """(x, top y, z, yaw degrees) of platform p at frame t."""
    k = p["kind"]
    if k == PENDULUM:
        th = math.radians(p["amp"]) * math.sin(2 * math.pi * (t / p["period"] + p["phase"]))
        px, py, pz = p["pivot"]
        ax = math.radians(p["axis"])
        s = p["length"] * math.sin(th)
        return px + s * math.cos(ax), py - p["length"] * math.cos(th), pz - s * math.sin(ax), p["yaw"]
    if k == ORBIT:
        a = 2 * math.pi * (t / p["period"] + p["phase"])
        cx, cz = p["center"]
        return cx + p["radius"] * math.sin(a), p["top"], cz + p["radius"] * math.cos(a), math.degrees(a) + p["yaw"]
    if k == LIFT:
        c = math.cos(2 * math.pi * (t / p["period"] + p["phase"]))
        x, z = p["at"]
        return x, (p["lo"] + p["hi"]) / 2 - (p["hi"] - p["lo"]) / 2 * c, z, p["yaw"]
    # shuttle: dwell at a, move to b, dwell at b, move back
    cyc = 2 * (p["move"] + p["dwell"])
    u = (t + p["phase"] * cyc) % cyc
    if u < p["dwell"]:
        f = 0.0
    elif u < p["dwell"] + p["move"]:
        f = (u - p["dwell"]) / p["move"]
    elif u < 2 * p["dwell"] + p["move"]:
        f = 1.0
    else:
        f = 1.0 - (u - 2 * p["dwell"] - p["move"]) / p["move"]
    f = 0.5 - 0.5 * math.cos(math.pi * f)  # (eased)
    a, b = p["a"], p["b"]
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, p["yaw"]


def plaque(p, t):
    """The target's centre (on the plaque's face) and the direction it faces."""
    x, y, z, yaw = pos(p, t)
    lx, lz = p["plaque"]
    r = math.radians(yaw)
    wx = x + lx * math.cos(r) + lz * math.sin(r)
    wz = z - lx * math.sin(r) + lz * math.cos(r)
    return (wx, y + p["ph"], wz), (math.sin(r), math.cos(r))


def can_grapple(frm, p, t, margin=0.0):
    """Link standing at frm (x, y, z feet) can grapple platform p's target at frame t: in range and in front of it."""
    (tx, ty, tz), (fx, fz) = plaque(p, t)
    dx, dy, dz = frm[0] - tx, frm[1] + CHEST_Y - ty, frm[2] - tz
    if math.sqrt(dx * dx + dy * dy + dz * dz) >= HOOK - margin or dx * fx + dz * fz <= 20:
        return False
    # the chain passes over the platform's own edge, not through it
    x, y, z, yaw = pos(p, t)
    r = math.radians(yaw)
    for k in range(1, 20):
        u = k / 20
        sx, sy, sz = tx + dx * u, ty + dy * u, tz + dz * u
        lx = (sx - x) * math.cos(r) - (sz - z) * math.sin(r)
        lz = (sx - x) * math.sin(r) + (sz - z) * math.cos(r)
        if abs(lx) < p["w"] / 2 and abs(lz) < p["d"] / 2 and y - 32 < sy < y + 4:
            return False
    return True


def stand(p, t, inset=30):
    """The points of platform p's top Link could stand on (its edge, `inset` in), as (x, y, z)."""
    x, y, z, yaw = pos(p, t)
    r = math.radians(yaw)
    out = []
    for lx in (-p["w"] / 2 + inset, 0, p["w"] / 2 - inset):
        for lz in (-p["d"] / 2 + inset, 0, p["d"] / 2 - inset):
            out.append((x + lx * math.cos(r) + lz * math.sin(r), y, z - lx * math.sin(r) + lz * math.cos(r)))
    return out


def windows(frm_fn, targets, horizon=2400):
    """Frames at which some standing point frm_fn(t) can grapple one of the target platforms."""
    if isinstance(targets, dict):
        targets = [targets]
    return [t for t in range(horizon) if any(can_grapple(f, p, t, margin=10) for f in frm_fn(t) for p in targets)]


def check():
    """Every intended grapple has windows (of at least a second); the pendulum can't be reached by jumping; the
    final target only from the rotor, through the ring's opening."""
    ledge = lambda t: [(x, START["top"], START["z0"] + 20) for x in (-60, 0, 60)]  # noqa: E731
    hops = [("start -> pendulum", ledge, P[I_P1])]
    hops.append(("pendulum -> carousel", lambda t: stand(P[I_P1], t), [P[c] for c in I_C if not P[c]["crumble"]]))
    hops.append(("carousel -> tower 1", lambda t: [s for c in I_C for s in stand(P[c], t)], P[I_T[0]]))
    hops.append(("tower 1 -> tower 2", lambda t: stand(P[I_T[0]], t), P[I_T[1]]))
    hops.append(("tower 2 -> tower 3", lambda t: stand(P[I_T[1]], t), P[I_T[2]]))
    hops.append(("tower 3 -> shuttle", lambda t: stand(P[I_T[2]], t), P[I_SH]))
    hops.append(("crossing A -> B", lambda t: stand(P[I_A], t), P[I_B]))
    l5 = lambda t: [(x, LEDGE5["top"], LEDGE5["z0"] + 20) for x in (-440, -400, -360)]  # noqa: E731
    hops.append(("ledge 5 -> swing", l5, P[I_S6]))
    hops.append(("swing -> elevator", lambda t: stand(P[I_S6], t), P[I_E]))
    hops.append(("elevator -> rotor", lambda t: stand(P[I_E], t), P[I_R]))
    report = []
    for name, f, p in hops:
        w = windows(f, p)
        runs, cur = [], 0
        for i, t in enumerate(w):
            cur = cur + 1 if i and t == w[i - 1] + 1 else 1
            if i == len(w) - 1 or w[i + 1] != t + 1:
                runs.append(cur)
        best = max(runs) if runs else 0
        report.append(f"{name}: {len(runs)} windows, longest {best / 20:.1f}s" + ("" if best >= 20 else "  <-- TOO SHORT"))
    # the final shot: from the rotor, through the ring's opening, to the pillar
    shots = 0
    for t in range(2400):
        x, y, z, _ = pos(P[I_R], t)
        a = math.atan2(x - CORE[0], z - CORE[1])
        ring = 2 * math.pi * t / RING["period"]
        gap = math.degrees((a - ring + math.pi) % (2 * math.pi) - math.pi)
        inner = math.hypot(x - CORE[0], z - CORE[1]) - P[I_R]["d"] / 2 + 20
        dist = math.hypot(inner - PILLAR["r"], (PILLAR["top"] + BALCONY_TOP) / 2 - (y + CHEST_Y))
        if abs(gap) < math.degrees(RING["gap"] / 2 / RING["r"]) and dist < HOOK:
            shots += 1
    report.append(f"rotor -> pillar through the ring: {shots / 20:.1f}s in 2 minutes" + ("" if shots >= 40 else "  <-- TOO SHORT"))
    # nothing reaches the pillar but the rotor
    for i in (I_S6, I_E, *I_O):
        for t in range(0, 2400, 5):
            for s in stand(P[i], t):
                r = math.hypot(s[0] - CORE[0], s[2] - CORE[1])
                if not (r - PILLAR["r"] > HOOK - 10 or s[1] + CHEST_Y < BALCONY_TOP - 120):
                    report.append(f"{P[i]['name']} reaches the pillar  <-- WRONG")
                    break
    assert not any("<--" in line for line in report), "\n".join(report)
    return report


if __name__ == "__main__":
    for line in check():
        print(line)
