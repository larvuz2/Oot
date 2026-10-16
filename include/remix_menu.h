#ifndef REMIX_MENU_H
#define REMIX_MENU_H

#include "ultra64.h"

struct Actor;
struct PlayState;
struct SceneTableEntry;

// Web Remix in-game menu (src/code/z_remix_menu.c). Press D-pad Up during gameplay.
void RemixMenu_Update(struct PlayState* play);
void RemixMenu_Draw(struct PlayState* play);
// Called right after Actor_UpdateAll: keeps a "play as" puppet actor glued to Link.
void RemixMenu_AfterActorUpdate(struct PlayState* play);

// Custom model (object_remix_model) helpers, shared with ovl_En_Remix_Model.
// `slot` is the object slot holding object_remix_model; it must be loaded.
s16 RemixModel_GetInfo(struct PlayState* play, s32 slot, s32 field);
Gfx* RemixModel_GetFrameDL(struct PlayState* play, s32 slot, s32 frame);
// Frame to show for a character moving at `speed`, advancing *animTime.
s32 RemixModel_AnimFrame(struct PlayState* play, s32 slot, f32 speed, f32* animTime);

// "Play as" (custom model or a puppet actor): Actor_Draw calls this instead of Link's draw function.
s32 RemixCostume_IsActive(void);
void RemixCostume_DrawPlayer(struct PlayState* play, struct Actor* player);

// Biomes: Play_SpawnScene calls this; returns the scene entry to load (a restyled copy of Hyrule Field
// while a biome is on).
struct SceneTableEntry* RemixBiome_OverrideScene(struct PlayState* play, s32 sceneId, struct SceneTableEntry* scene);

#endif
