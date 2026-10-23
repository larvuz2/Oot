/*
 * File: z_en_remix_time.c
 * Overlay: ovl_En_Remix_Time
 * Description: Web Remix level 6, the Temple of Two Truths: one great round hall seen in two eras. The Song of Time
 *              on the clock-plate in the middle of the dais takes Link between them (child and adult); what he moves
 *              in the past stays moved in the present, and some things grow there while others decay. The shrine's
 *              pieces (object_remix_time, tools/remix/make_time_parts.py, which also writes the plan this file
 *              reads: TIME_* in object_remix_time.h) and the room (tools/remix/make_time.py).
 *
 *   TIME_CONTROLLER  The Song of Time on the clock-plate switches the era: play->linkAgeOnLoad, as the Temple of
 *                    Time does, and the room comes back with Link on his era's pad (spawn 1 / 2). The water rises in
 *                    the pit and the east basin (the scene's water box) once the four torches have burned together,
 *                    in the adult era, while the mirror block (moved or not in the past) plugs the drain. The sun
 *                    falls through the ceiling into the basin: on the mirror of the grown block (adult era, block in
 *                    the sunbeam) it is thrown onto the walkway, where Link turns it with the Mirror Shield onto the
 *                    sun symbol (the statue's mouth opens) or onto the seed planted in the first eye. Draws the
 *                    hourglass and its three rings, the clock's hand, the water, the light, the eyes.
 *   TIME_SPHERE      The golden sphere's journey, kept in switch flags (TIME_FLAG_STAGE): the pedestal; rolled down
 *                    the curved track into ring 1's cradle (its plate starts the ring); floated up in a bubble into
 *                    the statue's head when the water reaches it; dropped onto the first eye's plate by the hammer
 *                    switch (eye 1, the way out, the second eye appears; the sphere returns to its pedestal); or
 *                    thrown by the ring turning backwards onto the scale's right pan, lifted to the second eye (the
 *                    statue awakes, the chest falls). In the child era it is a golden seed Link can carry: planted in
 *                    the first eye, it waits there in the present until sunlight finds it, grows and opens the eye.
 *   TIME_PEDESTAL    Sinks into the dais when the adult stands on it, and the sphere falls into the pit (it comes
 *                    back), unless the crystal under it is struck (TIME_FLAG_LOCK).
 *   TIME_RING        Turns while the sphere has started it (TIME_FLAG_PLATE), in the adult era; backwards once the
 *                    blast crystal is hit (TIME_FLAG_REVERSE). Stands still in the past (its south opening lets the
 *                    child's bridge through).
 *   TIME_ECHO        In the past a small block the child pushes from place to place; in the present the same block
 *                    where he left it: a worn block sunk in the drain (too heavy), or a pillar grown out of it (the
 *                    mirror block's carries the mirror; the scale's, standing on the left pan, weighs it down).
 *   TIME_PAN, TIME_WEIGHT
 *                    The scale: the weight (dropped by the floor switch on the high platform) and the pillar on the
 *                    left pan lift the right pan; with both, up to the second eye.
 *   TIME_BRIDGE, TIME_RAMP
 *                    The child era's bridge and ramp; ruins in the adult era.
 *   TIME_TABLET      Inscriptions (talk to them).
 *   TIME_BLAST       A crystal under the dais's south edge that only a blast wakes (a Bombchu run down the side).
 *   TIME_DOOR        The statue's jaw (sinks), the way-out door (rises), each once its flag is set.
 */

#include "z_en_remix_time.h"

#include "gfx.h"
#include "gfx_setupdl.h"
#include "array_count.h"
#include "libc/math.h"
#include "libc64/math64.h"
#include "attributes.h"
#include "ichain.h"
#include "sfx.h"
#include "sys_matrix.h"
#include "z_lib.h"
#include "z_math.h"
#include "audio.h"
#include "message.h"
#include "ocarina.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "scene.h"
#include "sequence.h"
#include "transition.h"
#include "remix_level.h"

#include "assets/objects/object_remix_time/object_remix_time.h"

#define FLAGS (ACTOR_FLAG_UPDATE_CULLING_DISABLED | ACTOR_FLAG_DRAW_CULLING_DISABLED | ACTOR_FLAG_UPDATE_DURING_OCARINA)

#define TEXT_TABLET_BASE 0x7FA1    // assets/text/message_data.h: the inscriptions
#define TEXT_TRUTH 0x7FA3          // "You have opened the way. But have you understood the truth?"
#define TIME_CHILD_PEDESTAL -40.0f // the pedestal in the past (it grew)

void EnRemixTime_Init(Actor* thisx, PlayState* play);
void EnRemixTime_Destroy(Actor* thisx, PlayState* play);
void EnRemixTime_Update(Actor* thisx, PlayState* play);
void EnRemixTime_Draw(Actor* thisx, PlayState* play);

ActorProfile En_Remix_Time_Profile = {
    /**/ ACTOR_EN_REMIX_TIME,
    /**/ ACTORCAT_BG,
    /**/ FLAGS,
    /**/ OBJECT_REMIX_TIME,
    /**/ sizeof(EnRemixTime),
    /**/ EnRemixTime_Init,
    /**/ EnRemixTime_Destroy,
    /**/ EnRemixTime_Update,
    /**/ EnRemixTime_Draw,
};

// The pieces that need each other (set by their Init, cleared by their Destroy)
typedef struct TimeShared {
    EnRemixTime* controller;
    EnRemixTime* sphere;
    EnRemixTime* pedestal;
    EnRemixTime* ring;
    EnRemixTime* echo[2];
    EnRemixTime* pan[2];
    u8 sunOnSeed;
} TimeShared;

static TimeShared sTime;

static Vec3s sTrack[TIME_TRACK_N] = TIME_TRACK_POINTS;

// The sphere: struck by anything (a sword, the hookshot, an arrow, the boomerang) it rolls off its pedestal
static ColliderCylinderInit sSphereInit = {
    {
        COL_MATERIAL_NONE,
        AT_NONE,
        AC_ON | AC_TYPE_PLAYER,
        OC1_NONE,
        OC2_NONE,
        COLSHAPE_CYLINDER,
    },
    {
        ELEM_MATERIAL_UNK0,
        { 0x00000000, HIT_SPECIAL_EFFECT_NONE, 0x00 },
        { 0xFFCFFFFF, HIT_BACKLASH_NONE, 0x00 },
        ATELEM_NONE,
        ACELEM_ON,
        OCELEM_NONE,
    },
    { 30, 60, -30, { 0, 0, 0 } },
};

// The blast crystal: a Bombchu runs into it (OC) and blows up; only the blast (DMG_EXPLOSIVE) wakes it
static ColliderCylinderInit sBlastInit = {
    {
        COL_MATERIAL_NONE,
        AT_NONE,
        AC_ON | AC_TYPE_PLAYER,
        OC1_ON | OC1_TYPE_ALL,
        OC2_TYPE_2,
        COLSHAPE_CYLINDER,
    },
    {
        ELEM_MATERIAL_UNK0,
        { 0x00000000, HIT_SPECIAL_EFFECT_NONE, 0x00 },
        { DMG_EXPLOSIVE, HIT_BACKLASH_NONE, 0x00 },
        ATELEM_NONE,
        ACELEM_ON,
        OCELEM_ON,
    },
    { 26, 50, -25, { 0, 0, 0 } },
};

// ---------------------------------------------------------------- helpers

static s32 Time_GetBits(PlayState* play, s32 first, s32 n) {
    s32 v = 0;
    s32 i;

    for (i = 0; i < n; i++) {
        if (Flags_GetSwitch(play, first + i)) {
            v |= 1 << i;
        }
    }
    return v;
}

static void Time_SetBits(PlayState* play, s32 first, s32 n, s32 v) {
    s32 i;

    for (i = 0; i < n; i++) {
        if ((v >> i) & 1) {
            Flags_SetSwitch(play, first + i);
        } else {
            Flags_UnsetSwitch(play, first + i);
        }
    }
}

static s32 Time_Stage(PlayState* play) {
    return Time_GetBits(play, TIME_FLAG_STAGE, 4);
}

static void Time_SetStage(PlayState* play, s32 stage) {
    Time_SetBits(play, TIME_FLAG_STAGE, 4, stage);
}

static s32 Time_IsChild(void) {
    return !LINK_IS_ADULT;
}

