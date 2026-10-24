/*
 * File: z_en_remix_abyss.c
 * Overlay: ovl_En_Remix_Abyss
 * Description: Web Remix level 9, the Shrine of the Swinging Abyss. A small stone room where Link earns the Hookshot,
 *              then one enormous bottomless chamber of moving platforms, every one with a Hookshot target: a pendulum,
 *              a carousel, rising towers, a platform that runs through a tunnel, two crossing paths, and the
 *              clockwork storm round the central mechanism, the exit on top inside a turning ring. The pieces are
 *              object_remix_abyss (tools/remix/make_abyss_parts.py, which also writes the plan this file reads: every
 *              platform's motion, ABYSS_PLATS in object_remix_abyss.h); the rooms are tools/remix/make_abyss.py.
 *
 *   ABYSS_CTRL      The gauntlet's clock: every platform's place is a function of it, so each attempt is the same.
 *                   A fall into the abyss: half a second of black and Link stands at the start of the gauntlet again,
 *                   the clock (and every platform) back at the beginning. Once Link has the Hookshot, it goes on a
 *                   C button.
 *   ABYSS_PLATFORM  A moving platform (pendulum, orbit, lift or shuttle). Its target plaque's face is a Hookshot
 *                   surface; the plaque glows, and Z-targeting locks on to it, while it is within the Hookshot's
 *                   reach. The cracked ones break away a moment after Link lands on them, and come back later.
 *   ABYSS_RING      The stone ring round the exit balcony: one opening, turning.
 *   ABYSS_CUBE      Pushed (both ways) between its place and the ramp. On the ramp when the crystal raises it, it
 *                   slides over the curb into the trench, onto the floor switch, and stays there.
 *   ABYSS_RAMP      Raised by the crystal for a few seconds, then lowered (the crystal goes out again).
 *   ABYSS_BARS      Open while the floor switch (Obj_Switch, held) is pressed.
 *   ABYSS_DOOR      Opens once the Hookshot's chest has been opened.
 *   ABYSS_EYE       A thrown stone (En_Ishi) that reaches the crystal lights it (Obj_Switch shows the flag).
 */

#include "z_en_remix_abyss.h"

#include "gfx.h"
#include "gfx_setupdl.h"
#include "array_count.h"
#include "libc/math.h"
#include "sfx.h"
#include "sys_matrix.h"
#include "z_lib.h"
#include "z_math.h"
#include "sys_math.h"
#include "audio.h"
#include "camera.h"
#include "environment.h"
#include "interface.h"
#include "item.h"
#include "message.h"
#include "pause.h"
#include "play_state.h"
#include "player.h"
#include "save.h"

#include "assets/objects/object_remix_abyss/object_remix_abyss.h"

#define FLAGS (ACTOR_FLAG_UPDATE_CULLING_DISABLED | ACTOR_FLAG_DRAW_CULLING_DISABLED)

#define KIND_PENDULUM 0
#define KIND_ORBIT 1
#define KIND_LIFT 2
#define KIND_SHUTTLE 3

#define FADE_FRAMES 5 // each way; black for as long again in between (half a second in all)

void EnRemixAbyss_Init(Actor* thisx, PlayState* play);
void EnRemixAbyss_Destroy(Actor* thisx, PlayState* play);
void EnRemixAbyss_Update(Actor* thisx, PlayState* play);
void EnRemixAbyss_Draw(Actor* thisx, PlayState* play);

ActorProfile En_Remix_Abyss_Profile = {
    /**/ ACTOR_EN_REMIX_ABYSS,
    /**/ ACTORCAT_BG,
    /**/ FLAGS,
    /**/ OBJECT_REMIX_ABYSS,
    /**/ sizeof(EnRemixAbyss),
    /**/ EnRemixAbyss_Init,
    /**/ EnRemixAbyss_Destroy,
    /**/ EnRemixAbyss_Update,
    /**/ EnRemixAbyss_Draw,
};

