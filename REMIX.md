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

### If the game runs slowly (tablets, phones)

The start screen has two switches, remembered on that device:
- **Performance mode** (on by default on iPads, iPhones and Android): the emulator draws at the console's own
  resolution (320x240 instead of 640x480), skips copying the depth buffer back to the console in software (only
  the sun's lens flare uses it) and texture level-of-detail, and repeats a frame when the next one is late. The
  picture is a little softer; the game and its music keep up better. Settings you change in the emulator's own
  menu still win.
- **Speed meter** (also on by default on tablets and phones): a small box over the game showing the emulation
  speed (100% = the console's 60 frames a second; below that the game and music slow down). Tap it to hide it.

Both can also be set in the address: `?perf=1` / `?perf=0`, `?speed=1` / `?speed=0`.

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
cliff textures, its sky and its time-of-day lighting and fog, and the field's own trees, bush and rock models,
butterflies. What is new is the layout, the monument, the town and the sky island.

- **The field**: rolling grass with winding dirt paths, broken stone pillars with glowing bands, Hyrule Field's
  trees and rocks and clumps of glowing bushes.
- **The arrival**: the road where Link arrives runs under the Desert Colossus's stone arch (restyled), between
  Sheikah obelisks and torches, past a giant rock with a glowing Sheikah eye watching over it.
- **The sky island**: north of the town, a floating island with rocks circling it. Zora's River's own waterfall
  (Bg_Spot03_Taki, with its sound) pours over its edge into a pool on the field, where a Zora waits. On top:
  a big chest with Biggoron's Sword, Hyrule Field's trees, and the game's bushes, flowers and stones. Floating
  rocks spiral up to it: hop across the small gaps (run off the edge) and climb the ledges. From the island,
  Zora's River's rope bridge leads to an islet with a Heart Piece. More rocks drift high over the town.
- **The mountains**: a ring of cliffs, in Hyrule Field's rock, that closes the valley.
- **The plaza**: a raised stone circle with glowing circuit lines (light pulses flow along them), Sheikah eye
  emblems, golden torches at each staircase and eight glowing monoliths around it.
- **The town**: houses, a barn, sheds, silos, wells, a watchtower and a shop borrowed from Kakariko Village,
  Lon Lon Ranch and Kokiri Forest, plus Lake Hylia's lab and ruins, the Colossus's ruined walls and a Gerudo
  watchtower, restyled in the Plateau's stone and teal (roofs of teal slate, windows that glow), around the
  plaza; a Lon Lon arch is the town gate on the road in and a second one spans a street. A dirt ring road
  circles the plaza, a main street (with a torch at the corner) runs into each quarter and lanes lead to every
  front door. Inside the town the ground is the Lost Woods' mossy stone; hedges of glowing blue bushes (the
  game's bush, recolored) line every street, road and house, with flower beds, pebbles and rocks. Townspeople
  from the Market and Kakariko on the plaza and at their doors, a stroller and two dogs on the walk around the
  plaza, and rupees in the pots inside the houses.
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
`src/code/z_remix_level.c` (glow colors, flowing light and water, the ring, crystal and shards, the rocks
circling the island). Change the script and run
`python3 tools/remix/make_level.py` (it needs `numpy`, `pillow` and `shapely`); add `--preview level.json` to
dump the geometry for a quick three.js look.

Hyrule Field's assets come from your ROM, so they are never committed. After `make setup`,
`tools/remix/link_level_assets.py` finds the field's grass, dirt and cliff textures (by replaying its display
lists and measuring what each texture covers), converts them to the level's format and points the level at them
and at the field's light settings through `build/VERSION/assets/scenes/remix/ancient/ancient_hf.h`. Without it the
level builds with its own look-alike textures and lights. The same script borrows the town's ground (the Lost
Woods) and the waterfall's water (Zora's River), and copies the game's bush (gameplay_field_keep) with its
texture recolored to glow (without the ROM's assets the bushes are the game's green ones). The remix build runs
it for you.

