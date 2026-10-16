#ifndef Z_EN_REMIX_MODEL_H
#define Z_EN_REMIX_MODEL_H

#include "ultra64.h"
#include "actor.h"

typedef struct EnRemixModel {
    /* 0x0000 */ Actor actor;
    /* 0x014C */ s16 timer;
    /* 0x014E */ s16 frame;
    /* 0x0150 */ f32 animTime;
    /* 0x0154 */ s32 isCharacter; // the model has a walk cycle: follow Link instead of floating
} EnRemixModel;

#endif
