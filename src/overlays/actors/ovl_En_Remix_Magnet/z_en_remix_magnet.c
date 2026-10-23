/*
 * File: z_en_remix_magnet.c
 * Overlay: ovl_En_Remix_Magnet
 * Description: Web Remix level 4, the Lodestone Shrine: Magnesis (a Breath of the Wild rune) and the shrine's moving
 *              pieces (object_remix_magnet, tools/remix/make_magnet_parts.py).
 *
 *   MAGNET_CONTROLLER  Magnesis. Once the chest with its treasure flag is open, hold L to grab the iron piece (or the
 *                      iron chest) Link faces: it hangs in the air while L is held. The Control Stick swings it around
 *                      Link and pushes it away or pulls it in, C-Up/C-Down lift and lower it, C-Left/C-Right turn
 *                      it. Let go of L to drop it, or press B to fling it. Link stands still meanwhile: this actor
 *                      updates before the player (actor category BG) and takes the buttons it uses off the input.
 *   MAGNET_CRATE, MAGNET_GIRDER, MAGNET_SLAB
 *                      Iron pieces. When not held they fall and rest on the highest floor under any of their sample
 *                      points (a girder rests on its two ends across a gap) and press the floor switches they rest on.
 *                      One that falls far below where it started comes back to its start.
 *   MAGNET_LIFT        Rides up and down while its switch flag is set (a floor switch held down by a crate).
 *   MAGNET_BRIDGE      Turns a quarter (carrying Link) each time one of its two switch flags changes (crystal
 *                      switches that toggle).
 */

#include "z_en_remix_magnet.h"

#include "gfx.h"
#include "gfx_setupdl.h"
#include "libu64/gfxprint.h"
#include "array_count.h"
#include "gfxalloc.h"
#include "pause.h"
#include "controller.h"
#include "libc/math.h"
#include "ichain.h"
#include "sfx.h"
#include "sys_matrix.h"
#include "z_lib.h"
#include "z_math.h"
#include "audio.h"
#include "message.h"
#include "play_state.h"
#include "player.h"

#include "assets/objects/object_remix_magnet/object_remix_magnet.h"

#define FLAGS (ACTOR_FLAG_UPDATE_CULLING_DISABLED | ACTOR_FLAG_DRAW_CULLING_DISABLED)

#define MAGNESIS_RANGE 650.0f
#define MAGNESIS_MIN_DIST 70.0f
#define MAGNESIS_FOV 0x2C00
#define MAGNESIS_MOVE 12.0f
#define MAGNESIS_SFX NA_SE_EV_ELEVATOR_MOVE

void EnRemixMagnet_Init(Actor* thisx, PlayState* play);
void EnRemixMagnet_Destroy(Actor* thisx, PlayState* play);
void EnRemixMagnet_Update(Actor* thisx, PlayState* play);
void EnRemixMagnet_Draw(Actor* thisx, PlayState* play);

ActorProfile En_Remix_Magnet_Profile = {
    /**/ ACTOR_EN_REMIX_MAGNET,
    /**/ ACTORCAT_BG,
    /**/ FLAGS,
    /**/ OBJECT_REMIX_MAGNET,
    /**/ sizeof(EnRemixMagnet),
    /**/ EnRemixMagnet_Init,
    /**/ EnRemixMagnet_Destroy,
    /**/ EnRemixMagnet_Update,
    /**/ EnRemixMagnet_Draw,
};

static CollisionHeader* sCollision[] = {
    NULL, &gMagnetCrateCol, &gMagnetGirderCol, &gMagnetSlabCol, &gMagnetLiftCol, &gMagnetBridgeCol,
};

static Gfx* sDisplayLists[] = {
    NULL, gMagnetCrateDL, gMagnetGirderDL, gMagnetSlabDL, gMagnetLiftDL, gMagnetBridgeDL,
};

static f32 sHeights[] = {
    0.0f, MAGNET_CRATE_SIZE, MAGNET_GIRDER_HEIGHT, MAGNET_SLAB_HEIGHT, 0.0f, 0.0f,
};

