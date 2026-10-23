#ifndef OBJECT_REMIX_MAGNET_H
#define OBJECT_REMIX_MAGNET_H

#include "ultra64.h"
#include "bgcheck.h"

// The Lodestone Shrine's moving pieces (tools/remix/make_magnet_parts.py), drawn and moved by En_Remix_Magnet.

#define MAGNET_CRATE_SIZE 70
#define MAGNET_GIRDER_LENGTH 340
#define MAGNET_GIRDER_HEIGHT 24
#define MAGNET_GIRDER_WIDTH 60
#define MAGNET_SLAB_WIDTH 250
#define MAGNET_SLAB_HEIGHT 220
#define MAGNET_SLAB_THICKNESS 30
#define MAGNET_LIFT_SIZE 160
#define MAGNET_BRAZIER_HEIGHT 55
#define MAGNET_BRAZIER_RIM 40
#define MAGNET_GATE_HEIGHT 240
#define MAGNET_BEAM_LENGTH 1000

extern Gfx gMagnetCrateDL[];
extern CollisionHeader gMagnetCrateCol;
extern Gfx gMagnetGirderDL[];
extern CollisionHeader gMagnetGirderCol;
extern Gfx gMagnetSlabDL[];
extern CollisionHeader gMagnetSlabCol;
extern Gfx gMagnetLiftDL[];
extern CollisionHeader gMagnetLiftCol;
extern Gfx gMagnetBridgeDL[];
extern CollisionHeader gMagnetBridgeCol;
extern Gfx gMagnetBrazierDL[];
extern CollisionHeader gMagnetBrazierCol;
extern Gfx gMagnetGateDL[];
extern CollisionHeader gMagnetGateCol;
extern Gfx gMagnetSpanDL[];
extern CollisionHeader gMagnetSpanCol;
extern Gfx gMagnetBeamDL[];

#endif
