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
 *   - The Ember Shrine's draw config (level 2): the same glow, the circuit lines of each stage of its trial
 *     (segments 0x09-0x0B: dim blue until the stage's switch flag is set, then burning orange) and the rune ring
 *     turning over the altar (0x0F), faster once the trial is done.
 *   - The Seeker's Shrine's draw config (level 3): what the Lens of Truth shows (0x09: the invisible bridge) and
 *     takes away (0x0A: the fake wall), each tool's circuit lines once its chest is opened (0x0E's table).
 *   - The Seeker's Shrine's trial: Link goes in with nothing but his sword and shield (his items wait outside, and
 *     come back when he leaves; what he finds inside stays inside).
 *   - Travel to the levels from the Remix menu, and the website's "boot straight into a level" options.
 */

#include "remix_level.h"

#include "array_count.h"
#include "environment.h"
#include "game.h"
#include "gfx.h"
#include "interface.h"
#include "inventory.h"
#include "item.h"
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
#include "assets/scenes/remix/ember/ember_room_0.h"
#include "assets/scenes/remix/seeker/seeker_room_0.h"

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

/**
 * Color of a stage's circuit lines: dim blue until its switch flag is set, then pulsing orange.
 */
static Gfx* RemixLevel_ShrineStageColor(PlayState* play, s32 flag, f32 wave) {
    Gfx* dl = GRAPH_ALLOC(play->state.gfxCtx, 3 * sizeof(Gfx));

    gDPPipeSync(dl);
    if (Flags_GetSwitch(play, flag)) {
        gDPSetPrimColor(dl + 1, 0, 0, 255, 150 - (s32)(wave * 30.0f), 40, 235 - (s32)(wave * 20.0f));
    } else {
        gDPSetPrimColor(dl + 1, 0, 0, 40, 90, 150, 110);
    }
    gSPEndDisplayList(dl + 2);
    return dl;
}

void RemixLevel_DrawConfigShrine(PlayState* play) {
    GraphicsContext* gfxCtx = play->state.gfxCtx;
    u32 frames = play->gameplayFrames;
    f32 wave = Math_SinS((s16)(frames * 0x2C0));
    s32 done = Flags_GetSwitch(play, SHRINE_FLAG_KINDLE);
    Gfx* cyan = GRAPH_ALLOC(gfxCtx, 3 * sizeof(Gfx));
    Gfx* orange = GRAPH_ALLOC(gfxCtx, 3 * sizeof(Gfx));
    Gfx* scroll = Gfx_TexScroll(gfxCtx, (128 - ((frames * 3) % 128)) % 128, 0, 32, 32);
    Gfx* stage1 = RemixLevel_ShrineStageColor(play, SHRINE_FLAG_EYE, wave);
    Gfx* stage2 = RemixLevel_ShrineStageColor(play, SHRINE_FLAG_BLOCK, wave);
    Gfx* stage3 = RemixLevel_ShrineStageColor(play, SHRINE_FLAG_KINDLE, wave);
    Mtx* ringMtx;

    gDPPipeSync(cyan);
    gDPSetPrimColor(cyan + 1, 0, 0, 70, 215 + (s32)(wave * 25.0f), 255, 190 + (s32)(wave * 40.0f));
    gSPEndDisplayList(cyan + 2);
    gDPPipeSync(orange);
    gDPSetPrimColor(orange + 1, 0, 0, 255, 150 - (s32)(wave * 30.0f), 40, 230 - (s32)(wave * 40.0f));
    gSPEndDisplayList(orange + 2);

    Matrix_Push();
    Matrix_Translate(SHRINE_RING_X, SHRINE_RING_Y + Math_SinS((s16)(frames * 0x200)) * 10.0f, SHRINE_RING_Z,
                     MTXMODE_NEW);
    Matrix_RotateY(frames * (done ? 0.05f : 0.01f), MTXMODE_APPLY);
    ringMtx = MATRIX_FINALIZE(gfxCtx, "../z_remix_level.c", __LINE__);
    Matrix_Pop();

    OPEN_DISPS(gfxCtx, "../z_remix_level.c", __LINE__);

    gSPSegment(POLY_OPA_DISP++, 0x08, cyan);
    gSPSegment(POLY_OPA_DISP++, 0x0C, orange);
    gSPSegment(POLY_OPA_DISP++, 0x0D, scroll);
    gSPSegment(POLY_OPA_DISP++, 0x09, stage1);
    gSPSegment(POLY_OPA_DISP++, 0x0A, stage2);
    gSPSegment(POLY_OPA_DISP++, 0x0B, stage3);
    gSPSegment(POLY_OPA_DISP++, 0x0F, ringMtx);
    gDPPipeSync(POLY_OPA_DISP++);
    gDPSetEnvColor(POLY_OPA_DISP++, 128, 128, 128, 128);

    gSPSegment(POLY_XLU_DISP++, 0x08, cyan);
    gSPSegment(POLY_XLU_DISP++, 0x0C, orange);
    gSPSegment(POLY_XLU_DISP++, 0x0D, scroll);
    gSPSegment(POLY_XLU_DISP++, 0x09, stage1);
    gSPSegment(POLY_XLU_DISP++, 0x0A, stage2);
    gSPSegment(POLY_XLU_DISP++, 0x0B, stage3);
    gSPSegment(POLY_XLU_DISP++, 0x0F, ringMtx);
    gDPPipeSync(POLY_XLU_DISP++);
    gDPSetEnvColor(POLY_XLU_DISP++, 128, 128, 128, 128);

    CLOSE_DISPS(gfxCtx, "../z_remix_level.c", __LINE__);
}

