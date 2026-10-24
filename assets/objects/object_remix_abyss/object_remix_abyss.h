#ifndef OBJECT_REMIX_ABYSS_H
#define OBJECT_REMIX_ABYSS_H

#include "ultra64.h"
#include "bgcheck.h"

// The Shrine of the Swinging Abyss's pieces (tools/remix/make_abyss_parts.py), drawn and moved by En_Remix_Abyss, and
// the shrine's plan (tools/remix/abyss_plan.py) in world coordinates.

// A moving platform: kind (0 pendulum, 1 orbit, 2 lift, 3 shuttle), slab size, yaw, the target plaque's place
// (local x, z, height), whether it breaks away under Link, and its motion:
//   pendulum: pivot x, y, z, length, amplitude (degrees), period, phase, swing direction (degrees)
//   orbit:    centre x, top, centre z, radius, period (negative: clockwise), phase
//   lift:     x, z, lowest top, highest top, period, phase
//   shuttle:  a x, y, z, b x, y, z, frames moving, frames waiting at each end, phase
typedef struct AbyssPlatInfo {
    s16 kind;
    s16 w;
    s16 d;
    s16 yaw;
    s16 plaqueX;
    s16 plaqueZ;
    s16 plaqueY;
    s16 crumble;
    f32 m[9];
} AbyssPlatInfo;

#define ABYSS_HOOK_RANGE 240.0f
#define ABYSS_FALL_Y -400.0f
#define ABYSS_RESPAWN_X 0.0f
#define ABYSS_RESPAWN_Y 0.0f
#define ABYSS_RESPAWN_Z 100.0f
#define ABYSS_CUBE_SIZE 60.0f
#define ABYSS_CUBE_CELLS \
    {                    \
        { 230, 400 }, {  \
            230, 570     \
        }                \
    }
