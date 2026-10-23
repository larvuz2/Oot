#ifndef Z_EN_REMIX_TIME_H
#define Z_EN_REMIX_TIME_H

#include "ultra64.h"
#include "actor.h"
#include "collision_check.h"

// The Temple of Two Truths (Web Remix level 6, see z_en_remix_time.c).
typedef enum EnRemixTimeType {
    /*  0 */ TIME_CONTROLLER, // one: the Song of Time on the clock-plate, the water, the sunlight, the decor
    /*  1 */ TIME_SPHERE,     // the golden sphere (adult) / golden seed (child)
    /*  2 */ TIME_PEDESTAL,   // the sphere's pedestal: sinks when the adult lands on the dais, unless locked
    /*  3 */ TIME_RING,       // ring 1: turns once the sphere is in its cradle, backwards after the blast crystal
    /*  4 */ TIME_ECHO,       // an echo block (arg 0 the mirror block, 1 the scale's block)
    /*  5 */ TIME_PAN,        // a pan of the scale (arg 0 left, 1 right)
    /*  6 */ TIME_WEIGHT,     // the stone weight over the left pan
    /*  7 */ TIME_BRIDGE,     // the child era's bridge to the dais
    /*  8 */ TIME_RAMP,       // the child era's ramp up the statue
    /*  9 */ TIME_TABLET,     // an inscription (arg: which)
    /* 10 */ TIME_BLAST,      // the crystal only a blast wakes (sets TIME_FLAG_REVERSE)
    /* 11 */ TIME_DOOR        // arg: switch flag; home.rot.z 0 the statue's jaw (sinks), 1 the way-out door (rises)
} EnRemixTimeType;

#define TIME_TYPE(params) ((params)&0xF)
#define TIME_ARG(params) (((params) >> 8) & 0xFF)
#define TIME_PARAMS(type, arg) ((((arg)&0xFF) << 8) | ((type)&0xF))

// Where the sphere is (switch flags TIME_FLAG_STAGE..+3)
typedef enum EnRemixTimeStage {
    /* 0 */ TIME_STAGE_PEDESTAL,
    /* 1 */ TIME_STAGE_RING,
    /* 2 */ TIME_STAGE_HEAD,
    /* 3 */ TIME_STAGE_PAN,
    /* 4 */ TIME_STAGE_EYE2,
    /* 5 */ TIME_STAGE_SEED_EYE1
} EnRemixTimeStage;

typedef struct EnRemixTime {
    DynaPolyActor dyna;
    s16 type;
    s16 arg;
    s16 mode;
    s16 timer;
    s16 cell;      // echo blocks
    s16 target;    // echo blocks: the cell it slides to
    s16 yaw;       // ring: its turn; controller: the clock hand
    s16 pushTimer; // sphere
    u8 hasDyna;
    u8 isChild;
    u8 lit;
    u8 talking;
    f32 offset; // pedestal, door, pans: how far it moved; controller: the water's height
    f32 scale;  // sphere
    f32 t;      // sphere: along its path
    Vec3f from;
    Vec3f to;
    Vec3f mid;
    s16 trackIndex;
    s16 prevSong;
    s16 songMode;
    s16 songTimer;
    s16 sunTimer;
    s16 beam;    // controller: Link turns the sunlight with the Mirror Shield (1), onto a target (2)
    s16 beamYaw; // ...that way
    Vec3f beamFrom;
    Vec3f beamTo;
    ColliderCylinder collider; // sphere (hits push it), blast crystal (blasts)
} EnRemixTime;

#endif
