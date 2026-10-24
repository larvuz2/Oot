/*
 * File: z_en_remix_years.c
 * Overlay: ovl_En_Remix_Years
 * Description: Web Remix level 7, the Shrine of Seven Years. The Master Sword's pedestal is the only place time
 *              turns: place the sword and Link is a child seven years ago, draw it and he is an adult again (the
 *              Temple of Time's play->linkAgeOnLoad). The room is the same room in both: what the child moves stays
 *              where he left it, and seven years age it naturally (a sapling grows into a tree, stairs without
 *              their support fall, a wall crumbles into rubble, roots seal a crack). The pieces are
 *              object_remix_years (tools/remix/make_years_parts.py, which also writes the plan this file reads:
 *              YEARS_* in object_remix_years.h); the room is tools/remix/make_years.py.
 *
 *   YEARS_PEDESTAL  Talk to it (A): the sword goes in (adult) or comes out (child), and the room comes back seven
 *                   years away, Link standing before the pedestal (spawn 1 / 2). Leaving the shrine any other way, he
 *                   leaves at the age he came in.
 *   YEARS_PUSH      A block that moves between marked places when pushed, kept in switch flags. The cube: pushed
 *                   by both ages (a stone block stays a stone block). The planter: pushed by the child; seven years
 *                   later a tree stands there, its branch towards wherever the planter was turned (climb its ivy). The
 *                   support: pushed by the child; under the final staircase it keeps the stairs whole.
 *   YEARS_ERA       The garden's wall with a child's doorway (past) / the rubble it fell into (future); the east
 *                   stairs (past) / their ruin; the cracked wall of the secret alcove (past) / the roots sealing it,
 *                   pushed aside by the adult (future); the final staircase, whole in the past, broken in the future
 *                   unless the support stands under it.
 *   YEARS_NARROW    An opening too small for the adult: a block only he collides with.
 *   YEARS_CARRY     The golden medallion and the loose stone (the child lifts and carries them). With the stone
 *                   lifted off the cavity, the medallion dropped into it stays buried there.
 *   YEARS_SECRET    In the future, the medallion's place holds a chest (spawned only if it was buried).
 *   YEARS_TABLET    Inscriptions.
 *   YEARS_DOOR      The exit door: no handle; it rises once the floor switch behind it is pressed (by the child,
 *                   through the narrow opening beside it), and stays open in both ages.
 */

#include "z_en_remix_years.h"

#include "gfx.h"
#include "gfx_setupdl.h"
#include "array_count.h"
#include "libc/math.h"
#include "attributes.h"
#include "sfx.h"
#include "sys_matrix.h"
#include "z_lib.h"
#include "z_math.h"
#include "sys_math.h"
#include "audio.h"
#include "message.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "scene.h"
#include "sequence.h"
#include "transition.h"
#include "item.h"
#include "remix_level.h"
#include "src/overlays/actors/ovl_En_Box/z_en_box.h"

#include "assets/objects/object_remix_years/object_remix_years.h"

#define FLAGS (ACTOR_FLAG_UPDATE_CULLING_DISABLED | ACTOR_FLAG_DRAW_CULLING_DISABLED)

#define TEXT_DRAW 0x7FA5  // the child draws the sword
#define TEXT_PLACE 0x7FA6 // the adult places it
#define TEXT_TABLET_BASE 0x7FA7

void EnRemixYears_Init(Actor* thisx, PlayState* play);
void EnRemixYears_Destroy(Actor* thisx, PlayState* play);
void EnRemixYears_Update(Actor* thisx, PlayState* play);
void EnRemixYears_Draw(Actor* thisx, PlayState* play);

ActorProfile En_Remix_Years_Profile = {
    /**/ ACTOR_EN_REMIX_YEARS,
    /**/ ACTORCAT_BG,
    /**/ FLAGS,
    /**/ OBJECT_REMIX_YEARS,
    /**/ sizeof(EnRemixYears),
    /**/ EnRemixYears_Init,
    /**/ EnRemixYears_Destroy,
    /**/ EnRemixYears_Update,
    /**/ EnRemixYears_Draw,
};

