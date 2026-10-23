#ifndef OBJECT_REMIX_YEARS_H
#define OBJECT_REMIX_YEARS_H

#include "ultra64.h"
#include "bgcheck.h"

// The Shrine of Seven Years' pieces (tools/remix/make_years_parts.py), drawn and moved by En_Remix_Years, and the
// shrine's plan (tools/remix/years_plan.py) in world coordinates.

#define YEARS_PEDESTAL_X 0.0f
#define YEARS_PEDESTAL_Z 360.0f
#define YEARS_DAIS_H 24.0f
#define YEARS_CUBE_N 6
#define YEARS_CUBE_CELLS                                                                  \
    {                                                                                     \
        { -950, -400 }, { -800, -400 }, { -700, -400 }, { -700, -560 }, { -700, -700 }, { \
            -700, -805                                                                    \
        }                                                                                 \
    }
#define YEARS_PLANTER_N 3
#define YEARS_PLANTER_CELLS                 \
    {                                       \
        { -720, -1100 }, { -575, -1100 }, { \
            -575, -1390                     \
        }                                   \
    }
#define YEARS_PLANTER_START 1
#define YEARS_SUPPORT_N 3
#define YEARS_SUPPORT_CELLS               \
    {                                     \
        { 280, -1480 }, { 280, -1540 }, { \
            280, -1600                    \
        }                                 \
    }
#define YEARS_UPPER_Y 330.0f
#define YEARS_CAVITY_X 900.0f
#define YEARS_CAVITY_Z -300.0f
#define YEARS_DOOR_H 310.0f
#define YEARS_FLAG_DOOR 5
#define YEARS_FLAG_MEDALLION 6
#define YEARS_FLAG_ROOTS 7
#define YEARS_FLAG_CUBE 0x10
#define YEARS_FLAG_PLANTER 0x13
#define YEARS_FLAG_SUPPORT 0x15
#define YEARS_T_SECRET 2

extern Gfx gYearsPedestalDL[];
extern CollisionHeader gYearsPedestalCol;
extern Gfx gYearsSwordDL[];
extern Gfx gYearsCubeDL[];
extern CollisionHeader gYearsCubeCol;
extern Gfx gYearsPlanterDL[];
extern CollisionHeader gYearsPlanterCol;
extern Gfx gYearsTreeDL[];
extern CollisionHeader gYearsTreeCol;
extern Gfx gYearsSupportDL[];
extern CollisionHeader gYearsSupportCol;
extern Gfx gYearsStairsFullDL[];
extern CollisionHeader gYearsStairsFullCol;
extern Gfx gYearsStairsBrokenDL[];
extern CollisionHeader gYearsStairsBrokenCol;
extern Gfx gYearsEastStairsDL[];
extern CollisionHeader gYearsEastStairsCol;
extern Gfx gYearsEastStairsRuinDL[];
extern Gfx gYearsGardenWallDL[];
extern CollisionHeader gYearsGardenWallCol;
extern Gfx gYearsRubbleDL[];
extern CollisionHeader gYearsRubbleCol;
extern Gfx gYearsCrackWallDL[];
extern CollisionHeader gYearsCrackWallCol;
extern Gfx gYearsRootsDL[];
extern CollisionHeader gYearsRootsCol;
extern Gfx gYearsMedallionDL[];
extern Gfx gYearsLooseStoneDL[];
extern Gfx gYearsCavityDL[];
extern Gfx gYearsDoorDL[];
extern CollisionHeader gYearsDoorCol;
extern Gfx gYearsTabletDL[];
extern CollisionHeader gYearsTabletCol;
extern Gfx gYearsNarrowDL[];
extern CollisionHeader gYearsNarrowCol;

#endif