/** Link stands on the dais (not in the air over it). */
static s32 Time_LinkOnDais(PlayState* play) {
    Player* player = GET_PLAYER(play);
    f32 r = sqrtf(SQ(player->actor.world.pos.x) + SQ(player->actor.world.pos.z));

    return (r < TIME_DAIS_R) && (player->actor.world.pos.y > -10.0f) && (player->actor.world.pos.y < 30.0f) &&
           (player->actor.bgCheckFlags & BGCHECKFLAG_GROUND);
}

/** The cradle (where the sphere rides) for the ring's current turn. */
static void Time_CradlePos(Vec3f* pos) {
    s16 phi = TIME_CRADLE_PHI + ((sTime.ring != NULL) ? sTime.ring->yaw : 0);

    pos->x = Math_SinS(phi) * TIME_CRADLE_R;
    pos->y = TIME_CRADLE_Y + TIME_SPHERE_R;
    pos->z = Math_CosS(phi) * TIME_CRADLE_R;
}

static f32 Time_Water(void) {
    return (sTime.controller != NULL) ? sTime.controller->offset : TIME_WATER_LOW;
}

static f32 Time_PanTop(s32 which) {
    if (sTime.pan[which] != NULL) {
        return sTime.pan[which]->dyna.actor.world.pos.y;
    }
    return which ? TIME_PAN_R_TOP : 0.0f;
}

/** How far the scale is tipped: the weight on the left pan, and the pillar grown there from the past's block. */
static f32 Time_Tilt(PlayState* play) {
    f32 tilt = 0.0f;

    if (Time_IsChild()) {
        return 0.0f; // the weight still hangs in the past, and the block is only a block
    }
    if (Flags_GetSwitch(play, TIME_FLAG_WEIGHT)) {
        tilt += TIME_TILT_WEIGHT;
    }
    if (Time_GetBits(play, TIME_FLAG_BAL_CELL, 1) == 1) {
        tilt += TIME_TILT_PILLAR;
    }
    return tilt;
}

static void Time_Chime(void) {
    Sfx_PlaySfxCentered(NA_SE_SY_CORRECT_CHIME);
}

// ---------------------------------------------------------------- init / destroy

void EnRemixTime_Init(Actor* thisx, PlayState* play) {
    static CollisionHeader* const sChildCol[] = { &gTimeBridgeCol, &gTimeRampCol };
    EnRemixTime* this = (EnRemixTime*)thisx;
    CollisionHeader* colHeader = NULL;
    CollisionHeader* col = NULL;
    s32 transform = DYNA_TRANSFORM_POS;
    s16 rotZ = thisx->home.rot.z;

    this->type = TIME_TYPE(thisx->params);
    this->arg = TIME_ARG(thisx->params);
    this->isChild = Time_IsChild();
    thisx->home.rot.x = thisx->home.rot.z = 0;
    thisx->world.rot = thisx->shape.rot = thisx->home.rot;
    Actor_SetScale(thisx, 1.0f);
    this->scale = 1.0f;
    this->mode = 0;

    switch (this->type) {
        case TIME_CONTROLLER:
            sTime.controller = this;
            sTime.sunOnSeed = false;
            this->prevSong = play->msgCtx.lastPlayedSong;
            // the water: already up if it should be (no rising again after a void out or the age switch)
            this->offset = TIME_WATER_LOW;
            if (!this->isChild && Flags_GetSwitch(play, TIME_FLAG_TORCHES) &&
                (Time_GetBits(play, TIME_FLAG_MIRROR_CELL, 2) != 2)) {
                this->offset = TIME_WATER_HIGH;
            }
            // the clock's hand starts on the era Link came from (it swings over)
            this->yaw = this->isChild ? -0x4000 : 0x4000;
            this->timer = 25;
            break;

        case TIME_SPHERE:
            sTime.sphere = this;
            Collider_InitCylinder(play, &this->collider);
            Collider_SetCylinder(play, &this->collider, thisx, &sSphereInit);
            thisx->gravity = -1.2f;
            thisx->minVelocityY = -20.0f;
            break;

        case TIME_PEDESTAL:
            sTime.pedestal = this;
            col = &gTimePedestalCol;
            if (this->isChild) {
                this->offset = TIME_CHILD_PEDESTAL;
                thisx->world.pos.y = thisx->home.pos.y + this->offset;
            }
            break;

        case TIME_RING:
            sTime.ring = this;
            col = &gTimeRingCol;
            transform = DYNA_TRANSFORM_POS | DYNA_TRANSFORM_ROT_Y;
            this->yaw = 0;
            break;

        case TIME_ECHO:
            this->arg &= 1;
            sTime.echo[this->arg] = this;
            this->cell = this->target = (this->arg == 0) ? Time_GetBits(play, TIME_FLAG_MIRROR_CELL, 2)
                                                         : Time_GetBits(play, TIME_FLAG_BAL_CELL, 1);
            if (this->cell > ((this->arg == 0) ? 2 : 1)) {
                this->cell = this->target = 0;
            }
            if (this->arg == 0) {
                thisx->world.pos.x = (this->cell == 0)   ? TIME_MIRROR_CELL0_X
                                     : (this->cell == 1) ? TIME_MIRROR_CELL1_X
                                                         : TIME_MIRROR_CELL2_X;
                thisx->world.pos.z = (this->cell == 0)   ? TIME_MIRROR_CELL0_Z
                                     : (this->cell == 1) ? TIME_MIRROR_CELL1_Z
                                                         : TIME_MIRROR_CELL2_Z;
                thisx->world.pos.y = TIME_BASIN_FLOOR;
            } else {
                thisx->world.pos.x = this->cell ? TIME_BAL_CELL1_X : TIME_BAL_CELL0_X;
                thisx->world.pos.z = this->cell ? TIME_BAL_CELL1_Z : TIME_BAL_CELL0_Z;
                thisx->world.pos.y = 0.0f;
            }
            if (this->isChild) {
                col = &gTimeBlockCol;
            } else if ((this->arg == 0) && (this->cell == 0)) {
                col = &gTimeBlockDecayedCol; // sunk in the drain: worn, too heavy
            } else {
                col = &gTimePillarCol; // grown
            }
            break;

        case TIME_PAN:
            this->arg &= 1;
            sTime.pan[this->arg] = this;
            col = this->arg ? &gTimePanRCol : &gTimePanLCol;
            this->offset = Time_Tilt(play);
            thisx->world.pos.y = thisx->home.pos.y + (this->arg ? this->offset : -this->offset);
            break;

        case TIME_WEIGHT:
            if (!this->isChild && Flags_GetSwitch(play, TIME_FLAG_WEIGHT)) {
                this->mode = 2; // resting on the left pan
            }
            break;

        case TIME_BRIDGE:
        case TIME_RAMP:
            if (this->isChild) {
                col = sChildCol[this->type - TIME_BRIDGE];
            }
            break;

        case TIME_TABLET:
            col = &gTimeTabletCol;
            thisx->flags |= ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_FRIENDLY;
            thisx->attentionRangeType = ATTENTION_RANGE_1;
            thisx->textId = TEXT_TABLET_BASE + this->arg;
            thisx->focus.pos = thisx->world.pos;
            thisx->focus.pos.y += 70.0f;
            break;

        case TIME_BLAST:
            Collider_InitCylinder(play, &this->collider);
            Collider_SetCylinder(play, &this->collider, thisx, &sBlastInit);
            break;

        case TIME_DOOR:
            this->mode = rotZ; // 0 jaw, 1 door
            col = (this->mode == 0) ? &gTimeJawCol : &gTimeDoorCol;
            if (Flags_GetSwitch(play, this->arg)) {
                this->offset = (this->mode == 0) ? -250.0f : 260.0f;
                thisx->world.pos.y = thisx->home.pos.y + this->offset;
            }
            break;
    }

    if (col != NULL) {
        DynaPolyActor_Init(&this->dyna, transform);
        CollisionHeader_GetVirtual(col, &colHeader);
        this->dyna.bgId = DynaPoly_SetBgActor(play, &play->colCtx.dyna, thisx, colHeader);
        this->hasDyna = true;
    }
}

void EnRemixTime_Destroy(Actor* thisx, PlayState* play) {
    EnRemixTime* this = (EnRemixTime*)thisx;
    static EnRemixTime** const slots[] = {
        &sTime.controller, &sTime.sphere,  &sTime.pedestal, &sTime.ring,
        &sTime.echo[0],    &sTime.echo[1], &sTime.pan[0],   &sTime.pan[1],
    };
    s32 i;

    if (this->hasDyna) {
        DynaPoly_DeleteBgActor(play, &play->colCtx.dyna, this->dyna.bgId);
    }
    if ((this->type == TIME_SPHERE) || (this->type == TIME_BLAST)) {
        Collider_DestroyCylinder(play, &this->collider);
    }
    for (i = 0; i < ARRAY_COUNT(slots); i++) {
        if (*slots[i] == this) {
            *slots[i] = NULL;
        }
    }
}