static s16 sCubeCells[YEARS_CUBE_N][2] = YEARS_CUBE_CELLS;
static s16 sPlanterCells[YEARS_PLANTER_N][2] = YEARS_PLANTER_CELLS;
static s16 sSupportCells[YEARS_SUPPORT_N][2] = YEARS_SUPPORT_CELLS;

// the loose stone (the medallion needs to know whether it has been lifted off the cavity)
static EnRemixYears* sStone;

typedef struct PushInfo {
    s16 (*cells)[2];
    s16 n;
    s16 flag;
    s16 bits;
    s16 start;
} PushInfo;

static PushInfo sPush[] = {
    { sCubeCells, YEARS_CUBE_N, YEARS_FLAG_CUBE, 3, 0 },
    { sPlanterCells, YEARS_PLANTER_N, YEARS_FLAG_PLANTER, 2, YEARS_PLANTER_START },
    { sSupportCells, YEARS_SUPPORT_N, YEARS_FLAG_SUPPORT, 2, 0 },
};

// ---------------------------------------------------------------- helpers

static s32 Years_GetBits(PlayState* play, s32 first, s32 n) {
    s32 v = 0;
    s32 i;

    for (i = 0; i < n; i++) {
        if (Flags_GetSwitch(play, first + i)) {
            v |= 1 << i;
        }
    }
    return v;
}

static void Years_SetBits(PlayState* play, s32 first, s32 n, s32 v) {
    s32 i;

    for (i = 0; i < n; i++) {
        if ((v >> i) & 1) {
            Flags_SetSwitch(play, first + i);
        } else {
            Flags_UnsetSwitch(play, first + i);
        }
    }
}

/** Where a pushed block was left. Stored as cell + 1, so a fresh save (all clear) reads as its starting place. */
static s32 Years_Cell(PlayState* play, PushInfo* info) {
    s32 v = Years_GetBits(play, info->flag, info->bits);

    return ((v == 0) || (v > info->n)) ? info->start : (v - 1);
}

static void Years_Chime(void) {
    Sfx_PlaySfxCentered(NA_SE_SY_CORRECT_CHIME);
}

// ---------------------------------------------------------------- init / destroy