static AbyssPlatInfo sPlats[ABYSS_PLATS_N] = ABYSS_PLATS;
static s16 sCubeCells[2][2] = ABYSS_CUBE_CELLS;
static Gfx* sPlatDLs[ABYSS_PLATS_N] = ABYSS_PLAT_DLS;
static CollisionHeader* sPlatCols[ABYSS_PLATS_N] = ABYSS_PLAT_COLS;

static s32 sTick;  // the gauntlet's clock (game frames)
static s16 sReset; // counts the falls: platforms that broke away come back
static EnRemixAbyss* sCube;
static EnRemixAbyss* sRamp;

// ---------------------------------------------------------------- helpers

static void Abyss_Chime(void) {
    Sfx_PlaySfxCentered(NA_SE_SY_CORRECT_CHIME);
}

/** The fraction of a cycle at frame t (period in frames, negative: backwards), as a binary angle. */
static s16 Abyss_Angle(f32 period, f32 phase) {
    f32 u = (f32)sTick / period + phase;

    u -= (s32)u;
    return (s16)(s32)(u * 65536.0f);
}

/** Platform i's place (its top's centre) and yaw at the clock's frame. */
static void Abyss_PlatPos(s32 i, Vec3f* pos, s16* yaw) {
    AbyssPlatInfo* p = &sPlats[i];
    f32* m = p->m;

    *yaw = p->yaw;
    switch (p->kind) {
        case KIND_PENDULUM: {
            s16 th = (s16)(s32)(m[4] / 360.0f * 65536.0f * Math_SinS(Abyss_Angle(m[5], m[6])));
            s16 axis = (s16)(s32)(m[7] / 360.0f * 65536.0f);
            f32 s = m[3] * Math_SinS(th);

            pos->x = m[0] + s * Math_CosS(axis);
            pos->y = m[1] - m[3] * Math_CosS(th);
            pos->z = m[2] - s * Math_SinS(axis);
            break;
        }
        case KIND_ORBIT: {
            s16 a = Abyss_Angle(m[4], m[5]);

            pos->x = m[0] + m[3] * Math_SinS(a);
            pos->y = m[1];
            pos->z = m[2] + m[3] * Math_CosS(a);
            *yaw += a;
            break;
        }
        case KIND_LIFT:
            pos->x = m[0];
            pos->z = m[1];
            pos->y = (m[2] + m[3]) / 2 - (m[3] - m[2]) / 2 * Math_CosS(Abyss_Angle(m[4], m[5]));
            break;
        default: {
            f32 move = m[6];
            f32 dwell = m[7];
            f32 cyc = 2.0f * (move + dwell);
            f32 u = (f32)sTick + m[8] * cyc;
            f32 f;

            u -= (s32)(u / cyc) * cyc;
            if (u < dwell) {
                f = 0.0f;
            } else if (u < dwell + move) {
                f = (u - dwell) / move;
            } else if (u < 2.0f * dwell + move) {
                f = 1.0f;
            } else {
                f = 1.0f - (u - 2.0f * dwell - move) / move;
            }
            f = 0.5f - 0.5f * Math_CosS((s16)(s32)(f * 32768.0f)); // (eased)
            pos->x = m[0] + (m[3] - m[0]) * f;
            pos->y = m[1] + (m[4] - m[1]) * f;
            pos->z = m[2] + (m[5] - m[2]) * f;
            break;
        }
    }
}

static s32 Abyss_HasHookshot(void) {
    return (INV_CONTENT(ITEM_HOOKSHOT) == ITEM_HOOKSHOT) || (INV_CONTENT(ITEM_HOOKSHOT) == ITEM_LONGSHOT);
}

// ---------------------------------------------------------------- init / destroy