#define ABYSS_RAMP_X 230.0f
#define ABYSS_RAMP_Z 570.0f
#define ABYSS_RAMP_HINGE_Z 620.0f
#define ABYSS_RAMP_LIFT 40.0f
#define ABYSS_TRENCH_Y -60.0f
#define ABYSS_SWITCH_X 230.0f
#define ABYSS_SWITCH_Z 690.0f
#define ABYSS_BARS_H 150.0f
#define ABYSS_DOOR_H 170.0f
#define ABYSS_CRYSTAL_X -180.0f
#define ABYSS_CRYSTAL_Y 170.0f
#define ABYSS_CRYSTAL_Z 225.0f
#define ABYSS_RING_PERIOD -240
#define ABYSS_CORE_X 0.0f
#define ABYSS_CORE_Z -3350.0f
#define ABYSS_FLAG_RAMP 1
#define ABYSS_FLAG_BARS 2
#define ABYSS_FLAG_CUBE_RAMP 3
#define ABYSS_FLAG_CUBE_IN 4
#define ABYSS_T_HOOK 1
#define ABYSS_T_HIDDEN 2
#define ABYSS_T_HEART 3
#define ABYSS_PLATS_N 17
#define ABYSS_PLATS                                                                                                        \
    {                                                                                                                      \
        { 0,  160, 160,                                                                                                    \
          0,  0,   0,                                                                                                      \
          70, 0,   { 0.0000f, 700.0000f, -220.0000f, 640.0000f, 34.0000f, 240.0000f, 0.0000f, 0.0000f, 0.0000f } },        \
            { 1,  140, 140,                                                                                                \
              0,  0,   0,                                                                                                  \
              70, 0,   { -680.0000f, 240.0000f, -520.0000f, 220.0000f, 320.0000f, 0.5625f, 0.0000f, 0.0000f, 0.0000f } },  \
            { 1,  140, 140,                                                                                                \
              0,  0,   0,                                                                                                  \
              70, 0,   { -680.0000f, 240.0000f, -520.0000f, 220.0000f, 320.0000f, 0.8125f, 0.0000f, 0.0000f, 0.0000f } },  \
            { 1,  140, 140,                                                                                                \
              0,  0,   0,                                                                                                  \
              70, 1,   { -680.0000f, 240.0000f, -520.0000f, 220.0000f, 320.0000f, 1.0625f, 0.0000f, 0.0000f, 0.0000f } },  \
            { 1,  140, 140,                                                                                                \
              0,  0,   0,                                                                                                  \
              70, 0,   { -680.0000f, 240.0000f, -520.0000f, 220.0000f, 320.0000f, 1.3125f, 0.0000f, 0.0000f, 0.0000f } },  \
            { 2,  100, 100,                                                                                                \
              0,  0,   0,                                                                                                  \
              70, 0,   { -560.0000f, -920.0000f, -60.0000f, 420.0000f, 220.0000f, 0.0000f, 0.0000f, 0.0000f, 0.0000f } },  \
            { 2,  100, 100,                                                                                                \
              0,  0,   0,                                                                                                  \
              70, 0,   { -380.0000f, -1050.0000f, 150.0000f, 600.0000f, 160.0000f, 0.3000f, 0.0000f, 0.0000f, 0.0000f } }, \
            { 2,  100, 100,                                                                                                \
              0,  0,   0,                                                                                                  \
              70, 0,   { -200.0000f, -1130.0000f, 300.0000f, 700.0000f, 300.0000f, 0.4500f, 0.0000f, 0.0000f, 0.0000f } }, \
            { 3,                                                                                                           \
              260,                                                                                                         \
              140,                                                                                                         \
              -16384,                                                                                                      \
              90,                                                                                                          \
              0,                                                                                                           \
              70,                                                                                                          \
              0,                                                                                                           \
              { 30.0000f, 560.0000f, -1200.0000f, 30.0000f, 560.0000f, -1800.0000f, 100.0000f, 50.0000f, 0.0000f } },      \
            { 3,                                                                                                           \
              150,                                                                                                         \
              150,                                                                                                         \
              -32768,                                                                                                      \
              0,                                                                                                           \
              0,                                                                                                           \
              70,                                                                                                          \
              0,                                                                                                           \
              { 0.0000f, 560.0000f, -2120.0000f, -760.0000f, 560.0000f, -2120.0000f, 240.0000f, 40.0000f, 0.0000f } },     \
            { 3,                                                                                                           \
              150,                                                                                                         \
              150,                                                                                                         \
              0,                                                                                                           \
              0,                                                                                                           \
              0,                                                                                                           \
              70,                                                                                                          \
              0,                                                                                                           \
              { -400.0000f, 660.0000f, -2270.0000f, -400.0000f, 660.0000f, -2610.0000f, 200.0000f, 80.0000f, 0.3000f } },  \
            { 0,                                                                                                           \
              160,                                                                                                         \
              160,                                                                                                         \
              0,                                                                                                           \
              0,                                                                                                           \
              0,                                                                                                           \
              70,                                                                                                          \
              0,                                                                                                           \
              { -300.0000f, 1300.0000f, -2950.0000f, 520.0000f, 30.0000f, 200.0000f, 0.0000f, 0.0000f, 0.0000f } },        \
            { 2,  100, 100,                                                                                                \
              0,  0,   0,                                                                                                  \
              70, 0,   { -560.0000f, -3150.0000f, 700.0000f, 950.0000f, 210.0000f, 0.1000f, 0.0000f, 0.0000f, 0.0000f } }, \
            { 1,  150, 160,                                                                                                \
              0,  0,   40,                                                                                                 \
              70, 0,   { 0.0000f, 960.0000f, -3350.0000f, 330.0000f, 420.0000f, 0.6200f, 0.0000f, 0.0000f, 0.0000f } },    \
            { 1,  140, 140,                                                                                                \
              0,  0,   0,                                                                                                  \
              70, 1,   { 0.0000f, 600.0000f, -3350.0000f, 470.0000f, -300.0000f, 0.1000f, 0.0000f, 0.0000f, 0.0000f } },   \
            { 1,  140, 140,                                                                                                \
              0,  0,   0,                                                                                                  \
              70, 1,   { 0.0000f, 350.0000f, -3350.0000f, 520.0000f, 420.0000f, 0.4000f, 0.0000f, 0.0000f, 0.0000f } },    \
        {                                                                                                                  \
            1, 140, 140, 0, 0, 0, 70, 1, {                                                                                 \
                0.0000f, 700.0000f, -3350.0000f, 300.0000f, -260.0000f, 0.7500f, 0.0000f, 0.0000f, 0.0000f                 \
            }                                                                                                              \
        }                                                                                                                  \
    }

