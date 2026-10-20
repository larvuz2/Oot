/*
 * File: z_remix_level.c
 * Description: Web Remix new levels.
 *   - The Ancient Plateau's scene draw config: everything in that level that moves or glows is animated here,
 *     the way the game's own scenes animate water and lava (see z_scene_table.c), by pointing segments at
 *     per-frame data that the room's display lists call (tools/remix/make_level.py):
 *       0x08  cyan glow color (circuits, ring band, monolith rings), pulsing
 *       0x0C  orange glow color (Spire slits, pedestal bands, pillar bands, Sheikah eyes), pulsing
 *       0x0D  texture scroll that makes light pulses flow along the glowing lines
 *       0x09  matrix of the ring spinning above the Spire
 *       0x0A  matrix of the rock shards orbiting the Spire
 *       0x0B  matrix of the crystal hovering inside the ring
 *   - Travel to the level from the Remix menu, and the website's "boot straight into the new level" option.
 */

#include "remix_level.h"

#include "environment.h"
#include "game.h"
#include "gfx.h"
#include "play_state.h"
#include "save.h"
#include "scene.h"
#include "seqcmd.h"
#include "sequence.h"
#include "sram.h"
#include "sys_matrix.h"
#include "transition.h"
#include "z_lib.h"
#include "libc64/malloc.h"

#include "assets/scenes/remix/ancient/ancient_room_0.h"

#define ANCIENT_SPIRE_TOP_Y ((f32)ANCIENT_RING_Y)

RemixBootConfig gRemixBootConfig = { { 'R', 'M', 'X', 'B', 'O', 'O', 'T', '1' }, 0, { 0, 0, 0, 0, 0, 0, 0 } };

void RemixLevel_DrawConfigAncient(PlayState* play) {
    GraphicsContext* gfxCtx = play->state.gfxCtx;
    u32 frames = play->gameplayFrames;
    s16 phase = (s16)(frames * 0x2C0);
    f32 wave = Math_SinS(phase);
    s32 glowA = 205 + (s32)(wave * 45.0f);
    Gfx* cyan = GRAPH_ALLOC(gfxCtx, 3 * sizeof(Gfx));
    Gfx* orange = GRAPH_ALLOC(gfxCtx, 3 * sizeof(Gfx));
    Gfx* scroll;
    Mtx* ringMtx;
    Mtx* shardsMtx;
    Mtx* crystalMtx;

    // Glow colors breathe slowly; orange runs half a beat behind cyan.
    gDPPipeSync(cyan);
    gDPSetPrimColor(cyan + 1, 0, 0, 70, 225 + (s32)(wave * 25.0f), 255, glowA);
    gSPEndDisplayList(cyan + 2);
    gDPPipeSync(orange);
    gDPSetPrimColor(orange + 1, 0, 0, 255, 150 - (s32)(wave * 30.0f), 40, 230 - (s32)(wave * 40.0f));
    gSPEndDisplayList(orange + 2);

    // Light pulses travel along the strips (32-texel texture, scrolled in quarter texels).
    scroll = Gfx_TexScroll(gfxCtx, (128 - ((frames * 3) % 128)) % 128, 0, 32, 32);

    Matrix_Push();

    Matrix_Translate(0.0f, ANCIENT_SPIRE_TOP_Y, 0.0f, MTXMODE_NEW);
    Matrix_RotateY(frames * 0.012f, MTXMODE_APPLY);
    Matrix_RotateZ(0.18f, MTXMODE_APPLY);
    ringMtx = MATRIX_FINALIZE(gfxCtx, "../z_remix_level.c", __LINE__);

    Matrix_RotateY(frames * -0.004f, MTXMODE_NEW);
    shardsMtx = MATRIX_FINALIZE(gfxCtx, "../z_remix_level.c", __LINE__);

    Matrix_Translate(0.0f, ANCIENT_SPIRE_TOP_Y + Math_SinS((s16)(frames * 0x200)) * 14.0f, 0.0f, MTXMODE_NEW);
    Matrix_RotateY(frames * -0.03f, MTXMODE_APPLY);
    crystalMtx = MATRIX_FINALIZE(gfxCtx, "../z_remix_level.c", __LINE__);

    Matrix_Pop();

    OPEN_DISPS(gfxCtx, "../z_remix_level.c", __LINE__);

    gSPSegment(POLY_OPA_DISP++, 0x08, cyan);
    gSPSegment(POLY_OPA_DISP++, 0x0C, orange);
    gSPSegment(POLY_OPA_DISP++, 0x0D, scroll);
    gSPSegment(POLY_OPA_DISP++, 0x09, ringMtx);
    gSPSegment(POLY_OPA_DISP++, 0x0A, shardsMtx);
    gSPSegment(POLY_OPA_DISP++, 0x0B, crystalMtx);
    gDPPipeSync(POLY_OPA_DISP++);
    gDPSetEnvColor(POLY_OPA_DISP++, 128, 128, 128, 128);

    gSPSegment(POLY_XLU_DISP++, 0x08, cyan);
    gSPSegment(POLY_XLU_DISP++, 0x0C, orange);
    gSPSegment(POLY_XLU_DISP++, 0x0D, scroll);
    gSPSegment(POLY_XLU_DISP++, 0x09, ringMtx);
    gSPSegment(POLY_XLU_DISP++, 0x0A, shardsMtx);
    gSPSegment(POLY_XLU_DISP++, 0x0B, crystalMtx);
    gDPPipeSync(POLY_XLU_DISP++);
    gDPSetEnvColor(POLY_XLU_DISP++, 128, 128, 128, 128);

    CLOSE_DISPS(gfxCtx, "../z_remix_level.c", __LINE__);
}

