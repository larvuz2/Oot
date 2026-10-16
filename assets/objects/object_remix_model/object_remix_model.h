#ifndef OBJECT_REMIX_MODEL_H
#define OBJECT_REMIX_MODEL_H

#include "ultra64.h"

// The custom 3D model used by ovl_En_Remix_Model and the "play as" costume.
// Either the hand-made crystal or a Character Studio model converted by
// tools/remix/glb_to_oot.py: one display list per animation frame, idle frames first.

typedef enum RemixModelInfo {
    REMIX_MODEL_INFO_IDLE_FRAMES, // frames of the idle animation (at least 1)
    REMIX_MODEL_INFO_WALK_FRAMES, // frames of the walk cycle that follow the idle frames (0 = a static prop)
    REMIX_MODEL_INFO_HEIGHT,      // model height in model units (drawn at scale 0.01)
    REMIX_MODEL_INFO_RESERVED,
    REMIX_MODEL_INFO_MAX
} RemixModelInfo;

extern Gfx* gRemixModelFrameDLs[];
extern s16 gRemixModelInfo[REMIX_MODEL_INFO_MAX];

#endif
