/*
 * File: z_en_remix_wind.c
 * Overlay: ovl_En_Remix_Wind
 * Description: Web Remix level 8, the Shrine of the Upside-Down Wind. One chamber with two floors, the ground and the
 *              ceiling, the exit on the ceiling right above the entrance, and no stairs between them: a machine that
 *              works in reverse. The pieces are object_remix_wind (tools/remix/make_wind_parts.py, which also writes
 *              the plan this file reads: WIND_* in object_remix_wind.h); the room is tools/remix/make_wind.py.
 *
 *   WIND_CTRL     The machine. Counts down the timed switch's upside-down gravity; reads the two ceiling switches
 *                 (the plate: the heavy cube against it; the ceiling fan's housing: a lighter cube pulled up against
 *                 it while the wind is turned); with both pressed at once the final ladder comes down from the exit
 *                 platform, for good. A cube that falls upwards through the glass room's hole and strikes the iron
 *                 shelf inside lights its crystal: the glass retracts.
 *   WIND_CUBE     An iron cube (light, medium, heavy). Magnesis moves it (En_Remix_Magnet: this actor begins with
 *                 an EnRemixMagnet). Loose, it falls; with the gravity turned upside down it falls up, to whatever is
 *                 above it. In the column of wind the light and medium cubes dance (the crystal blue: the wind blows
 *                 up) or, the wind turned (orange), are pulled up against the ceiling fan if high enough, else fall.
 *                 The heavy cube is too heavy for the wind. Standing on a dancing cube Link rides it up, as high as
 *                 the wind can carry him: the child to the final ladder, the adult not. The medium cube locks into
 *                 the bracket beside the plate; with it there, the heavy cube is wedged against the plate and stays.
 *   WIND_FAN      The floor's and the ceiling's fans: housings, turning blades, and the wind between them.
 *   WIND_PLATE    The first ceiling switch; glows while pressed.
 *   WIND_BRACKET  The bracket beside it.
 *   WIND_TIMER    The timed switch: step on it, and for eight seconds every loose object falls upwards (not Link).
 *   WIND_LADDER   The ladder to the middle balcony; the final ladder, folded up through the exit platform until
 *                 both ceiling switches have been pressed at once, then lowered, stopping short of the floor.
 *   WIND_GATE     The gate before the first ladder (open while the plate is pressed); the hidden treasure's glass.
 */

#include "z_en_remix_wind.h"

#include "gfx.h"
#include "gfx_setupdl.h"
#include "array_count.h"
#include "libc/math.h"
#include "sfx.h"
#include "sys_matrix.h"
#include "z_lib.h"
#include "z_math.h"
#include "audio.h"
#include "play_state.h"
#include "player.h"
#include "save.h"

#include "assets/objects/object_remix_wind/object_remix_wind.h"

#define FLAGS (ACTOR_FLAG_UPDATE_CULLING_DISABLED | ACTOR_FLAG_DRAW_CULLING_DISABLED)

#define WIND_GRAVITY 1.5f
#define WIND_PULL 1.2f // the turned wind pulling a cube up against the ceiling fan

void EnRemixWind_Init(Actor* thisx, PlayState* play);
void EnRemixWind_Destroy(Actor* thisx, PlayState* play);
void EnRemixWind_Update(Actor* thisx, PlayState* play);
void EnRemixWind_Draw(Actor* thisx, PlayState* play);

ActorProfile En_Remix_Wind_Profile = {
    /**/ ACTOR_EN_REMIX_WIND,
    /**/ ACTORCAT_BG,
    /**/ FLAGS,
    /**/ OBJECT_REMIX_WIND,
    /**/ sizeof(EnRemixWind),
    /**/ EnRemixWind_Init,
    /**/ EnRemixWind_Destroy,
    /**/ EnRemixWind_Update,
    /**/ EnRemixWind_Draw,
};

static f32 sCubeSizes[] = WIND_CUBE_SIZES;
static CollisionHeader* sCubeCols[] = { &gWindCubeSCol, &gWindCubeMCol, &gWindCubeLCol };
static Gfx* sCubeDLs[] = { gWindCubeSDL, gWindCubeMDL, gWindCubeLDL };

