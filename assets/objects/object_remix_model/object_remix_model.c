// "Remix Crystal": a small hand-made model so the custom-asset pipeline works
// out of the box. Vertex-coloured, untextured, drawn without lighting.
// Model units: the actor draws it at scale 0.03, so 1000 units = 30 game units.

#include "object_remix_model.h"
#include "gfx.h"

Vtx gRemixModelVtx[] = {
    // upper half (gold)
    VTX(0, 1500, 0, 0, 0, 255, 245, 190, 255), // 0 apex
    VTX(800, 0, 0, 0, 0, 240, 180, 40, 255),   // 1 +x
    VTX(0, 0, 800, 0, 0, 200, 140, 20, 255),   // 2 +z
    VTX(-800, 0, 0, 0, 0, 240, 180, 40, 255),  // 3 -x
    VTX(0, 0, -800, 0, 0, 255, 210, 70, 255),  // 4 -z
    // lower half (teal)
    VTX(0, -1500, 0, 0, 0, 20, 90, 110, 255), // 5 apex
    VTX(800, 0, 0, 0, 0, 60, 210, 200, 255),  // 6 +x
    VTX(0, 0, 800, 0, 0, 40, 170, 180, 255),  // 7 +z
    VTX(-800, 0, 0, 0, 0, 60, 210, 200, 255), // 8 -x
    VTX(0, 0, -800, 0, 0, 90, 235, 220, 255), // 9 -z
};

Gfx gRemixModelDL[] = {
    gsDPPipeSync(),
    gsDPSetCycleType(G_CYC_1CYCLE),
    gsSPTexture(0, 0, 0, G_TX_RENDERTILE, G_OFF),
    gsSPClearGeometryMode(G_LIGHTING | G_FOG | G_CULL_BOTH | G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR),
    gsSPSetGeometryMode(G_SHADE | G_SHADING_SMOOTH | G_ZBUFFER),
    gsDPSetCombineMode(G_CC_SHADE, G_CC_SHADE),
    gsDPSetRenderMode(G_RM_AA_ZB_OPA_SURF, G_RM_AA_ZB_OPA_SURF2),
    gsSPVertex(gRemixModelVtx, 10, 0),
    gsSP2Triangles(0, 2, 1, 0, 0, 3, 2, 0),
    gsSP2Triangles(0, 4, 3, 0, 0, 1, 4, 0),
    gsSP2Triangles(5, 6, 7, 0, 5, 7, 8, 0),
    gsSP2Triangles(5, 8, 9, 0, 5, 9, 6, 0),
    gsSPEndDisplayList(),
};