/**
 * Coming back out of a shrine, Link is launched up out of its hole in the Ancient Plateau (grotto exits return to
 * where Door_Ana sent Link down; this sets that when he got there some other way).
 */
static void RemixLevel_SetShrineReturn(f32 x, f32 y, f32 z, s16 yaw) {
    RespawnData* r = &gSaveContext.respawn[RESPAWN_MODE_RETURN];

    r->pos.x = x;
    r->pos.y = y;
    r->pos.z = z;
    r->yaw = yaw;
    r->playerParams = PLAYER_PARAMS(PLAYER_START_MODE_GROTTO, PLAYER_START_BG_CAM_DEFAULT);
    r->entranceIndex = ENTR_REMIX_ANCIENT_0;
    r->roomIndex = 0;
    r->data = 0;
    r->tempSwchFlags = r->tempCollectFlags = 0;
}

static void RemixLevel_GoDown(PlayState* play, s16 entranceIndex) {
    play->nextEntranceIndex = entranceIndex;
    play->transitionTrigger = TRANS_TRIGGER_START;
    play->transitionType = TRANS_TYPE_FADE_BLACK;
    gSaveContext.showTitleCard = true;
}

void RemixLevel_GoToShrine(PlayState* play) {
    RemixLevel_SetShrineReturn(ANCIENT_SHRINE_HOLE_X, ANCIENT_SHRINE_HOLE_Y, ANCIENT_SHRINE_HOLE_Z,
                               ANCIENT_SHRINE_HOLE_YAW);
    RemixLevel_GoDown(play, ENTR_REMIX_SHRINE_0);
}

void RemixLevel_GoToSeeker(PlayState* play) {
    RemixLevel_SetShrineReturn(ANCIENT_SEEKER_HOLE_X, ANCIENT_SEEKER_HOLE_Y, ANCIENT_SEEKER_HOLE_Z,
                               ANCIENT_SEEKER_HOLE_YAW);
    RemixLevel_GoDown(play, ENTR_REMIX_SEEKER_0);
}

/**
 * Branch to `dl` when `show`, else nothing: a one-command list the room's lists call through a segment.
 */
static Gfx* RemixLevel_Switch(PlayState* play, Gfx* dl, s32 show) {
    Gfx* sw = GRAPH_ALLOC(play->state.gfxCtx, sizeof(Gfx));

    if (show) {
        gSPBranchList(sw, dl);
    } else {
        gSPEndDisplayList(sw);
    }
    return sw;
}

