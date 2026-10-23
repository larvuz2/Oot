"""The plan of the Temple of Two Truths (Web Remix level 6), shared by make_time.py (the room) and make_time_parts.py
(the moving pieces and the header En_Remix_Time reads its coordinates from).

One great round hall, y up, north is -z, the centre at (0, 0). Angles (phi) are measured from +z (south) towards +x
(east): x = r sin(phi), z = r cos(phi).
"""

import math

R, H = 1000, 1100  # the hall's radius and height
PIT_R, PIT_Y = 560, -900  # the bottomless pit inside the walkway, its void floor
DAIS_R = 200  # the central dais (top at y = 0)
PLATE_R = 70  # the clock-plate in its middle: the Song of Time works on it
BLUE_PAD, ORANGE_PAD, PAD_R = (-115, 70), (115, 70), 42  # where the child and the adult arrive

# the golden sphere's pedestal on the dais, the hookshot lintel over it
PEDESTAL = (0, -130)
PEDESTAL_R, PEDESTAL_TOP = 34, 60
SPHERE_R = 28
LINTEL = dict(x=80, z=-130, y0=230, y1=270, post=14)

# ring 1: a rotating stone band around the dais, four openings, a cradle on its inner face
RING_R0, RING_R1, RING_Y0, RING_Y1 = 410, 430, -300, 200
OPENINGS = [0, 80, 150, 290]  # centre angles (degrees) at rest
OPENING_W = 44
CRADLE_PHI, CRADLE_R, CRADLE_Y = 230, 390, -40  # where the sphere rides (its plate; the sphere sits on top)
RING_SPEED = 100  # binary angle units a frame (one turn in about 33 seconds)
LAUNCH_PHI = 165  # turning backwards, the cradle throws the sphere when it faces the scale's right pan

# four timed torches on pillars between the dais and the ring, at different heights
TORCH_R = 300
TORCHES = [(30, -100), (110, 20), (270, -40), (330, 80)]  # (phi, base height)
TORCH_COUNT = 1  # Obj_Syokudai: 50 * 1 + 110 frames, 8 seconds

# the curved track from the pedestal down to the cradle (at rest)
TRACK_N = 14

# the child era's bridge from the south walkway to the dais (through the ring's south opening)
BRIDGE_W = 100

# crystal switches: under the pedestal (boomerang, arrows, hookshot), and on the dais's south face (blasts only)
LOCK_CRYSTAL = (0, -70, -224)
BLAST_CRYSTAL = (0, -140, 214)

# the east basin (the lower chamber): the echo block, its three places, the drain, the sun through the ceiling
BASIN = dict(x0=610, x1=940, z0=-220, z1=220, floor=-120)
BASIN_STEPS = [(900, 940, -40), (860, 900, -80)]  # (x0, x1, top)
MIRROR_CELLS = [(760, 110), (760, 0), (760, -110)]  # 0 the drain, 1 in the sunbeam, 2 out of the way
SUN = MIRROR_CELLS[1]
SPOT = (650, -360)  # where the mirror throws the sunlight (on the walkway)
SPOT_R = 45
WATER_HIGH, WATER_LOW = -20, -1000
WATERBOX = (-560, 960, -560, 560)  # x0, x1, z0, z1

# the west wall: the way out behind a door, the sun symbol above it
EXIT_DOOR = (-1000, 0)
EXIT_ALCOVE = dict(x0=-1220, x1=-1000, z0=-130, z1=130)
EXIT_RING = (-1110, 0)
SUN_SYMBOL = (-995, 560, 0)

