/*
 * File: z_en_remix_model.c
 * Overlay: ovl_En_Remix_Model
 * Description: Web Remix custom 3D model (spawnable from the Remix menu).
 *              Draws object_remix_model: either a static prop (the default crystal), which floats
 *              and spins, or a Character Studio character, which walks after Link using its
 *              pre-posed walk frames and idles when close.
 *              Params: scale in percent (0 = 100%).
 */

#include "z_en_remix_model.h"

#include "play_state.h"
#include "remix_menu.h"
#include "z_lib.h"

#include "assets/objects/object_remix_model/object_remix_model.h"

#define FLAGS (ACTOR_FLAG_UPDATE_CULLING_DISABLED | ACTOR_FLAG_DRAW_CULLING_DISABLED)

void EnRemixModel_Init(Actor* thisx, PlayState* play);
void EnRemixModel_Destroy(Actor* thisx, PlayState* play);
void EnRemixModel_Update(Actor* thisx, PlayState* play);
void EnRemixModel_Draw(Actor* thisx, PlayState* play);

ActorProfile En_Remix_Model_Profile = {
    /**/ ACTOR_EN_REMIX_MODEL,
    /**/ ACTORCAT_PROP,
    /**/ FLAGS,
    /**/ OBJECT_REMIX_MODEL,
    /**/ sizeof(EnRemixModel),
    /**/ EnRemixModel_Init,
    /**/ EnRemixModel_Destroy,
    /**/ EnRemixModel_Update,
    /**/ EnRemixModel_Draw,
};

void EnRemixModel_Init(Actor* thisx, PlayState* play) {
    EnRemixModel* this = (EnRemixModel*)thisx;
    s32 percent = (this->actor.params > 0) ? this->actor.params : 100;

    Actor_SetScale(&this->actor, 0.01f * percent / 100.0f);
    this->timer = 0;
    this->frame = 0;
    this->animTime = 0.0f;
    this->isCharacter = RemixModel_GetInfo(play, this->actor.objectSlot, REMIX_MODEL_INFO_WALK_FRAMES) > 0;

    if (this->isCharacter) {
        ActorShape_Init(&this->actor.shape, 0.0f, ActorShadow_DrawCircle, 25.0f);
        this->actor.gravity = -1.0f;
    }
}

void EnRemixModel_Destroy(Actor* thisx, PlayState* play) {
}

void EnRemixModel_Update(Actor* thisx, PlayState* play) {
    EnRemixModel* this = (EnRemixModel*)thisx;

    this->timer++;

    if (!this->isCharacter) {
        this->actor.shape.rot.y += 0x300;
        this->actor.world.pos.y = this->actor.home.pos.y + 50.0f + Math_SinS(this->timer * 0x400) * 6.0f;
        return;
    }

    // Walk towards Link until close, then stand and face him.
    if (this->actor.xzDistToPlayer > 90.0f) {
        Math_StepToF(&this->actor.speed, 2.5f, 0.2f);
    } else {
        Math_StepToF(&this->actor.speed, 0.0f, 0.4f);
    }
    Math_SmoothStepToS(&this->actor.world.rot.y, this->actor.yawTowardsPlayer, 5, 0x800, 0x100);
    this->actor.shape.rot.y = this->actor.world.rot.y;

    Actor_MoveXZGravity(&this->actor);
    Actor_UpdateBgCheckInfo(play, &this->actor, 20.0f, 25.0f, 40.0f, UPDBGCHECKINFO_FLAG_0 | UPDBGCHECKINFO_FLAG_2);

    this->frame = RemixModel_AnimFrame(play, this->actor.objectSlot, this->actor.speed, &this->animTime);
}

void EnRemixModel_Draw(Actor* thisx, PlayState* play) {
    EnRemixModel* this = (EnRemixModel*)thisx;

    Gfx_DrawDListOpa(play, RemixModel_GetFrameDL(play, this->actor.objectSlot, this->frame));
}
