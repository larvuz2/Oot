#ifndef Z_EN_REMIX_ABYSS_H
#define Z_EN_REMIX_ABYSS_H

#include "ultra64.h"
#include "actor.h"

// The Shrine of the Swinging Abyss (Web Remix level 9, see z_en_remix_abyss.c).
typedef enum EnRemixAbyssType {
    /* 0 */ ABYSS_CTRL,     // the gauntlet's clock, falls into the abyss (back to the start), the Hookshot's button
    /* 1 */ ABYSS_PLATFORM, // a moving platform (arg: which, object_remix_abyss.h ABYSS_PLATS)
    /* 2 */ ABYSS_RING,     // the stone ring turning round the exit balcony
    /* 3 */ ABYSS_CUBE,     // the stone room's cube (pushed onto the ramp, slides into the trench)
    /* 4 */ ABYSS_RAMP,     // the ramp the crystal raises
    /* 5 */ ABYSS_BARS,     // the bars before the Hookshot's chest (open while the floor switch is held)
    /* 6 */ ABYSS_DOOR,     // the door to the abyss (opens once the Hookshot is in hand)
    /* 7 */ ABYSS_EYE       // watches the crystal: a thrown stone that reaches it lights it
} EnRemixAbyssType;

#define ABYSS_TYPE(params) ((params)&0xF)
#define ABYSS_ARG(params) (((params) >> 8) & 0xFF)

typedef struct EnRemixAbyss {
    DynaPolyActor dyna;
    s16 type;
    s16 arg;
    s16 mode;
    s16 timer;
    s16 cell;
    s16 target;
    s16 reset;
    u8 hasDyna;
    u8 inReach;
    f32 offset;
    f32 vel;
    f32 tilt;
} EnRemixAbyss;

#endif