void EnRemixYears_Init(Actor* thisx, PlayState* play) {
    EnRemixYears* this = (EnRemixYears*)thisx;
    CollisionHeader* colHeader = NULL;
    CollisionHeader* col = NULL;
    s16 rotZ = thisx->home.rot.z;

    this->type = YEARS_TYPE(thisx->params);
    this->arg = YEARS_ARG(thisx->params);
    this->isChild = !LINK_IS_ADULT;
    thisx->home.rot.x = thisx->home.rot.z = 0;
    thisx->world.rot = thisx->shape.rot = thisx->home.rot;
    Actor_SetScale(thisx, 1.0f);
    this->scale = 1.0f;
    this->mode = 0;

    switch (this->type) {
        case YEARS_PEDESTAL:
            col = &gYearsPedestalCol;
            thisx->flags |= ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_FRIENDLY;
            thisx->attentionRangeType = ATTENTION_RANGE_1;
            thisx->textId = this->isChild ? TEXT_DRAW : TEXT_PLACE;
            thisx->focus.pos = thisx->world.pos;
            thisx->focus.pos.y += 90.0f;
            break;

        case YEARS_PUSH: {
            PushInfo* info = &sPush[this->arg % ARRAY_COUNT(sPush)];

            this->arg %= ARRAY_COUNT(sPush);
            this->cell = this->target = Years_Cell(play, info);
            thisx->world.pos.x = info->cells[this->cell][0];
            thisx->world.pos.z = info->cells[this->cell][1];
            if ((this->arg == 1) && !this->isChild) {
                col = &gYearsTreeCol; // seven years later: a tree, its branch towards the west ledge or north
                thisx->shape.rot.y = thisx->world.rot.y = (this->cell == 0) ? 0x4000 : 0;
            } else {
                col = (this->arg == 0) ? &gYearsCubeCol : (this->arg == 1) ? &gYearsPlanterCol : &gYearsSupportCol;
            }
            break;
        }

        case YEARS_ERA:
            switch (this->arg) {
                case 0:
                    col = this->isChild ? &gYearsGardenWallCol : &gYearsRubbleCol;
                    break;
                case 1:
                    col = this->isChild ? &gYearsEastStairsCol : NULL;
                    break;
                case 2:
                    if (this->isChild) {
                        col = &gYearsCrackWallCol;
                    } else if (!Flags_GetSwitch(play, YEARS_FLAG_ROOTS)) {
                        col = &gYearsRootsCol;
                    } else {
                        this->mode = 2; // pushed aside long ago
                    }
                    break;
                default:
                    this->arg = 3;
                    // whole in the past; in the future only if the support stands under it
                    this->mode = this->isChild || (Years_Cell(play, &sPush[2]) == YEARS_SUPPORT_N - 1);
                    col = this->mode ? &gYearsStairsFullCol : &gYearsStairsBrokenCol;
                    break;
            }
            break;

        case YEARS_NARROW:
            if (this->isChild) {
                Actor_Kill(thisx); // the child fits
                return;
            }
            col = &gYearsNarrowCol;
            break;

        case YEARS_CARRY:
            if (!this->isChild) {
                Actor_Kill(thisx); // (the future: the medallion is buried, the stone overgrown)
                return;
            }
            thisx->gravity = -1.2f;
            if (this->arg == 1) {
                sStone = this;
                if (Flags_GetSwitch(play, YEARS_FLAG_MEDALLION)) {
                    thisx->world.pos.x += 45.0f; // (lifted aside when the medallion went in)
                }
            } else if (Flags_GetSwitch(play, YEARS_FLAG_MEDALLION)) {
                this->mode = 3; // buried
                thisx->world.pos.x = YEARS_CAVITY_X;
                thisx->world.pos.z = YEARS_CAVITY_Z;
                thisx->world.pos.y = thisx->home.pos.y = 0.0f;
            }
            break;

        case YEARS_SECRET:
            if (!this->isChild && Flags_GetSwitch(play, YEARS_FLAG_MEDALLION)) {
                // the medallion buried seven years ago: a chest stands where it was
                Actor_Spawn(&play->actorCtx, play, ACTOR_EN_BOX, thisx->world.pos.x, thisx->world.pos.y,
                            thisx->world.pos.z, 0, thisx->shape.rot.y, 0,
                            (ENBOX_TYPE_SMALL << 12) | (GI_HEART_PIECE << 5) | YEARS_T_SECRET);
            }
            Actor_Kill(thisx);
            return;

        case YEARS_TABLET:
            col = &gYearsTabletCol;
            thisx->flags |= ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_FRIENDLY;
            thisx->attentionRangeType = ATTENTION_RANGE_1;
            thisx->textId = TEXT_TABLET_BASE + this->arg;
            thisx->focus.pos = thisx->world.pos;
            thisx->focus.pos.y += 70.0f;
            break;

        case YEARS_DOOR:
            col = &gYearsDoorCol;
            if (Flags_GetSwitch(play, YEARS_FLAG_DOOR)) {
                this->offset = YEARS_DOOR_H;
                thisx->world.pos.y = thisx->home.pos.y + this->offset;
            }
            break;
    }
    (void)rotZ;

    if (col != NULL) {
        DynaPolyActor_Init(&this->dyna, DYNA_TRANSFORM_POS);
        CollisionHeader_GetVirtual(col, &colHeader);
        this->dyna.bgId = DynaPoly_SetBgActor(play, &play->colCtx.dyna, thisx, colHeader);
        this->hasDyna = true;
    }
}