// ---------------------------------------------------------------- the controller

static void EnRemixTime_SwitchEra(EnRemixTime* this, PlayState* play) {
    play->linkAgeOnLoad = this->isChild ? LINK_AGE_ADULT : LINK_AGE_CHILD;
    play->nextEntranceIndex = ENTR_REMIX_TIME_1; // spawn 1 (child) / 2 (adult): Link's pad on the dais
    play->transitionTrigger = TRANS_TRIGGER_START;
    play->transitionType = TRANS_TYPE_FADE_WHITE;
    gSaveContext.nextTransitionType = TRANS_TYPE_FADE_WHITE_SLOW;
    gSaveContext.showTitleCard = false;
    Sfx_PlaySfxCentered(NA_SE_SY_WHITE_OUT_T);
}

/** The Song of Time, played on the clock-plate (as an Obj_Timeblock listens for it). */
static void EnRemixTime_ListenForSong(EnRemixTime* this, PlayState* play) {
    Player* player = GET_PLAYER(play);
    f32 r = sqrtf(SQ(player->actor.world.pos.x) + SQ(player->actor.world.pos.z));
    s32 onPlate = (r < TIME_PLATE_R + 25.0f) && (fabsf(player->actor.world.pos.y) < 40.0f);

    if (this->songTimer > 0) {
        if (--this->songTimer == 0) {
            EnRemixTime_SwitchEra(this, play);
        }
        return;
    }
    if (play->transitionTrigger != TRANS_TRIGGER_OFF) {
        return;
    }
    if (this->songMode == 0) {
        if (onPlate) {
            if (player->stateFlags2 & PLAYER_STATE2_24) {
                Message_StartOcarina(play, OCARINA_ACTION_FREE_PLAY);
                this->songMode = 1;
            } else {
                player->stateFlags2 |= PLAYER_STATE2_23;
            }
        }
    } else {
        if (play->msgCtx.ocarinaMode == OCARINA_MODE_04) {
            this->songMode = 0;
        }
        if ((play->msgCtx.lastPlayedSong == OCARINA_SONG_TIME) && (this->prevSong != OCARINA_SONG_TIME) && onPlate) {
            this->songTimer = 60; // let the song's jingle finish
            this->songMode = 0;
        }
    }
    this->prevSong = play->msgCtx.lastPlayedSong;
}

static void EnRemixTime_UpdateWater(EnRemixTime* this, PlayState* play) {
    CollisionHeader* colHeader = play->colCtx.colHeader;
    s32 high = !this->isChild && Flags_GetSwitch(play, TIME_FLAG_TORCHES) &&
               (Time_GetBits(play, TIME_FLAG_MIRROR_CELL, 2) != 2);

    if (high && (this->offset < TIME_WATER_HIGH)) {
        if (this->offset < -760.0f) {
            this->offset = -760.0f; // (from just under where it can be seen)
        }
        Math_StepToF(&this->offset, TIME_WATER_HIGH, 3.0f);
        Actor_PlaySfx_Flagged(&this->dyna.actor, NA_SE_EV_WATER_LEVEL_DOWN - SFX_FLAG);
    } else if (!high && (this->offset > TIME_WATER_LOW)) {
        this->offset -= 5.0f; // the drain is open: it runs out
        Actor_PlaySfx_Flagged(&this->dyna.actor, NA_SE_EV_WATER_LEVEL_DOWN - SFX_FLAG);
        if (this->offset < -760.0f) {
            this->offset = TIME_WATER_LOW;
        }
    }
    if ((colHeader != NULL) && (colHeader->numWaterBoxes > 0)) {
        colHeader->waterBoxes[0].ySurface = (this->offset > -760.0f) ? (s16)this->offset : (s16)TIME_WATER_LOW;
    }
}

/** The sunlight thrown by the mirror, turned by Link's Mirror Shield. */
static void EnRemixTime_UpdateSun(EnRemixTime* this, PlayState* play) {
    Player* player = GET_PLAYER(play);
    s32 mirror = !this->isChild && (Time_GetBits(play, TIME_FLAG_MIRROR_CELL, 2) == 1);
    f32 dx = player->actor.world.pos.x - TIME_SPOT_X;
    f32 dz = player->actor.world.pos.z - TIME_SPOT_Z;
    Vec3f sun = { TIME_SUN_SYMBOL_X, TIME_SUN_SYMBOL_Y, TIME_SUN_SYMBOL_Z };
    Vec3f eye = { TIME_SOCKET_PLATE_X, TIME_UPPER + 20.0f, TIME_SOCKET_PLATE_Z };
    s16 yaw = player->actor.shape.rot.y;
    s32 onSun = false;
    s32 onEye = false;

    this->beam = 0;
    sTime.sunOnSeed = false;
    if (!mirror || (SQ(dx) + SQ(dz) > SQ(TIME_SPOT_R)) || !(player->actor.bgCheckFlags & BGCHECKFLAG_GROUND) ||
        (player->currentShield != PLAYER_SHIELD_MIRROR) || !(player->stateFlags1 & PLAYER_STATE1_SHIELDING)) {
        this->sunTimer = 0;
        return;
    }
    this->beam = 1;
    this->beamYaw = yaw;
    this->beamFrom = player->actor.world.pos;
    this->beamFrom.x += Math_SinS(yaw) * 18.0f;
    this->beamFrom.y += 42.0f;
    this->beamFrom.z += Math_CosS(yaw) * 18.0f;
    if (ABS((s16)(Math_Vec3f_Yaw(&this->beamFrom, &sun) - yaw)) < 0x0A00) {
        onSun = true;
        this->beamTo = sun;
    } else if (ABS((s16)(Math_Vec3f_Yaw(&this->beamFrom, &eye) - yaw)) < 0x0A00) {
        onEye = true;
        this->beamTo = eye;
    } else {
        this->beamTo.x = this->beamFrom.x + Math_SinS(yaw) * 1400.0f;
        this->beamTo.y = this->beamFrom.y + 260.0f;
        this->beamTo.z = this->beamFrom.z + Math_CosS(yaw) * 1400.0f;
    }
    if (onSun || onEye) {
        this->beam = 2;
        this->sunTimer++;
        if (onSun && (this->sunTimer == 25) && !Flags_GetSwitch(play, TIME_FLAG_MOUTH)) {
            Flags_SetSwitch(play, TIME_FLAG_MOUTH);
            Time_Chime();
        }
        if (onEye && (Time_Stage(play) == TIME_STAGE_SEED_EYE1)) {
            sTime.sunOnSeed = true;
        }
    } else {
        this->sunTimer = 0;
    }
}

static void EnRemixTime_UpdateController(EnRemixTime* this, PlayState* play) {
    s16 hand = this->isChild ? 0x4000 : -0x4000; // the clock's hand: CHILD to the left, ADULT to the right

    EnRemixTime_ListenForSong(this, play);
    EnRemixTime_UpdateWater(this, play);
    EnRemixTime_UpdateSun(this, play);

    if (this->timer > 0) {
        this->timer--;
    } else {
        Math_ScaledStepToS(&this->yaw, hand, 0x300);
    }

    // Leaving the shrine some other way than by the song: Link goes out at the age he came in
    if ((play->transitionTrigger != TRANS_TRIGGER_OFF) && (this->songTimer == 0) &&
        ((play->nextEntranceIndex < ENTR_REMIX_TIME_0) || (play->nextEntranceIndex > ENTR_REMIX_TIME_1_3))) {
        play->linkAgeOnLoad = RemixLevel_TimeEntryAge();
    }
}

// ---------------------------------------------------------------- the sphere

typedef enum SphereMode {
    /*  0 */ SPHERE_REST,    // where its stage puts it
    /*  1 */ SPHERE_FALL,    // off the sinking pedestal, into the pit
    /*  2 */ SPHERE_GONE,    // waiting to come back to the pedestal
    /*  3 */ SPHERE_TRACK,   // rolling down the curved track
    /*  4 */ SPHERE_PATH,    // flying along a curve (from -> mid -> to) for `timer` frames, then `next`
    /*  5 */ SPHERE_GLOW,    // on the first eye's plate, lighting it
    /*  6 */ SPHERE_SEED,    // the child era's seed: lying somewhere
    /*  7 */ SPHERE_CARRIED, // ...carried by Link
    /*  8 */ SPHERE_THROWN,  // ...dropped or thrown
    /*  9 */ SPHERE_GROW,    // the planted seed growing in the sunlight
    /* 10 */ SPHERE_ROLL_OFF // off the right pan (the second eye is still shut), back to the pedestal
} SphereMode;

