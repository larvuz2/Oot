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
| **Warp anywhere (Map Select)** | Opens the developers' Map Select screen, which ships unused in every version of the game. Pick any area and press **A**. **B** switches child/adult, **Z**/**R** change the time of day / cutscene. Your current save and items carry over. |
| **Fully equipped: ON/OFF** | ON gives every item, sword, shield, tunic, boots and upgrade, all medallions, songs and stones, 20 hearts with double defense, double magic and 500 rupees. OFF puts back exactly what you had. (If you save while it is ON, the full kit is saved.) |
| **Spawn characters/objects** | Places an actor in front of Link. **FAVORITES** lists ~60 well-known enemies, bosses, characters and props by name (plus the custom 3D model); **ALL ACTORS** lists all 428 actors by their decomp name. Left/right picks (hold **R** to jump 10); **Params** sets the actor's parameter value (hold **R** for ×0x10, **Z** for ×0x100). The 3D data the actor needs is loaded on the fly. |

Things to know about spawning:
- Spawned actors disappear when you change rooms, because rooms swap their 3D data out.
- Enemies won't spawn in a room you have already cleared, and some areas run out of object memory.
- A few actors only work outdoors or only in dungeons (the menu says so).
- Bosses and story characters expect their own arena or cutscene and may misbehave or crash.
  Make a save state first (the emulator's save button) if you want to experiment.

### Custom 3D models

"Custom 3D Model" (first in FAVORITES) spawns the actor `En_Remix_Model`, which draws the display
list `gRemixModelDL` from the new object `object_remix_model`. The repo ships a small spinning
crystal there. To use your own model:

1. In Blender, install [fast64](https://github.com/Fast-64/fast64) and set the game to *Ocarina of Time*.
2. Build or import your model, then export it as a **Display List** (C) with the name `gRemixModel`.
   Keep it small: each object has to fit in the area's spare object memory (a few hundred KB at most).
3. Replace `assets/objects/object_remix_model/object_remix_model.c` (and the `.h`) with the export.
   Use `#include "ultra64.h"` and `#include "gfx.h"` at the top of the `.c`. Textures can be committed
   as PNGs next to it, named like `myTex.rgba16.png`, and included as `myTex.rgba16.inc.c`, the same
   way the other committed objects in `assets/objects/` do it.
4. Make sure the display list is called `gRemixModelDL` (or change the name in
   `src/overlays/actors/ovl_En_Remix_Model/z_en_remix_model.c`). The actor draws it at scale 0.03,
   spinning and bobbing; the spawn menu's **Params** value is a size in percent (0 = 100%).
5. Push. The Remix build workflow compiles it and the site picks up the new patch.

To add more spawnable things, add an actor at the end of `include/tables/actor_table.h` (and an object
at the end of `include/tables/object_table.h`), list the new segments in `spec/remix.inc`, and run
`python3 tools/remix/gen_actor_db.py` to refresh the menu's list (`FAVORITES` in that script controls
the named shortlist).

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
| `src/overlays/actors/ovl_En_Remix_Model/`, `assets/objects/object_remix_model/`, `spec/remix.inc` | Custom 3D model actor and object |

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