The town's buildings come from your ROM too. `tools/remix/survey_scenes.py` lists and pictures every chunk of
the game's town scenes (that is how the buildings were picked), and at build time `tools/remix/make_town.py`
copies the chosen ones onto the plots of `tools/remix/town_plan.py`, turned to face the Spire, with their
collision, and restyles every texture they use (`tools/remix/restyle.py`: same size and detail, the Plateau's
colors). It writes `build/VERSION/assets/scenes/remix/ancient/ancient_town.h` and the data it points to; the
remix build uploads pictures of the result (`town-preview`). Without a ROM the plaza stands alone. Memory: the
Plateau keeps 900 KB for objects instead of 1000 KB (its objects take about 893 KB), which leaves room in
actor memory for the townspeople. The bushes, flowers and rocks are drawn by the room itself (Hyrule Field's
models; each hedge, clump or flower bed is one matrix), and so are the floating rocks (one shared model), so
they cost no actor memory; the bushes can't be cut nor the rocks lifted. They are kept cheap to draw: the
models are split into their material and their shape (`decor_models.inc.c`, from `link_level_assets.py`), so a
group of copies sets texture and render mode once; the copies are grouped in squares of the valley, and the draw
config switches each group on only within 1500 units of the camera (segment 0x0E; the game's own bushes, which
are actors, vanish at 1200). `tools/remix/frame_cost.py` (run by the remix build) counts what a frame asks of the
emulator: vertices, triangles, texture loads, render-mode changes and matrices, for the whole level, for the
scenery seen from the plaza and the south gate, and for the game's own areas next to it. The child Market
has the shops and stalls a market would want, but it is a prerendered background (only a rough, untextured
floor and wall shape exists as 3D), so none of it can be borrowed.

The remix build also checks the level:
- its log compares the level's memory use with Hyrule Field's (the level has to fit where the field fits);
- `tools/remix/smoke_test.py` boots the ROM straight into the level in the website's own emulator (headless
  Chromium), runs for about 25 seconds of game time with Link running forward, and checks that the picture is not
  blank and keeps changing. It also reads the console's memory from the emulator and reports where each of the
  game's threads is and whether one crashed (with the function name), and how much actor memory is left (next to
  Hyrule Field's, booted the same way). If the level shows nothing, it boots
  Hyrule Field the same quick way, and the game normally, to tell a level problem from a boot problem. It also
  runs the level in the website's performance mode, and prints each run's emulation speed (CI's software GPU is
  slow, so compare the runs with each other). The screenshots are attached to the run (`smoke-screenshots`).

## Level 2: the Ember Shrine

A shrine in the style of Breath of the Wild, under the Ancient Plateau: west of the south road where Link arrives,
across from the eye rock, a round platform with rings of orange light holds the game's grotto hole. Walk into it
and Link drops into the shrine, the way he falls into a grotto. On the website, **2 · Ember Shrine** (or the
key <kbd>2</kbd> on the start screen) starts a test save there; from your own save, Remix menu &rarr;
*Go to: Ember Shrine*.

The arrival chamber is the cow grotto's, rebuilt in the Plateau's Sheikah stone: a cow in its corner, pots of
arrows, and the glowing pedestal that takes Link back up through the hole. The hall holds the trial, *Carry the
Flame*, built only from the game's own puzzle pieces (about five minutes):

1. **Wake the shrine.** A Sheikah eye watches over the arch you came through: an arrow in it (an eye switch)
   lights the great brazier in the middle of the hall.
2. **Push.** A stone block sits on a track by the east gallery. At the end of the track it rests on a floor
   switch: the gallery's brazier lights, and the block is the step up to the gallery.
3. **Kindle.** Three torches must burn at once (each burns 13 seconds). Arrows shot through a burning brazier
   catch fire and light what they hit: two torches are on the floor, one is on the west gallery, which nobody can
   reach (a parapet stops shots from below; shoot across the hall from the east gallery).
4. The big chest drops onto the altar with a Heart Container, and every circuit line in the shrine burns orange.

Each stage's circuit lines (from the eye to the brazier, from the switch up to the gallery, from the torches to
the altar) glow dim blue until that stage is done, then orange. Puzzle state is saved like a dungeon's.