static EnRemixWind* sCubes[3];
static s16 sGravTimer; // frames of upside-down gravity left
static s16 sTick;      // the wind's dance

// ---------------------------------------------------------------- helpers

static s32 Wind_Turned(PlayState* play) {
    return Flags_GetSwitch(play, WIND_FLAG_FANS); // the crystal orange: the wind blows down
}

static void Wind_Chime(void) {
    Sfx_PlaySfxCentered(NA_SE_SY_CORRECT_CHIME);
}

static void Wind_SetFlag(PlayState* play, s32 flag, s32 on) {
    if (on) {
        Flags_SetSwitch(play, flag);
    } else {
        Flags_UnsetSwitch(play, flag);
    }
}

// ---------------------------------------------------------------- init / destroy

void EnRemixWind_Init(Actor* thisx, PlayState* play) {
    EnRemixWind* this = (EnRemixWind*)thisx;
    CollisionHeader* colHeader = NULL;
    CollisionHeader* col = NULL;

    this->type = WIND_TYPE(thisx->params);
    this->arg = WIND_ARG(thisx->params);
    thisx->home.rot.x = thisx->home.rot.z = 0;
    thisx->world.rot = thisx->shape.rot = thisx->home.rot;
    Actor_SetScale(thisx, 1.0f);
    this->base.type = MAGNET_LIFT; // (not magnetic: only loose cubes are)
    this->base.target = this->base.aim = this->base.falling = NULL;

    switch (this->type) {
        case WIND_CTRL:
            sGravTimer = 0;
            break;

        case WIND_CUBE:
            this->arg %= 3;
            this->size = sCubeSizes[this->arg];
            this->base.lift = this->size; // (Magnesis reads the height from here)
            this->base.type = MAGNET_CRATE;
            this->base.lastSafe = thisx->home.pos;
            col = sCubeCols[this->arg];
            sCubes[this->arg] = this;
            if ((this->arg == 1) && Flags_GetSwitch(play, WIND_FLAG_BRACKET)) {
                this->locked = true;
                thisx->world.pos.x = WIND_BRACKET_X;
                thisx->world.pos.y = WIND_BRACKET_Y - this->size / 2;
                thisx->world.pos.z = WIND_BRACKET_Z;
            } else if ((this->arg == 2) && Flags_GetSwitch(play, WIND_FLAG_WEDGED)) {
                this->locked = true;
                thisx->world.pos.x = WIND_PLATE_X;
                thisx->world.pos.y = WIND_PLATE_BOTTOM - this->size;
                thisx->world.pos.z = WIND_PLATE_Z;
            }
            if (this->locked) {
                this->base.type = MAGNET_LIFT;
            }
            break;

        case WIND_FAN:
            col = (this->arg == 0) ? &gWindFanFloorCol : &gWindFanCeilingCol;
            break;

        case WIND_PLATE:
            col = &gWindPlateCol;
            break;

        case WIND_TIMER:
            col = &gWindTimerCol;
            break;

        case WIND_LADDER:
            col = (this->arg == 0) ? &gWindLadder1Col : &gWindLadder2Col;
            if ((this->arg == 1) && !Flags_GetSwitch(play, WIND_FLAG_LADDER)) {
                this->offset = WIND_LADDER2_LIFT; // folded up through the exit platform
            }
            thisx->world.pos.y = thisx->home.pos.y + this->offset;
            break;

        case WIND_GATE:
            col = (this->arg == 0) ? &gWindGateCol : &gWindGlassCol;
            if ((this->arg == 1) && Flags_GetSwitch(play, WIND_FLAG_GLASS)) {
                this->offset = WIND_GLASS_DROP; // retracted long ago
            }
            break;

        default:
            break;
    }

    if (col != NULL) {
        DynaPolyActor_Init(&this->base.dyna, DYNA_TRANSFORM_POS);
        CollisionHeader_GetVirtual(col, &colHeader);
        this->base.dyna.bgId = DynaPoly_SetBgActor(play, &play->colCtx.dyna, thisx, colHeader);
        this->hasDyna = true;
        if ((this->type == WIND_GATE) && (this->arg == 1) && (this->offset != 0.0f)) {
            DynaPoly_DisableCollision(play, &play->colCtx.dyna, this->base.dyna.bgId);
        }
    }
}