void EnRemixYears_Destroy(Actor* thisx, PlayState* play) {
    EnRemixYears* this = (EnRemixYears*)thisx;

    if (this->hasDyna) {
        DynaPoly_DeleteBgActor(play, &play->colCtx.dyna, this->dyna.bgId);
    }
    if (sStone == this) {
        sStone = NULL;
    }
}

// ---------------------------------------------------------------- the pedestal

/**
 * The scene's first entrance (its eight entrances follow it: entrance_table.h). The pedestal stands in the Shrine of
 * Seven Years and in the Shrine of the Upside-Down Wind.
 */
static s32 EnRemixYears_FirstEntrance(PlayState* play) {
    return (play->sceneId == SCENE_REMIX_WIND) ? ENTR_REMIX_WIND_0 : ENTR_REMIX_YEARS_0;
}

static void EnRemixYears_TurnTime(EnRemixYears* this, PlayState* play) {
    play->linkAgeOnLoad = this->isChild ? LINK_AGE_ADULT : LINK_AGE_CHILD;
    // spawn 1 (child) / 2 (adult): before the pedestal
    play->nextEntranceIndex = (play->sceneId == SCENE_REMIX_WIND) ? ENTR_REMIX_WIND_1 : ENTR_REMIX_YEARS_1;
    play->transitionTrigger = TRANS_TRIGGER_START;
    play->transitionType = TRANS_TYPE_FADE_WHITE;
    gSaveContext.nextTransitionType = TRANS_TYPE_FADE_WHITE_SLOW;
    gSaveContext.showTitleCard = false;
    Sfx_PlaySfxCentered(NA_SE_SY_WHITE_OUT_T);
}

static void EnRemixYears_UpdatePedestal(EnRemixYears* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;

    if (this->timer > 0) {
        if (--this->timer == 0) {
            EnRemixYears_TurnTime(this, play);
        }
    } else if (this->talking) {
        if (Actor_TextboxIsClosing(thisx, play)) {
            this->talking = false;
            this->timer = 6;
            Actor_PlaySfx(thisx, this->isChild ? NA_SE_IT_SWORD_PICKOUT : NA_SE_IT_SWORD_PUTAWAY);
        }
    } else if (Actor_TalkOfferAccepted(thisx, play)) {
        this->talking = true;
    } else if (play->transitionTrigger == TRANS_TRIGGER_OFF) {
        Actor_OfferTalk(thisx, play, 90.0f);
    }

    // Leaving the shrine any other way: Link goes out at the age he came in
    if ((play->transitionTrigger != TRANS_TRIGGER_OFF) && (this->timer == 0) &&
        ((play->nextEntranceIndex < EnRemixYears_FirstEntrance(play)) ||
         (play->nextEntranceIndex > EnRemixYears_FirstEntrance(play) + (ENTR_REMIX_YEARS_1_3 - ENTR_REMIX_YEARS_0)))) {
        play->linkAgeOnLoad = RemixLevel_TimeEntryAge();
    }
}

// ---------------------------------------------------------------- pushed blocks

static void EnRemixYears_UpdatePush(EnRemixYears* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    Player* player = GET_PLAYER(play);
    PushInfo* info = &sPush[this->arg];
    s32 movable = this->isChild || (this->arg == 0); // the cube moves in both ages; the rest only in the past

    if (this->target == this->cell) {
        if (fabsf(this->dyna.unk_150) > 0.001f) {
            s16 dir = this->dyna.unk_158 + ((this->dyna.unk_150 < 0.0f) ? 0x8000 : 0);
            s32 k;

            this->dyna.unk_150 = 0.0f;
            if (movable) {
                for (k = -1; k <= 1; k += 2) {
                    s32 next = this->cell + k;
                    s16 yaw;

                    if ((next < 0) || (next >= info->n)) {
                        continue;
                    }
                    yaw = Math_Atan2S(info->cells[next][1] - info->cells[this->cell][1],
                                      info->cells[next][0] - info->cells[this->cell][0]);
                    if (ABS((s16)(yaw - dir)) < 0x2000) {
                        this->target = next;
                        break;
                    }
                }
            }
            if (this->target == this->cell) {
                player->stateFlags2 &= ~PLAYER_STATE2_4; // it won't go that way (or it's too heavy)
            }
        }
        return;
    }

    // sliding to the next place
    this->dyna.unk_150 = 0.0f;
    Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ROCK_SLIDE - SFX_FLAG);
    Math_StepToF(&thisx->world.pos.x, info->cells[this->target][0], 2.5f);
    Math_StepToF(&thisx->world.pos.z, info->cells[this->target][1], 2.5f);
    if ((thisx->world.pos.x == info->cells[this->target][0]) && (thisx->world.pos.z == info->cells[this->target][1])) {
        this->cell = this->target;
        Years_SetBits(play, info->flag, info->bits, this->cell + 1);
        Actor_PlaySfx(thisx, NA_SE_EV_BLOCK_BOUND);
        player->stateFlags2 &= ~PLAYER_STATE2_4;
        if ((this->arg == 2) && (this->cell == YEARS_SUPPORT_N - 1)) {
            Years_Chime(); // under the stairs: they will stand
        }
    }
}