void EnRemixAbyss_Init(Actor* thisx, PlayState* play) {
    EnRemixAbyss* this = (EnRemixAbyss*)thisx;
    CollisionHeader* colHeader = NULL;
    CollisionHeader* col = NULL;
    s32 flags = DYNA_TRANSFORM_POS;

    this->type = ABYSS_TYPE(thisx->params);
    this->arg = ABYSS_ARG(thisx->params);
    thisx->home.rot.x = thisx->home.rot.z = 0;
    thisx->world.rot = thisx->shape.rot = thisx->home.rot;
    Actor_SetScale(thisx, 1.0f);
    this->reset = sReset;

    switch (this->type) {
        case ABYSS_CTRL:
            sTick = 0;
            sReset = 0;
            this->reset = 0;
            break;

        case ABYSS_PLATFORM:
            this->arg %= ABYSS_PLATS_N;
            col = sPlatCols[this->arg];
            flags = DYNA_TRANSFORM_POS | DYNA_TRANSFORM_ROT_Y;
            Abyss_PlatPos(this->arg, &thisx->world.pos, &thisx->shape.rot.y);
            thisx->world.rot.y = thisx->shape.rot.y;
            thisx->attentionRangeType = ATTENTION_RANGE_8; // (the Hookshot's reach)
            break;

        case ABYSS_RING:
            col = &gAbyssRingCol;
            flags = DYNA_TRANSFORM_POS | DYNA_TRANSFORM_ROT_Y;
            break;

        case ABYSS_CUBE:
            col = &gAbyssCubeCol;
            sCube = this;
            if (Flags_GetSwitch(play, ABYSS_FLAG_CUBE_IN)) {
                this->mode = 3; // in the trench, on the switch
                thisx->world.pos.x = ABYSS_SWITCH_X;
                thisx->world.pos.y = ABYSS_TRENCH_Y;
                thisx->world.pos.z = ABYSS_SWITCH_Z;
            } else {
                this->cell = this->target = Flags_GetSwitch(play, ABYSS_FLAG_CUBE_RAMP) ? 1 : 0;
                thisx->world.pos.x = sCubeCells[this->cell][0];
                thisx->world.pos.z = sCubeCells[this->cell][1];
            }
            break;

        case ABYSS_RAMP:
            col = &gAbyssRampCol;
            sRamp = this;
            Flags_UnsetSwitch(play, ABYSS_FLAG_RAMP); // (down whenever the room is entered)
            break;

        case ABYSS_BARS:
            col = &gAbyssBarsCol;
            break;

        case ABYSS_DOOR:
            col = &gAbyssDoorCol;
            if (Flags_GetTreasure(play, ABYSS_T_HOOK)) {
                this->offset = -ABYSS_DOOR_H - 5.0f;
                thisx->world.pos.y = thisx->home.pos.y + this->offset;
            }
            break;

        default:
            break;
    }

    if (col != NULL) {
        DynaPolyActor_Init(&this->dyna, flags);
        CollisionHeader_GetVirtual(col, &colHeader);
        this->dyna.bgId = DynaPoly_SetBgActor(play, &play->colCtx.dyna, thisx, colHeader);
        this->hasDyna = true;
    }
}

void EnRemixAbyss_Destroy(Actor* thisx, PlayState* play) {
    EnRemixAbyss* this = (EnRemixAbyss*)thisx;

    if (this->hasDyna) {
        DynaPoly_DeleteBgActor(play, &play->colCtx.dyna, this->dyna.bgId);
    }
    if (sCube == this) {
        sCube = NULL;
    }
    if (sRamp == this) {
        sRamp = NULL;
    }
    if (this->type == ABYSS_CTRL) {
        play->envCtx.fillScreen = false;
    }
}

// ---------------------------------------------------------------- the clock, falls, the Hookshot's button