# the statue (north): its face is the chord at z = -900
FACE_Z = -900
FACE_X = int(math.sqrt(R * R - FACE_Z * FACE_Z))  # 435
EYE1 = (-220, 300)  # (x, y) on the face
EYE1_WIN = dict(x0=-280, x1=-160, y0=260, y1=345)
EYE2 = (0, 650)
EYE_R = 60
MOUTH = dict(x0=-110, x1=110, y1=240)
# inside the statue
CORRIDOR = dict(z0=-1050, z1=FACE_Z)
GAP = dict(z0=-1300, z1=-1050, x0=-320, x1=320, floor=-600)
LANDING = dict(z0=-1600, z1=-1300)
STAIRS = dict(x0=-320, x1=240, z0=-1600, z1=-1480, steps=7, top=260)
UPPER = 260
U_EAST = dict(x0=240, x1=320, z0=-1600, z1=-1250)
U_CROSS = dict(x0=-320, x1=320, z0=-1350, z1=-1250)
NARROW = dict(x0=-240, x1=-200, z0=-1250, z1=-1010)
SOCKET = dict(x0=-320, x1=-120, z0=-1010, z1=FACE_Z, ceil=420)
SOCKET_PLATE = (-220, -950)
HAMMER_SWITCH = (-160, -985)
HEAD_SPHERE = (-220, 475, -955)  # where the sphere waits above the grate
GRATE = dict(x=-220, z=-955, w=110, d=80)
FAR_TARGET = (0, 160, -1600)

# Phase V: the platform nobody can reach, the scale (two pans), the weight hanging over the left pan
HIGH = dict(x0=300, x1=420, z0=-900, z1=-780, top=300)
HIGH_TARGET = (360, 480)  # (x, y) on the face, above the platform
WEIGHT_SWITCH = (380, -830)
PAN_R = (220, -835, 300)  # right pan: x, z, top at rest
PAN_R_SIZE = 100
PAN_L = (520, -700, 0)  # left pan, flush with the walkway at rest
PAN_L_SIZE = 120
WEIGHT = (520, 450, -700)
WEIGHT_SIZE = 100
TILT_WEIGHT, TILT_PILLAR = 270, 80  # how far the weight, the grown pillar move the scale: both together, eye 2
BAL_CELLS = [(520, -560), (520, -700)]  # the second echo block: its spot, the left pan

# the child era's ramp up the statue's face to the first eye
RAMP = dict(x=-220, w=90, z0=-560, z1=-905)

# decor
HOURGLASS = (0, 640, 0)
CLOCK = (990, 640, 0)  # on the east wall, facing west
CLOCK_R = 170
WATERFALL_PHI, WATERFALL_W = 225, 200

# switch flags (scene) and the treasure flag
FLAG_LOCK, FLAG_PLATE, FLAG_TORCHES, FLAG_MOUTH, FLAG_HAMMER, FLAG_EYE1, FLAG_REVERSE, FLAG_WEIGHT, FLAG_ALIVE = \
    1, 2, 3, 4, 5, 6, 7, 8, 9
FLAG_STAGE = 0x10  # 4 bits: where the sphere is
FLAG_MIRROR_CELL = 0x14  # 2 bits
FLAG_BAL_CELL = 0x16  # 1 bit
T_CHEST = 1

SPHERE_STAGES = ["PEDESTAL", "RING", "HEAD", "PAN", "EYE2", "SEED_EYE1"]


def polar(phi_deg, r):
    a = math.radians(phi_deg)
    return r * math.sin(a), r * math.cos(a)


def track_points():
    """The curved track from the pedestal's lip down to the cradle (ring at rest): a quarter spiral."""
    pts = []
    p0 = math.degrees(math.atan2(PEDESTAL[0], PEDESTAL[1])) % 360  # 180 (north)
    r0 = abs(PEDESTAL[1])
    for k in range(TRACK_N + 1):
        t = k / TRACK_N
        phi = p0 + (CRADLE_PHI - p0) * t
        r = r0 + (CRADLE_R - r0) * (t ** 0.8)
        y = PEDESTAL_TOP + SPHERE_R + (CRADLE_Y + SPHERE_R - PEDESTAL_TOP - SPHERE_R) * (1 - math.cos(t * math.pi / 2))
        x, z = polar(phi, r)
        pts.append((x, y, z))
    return pts