// ---------------------------------------------------------------- carried things

static void EnRemixYears_UpdateCarry(EnRemixYears* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    Player* player = GET_PLAYER(play);

    switch (this->mode) {
        case 0: // lying somewhere: the child can lift it
            if (Actor_HasParent(thisx, play)) {
                this->mode = 1;
                Player_PlaySfx(player, NA_SE_PL_PULL_UP_POT);
                break;
            }
            if ((thisx->xzDistToPlayer < 55.0f) && (fabsf(thisx->yDistToPlayer) < 40.0f)) {
                s16 facing = thisx->yawTowardsPlayer - player->actor.world.rot.y;

                if (ABS(facing) >= 0x5556) {
                    Actor_OfferGetItem(thisx, play, GI_NONE, 40.0f, 40.0f);
                }
            }
            break;

        case 1: // carried
            if (Actor_HasNoParent(thisx, play)) {
                this->mode = 2;
                thisx->velocity.x = Math_SinS(thisx->world.rot.y) * thisx->speed;
                thisx->velocity.z = Math_CosS(thisx->world.rot.y) * thisx->speed;
                thisx->velocity.y = CLAMP_MIN(thisx->velocity.y, 0.0f);
            }
            break;

        case 2: // dropped or thrown
            thisx->velocity.y = CLAMP_MIN(thisx->velocity.y - 1.2f, -20.0f);
            Actor_UpdatePos(thisx);
            Actor_UpdateBgCheckInfo(play, thisx, 10.0f, 10.0f, 0.0f,
                                    UPDBGCHECKINFO_FLAG_0 | UPDBGCHECKINFO_FLAG_2 | UPDBGCHECKINFO_FLAG_7);
            if (thisx->bgCheckFlags & BGCHECKFLAG_GROUND) {
                f32 dx = thisx->world.pos.x - YEARS_CAVITY_X;
                f32 dz = thisx->world.pos.z - YEARS_CAVITY_Z;
                f32 sx = (sStone != NULL) ? (sStone->dyna.actor.world.pos.x - YEARS_CAVITY_X) : 0.0f;
                f32 sz = (sStone != NULL) ? (sStone->dyna.actor.world.pos.z - YEARS_CAVITY_Z) : 0.0f;

                thisx->velocity.x = thisx->velocity.y = thisx->velocity.z = 0.0f;
                this->mode = 0;
                Actor_PlaySfx(thisx, NA_SE_EV_STONE_BOUND);
                if ((this->arg == 0) && (SQ(dx) + SQ(dz) < SQ(40.0f)) && (SQ(sx) + SQ(sz) > SQ(35.0f))) {
                    // into the cavity, the stone lifted off it: buried
                    thisx->world.pos.x = YEARS_CAVITY_X;
                    thisx->world.pos.z = YEARS_CAVITY_Z;
                    this->mode = 3;
                    Flags_SetSwitch(play, YEARS_FLAG_MEDALLION);
                    Years_Chime();
                }
            } else if (thisx->world.pos.y < -300.0f) {
                thisx->world.pos = thisx->home.pos;
                this->mode = 0;
            }
            break;

        default: // buried
            break;
    }
}

