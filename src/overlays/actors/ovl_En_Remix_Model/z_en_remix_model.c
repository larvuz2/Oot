/*
 * File: z_en_remix_model.c
 * Overlay: ovl_En_Remix_Model
 * Description: Web Remix custom 3D model (spawnable from the Remix menu).
 *              Draws gRemixModelDL from object_remix_model, spinning and bobbing.
 *              Params: scale in percent (0 = 100%).
 */

#include "z_en_remix_model.h"

#include "play_state.h"
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

    Actor_SetScale(&this->actor, 0.03f * percent / 100.0f);
    this->timer = 0;
}

void EnRemixModel_Destroy(Actor* thisx, PlayState* play) {
}

void EnRemixModel_Update(Actor* thisx, PlayState* play) {
    EnRemixModel* this = (EnRemixModel*)thisx;

    this->timer++;
    this->actor.shape.rot.y += 0x300;
    this->actor.world.pos.y = this->actor.home.pos.y + 25.0f + Math_SinS(this->timer * 0x400) * 6.0f;
}

void EnRemixModel_Draw(Actor* thisx, PlayState* play) {
    Gfx_DrawDListOpa(play, gRemixModelDL);
}