static s32 EnRemixMagnet_IsMagnetic(Actor* actor) {
    if (actor->id == ACTOR_EN_REMIX_MAGNET) {
        s32 type = ((EnRemixMagnet*)actor)->type;

        return (type == MAGNET_CRATE) || (type == MAGNET_GIRDER) || (type == MAGNET_SLAB);
    }
    return false;
}

void EnRemixMagnet_Init(Actor* thisx, PlayState* play) {
    EnRemixMagnet* this = (EnRemixMagnet*)thisx;
    CollisionHeader* colHeader = NULL;

    this->type = MAGNET_TYPE(thisx->params);
    if (this->type > MAGNET_BRIDGE) {
        this->type = MAGNET_CRATE;
    }
    this->extra = thisx->home.rot.z;
    thisx->home.rot.x = thisx->home.rot.z = 0;
    thisx->world.rot = thisx->shape.rot = thisx->home.rot;
    Actor_SetScale(thisx, 1.0f);
    this->targetYaw = thisx->shape.rot.y;
    this->resting = false;
    this->target = this->aim = this->falling = NULL;

    if (this->type == MAGNET_CONTROLLER) {
        return; // (no collision: it only draws the beam and the hint)
    }

    DynaPolyActor_Init(&this->dyna, (this->type == MAGNET_BRIDGE) ? (DYNA_TRANSFORM_POS | DYNA_TRANSFORM_ROT_Y)
                                                                  : DYNA_TRANSFORM_POS);
    CollisionHeader_GetVirtual(sCollision[this->type], &colHeader);
    this->dyna.bgId = DynaPoly_SetBgActor(play, &play->colCtx.dyna, thisx, colHeader);

    if (this->type == MAGNET_BRIDGE) {
        this->switchState[0] = Flags_GetSwitch(play, MAGNET_FLAG(thisx->params));
        this->switchState[1] = Flags_GetSwitch(play, this->extra);
    }
}

void EnRemixMagnet_Destroy(Actor* thisx, PlayState* play) {
    EnRemixMagnet* this = (EnRemixMagnet*)thisx;

    if (this->type != MAGNET_CONTROLLER) {
        DynaPoly_DeleteBgActor(play, &play->colCtx.dyna, this->dyna.bgId);
    }
}

// ---------------------------------------------------------------- floors under the iron pieces

/**
 * The highest floor under the piece's sample points (not counting the piece itself), checked from `above` units over
 * its bottom. With `press`, the floor switches (and other dynapoly actors) it rests on are told so.
 */
static f32 EnRemixMagnet_Floor(EnRemixMagnet* this, PlayState* play, Vec3f* at, f32 above, s32 press) {
    Actor* thisx = &this->dyna.actor;
    f32 offsets[MAGNET_SAMPLES][2];
    f32 floors[MAGNET_SAMPLES];
    s32 bgIds[MAGNET_SAMPLES];
    CollisionPoly* poly;
    f32 sin = Math_SinS(thisx->shape.rot.y);
    f32 cos = Math_CosS(thisx->shape.rot.y);
    f32 best = BGCHECK_Y_MIN;
    f32 h;
    s32 n;
    s32 i;

    if (this->type == MAGNET_CRATE) {
        h = MAGNET_CRATE_SIZE / 2 - 8;
        offsets[0][0] = 0.0f, offsets[0][1] = 0.0f;
        offsets[1][0] = h, offsets[1][1] = h;
        offsets[2][0] = -h, offsets[2][1] = h;
        offsets[3][0] = h, offsets[3][1] = -h;
        offsets[4][0] = -h, offsets[4][1] = -h;
    } else {
        // along the piece's length (local x): a girder bridges a gap on its two ends
        h = ((this->type == MAGNET_GIRDER) ? MAGNET_GIRDER_LENGTH : MAGNET_SLAB_WIDTH) / 2 - 15;
        for (i = 0; i < MAGNET_SAMPLES; i++) {
            offsets[i][0] = h * (i - (MAGNET_SAMPLES / 2)) / (MAGNET_SAMPLES / 2);
            offsets[i][1] = 0.0f;
        }
    }
    n = MAGNET_SAMPLES;

    for (i = 0; i < n; i++) {
        Vec3f pos;

        // local (x, z) turned by the yaw: x' = x cos + z sin, z' = -x sin + z cos
        pos.x = at->x + offsets[i][0] * cos + offsets[i][1] * sin;
        pos.z = at->z - offsets[i][0] * sin + offsets[i][1] * cos;
        pos.y = at->y + above;
        floors[i] = BgCheck_EntityRaycastDown4(&play->colCtx, &poly, &bgIds[i], thisx, &pos);
        if (floors[i] > best) {
            best = floors[i];
        }
    }

    if (press) {
        for (i = 0; i < n; i++) {
            if ((floors[i] > best - 3.0f) && (bgIds[i] != BGCHECK_SCENE)) {
                DynaPolyActor* under = DynaPoly_GetActor(&play->colCtx, bgIds[i]);

                if (under != NULL) {
                    DynaPolyActor_SetActorOnTop(under);
                    DynaPolyActor_SetSwitchPressed(under);
                }
            }
        }
    }
    return best;
}

