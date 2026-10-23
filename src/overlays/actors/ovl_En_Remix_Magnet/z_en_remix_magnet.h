#ifndef Z_EN_REMIX_MAGNET_H
#define Z_EN_REMIX_MAGNET_H

#include "ultra64.h"
#include "actor.h"
#include "collision_check.h"
#include "light.h"

// The Lodestone Shrine's moving pieces and the Magnesis rune (Web Remix level 4, see z_en_remix_magnet.c).
typedef enum EnRemixMagnetType {
    /* 0 */ MAGNET_CONTROLLER, // Magnesis itself (one per scene): flag = the chest's treasure flag that gives it,
                               // home.rot.z = treasure flag of a chest it can lift too (0 = none)
    /* 1 */ MAGNET_CRATE,      // iron block: magnetic, presses floor switches
    /* 2 */ MAGNET_GIRDER,     // iron beam: magnetic, rests on its two ends
    /* 3 */ MAGNET_SLAB,       // iron door slab: magnetic
    /* 4 */ MAGNET_LIFT,       // platform: rises home.rot.z units and back, over and over, while switch `flag` is set
    /* 5 */ MAGNET_BRIDGE,     // L-shaped bridge: turns a quarter each time switch `flag` or home.rot.z changes
    /* 6 */ MAGNET_BRAZIER,    // iron fire basket: magnetic; catches fire from a burning torch, lights the torches it
                               // touches (Din's Fire to them), goes out in water
    /* 7 */ MAGNET_GATE,       // shutter: rises home.rot.z units (and stays) once switch `flag` is set
    /* 8 */ MAGNET_SPAN        // bridge span: rises home.rot.z units out of a chasm (and stays) once `flag` is set
} EnRemixMagnetType;

// MAGNET_CONTROLLER with this flag: Magnesis works from the start (the Forge Shrine lends it)
#define MAGNET_ALWAYS 0x3F

#define MAGNET_TYPE(params) ((params)&0xF)
#define MAGNET_FLAG(params) (((params) >> 8) & 0x3F)
#define MAGNET_PARAMS(type, flag) ((((flag)&0x3F) << 8) | ((type)&0xF))

#define MAGNET_SAMPLES 5

typedef struct EnRemixMagnet {
    DynaPolyActor dyna;
    s16 type;
    s16 timer;
    s16 targetYaw; // bridge: where it is turning to
    s16 extra;     // lift: rise; bridge: the second switch flag; controller: liftable chest's flag
    u8 switchState[2];
    u8 held;        // magnetic pieces: held by Magnesis (moved by the controller)
    u8 resting;     // magnetic pieces: standing on something
    u8 aimed;       // magnetic pieces: Magnesis would grab this one
    u8 hasMagnesis; // controller
    s16 liftWait;
    f32 lift;              // lift: current height above home
    Vec3f vel;             // magnetic pieces (and a dropped chest, for the controller)
    Actor* target;         // controller: what Magnesis holds
    Actor* aim;            // controller: what Magnesis would grab
    Actor* falling;        // controller: a chest it dropped, falling
    f32 holdDist;          // controller: how far from Link (horizontally)
    f32 holdHeight;        // controller: how high above Link's feet
    s16 holdYaw;           // controller: direction from Link
    Vec3f lastSafe;        // magnetic pieces: the last place it stood (or hung) over solid floor: it comes back there
    f32 floorY;            // magnetic pieces: the floor under it this frame
    u8 floorSafe;          // magnetic pieces: ...and whether that floor is solid ground (not a chasm's void floor)
    u8 lit;                // brazier: burning
    ColliderCylinder fire; // brazier: its flame (Din's Fire to torches)
    LightNode* lightNode;  // brazier: its glow
    LightInfo lightInfo;
} EnRemixMagnet;

#endif