static void EnRemixAbyss_Respawn(EnRemixAbyss* this, PlayState* play) {
    Player* player = GET_PLAYER(play);
    Camera* cam = GET_ACTIVE_CAM(play);

    player->actor.world.pos.x = ABYSS_RESPAWN_X;
    player->actor.world.pos.y = ABYSS_RESPAWN_Y;
    player->actor.world.pos.z = ABYSS_RESPAWN_Z;
    player->actor.prevPos = player->actor.world.pos;
    player->actor.velocity.x = player->actor.velocity.y = player->actor.velocity.z = 0.0f;
    player->actor.speed = 0.0f;
    player->actor.world.rot.y = player->actor.shape.rot.y = player->yaw = 0x8000; // facing the abyss
    player->fallStartHeight = (s16)ABYSS_RESPAWN_Y;
    player->fallDistance = 0;
    // the camera behind him at once, not flying all the way back
    cam->at = player->actor.world.pos;
    cam->at.y += 45.0f;
    cam->eye = cam->at;
    cam->eye.y += 50.0f;
    cam->eye.z += 120.0f;
    cam->eyeNext = cam->eye;
    // every platform back to the beginning of its cycle
    sTick = 0;
    sReset++;
}

static void EnRemixAbyss_UpdateCtrl(EnRemixAbyss* this, PlayState* play) {
    Player* player = GET_PLAYER(play);
    ItemEquips* eq = &gSaveContext.save.info.equips;
    s32 alpha = 0;

    sTick++;

    switch (this->mode) {
        case 0:
            if ((player->actor.world.pos.y < ABYSS_FALL_Y) && !Player_InCsMode(play) &&
                (play->transitionTrigger == TRANS_TRIGGER_OFF)) {
                this->mode = 1;
                this->timer = 0;
            }
            break;
        case 1: // to black
            alpha = 255 * ++this->timer / FADE_FRAMES;
            if (this->timer >= FADE_FRAMES) {
                EnRemixAbyss_Respawn(this, play);
                this->mode = 2;
                this->timer = 0;
            }
            break;
        case 2: // black
            alpha = 255;
            if (++this->timer >= FADE_FRAMES) {
                this->mode = 3;
                this->timer = FADE_FRAMES;
            }
            break;
        default: // back
            alpha = 255 * --this->timer / FADE_FRAMES;
            if (this->timer <= 0) {
                this->mode = 0;
            }
            break;
    }
    play->envCtx.fillScreen = (alpha > 0);
    play->envCtx.screenFillColor[0] = play->envCtx.screenFillColor[1] = play->envCtx.screenFillColor[2] = 0;
    play->envCtx.screenFillColor[3] = alpha;

    // the Hookshot onto a free C button (C-Left) as soon as he has it
    if (Abyss_HasHookshot() && (eq->buttonItems[1] != INV_CONTENT(ITEM_HOOKSHOT)) &&
        (eq->buttonItems[2] != INV_CONTENT(ITEM_HOOKSHOT)) && (eq->buttonItems[3] != INV_CONTENT(ITEM_HOOKSHOT)) &&
        (eq->buttonItems[1] == ITEM_NONE) && (play->msgCtx.msgMode == MSGMODE_NONE) && (play->pauseCtx.state == 0) &&
        !Player_InCsMode(play)) {
        eq->buttonItems[1] = INV_CONTENT(ITEM_HOOKSHOT);
        eq->cButtonSlots[0] = SLOT_HOOKSHOT;
        Interface_LoadItemIcon1(play, 1);
    }
}

// ---------------------------------------------------------------- the platforms