static void EnRemixMagnet_Respawn(EnRemixMagnet* this) {
    Actor* thisx = &this->dyna.actor;

    thisx->world.pos = thisx->home.pos;
    thisx->world.pos.y += 60.0f;
    thisx->shape.rot.y = thisx->world.rot.y = thisx->home.rot.y;
    this->vel.x = this->vel.y = this->vel.z = 0.0f;
    this->resting = false;
    Actor_PlaySfx(thisx, NA_SE_SY_TRE_BOX_APPEAR);
}

/** Move horizontally unless a wall is in the way (a line through the piece's middle). */
static s32 EnRemixMagnet_MoveXZ(Actor* actor, PlayState* play, f32 dx, f32 dz, f32 midHeight) {
    Vec3f from;
    Vec3f to;
    Vec3f hit;
    CollisionPoly* poly;
    s32 bgId;

    if ((dx == 0.0f) && (dz == 0.0f)) {
        return true;
    }
    from = actor->world.pos;
    from.y += midHeight;
    to.x = from.x + dx + ((dx > 0.0f) ? 10.0f : (dx < 0.0f) ? -10.0f : 0.0f);
    to.y = from.y;
    to.z = from.z + dz + ((dz > 0.0f) ? 10.0f : (dz < 0.0f) ? -10.0f : 0.0f);
    if (BgCheck_EntityLineTest2(&play->colCtx, &from, &to, &hit, &poly, true, false, false, true, &bgId, actor)) {
        return false;
    }
    actor->world.pos.x += dx;
    actor->world.pos.z += dz;
    return true;
}

static void EnRemixMagnet_UpdatePiece(EnRemixMagnet* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    f32 floor;

    if (this->held) {
        this->resting = false;
        this->vel.x = this->vel.y = this->vel.z = 0.0f;
        return;
    }

    floor = EnRemixMagnet_Floor(this, play, &thisx->world.pos, 40.0f, this->resting);
    if (this->resting) {
        if (floor < thisx->world.pos.y - 2.0f) {
            this->resting = false; // what it stood on moved away
        } else {
            thisx->world.pos.y = floor; // rides what it stands on up and down
        }
    }
    if (!this->resting) {
        this->vel.y = CLAMP_MIN(this->vel.y - 1.5f, -25.0f);
        if (!EnRemixMagnet_MoveXZ(thisx, play, this->vel.x, this->vel.z, sHeights[this->type] / 2)) {
            this->vel.x = this->vel.z = 0.0f;
        }
        this->vel.x *= 0.98f;
        this->vel.z *= 0.98f;
        thisx->world.pos.y += this->vel.y;
        if (thisx->world.pos.y <= floor) {
            thisx->world.pos.y = floor;
            if (this->vel.y < -6.0f) {
                Actor_PlaySfx(thisx, NA_SE_EV_BLOCK_BOUND);
            }
            this->vel.x = this->vel.y = this->vel.z = 0.0f;
            this->resting = true;
        }
        if (thisx->world.pos.y < thisx->home.pos.y - 450.0f) {
            EnRemixMagnet_Respawn(this); // fell into the chasm
        }
    }
}

