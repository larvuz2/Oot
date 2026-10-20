# Ocarina of Time — Web Remix

This repository is a remix of the [zeldaret/oot](https://github.com/zeldaret/oot) decompilation
(full upstream history is kept, so upstream improvements can be merged in). On top of the
decomp it adds a **static web player** that runs the game in the browser, plus a **CI
pipeline** that turns changes to the C source into a playable build on the site.

```
 C source (src/, include/, spec, …)
        │  GitHub Actions: make setup + make  (.github/workflows/remix.yml)
        ▼
 build/<version>/oot-<version>.z64  ──flips──▶  web/patches/oot-<version>-<region>.bps  (+ manifest.json)
                                                        │  commit → Netlify redeploys web/
                                                        ▼
 Player's browser: their own ROM ─▶ verify (MD5) ─▶ decompress (Yaz0) ─▶ apply BPS ─▶ N64 emulator (WebAssembly)
```

No Nintendo data is stored in this repo or on the site. Players bring a dump of a cartridge
or disc they own; it is processed locally in their browser and never uploaded. What gets
published is only the *difference* between the retail game and your remix — the same way
ROM hacks have always been distributed.

## Play

Open the site, drop in a ROM (`.z64`, `.n64` or `.v64`, or zipped as `.zip`/`.7z`/`.rar`) of any version the decomp supports
(N64 NTSC 1.0/1.1/1.2 JP/US, PAL 1.0/1.1, the GameCube releases, the debug ROMs, iQue). The
ROM is remembered in the browser, so next time it is one click.

If a remix build has been published for that version you can choose **Remix** or
**Original game**. Each keeps its own save file. Controls are listed on the page and can be
remapped from the emulator's menu; gamepads and touch controls work.

### If the game freezes

Two N64 emulator cores ship with the site: **Standard** (Mupen64Plus-Next, the default) and
**Compatibility** (ParaLLEl N64). Both are EmulatorJS 4.2.3 WebAssembly builds, and each has
crash bugs on some games. The page watches the emulator: if it crashes or stops producing
frames, a panel offers **Try the other emulator** (remembered from then on), **Restart game**,
and **Copy details for a bug report**. You can also pick the core on the start screen.

## The Remix menu (in the remix build)

Press **D-pad Up** during gameplay (keyboard: **T**) to open the Web Remix menu. The world freezes
while it is open. Move with the D-pad or stick, **A** selects, **B** goes back, **Start** closes.

| Option | What it does |
|---|---|
| **Go to: Ancient Plateau (NEW)** | Takes you to the new level built for this remix (see [The Ancient Plateau](#the-ancient-plateau-a-new-level)). |
| **Warp anywhere (Map Select)** | Opens the developers' Map Select screen, which ships unused in every version of the game. Pick any area and press **A**. **B** switches child/adult, **Z**/**R** change the time of day / cutscene. Your current save and items carry over. |
| **Fully equipped: ON/OFF** | ON gives every item, sword, shield, tunic, boots and upgrade, all medallions, songs and stones, 20 hearts with double defense, double magic and 500 rupees. OFF puts back exactly what you had. (If you save while it is ON, the full kit is saved.) |
| **Spawn characters/objects** | Places an actor in front of Link. **FAVORITES** lists ~60 well-known enemies, bosses, characters and props by name (plus the custom 3D model); **ALL ACTORS** lists all 428 actors by their decomp name. Left/right picks (hold **R** to jump 10); **SPAWN!** places it, **PLAY AS!** makes you that character (see below); **Params** sets the actor's parameter value (hold **R** for ×0x10, **Z** for ×0x100). The 3D data the actor needs is loaded on the fly. |
| **Biome: Hyrule Field / Frozen Tundra** | Swaps Hyrule Field for a snowy copy of it and takes you there: snow-covered ground, frosted blue rock, icy fog and light, and falling snow. Pick it again to switch back. Everything else (exits, enemies, music, the minimap) stays Hyrule Field's. See [Biomes](#biomes). |
| **Play as custom model: ON/OFF** | You become the custom 3D model (your Character Studio character): it replaces Link's look and plays its idle or walk animation as you move. Link's moves, sword hitboxes and items all still work, just invisibly. |

Things to know about spawning:
- Spawned actors disappear when you change rooms, because rooms swap their 3D data out.
- Enemies won't spawn in a room you have already cleared, and some areas run out of object memory.
- A few actors only work outdoors or only in dungeons (the menu says so).
- Bosses and story characters expect their own arena or cutscene and may misbehave or crash.
  Make a save state first (the emulator's save button) if you want to experiment.

### Playing as any character

**Spawn → pick a character → PLAY AS!** turns you into any of the 428 actors in the game. The character
is spawned as a "puppet" that follows Link's position and facing every frame and keeps playing its own
animations from the game's code. You still move with Link's controls and abilities (run, jump, roll,
sword), and Link is drawn invisibly. The puppet's hitboxes and its talk/target prompts are switched off,
so it can't hurt you or start conversations with you. It comes back automatically after room changes.
Open the menu and choose **Stop playing as …** to go back to Link.

Limits: the character's own AI still picks its animations (an enemy may play attack animations because
"Link" is right on top of it), and its special moves (e.g. Epona's gallop) aren't mapped to your
buttons. Bosses and story characters may misbehave outside their own scenes.

### Skipping cutscenes

In the remix build, press **D-pad Right** (keyboard **H**) during a cutscene to skip it. A cutscene that leads
somewhere (the next scene, the next cutscene) jumps straight there; others just end. Skipping story scenes can
skip what they set up, so save first. Holding **Space** fast-forwards instead.

## The Ancient Plateau: a new level

A whole new area, built the way the game's own levels are: an ancient-technology valley where stone merges
with glowing Sheikah machinery.

It sits in the same world as Hyrule Field and reuses as much of it as it can: the field's grass, dirt-path and
cliff textures, its sky and its time-of-day lighting and fog, and the field's own trees, bushes, liftable rocks,
bomb-able boulders and butterflies. What is new is the layout and the monument.

- **The field**: rolling grass with winding dirt paths, broken stone pillars with glowing bands, Hyrule Field's
  trees, bushes and rocks, and three Beamos watching from the hills.
- **The mountains**: a ring of cliffs, in Hyrule Field's rock, that closes the valley.
- **The plaza**: a raised stone circle with glowing circuit lines (light pulses flow along them), Sheikah eye
  emblems, golden torches at each staircase, eight glowing monoliths around it and four Armos "guardians" on it.
  Two of them wake up.
- **The Ancient Spire**: a stepped pedestal and an engraved obelisk with glowing rune panels and orange light
  slits, crowned by a ring that spins around a hovering crystal, with rock shards orbiting it. Two Gossip Stones
  stand at its feet.

It follows the time of day (sunrise, noon, sunset, night: the glow stands out at night) and has its own title
card, music (Sheik's theme) and footstep sounds.

How to get there:
- On the site: **Jump into the new level** starts a test save as adult Link right there.
- From your own save: Remix menu → **Go to: Ancient Plateau**.
- In Map Select: the last entry, **NEW:ANCIENT PLATEAU**.

How it's made: `tools/remix/make_level.py` builds the whole level procedurally, with textures for the ancient
technology in `tools/remix/biome_art/ancient/` (made with GPT Image): terrain, paths cut into it, mountains, plaza, Spire,
props, collision, lighting, actors and the title card. It writes `assets/scenes/remix/ancient/`, which is
committed and compiled like any scene. Moving and glowing parts are animated by the scene's draw config in
`src/code/z_remix_level.c` (glow colors, flowing light, the ring, crystal and shards). Change the script and run
`python3 tools/remix/make_level.py` (it needs `numpy`, `pillow` and `shapely`); add `--preview level.json` to
dump the geometry for a quick three.js look.

Hyrule Field's assets come from your ROM, so they are never committed. After `make setup`,
`tools/remix/link_level_assets.py` finds the field's grass, dirt and cliff textures (by replaying its display
lists and measuring what each texture covers), converts them to the level's format and points the level at them
and at the field's light settings through `build/VERSION/assets/scenes/remix/ancient/ancient_hf.h`. Without it the
level builds with its own look-alike textures and lights. The remix build runs it for you.

The remix build also checks the level:
- its log compares the level's memory use with Hyrule Field's (the level has to fit where the field fits);
- `tools/remix/smoke_test.py` boots the ROM straight into the level in the website's own emulator (headless
  Chromium), runs for about 25 seconds of game time with Link running forward, and checks that the picture is not
  blank and keeps changing. It also reads the console's memory from the emulator and reports where each of the
  game's threads is and whether one crashed (with the function name). If the level shows nothing, it boots
  Hyrule Field the same quick way, and the game normally, to tell a level problem from a boot problem. The
  screenshots are attached to the run (`smoke-screenshots`).

## Character Studio: make your own character

`studio.html` on the site (linked from the top of the player) turns a few words into a character
you can play as:

1. **Describe it** ("a zombie", "a robot chef"). An LLM (Gemini 2.5 Flash via fal's OpenRouter endpoint)
   rewrites it into a detailed prompt: T-pose, full body, front view, N64 Ocarina of Time style, family-friendly.
   It also picks a character type that decides the walk animation. **GPT Image 2.5** then draws four concepts.
2. **Pick one → Build 3D character.** **Meshy 7.1** turns the picture into a textured 3D model (~3 min),
   then **Meshy rigging** adds a humanoid skeleton plus an idle animation and a walk that suits the type
   (lurching zombie, mummy stagger, sneaky walk, proud strut…) (~1 min). You get a spinnable, animated preview.
3. **Add to game.** Commits `assets/remix_character/character.json` (links to the animated models). The
   Remix build runs `tools/remix/glb_to_oot.py`, which turns the character into N64 graphics: about
   450 vertex-coloured triangles with baked lighting, posed at 3 idle and 8 walk frames (~140 KB). Then it
   builds the ROM and publishes the patch. In the game, use **Play as custom model** or **Spawn → Custom 3D Model**
   (the spawned one walks after Link).

The repo ships with a zombie made this way, so the custom model works before you make your own.

### Setting up the Studio on Netlify

In Netlify: **Site configuration → Environment variables → Add a variable**, then redeploy:

| Variable | Needed | What it is |
|---|---|---|
| `FAL_KEY` | yes | Your [fal.ai](https://fal.ai/dashboard/keys) API key. It stays on the server and is never sent to browsers. |
| `STUDIO_PASSWORD` | yes | Any password. The Studio asks for it once per browser, so visitors can't spend your fal credits. |
| `GITHUB_TOKEN` | optional | A [fine-grained token](https://github.com/settings/personal-access-tokens/new) for `larvuz2/Oot` with **Contents: Read and write**. Lets **Add to game** commit by itself; without it the Studio downloads `character.json` for you to upload to `assets/remix_character/` on GitHub. |

Without `FAL_KEY` on Netlify the Studio still works if you paste your own fal key into it (kept only in
that browser). One character costs roughly a dollar or two in fal credits (4 images + 3D + rigging).

### Custom 3D models by hand

You can also make the model yourself. `object_remix_model` holds one display list per animation frame
(`gRemixModelFrameDLs`, idle frames first) and `gRemixModelInfo` (frame counts and height). The easiest
route is any animated, skinned GLB: export an idle and a walk clip and run

```bash
pip install numpy pillow fast-simplification
python3 tools/remix/glb_to_oot.py --idle idle.glb --walk walk.glb --name "My Hero"
```

To add more spawnable things, add an actor at the end of `include/tables/actor_table.h` (and an object
at the end of `include/tables/object_table.h`), list the new segments in `spec/remix_overlays.inc` / `spec/remix_objects.inc`, and run
`python3 tools/remix/gen_actor_db.py` to refresh the menu's list (`FAVORITES` in that script controls
the named shortlist).

## Biomes

The **Biome** option in the Remix menu turns Hyrule Field into the **Frozen Tundra**. How it's built:

1. `tools/remix/biome_art/` holds the art made with GPT Image (ground and rock tiles, a landmark concept)
   for three biomes: `tundra`, `swamp` and `autumn`. Only the tundra is wired in so far.
2. After `make setup`, `tools/remix/make_biome.py` copies the extracted Hyrule Field scene to
   `extracted/<version>/assets/scenes/remix/tundra/` and restyles the copy: opaque grass textures become the
   snow tile, dark rocky ones the rock tile, other textures, palettes and vertex colors are mapped to snow and
   frosty blue-grey (water and signs are kept), and the light settings get icy fog. Its log lists what happened
   to each texture.
3. The Makefile notices the copy and builds it in (`REMIX_HAS_TUNDRA=1`, `spec/remix_scenes.inc`).
4. In game, `RemixBiome_OverrideScene` (called from `Play_SpawnScene`) loads the copy's scene file whenever
   Hyrule Field loads with the biome on, and the game's own (unused) snowfall effect is switched on.

The CI build runs all of this. If the copy fails to build, the ROM is built without it and the run shows a
"Biome dropped" warning. `python3 tools/remix/test_make_biome.py` tests the script without a ROM.

Things to know: grass bushes and trees are separate objects, so they stay green for now; the copy only
exists in ROMs built by this repo, never in git (it is made from your ROM's data).

## Deploy on Netlify

1. In Netlify: **Add new site → Import an existing project → GitHub → `larvuz2/Oot`**.
   (Or use <https://app.netlify.com/start/deploy?repository=https://github.com/larvuz2/Oot>.)
2. Leave the build settings alone — `netlify.toml` already says: base directory `web`,
   publish `.` (i.e. `web/`), no real build command.
3. Deploy. Every push to `main` redeploys automatically.

The site is plain static files (HTML/CSS/ES modules + a vendored copy of EmulatorJS 4.2.3 and
its mupen64plus-next core), so any static host works too.

To try it locally: `python3 -m http.server -d web 8000` and open <http://localhost:8000>.

## Ship your own changes (the remix loop)

The decomp needs a base ROM to extract textures, models, audio and text from before it can
compile. Give GitHub Actions access to **your own** dump:

1. Put the ROM somewhere private that has a direct download link (a `.zip` containing the ROM
   is fine). Recommended: the N64 **NTSC 1.0 (US)** or **NTSC 1.2** cartridge dump.
2. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**
   - `BASEROM_URL` — the direct download link.
   - `BASEROM_AUTH_HEADER` *(optional)* — a full header line if the link needs one, e.g.
     `Authorization: Bearer <token>`.
3. Optional repository **variables** (same page, *Variables* tab):
   - `REMIX_TITLE` — the name shown on the site, e.g. `Hero Mode Remix`.
   - `REMIX_MAKE_FLAGS` — extra `make` flags, e.g. `NON_MATCHING=1` or `DEBUG_FEATURES=1`.

Now every push to `main` that touches the game source runs **Remix build**, which:
identifies the ROM (`tools/web/identify_rom.py`), runs `make setup` and `make`, diffs the
result against `baserom-decompressed.z64` with Floating IPS (`tools/web/make_patch.py`,
round-trip verified), and commits `web/patches/*.bps` + `manifest.json`. Netlify picks that
commit up and the site offers the new remix. You can also run it by hand from the
**Actions** tab (*Remix build → Run workflow*).

Without the secret the workflow just prints a notice and exits green.

### Building locally instead

Follow the upstream instructions in [README.md](README.md) (Linux/WSL, `make setup`, `make`),
then publish the result yourself:

```bash
make setup VERSION=ntsc-1.0
make VERSION=ntsc-1.0 REGION=US COMPARE=0
python3 tools/web/make_patch.py --version ntsc-1.0 --region US \
    --target build/ntsc-1.0/oot-ntsc-1.0.z64 --flips path/to/flips --title "My Remix"
git add web/patches && git commit -m "Publish remix" && git push
```

### Where things live

| Want to change… | Look in |
|---|---|
| Link's movement, items, combat | `src/overlays/actors/ovl_player_actor/z_player.c` |
| Enemies, NPCs, objects (427 actors) | `src/overlays/actors/ovl_*/` |
| Title screen, file select, game states | `src/overlays/gamestates/` |
| Engine: camera, collision, rendering, save data | `src/code/` |
| Scenes/rooms/actor spawn lists, models, textures | `assets/xml/` + `extracted/<version>/` after setup |
| What goes into the ROM and in which order | `spec/` |
| Debug "REG" tuning values (e.g. `R_RUN_SPEED_LIMIT`) | `include/regs.h` |

Upstream notes: building with `COMPARE=0` is required once the ROM no longer matches retail;
`NON_MATCHING=1` is recommended for larger mods (see the top of the `Makefile`).
`docs/` has the decomp team's guides.

## What was added to the decomp

| Path | Purpose |
|---|---|
| `web/` | The site: `index.html`, `css/`, `js/` (ROM pipeline + UI), `patches/`, `emulatorjs/` (vendored, GPL-3.0) |
| `web/js/rom.js`, `yaz0.js`, `md5.js`, `n64crc.js` | Browser port of `tools/decompress_baserom.py` (byte-identical output) |
| `web/js/bps.js`, `crc32.js` | BPS patcher |
| `web/js/versions.js` | Generated by `tools/web/gen_versions.py` from `baseroms/*/` |
| `web/tests/` | Tests: the JS pipeline vs. the decomp's own Python tooling (`crunch64`, `ipl3checksum`, Floating IPS) |
| `tools/web/` | `gen_versions.py`, `identify_rom.py`, `make_patch.py` |
| `.github/workflows/remix.yml` | ROM build → patch → commit |
| `.github/workflows/web-tests.yml` | Runs `web/tests` |
| `netlify.toml` | Netlify config |
| `src/code/z_remix_menu.c`, `include/remix_menu.h` | In-game Remix menu (hooked into `src/code/z_play.c`) |
| `src/code/z_remix_actor_db.inc`, `tools/remix/gen_actor_db.py` | Spawnable actor list: object each actor needs + display names |
| `src/overlays/actors/ovl_En_Remix_Model/`, `assets/objects/object_remix_model/`, `spec/remix_*.inc` | Custom 3D model actor and object (frame-animated) |
| `src/code/z_actor.c` (3 lines) | Lets "play as" draw instead of Link |
| `web/studio.html`, `web/js/studio*.js`, `web/netlify/functions/studio.mjs` | Character Studio and its fal/GitHub backend |
| `tools/remix/glb_to_oot.py`, `assets/remix_character/` | Animated GLB → N64 frames converter, and the current Studio character |
| `tools/remix/make_level.py`, `assets/scenes/remix/ancient/`, `src/code/z_remix_level.c`, `include/remix_level.h` | The Ancient Plateau: level generator, generated level, its draw config and the boot-into-level switch. Registered in `include/tables/scene_table.h`, `entrance_table.h`, `include/scene.h` (draw config), `z_scene_table.c`, `z_bgcheck.c` (collision memory), Map Select and `z_title.c` |
| `src/code/z_demo.c` (skip) | D-pad Right skips cutscenes |
| `tools/remix/link_level_assets.py`, `tools/remix/test_link_level_assets.py` | Lets the Ancient Plateau use Hyrule Field's textures and lights from your ROM at build time, and its test |
| `tools/remix/smoke_test.py`, `tools/remix/smoke_capture.mjs`, `web/js/boot.js` | Emulator smoke test in CI (the website's player in headless Chromium); the site's "Jump into the new level" switch |
| `tools/remix/make_biome.py`, `tools/remix/biome_art/`, `spec/remix_scenes.inc` | Biomes: restyled copy of Hyrule Field (Frozen Tundra); 1 line in `Play_SpawnScene`, 2 in `include/segment_symbols.h`, 6 in the `Makefile` |

## Updating from upstream

```bash
git remote add upstream https://github.com/zeldaret/oot.git   # once
git pull upstream main
python3 tools/web/gen_versions.py   # if baseroms/ changed
```

## Going further

The emulator approach gets the *real* compiled game running everywhere today. A native web
port (compiling the decomp's C straight to WebAssembly with a graphics/audio layer instead of
emulating an N64) would unlock widescreen, 60 fps and mods beyond the N64's limits; it's a large
project, and this repo is a good base for it. The [REA](https://github.com/morluto/rea)
reverse-engineering toolkit is not needed for this pipeline — the decomp already provides
readable source — but it can help with analysing other binaries or emulator behaviour.

## Credits

- [zeldaret/oot](https://github.com/zeldaret/oot) — the decompilation this is built from.
- [EmulatorJS](https://github.com/EmulatorJS/EmulatorJS) 4.2.3 with the
  [mupen64plus-next](https://github.com/EmulatorJS/mupen64plus-libretro-nx) core — GPL-3.0, see
  `web/emulatorjs/LICENSE`.
- [Floating IPS](https://github.com/Alcaro/Flips) — patch creation in CI.

Unofficial fan project, not affiliated with or endorsed by Nintendo.
