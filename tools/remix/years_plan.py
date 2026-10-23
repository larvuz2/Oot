"""The plan of the Shrine of Seven Years (Web Remix level 7), shared by make_years.py (the room) and
make_years_parts.py (the moving pieces, and the header En_Remix_Years reads its coordinates from).

y up, north is -z. The Master Sword's hall (Temple of Time style) is in the south, z 0..700; the puzzle chamber behind
the Door of Time arch runs north to z -1800, the reward room beyond its exit door.
"""

# the hall of the Master Sword
HALL_X, HALL_Z0, HALL_Z1, HALL_H = 450, 0, 700, 720
PEDESTAL = (0, 360)  # the pedestal on its dais
DAIS_R, DAIS_H = 140, 24
SPAWN_AT_PEDESTAL = (0, 24, 440)  # where Link stands after time turns (facing the pedestal, north)
ARCH_X, ARCH_H = 160, 380  # the Door of Time's arch at z = 0

# the puzzle chamber
X0, X1, Z0, Z1, H = -800, 800, -1800, 0, 1000
UPPER_Z = -1450  # the upper floor: z -1800..-1450, all across
UPPER_Y = 330
LANDING = dict(x0=480, x1=800, z0=-1800, z1=-1550, top=600)  # the exit landing, up on the upper floor's east end
DOOR = dict(x0=500, x1=720, y1=310)  # the massive exit door (in the north wall, on the landing)
SLIT = dict(x0=740, x1=790, h=64)  # the narrow opening beside it
REWARD = dict(x0=480, x1=800, z0=-2200, z1=-1800, ceil=950)  # behind the door
PLINTH = dict(x=640, z=-2080, w=140, h=90)  # the reward, out of a child's reach
FLOOR_SWITCH = (765, -1900)

# 4. the final staircase: from the upper floor up to the landing, flying over the upper floor
STAIRS = dict(x0=30, x1=LANDING["x0"], z0=-1650, z1=-1550, steps=10, slab=20)
BROKEN_STEPS = (3, 4, 5, 6)  # what has fallen in seven years without its support
SUPPORT_CELLS = [(280, -1480), (280, -1540), (280, -1600)]  # the last: under the stairs' middle
SUPPORT_W, SUPPORT_H = 70, 142

# the east stairs: up to the upper floor in the past, rotted away in the future
EAST_STAIRS = dict(x0=700, x1=800, z0=-500, z1=UPPER_Z, steps=15)

# 1. the small door: an aperture in the west wall, the little room behind it, the cube
APERTURE = dict(z=-400, w=70, h=64)
CRAWL_ROOM = dict(x0=-1060, x1=X0, z0=-520, z1=-280, ceil=200)
CUBE = 60
CUBE_CELLS = [(-950, -400), (-800, -400), (-700, -400), (-700, -560), (-700, -700), (-700, -805)]
MEDALLION = (-1010, -470)  # the golden medallion, in a corner of the little room

# 2./3. the garden: walled in, its south wall (past: a wall with a child's doorway; future: a mound of rubble)
GARDEN = dict(x0=X0, x1=-350, z0=UPPER_Z, z1=-900)
GARDEN_DOOR = dict(x=-575, w=50, h=64)
RUBBLE = dict(z0=-960, z1=-840, h=160, step_h=80)
PLANTER_CELLS = [(-720, -1100), (-575, -1100), (-575, -1390)]  # west (the ledge), middle (nothing), north (the upper floor)
PLANTER_START = 1
PLANTER = 80
TREE_H = 350  # the grown tree's branches: at the upper floor's height
WEST_LEDGE = dict(x0=X0, x1=-730, z0=-1180, z1=-1020, top=UPPER_Y)

# 5. the secret: a crack in the east wall (an opening the roots seal in the future), the alcove behind
CRACK = dict(z=-300, w=140, h=200, crack_w=50, crack_h=64)
ALCOVE = dict(x0=X1, x1=1000, z0=-400, z1=-200, ceil=230)
CAVITY = (900, -300)

# switch flags (scene) and treasure flags
FLAG_DOOR, FLAG_MEDALLION, FLAG_ROOTS = 5, 6, 7
FLAG_CUBE, FLAG_PLANTER, FLAG_SUPPORT = 0x10, 0x13, 0x15  # 3, 2, 2 bits: where each was left
T_HEART, T_SECRET, T_LEDGE = 1, 2, 3