// ---------------------------------------------------------------- the powered pieces

static void EnRemixMagnet_UpdateLift(EnRemixMagnet* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    f32 rise = this->extra;
    s32 on = Flags_GetSwitch(play, MAGNET_FLAG(thisx->params));
    f32 prev = this->lift;

    if (this->liftWait > 0) {
        this->liftWait--;
    } else if (on) {
        // up, wait at the top, down, wait at the bottom, ... while the switch is held
        if (this->timer == 0) {
            if (Math_StepToF(&this->lift, rise, 3.0f)) {
                this->timer = 1;
                this->liftWait = 70;
                Actor_PlaySfx(thisx, NA_SE_EV_ELEVATOR_STOP);
            }
        } else if (Math_StepToF(&this->lift, 0.0f, 3.0f)) {
            this->timer = 0;
            this->liftWait = 50;
            Actor_PlaySfx(thisx, NA_SE_EV_ELEVATOR_STOP);
        }
    } else if (this->lift > 0.0f) {
        this->timer = 1;
        if (Math_StepToF(&this->lift, 0.0f, 3.0f)) {
            this->timer = 0;
            Actor_PlaySfx(thisx, NA_SE_EV_ELEVATOR_STOP);
        }
    }
    if (this->lift != prev) {
        Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ELEVATOR_MOVE3 - SFX_FLAG);
    }
    thisx->world.pos.y = thisx->home.pos.y + this->lift;
}

static void EnRemixMagnet_UpdateBridge(EnRemixMagnet* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    s32 flags[2];
    s32 i;

    flags[0] = MAGNET_FLAG(thisx->params);
    flags[1] = this->extra;
    for (i = 0; i < 2; i++) {
        u8 now = Flags_GetSwitch(play, flags[i]) ? 1 : 0;

        if (now != this->switchState[i]) {
            this->switchState[i] = now;
            this->targetYaw += 0x4000;
            Actor_PlaySfx(thisx, NA_SE_EV_STONE_STATUE_OPEN);
        }
    }
    if (thisx->shape.rot.y != this->targetYaw) {
        Math_ScaledStepToS(&thisx->shape.rot.y, this->targetYaw, 0x140);
        Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ROLL_STAND_2 - SFX_FLAG);
        if (thisx->shape.rot.y == this->targetYaw) {
            Actor_PlaySfx(thisx, NA_SE_EV_STONEDOOR_STOP);
        }
    }
    thisx->world.rot.y = thisx->shape.rot.y;
}

// ---------------------------------------------------------------- Magnesis

static s32 EnRemixMagnet_IsLiftableChest(EnRemixMagnet* this, Actor* actor) {
    return (actor->id == ACTOR_EN_BOX) && (this->extra != 0) && ((actor->params & 0x1F) == this->extra);
}

static f32 EnRemixMagnet_TargetHeight(Actor* actor) {
    return (actor->id == ACTOR_EN_REMIX_MAGNET) ? sHeights[((EnRemixMagnet*)actor)->type] : 40.0f;
}

/** The iron piece (or iron chest) Link faces, nearest first, within reach. */
static Actor* EnRemixMagnet_FindTarget(EnRemixMagnet* this, PlayState* play, Player* player) {
    static u8 sCategories[] = { ACTORCAT_BG, ACTORCAT_CHEST };
    Actor* best = NULL;
    f32 bestScore = 1e9f;
    s32 c;

    for (c = 0; c < ARRAY_COUNT(sCategories); c++) {
        Actor* actor = play->actorCtx.actorLists[sCategories[c]].head;

        for (; actor != NULL; actor = actor->next) {
            f32 dist;
            s16 dyaw;
            f32 score;

            if (!EnRemixMagnet_IsMagnetic(actor) && !EnRemixMagnet_IsLiftableChest(this, actor)) {
                continue;
            }
            dist = Math_Vec3f_DistXZ(&player->actor.world.pos, &actor->world.pos);
            if ((dist > MAGNESIS_RANGE) || (fabsf(actor->world.pos.y - player->actor.world.pos.y) > 600.0f)) {
                continue;
            }
            dyaw = Math_Vec3f_Yaw(&player->actor.world.pos, &actor->world.pos) - player->actor.shape.rot.y;
            if ((dist > 60.0f) && (ABS(dyaw) > MAGNESIS_FOV)) {
                continue;
            }
            score = dist * (1.0f + ABS(dyaw) / (f32)MAGNESIS_FOV);
            if (score < bestScore) {
                bestScore = score;
                best = actor;
            }
        }
    }
    return best;
}