void EnRemixWind_Destroy(Actor* thisx, PlayState* play) {
    EnRemixWind* this = (EnRemixWind*)thisx;
    s32 i;

    if (this->hasDyna) {
        DynaPoly_DeleteBgActor(play, &play->colCtx.dyna, this->base.dyna.bgId);
    }
    for (i = 0; i < ARRAY_COUNT(sCubes); i++) {
        if (sCubes[i] == this) {
            sCubes[i] = NULL;
        }
    }
}

// ---------------------------------------------------------------- the cubes

/** The sample points under / over a cube: its middle and (just inside) its four corners. */
static void Wind_Samples(EnRemixWind* this, f32 inset, f32 out[5][2]) {
    Actor* thisx = &this->base.dyna.actor;
    f32 h = this->size / 2 - inset;
    s32 i;

    for (i = 0; i < 5; i++) {
        out[i][0] = thisx->world.pos.x + ((i == 0) ? 0.0f : ((i & 1) ? h : -h));
        out[i][1] = thisx->world.pos.z + ((i == 0) ? 0.0f : ((i & 2) ? h : -h));
    }
}

/** The highest floor under the cube (not counting itself). */
static f32 Wind_Floor(EnRemixWind* this, PlayState* play) {
    Actor* thisx = &this->base.dyna.actor;
    f32 pts[5][2];
    f32 best = BGCHECK_Y_MIN;
    CollisionPoly* poly;
    s32 bgId;
    Vec3f pos;
    f32 y;
    s32 i;

    Wind_Samples(this, 8.0f, pts);
    for (i = 0; i < 5; i++) {
        pos.x = pts[i][0];
        pos.y = thisx->world.pos.y + 40.0f;
        pos.z = pts[i][1];
        y = BgCheck_EntityRaycastDown4(&play->colCtx, &poly, &bgId, thisx, &pos);
        if (y > best) {
            best = y;
        }
    }
    return best;
}

/** The lowest ceiling over the cube (the room's, a platform's, a switch, another cube; through a hole if it fits). */
static f32 Wind_Ceiling(EnRemixWind* this, PlayState* play) {
    Actor* thisx = &this->base.dyna.actor;
    f32 pts[5][2];
    f32 best = WIND_CEIL;
    CollisionPoly* poly;
    s32 bgId;
    Vec3f from;
    Vec3f to;
    Vec3f hit;
    s32 i;

    Wind_Samples(this, 2.0f, pts);
    for (i = 0; i < 5; i++) {
        from.x = to.x = pts[i][0];
        from.z = to.z = pts[i][1];
        from.y = thisx->world.pos.y + this->size / 2;
        to.y = WIND_CEIL + 20.0f;
        if (BgCheck_EntityLineTest2(&play->colCtx, &from, &to, &hit, &poly, false, false, true, true, &bgId, thisx) &&
            (hit.y < best)) {
            best = hit.y;
        }
    }
    return best;
}

/** Move horizontally unless a wall is in the way (a line through the cube's middle). */
static s32 Wind_MoveXZ(EnRemixWind* this, PlayState* play, f32 dx, f32 dz) {
    Actor* thisx = &this->base.dyna.actor;
    Vec3f from;
    Vec3f to;
    Vec3f hit;
    CollisionPoly* poly;
    s32 bgId;
    f32 reach = this->size / 2 + 4.0f;

    if ((dx == 0.0f) && (dz == 0.0f)) {
        return true;
    }
    from = thisx->world.pos;
    from.y += this->size / 2;
    to.x = from.x + dx + ((dx > 0.0f) ? reach : (dx < 0.0f) ? -reach : 0.0f);
    to.y = from.y;
    to.z = from.z + dz + ((dz > 0.0f) ? reach : (dz < 0.0f) ? -reach : 0.0f);
    if (BgCheck_EntityLineTest2(&play->colCtx, &from, &to, &hit, &poly, true, false, false, true, &bgId, thisx)) {
        return false;
    }
    thisx->world.pos.x += dx;
    thisx->world.pos.z += dz;
    return true;
}

