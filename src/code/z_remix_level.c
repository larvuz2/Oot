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
 *       0x0E  a table: [0] texture scroll of the floating island's stream and waterfall (falling water), then one
 *             entry per group of scenery (bushes, stones): the group's display list near the camera, nothing
 *             further away (the fog hides the little models there anyway, and a slow device has less to draw)
 *       0x0F  matrix of the rocks circling the floating island
 *   - Travel to the level from the Remix menu, and the website's "boot straight into the new level" option.
 */

#include "remix_level.h"

#include "environment.h"
#include "game.h"
#include "gfx.h"
#include "play_state.h"
#include "player.h"
#include "save.h"
#include "scene.h"
#include "seqcmd.h"
#include "sequence.h"
#include "sram.h"
#include "sys_matrix.h"
#include "transition.h"
#include "z_lib.h"

#include "assets/scenes/remix/ancient/ancient_room_0.h"

#define ANCIENT_SPIRE_TOP_Y ((f32)ANCIENT_RING_Y)

#if ANCIENT_DECOR_SECTORS > 0
static const s16 sDecorSectors[ANCIENT_DECOR_SECTORS][4] = ANCIENT_DECOR_SECTOR_LIST; // x, z, radius, on the island
static Gfx* const sDecorSectorDLs[ANCIENT_DECOR_SECTORS] = ANCIENT_DECOR_SECTOR_DLS;
#endif

/**
 * Segment 0x0E's table: the falling water's scroll, then each scenery group's display list or nothing, by how far
 * the camera is from it.
 */