typedef enum SphereNext {
    /* 0 */ NEXT_RING,
    /* 1 */ NEXT_HEAD,
    /* 2 */ NEXT_PLATE,
    /* 3 */ NEXT_PAN,
    /* 4 */ NEXT_EYE2
} SphereNext;

static void EnRemixTime_SphereStagePos(EnRemixTime* this, PlayState* play, s32 stage, Vec3f* pos) {
    switch (stage) {
        case TIME_STAGE_RING:
            Time_CradlePos(pos);
            break;
        case TIME_STAGE_HEAD:
            pos->x = TIME_HEAD_X;
            pos->y = TIME_HEAD_Y;
            pos->z = TIME_HEAD_Z;
            break;
        case TIME_STAGE_PAN:
            pos->x = TIME_PAN_R_X;
            pos->y = Time_PanTop(1) + TIME_SPHERE_R;
            pos->z = TIME_PAN_R_Z;
            break;
        case TIME_STAGE_EYE2:
            pos->x = TIME_EYE2_X;
            pos->y = TIME_EYE2_Y;
            pos->z = TIME_FACE_Z - 12.0f;
            break;
        case TIME_STAGE_SEED_EYE1:
            pos->x = TIME_SOCKET_PLATE_X;
            pos->y = TIME_UPPER + 2.0f;
            pos->z = TIME_SOCKET_PLATE_Z;
            break;
        default:
            pos->x = TIME_PEDESTAL_X;
            pos->y = TIME_PEDESTAL_TOP + TIME_SPHERE_R + ((sTime.pedestal != NULL) ? sTime.pedestal->offset : 0.0f);
            pos->z = TIME_PEDESTAL_Z;
            if (this->isChild) {
                pos->y = TIME_PEDESTAL_TOP + TIME_CHILD_PEDESTAL; // (lower in the past: the child reaches the seed)
            }
            break;
    }
}

static void EnRemixTime_SphereFly(EnRemixTime* this, Vec3f* to, f32 arc, s16 frames, s16 next) {
    Actor* thisx = &this->dyna.actor;

    this->from = thisx->world.pos;
    this->to = *to;
    this->mid.x = (this->from.x + to->x) / 2.0f;
    this->mid.y = MAX(this->from.y, to->y) + arc;
    this->mid.z = (this->from.z + to->z) / 2.0f;
    this->t = 0.0f;
    this->timer = frames;
    this->trackIndex = next;
    this->mode = SPHERE_PATH;
}

/** Back on the pedestal (it fades in). */
static void EnRemixTime_SphereReturn(EnRemixTime* this, PlayState* play) {
    Time_SetStage(play, TIME_STAGE_PEDESTAL);
    this->mode = SPHERE_GONE;
    this->timer = 30;
}

/** The sphere (or the seed grown into it) on the first eye's plate: the eye opens. */
static void EnRemixTime_LightEye1(EnRemixTime* this, PlayState* play) {
    this->mode = SPHERE_GLOW;
    this->timer = 70;
    if (!Flags_GetSwitch(play, TIME_FLAG_EYE1)) {
        Flags_SetSwitch(play, TIME_FLAG_EYE1);
        Time_Chime();
        Audio_PlayFanfare(NA_BGM_APPEAR);
        Message_StartTextbox(play, TEXT_TRUTH, NULL);
    }
}

static void EnRemixTime_PathDone(EnRemixTime* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;

    switch (this->trackIndex) {
        case NEXT_RING:
            Time_SetStage(play, TIME_STAGE_RING);
            this->mode = SPHERE_REST;
            break;
        case NEXT_HEAD:
            Time_SetStage(play, TIME_STAGE_HEAD);
            this->mode = SPHERE_REST;
            Actor_PlaySfx(thisx, NA_SE_EV_STONE_BOUND);
            break;
        case NEXT_PLATE:
            Actor_PlaySfx(thisx, NA_SE_EV_BLOCK_BOUND);
            EnRemixTime_LightEye1(this, play);
            break;
        case NEXT_PAN:
            Time_SetStage(play, TIME_STAGE_PAN);
            Actor_PlaySfx(thisx, NA_SE_EV_STONE_BOUND);
            this->mode = SPHERE_REST;
            this->timer = 60;
            break;
        case NEXT_EYE2:
            Time_SetStage(play, TIME_STAGE_EYE2);
            this->mode = SPHERE_REST;
            if (!Flags_GetSwitch(play, TIME_FLAG_ALIVE)) {
                Flags_SetSwitch(play, TIME_FLAG_ALIVE); // the statue awakes: the chest falls onto the dais
                Time_Chime();
                Audio_PlayFanfare(NA_BGM_MEDALLION_GET);
            }
            break;
    }
}