How it is made: `tools/remix/make_shrine.py` generates `assets/scenes/remix/ember/` (committed; the scene is
`ember_scene` because the game already has a `shrine_scene`, the Temple of Time's outside) with the Plateau's
own textures and display-list tools, and checks the trial's shots (each arrow line clear, the west torch out of
reach from the floor). The pieces are the game's: torches (Obj_Syokudai, golden and timed wooden), the eye switch
and floor switch (Obj_Switch), the push block (Obj_Oshihiki, tinted the shrine's teal), the falling big chest
(En_Box), fire walls as flame pillars (Bg_Hidan_Curtain), pots (Obj_Tsubo), the cow (En_Cow), the grotto hole
(Door_Ana, whose list of grottos gained the shrine) and the grotto exit (`ENTR_RETURN_GROTTO`). Kept cheap to
draw: about 1,000 triangles in five room chunks, each material set once per chunk, no per-copy matrices
(`frame_cost.py`: 976 triangles, 41 texture loads, 81 render-mode changes for the whole shrine; Hyrule Field's
room is 1,639 / 241 / 336). The draw config (`RemixLevel_DrawConfigShrine` in `src/code/z_remix_level.c`)
reads the trial's switch flags for the circuit lines and turns the rune ring over the altar. The smoke test boots
into the shrine too (pictures, crash and memory checks).

## Level 3: the Seeker's Shrine

A second shrine under the Plateau, by the west road (its hole sits on the same kind of orange-ringed platform).
On the website, **3 · Seeker's Shrine** (or the key <kbd>3</kbd>); from your own save, Remix menu &rarr;
*Go to: Seeker's Shrine*.

**You go in with nothing but your sword and shield.** Like Eventide Island in Breath of the Wild, the shrine keeps
your items while you are inside (swords, shields and tunics stay; you get a full magic meter) and gives them all
back as soon as you leave; what you find inside stays inside, but the Heart Container at the end is yours to keep.
Saving inside writes your own items to the save, not the trial's. The trial, *The Lost Tools* (the game's own
pieces only):

1. **Empty-handed.** A crystal switch stands on a pedestal out in the chasm, out of reach. Pick up a pot, lock on to
   the crystal and throw: the fire in a doorway in the west wall dies down for 20 seconds. Inside the alcove: the
   **Hover Boots** (and a crystal to strike to get back out). Equip them from the pause menu.
2. **The gap.** A low stone lintel hangs over the gap: a running jump hits it and drops into the pit
   (stairs lead back up). With them he floats across to the island: the **Lens of Truth** (pots of magic nearby).
3. **The unseen.** Through the Lens a zigzag bridge appears over the chasm (it is there all along, only invisible);
   and one stretch of the far wall is not a wall at all (a glowing line runs into it). Behind it: the **Hookshot**.
4. **The ascent.** A crystal by the shelf raises hookshot posts out of the shelf and the balcony: pull up to the
   shelf, then to the balcony, then float across to the altar on the hover boots. The Heart Container, and the
   pedestal home.

Each tool's circuit lines glow orange once its chest is opened.

How it is made: `tools/remix/make_seeker.py` generates `assets/scenes/remix/seeker/` with the Ember Shrine's tools
(`make_shrine.py`) and checks the hookshot reaches (the hookshot is 260 long) and the hover gaps. The pieces: the
targetable crystal switch and the plain one (Obj_Switch), a pot as the projectile (Obj_Tsubo), the fire in the
doorway (Bg_Hidan_Curtain), the chests (En_Box with GI_BOOTS_HOVER, GI_LENS_OF_TRUTH, GI_HOOKSHOT,
GI_HEART_CONTAINER), the rising hookshot posts (Obj_Hsblock), and floors with the game's "no jumping" property
(FLOOR_PROPERTY_9: Link steps off without jumping; the hover boots still carry him). The invisible bridge and the
fake wall are ordinary room geometry that the draw config (`RemixLevel_DrawConfigSeeker`) draws or hides each
frame from `lensActive`: the bridge's collision is always there, the fake wall has none. The items are taken and
given back by `RemixLevel_OnSceneStart` (called from `Play_Init`), with hooks in `z_sram.c`. About 750 triangles in
nine room chunks (`frame_cost.py`: 747 triangles, 55 texture loads, 108 render-mode changes).

## Level 4: the Lodestone Shrine (and a new item: Magnesis)

A third shrine under the Plateau, by the east road. On the website, **4 · Lodestone Shrine** (or the key
<kbd>4</kbd>); from your own save, Remix menu &rarr; *Go to: Lodestone Shrine*.

The shrine gives Link a rune from Breath of the Wild, **Magnesis**, then a trial that needs it (*The Iron Will*):

1. **The compass bridge.** A chasm fills the middle of the hall. On its pivot turns an L-shaped bridge that always
   links two neighbouring sides. A crystal switch at the edge of the south ledge and one at the north ledge turn it
   a quarter each time they are struck (south &rarr; east &rarr; north &rarr; west), carrying whoever stands on it.
   Stand on the bridge's tip and strike the crystal to ride it round. A floor switch on the east dock drops a chest
   onto the west dock: inside is the **Magnesis Rune**. Falling into the chasm voids you out.