static void Wind_Respawn(EnRemixWind* this) {
    Actor* thisx = &this->base.dyna.actor;

    thisx->world.pos = thisx->home.pos;
    thisx->world.pos.y += 40.0f;
    this->base.vel.x = this->base.vel.y = this->base.vel.z = 0.0f;
    this->base.resting = false;
    Actor_PlaySfx(thisx, NA_SE_SY_TRE_BOX_APPEAR);
}

static s32 Wind_InColumn(Actor* thisx) {
    f32 dx = thisx->world.pos.x - WIND_COLUMN_X;
    f32 dz = thisx->world.pos.z - WIND_COLUMN_Z;

    return SQ(dx) + SQ(dz) < SQ(WIND_FAN_R);
}

static void EnRemixWind_UpdateCube(EnRemixWind* this, PlayState* play) {
    Actor* thisx = &this->base.dyna.actor;
    Player* player = GET_PLAYER(play);
    f32 accel = -WIND_GRAVITY;
    f32 maxUp = 25.0f;
    f32 floor;
    f32 ceil;
    s32 inColumn;
    s32 rider;
    s32 direct = false;

    if (this->locked) {
        return;
    }
    if (this->base.held) {
        // Magnesis holds it: not through the ceiling
        this->base.resting = false;
        this->base.vel.x = this->base.vel.y = this->base.vel.z = 0.0f;
        ceil = Wind_Ceiling(this, play);
        if (thisx->world.pos.y + this->size > ceil) {
            thisx->world.pos.y = ceil - this->size;
        }
        return;
    }

    inColumn = Wind_InColumn(thisx) && (this->arg != 2); // (the heavy cube is too heavy for the wind)
    rider = DynaPolyActor_IsPlayerOnTop(&this->base.dyna);

    if (sGravTimer > 0) {
        accel = WIND_GRAVITY; // upside down: it falls up
        this->base.resting = false;
    } else if (inColumn && !Wind_Turned(play)) {
        // the wind blows up: it dances in the column (with Link on it, it carries him as high as it can)
        f32 goal;
        f32 step;

        if (rider) {
            goal = (LINK_IS_ADULT ? WIND_RIDE_TOP_ADULT : WIND_RIDE_TOP_CHILD) - this->size;
            step = CLAMP(goal - thisx->world.pos.y, -2.5f, 2.5f);
        } else {
            goal = WIND_HOVER_MID + WIND_HOVER_AMP * Math_SinS(sTick * (0x10000 / WIND_HOVER_PERIOD));
            step = CLAMP(goal - thisx->world.pos.y, -7.0f, 7.0f);
        }
        this->base.vel.y = step;
        direct = true;
        this->base.resting = false;
    } else if (inColumn && (thisx->world.pos.y > WIND_COLUMN_MID)) {
        accel = WIND_PULL; // the wind turned: pulled up against the ceiling fan
        maxUp = 12.0f;
        this->base.resting = false;
    }

    if (inColumn && (sGravTimer == 0) && (direct || (accel > 0.0f))) {
        // the wind draws it to the column's middle
        thisx->world.pos.x += (WIND_COLUMN_X - thisx->world.pos.x) * 0.04f;
        thisx->world.pos.z += (WIND_COLUMN_Z - thisx->world.pos.z) * 0.04f;
        this->base.vel.x = this->base.vel.z = 0.0f;
    }

    // horizontally: a fling carries it on
    if (!Wind_MoveXZ(this, play, this->base.vel.x, this->base.vel.z)) {
        this->base.vel.x = this->base.vel.z = 0.0f;
    }
    this->base.vel.x *= this->base.resting ? 0.5f : 0.98f;
    this->base.vel.z *= this->base.resting ? 0.5f : 0.98f;

    floor = Wind_Floor(this, play);
    if (this->base.resting && (accel < 0.0f)) {
        if (floor < thisx->world.pos.y - 2.0f) {
            this->base.resting = false; // what it stood on moved away
        } else {
            thisx->world.pos.y = floor; // rides what it stands on
            this->base.vel.y = 0.0f;
        }
    }
    if (!this->base.resting) {
        if (!direct) {
            this->base.vel.y = CLAMP(this->base.vel.y + accel, -25.0f, maxUp);
        }
        thisx->world.pos.y += this->base.vel.y;
        if (this->base.vel.y > 0.0f) {
            ceil = Wind_Ceiling(this, play);
            if (thisx->world.pos.y + this->size > ceil) {
                thisx->world.pos.y = ceil - this->size;
                if (this->base.vel.y > 6.0f) {
                    Actor_PlaySfx(thisx, NA_SE_EV_BLOCK_BOUND);
                }
                this->base.vel.y = 0.0f;
            }
        }
        if (thisx->world.pos.y <= floor) {
            thisx->world.pos.y = floor;
            if (this->base.vel.y < -6.0f) {
                Actor_PlaySfx(thisx, NA_SE_EV_BLOCK_BOUND);
            }
            this->base.vel.y = 0.0f;
            if (!direct) {
                this->base.resting = true;
                this->base.vel.x = this->base.vel.z = 0.0f;
            }
        }
    }
    if ((thisx->world.pos.y < -200.0f) || (floor < -200.0f)) {
        Wind_Respawn(this); // (out of the room)
    }

    // the medium cube into the bracket beside the plate
    if ((this->arg == 1) && (fabsf(thisx->world.pos.x - WIND_BRACKET_X) < 45.0f) &&
        (fabsf(thisx->world.pos.z - WIND_BRACKET_Z) < 45.0f) &&
        (thisx->world.pos.y + this->size / 2 > WIND_BRACKET_Y - 30.0f)) {
        this->locked = true;
        this->base.type = MAGNET_LIFT;
        thisx->world.pos.x = WIND_BRACKET_X;
        thisx->world.pos.y = WIND_BRACKET_Y - this->size / 2;
        thisx->world.pos.z = WIND_BRACKET_Z;
        Flags_SetSwitch(play, WIND_FLAG_BRACKET);
        Actor_PlaySfx(thisx, NA_SE_EV_STONE_BOUND);
        Wind_Chime();
    }
    (void)player;
}