// ---------------------------------------------------------------- the rest

static void EnRemixYears_UpdateEra(EnRemixYears* this, PlayState* play) {
    Actor* thisx = &this->dyna.actor;
    Player* player = GET_PLAYER(play);

    if ((this->arg != 2) || this->isChild) {
        if (this->hasDyna && (fabsf(this->dyna.unk_150) > 0.001f)) {
            this->dyna.unk_150 = 0.0f;
            player->stateFlags2 &= ~PLAYER_STATE2_4;
        }
        return;
    }
    // the roots: the adult pushes them aside, and they come apart
    switch (this->mode) {
        case 0:
            if (fabsf(this->dyna.unk_150) > 0.001f) {
                this->dyna.unk_150 = 0.0f;
                this->mode = 1;
                this->timer = 20;
                Actor_PlaySfx(thisx, NA_SE_EV_ROCK_SLIDE);
            }
            break;
        case 1:
            thisx->world.pos.x += 2.0f;
            this->scale -= 0.03f;
            if (--this->timer <= 0) {
                player->stateFlags2 &= ~PLAYER_STATE2_4;
                DynaPoly_DeleteBgActor(play, &play->colCtx.dyna, this->dyna.bgId);
                this->hasDyna = false;
                this->mode = 2;
                Flags_SetSwitch(play, YEARS_FLAG_ROOTS);
                Years_Chime();
            }
            break;
        default:
            break;
    }
}

void EnRemixYears_Update(Actor* thisx, PlayState* play) {
    EnRemixYears* this = (EnRemixYears*)thisx;
    f32 target;

    switch (this->type) {
        case YEARS_PEDESTAL:
            EnRemixYears_UpdatePedestal(this, play);
            break;
        case YEARS_PUSH:
            EnRemixYears_UpdatePush(this, play);
            break;
        case YEARS_ERA:
            EnRemixYears_UpdateEra(this, play);
            break;
        case YEARS_CARRY:
            EnRemixYears_UpdateCarry(this, play);
            break;
        case YEARS_TABLET:
            if (Actor_TalkOfferAccepted(thisx, play)) {
                this->talking = true;
            } else if (!this->talking || (Message_GetState(&play->msgCtx) == TEXT_STATE_NONE)) {
                this->talking = false;
                Actor_OfferTalk(thisx, play, 100.0f);
            }
            break;
        case YEARS_DOOR:
            if (Flags_GetSwitch(play, YEARS_FLAG_DOOR)) {
                target = YEARS_DOOR_H;
                if (this->offset != target) {
                    if (this->offset == 0.0f) {
                        Years_Chime();
                    }
                    Math_StepToF(&this->offset, target, 4.0f);
                    Actor_PlaySfx_Flagged(thisx, NA_SE_EV_STONE_STATUE_OPEN - SFX_FLAG);
                    if (this->offset == target) {
                        Actor_PlaySfx(thisx, NA_SE_EV_STONEDOOR_STOP);
                    }
                }
            }
            thisx->world.pos.y = thisx->home.pos.y + this->offset;
            break;
        default:
            break;
    }
}

// ---------------------------------------------------------------- drawing

static void Years_DrawDL(PlayState* play, Actor* thisx, Gfx* dl, f32 dy, f32 scaleY) {
    GraphicsContext* gfxCtx = play->state.gfxCtx;

    OPEN_DISPS(gfxCtx, "../z_en_remix_years.c", __LINE__);
    Gfx_SetupDL_25Opa(gfxCtx);
    gDPSetEnvColor(POLY_OPA_DISP++, 0, 0, 0, 255);
    Matrix_Translate(thisx->world.pos.x, thisx->world.pos.y + dy, thisx->world.pos.z, MTXMODE_NEW);
    Matrix_RotateY(BINANG_TO_RAD(thisx->shape.rot.y), MTXMODE_APPLY);
    Matrix_Scale(1.0f, scaleY, 1.0f, MTXMODE_APPLY);
    MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_years.c", __LINE__);
    gSPDisplayList(POLY_OPA_DISP++, dl);
    CLOSE_DISPS(gfxCtx, "../z_en_remix_years.c", __LINE__);
}