static void EnRemixTime_UpdateSphereAdult(EnRemixTime* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    Player* player = GET_PLAYER(play);
    s32 stage = Time_Stage(play);
    Vec3f pos;
    f32 t;

    switch (this->mode) {
        case SPHERE_REST:
            EnRemixTime_SphereStagePos(this, play, stage, &pos);
            thisx->world.pos = pos;
            this->scale = 1.0f;
            if (stage == TIME_STAGE_PEDESTAL) {
                if ((sTime.pedestal != NULL) && (sTime.pedestal->offset < -6.0f)) {
                    this->mode = SPHERE_FALL; // the pedestal sank under it
                    thisx->velocity.x = 0.0f;
                    thisx->velocity.y = 2.0f;
                    thisx->velocity.z = -2.5f;
                    break;
                }
                // pushed (Link walks into it) or struck: it rolls off down the track
                if ((thisx->xzDistToPlayer < 62.0f) && (fabsf(player->actor.world.pos.y - TIME_PEDESTAL_TOP) < 70.0f) &&
                    (player->speedXZ > 1.5f) &&
                    (ABS((s16)(thisx->yawTowardsPlayer + 0x8000 - player->actor.world.rot.y)) < 0x2400)) {
                    this->pushTimer++;
                } else {
                    this->pushTimer = 0;
                }
                if ((this->pushTimer > 6) || (this->collider.base.acFlags & AC_HIT)) {
                    this->collider.base.acFlags &= ~AC_HIT;
                    this->mode = SPHERE_TRACK;
                    this->trackIndex = 0;
                    this->t = 0.0f;
                    Actor_PlaySfx(thisx, NA_SE_EV_ROCK_SLIDE);
                }
            } else if (stage == TIME_STAGE_RING) {
                if (Time_Water() >= TIME_CRADLE_Y) { // the water reached it: up in a bubble, into the statue's head
                    Vec3f to = { TIME_HEAD_X, TIME_HEAD_Y, TIME_HEAD_Z };

                    EnRemixTime_SphereFly(this, &to, 700.0f, 110, NEXT_HEAD);
                    Actor_PlaySfx(thisx, NA_SE_EV_WATER_BUBBLE);
                } else if (Flags_GetSwitch(play, TIME_FLAG_REVERSE) &&
                           (ABS((s16)(TIME_CRADLE_PHI + ((sTime.ring != NULL) ? sTime.ring->yaw : 0) -
                                      TIME_LAUNCH_PHI)) < 0x300)) {
                    Vec3f to = { TIME_PAN_R_X, 0.0f, TIME_PAN_R_Z };

                    to.y = Time_PanTop(1) + TIME_SPHERE_R;
                    EnRemixTime_SphereFly(this, &to, 260.0f, 36, NEXT_PAN); // thrown by the ring turning back
                    Actor_PlaySfx(thisx, NA_SE_EV_STONE_LAUNCH);
                }
            } else if (stage == TIME_STAGE_HEAD) {
                if (Flags_GetSwitch(play, TIME_FLAG_HAMMER)) { // the grate opens: onto the first eye's plate
                    Vec3f to = { TIME_SOCKET_PLATE_X, TIME_UPPER + TIME_SPHERE_R, TIME_SOCKET_PLATE_Z };

                    EnRemixTime_SphereFly(this, &to, 0.0f, 16, NEXT_PLATE);
                }
            } else if (stage == TIME_STAGE_PAN) {
                if (this->timer > 0) {
                    this->timer--;
                } else if (!Flags_GetSwitch(play, TIME_FLAG_EYE1)) {
                    this->mode = SPHERE_ROLL_OFF; // the second eye is still shut
                    thisx->velocity.x = 3.0f;
                    thisx->velocity.y = 4.0f;
                    thisx->velocity.z = 3.0f;
                } else if (Time_PanTop(1) >= TIME_EYE2_Y - TIME_SPHERE_R - 2.0f) {
                    Vec3f to = { TIME_EYE2_X, TIME_EYE2_Y, TIME_FACE_Z - 12.0f };

                    EnRemixTime_SphereFly(this, &to, 20.0f, 30, NEXT_EYE2);
                    Actor_PlaySfx(thisx, NA_SE_EV_ROCK_SLIDE);
                }
            } else if (stage == TIME_STAGE_SEED_EYE1) {
                this->scale = 0.3f;
                if (sTime.sunOnSeed) {
                    this->timer++;
                    if (this->timer > 20) {
                        this->mode = SPHERE_GROW;
                        this->timer = 0;
                        Actor_PlaySfx(thisx, NA_SE_EV_STONE_GROW_UP);
                    }
                } else {
                    this->timer = 0;
                }
            }
            break;

        case SPHERE_FALL:
        case SPHERE_ROLL_OFF:
            thisx->velocity.y -= 1.2f;
            thisx->world.pos.x += thisx->velocity.x;
            thisx->world.pos.y += thisx->velocity.y;
            thisx->world.pos.z += thisx->velocity.z;
            if (this->mode == SPHERE_ROLL_OFF) {
                this->scale -= 0.04f; // (it fades as it falls: back to the pedestal)
            }
            if ((thisx->world.pos.y < -500.0f) || (this->scale <= 0.0f)) {
                EnRemixTime_SphereReturn(this, play);
            }
            break;

        case SPHERE_GONE: // comes back to the pedestal once it is up again
            this->scale = 0.0f;
            if ((this->timer > 0) && (--this->timer == 0)) {
                this->timer = -1;
            }
            if ((this->timer < 0) && ((sTime.pedestal == NULL) || (sTime.pedestal->offset > -1.0f))) {
                this->mode = SPHERE_REST;
                this->timer = 0;
                this->scale = 0.0f;
                Actor_PlaySfx(thisx, NA_SE_EV_TRE_BOX_FLASH);
            }
            break;

        case SPHERE_TRACK: // down the curved track, into the cradle
            this->t += 5.0f;
            while (this->trackIndex < TIME_TRACK_N - 1) {
                Vec3f a;
                Vec3f b;
                f32 len;

                a.x = sTrack[this->trackIndex].x;
                a.y = sTrack[this->trackIndex].y;
                a.z = sTrack[this->trackIndex].z;
                b.x = sTrack[this->trackIndex + 1].x;
                b.y = sTrack[this->trackIndex + 1].y;
                b.z = sTrack[this->trackIndex + 1].z;
                len = Math_Vec3f_DistXYZ(&a, &b);

                if (this->t < len) {
                    t = this->t / len;
                    thisx->world.pos.x = a.x + (b.x - a.x) * t;
                    thisx->world.pos.y = a.y + (b.y - a.y) * t;
                    thisx->world.pos.z = a.z + (b.z - a.z) * t;
                    break;
                }
                this->t -= len;
                this->trackIndex++;
            }
            Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ROLL_STAND - SFX_FLAG);
            if (this->trackIndex >= TIME_TRACK_N - 1) {
                // in the cradle: its plate starts the ring (and the sphere is trapped in it)
                if (!Flags_GetSwitch(play, TIME_FLAG_PLATE)) {
                    Flags_SetSwitch(play, TIME_FLAG_PLATE);
                    Time_Chime();
                }
                Actor_PlaySfx(thisx, NA_SE_EV_BLOCK_BOUND);
                Time_SetStage(play, TIME_STAGE_RING);
                this->mode = SPHERE_REST;
            }
            break;

        case SPHERE_PATH: // a quadratic curve from -> mid -> to
            this->t += 1.0f / this->timer;
            t = CLAMP_MAX(this->t, 1.0f);
            if (this->trackIndex == NEXT_PAN) { // the pan may be moving: aim at it
                this->to.y = Time_PanTop(1) + TIME_SPHERE_R;
            }
            thisx->world.pos.x = SQ(1 - t) * this->from.x + 2 * (1 - t) * t * this->mid.x + SQ(t) * this->to.x;
            thisx->world.pos.y = SQ(1 - t) * this->from.y + 2 * (1 - t) * t * this->mid.y + SQ(t) * this->to.y;
            thisx->world.pos.z = SQ(1 - t) * this->from.z + 2 * (1 - t) * t * this->mid.z + SQ(t) * this->to.z;
            if (this->t >= 1.0f) {
                EnRemixTime_PathDone(this, play);
            }
            break;

        case SPHERE_GLOW: // lighting the first eye, then home to the pedestal
            if (--this->timer <= 0) {
                EnRemixTime_SphereReturn(this, play);
            }
            break;

        case SPHERE_GROW: // the seed grows into the sphere in the sunlight
            this->timer++;
            this->scale = 0.3f + 0.7f * CLAMP_MAX(this->timer / 30.0f, 1.0f);
            thisx->world.pos.y = TIME_UPPER + TIME_SPHERE_R * this->scale;
            if (this->timer >= 40) {
                this->scale = 1.0f;
                EnRemixTime_LightEye1(this, play);
            }
            break;

        default:
            this->mode = SPHERE_REST;
            break;
    }

    // fading in after coming back
    if ((this->mode == SPHERE_REST) && (stage != TIME_STAGE_SEED_EYE1)) {
        Math_StepToF(&this->scale, 1.0f, 0.05f);
    }
    if ((this->mode == SPHERE_REST) && (stage == TIME_STAGE_PEDESTAL)) {
        Collider_UpdateCylinder(thisx, &this->collider);
        CollisionCheck_SetAC(play, &play->colChkCtx, &this->collider.base);
    }
}

static void EnRemixTime_UpdateSeed(EnRemixTime* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    Player* player = GET_PLAYER(play);
    s32 stage = Time_Stage(play);
    Vec3f pos;

    if ((stage == TIME_STAGE_EYE2) || Flags_GetSwitch(play, TIME_FLAG_ALIVE)) {
        this->scale = 0.0f; // it has done its work in the present: nothing left in the past
        return;
    }
    this->scale = 1.0f;
    switch (this->mode) {
        case SPHERE_REST: // on the pedestal (or planted in the first eye)
            EnRemixTime_SphereStagePos(this, play, (stage == TIME_STAGE_SEED_EYE1) ? stage : TIME_STAGE_PEDESTAL, &pos);
            thisx->world.pos = pos;
            if (stage == TIME_STAGE_SEED_EYE1) {
                break; // it has taken root
            }
            this->mode = SPHERE_SEED;
            FALLTHROUGH;
        case SPHERE_SEED:
            if (Actor_HasParent(thisx, play)) {
                this->mode = SPHERE_CARRIED;
                Player_PlaySfx(player, NA_SE_PL_PULL_UP_POT);
                break;
            }
            if ((thisx->xzDistToPlayer < 60.0f) && (fabsf(thisx->yDistToPlayer) < 50.0f)) {
                s16 facing = thisx->yawTowardsPlayer - player->actor.world.rot.y;

                if (ABS(facing) >= 0x5556) {
                    Actor_OfferGetItem(thisx, play, GI_NONE, 40.0f, 40.0f); // (GI_NONE: Link lifts it)
                }
            }
            break;

        case SPHERE_CARRIED:
            if (Actor_HasNoParent(thisx, play)) {
                this->mode = SPHERE_THROWN;
                thisx->velocity.x = Math_SinS(thisx->world.rot.y) * thisx->speed;
                thisx->velocity.z = Math_CosS(thisx->world.rot.y) * thisx->speed;
            }
            break;

        case SPHERE_THROWN:
            thisx->velocity.y = CLAMP_MIN(thisx->velocity.y - 1.2f, -20.0f);
            Actor_UpdatePos(thisx);
            Actor_UpdateBgCheckInfo(play, thisx, 10.0f, 10.0f, 0.0f,
                                    UPDBGCHECKINFO_FLAG_0 | UPDBGCHECKINFO_FLAG_2 | UPDBGCHECKINFO_FLAG_7);
            if (thisx->bgCheckFlags & BGCHECKFLAG_GROUND) {
                f32 px = thisx->world.pos.x - TIME_SOCKET_PLATE_X;
                f32 pz = thisx->world.pos.z - TIME_SOCKET_PLATE_Z;

                thisx->velocity.x = thisx->velocity.z = thisx->velocity.y = 0.0f;
                if ((SQ(px) + SQ(pz) < SQ(70.0f)) && (fabsf(thisx->world.pos.y - TIME_UPPER) < 30.0f)) {
                    Time_SetStage(play, TIME_STAGE_SEED_EYE1); // planted in the first eye
                    Time_Chime();
                    this->mode = SPHERE_REST;
                } else {
                    this->mode = SPHERE_SEED;
                }
            } else if (thisx->world.pos.y < -400.0f) { // into the pit: back on the pedestal
                this->mode = SPHERE_REST;
                Actor_PlaySfx(thisx, NA_SE_EV_TRE_BOX_FLASH);
            }
            break;

        default:
            this->mode = SPHERE_REST;
            break;
    }
}

