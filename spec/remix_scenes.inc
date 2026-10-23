// Web Remix scenes (see REMIX.md). Included right after the game's own scenes.

// New level: the Ancient Plateau (tools/remix/make_level.py, committed in assets/scenes/remix/ancient/)
beginseg
    name "ancient_scene"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/ancient/ancient_scene.o"
    number 2
endseg

beginseg
    name "ancient_room_0"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/ancient/ancient_room_0.o"
    number 3
endseg

beginseg
    name "g_pn_remix_ancient"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/ancient/ancient_title.o"
endseg

// Level 2: the Ember Shrine (tools/remix/make_shrine.py, committed in assets/scenes/remix/ember/)
beginseg
    name "ember_scene"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/ember/ember_scene.o"
    number 2
endseg

beginseg
    name "ember_room_0"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/ember/ember_room_0.o"
    number 3
endseg

beginseg
    name "g_pn_remix_ember"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/ember/ember_title.o"
endseg

// Biomes:
// tools/remix/make_biome.py copies Hyrule Field into extracted/VERSION/assets/scenes/remix/tundra/ after
// `make setup`; the Makefile then sets REMIX_HAS_TUNDRA=1. Without that step the ROM is built without biomes.

#if REMIX_HAS_TUNDRA
beginseg
    name "tundra_scene"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/tundra/tundra_scene.o"
    number 2
endseg

beginseg
    name "tundra_room_0"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/tundra/tundra_room_0.o"
    number 3
endseg
#endif
