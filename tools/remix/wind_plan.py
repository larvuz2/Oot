"""The plan of the Shrine of the Upside-Down Wind (Web Remix level 8), shared by make_wind.py (the room) and
make_wind_parts.py (the pieces, and the header En_Remix_Wind reads its coordinates from).

One chamber with two floors: the ground, and the ceiling (where the exit is, right above the entrance). y up, north
is -z. The entrance is in the south wall (z = Z1), at x = 0.
"""

X0, X1, Z0, Z1, CEIL = -600, 600, -700, 700, 800

# the column of wind: the floor fan, the ceiling fan right above it (its housing is the second ceiling switch). Beside
# the middle balcony, under the west end of the exit platform.
COLUMN = (-370, 400)
FAN_R = 70
CEIL_FAN_BOTTOM = CEIL - 60  # the ceiling fan's housing hangs down to here
# Blue (the wind blows up): a light or medium cube dances in the column, its bottom between HOVER_MID - HOVER_AMP and
# HOVER_MID + HOVER_AMP. Orange (the wind turned): a cube whose bottom is above COLUMN_MID is pulled up against the
# ceiling fan, one below it falls.
HOVER_MID, HOVER_AMP, HOVER_PERIOD = 290, 130, 120
COLUMN_MID = 360

# the three iron cubes: size (and how the fans treat them), where each starts
CUBES = [dict(size=50, home=COLUMN),  # light: dancing in the wind from the start; fits through the glass room's hole
         dict(size=72, home=(150, -300)),  # medium: the fans lift it; fits the bracket
         dict(size=96, home=(-150, -150))]  # heavy: too heavy for the fans; starts under its ceiling switch
RIDE_TOP = dict(child=440, adult=230)  # how high the floor fan lifts a cube's top with Link standing on it

# the first ceiling switch (heavy) and the bracket beside it
PLATE = dict(x=-150, z=-150, w=110, t=20)
BRACKET = (PLATE["x"] - 55 - 36 - 2, CEIL - 36, PLATE["z"])  # where the medium cube locks (its centre)

# the middle balcony (west wall, a solid block), its ladder in an alcove behind a gate, the crystal that turns the wind
BALCONY = dict(x0=X0, x1=-460, z0=-380, z1=470, top=300)
LADDER1 = dict(x=-460, z=0, w=70)
GATE1 = dict(x=-436, z=0, w=130, h=300)  # (jambs from the balcony to the gate on both sides)
CRYSTAL_FANS = (-530, 380)
TIMER = (-150, 130)  # the timed switch: eight seconds of upside-down gravity for every loose object
TIMER_FRAMES = 160

# the exit platform hanging under the ceiling above the entrance, the final ladder down from it over the column
EXIT_PLATFORM = dict(x0=-440, x1=200, z0=432, z1=Z1, top=620, t=30)
LADDER2 = dict(x=COLUMN[0], z=432, w=70, bottom=450, lift=110)  # extended; folded up by `lift` until then
EXIT_RING = (0, 620)
CHEST_EXIT = (120, 540)

# the hidden treasure: a glass chamber on the west wall north of the balcony, a hole in its floor, an iron shelf over
# the hole with a crystal on it (a cube falling upwards through the hole strikes the shelf)
GLASS_ROOM = dict(x0=X0, x1=-460, z0=Z0, z1=-380, floor=300, t=30, ceil=520)
HOLE = dict(x=-530, z=-540, w=60)
GLASS_CAP = 430  # the shelf's underside
CRYSTAL_GLASS = (-530, GLASS_CAP + 10, -540)
CHEST_GLASS = (-530, -440)

# the Master Sword's pedestal (En_Remix_Years): the child is light enough to ride the cube up to the final ladder
PEDESTAL = (380, 420)
SPAWN_AT_PEDESTAL = (380, 20, 345)  # (on its dais)

# switch flags
FLAG_FANS, FLAG_P1, FLAG_WEDGED, FLAG_BRACKET, FLAG_LADDER, FLAG_GLASS, FLAG_P2 = 1, 2, 3, 4, 5, 6, 7
T_HEART, T_GLASS = 1, 2