static void EnRemixMagnet_Release(EnRemixMagnet* this, s32 fling) {
    Actor* target = this->target;
    Vec3f vel;

    vel.x = vel.y = vel.z = 0.0f;
    if (fling) {
        vel.x = Math_SinS(this->holdYaw) * 16.0f;
        vel.z = Math_CosS(this->holdYaw) * 16.0f;
        vel.y = 8.0f;
        Actor_PlaySfx(target, NA_SE_EV_HEAVY_THROW);
    }
    if (target->id == ACTOR_EN_REMIX_MAGNET) {
        EnRemixMagnet* piece = (EnRemixMagnet*)target;

        piece->held = false;
        piece->resting = false;
        piece->vel = vel;
    } else {
        this->falling = target; // a chest: this actor drops it (see EnRemixMagnet_UpdateFallingChest)
        this->vel = vel;
    }
    this->target = NULL;
}

static void EnRemixMagnet_UpdateFallingChest(EnRemixMagnet* this, PlayState* play) {
    Actor* chest = this->falling;
    CollisionPoly* poly;
    s32 bgId;
    Vec3f pos;
    f32 floor;

    if ((chest == NULL) || (chest->update == NULL)) {
        this->falling = NULL;
        return;
    }
    pos = chest->world.pos;
    pos.y += 40.0f;
    floor = BgCheck_EntityRaycastDown4(&play->colCtx, &poly, &bgId, chest, &pos);
    this->vel.y = CLAMP_MIN(this->vel.y - 1.5f, -25.0f);
    if (!EnRemixMagnet_MoveXZ(chest, play, this->vel.x, this->vel.z, 30.0f)) {
        this->vel.x = this->vel.z = 0.0f;
    }
    chest->world.pos.y += this->vel.y;
    if (chest->world.pos.y <= floor) {
        chest->world.pos.y = floor;
        Actor_PlaySfx(chest, NA_SE_EV_BLOCK_BOUND);
        this->falling = NULL;
    } else if (chest->world.pos.y < chest->home.pos.y - 800.0f) {
        chest->world.pos = chest->home.pos;
        this->falling = NULL;
    }
}

/** Link can use Magnesis: standing on the ground, free (not talking, carrying, climbing, swimming, in a cutscene). */
static s32 EnRemixMagnet_CanUse(PlayState* play, Player* player) {
    if (!(player->actor.bgCheckFlags & BGCHECKFLAG_GROUND) || Player_InCsMode(play) ||
        (play->msgCtx.msgMode != MSGMODE_NONE) || (play->pauseCtx.state != 0)) {
        return false;
    }
    if (player->stateFlags1 &
        (PLAYER_STATE1_TALKING | PLAYER_STATE1_DEAD | PLAYER_STATE1_10 | PLAYER_STATE1_CARRYING_ACTOR |
         PLAYER_STATE1_13 | PLAYER_STATE1_14 | PLAYER_STATE1_21 | PLAYER_STATE1_27 | PLAYER_STATE1_29)) {
        return false;
    }
    return true;
}