static void EnRemixAbyss_UpdatePlatform(EnRemixAbyss* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    AbyssPlatInfo* info = &sPlats[this->arg];
    Player* player = GET_PLAYER(play);
    Vec3f pos;
    Vec3f chest;
    s16 yaw;
    f32 dist;

    if (this->reset != sReset) {
        this->reset = sReset; // back after a fall: whole again
        if (this->mode == 3) {
            DynaPoly_EnableCollision(play, &play->colCtx.dyna, this->dyna.bgId);
        }
        this->mode = 0;
        this->offset = this->vel = 0.0f;
    }

    Abyss_PlatPos(this->arg, &pos, &yaw);

    // a cracked target: it breaks away under Link (shakes, falls, comes back a while later)
    if (info->crumble) {
        switch (this->mode) {
            case 0:
                if (DynaPolyActor_IsPlayerOnTop(&this->dyna)) {
                    this->mode = 1;
                    this->timer = 22;
                    Actor_PlaySfx(thisx, NA_SE_EV_BLOCK_SHAKE);
                }
                break;
            case 1:
                if (--this->timer <= 0) {
                    this->mode = 2;
                    this->timer = 30;
                    Actor_PlaySfx(thisx, NA_SE_EV_WALL_BROKEN);
                }
                break;
            case 2:
                this->vel += 1.5f;
                this->offset -= this->vel;
                if (--this->timer <= 0) {
                    this->mode = 3;
                    this->timer = 140;
                    DynaPoly_DisableCollision(play, &play->colCtx.dyna, this->dyna.bgId);
                }
                break;
            default:
                if (--this->timer <= 0) {
                    this->mode = 0;
                    this->offset = this->vel = 0.0f;
                    DynaPoly_EnableCollision(play, &play->colCtx.dyna, this->dyna.bgId);
                }
                break;
        }
    }

    thisx->world.pos = pos;
    thisx->world.pos.y += this->offset;
    if (this->mode == 1) {
        thisx->world.pos.x += (this->timer & 1) ? 2.0f : -2.0f; // (shaking)
    }
    thisx->shape.rot.y = thisx->world.rot.y = yaw;

    // the target: where it is, and whether the Hookshot reaches it from here (it glows, Z-targeting locks on)
    thisx->focus.pos.x = thisx->world.pos.x + info->plaqueX * Math_CosS(yaw) + (info->plaqueZ + 2) * Math_SinS(yaw);
    thisx->focus.pos.y = thisx->world.pos.y + info->plaqueY;
    thisx->focus.pos.z = thisx->world.pos.z - info->plaqueX * Math_SinS(yaw) + (info->plaqueZ + 2) * Math_CosS(yaw);
    chest = player->actor.world.pos;
    chest.y += 45.0f;
    dist = Math_Vec3f_DistXYZ(&chest, &thisx->focus.pos);
    this->inReach =
        (this->mode < 2) && LINK_IS_ADULT && Abyss_HasHookshot() && (dist < ABYSS_HOOK_RANGE) &&
        ((chest.x - thisx->focus.pos.x) * Math_SinS(yaw) + (chest.z - thisx->focus.pos.z) * Math_CosS(yaw) > 10.0f);
    if (this->inReach) {
        thisx->flags |= ACTOR_FLAG_ATTENTION_ENABLED;
    } else {
        thisx->flags &= ~ACTOR_FLAG_ATTENTION_ENABLED;
    }
}

// ---------------------------------------------------------------- the stone room