extern Gfx gAbyssPlat0DL[];
extern CollisionHeader gAbyssPlat0Col;
extern Gfx gAbyssPlat1DL[];
extern CollisionHeader gAbyssPlat1Col;
extern Gfx gAbyssPlat2DL[];
extern CollisionHeader gAbyssPlat2Col;
extern Gfx gAbyssPlat3DL[];
extern CollisionHeader gAbyssPlat3Col;
extern Gfx gAbyssPlat4DL[];
extern CollisionHeader gAbyssPlat4Col;
extern Gfx gAbyssPlat5DL[];
extern CollisionHeader gAbyssPlat5Col;
extern Gfx gAbyssPlat6DL[];
extern CollisionHeader gAbyssPlat6Col;
extern Gfx gAbyssPlat7DL[];
extern CollisionHeader gAbyssPlat7Col;
extern Gfx gAbyssPlat8DL[];
extern CollisionHeader gAbyssPlat8Col;
extern Gfx gAbyssPlat9DL[];
extern CollisionHeader gAbyssPlat9Col;
extern Gfx gAbyssPlat10DL[];
extern CollisionHeader gAbyssPlat10Col;
extern Gfx gAbyssPlat11DL[];
extern CollisionHeader gAbyssPlat11Col;
extern Gfx gAbyssPlat12DL[];
extern CollisionHeader gAbyssPlat12Col;
extern Gfx gAbyssPlat13DL[];
extern CollisionHeader gAbyssPlat13Col;
extern Gfx gAbyssPlat14DL[];
extern CollisionHeader gAbyssPlat14Col;
extern Gfx gAbyssPlat15DL[];
extern CollisionHeader gAbyssPlat15Col;
extern Gfx gAbyssPlat16DL[];
extern CollisionHeader gAbyssPlat16Col;
extern Gfx gAbyssTargetDL[];
extern Gfx gAbyssCrackedDL[];
extern Gfx gAbyssChainDL[];
extern Gfx gAbyssRingDL[];
extern CollisionHeader gAbyssRingCol;
extern Gfx gAbyssCubeDL[];
extern CollisionHeader gAbyssCubeCol;
extern Gfx gAbyssRampDL[];
extern CollisionHeader gAbyssRampCol;
extern Gfx gAbyssBarsDL[];
extern CollisionHeader gAbyssBarsCol;
extern Gfx gAbyssDoorDL[];
extern CollisionHeader gAbyssDoorCol;

// (for tables in the actor's own data: the object is only reached through segment 6 by the RSP and the bgcheck)
#define ABYSS_PLAT_DLS                                                                                           \
    {                                                                                                            \
        gAbyssPlat0DL, gAbyssPlat1DL, gAbyssPlat2DL, gAbyssPlat3DL, gAbyssPlat4DL, gAbyssPlat5DL, gAbyssPlat6DL, \
            gAbyssPlat7DL, gAbyssPlat8DL, gAbyssPlat9DL, gAbyssPlat10DL, gAbyssPlat11DL, gAbyssPlat12DL,         \
            gAbyssPlat13DL, gAbyssPlat14DL, gAbyssPlat15DL, gAbyssPlat16DL                                       \
    }
#define ABYSS_PLAT_COLS                                                                                             \
    {                                                                                                               \
        &gAbyssPlat0Col, &gAbyssPlat1Col, &gAbyssPlat2Col, &gAbyssPlat3Col, &gAbyssPlat4Col, &gAbyssPlat5Col,       \
            &gAbyssPlat6Col, &gAbyssPlat7Col, &gAbyssPlat8Col, &gAbyssPlat9Col, &gAbyssPlat10Col, &gAbyssPlat11Col, \
            &gAbyssPlat12Col, &gAbyssPlat13Col, &gAbyssPlat14Col, &gAbyssPlat15Col, &gAbyssPlat16Col                \
    }

#endif
