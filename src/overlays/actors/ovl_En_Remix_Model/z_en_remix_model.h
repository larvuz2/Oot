#ifndef Z_EN_REMIX_MODEL_H
#define Z_EN_REMIX_MODEL_H

#include "ultra64.h"
#include "actor.h"

typedef struct EnRemixModel {
    /* 0x0000 */ Actor actor;
    /* 0x014C */ s16 timer;
} EnRemixModel;

#endif
