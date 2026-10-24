#ifndef OBJECT_REMIX_WIND_H
#define OBJECT_REMIX_WIND_H

#include "ultra64.h"
#include "bgcheck.h"

// The Shrine of the Upside-Down Wind's pieces (tools/remix/make_wind_parts.py), drawn and moved by En_Remix_Wind, and
// the shrine's plan (tools/remix/wind_plan.py) in world coordinates.

#define WIND_CEIL 800.0f
#define WIND_COLUMN_X -370.0f
#define WIND_COLUMN_Z 400.0f
#define WIND_FAN_R 70.0f
#define WIND_CEIL_FAN_BOTTOM 740.0f
#define WIND_COLUMN_MID 360.0f
#define WIND_HOVER_MID 290.0f
#define WIND_HOVER_AMP 130.0f
#define WIND_HOVER_PERIOD 120
#define WIND_CUBE_SIZES \
    { 50.0f, 72.0f, 96.0f }
#define WIND_RIDE_TOP_CHILD 440.0f
#define WIND_RIDE_TOP_ADULT 230.0f
#define WIND_PLATE_X -150.0f
#define WIND_PLATE_Z -150.0f
#define WIND_PLATE_HALF 55.0f
#define WIND_PLATE_BOTTOM 780.0f
#define WIND_BRACKET_X -243.0f
#define WIND_BRACKET_Y 764.0f
#define WIND_BRACKET_Z -150.0f
#define WIND_TIMER_FRAMES 160
#define WIND_GATE_DROP -310.0f
#define WIND_GLASS_DROP -260.0f
#define WIND_LADDER2_LIFT 110.0f
#define WIND_HOLE_X -530.0f
#define WIND_HOLE_Z -540.0f
#define WIND_HOLE_HALF 30.0f
#define WIND_GLASS_CAP 430.0f
#define WIND_FLAG_FANS 1
#define WIND_FLAG_P1 2
#define WIND_FLAG_WEDGED 3
#define WIND_FLAG_BRACKET 4
#define WIND_FLAG_LADDER 5
#define WIND_FLAG_GLASS 6
#define WIND_FLAG_P2 7

extern Gfx gWindCubeSDL[];
extern CollisionHeader gWindCubeSCol;
extern Gfx gWindCubeMDL[];
extern CollisionHeader gWindCubeMCol;
extern Gfx gWindCubeLDL[];
extern CollisionHeader gWindCubeLCol;
extern Gfx gWindFanFloorDL[];
extern CollisionHeader gWindFanFloorCol;
extern Gfx gWindFanCeilingDL[];
extern CollisionHeader gWindFanCeilingCol;
extern Gfx gWindBladesDL[];
extern Gfx gWindPlateDL[];
extern CollisionHeader gWindPlateCol;
extern Gfx gWindBracketDL[];
extern Gfx gWindTimerDL[];
extern CollisionHeader gWindTimerCol;
extern Gfx gWindLadder1DL[];
extern CollisionHeader gWindLadder1Col;
extern Gfx gWindLadder2DL[];
extern CollisionHeader gWindLadder2Col;
extern Gfx gWindGateDL[];
extern CollisionHeader gWindGateCol;
extern Gfx gWindGlassDL[];
extern CollisionHeader gWindGlassCol;
extern Gfx gWindColumnDL[];

#endif
