// Web Remix biome scenes (see REMIX.md). Included right after the game's own scenes.
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
