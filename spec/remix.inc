// Web Remix additions (see REMIX.md). Kept in their own file so upstream
// spec changes merge cleanly.

beginseg
    name "ovl_En_Remix_Model"
    compress
    flags OVERLAY
    include "$(BUILD_DIR)/src/overlays/actors/ovl_En_Remix_Model/z_en_remix_model.o"
endseg

beginseg
    name "object_remix_model"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/objects/object_remix_model/object_remix_model.o"
    number 6
endseg