2. **Magnesis.** Hold **L** (keyboard <kbd>E</kbd>) facing something made of iron: it glows pink and hangs in
   the air while you hold L. The stick swings it around Link and pushes it away or pulls it in, **C-Up / C-Down**
   lift and lower it, **C-Left / C-Right** turn it. Let go of L to drop it, or press **B** to fling it. A hint at
   the bottom of the screen shows the controls. (Magnesis works inside this shrine only.)
3. **Iron.** The north doorway is shut by an iron slab: pull it out. Beyond it, an iron crate goes onto the floor
   switch on top of a pillar Link can't climb; while it holds the switch down, a lift rides up to the balcony. The
   altar is across a gap: lift the iron girder off the floor, turn it and lay it across. An iron chest stands on top
   of a column, out of reach: bring it down too. At the altar: the Heart Container and a ring of light home.

The new item. The rune Link holds up is a model made with fal (the same endpoints as the Character Studio):
gpt-image made the picture of a slate with a magnet on it, Meshy turned it into a 3D model, and
`tools/remix/make_slate.py` bakes its face into a 32x48 texture and simplifies it to 178 triangles, into
`assets/objects/object_remix_slate/` (6.8 KB: get-item objects must fit the player's 8 KB buffer). It is a real
get-item: `GI_REMIX_MAGNESIS` (0x7E) in `include/item.h`, its draw entry `GID_REMIX_MAGNESIS` in `z_draw.c`, its row in
the player's get-item table (whose text id is now 16 bits) and its text box, id 0x7FA0, in
`assets/text/message_data.h` (the build would fail if the game used that id: message symbols are named after it).

How it is made: `tools/remix/make_magnet.py` generates `assets/scenes/remix/magnet/` with the Ember Shrine's tools and
checks the layout (the bridge clears the ledges and crystals as it turns, the crystals are in sword reach of its
tips, no gap can be jumped, nothing Magnesis must carry things onto can be climbed, the girder's ends land on both
sides of the gap). The moving pieces and Magnesis are a new actor, `ovl_En_Remix_Magnet`, drawing
`object_remix_magnet` (`tools/remix/make_magnet_parts.py`: textured iron with baked light, and collision for each
piece). Magnesis updates before the player (actor category BG) and takes the buttons it uses off the input, so Link
stands still while he holds something. Iron pieces fall and rest on the highest floor under any of their sample
points, press the floor switches they rest on (`DynaPolyActor_SetSwitchPressed`), ride the lift, and come back
to their start if they fall into the chasm. The game's own pieces: crystal switches that toggle and floor switches
(Obj_Switch), the chests (En_Box: GI_REMIX_MAGNESIS dropping on a switch flag, GI_RUPEE_GOLD on the column,
GI_HEART_CONTAINER), torches and the arrival chamber's cow. The draw config (`RemixLevel_DrawConfigMagnet`) lights
Magnesis's lines once the rune is found and the lift's while it runs. About 1030 triangles in seven room chunks.

## Level 5: the Forge Shrine (Magnesis and fire)

A fourth shrine under the Plateau, by the north road. On the website, **5 · Forge Shrine** (or the key <kbd>5</kbd>);
from your own save, Remix menu &rarr; *Go to: Forge Shrine*. The shrine lends Link Magnesis (hold L).

Built the way Breath of the Wild grows a puzzle: one new object, then more interactions and constraints in each
room rather than new mechanics. The object is an **iron fire basket**: Magnesis carries it, a burning torch sets it
alight, its flame lights the wooden torches it touches, and water puts it out. The trial, *The Iron Flame*:

1. **Introduce.** The basket stands by an eternal torch, already burning. Carry it to the wooden torch by the gate:
   the gate rises.
2. **Apply.** The next torch stands across a chasm Link can't cross. Float the burning basket over to it: a bridge
   rises out of the chasm.
3. **Combine.** Three timed torches stand on posts in a pool, and all three must burn at once (each burns about 13
   seconds). Link can't walk while he holds something, and the basket goes out if it drops into the water: find the
   one spot on the shore that reaches all three (it is marked), keep the flame above the water, be quick.
4. **Subvert.** The last torch is far out in a chasm, beyond Magnesis's reach. Hold the basket as far out as it
   goes and **fling** it (B): it flies on, onto the torch's platform. The Heart Container drops by the exit.

Every room has an eternal torch to rekindle the basket, and a basket that falls into a chasm comes back to the last
place it was over solid ground, so the trial can't be lost. Deku sticks and fire arrows light the torches too, as
they would anywhere in the game: other solutions are part of the fun.

How it is made: `tools/remix/make_forge.py` generates `assets/scenes/remix/forge/` and checks the layout (every
torch within Magnesis's reach of where Link can stand but the last, the pool's spot reaching all three posts, the
fling from the last ledge landing on the platform, nothing that can be jumped). The basket, the gates and the
bridge span are new kinds of `ovl_En_Remix_Magnet` (`MAGNET_BRAZIER`, `MAGNET_GATE`, `MAGNET_SPAN`, drawn from
`object_remix_magnet`). The basket's flame is a collider that hits like Din's Fire: wooden torches (Obj_Syokudai)
take it as they take a fire arrow, so the game's own torch logic does the rest (single torches, and the pool's
"light all three in time" group). Its fire is the torches' own flame model, with a point light. The pool is a real
water box (`make_shrine.py` writes them now). About 1160 triangles in seven room chunks.

