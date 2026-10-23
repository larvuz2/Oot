#ifndef Z_EN_REMIX_YEARS_H
#define Z_EN_REMIX_YEARS_H

#include "ultra64.h"
#include "actor.h"

// The Shrine of Seven Years (Web Remix level 7, see z_en_remix_years.c).
typedef enum EnRemixYearsType {
    /* 0 */ YEARS_PEDESTAL, // the Master Sword's pedestal: place the sword (child) or draw it (adult)
    /* 1 */ YEARS_PUSH,     // a block pushed from place to place (arg 0 the cube, 1 the planter / tree, 2 the support)
    /* 2 */ YEARS_ERA,      // what seven years change (arg 0 garden wall / rubble, 1 east stairs / ruin,
                            // 2 cracked wall / roots, 3 the final staircase)
    /* 3 */ YEARS_NARROW,   // an opening too small for the adult (an invisible block, adult only)
    /* 4 */ YEARS_CARRY,    // carried by the child (arg 0 the golden medallion, 1 the loose stone)
    /* 5 */ YEARS_SECRET,   // the future's chest, where the medallion was buried
    /* 6 */ YEARS_TABLET,   // an inscription (arg: which)
    /* 7 */ YEARS_DOOR      // the massive exit door (rises once TIME's door flag is set)
} EnRemixYearsType;

#define YEARS_TYPE(params) ((params)&0xF)
#define YEARS_ARG(params) (((params) >> 8) & 0xFF)

typedef struct EnRemixYears {
    DynaPolyActor dyna;
    s16 type;
    s16 arg;
    s16 mode;
    s16 timer;
    s16 cell;
    s16 target;
    u8 hasDyna;
    u8 isChild;
    u8 talking;
    f32 offset;
    f32 scale;
} EnRemixYears;

#endif