u32 RemixLevel_PlayHeapSize(GameState* state, u32 size) {
    s32 entrance = gSaveContext.save.entranceIndex;
    u32 maxFree;
    u32 free;
    u32 alloc;
    u32 avail;
    u32 extra;

    if ((entrance < 0) || (entrance >= ENTR_MAX) || (gEntranceTable[entrance].sceneId != SCENE_REMIX_ANCIENT)) {
        return size;
    }
    // The current game state heap is freed before the new one is allocated, so it counts as available.
    SystemArena_GetSizes(&maxFree, &free, &alloc);
    avail = maxFree + state->tha.size;
    if (avail <= size + REMIX_SYSTEM_HEAP_RESERVE) {
        return size;
    }
    extra = avail - size - REMIX_SYSTEM_HEAP_RESERVE;
    if (extra > REMIX_ANCIENT_EXTRA_HEAP) {
        extra = REMIX_ANCIENT_EXTRA_HEAP;
    }
    return size + extra;
}

void RemixLevel_GoToAncient(PlayState* play) {
    play->nextEntranceIndex = ENTR_REMIX_ANCIENT_0;
    play->transitionTrigger = TRANS_TRIGGER_START;
    play->transitionType = TRANS_TYPE_FADE_WHITE;
    gSaveContext.showTitleCard = true;
}

s32 RemixBoot_IsRequested(void) {
    return gRemixBootConfig.mode != 0;
}

/**
 * Same as Map Select's MapSelect_LoadGame with a fresh test save (adult Link), entering the Ancient Plateau
 * in the morning.
 */
void RemixBoot_Start(GameState* gameState) {
    s32 mode = gRemixBootConfig.mode;

    gRemixBootConfig.mode = 0;

    gSaveContext.fileNum = 0xFF;
    gSaveContext.save.linkAge = LINK_AGE_ADULT;
    Sram_InitDebugSave();
    // Save to file 1 if the player saves: file 0xFF would make Sram_WriteSave write outside the save slots.
    // (The website keeps these quick-boot sessions in their own save storage.)
    gSaveContext.fileNum = 0;
    gSaveContext.magicFillTarget = gSaveContext.save.info.playerData.magic;
    gSaveContext.magicCapacity = 0;
    gSaveContext.save.info.playerData.magicLevel = gSaveContext.save.info.playerData.magic = 0;

    gSaveContext.save.cutsceneIndex = CS_INDEX_NONE;
    gSaveContext.save.dayTime = gSaveContext.skyboxTime = CLOCK_TIME(9, 30);
    gSaveContext.gameMode = GAMEMODE_NORMAL;

    gSaveContext.buttonStatus[0] = gSaveContext.buttonStatus[1] = gSaveContext.buttonStatus[2] =
        gSaveContext.buttonStatus[3] = gSaveContext.buttonStatus[4] = BTN_ENABLED;
    gSaveContext.forceRisingButtonAlphas = gSaveContext.nextHudVisibilityMode = gSaveContext.hudVisibilityMode =
        gSaveContext.hudVisibilityModeTimer = 0;
    SEQCMD_STOP_SEQUENCE(SEQ_PLAYER_BGM_MAIN, 0);
    // Mode 2 (Hyrule Field) is for tests: the same quick boot into a level of the original game.
    gSaveContext.save.entranceIndex = (mode == REMIX_BOOT_HYRULE_FIELD) ? ENTR_HYRULE_FIELD_0 : ENTR_REMIX_ANCIENT_0;
    gSaveContext.respawnFlag = 0;
    gSaveContext.respawn[RESPAWN_MODE_DOWN].entranceIndex = ENTR_LOAD_OPENING;
    gSaveContext.seqId = (u8)NA_BGM_DISABLED;
    gSaveContext.natureAmbienceId = 0xFF;
    gSaveContext.showTitleCard = true;
    gWeatherMode = WEATHER_MODE_CLEAR;

    // (Not named `state`: SET_NEXT_GAMESTATE declares its own `state`, and `GameState* state = state;` would set
    // the next game state on a garbage pointer, ending the game loop on a black screen.)
    gameState->running = false;
    SET_NEXT_GAMESTATE(gameState, Play_Init, PlayState);
}