// ---------------------------------------------------------------- the other pieces

static void EnRemixTime_UpdateEcho(EnRemixTime* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    Player* player = GET_PLAYER(play);
    s32 max = (this->arg == 0) ? 2 : 1;
    f32 tx;
    f32 tz;

    if (!this->isChild) {
        // the present: where the past left it (the scale's pillar rides the left pan)
        if ((this->arg == 1) && (this->cell == 1)) {
            thisx->world.pos.y = Time_PanTop(0);
        }
        if (fabsf(this->dyna.unk_150) > 0.001f) {
            this->dyna.unk_150 = 0.0f; // too heavy: it does not move
            player->stateFlags2 &= ~PLAYER_STATE2_4;
        }
        return;
    }

    if (this->target == this->cell) {
        if (fabsf(this->dyna.unk_150) > 0.001f) {
            s16 dir = this->dyna.unk_158 + ((this->dyna.unk_150 < 0.0f) ? 0x8000 : 0);

            if ((ABS((s16)(dir - 0x8000)) < 0x2000) && (this->cell < max)) {
                this->target = this->cell + 1; // towards -z
            } else if ((ABS(dir) < 0x2000) && (this->cell > 0)) {
                this->target = this->cell - 1; // towards +z
            } else {
                player->stateFlags2 &= ~PLAYER_STATE2_4;
            }
            this->dyna.unk_150 = 0.0f;
        }
        return;
    }

    // sliding to the next place
    if (this->arg == 0) {
        tx = (this->target == 0)   ? TIME_MIRROR_CELL0_X
             : (this->target == 1) ? TIME_MIRROR_CELL1_X
                                   : TIME_MIRROR_CELL2_X;
        tz = (this->target == 0)   ? TIME_MIRROR_CELL0_Z
             : (this->target == 1) ? TIME_MIRROR_CELL1_Z
                                   : TIME_MIRROR_CELL2_Z;
    } else {
        tx = this->target ? TIME_BAL_CELL1_X : TIME_BAL_CELL0_X;
        tz = this->target ? TIME_BAL_CELL1_Z : TIME_BAL_CELL0_Z;
    }
    this->dyna.unk_150 = 0.0f;
    Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ROCK_SLIDE - SFX_FLAG);
    Math_StepToF(&thisx->world.pos.x, tx, 2.5f);
    if (Math_StepToF(&thisx->world.pos.z, tz, 2.5f) && (thisx->world.pos.x == tx)) {
        this->cell = this->target;
        if (this->arg == 0) {
            Time_SetBits(play, TIME_FLAG_MIRROR_CELL, 2, this->cell);
        } else {
            Time_SetBits(play, TIME_FLAG_BAL_CELL, 1, this->cell);
        }
        Actor_PlaySfx(thisx, NA_SE_EV_BLOCK_BOUND);
        player->stateFlags2 &= ~PLAYER_STATE2_4;
    }
}

static void EnRemixTime_UpdatePiece(EnRemixTime* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    f32 target;

    switch (this->type) {
        case TIME_PEDESTAL:
            // sinks while the adult stands on the dais, unless the crystal under it locked it; lower in the past
            target = this->isChild ? TIME_CHILD_PEDESTAL : 0.0f;
            if (!this->isChild && !Flags_GetSwitch(play, TIME_FLAG_LOCK) && Time_LinkOnDais(play) &&
                (Time_Stage(play) == TIME_STAGE_PEDESTAL)) {
                target = -110.0f;
            }
            if (this->offset != target) {
                Math_StepToF(&this->offset, target, (target < 0.0f) ? 5.0f : 2.0f);
                Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ELEVATOR_MOVE3 - SFX_FLAG);
            }
            thisx->world.pos.y = thisx->home.pos.y + this->offset;
            break;

        case TIME_RING:
            if (!this->isChild && Flags_GetSwitch(play, TIME_FLAG_PLATE)) {
                this->yaw += Flags_GetSwitch(play, TIME_FLAG_REVERSE) ? -TIME_RING_SPEED : TIME_RING_SPEED;
                Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ELEVATOR_MOVE3 - SFX_FLAG);
            }
            thisx->shape.rot.y = thisx->world.rot.y = this->yaw;
            break;

        case TIME_ECHO:
            EnRemixTime_UpdateEcho(this, play);
            break;

        case TIME_PAN:
            target = Time_Tilt(play);
            if (this->offset != target) {
                Math_StepToF(&this->offset, target, 3.0f);
                Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ELEVATOR_MOVE3 - SFX_FLAG);
            }
            thisx->world.pos.y = thisx->home.pos.y + (this->arg ? this->offset : -this->offset);
            break;

        case TIME_WEIGHT:
            if ((this->mode == 0) && !this->isChild && Flags_GetSwitch(play, TIME_FLAG_WEIGHT)) {
                this->mode = 1; // the floor switch cut its rope
                thisx->velocity.y = 0.0f;
            }
            if (this->mode >= 1) {
                f32 rest = Time_PanTop(0) + ((Time_GetBits(play, TIME_FLAG_BAL_CELL, 1) == 1) ? 180.0f : 0.0f);

                if (this->mode == 1) {
                    thisx->velocity.y -= 1.5f;
                    thisx->world.pos.y += thisx->velocity.y;
                    if (thisx->world.pos.y <= rest) {
                        thisx->world.pos.y = rest;
                        this->mode = 2;
                        Actor_PlaySfx(thisx, NA_SE_EV_STONE_BOUND);
                    }
                } else {
                    thisx->world.pos.y = rest;
                }
            }
            break;

        case TIME_TABLET:
            if ((this->arg == 2) && !Flags_GetSwitch(play, TIME_FLAG_EYE1)) {
                break; // appears with the first eye's light
            }
            if (Actor_TalkOfferAccepted(thisx, play)) {
                this->talking = true;
            } else if (!this->talking || (Message_GetState(&play->msgCtx) == TEXT_STATE_NONE)) {
                this->talking = false;
                Actor_OfferTalk(thisx, play, 100.0f);
            }
            break;

        case TIME_BLAST:
            if (!Flags_GetSwitch(play, TIME_FLAG_REVERSE)) {
                if (this->collider.base.acFlags & AC_HIT) {
                    this->collider.base.acFlags &= ~AC_HIT;
                    Flags_SetSwitch(play, TIME_FLAG_REVERSE); // ring 1 turns the other way
                    Time_Chime();
                }
                Collider_UpdateCylinder(thisx, &this->collider);
                CollisionCheck_SetAC(play, &play->colChkCtx, &this->collider.base);
                CollisionCheck_SetOC(play, &play->colChkCtx, &this->collider.base);
            }
            break;

        case TIME_DOOR:
            if (Flags_GetSwitch(play, this->arg)) {
                target = (this->mode == 0) ? -250.0f : 260.0f;
                if (this->offset != target) {
                    Math_StepToF(&this->offset, target, 4.0f);
                    Actor_PlaySfx_Flagged(thisx, NA_SE_EV_STONE_STATUE_OPEN - SFX_FLAG);
                    if (this->offset == target) {
                        Actor_PlaySfx(thisx, NA_SE_EV_STONEDOOR_STOP);
                    }
                }
            }
            thisx->world.pos.y = thisx->home.pos.y + this->offset;
            break;
    }
}

void EnRemixTime_Update(Actor* thisx, PlayState* play) {
    EnRemixTime* this = (EnRemixTime*)thisx;

    switch (this->type) {
        case TIME_CONTROLLER:
            EnRemixTime_UpdateController(this, play);
            break;
        case TIME_SPHERE:
            if (this->isChild) {
                EnRemixTime_UpdateSeed(this, play);
            } else {
                EnRemixTime_UpdateSphereAdult(this, play);
            }
            break;
        default:
            EnRemixTime_UpdatePiece(this, play);
            break;
    }
}