// ---------------------------------------------------------------- the machine

static void EnRemixWind_UpdateCtrl(EnRemixWind* this, PlayState* play) {
    EnRemixWind* heavy = sCubes[2];
    s32 p1 = false;
    s32 p2 = false;
    s32 i;

    sTick++;
    if (sGravTimer > 0) {
        sGravTimer--;
        if (sGravTimer == 0) {
            Actor_PlaySfx(&this->base.dyna.actor, NA_SE_EV_TRIFORCE_FLASH);
        }
    }

    // the first ceiling switch: the heavy cube against the plate (wedged there by the medium cube in the bracket)
    if (heavy != NULL) {
        Actor* h = &heavy->base.dyna.actor;

        p1 = (h->world.pos.y + heavy->size >= WIND_PLATE_BOTTOM - 3.0f) &&
             (fabsf(h->world.pos.x - WIND_PLATE_X) < WIND_PLATE_HALF) &&
             (fabsf(h->world.pos.z - WIND_PLATE_Z) < WIND_PLATE_HALF);
        if (p1 && !heavy->locked && !heavy->base.held && Flags_GetSwitch(play, WIND_FLAG_BRACKET)) {
            heavy->locked = true;
            heavy->base.type = MAGNET_LIFT;
            Flags_SetSwitch(play, WIND_FLAG_WEDGED);
            Actor_PlaySfx(h, NA_SE_EV_STONE_BOUND);
            Wind_Chime();
        }
    }
    if (p1 != Flags_GetSwitch(play, WIND_FLAG_P1)) {
        Wind_SetFlag(play, WIND_FLAG_P1, p1);
        Actor_PlaySfx(&this->base.dyna.actor, NA_SE_EV_METALDOOR_OPEN);
    }

    for (i = 0; i < 2; i++) {
        EnRemixWind* cube = sCubes[i];
        Actor* c;

        if (cube == NULL) {
            continue;
        }
        c = &cube->base.dyna.actor;
        // the second ceiling switch: a lighter cube pulled up against the ceiling fan
        if (Wind_InColumn(c) && Wind_Turned(play) && (c->world.pos.y + cube->size >= WIND_CEIL_FAN_BOTTOM - 3.0f)) {
            p2 = true;
        }
        // the hidden treasure: a cube up through the hole against the glass room's shelf
        if (!Flags_GetSwitch(play, WIND_FLAG_GLASS) && (fabsf(c->world.pos.x - WIND_HOLE_X) < WIND_HOLE_HALF) &&
            (fabsf(c->world.pos.z - WIND_HOLE_Z) < WIND_HOLE_HALF) &&
            (c->world.pos.y + cube->size >= WIND_GLASS_CAP - 3.0f)) {
            Flags_SetSwitch(play, WIND_FLAG_GLASS);
            Actor_PlaySfx(c, NA_SE_EV_ICE_BROKEN);
            Wind_Chime();
        }
    }
    if (p2 != Flags_GetSwitch(play, WIND_FLAG_P2)) {
        Wind_SetFlag(play, WIND_FLAG_P2, p2);
        if (p2) {
            Actor_PlaySfx(&this->base.dyna.actor, NA_SE_EV_METALDOOR_OPEN);
        }
    }

    // both at once: the final ladder comes down, for good
    if (p1 && p2 && !Flags_GetSwitch(play, WIND_FLAG_LADDER)) {
        Flags_SetSwitch(play, WIND_FLAG_LADDER);
        Wind_Chime();
    }
}