static void EnRemixMagnet_Hold(EnRemixMagnet* this, PlayState* play, Player* player, Input* input) {
    Actor* target = this->target;
    f32 height = EnRemixMagnet_TargetHeight(target);
    Vec3f goal;
    Vec3f prev = target->world.pos;
    f32 floor;
    s32 stickX = input->rel.stick_x;
    s32 stickY = input->rel.stick_y;

    // the stick swings the piece around Link (left/right) and pushes it away or pulls it in (up/down)
    this->holdYaw -= stickX * 0x18;
    this->holdDist = CLAMP(this->holdDist + stickY * 0.09f, MAGNESIS_MIN_DIST, MAGNESIS_RANGE);
    if (CHECK_BTN_ALL(input->cur.button, BTN_CUP)) {
        this->holdHeight = CLAMP_MAX(this->holdHeight + 4.5f, 520.0f);
    }
    if (CHECK_BTN_ALL(input->cur.button, BTN_CDOWN)) {
        this->holdHeight = CLAMP_MIN(this->holdHeight - 4.5f, -300.0f);
    }
    if (CHECK_BTN_ALL(input->cur.button, BTN_CLEFT)) {
        target->shape.rot.y += 0x200;
    }
    if (CHECK_BTN_ALL(input->cur.button, BTN_CRIGHT)) {
        target->shape.rot.y -= 0x200;
    }
    target->world.rot.y = target->shape.rot.y;

    goal.x = player->actor.world.pos.x + Math_SinS(this->holdYaw) * this->holdDist;
    goal.z = player->actor.world.pos.z + Math_CosS(this->holdYaw) * this->holdDist;
    goal.y = player->actor.world.pos.y + this->holdHeight;

    // move towards the goal, but not through walls nor into the floor
    if (!EnRemixMagnet_MoveXZ(target, play, CLAMP(goal.x - prev.x, -MAGNESIS_MOVE, MAGNESIS_MOVE),
                              CLAMP(goal.z - prev.z, -MAGNESIS_MOVE, MAGNESIS_MOVE), height / 2)) {
        // blocked: hold it where it is
        this->holdDist =
            CLAMP(Math_Vec3f_DistXZ(&player->actor.world.pos, &target->world.pos), MAGNESIS_MIN_DIST, MAGNESIS_RANGE);
        this->holdYaw = Math_Vec3f_Yaw(&player->actor.world.pos, &target->world.pos);
    }
    target->world.pos.y += CLAMP(goal.y - prev.y, -MAGNESIS_MOVE, MAGNESIS_MOVE);
    if (target->id == ACTOR_EN_REMIX_MAGNET) {
        floor = EnRemixMagnet_Floor((EnRemixMagnet*)target, play, &target->world.pos, 40.0f, false);
    } else {
        CollisionPoly* poly;
        s32 bgId;
        Vec3f pos = target->world.pos;

        pos.y += 40.0f;
        floor = BgCheck_EntityRaycastDown4(&play->colCtx, &poly, &bgId, target, &pos);
    }
    if (target->world.pos.y < floor) {
        target->world.pos.y = floor;
        this->holdHeight = floor - player->actor.world.pos.y;
    }

    // Link faces what he holds, and stands still
    player->actor.shape.rot.y = player->actor.world.rot.y = player->yaw =
        Math_Vec3f_Yaw(&player->actor.world.pos, &target->world.pos);
    if ((prev.x != target->world.pos.x) || (prev.y != target->world.pos.y) || (prev.z != target->world.pos.z)) {
        Actor_PlaySfx_Flagged(target, MAGNESIS_SFX - SFX_FLAG);
    }
}

