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

// Level 3: the Seeker's Shrine (tools/remix/make_seeker.py, committed in assets/scenes/remix/seeker/)
beginseg
    name "seeker_scene"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/seeker/seeker_scene.o"
    number 2
endseg

beginseg
    name "seeker_room_0"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/seeker/seeker_room_0.o"
    number 3
endseg

beginseg
    name "g_pn_remix_seeker"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/seeker/seeker_title.o"
endseg

// Level 4: the Lodestone Shrine (tools/remix/make_magnet.py, committed in assets/scenes/remix/magnet/)
beginseg
    name "magnet_scene"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/magnet/magnet_scene.o"
    number 2
endseg

beginseg
    name "magnet_room_0"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/magnet/magnet_room_0.o"
    number 3
endseg

beginseg
    name "g_pn_remix_magnet"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/magnet/magnet_title.o"
endseg

// Level 5: the Forge Shrine (tools/remix/make_forge.py, committed in assets/scenes/remix/forge/)
beginseg
    name "forge_scene"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/forge/forge_scene.o"
    number 2
endseg

beginseg
    name "forge_room_0"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/forge/forge_room_0.o"
    number 3
endseg

beginseg
    name "g_pn_remix_forge"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/forge/forge_title.o"
endseg

// Level 6: the Temple of Two Truths (tools/remix/make_time.py, committed in assets/scenes/remix/time/)
beginseg
    name "time_scene"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/time/time_scene.o"
    number 2
endseg

beginseg
    name "time_room_0"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/time/time_room_0.o"
    number 3
endseg

beginseg
    name "g_pn_remix_time"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/time/time_title.o"
endseg

// Level 7: the Shrine of Seven Years (tools/remix/make_years.py, committed in assets/scenes/remix/years/)
beginseg
    name "years_scene"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/years/years_scene.o"
    number 2
endseg

beginseg
    name "years_room_0"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/years/years_room_0.o"
    number 3
endseg

beginseg
    name "g_pn_remix_years"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/years/years_title.o"
endseg

// Level 8: the Shrine of the Upside-Down Wind (tools/remix/make_wind.py, committed in assets/scenes/remix/wind/)
beginseg
    name "wind_scene"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/wind/wind_scene.o"
    number 2
endseg

beginseg
    name "wind_room_0"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/wind/wind_room_0.o"
    number 3
endseg

beginseg
    name "g_pn_remix_wind"
    compress
    romalign 0x1000
    include "$(BUILD_DIR)/assets/scenes/remix/wind/wind_title.o"
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
