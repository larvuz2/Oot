// Web Remix actor overlays (see REMIX.md). Included right after the game's own
// overlays so their VRAM follows the other actors (not the segment-6 objects).

beginseg
    name "ovl_En_Remix_Model"
    compress
    flags OVERLAY
    include "$(BUILD_DIR)/src/overlays/actors/ovl_En_Remix_Model/z_en_remix_model.o"
endseg