// ---------------------------------------------------------------- drawing

/** A light shaft from `a` to `b` (radius `r`). */
static void Time_DrawBeam(PlayState* play, Vec3f* a, Vec3f* b, f32 r, u8 cr, u8 cg, u8 cb, u8 alpha) {
    f32 dx = b->x - a->x;
    f32 dy = b->y - a->y;
    f32 dz = b->z - a->z;
    f32 len = sqrtf(SQ(dx) + SQ(dy) + SQ(dz));

    if (len < 1.0f) {
        return;
    }
    OPEN_DISPS(play->state.gfxCtx, "../z_en_remix_time.c", __LINE__);
    Matrix_Translate(a->x, a->y, a->z, MTXMODE_NEW);
    // turn +y onto the shaft: yaw towards it, then tip forwards by the pitch
    Matrix_RotateY(Math_FAtan2F(dx, dz), MTXMODE_APPLY);
    Matrix_RotateX(Math_FAtan2F(sqrtf(SQ(dx) + SQ(dz)), dy), MTXMODE_APPLY);
    Matrix_Scale(r, len, r, MTXMODE_APPLY);
    gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, cr, cg, cb, alpha);
    MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, play->state.gfxCtx, "../z_en_remix_time.c", __LINE__);
    gSPDisplayList(POLY_XLU_DISP++, gTimeBeamDL);
    CLOSE_DISPS(play->state.gfxCtx, "../z_en_remix_time.c", __LINE__);
}

/** A glowing disc at `pos`, facing up (or towards +z with `upright`, +x with `east`). */
static void Time_DrawDisc(PlayState* play, f32 x, f32 y, f32 z, f32 r, s32 facing, u8 cr, u8 cg, u8 cb, u8 alpha) {
    OPEN_DISPS(play->state.gfxCtx, "../z_en_remix_time.c", __LINE__);
    Matrix_Translate(x, y, z, MTXMODE_NEW);
    if (facing == 1) {
        Matrix_RotateX(M_PI / 2, MTXMODE_APPLY); // +y to +z
    } else if (facing == 2) {
        Matrix_RotateZ(-M_PI / 2, MTXMODE_APPLY); // +y to +x
    }
    Matrix_Scale(r, 1.0f, r, MTXMODE_APPLY);
    gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, cr, cg, cb, alpha);
    MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, play->state.gfxCtx, "../z_en_remix_time.c", __LINE__);
    gSPDisplayList(POLY_XLU_DISP++, gTimeDiscDL);
    CLOSE_DISPS(play->state.gfxCtx, "../z_en_remix_time.c", __LINE__);
}

static void EnRemixTime_DrawController(EnRemixTime* this, PlayState* play) {
    GraphicsContext* gfxCtx = play->state.gfxCtx;
    u32 frames = play->gameplayFrames;
    f32 pulse = 0.5f + 0.5f * Math_SinS((s16)(frames * 0x500));
    s32 alive = Flags_GetSwitch(play, TIME_FLAG_ALIVE);
    s32 eye1 = Flags_GetSwitch(play, TIME_FLAG_EYE1);
    s32 cell = Time_GetBits(play, TIME_FLAG_MIRROR_CELL, 2);
    f32 sunEnd;
    Vec3f a;
    Vec3f b;

    OPEN_DISPS(gfxCtx, "../z_en_remix_time.c", __LINE__);

    Gfx_SetupDL_25Opa(gfxCtx);
    gDPSetEnvColor(POLY_OPA_DISP++, 0, 0, 0, 255);

    // the hourglass over the dais (upside down in the past), its three rings: they line up once the statue awakes
    Matrix_Translate(TIME_HOURGLASS_X, TIME_HOURGLASS_Y + Math_SinS((s16)(frames * 0x180)) * 12.0f, TIME_HOURGLASS_Z,
                     MTXMODE_NEW);
    Matrix_Push();
    Matrix_RotateY(frames * 0.01f, MTXMODE_APPLY);
    if (this->isChild) {
        Matrix_RotateX(M_PI, MTXMODE_APPLY);
    }
    MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
    gSPDisplayList(POLY_OPA_DISP++, gTimeHourglassDL);
    Matrix_Pop();
    {
        static Gfx* const sRings[] = { gTimeDecoRingADL, gTimeDecoRingBDL, gTimeDecoRingCDL };
        s32 i;

        if (alive) {
            gDPSetEnvColor(POLY_OPA_DISP++, 60, 50, 0, 255);
        }
        for (i = 0; i < 3; i++) {
            Matrix_Push();
            if (alive) {
                Matrix_RotateY(frames * 0.02f, MTXMODE_APPLY); // aligned, turning together
            } else {
                Matrix_RotateY(frames * (0.012f + 0.006f * i) * ((i & 1) ? -1 : 1), MTXMODE_APPLY);
                Matrix_RotateX(0.5f + frames * (0.009f + 0.004f * i), MTXMODE_APPLY);
                Matrix_RotateZ(0.3f * i, MTXMODE_APPLY);
            }
            MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
            gSPDisplayList(POLY_OPA_DISP++, sRings[i]);
            Matrix_Pop();
        }
        gDPSetEnvColor(POLY_OPA_DISP++, 0, 0, 0, 255);
    }

    // the clock's hand (on the east wall, facing west): CHILD or ADULT
    Matrix_Translate(TIME_CLOCK_X, TIME_CLOCK_Y, TIME_CLOCK_Z, MTXMODE_NEW);
    Matrix_RotateY(-M_PI / 2, MTXMODE_APPLY);
    Matrix_RotateZ(BINANG_TO_RAD(this->yaw), MTXMODE_APPLY);
    MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
    gSPDisplayList(POLY_OPA_DISP++, gTimeHandDL);

    // the second eye: a stone lid until the first is lit
    if (!eye1) {
        Matrix_Translate(TIME_EYE2_X, TIME_EYE2_Y, TIME_FACE_Z, MTXMODE_NEW);
        MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
        gSPDisplayList(POLY_OPA_DISP++, gTimeLidDL);
    }

    // the grate over the first eye's plate: slides away once the hammer switch is down
    Matrix_Translate(TIME_SOCKET_PLATE_X + (Flags_GetSwitch(play, TIME_FLAG_HAMMER) ? 95.0f : 0.0f), TIME_GRATE_Y,
                     TIME_HEAD_Z, MTXMODE_NEW);
    MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
    gSPDisplayList(POLY_OPA_DISP++, gTimeGrateDL);

    Gfx_SetupDL_25Xlu(gfxCtx);

    // the water in the pit and the basin
    if (this->offset > -760.0f) {
        Matrix_Translate(0.0f, this->offset, 0.0f, MTXMODE_NEW);
        gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, 70, 150, 235, 150);
        MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
        gSPDisplayList(POLY_XLU_DISP++, gTimeWaterDL);
    }
    // the hourglass's glass
    Matrix_Translate(TIME_HOURGLASS_X, TIME_HOURGLASS_Y + Math_SinS((s16)(frames * 0x180)) * 12.0f, TIME_HOURGLASS_Z,
                     MTXMODE_NEW);
    Matrix_RotateY(frames * 0.01f, MTXMODE_APPLY);
    gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, 200, 230, 255, 90);
    MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
    gSPDisplayList(POLY_XLU_DISP++, gTimeHourglassGlassDL);

    CLOSE_DISPS(gfxCtx, "../z_en_remix_time.c", __LINE__);

    // the sun through the ceiling, into the basin: onto the mirror (present, block in the beam), else the floor
    sunEnd = TIME_BASIN_FLOOR;
    if (cell == 1) {
        sunEnd = this->isChild ? (TIME_BASIN_FLOOR + 60.0f) : (TIME_BASIN_FLOOR + 210.0f);
    }
    a.x = b.x = TIME_MIRROR_CELL1_X;
    a.z = b.z = TIME_MIRROR_CELL1_Z;
    a.y = TIME_CEILING;
    b.y = sunEnd;
    Time_DrawBeam(play, &b, &a, 38.0f, 255, 240, 170, 70);
    Time_DrawDisc(play, b.x, b.y + 2.0f, b.z, 45.0f + pulse * 6.0f, 0, 255, 240, 170, 110);
    if (!this->isChild && (cell == 1)) { // thrown by the mirror onto the walkway
        Vec3f spot = { TIME_SPOT_X, 2.0f, TIME_SPOT_Z };

        Time_DrawBeam(play, &b, &spot, 16.0f, 255, 240, 170, 90);
        Time_DrawDisc(play, spot.x, spot.y, spot.z, TIME_SPOT_R + pulse * 8.0f, 0, 255, 230, 150, 140);
    }
    if (this->beam) { // turned by the Mirror Shield
        Time_DrawBeam(play, &this->beamFrom, &this->beamTo, (this->beam == 2) ? 14.0f : 10.0f, 255, 245, 190,
                      (this->beam == 2) ? 170 : 120);
    }

    // the eyes: the first glows once lit, the second once open (brightly once the statue is awake)
    if (eye1) {
        Time_DrawDisc(play, TIME_EYE1_X, TIME_EYE1_Y, TIME_FACE_Z + 4.0f, 62.0f, 1, 120, 230, 255,
                      150 + (s32)(pulse * 80));
        Time_DrawDisc(play, TIME_EYE2_X, TIME_EYE2_Y, TIME_FACE_Z + 4.0f, 62.0f, 1, 120, 230, 255,
                      alive ? (150 + (s32)(pulse * 80)) : 40);
    }
    if (Flags_GetSwitch(play, TIME_FLAG_MOUTH)) { // the sun symbol, woken by the light
        Time_DrawDisc(play, TIME_SUN_SYMBOL_X + 4.0f, TIME_SUN_SYMBOL_Y, TIME_SUN_SYMBOL_Z, 80.0f, 2, 255, 170, 60,
                      140 + (s32)(pulse * 60));
    }
}

