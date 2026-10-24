#ifndef Z_EN_REMIX_WIND_H
#define Z_EN_REMIX_WIND_H

#include "ultra64.h"
#include "actor.h"
#include "src/overlays/actors/ovl_En_Remix_Magnet/z_en_remix_magnet.h"

// The Shrine of the Upside-Down Wind (Web Remix level 8, see z_en_remix_wind.c).
typedef enum EnRemixWindType {
    /* 0 */ WIND_CTRL,    // the machine: the gravity timer, the two ceiling switches, the final ladder, the glass
    /* 1 */ WIND_CUBE,    // an iron cube (arg 0 light, 1 medium, 2 heavy): Magnesis moves it, the wind lifts it
    /* 2 */ WIND_FAN,     // a fan (arg 0 the floor's, blowing up; 1 the ceiling's, blowing down)
    /* 3 */ WIND_PLATE,   // the first ceiling switch (heavy)
    /* 4 */ WIND_BRACKET, // the bracket beside it (the medium cube locks into it)
    /* 5 */ WIND_TIMER,   // the timed switch: eight seconds of upside-down gravity for every loose object
    /* 6 */ WIND_LADDER,  // arg 0 the ladder to the middle balcony, 1 the final ladder (lowered from the exit)
    /* 7 */ WIND_GATE     // arg 0 the gate before the first ladder, 1 the glass wall of the hidden treasure
} EnRemixWindType;

#define WIND_TYPE(params) ((params)&0xF)
#define WIND_ARG(params) (((params) >> 8) & 0xFF)

typedef struct EnRemixWind {
    EnRemixMagnet base; // (first: Magnesis holds the cubes like the Lodestone Shrine's crates; base.lift = size)
    s16 type;
    s16 arg;
    s16 timer;
    s16 spin;
    u8 hasDyna;
    u8 locked; // cubes: in the bracket / wedged against the plate
    u8 pressed;
    f32 size;
    f32 offset;
} EnRemixWind;

#endif