void EnRemixYears_Draw(Actor* thisx, PlayState* play) {
    EnRemixYears* this = (EnRemixYears*)thisx;

    switch (this->type) {
        case YEARS_PEDESTAL:
            Years_DrawDL(play, thisx, gYearsPedestalDL, 0.0f, 1.0f);
            if (this->isChild) { // the sword rests in it in the past (the adult carries it)
                Years_DrawDL(play, thisx, gYearsSwordDL, 66.0f, 1.0f);
            }
            break;
        case YEARS_PUSH:
            if (this->arg == 0) {
                Years_DrawDL(play, thisx, gYearsCubeDL, 0.0f, 1.0f);
            } else if (this->arg == 1) {
                Years_DrawDL(play, thisx, this->isChild ? gYearsPlanterDL : gYearsTreeDL, 0.0f, 1.0f);
            } else {
                Years_DrawDL(play, thisx, gYearsSupportDL, 0.0f, 1.0f);
            }
            break;
        case YEARS_ERA:
            switch (this->arg) {
                case 0:
                    Years_DrawDL(play, thisx, this->isChild ? gYearsGardenWallDL : gYearsRubbleDL, 0.0f, 1.0f);
                    break;
                case 1:
                    Years_DrawDL(play, thisx, this->isChild ? gYearsEastStairsDL : gYearsEastStairsRuinDL, 0.0f, 1.0f);
                    break;
                case 2:
                    if (this->isChild) {
                        Years_DrawDL(play, thisx, gYearsCrackWallDL, 0.0f, 1.0f);
                    } else if (this->mode < 2) {
                        Years_DrawDL(play, thisx, gYearsRootsDL, 0.0f, this->scale);
                    }
                    break;
                default:
                    Years_DrawDL(play, thisx, this->mode ? gYearsStairsFullDL : gYearsStairsBrokenDL, 0.0f, 1.0f);
                    break;
            }
            break;
        case YEARS_CARRY:
            if (this->arg == 1) {
                // the stone; and the cavity under where it lay, once it is lifted off
                if ((SQ(thisx->world.pos.x - YEARS_CAVITY_X) + SQ(thisx->world.pos.z - YEARS_CAVITY_Z)) > SQ(35.0f)) {
                    GraphicsContext* gfxCtx = play->state.gfxCtx;

                    OPEN_DISPS(gfxCtx, "../z_en_remix_years.c", __LINE__);
                    Gfx_SetupDL_25Opa(gfxCtx);
                    gDPSetEnvColor(POLY_OPA_DISP++, 0, 0, 0, 255);
                    Matrix_Translate(YEARS_CAVITY_X, 0.5f, YEARS_CAVITY_Z, MTXMODE_NEW);
                    MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, gfxCtx, "../z_en_remix_years.c", __LINE__);
                    gSPDisplayList(POLY_OPA_DISP++, gYearsCavityDL);
                    CLOSE_DISPS(gfxCtx, "../z_en_remix_years.c", __LINE__);
                }
                Years_DrawDL(play, thisx, gYearsLooseStoneDL, 0.0f, 1.0f);
            } else {
                Years_DrawDL(play, thisx, gYearsMedallionDL, (this->mode == 3) ? -2.0f : 0.0f, 1.0f);
            }
            break;
        case YEARS_TABLET:
            Years_DrawDL(play, thisx, gYearsTabletDL, 0.0f, 1.0f);
            break;
        case YEARS_DOOR:
            Years_DrawDL(play, thisx, gYearsDoorDL, 0.0f, 1.0f);
            break;
        default:
            break;
    }
}