static void EnRemixAbyss_UpdateCube(EnRemixAbyss* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    Player* player = GET_PLAYER(play);

    switch (this->mode) {
        case 0: // pushed between its place and the ramp
            if (this->target == this->cell) {
                if (fabsf(this->dyna.unk_150) > 0.001f) {
                    s16 dir = this->dyna.unk_158 + ((this->dyna.unk_150 < 0.0f) ? 0x8000 : 0);
                    s32 next = 1 - this->cell;
                    s16 yaw = Math_Atan2S(sCubeCells[next][1] - sCubeCells[this->cell][1],
                                          sCubeCells[next][0] - sCubeCells[this->cell][0]);

                    this->dyna.unk_150 = 0.0f;
                    if ((ABS((s16)(yaw - dir)) < 0x2000) && ((sRamp == NULL) || (sRamp->offset == 0.0f))) {
                        this->target = next;
                    } else {
                        player->stateFlags2 &= ~PLAYER_STATE2_4; // (it won't go that way)
                    }
                }
                if ((this->cell == 1) && (sRamp != NULL) && (sRamp->offset > 0.0f)) {
                    this->mode = 1; // the ramp rises under it
                }
                break;
            }
            this->dyna.unk_150 = 0.0f;
            Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ROCK_SLIDE - SFX_FLAG);
            Math_StepToF(&thisx->world.pos.x, sCubeCells[this->target][0], 2.5f);
            Math_StepToF(&thisx->world.pos.z, sCubeCells[this->target][1], 2.5f);
            if ((thisx->world.pos.x == sCubeCells[this->target][0]) &&
                (thisx->world.pos.z == sCubeCells[this->target][1])) {
                this->cell = this->target;
                if (this->cell == 1) {
                    Flags_SetSwitch(play, ABYSS_FLAG_CUBE_RAMP);
                } else {
                    Flags_UnsetSwitch(play, ABYSS_FLAG_CUBE_RAMP);
                }
                Actor_PlaySfx(thisx, NA_SE_EV_BLOCK_BOUND);
                player->stateFlags2 &= ~PLAYER_STATE2_4;
            }
            break;

        case 1: // riding the ramp up (its top under the cube: lift + slope), then sliding off its south edge
            if (sRamp == NULL) {
                this->mode = 0;
                break;
            }
            thisx->world.pos.y = sRamp->offset + (ABYSS_RAMP_HINGE_Z - thisx->world.pos.z) * Math_SinS(sRamp->tilt);
            if (sRamp->mode == 2) { // fully raised: it slides
                thisx->world.pos.z += 6.0f;
                Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ROCK_SLIDE - SFX_FLAG);
                if (thisx->world.pos.z > ABYSS_RAMP_HINGE_Z + 20.0f) { // over the curb: falls into the trench
                    this->mode = 2;
                    this->vel = 0.0f;
                }
            } else if (sRamp->offset <= 0.0f) {
                this->mode = 0;
                thisx->world.pos.y = 0.0f;
            }
            break;

        case 2: // falling into the trench, onto the switch
            Math_StepToF(&thisx->world.pos.z, ABYSS_SWITCH_Z, 6.0f);
            this->vel += 2.0f;
            thisx->world.pos.y -= this->vel;
            if (thisx->world.pos.y <= ABYSS_TRENCH_Y) {
                thisx->world.pos.y = ABYSS_TRENCH_Y;
                thisx->world.pos.z = ABYSS_SWITCH_Z;
                this->mode = 3;
                Flags_SetSwitch(play, ABYSS_FLAG_CUBE_IN);
                Actor_PlaySfx(thisx, NA_SE_EV_STONE_BOUND);
                Abyss_Chime();
            }
            break;

        default: { // on the switch: holds it down
            CollisionPoly* poly;
            s32 bgId;
            Vec3f at = thisx->world.pos;

            at.y += 10.0f;
            BgCheck_EntityRaycastDown4(&play->colCtx, &poly, &bgId, thisx, &at);
            if (bgId != BGCHECK_SCENE) {
                DynaPolyActor* under = DynaPoly_GetActor(&play->colCtx, bgId);

                if (under != NULL) {
                    DynaPolyActor_SetActorOnTop(under);
                    DynaPolyActor_SetSwitchPressed(under);
                }
            }
            break;
        }
    }
}