static Gfx* RemixLevel_AncientTable(PlayState* play, Gfx* water) {
    Gfx* table = GRAPH_ALLOC(play->state.gfxCtx, (1 + ANCIENT_DECOR_SECTORS) * sizeof(Gfx));
#if ANCIENT_DECOR_SECTORS > 0
    f32 eyeX = play->view.eye.x;
    f32 eyeZ = play->view.eye.z;
    s32 i;
#endif

    gSPBranchList(&table[0], water);
#if ANCIENT_DECOR_SECTORS > 0
    for (i = 0; i < ANCIENT_DECOR_SECTORS; i++) {
        f32 dx = eyeX - sDecorSectors[i][0];
        f32 dz = eyeZ - sDecorSectors[i][1];
        // the floating island stands out against the sky: its bushes stay a little further
        f32 reach =
            (sDecorSectors[i][3] ? ANCIENT_DECOR_DRAW_DIST * 3 / 2 : ANCIENT_DECOR_DRAW_DIST) + sDecorSectors[i][2];

        if (SQ(dx) + SQ(dz) < SQ(reach)) {
            gSPBranchList(&table[1 + i], sDecorSectorDLs[i]);
        } else {
            gSPEndDisplayList(&table[1 + i]);
        }
    }
#endif
    return table;
}

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
    Mtx* islandMtx;
    Gfx* water;

    // Glow colors breathe slowly; orange runs half a beat behind cyan.
    gDPPipeSync(cyan);
    gDPSetPrimColor(cyan + 1, 0, 0, 70, 225 + (s32)(wave * 25.0f), 255, glowA);
    gSPEndDisplayList(cyan + 2);
    gDPPipeSync(orange);
    gDPSetPrimColor(orange + 1, 0, 0, 255, 150 - (s32)(wave * 30.0f), 40, 230 - (s32)(wave * 40.0f));
    gSPEndDisplayList(orange + 2);

    // Light pulses travel along the strips (32-texel texture, scrolled in quarter texels).
    scroll = Gfx_TexScroll(gfxCtx, (128 - ((frames * 3) % 128)) % 128, 0, 32, 32);
    // Water falls: its 32-texel texture moves along t, a texel and a half per frame.
    water = RemixLevel_AncientTable(play, Gfx_TexScroll(gfxCtx, 0, (frames * 6) % 128, 32, 32));

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

    Matrix_Translate(ANCIENT_ISLAND_X, ANCIENT_ISLAND_Y + Math_SinS((s16)(frames * 0x180)) * 18.0f, ANCIENT_ISLAND_Z,
                     MTXMODE_NEW);
    Matrix_RotateY(frames * 0.006f, MTXMODE_APPLY);
    islandMtx = MATRIX_FINALIZE(gfxCtx, "../z_remix_level.c", __LINE__);

    Matrix_Pop();

    OPEN_DISPS(gfxCtx, "../z_remix_level.c", __LINE__);

    gSPSegment(POLY_OPA_DISP++, 0x08, cyan);
    gSPSegment(POLY_OPA_DISP++, 0x0C, orange);
    gSPSegment(POLY_OPA_DISP++, 0x0D, scroll);
    gSPSegment(POLY_OPA_DISP++, 0x09, ringMtx);
    gSPSegment(POLY_OPA_DISP++, 0x0A, shardsMtx);
    gSPSegment(POLY_OPA_DISP++, 0x0B, crystalMtx);
    gSPSegment(POLY_OPA_DISP++, 0x0E, water);
    gSPSegment(POLY_OPA_DISP++, 0x0F, islandMtx);
    gDPPipeSync(POLY_OPA_DISP++);
    gDPSetEnvColor(POLY_OPA_DISP++, 128, 128, 128, 128);

    gSPSegment(POLY_XLU_DISP++, 0x08, cyan);
    gSPSegment(POLY_XLU_DISP++, 0x0C, orange);
    gSPSegment(POLY_XLU_DISP++, 0x0D, scroll);
    gSPSegment(POLY_XLU_DISP++, 0x09, ringMtx);
    gSPSegment(POLY_XLU_DISP++, 0x0A, shardsMtx);
    gSPSegment(POLY_XLU_DISP++, 0x0B, crystalMtx);
    gSPSegment(POLY_XLU_DISP++, 0x0E, water);
    gSPSegment(POLY_XLU_DISP++, 0x0F, islandMtx);
    gDPPipeSync(POLY_XLU_DISP++);
    gDPSetEnvColor(POLY_XLU_DISP++, 128, 128, 128, 128);

    CLOSE_DISPS(gfxCtx, "../z_remix_level.c", __LINE__);
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
    if (mode == REMIX_BOOT_ISLAND_VIEW || mode == REMIX_BOOT_POOL_VIEW) {
        // Tests: start somewhere else in the level, the way Link comes back after a void out (z_player.c).
        RespawnData* r = &gSaveContext.respawn[RESPAWN_MODE_RETURN];
        s32 island = (mode == REMIX_BOOT_ISLAND_VIEW);

        r->pos.x = island ? ANCIENT_VIEW_ISLAND_X : ANCIENT_VIEW_POOL_X;
        r->pos.y = island ? ANCIENT_VIEW_ISLAND_Y : ANCIENT_VIEW_POOL_Y;
        r->pos.z = island ? ANCIENT_VIEW_ISLAND_Z : ANCIENT_VIEW_POOL_Z;
        r->yaw = island ? ANCIENT_VIEW_ISLAND_YAW : ANCIENT_VIEW_POOL_YAW;
        r->playerParams = PLAYER_PARAMS(PLAYER_START_MODE_IDLE, PLAYER_START_BG_CAM_DEFAULT);
        r->entranceIndex = ENTR_REMIX_ANCIENT_0;
        r->roomIndex = 0;
        r->data = 0;
        r->tempSwchFlags = r->tempCollectFlags = 0;
        gSaveContext.respawnFlag = RESPAWN_MODE_RETURN + 1;
    }
    gSaveContext.seqId = (u8)NA_BGM_DISABLED;
    gSaveContext.natureAmbienceId = 0xFF;
    gSaveContext.showTitleCard = true;
    gWeatherMode = WEATHER_MODE_CLEAR;

    // (Not named `state`: SET_NEXT_GAMESTATE declares its own `state`, and `GameState* state = state;` would set
    // the next game state on a garbage pointer, ending the game loop on a black screen.)
    gameState->running = false;
    SET_NEXT_GAMESTATE(gameState, Play_Init, PlayState);
}