// ---------------------------------------------------------------- the other pieces

static void EnRemixWind_UpdateTimer(EnRemixWind* this, PlayState* play) {
    Actor* thisx = &this->base.dyna.actor;
    s32 on = DynaPolyActor_IsPlayerOnTop(&this->base.dyna);

    // stepped on (standing on it does not start it again: step off and on)
    if ((sGravTimer == 0) && on && !this->pressed) {
        sGravTimer = WIND_TIMER_FRAMES;
        Actor_PlaySfx(thisx, NA_SE_EV_TRIFORCE_FLASH);
    }
    this->pressed = on;
    if (sGravTimer > 0) {
        // the countdown: faster for the last two seconds
        if ((sGravTimer > 40) ? ((sGravTimer % 20) == 0) : ((sGravTimer % 8) == 0)) {
            Sfx_PlaySfxCentered((sGravTimer > 40) ? NA_SE_SY_WARNING_COUNT_N : NA_SE_SY_WARNING_COUNT_E);
        }
        Math_StepToF(&this->offset, -8.0f, 2.0f);
    } else {
        Math_StepToF(&this->offset, 0.0f, 1.0f);
    }
}

static void EnRemixWind_UpdateLadder(EnRemixWind* this, PlayState* play) {
    Actor* thisx = &this->base.dyna.actor;

    if ((this->arg == 1) && (this->offset > 0.0f) && Flags_GetSwitch(play, WIND_FLAG_LADDER)) {
        Math_StepToF(&this->offset, 0.0f, 3.0f);
        Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ELEVATOR_MOVE - SFX_FLAG);
        if (this->offset == 0.0f) {
            Actor_PlaySfx(thisx, NA_SE_EV_STONEDOOR_STOP);
        }
    }
    thisx->world.pos.y = thisx->home.pos.y + this->offset;
}

static void EnRemixWind_UpdateGate(EnRemixWind* this, PlayState* play) {
    Actor* thisx = &this->base.dyna.actor;
    f32 prev = this->offset;

    if (this->arg == 0) {
        // open while the plate is pressed
        if (Flags_GetSwitch(play, WIND_FLAG_P1)) {
            Math_StepToF(&this->offset, WIND_GATE_DROP, 12.0f);
        } else {
            Math_StepToF(&this->offset, 0.0f, 8.0f);
        }
        thisx->world.pos.y = thisx->home.pos.y + this->offset;
    } else if (Flags_GetSwitch(play, WIND_FLAG_GLASS)) {
        // the glass sinks into its slot (drawn shrinking): the way in is open at once
        if (this->offset == 0.0f) {
            DynaPoly_DisableCollision(play, &play->colCtx.dyna, this->base.dyna.bgId);
        }
        Math_StepToF(&this->offset, WIND_GLASS_DROP, 4.0f);
    }
    if (prev != this->offset) {
        Actor_PlaySfx_Flagged(thisx, NA_SE_EV_ELEVATOR_MOVE - SFX_FLAG);
    }
}