static void EnRemixMagnet_UpdateController(EnRemixMagnet* this, PlayState* play) {
    Player* player = GET_PLAYER(play);
    Input* input = &play->state.input[0];
    Actor* actor;

    EnRemixMagnet_UpdateFallingChest(this, play);

    this->hasMagnesis = Flags_GetTreasure(play, MAGNET_FLAG(this->dyna.actor.params));
    if (this->aim != NULL && this->aim->id == ACTOR_EN_REMIX_MAGNET) {
        ((EnRemixMagnet*)this->aim)->aimed = false;
    }
    this->aim = NULL;
    if (!this->hasMagnesis) {
        return;
    }

    if (this->target != NULL) {
        if ((this->target->update == NULL) || !EnRemixMagnet_CanUse(play, player) ||
            !CHECK_BTN_ALL(input->cur.button, BTN_L) ||
            ((this->target->id == ACTOR_EN_REMIX_MAGNET) &&
             DynaPolyActor_IsPlayerOnTop(&((EnRemixMagnet*)this->target)->dyna))) {
            EnRemixMagnet_Release(this, false);
        } else if (CHECK_BTN_ALL(input->press.button, BTN_B)) {
            EnRemixMagnet_Release(this, true);
        } else {
            EnRemixMagnet_Hold(this, play, player, input);
        }
    } else if (EnRemixMagnet_CanUse(play, player)) {
        actor = EnRemixMagnet_FindTarget(this, play, player);
        this->aim = actor;
        if (actor != NULL) {
            if (actor->id == ACTOR_EN_REMIX_MAGNET) {
                ((EnRemixMagnet*)actor)->aimed = true;
            }
            if (CHECK_BTN_ALL(input->press.button, BTN_L) && (actor != this->falling)) {
                this->target = actor;
                this->holdYaw = Math_Vec3f_Yaw(&player->actor.world.pos, &actor->world.pos);
                this->holdDist = CLAMP(Math_Vec3f_DistXZ(&player->actor.world.pos, &actor->world.pos),
                                       MAGNESIS_MIN_DIST, MAGNESIS_RANGE);
                // lift it off the floor a little straight away
                this->holdHeight = actor->world.pos.y - player->actor.world.pos.y + 25.0f;
                if (actor->id == ACTOR_EN_REMIX_MAGNET) {
                    ((EnRemixMagnet*)actor)->held = true;
                }
                Actor_PlaySfx(actor, NA_SE_EV_TRIFORCE_FLASH);
            }
        }
    }

    if (this->target != NULL) {
        // Link stands still while he holds something: the player reads this input after this actor's update
        u16 mask = BTN_A | BTN_B | BTN_Z | BTN_R | BTN_CUP | BTN_CDOWN | BTN_CLEFT | BTN_CRIGHT;

        input->cur.button &= ~mask;
        input->press.button &= ~mask;
        input->rel.button &= ~mask;
        input->cur.stick_x = input->cur.stick_y = 0;
        input->rel.stick_x = input->rel.stick_y = 0;
    }
}

void EnRemixMagnet_Update(Actor* thisx, PlayState* play) {
    EnRemixMagnet* this = (EnRemixMagnet*)thisx;

    this->timer += (this->type == MAGNET_LIFT) ? 0 : 1;
    switch (this->type) {
        case MAGNET_CONTROLLER:
            EnRemixMagnet_UpdateController(this, play);
            break;
        case MAGNET_LIFT:
            EnRemixMagnet_UpdateLift(this, play);
            break;
        case MAGNET_BRIDGE:
            EnRemixMagnet_UpdateBridge(this, play);
            break;
        default:
            EnRemixMagnet_UpdatePiece(this, play);
            break;
    }
}

// ---------------------------------------------------------------- drawing

static void EnRemixMagnet_DrawHint(EnRemixMagnet* this, PlayState* play) {
    GraphicsContext* gfxCtx = play->state.gfxCtx;
    GfxPrint printer;
    Gfx* gfx;
    Gfx* gfxRef;

    OPEN_DISPS(gfxCtx, "../z_en_remix_magnet.c", __LINE__);

    gfxRef = POLY_OPA_DISP;
    gfx = Gfx_Open(gfxRef);
    gSPDisplayList(OVERLAY_DISP++, gfx);
    GfxPrint_Init(&printer);
    GfxPrint_Open(&printer, gfx);
    GfxPrint_SetColor(&printer, 255, 120, 230, 255);
    if (this->target != NULL) {
        GfxPrint_SetPos(&printer, 3, 22);
        GfxPrint_Printf(&printer, "MAGNESIS  Stick:Move  C-Up/Down:Lift");
        GfxPrint_SetPos(&printer, 3, 23);
        GfxPrint_Printf(&printer, "C-Left/Right:Turn  B:Fling  L:Drop");
    } else {
        GfxPrint_SetPos(&printer, 3, 23);
        GfxPrint_Printf(&printer, "Hold L: Magnesis");
    }
    gfx = GfxPrint_Close(&printer);
    GfxPrint_Destroy(&printer);
    gSPEndDisplayList(gfx++);
    Gfx_Close(gfxRef, gfx);
    POLY_OPA_DISP = gfx;

    CLOSE_DISPS(gfxCtx, "../z_en_remix_magnet.c", __LINE__);
}