static void EnRemixAbyss_UpdateRamp(EnRemixAbyss* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;

    switch (this->mode) {
        case 0: // down
            if (Flags_GetSwitch(play, ABYSS_FLAG_RAMP)) {
                this->mode = 1;
                Actor_PlaySfx(thisx, NA_SE_EV_STONE_STATUE_OPEN);
            }
            break;
        case 1: // rising: up off the floor, its north end higher
            Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ELEVATOR_MOVE - SFX_FLAG);
            Math_StepToF(&this->offset, ABYSS_RAMP_LIFT, 2.5f);
            this->tilt = (s16)(0x0C00 * this->offset / ABYSS_RAMP_LIFT);
            if (this->offset == ABYSS_RAMP_LIFT) {
                this->mode = 2;
                this->timer = 70;
                Actor_PlaySfx(thisx, NA_SE_EV_STONEDOOR_STOP);
            }
            break;
        case 2: // up for a while
            if (--this->timer <= 0) {
                this->mode = 3;
            }
            break;
        default: // down again, the crystal out
            Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ELEVATOR_MOVE - SFX_FLAG);
            Math_StepToF(&this->offset, 0.0f, 2.0f);
            this->tilt = (s16)(0x0C00 * this->offset / ABYSS_RAMP_LIFT);
            if (this->offset == 0.0f) {
                this->mode = 0;
                Flags_UnsetSwitch(play, ABYSS_FLAG_RAMP);
            }
            break;
    }
    thisx->world.pos.y = thisx->home.pos.y + this->offset;
    thisx->shape.rot.x = (s16)this->tilt;
}

static void EnRemixAbyss_UpdateEye(EnRemixAbyss* this, PlayState* play) {
    Actor* actor = play->actorCtx.actorLists[ACTORCAT_PROP].head;
    Vec3f crystal;

    if (Flags_GetSwitch(play, ABYSS_FLAG_RAMP)) {
        return;
    }
    crystal.x = ABYSS_CRYSTAL_X;
    crystal.y = ABYSS_CRYSTAL_Y;
    crystal.z = ABYSS_CRYSTAL_Z;
    for (; actor != NULL; actor = actor->next) {
        if ((actor->id == ACTOR_EN_ISHI) && (actor->parent == NULL) &&
            (Math_Vec3f_DistXYZ(&actor->world.pos, &crystal) < 50.0f)) {
            Flags_SetSwitch(play, ABYSS_FLAG_RAMP);
            Sfx_PlaySfxCentered(NA_SE_SY_TRE_BOX_APPEAR);
            break;
        }
    }
}

static void EnRemixAbyss_UpdateMover(EnRemixAbyss* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    f32 prev = this->offset;

    if (this->type == ABYSS_BARS) {
        if (Flags_GetSwitch(play, ABYSS_FLAG_BARS)) {
            Math_StepToF(&this->offset, -ABYSS_BARS_H - 5.0f, 12.0f);
        } else {
            Math_StepToF(&this->offset, 0.0f, 10.0f);
        }
    } else if (Flags_GetTreasure(play, ABYSS_T_HOOK)) {
        Math_StepToF(&this->offset, -ABYSS_DOOR_H - 5.0f, 4.0f);
    }
    if (prev != this->offset) {
        Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ELEVATOR_MOVE - SFX_FLAG);
        if ((this->offset == 0.0f) || (this->offset <= -ABYSS_BARS_H - 5.0f) ||
            (this->offset <= -ABYSS_DOOR_H - 5.0f)) {
            Actor_PlaySfx(thisx, NA_SE_EV_STONEDOOR_STOP);
        }
    }
    thisx->world.pos.y = thisx->home.pos.y + this->offset;
}

void EnRemixAbyss_Update(Actor* thisx, PlayState* play) {
    EnRemixAbyss* this = (EnRemixAbyss*)thisx;

    switch (this->type) {
        case ABYSS_CTRL:
            EnRemixAbyss_UpdateCtrl(this, play);
            break;
        case ABYSS_PLATFORM:
            EnRemixAbyss_UpdatePlatform(this, play);
            break;
        case ABYSS_RING:
            thisx->shape.rot.y = thisx->world.rot.y = Abyss_Angle((f32)ABYSS_RING_PERIOD, 0.0f);
            break;
        case ABYSS_CUBE:
            EnRemixAbyss_UpdateCube(this, play);
            break;
        case ABYSS_RAMP:
            EnRemixAbyss_UpdateRamp(this, play);
            break;
        case ABYSS_EYE:
            EnRemixAbyss_UpdateEye(this, play);
            break;
        case ABYSS_BARS:
        case ABYSS_DOOR:
            EnRemixAbyss_UpdateMover(this, play);
            break;
        default:
            break;
    }
}