void EnRemixWind_Update(Actor* thisx, PlayState* play) {
    EnRemixWind* this = (EnRemixWind*)thisx;

    this->timer++;
    switch (this->type) {
        case WIND_CTRL:
            EnRemixWind_UpdateCtrl(this, play);
            break;
        case WIND_CUBE:
            EnRemixWind_UpdateCube(this, play);
            break;
        case WIND_FAN:
            this->spin += Wind_Turned(play) ? -0x0C00 : 0x0C00;
            if (this->arg == 0) {
                Actor_PlaySfx_Flagged(thisx, NA_SE_EV_WIND_TRAP - SFX_FLAG);
            }
            break;
        case WIND_PLATE:
            this->pressed = Flags_GetSwitch(play, WIND_FLAG_P1);
            break;
        case WIND_TIMER:
            EnRemixWind_UpdateTimer(this, play);
            break;
        case WIND_LADDER:
            EnRemixWind_UpdateLadder(this, play);
            break;
        case WIND_GATE:
            EnRemixWind_UpdateGate(this, play);
            break;
        default:
            break;
    }
}

// ---------------------------------------------------------------- drawing

static void Wind_DrawOpa(PlayState* play, Gfx* dl, s32 r, s32 g, s32 b) {
    OPEN_DISPS(play->state.gfxCtx, "../z_en_remix_wind.c", __LINE__);

    Gfx_SetupDL_25Opa(play->state.gfxCtx);
    gDPSetEnvColor(POLY_OPA_DISP++, r, g, b, 255);
    MATRIX_FINALIZE_AND_LOAD(POLY_OPA_DISP++, play->state.gfxCtx, "../z_en_remix_wind.c", __LINE__);
    gSPDisplayList(POLY_OPA_DISP++, dl);

    CLOSE_DISPS(play->state.gfxCtx, "../z_en_remix_wind.c", __LINE__);
}

/** The wind between the fans: a faint column, and bands rising (blue) or sinking (orange) through it. */
static void Wind_DrawColumn(EnRemixWind* this, PlayState* play) {
    s32 turned = Wind_Turned(play);
    s32 cr = turned ? 255 : 120;
    s32 cg = turned ? 160 : 210;
    s32 cb = turned ? 70 : 255;
    f32 height = WIND_CEIL_FAN_BOTTOM - 20.0f;
    s32 k;

    OPEN_DISPS(play->state.gfxCtx, "../z_en_remix_wind.c", __LINE__);

    Gfx_SetupDL_25Xlu(play->state.gfxCtx);
    Matrix_Push();
    Matrix_Translate(0.0f, 20.0f, 0.0f, MTXMODE_APPLY);
    Matrix_Scale(WIND_FAN_R, height, WIND_FAN_R, MTXMODE_APPLY);
    gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, cr, cg, cb, 34);
    MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, play->state.gfxCtx, "../z_en_remix_wind.c", __LINE__);
    gSPDisplayList(POLY_XLU_DISP++, gWindColumnDL);
    Matrix_Pop();
    for (k = 0; k < 4; k++) {
        s32 t = (this->timer * 9 + k * 180) % 720;
        f32 y = 20.0f + (turned ? (720 - t) : t) * (height - 30.0f) / 720.0f;

        Matrix_Push();
        Matrix_Translate(0.0f, y, 0.0f, MTXMODE_APPLY);
        Matrix_Scale(WIND_FAN_R * 0.92f, 26.0f, WIND_FAN_R * 0.92f, MTXMODE_APPLY);
        gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, cr, cg, cb, 70);
        MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, play->state.gfxCtx, "../z_en_remix_wind.c", __LINE__);
        gSPDisplayList(POLY_XLU_DISP++, gWindColumnDL);
        Matrix_Pop();
    }

    CLOSE_DISPS(play->state.gfxCtx, "../z_en_remix_wind.c", __LINE__);
}

