// Web Remix objects (see REMIX.md). Included right after the game's own objects.

beginseg
    name "object_remix_model"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/objects/object_remix_model/object_remix_model.o"
    number 6
endseg

// The Magnesis Rune Link holds up (tools/remix/make_slate.py, from a fal-made model). Get-item objects must stay
// under 8 KB (the player's get-item buffer).
beginseg
    name "object_remix_slate"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/objects/object_remix_slate/object_remix_slate.o"
    number 6
endseg

// The Lodestone Shrine's moving pieces (tools/remix/make_magnet_parts.py), for ovl_En_Remix_Magnet
beginseg
    name "object_remix_magnet"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/objects/object_remix_magnet/object_remix_magnet.o"
    number 6
endseg

// The Temple of Two Truths' pieces (tools/remix/make_time_parts.py), for ovl_En_Remix_Time
beginseg
    name "object_remix_time"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/objects/object_remix_time/object_remix_time.o"
    number 6
endseg

// The Shrine of Seven Years' pieces (tools/remix/make_years_parts.py), for ovl_En_Remix_Years
beginseg
    name "object_remix_years"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/objects/object_remix_years/object_remix_years.o"
    number 6
endseg