void RemixLevel_DrawConfigSeeker(PlayState* play) {
    GraphicsContext* gfxCtx = play->state.gfxCtx;
    u32 frames = play->gameplayFrames;
    f32 wave = Math_SinS((s16)(frames * 0x2C0));
    s32 lens = play->actorCtx.lensActive;
    s32 found[3];
    Gfx* cyan = GRAPH_ALLOC(gfxCtx, 3 * sizeof(Gfx));
    Gfx* orange = GRAPH_ALLOC(gfxCtx, 3 * sizeof(Gfx));
    Gfx* ghost = GRAPH_ALLOC(gfxCtx, 3 * sizeof(Gfx));
    Gfx* tools = GRAPH_ALLOC(gfxCtx, 9 * sizeof(Gfx));
    Gfx* scroll = Gfx_TexScroll(gfxCtx, (128 - ((frames * 3) % 128)) % 128, 0, 32, 32);
    Gfx* reveal = RemixLevel_Switch(play, seeker_room_0DL_reveal_xlu, lens);
    Gfx* fake = RemixLevel_Switch(play, seeker_room_0DL_fake_opa, !lens);
    Mtx* ringMtx;
    s32 i;

    found[0] = Flags_GetTreasure(play, SEEKER_TREASURE_HOVER);
    found[1] = Flags_GetTreasure(play, SEEKER_TREASURE_LENS);
    found[2] = Flags_GetTreasure(play, SEEKER_TREASURE_HOOK);

    gDPPipeSync(cyan);
    gDPSetPrimColor(cyan + 1, 0, 0, 70, 215 + (s32)(wave * 25.0f), 255, 190 + (s32)(wave * 40.0f));
    gSPEndDisplayList(cyan + 2);
    gDPPipeSync(orange);
    gDPSetPrimColor(orange + 1, 0, 0, 255, 150 - (s32)(wave * 30.0f), 40, 230 - (s32)(wave * 40.0f));
    gSPEndDisplayList(orange + 2);
    gDPPipeSync(ghost); // the Lens's violet
    gDPSetPrimColor(ghost + 1, 0, 0, 190, 120, 255, 150 + (s32)(wave * 50.0f));
    gSPEndDisplayList(ghost + 2);
    for (i = 0; i < 3; i++) {
        gDPPipeSync(&tools[3 * i]);
        if (found[i]) {
            gDPSetPrimColor(&tools[3 * i + 1], 0, 0, 255, 150 - (s32)(wave * 30.0f), 40, 235 - (s32)(wave * 20.0f));
        } else {
            gDPSetPrimColor(&tools[3 * i + 1], 0, 0, 40, 90, 150, 110);
        }
        gSPEndDisplayList(&tools[3 * i + 2]);
    }

    Matrix_Push();
    Matrix_Translate(SEEKER_RING_X, SEEKER_RING_Y + Math_SinS((s16)(frames * 0x200)) * 10.0f, SEEKER_RING_Z,
                     MTXMODE_NEW);
    Matrix_RotateY(frames * (found[2] ? 0.03f : 0.008f), MTXMODE_APPLY);
    ringMtx = MATRIX_FINALIZE(gfxCtx, "../z_remix_level.c", __LINE__);
    Matrix_Pop();

    OPEN_DISPS(gfxCtx, "../z_remix_level.c", __LINE__);

    gSPSegment(POLY_OPA_DISP++, 0x08, cyan);
    gSPSegment(POLY_OPA_DISP++, 0x0C, orange);
    gSPSegment(POLY_OPA_DISP++, 0x0D, scroll);
    gSPSegment(POLY_OPA_DISP++, 0x09, reveal);
    gSPSegment(POLY_OPA_DISP++, 0x0A, fake);
    gSPSegment(POLY_OPA_DISP++, 0x0B, ghost);
    gSPSegment(POLY_OPA_DISP++, 0x0E, tools);
    gSPSegment(POLY_OPA_DISP++, 0x0F, ringMtx);
    gDPPipeSync(POLY_OPA_DISP++);
    gDPSetEnvColor(POLY_OPA_DISP++, 128, 128, 128, 128);

    gSPSegment(POLY_XLU_DISP++, 0x08, cyan);
    gSPSegment(POLY_XLU_DISP++, 0x0C, orange);
    gSPSegment(POLY_XLU_DISP++, 0x0D, scroll);
    gSPSegment(POLY_XLU_DISP++, 0x09, reveal);
    gSPSegment(POLY_XLU_DISP++, 0x0A, fake);
    gSPSegment(POLY_XLU_DISP++, 0x0B, ghost);
    gSPSegment(POLY_XLU_DISP++, 0x0E, tools);
    gSPSegment(POLY_XLU_DISP++, 0x0F, ringMtx);
    gDPPipeSync(POLY_XLU_DISP++);
    gDPSetEnvColor(POLY_XLU_DISP++, 128, 128, 128, 128);

    CLOSE_DISPS(gfxCtx, "../z_remix_level.c", __LINE__);
}

// ---- the Seeker's Shrine's trial: nothing but the sword going in ----

typedef struct RemixTrial {
    s32 active;
    Inventory inventory;
    ItemEquips equips;
    u8 isMagicAcquired;
    u8 isDoubleMagicAcquired;
    s8 magic;
} RemixTrial;

static RemixTrial sTrial;

