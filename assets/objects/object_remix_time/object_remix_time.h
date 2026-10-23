#ifndef OBJECT_REMIX_TIME_H
#define OBJECT_REMIX_TIME_H

#include "ultra64.h"
#include "bgcheck.h"

// The Temple of Two Truths' pieces (tools/remix/make_time_parts.py), drawn and moved by En_Remix_Time, and the
// shrine's plan (tools/remix/time_plan.py) in world coordinates.

#define TIME_DAIS_R 200.0f
#define TIME_PLATE_R 70.0f
#define TIME_PIT_R 560.0f
#define TIME_PEDESTAL_X 0.0f
#define TIME_PEDESTAL_Z -130.0f
#define TIME_PEDESTAL_TOP 60.0f
#define TIME_SPHERE_R 28.0f
#define TIME_CRADLE_PHI 0xA38E
#define TIME_CRADLE_R 390.0f
#define TIME_CRADLE_Y -40.0f
#define TIME_LAUNCH_PHI 0x7555
#define TIME_RING_SPEED 100
#define TIME_WATER_HIGH -20.0f
#define TIME_WATER_LOW -1000.0f
#define TIME_MIRROR_CELL0_X 760.0f
#define TIME_MIRROR_CELL0_Z 110.0f
#define TIME_MIRROR_CELL1_X 760.0f
#define TIME_MIRROR_CELL1_Z 0.0f
#define TIME_MIRROR_CELL2_X 760.0f
#define TIME_MIRROR_CELL2_Z -110.0f
#define TIME_BAL_CELL0_X 520.0f
#define TIME_BAL_CELL0_Z -560.0f
#define TIME_BAL_CELL1_X 520.0f
#define TIME_BAL_CELL1_Z -700.0f
#define TIME_BASIN_FLOOR -120.0f
#define TIME_SPOT_X 650.0f
#define TIME_SPOT_Z -360.0f
#define TIME_SPOT_R 45.0f
#define TIME_CEILING 1100.0f
#define TIME_SUN_SYMBOL_X -995.0f
#define TIME_SUN_SYMBOL_Y 560.0f
#define TIME_SUN_SYMBOL_Z 0.0f
#define TIME_FACE_Z -900.0f
#define TIME_EYE1_X -220.0f
#define TIME_EYE1_Y 300.0f
#define TIME_EYE2_X 0.0f
#define TIME_EYE2_Y 650.0f
#define TIME_UPPER 260.0f
#define TIME_SOCKET_PLATE_X -220.0f
#define TIME_SOCKET_PLATE_Z -950.0f
#define TIME_HEAD_X -220.0f
#define TIME_HEAD_Y 475.0f
#define TIME_HEAD_Z -955.0f
#define TIME_GRATE_Y 420.0f
#define TIME_PAN_R_X 220.0f
#define TIME_PAN_R_Z -835.0f
#define TIME_PAN_R_TOP 300.0f
#define TIME_PAN_L_X 520.0f
#define TIME_PAN_L_Z -700.0f
#define TIME_WEIGHT_X 520.0f
#define TIME_WEIGHT_Y 450.0f
#define TIME_WEIGHT_Z -700.0f
#define TIME_WEIGHT_SIZE 100.0f
#define TIME_TILT_WEIGHT 270.0f
#define TIME_TILT_PILLAR 80.0f
#define TIME_HOURGLASS_X 0.0f
#define TIME_HOURGLASS_Y 640.0f
#define TIME_HOURGLASS_Z 0.0f
#define TIME_CLOCK_X 990.0f
#define TIME_CLOCK_Y 640.0f
#define TIME_CLOCK_Z 0.0f
#define TIME_EXIT_X -1000.0f
#define TIME_FLAG_LOCK 1
#define TIME_FLAG_PLATE 2
#define TIME_FLAG_TORCHES 3
#define TIME_FLAG_MOUTH 4
#define TIME_FLAG_HAMMER 5
#define TIME_FLAG_EYE1 6
#define TIME_FLAG_REVERSE 7
#define TIME_FLAG_WEIGHT 8
#define TIME_FLAG_ALIVE 9
#define TIME_FLAG_STAGE 0x10
#define TIME_FLAG_MIRROR_CELL 0x14
#define TIME_FLAG_BAL_CELL 0x16
#define TIME_TRACK_N 15
#define TIME_TRACK_POINTS                                                                                     \
    {                                                                                                         \
        { 0, 88, -130 }, { -10, 87, -161 }, { -23, 85, -183 }, { -38, 82, -202 }, { -56, 78, -218 },          \
            { -75, 73, -232 }, { -96, 66, -244 }, { -118, 59, -253 }, { -142, 50, -260 }, { -166, 41, -265 }, \
            { -192, 31, -267 }, { -218, 21, -267 }, { -245, 10, -264 }, { -272, -1, -258 }, {                 \
            -299, -12, -251                                                                                   \
        }                                                                                                     \
    }

extern Gfx gTimeSphereDL[];
extern Gfx gTimeSeedDL[];
extern Gfx gTimeBubbleDL[];
extern Gfx gTimePedestalDL[];
extern CollisionHeader gTimePedestalCol;
extern Gfx gTimeRingDL[];
extern CollisionHeader gTimeRingCol;
extern Gfx gTimeBlockDL[];
extern CollisionHeader gTimeBlockCol;
extern Gfx gTimeBlockDecayedDL[];
extern CollisionHeader gTimeBlockDecayedCol;
extern Gfx gTimePillarDL[];
extern CollisionHeader gTimePillarCol;
extern Gfx gTimeMirrorDL[];
extern Gfx gTimePanLDL[];
extern CollisionHeader gTimePanLCol;
extern Gfx gTimePanRDL[];
extern CollisionHeader gTimePanRCol;
extern Gfx gTimeChainDL[];
extern Gfx gTimeWeightDL[];
extern CollisionHeader gTimeWeightCol;
extern Gfx gTimeBridgeDL[];
extern CollisionHeader gTimeBridgeCol;
extern Gfx gTimeBridgeRuinDL[];
extern Gfx gTimeRampDL[];
extern CollisionHeader gTimeRampCol;
extern Gfx gTimeRampRuinDL[];
extern Gfx gTimeJawDL[];
extern CollisionHeader gTimeJawCol;
extern Gfx gTimeDoorDL[];
extern CollisionHeader gTimeDoorCol;
extern Gfx gTimeTabletDL[];
extern CollisionHeader gTimeTabletCol;
extern Gfx gTimeCrystalDL[];
extern Gfx gTimeGrateDL[];
extern Gfx gTimeHourglassDL[];
extern Gfx gTimeHourglassGlassDL[];
extern Gfx gTimeDecoRingADL[];
extern Gfx gTimeDecoRingBDL[];
extern Gfx gTimeDecoRingCDL[];
extern Gfx gTimeHandDL[];
extern Gfx gTimeLidDL[];
extern Gfx gTimeWaterDL[];
extern Gfx gTimeBeamDL[];
extern Gfx gTimeDiscDL[];

#endif