## Level 6: the Temple of Two Truths (child and adult)

A fifth shrine under the Plateau, by the south road nearer the town. On the website, **6 · Temple of Two Truths**
(or the key <kbd>6</kbd>); from your own save, Remix menu &rarr; *Go to: Temple of Two Truths*. Inside, the temple
lends Link a kit for both his ages (the Ocarina of Time and the Song of Time, the boomerang, slingshot, Deku sticks,
bombs and Bombchus, the bow and fire arrows, Din's Fire and a full magic meter, the longshot, the Megaton Hammer, the
Mirror Shield, iron and hover boots); his own things, and the age he came in at, come back when he leaves.

One enormous round hall in sandstone, the way the Spirit Temple's are, and everything is in view from the entrance:
the bottomless pit and the dais in its middle under a hanging hourglass and its three turning rings, the golden
sphere on its pedestal, ring 1 (a stone band round the dais with four openings), four unlit torches at different
heights, a waterfall that flows **upwards**, the basin where the sun comes through the ceiling, a great statue in
the north wall (a locked mouth, an empty eye), the scale by its shoulder, a clock whose hand points to **CHILD** or
**ADULT**, and two identical pads on the dais, one blue, one orange.

**Time echo.** Play the Song of Time on the clock-plate in the middle of the dais: the hall comes back in the other
era, and Link with it, as a child on the blue pad or as an adult on the orange one. What he moves in the past stays
moved in the present. Some things grow over the years (a small block becomes a pillar), some decay (the child's
bridge to the dais and his ramp up the statue are ruins in the present, a block left in the drain wears away), some
don't change (the scale, the ring). In the past the golden sphere is a small golden seed.

1. **The sphere.** Hookshot to the lintel over the sphere: landing on the dais sinks its pedestal and the sphere
   falls into the pit (it comes back). A crystal hides under the pedestal: strike it (boomerang, an arrow) and the
   pedestal is locked. Push the sphere: it rolls down the curved track into ring 1's cradle, the plate there starts
   the ring turning, and the sphere is trapped in it.
2. **The four flames.** Four timed torches stand round the dais, each at its own height; each burns 8 seconds, and
   the ring's openings line up with them at different times (fire arrows through the openings is very hard). From
   the middle of the dais Din's Fire reaches them all at once. With all four burning the waterfall turns and falls,
   water fills the pit and the basin, and the sphere floats up in a bubble into the statue's head.
3. **Yesterday.** The sun falls on an old block in the basin: under water, worn, far too heavy. The inscription
   says *"What cannot be moved today may be moved yesterday."* As a child the basin is dry and the block small: push
   it into the sunbeam. Back in the present it has grown into a pillar standing in the light, a mirror on top that
   throws the sunlight onto the walkway. Stand in the light and raise the Mirror Shield towards the sun symbol over
   the way out: the statue's mouth opens.
4. **The first eye.** Inside the statue: a gap (longshot, or hover boots), stairs, a narrow bridge to the first
   eye. The sphere waits above a grate; the hammer switch drops it onto the eye's plate. The eye lights, the way out
   opens, a second eye opens on the statue's forehead: *"You have opened the way. But have you understood the
   truth?"* The sphere goes back to its pedestal; the chest is still nowhere.
