"""Where the Ancient Plateau's town goes: building plots around the central plaza, and the town's people.

Shared by make_level.py (flattens the plots, keeps trees and props off them, places the townspeople) and
make_town.py (puts the buildings borrowed from the game's towns on the plots at build time).
"""

import math

# The four paths leave the plaza at 0, 90, 180 and 270 degrees (make_level.PATH_ANGLES), so the town fills the
# four quarters between them: an inner ring of houses facing the plaza across the monoliths, and an outer ring.
TOWN_INNER, TOWN_OUTER = 1900, 2650  # plot distances from the Spire
TOWN_FLAT_R = (1350, 3150)  # the ground is flattened between these distances (gentle town terraces)


def _plots():
    out = []
    for q in range(4):
        mid = math.pi / 4 + q * math.pi / 2
        for r, offs in ((TOWN_INNER, (-0.27, 0.27)), (TOWN_OUTER, (-0.33, 0.0, 0.33))):
            for o in offs:
                a = mid + o
                x, z = math.sin(a) * r, math.cos(a) * r
                out.append(dict(x=round(x), z=round(z), face=math.atan2(-x, -z), r=360 if r == TOWN_INNER else 400,
                                ring="inner" if r == TOWN_INNER else "outer", quarter=q))
    return out


PLOTS = _plots()  # 20 plots: 2 inner + 3 outer per quarter; `face` is the yaw (radians) toward the Spire


def near_plot(x, z, margin=0.0):
    """True when (x, z) is on a building plot (plus margin)."""
    return any(math.hypot(x - p["x"], z - p["z"]) < p["r"] + margin for p in PLOTS)


RING_ROAD_R = 1075  # a dirt road around the plaza, between its stairs and the monoliths
LANE_HALF = 46  # half width of the town's lanes (the four main paths are 112)


def _polar(r, a):
    return (math.sin(a) * r, math.cos(a) * r)


def lanes():
    """The town's streets as polylines [(x, z), ...]: in each quarter a main street from the ring road to the far
    house, and lanes from it to the front of every other house (bent to pass between the monoliths)."""
    out = []
    for q in range(4):
        mid = math.pi / 4 + q * math.pi / 2
        plots = [p for p in PLOTS if p["quarter"] == q]
        far = min(plots, key=lambda p: abs(math.atan2(math.sin(math.atan2(p["x"], p["z"]) - mid),
                                                       math.cos(math.atan2(p["x"], p["z"]) - mid))) - p["r"] / 1e4
                  if p["ring"] == "outer" else 9)
        front_r = math.hypot(far["x"], far["z"]) - far["r"] * 0.55
        out.append([_polar(r, mid) for r in (RING_ROAD_R, 1500, 2000, front_r)])
        for p in plots:
            if p is far:
                continue
            a = math.atan2(p["x"], p["z"])
            da = math.atan2(math.sin(a - mid), math.cos(a - mid))
            r = math.hypot(p["x"], p["z"])
            front = _polar(r - p["r"] * 0.55, a)
            if p["ring"] == "inner":
                out.append([front, _polar(1550, mid + da * 0.5), _polar(1400, mid)])
            else:
                out.append([front, _polar(2250, mid + da * 0.45), _polar(2000, mid)])
    return out


def ring_road():
    return [_polar(RING_ROAD_R, 2 * math.pi * k / 48) for k in range(49)]


# ---------------------------------------------------------------- the sky island (north of the town)
# make_level.py builds the island, the floating rocks that lead up to it and its waterfall; make_town.py hangs
# Zora's River's rope bridge between the island and the islet beyond it.

ISLAND_A = math.radians(166)  # direction from the Spire
ISLAND = dict(x=math.sin(ISLAND_A) * 3330, z=math.cos(ISLAND_A) * 3330, top=960, r=330)
_ISLET_D = 920  # from the island's center, further out
ISLET = dict(x=ISLAND["x"] + math.sin(ISLAND_A + 0.55) * _ISLET_D, z=ISLAND["z"] + math.cos(ISLAND_A + 0.55) * _ISLET_D,
             top=ISLAND["top"] + 40, r=170)


def bridge_ends():
    """((x, y, z), (x, y, z)): where the rope bridge meets the island's and the islet's edges."""
    dx, dz = ISLET["x"] - ISLAND["x"], ISLET["z"] - ISLAND["z"]
    d = math.hypot(dx, dz)
    ux, uz = dx / d, dz / d
    a = (ISLAND["x"] + ux * (ISLAND["r"] - 20), ISLAND["top"], ISLAND["z"] + uz * (ISLAND["r"] - 20))
    b = (ISLET["x"] - ux * (ISLET["r"] - 20), ISLET["top"], ISLET["z"] - uz * (ISLET["r"] - 20))
    return a, b


# ---------------------------------------------------------------- scenery models (gameplay_field_keep)
# kind -> (display list in gameplay_field_keep, scale its actors draw it at, recolored to glow). link_level_assets.py
# splits each into a setup list (texture, render mode: once per group) and a geometry list (drawn per copy); make_level.py
# places them (ANCIENT_DECOR_<KIND>_SETUP / _GEOM).
DECOR_SOURCES = {
    "bush": ("gFieldBushDL", 0.4, True),
    "green_bush": ("gFieldBushDL", 0.4, False),
    "pebble": ("gFieldKakeraDL", 0.1, False),
    "rock": ("gSilverRockDL", 0.4, False),
    "flower": ("gHanaDL", 0.01, False),
}
