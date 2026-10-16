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

Open the site, drop in a ROM (`.z64`, `.n64` or `.v64`) of any version the decomp supports
(N64 NTSC 1.0/1.1/1.2 JP/US, PAL 1.0/1.1, the GameCube releases, the debug ROMs, iQue). The
ROM is remembered in the browser, so next time it is one click.

If a remix build has been published for that version you can choose **Remix** or
**Original game**. Each keeps its own save file. Controls are listed on the page and can be
remapped from the emulator's menu; gamepads and touch controls work.

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