5. **The truth.** As a child, push the old block out of the drain (in the present the water then won't rise). Send
   a Bombchu over the dais's south edge: it runs down the side onto a crystal only a blast wakes, and ring 1 turns
   backwards. Roll the sphere into the ring again: with no water to lift it, the ring throws it onto the scale's
   right pan up by the statue's shoulder. Longshot up there and step on the switch: the stone weight drops onto
   the left pan, the right pan lifts the sphere towards the second eye, and stops short. As a child, push the
   second small block onto the left pan: in the present it is a pillar, heavy enough to tip the scale all the way.
   The sphere rolls into the second eye, the statue awakes, the rings line up, and the chest falls onto the dais.

**The seed.** In the past the sphere is a seed the child can carry. Take it up the ramp (it stands in the past)
into the first eye and leave it there; in the present, turn the sunlight onto it with the Mirror Shield: it grows
into the sphere and the eye opens, phases 1 to 4 solved another way.

How it is made: `tools/remix/make_time.py` generates `assets/scenes/remix/time/` (the hall, the statue and its
inside) and checks the reaches it relies on; `tools/remix/time_plan.py` is the plan both it and
`tools/remix/make_time_parts.py` (the pieces, `object_remix_time`) read, and the latter writes it into the object's
header for the actor. `ovl_En_Remix_Time` does the moving parts: the age switch (the Song of Time as an Obj_Timeblock
listens for it, then `play->linkAgeOnLoad`, as the Temple of Time does, and an entrance whose spawn is the pad of
Link's new age), the water (the scene's water box, raised and lowered), the sunlight and the Mirror Shield, the
sphere's journey (kept in switch flags), the echo blocks (pushed like the game's blocks as a child, a pillar or a
worn block in the present), the ring, the scale, the bridge and ramp of the past, the inscriptions. The rest are the
game's own: crystal and floor switches (Obj_Switch), timed torches (Obj_Syokudai), the chest (En_Box).
`src/code/z_remix_level.c` lends the kit and keeps the age Link came in at; four new texts in
`assets/text/message_data.h`.

## Play on any device: your ROM in the cloud

Once a ROM is loaded, **Save to cloud** (under the Play buttons) keeps a copy in the site's own storage (Netlify
Blobs), locked with a passphrase you choose. The ROM is encrypted in your browser first (AES-GCM, with a key made
from the passphrase), and stored under a name also made from it, so the site only ever holds bytes nobody can read
without the passphrase. On another device, open the site and type the passphrase under **Load from cloud**, or open
the link the site gives you after saving (it carries the passphrase after a `#`, which browsers never send to the
server). The ROM is then remembered on that device too. Saving asks for the site password (`STUDIO_PASSWORD`, the
Character Studio's) when one is set, so only you can use the storage. Files: `web/js/cloud.js`,
`web/netlify/functions/rom.mjs`.

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
| `tools/remix/make_town.py`, `restyle.py`, `town_plan.py`, `survey_scenes.py`, `extracted_scene.py`, `test_make_town.py` | The Ancient Plateau's town: buildings borrowed from the game's towns at build time and restyled, the survey used to pick them, and the shared reader for extracted scenes. 4 lines in `src/code/z_scene.c` (the Plateau's object space) |
| `tools/remix/smoke_test.py`, `tools/remix/smoke_capture.mjs`, `web/js/boot.js` | Emulator smoke test in CI (the website's player in headless Chromium); the site's "Jump into the new level" switch |
| `tools/remix/make_magnet.py`, `make_magnet_parts.py`, `make_slate.py`, `assets/scenes/remix/magnet/`, `src/overlays/actors/ovl_En_Remix_Magnet/`, `assets/objects/object_remix_magnet/`, `assets/objects/object_remix_slate/` | Level 4, the Lodestone Shrine: Magnesis and the moving pieces, and the fal-made rune. `GI_REMIX_MAGNESIS` in `include/item.h`, `z_draw.c`, `z_player.c` (get-item table, text id now 16 bits) and `assets/text/message_data.h` |
| `tools/remix/make_forge.py`, `assets/scenes/remix/forge/` | Level 5, the Forge Shrine (the fire basket, gates and spans are `ovl_En_Remix_Magnet` too) |
| `tools/remix/make_time.py`, `make_time_parts.py`, `time_plan.py`, `assets/scenes/remix/time/`, `src/overlays/actors/ovl_En_Remix_Time/`, `assets/objects/object_remix_time/` | Level 6, the Temple of Two Truths: the hall, its pieces and the age switch; the kit in `z_remix_level.c`, texts in `assets/text/message_data.h` |
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