static void EnRemixTime_DrawSphere(EnRemixTime* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    GraphicsContext* gfxCtx = play->state.gfxCtx;
    s32 stage = Time_Stage(play);
    f32 s = this->scale;
    u32 frames = play->gameplayFrames;

    if (s <= 0.01f) {
        return;
    }
    OPEN_DISPS(gfxCtx, "../z_en_remix_time.c", __LINE__);
    Gfx_SetupDL_25Opa(gfxCtx);
    if (this->isChild || ((stage == TIME_STAGE_SEED_EYE1) && (this->mode == SPHERE_REST))) {
        // the seed (planted, it shows its sprout; it glitters in the sun)
        gDPSetEnvColor(POLY_OPA_DISP++, sTime.sunOnSeed ? 120 : 30, sTime.sunOnSeed ? 100 : 25, 0, 255);
        Matrix_Translate(thisx->world.pos.x, thisx->world.pos.y, thisx->world.pos.z, MTXMODE_NEW);
        Matrix_RotateY(frames * 0.03f, MTXMODE_APPLY);
        Matrix_Scale(1.4f, 1.4f, 1.4f, MTXMODE_APPLY);
        MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
        gSPDisplayList(POLY_OPA_DISP++, gTimeSeedDL);
    } else {
        s32 glow = (this->mode == SPHERE_GLOW) || (stage == TIME_STAGE_EYE2);

        gDPSetEnvColor(POLY_OPA_DISP++, glow ? 90 : 25, glow ? 80 : 20, 0, 255);
        Matrix_Translate(thisx->world.pos.x, thisx->world.pos.y, thisx->world.pos.z, MTXMODE_NEW);
        Matrix_RotateY(frames * 0.02f, MTXMODE_APPLY);
        Matrix_Scale(s, s, s, MTXMODE_APPLY);
        MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
        gSPDisplayList(POLY_OPA_DISP++, gTimeSphereDL);
        if ((this->mode == SPHERE_PATH) && (this->trackIndex == NEXT_HEAD)) { // the bubble it floats up in
            Gfx_SetupDL_25Xlu(gfxCtx);
            gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, 170, 220, 255, 110);
            Matrix_Translate(thisx->world.pos.x, thisx->world.pos.y, thisx->world.pos.z, MTXMODE_NEW);
            Matrix_Scale(1.0f + 0.06f * Math_SinS((s16)(frames * 0x900)), 1.0f, 1.0f, MTXMODE_APPLY);
            MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
            gSPDisplayList(POLY_XLU_DISP++, gTimeBubbleDL);
        }
    }
    CLOSE_DISPS(gfxCtx, "../z_en_remix_time.c", __LINE__);
}

void EnRemixTime_Draw(Actor* thisx, PlayState* play) {
    EnRemixTime* this = (EnRemixTime*)thisx;
    GraphicsContext* gfxCtx = play->state.gfxCtx;
    Gfx* dl = NULL;
    Gfx* extra = NULL;
    f32 extraY = 0.0f;

    switch (this->type) {
        case TIME_CONTROLLER:
            EnRemixTime_DrawController(this, play);
            return;
        case TIME_SPHERE:
            EnRemixTime_DrawSphere(this, play);
            return;
        case TIME_PEDESTAL:
            dl = gTimePedestalDL;
            break;
        case TIME_RING:
            dl = gTimeRingDL;
            break;
        case TIME_ECHO:
            if (this->isChild) {
                dl = gTimeBlockDL;
            } else if ((this->arg == 0) && (this->cell == 0)) {
                dl = gTimeBlockDecayedDL;
            } else {
                dl = gTimePillarDL;
                if (this->arg == 0) {
                    extra = gTimeMirrorDL;
                    extraY = 180.0f;
                }
            }
            break;
        case TIME_PAN:
            dl = this->arg ? gTimePanRDL : gTimePanLDL;
            break;
        case TIME_WEIGHT:
            dl = gTimeWeightDL;
            break;
        case TIME_BRIDGE:
            dl = this->isChild ? gTimeBridgeDL : gTimeBridgeRuinDL;
            break;
        case TIME_RAMP:
            dl = this->isChild ? gTimeRampDL : gTimeRampRuinDL;
            break;
        case TIME_TABLET:
            if ((this->arg == 2) && !Flags_GetSwitch(play, TIME_FLAG_EYE1)) {
                return;
            }
            dl = gTimeTabletDL;
            break;
        case TIME_DOOR:
            dl = (this->mode == 0) ? gTimeJawDL : gTimeDoorDL;
            break;
        case TIME_BLAST: {
            s32 woken = Flags_GetSwitch(play, TIME_FLAG_REVERSE);

            OPEN_DISPS(gfxCtx, "../z_en_remix_time.c", __LINE__);
            Gfx_SetupDL_25Xlu(gfxCtx);
            Matrix_Translate(thisx->world.pos.x, thisx->world.pos.y, thisx->world.pos.z, MTXMODE_NEW);
            Matrix_RotateY(play->gameplayFrames * (woken ? 0.08f : 0.03f), MTXMODE_APPLY);
            gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, woken ? 90 : 255, woken ? 170 : 60, woken ? 255 : 50, 220);
            MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
            gSPDisplayList(POLY_XLU_DISP++, gTimeCrystalDL);
            CLOSE_DISPS(gfxCtx, "../z_en_remix_time.c", __LINE__);
            return;
        }
        default:
            return;
    }

    OPEN_DISPS(gfxCtx, "../z_en_remix_time.c", __LINE__);
    Gfx_SetupDL_25Opa(gfxCtx);
    gDPSetEnvColor(POLY_OPA_DISP++, 0, 0, 0, 255);
    Matrix_Translate(thisx->world.pos.x, thisx->world.pos.y, thisx->world.pos.z, MTXMODE_NEW);
    Matrix_RotateY(BINANG_TO_RAD(thisx->shape.rot.y), MTXMODE_APPLY);
    MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
    gSPDisplayList(POLY_OPA_DISP++, dl);
    if (extra != NULL) {
        Matrix_Translate(0.0f, extraY, 0.0f, MTXMODE_APPLY);
        MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
        gSPDisplayList(POLY_OPA_DISP++, extra);
    }
    if ((this->type == TIME_PAN) || ((this->type == TIME_WEIGHT) && (this->mode == 0))) {
        // chains up to the ceiling (the weight's is cut when it falls)
        f32 top = thisx->world.pos.y + ((this->type == TIME_WEIGHT) ? TIME_WEIGHT_SIZE : 0.0f);
        f32 len = TIME_CEILING - top;
        s32 k;

        for (k = 0; k < ((this->type == TIME_PAN) ? 2 : 1); k++) {
            f32 dx = (this->type == TIME_PAN) ? (k ? 40.0f : -40.0f) : 0.0f;

            Matrix_Translate(thisx->world.pos.x + dx, top, thisx->world.pos.z, MTXMODE_NEW);
            Matrix_Scale(1.0f, len / 100.0f, 1.0f, MTXMODE_APPLY);
            MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_time.c", __LINE__);
            gSPDisplayList(POLY_OPA_DISP++, gTimeChainDL);
        }
    }
    CLOSE_DISPS(gfxCtx, "../z_en_remix_time.c", __LINE__);
}