void EnRemixWind_Draw(Actor* thisx, PlayState* play) {
    EnRemixWind* this = (EnRemixWind*)thisx;
    s32 glow;

    switch (this->type) {
        case WIND_CUBE:
            glow = 0;
            if (this->base.held) {
                glow = 95 + (s32)(35.0f * Math_SinS(this->timer * 0x1400));
            } else if (this->base.aimed) {
                glow = 45 + (s32)(25.0f * Math_SinS(this->timer * 0xC00));
            }
            if (this->locked) {
                Wind_DrawOpa(play, sCubeDLs[this->arg], 70, 40, 5);
            } else if ((sGravTimer > 0) && !this->base.held) {
                Wind_DrawOpa(play, sCubeDLs[this->arg], 20 + glow, 50, 90 + glow / 2);
            } else {
                Wind_DrawOpa(play, sCubeDLs[this->arg], glow, glow / 5, glow * 4 / 5);
            }
            break;

        case WIND_FAN:
            glow = Wind_Turned(play);
            Wind_DrawOpa(play, (this->arg == 0) ? gWindFanFloorDL : gWindFanCeilingDL, glow ? 50 : 10, glow ? 25 : 30,
                         glow ? 0 : 50);
            if ((this->arg == 1) && Flags_GetSwitch(play, WIND_FLAG_P2)) {
                Wind_DrawOpa(play, gWindFanCeilingDL, 90, 50, 0);
            }
            Matrix_Push();
            Matrix_Translate(0.0f, (this->arg == 0) ? 26.0f : (WIND_CEIL_FAN_BOTTOM - WIND_CEIL - 6.0f), 0.0f,
                             MTXMODE_APPLY);
            Matrix_RotateY(BINANG_TO_RAD(this->spin), MTXMODE_APPLY);
            Wind_DrawOpa(play, gWindBladesDL, 0, 0, 0);
            Matrix_Pop();
            if (this->arg == 0) {
                Wind_DrawColumn(this, play);
            }
            break;

        case WIND_PLATE:
            glow = this->pressed ? (70 + (s32)(20.0f * Math_SinS(this->timer * 0x1000))) : 0;
            Wind_DrawOpa(play, gWindPlateDL, glow, glow / 2, 0);
            break;

        case WIND_BRACKET:
            glow = (sCubes[1] != NULL) && sCubes[1]->locked;
            Wind_DrawOpa(play, gWindBracketDL, glow ? 60 : 0, glow ? 30 : 0, 0);
            break;

        case WIND_TIMER:
            glow = (sGravTimer > 0) ? (60 + (s32)(30.0f * Math_SinS(this->timer * 0x1800))) : 0;
            Matrix_Translate(0.0f, this->offset, 0.0f, MTXMODE_APPLY);
            Wind_DrawOpa(play, gWindTimerDL, glow / 3, glow / 2, glow);
            break;

        case WIND_LADDER:
            Wind_DrawOpa(play, (this->arg == 0) ? gWindLadder1DL : gWindLadder2DL, 0, 0, 0);
            break;

        case WIND_GATE:
            if (this->arg == 0) {
                Wind_DrawOpa(play, gWindGateDL, 0, 0, 0);
            } else if (this->offset > WIND_GLASS_DROP + 1.0f) {
                // the glass sinks into its slot in the floor (drawn shrinking, not through the floor)
                f32 t = 1.0f - this->offset / WIND_GLASS_DROP;

                Matrix_Scale(1.0f, CLAMP_MIN(t, 0.01f), 1.0f, MTXMODE_APPLY);
                OPEN_DISPS(play->state.gfxCtx, "../z_en_remix_wind.c", __LINE__);
                Gfx_SetupDL_25Xlu(play->state.gfxCtx);
                gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, 190, 235, 255, 110);
                gDPSetEnvColor(POLY_XLU_DISP++, 0, 0, 0, 255);
                MATRIX_FINALIZE_AND_LOAD(POLY_XLU_DISP++, play->state.gfxCtx, "../z_en_remix_wind.c", __LINE__);
                gSPDisplayList(POLY_XLU_DISP++, gWindGlassDL);
                CLOSE_DISPS(play->state.gfxCtx, "../z_en_remix_wind.c", __LINE__);
            }
            break;

        default:
            break;
    }
}