static void RemixTrial_Begin(void) {
    Inventory* inv = &gSaveContext.save.info.inventory;
    ItemEquips* eq = &gSaveContext.save.info.equips;
    SavePlayerData* pd = &gSaveContext.save.info.playerData;
    s32 i;

    sTrial.inventory = *inv;
    sTrial.equips = *eq;
    sTrial.isMagicAcquired = pd->isMagicAcquired;
    sTrial.isDoubleMagicAcquired = pd->isDoubleMagicAcquired;
    sTrial.magic = pd->magic;
    sTrial.active = true;

    // No items, no boots but the plain ones; swords, shields and tunics stay.
    for (i = 0; i < ARRAY_COUNT(inv->items); i++) {
        inv->items[i] = ITEM_NONE;
    }
    for (i = 0; i < ARRAY_COUNT(inv->ammo); i++) {
        inv->ammo[i] = 0;
    }
    inv->equipment &= ~(0xF << (EQUIP_TYPE_BOOTS * 4));
    inv->equipment |= (1 << EQUIP_INV_BOOTS_KOKIRI) << (EQUIP_TYPE_BOOTS * 4);
    for (i = 1; i < 4; i++) {
        eq->buttonItems[i] = ITEM_NONE;
        eq->cButtonSlots[i - 1] = SLOT_NONE;
    }
    if ((eq->buttonItems[0] < ITEM_SWORD_KOKIRI) || (eq->buttonItems[0] > ITEM_SWORD_BIGGORON)) {
        eq->buttonItems[0] = ITEM_NONE;
    }
    eq->equipment =
        (eq->equipment & ~(0xF << (EQUIP_TYPE_BOOTS * 4))) | (EQUIP_VALUE_BOOTS_KOKIRI << (EQUIP_TYPE_BOOTS * 4));

    // Magic for the Lens of Truth, found inside: a full meter (the HUD grows and fills it).
    pd->isMagicAcquired = true;
    pd->magicLevel = 0;
    gSaveContext.magicFillTarget = (pd->isDoubleMagicAcquired + 1) * MAGIC_NORMAL_METER;
}

static void RemixTrial_End(void) {
    SavePlayerData* pd = &gSaveContext.save.info.playerData;

    gSaveContext.save.info.inventory = sTrial.inventory;
    gSaveContext.save.info.equips = sTrial.equips;
    pd->isMagicAcquired = sTrial.isMagicAcquired;
    pd->isDoubleMagicAcquired = sTrial.isDoubleMagicAcquired;
    if (pd->isMagicAcquired) {
        pd->magic = CLAMP_MAX(sTrial.magic, (pd->isDoubleMagicAcquired + 1) * MAGIC_NORMAL_METER);
        pd->magicLevel = 0;
        gSaveContext.magicFillTarget = pd->magic;
    } else {
        pd->magicLevel = 0;
        pd->magic = 0;
        gSaveContext.magicCapacity = 0;
        gSaveContext.magicState = MAGIC_STATE_IDLE;
    }
    sTrial.active = false;
}

void RemixLevel_OnSceneStart(PlayState* play) {
    if (play->sceneId == SCENE_REMIX_SEEKER) {
        if (!sTrial.active) {
            RemixTrial_Begin();
        }
    } else if (sTrial.active) {
        RemixTrial_End();
    }
}

void RemixLevel_TrialSaveSwap(void) {
    if (sTrial.active) {
        Inventory inv = gSaveContext.save.info.inventory;
        ItemEquips eq = gSaveContext.save.info.equips;
        u8 acquired = gSaveContext.save.info.playerData.isMagicAcquired;

        gSaveContext.save.info.inventory = sTrial.inventory;
        gSaveContext.save.info.equips = sTrial.equips;
        gSaveContext.save.info.playerData.isMagicAcquired = sTrial.isMagicAcquired;
        sTrial.inventory = inv;
        sTrial.equips = eq;
        sTrial.isMagicAcquired = acquired;
    }
}

void RemixLevel_TrialForget(void) {
    sTrial.active = false;
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
    gSaveContext.save.entranceIndex = (mode == REMIX_BOOT_HYRULE_FIELD) ? ENTR_HYRULE_FIELD_0
                                      : (mode == REMIX_BOOT_SHRINE)     ? ENTR_REMIX_SHRINE_0
                                      : (mode == REMIX_BOOT_SEEKER)     ? ENTR_REMIX_SEEKER_0
                                                                        : ENTR_REMIX_ANCIENT_0;
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
    // The shrines' pedestals take Link up through their holes in the Ancient Plateau, as a grotto's exit would
    // (Door_Ana sets this when Link goes down the hole himself).
    if (mode == REMIX_BOOT_SHRINE) {
        RemixLevel_SetShrineReturn(ANCIENT_SHRINE_HOLE_X, ANCIENT_SHRINE_HOLE_Y, ANCIENT_SHRINE_HOLE_Z,
                                   ANCIENT_SHRINE_HOLE_YAW);
    } else if (mode == REMIX_BOOT_SEEKER) {
        RemixLevel_SetShrineReturn(ANCIENT_SEEKER_HOLE_X, ANCIENT_SEEKER_HOLE_Y, ANCIENT_SEEKER_HOLE_Z,
                                   ANCIENT_SEEKER_HOLE_YAW);
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