// ---------------------------------------------------------------- drawing

static void Abyss_DrawOpa(PlayState* play, Gfx* dl, s32 r, s32 g, s32 b) {
    OPEN_DISPS(play->state.gfxCtx, "../z_en_remix_abyss.c", __LINE__);

    Gfx_SetupDL_25Opa(play->state.gfxCtx);
    gDPSetEnvColor(POLY_OPA_DISP++, r, g, b, 255);
    MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, play->state.gfxCtx, "../z_en_remix_abyss.c", __LINE__);
    gSPDisplayList(POLY_OPA_DISP++, dl);

    CLOSE_DISPS(play->state.gfxCtx, "../z_en_remix_abyss.c", __LINE__);
}

/** A pendulum's two chains, from the pivot down to the slab. */
static void Abyss_DrawChains(EnRemixAbyss* this, PlayState* play) {
    AbyssPlatInfo* info = &sPlats[this->arg];
    f32* m = info->m;
    s16 th = (s16)(s32)(m[4] / 360.0f * 65536.0f * Math_SinS(Abyss_Angle(m[5], m[6])));
    s32 k;

    for (k = -1; k <= 1; k += 2) {
        Matrix_Translate(m[0], m[1], m[2] + k * (info->d / 2 - 20), MTXMODE_NEW);
        Matrix_RotateZ(BINANG_TO_RAD(th), MTXMODE_APPLY);
        Matrix_Scale(1.0f, m[3] - info->plaqueY - 20.0f, 1.0f, MTXMODE_APPLY);
        Abyss_DrawOpa(play, gAbyssChainDL, 0, 0, 0);
    }
}

void EnRemixAbyss_Draw(Actor* thisx, PlayState* play) {
    EnRemixAbyss* this = (EnRemixAbyss*)thisx;

    switch (this->type) {
        case ABYSS_PLATFORM: {
            AbyssPlatInfo* info = &sPlats[this->arg];
            s32 glow = 0;

            if (this->mode == 3) {
                break; // (broken away)
            }
            Abyss_DrawOpa(play, sPlatDLs[this->arg], 0, 0, 0);
            if (this->inReach) {
                glow = 70 + (s32)(40.0f * Math_SinS((s16)(play->gameplayFrames * 0x1200)));
            }
            Matrix_Push();
            Matrix_Translate(info->plaqueX, info->plaqueY, info->plaqueZ + 1.0f, MTXMODE_APPLY);
            Abyss_DrawOpa(play, info->crumble ? gAbyssCrackedDL : gAbyssTargetDL, glow, glow * 4 / 5, glow / 4);
            Matrix_Pop();
            if (info->kind == KIND_PENDULUM) {
                Abyss_DrawChains(this, play);
            }
            break;
        }
        case ABYSS_RING:
            Abyss_DrawOpa(play, gAbyssRingDL, 20, 12, 0);
            break;
        case ABYSS_CUBE:
            Abyss_DrawOpa(play, gAbyssCubeDL, 0, 0, 0);
            break;
        case ABYSS_RAMP:
            Abyss_DrawOpa(play, gAbyssRampDL, (this->offset > 0.0f) ? 40 : 0, (this->offset > 0.0f) ? 30 : 0, 0);
            break;
        case ABYSS_BARS:
            Abyss_DrawOpa(play, gAbyssBarsDL, 0, 0, 0);
            break;
        case ABYSS_DOOR:
            Abyss_DrawOpa(play, gAbyssDoorDL, 0, 0, 0);
            break;
        default:
            break;
    }
}