static void EnRemixMagnet_DrawBeam(EnRemixMagnet* this, PlayState* play, Player* player) {
    Actor* target = this->target;
    Vec3f from;
    Vec3f to;
    f32 dist;
    f32 width;
    s32 k;

    from = player->leftHandPos;
    to = target->world.pos;
    to.y += EnRemixMagnet_TargetHeight(target) / 2;
    dist = Math_Vec3f_DistXYZ(&from, &to);
    if (dist < 1.0f) {
        return;
    }

    OPEN_DISPS(play->state.gfxCtx, "../z_en_remix_magnet.c", __LINE__);

    Gfx_SetupDL_25Xlu(play->state.gfxCtx);
    for (k = 0; k < 2; k++) {
        width = (k == 0) ? (0.9f + 0.3f * Math_SinS(this->timer * 0x1800))
                         : (2.2f + 0.6f * Math_SinS(this->timer * 0x1100));
        Matrix_Translate(from.x, from.y, from.z, MTXMODE_NEW);
        Matrix_RotateY(BINANG_TO_RAD(Math_Vec3f_Yaw(&from, &to)), MTXMODE_APPLY);
        Matrix_RotateX(BINANG_TO_RAD(Math_Vec3f_Pitch(&from, &to)), MTXMODE_APPLY);
        Matrix_Scale(width, width, dist / MAGNET_BEAM_LENGTH, MTXMODE_APPLY);
        gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, 255, (k == 0) ? 200 : 70, 240, (k == 0) ? 200 : 90);
        MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, play->state.gfxCtx, "../z_en_remix_magnet.c", __LINE__);
        gSPDisplayList(POLY_XLU_DISP++, gMagnetBeamDL);
    }

    CLOSE_DISPS(play->state.gfxCtx, "../z_en_remix_magnet.c", __LINE__);
}

void EnRemixMagnet_Draw(Actor* thisx, PlayState* play) {
    EnRemixMagnet* this = (EnRemixMagnet*)thisx;
    s32 glow = 0;
    s32 r = 255;
    s32 g = 50;
    s32 b = 200;

    if (this->type == MAGNET_CONTROLLER) {
        Player* player = GET_PLAYER(play);

        if (this->target != NULL) {
            EnRemixMagnet_DrawBeam(this, play, player);
        }
        if (this->hasMagnesis && ((this->target != NULL) || (this->aim != NULL)) &&
            (play->msgCtx.msgMode == MSGMODE_NONE) && (play->pauseCtx.state == 0)) {
            EnRemixMagnet_DrawHint(this, play);
        }
        return;
    }

    if (this->held) {
        glow = 95 + (s32)(35.0f * Math_SinS(this->timer * 0x1400));
    } else if (this->aimed) {
        glow = 45 + (s32)(25.0f * Math_SinS(this->timer * 0xC00));
    } else if ((this->type == MAGNET_LIFT) && Flags_GetSwitch(play, MAGNET_FLAG(thisx->params))) {
        glow = 40 + (s32)(25.0f * Math_SinS(this->timer * 0x800));
        r = 255, g = 140, b = 30;
    } else if ((this->type == MAGNET_BRIDGE) && (thisx->shape.rot.y != this->targetYaw)) {
        glow = 70;
        r = 255, g = 140, b = 30;
    }
    if (this->type == MAGNET_LIFT) {
        this->timer++;
    }

    OPEN_DISPS(play->state.gfxCtx, "../z_en_remix_magnet.c", __LINE__);

    Gfx_SetupDL_25Opa(play->state.gfxCtx);
    gDPSetEnvColor(POLY_OPA_DISP++, r * glow / 255, g * glow / 255, b * glow / 255, 255);
    MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, play->state.gfxCtx, "../z_en_remix_magnet.c", __LINE__);
    gSPDisplayList(POLY_OPA_DISP++, sDisplayLists[this->type]);

    CLOSE_DISPS(play->state.gfxCtx, "../z_en_remix_magnet.c", __LINE__);
}
