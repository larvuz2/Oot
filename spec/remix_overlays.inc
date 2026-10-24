// Web Remix actor overlays (see REMIX.md). Included right after the game's own
// overlays so their VRAM follows the other actors (not the segment-6 objects).

beginseg
    name "ovl_En_Remix_Model"
    compress
    flags OVERLAY
    include "$(BUILD_DIR)/src/overlays/actors/ovl_En_Remix_Model/z_en_remix_model.o"
endseg

beginseg
    name "ovl_En_Remix_Magnet"
    compress
    flags OVERLAY
    include "$(BUILD_DIR)/src/overlays/actors/ovl_En_Remix_Magnet/z_en_remix_magnet.o"
endseg

beginseg
    name "ovl_En_Remix_Time"
    compress
    flags OVERLAY
    include "$(BUILD_DIR)/src/overlays/actors/ovl_En_Remix_Time/z_en_remix_time.o"
endseg

beginseg
    name "ovl_En_Remix_Years"
    compress
    flags OVERLAY
    include "$(BUILD_DIR)/src/overlays/actors/ovl_En_Remix_Years/z_en_remix_years.o"
endseg

beginseg
    name "ovl_En_Remix_Wind"
    compress
    flags OVERLAY
    include "$(BUILD_DIR)/src/overlays/actors/ovl_En_Remix_Wind/z_en_remix_wind.o"
endseg

beginseg
    name "ovl_En_Remix_Abyss"
    compress
    flags OVERLAY
    include "$(BUILD_DIR)/src/overlays/actors/ovl_En_Remix_Abyss/z_en_remix_abyss.o"
endseg
