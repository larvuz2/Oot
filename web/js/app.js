import { VERSIONS } from "./versions.js";
import { loadRom, saveRom, forgetRom } from "./storage.js";
import { archiveType, extractRom } from "./archive.js";
import { setBootMode, BOOT_ANCIENT_PLATEAU, BOOT_EMBER_SHRINE, BOOT_SEEKER_SHRINE, BOOT_LODESTONE_SHRINE, BOOT_FORGE_SHRINE, BOOT_TIME_TEMPLE, BOOT_SEVEN_YEARS, BOOT_UPSIDE_DOWN_WIND, BOOT_SWINGING_ABYSS } from "./boot.js";
import { cloudInfo, uploadRom, downloadRom } from "./cloud.js";

const $ = (id) => document.getElementById(id);
const setState = (s) => (document.body.dataset.state = s);

// ---- worker RPC -----------------------------------------------------------

const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
let nextId = 1;
const pending = new Map();
worker.onmessage = (e) => {
    const { id, progress, result, error } = e.data;
    const p = pending.get(id);
    if (!p) return;
    if (progress) return p.onProgress(progress);
    pending.delete(id);
    error ? p.reject(new Error(error)) : p.resolve(result);
};
function call(msg, transfer = [], onProgress = busy) {
    const id = nextId++;
    return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject, onProgress });
        worker.postMessage({ id, ...msg }, transfer);
    });
}

// ---- UI helpers -------------------------------------------------------------

function busy(msg) {
    $("busy-msg").textContent = msg;
    setState("busy");
}
function fail(err) {
    console.error(err);
    $("error-msg").textContent = err.message || String(err);
    setState("error");
}
const fmtMB = (n) => `${(n / 1048576).toFixed(1)} MB`;

let manifest = { patches: [] };
let rom = null; // { version, original, decompressed, name }

async function loadManifest() {
    try {
        const res = await fetch("patches/manifest.json", { cache: "no-cache" });
        if (res.ok) manifest = await res.json();
    } catch {
        /* no remix published yet */
    }
}

function renderVersions() {
    const ul = $("versions");
    ul.replaceChildren(
        ...[...VERSIONS].sort((a, b) => a.label.startsWith("N64") === b.label.startsWith("N64") ? a.label.localeCompare(b.label) : a.label.startsWith("N64") ? -1 : 1).map((v) => {
            const li = document.createElement("li");
            const name = document.createElement("span");
            name.textContent = v.label;
            li.append(name);
            if (manifest.patches.some((p) => p.sourceMd5 === v.decompressedMd5)) {
                const tag = document.createElement("span");
                tag.className = "tag";
                tag.textContent = "REMIX";
                li.append(tag);
            }
            return li;
        }),
    );
}

function renderReady() {
    const { version, name } = rom;
    $("rom-label").textContent = version.label;
    $("rom-detail").textContent = `${name} · decomp version ${version.version}`;

    const patch = manifest.patches.find((p) => p.sourceMd5 === version.decompressedMd5);
    $("play-level").hidden = !patch;
    $("play-shrine").hidden = !patch;
    $("play-seeker").hidden = !patch;
    $("play-magnet").hidden = !patch;
    $("play-forge").hidden = !patch;
    $("play-time").hidden = !patch;
    $("play-years").hidden = !patch;
    $("play-wind").hidden = !patch;
    $("play-abyss").hidden = !patch;
    $("play-level-note").hidden = !patch;
    const modes = $("modes");
    const options = [];
    if (patch) {
        const when = patch.builtAt ? new Date(patch.builtAt).toLocaleDateString() : "";
        options.push({
            value: "remix",
            title: patch.title || "Remix",
            desc: `Built from this repo's source${patch.commit ? ` @ ${patch.commit.slice(0, 7)}` : ""}${when ? ` on ${when}` : ""}.`,
        });
    }
    options.push({
        value: "original",
        title: "Original game",
        desc: patch ? "Your unmodified cartridge." : "No remix build has been published for this version yet, so you'll play the original.",
    });
    modes.replaceChildren(
        ...options.map((o, i) => {
            const label = document.createElement("label");
            label.className = "mode";
            const input = document.createElement("input");
            input.type = "radio";
            input.name = "mode";
            input.value = o.value;
            input.checked = i === 0;
            const text = document.createElement("div");
            const strong = document.createElement("strong");
            strong.textContent = o.title;
            const span = document.createElement("span");
            span.textContent = o.desc;
            text.append(strong, span);
            label.append(input, text);
            return label;
        }),
    );
    const select = $("core");
    select.replaceChildren(
        ...Object.entries(CORES).map(([value, label]) => {
            const o = document.createElement("option");
            o.value = value;
            o.textContent = label;
            return o;
        }),
    );
    select.value = preferredCore() in CORES ? preferredCore() : DEFAULT_CORE;
    $("perf").checked = perfMode();
    $("speed-meter").checked = speedMeterOn();
    prepareCloudSave();
    setState("ready");
    $("play").focus();
}

// ---- ROM intake -------------------------------------------------------------

async function ingest(bytes, name, remember) {
    busy("Reading ROM…");
    const result = await call({ cmd: "prepare", bytes: bytes.buffer }, [bytes.buffer]);
    rom = { ...result, name };
    if (remember) await saveRom(name, rom.original);
    renderReady();
}

async function onFile(file) {
    if (!file) return;
    try {
        if (file.size > 256 * 1048576) throw new Error(`That file is ${fmtMB(file.size)}; N64 ROMs are at most 64 MB.`);
        busy("Reading file…");
        let bytes = new Uint8Array(await file.arrayBuffer());
        let name = file.name;
        const type = archiveType(bytes);
        if (type) {
            busy(`Unpacking ${type} archive…`);
            ({ name, bytes } = await extractRom(bytes, type, (pct) => busy(`Unpacking ${type} archive… ${pct}%`)));
        }
        if (bytes.length > 128 * 1048576) throw new Error(`${name} is ${fmtMB(bytes.length)}; N64 ROMs are at most 64 MB.`);
        await ingest(bytes, name, true);
    } catch (err) {
        fail(err);
    }
}

// ---- Cloud copy (any device) ------------------------------------------------

const cloudLink = (pass) => `${location.origin}${location.pathname}#cloud=${encodeURIComponent(pass)}`;

async function prepareCloudSave() {
    $("cloud-save-msg").textContent = "";
    $("cloud-link-box").hidden = true;
    try {
        const info = await cloudInfo();
        $("cloud-site-pass").hidden = !info.passwordRequired;
        $("cloud-site-pass").required = !!info.passwordRequired;
    } catch {
        $("cloud-save-msg").textContent = "Cloud saving isn't available on this copy of the site.";
    }
}

async function saveToCloud(e) {
    e.preventDefault();
    const pass = $("cloud-save-pass").value;
    const msg = $("cloud-save-msg");
    if (pass.trim().length < 8) {
        msg.textContent = "Use at least 8 characters.";
        return;
    }
    const button = e.submitter || $("cloud-save").querySelector("button[type=submit]");
    button.disabled = true;
    try {
        msg.textContent = "Encrypting…";
        await uploadRom(pass, rom.name, rom.original, {
            sitePassword: $("cloud-site-pass").value,
            onProgress: (f) => (msg.textContent = `Saving to the cloud… ${Math.round(f * 100)}%`),
        });
        msg.textContent = "Saved. On another device, open this site and enter your passphrase, or open this link there " +
            "(it contains your passphrase, so keep it to yourself):";
        $("cloud-link").value = cloudLink(pass);
        $("cloud-link-box").hidden = false;
    } catch (err) {
        msg.textContent = `Couldn't save: ${err.message}`;
    } finally {
        button.disabled = false;
    }
}

async function loadFromCloud(pass) {
    const msg = $("cloud-load-msg");
    try {
        busy("Finding your ROM in the cloud…");
        const got = await downloadRom(pass, { onProgress: (f) => busy(`Loading your ROM from the cloud… ${Math.round(f * 100)}%`) });
        if (!got) {
            setState("empty");
            msg.textContent = "No ROM is saved with that passphrase.";
            return;
        }
        await ingest(got.bytes, got.name, true);
    } catch (err) {
        setState("empty");
        msg.textContent = err.name === "OperationError" ? "That passphrase doesn't open the saved ROM." : `Couldn't load: ${err.message}`;
    }
}

// ---- Emulator ---------------------------------------------------------------

const KEYS = {
    0: ["x", "BUTTON_1"], // A
    1: ["c", "BUTTON_3"], // B
    3: ["enter", "START"],
    4: ["t", "DPAD_UP"],
    5: ["g", "DPAD_DOWN"],
    6: ["f", "DPAD_LEFT"],
    7: ["h", "DPAD_RIGHT"],
    10: ["e", "LEFT_TOP_SHOULDER"], // L
    11: ["v", "RIGHT_TOP_SHOULDER"], // R
    12: ["z", "LEFT_BOTTOM_SHOULDER"], // Z
    16: ["d", "LEFT_STICK_X:+1"],
    17: ["a", "LEFT_STICK_X:-1"],
    18: ["s", "LEFT_STICK_Y:+1"],
    19: ["w", "LEFT_STICK_Y:-1"],
    20: ["right arrow", "RIGHT_STICK_X:+1"], // C-right
    21: ["left arrow", "RIGHT_STICK_X:-1"], // C-left
    22: ["down arrow", "RIGHT_STICK_Y:+1"], // C-down
    23: ["up arrow", "RIGHT_STICK_Y:-1"], // C-up
    // Emulator hotkeys (EmulatorJS slots): quick save/load state, hold to fast-forward.
    24: ["1"],
    25: ["2"],
    27: ["space"],
};

// Two N64 cores ship with the site. Each has known WebAssembly crash bugs on
// some games, so the player can switch, and a crash offers the other one.
const CORES = {
    mupen64plus_next: "Standard (Mupen64Plus-Next)",
    parallel_n64: "Compatibility (ParaLLEl N64)",
};
const DEFAULT_CORE = "mupen64plus_next";
const params = new URLSearchParams(location.search);
function preferredCore() {
    const q = params.get("core");
    if (q) return q;
    try {
        const c = localStorage.getItem("oot.core");
        if (c in CORES) return c;
    } catch {
        /* storage blocked */
    }
    return DEFAULT_CORE;
}
function setPreferredCore(c) {
    try {
        localStorage.setItem("oot.core", c);
    } catch {
        /* storage blocked */
    }
}

// ---- Performance mode and speed meter -----------------------------------------

// Tablets and phones (iPadOS reports itself as a Mac, but with a touch screen).
const TOUCH_DEVICE =
    /iPhone|iPad|iPod|Android/i.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);

/** A yes/no setting: ?name=1|0 in the address, else what the player chose last time, else the default. */
function flag(name, key, def) {
    const q = params.get(name);
    if (q === "1" || q === "0") return q === "1";
    try {
        const v = localStorage.getItem(key);
        if (v === "1" || v === "0") return v === "1";
    } catch {
        /* storage blocked */
    }
    return def;
}
function setFlag(key, on) {
    try {
        localStorage.setItem(key, on ? "1" : "0");
    } catch {
        /* storage blocked */
    }
}
const perfMode = () => flag("perf", "oot.perf", TOUCH_DEVICE);
const speedMeterOn = () => flag("speed", "oot.speed", TOUCH_DEVICE);

// Performance mode: the emulator draws at the console's own resolution (320x240 instead of 640x480, a quarter of
// the pixels) and skips work the game barely needs: copying the depth buffer back to the console's memory in
// software (only the sun's lens flare looks at it) and texture level-of-detail. Frame duplication keeps the
// picture steady when a frame comes late. Options the player changes in the emulator's menu still win.
const PERF_OPTIONS = {
    mupen64plus_next: {
        "mupen64plus-43screensize": "320x240",
        "mupen64plus-EnableCopyDepthToRDRAM": "Off",
        "mupen64plus-EnableLODEmulation": "False",
        "mupen64plus-MultiSampling": "0",
        "mupen64plus-FrameDuping": "True",
    },
    parallel_n64: {
        "parallel-n64-screensize": "320x240",
        "parallel-n64-framerate": "original",
    },
};

// Speed meter: frames the emulator ran in the last second against the console's 60 per second. Below 100% the
// game and its music slow down.
let speedTimer = 0;
function startSpeedMeter() {
    const el = $("speed");
    clearInterval(speedTimer);
    el.hidden = !speedMeterOn();
    let last = null;
    speedTimer = setInterval(() => {
        const e = window.EJS_emulator;
        if (el.hidden || !e || !e.started || e.paused || document.hidden) {
            last = null;
            return;
        }
        let n;
        try {
            n = e.gameManager.functions.getFrameNum();
        } catch {
            return;
        }
        const now = performance.now();
        if (last && now > last.t) {
            const fps = ((n - last.n) * 1000) / (now - last.t);
            const pct = Math.min(999, Math.round((fps / 60) * 100));
            el.textContent = `${pct}% · ${Math.round(fps)} fps${session?.perf ? " · perf" : ""}`;
            el.className = `speed${pct >= 95 ? "" : pct >= 80 ? " ok" : " slow"}`;
            if (session) session.speed = pct;
        }
        last = { n, t: now };
    }, 1000);
}

// Browsers may start audio suspended; resume it on any interaction so the
// emulator's sound output never waits on a context that can't play.
const audioContexts = new Set();
for (const name of ["AudioContext", "webkitAudioContext"]) {
    const Base = window[name];
    if (typeof Base !== "function") continue;
    try {
        window[name] = class extends Base {
            constructor(...args) {
                super(...args);
                audioContexts.add(this);
            }
        };
    } catch {
        /* leave the native constructor alone */
    }
}
function resumeAudio() {
    for (const ctx of audioContexts) if (ctx.state === "suspended") ctx.resume().catch(() => {});
}
for (const t of ["pointerdown", "keydown", "touchend"]) window.addEventListener(t, resumeAudio, true);

let session = null; // { core, mode, version, error, frames }

function showCrash(reason) {
    if (!session || session.crashed) return;
    session.crashed = true;
    session.error = reason;
    const other = Object.keys(CORES).find((c) => c !== session.core);
    $("crash-msg").textContent = reason;
    $("crash-switch").textContent = `Try the other emulator: ${CORES[other]}`;
    $("crash-switch").onclick = () => restart(other);
    $("crash").hidden = false;
}

function restart(core) {
    setPreferredCore(core);
    const u = new URL(location.href);
    u.search = "";
    u.searchParams.set("autostart", session.mode);
    location.href = u.href;
}

function diagnostics() {
    const e = window.EJS_emulator;
    let frames = "?";
    try {
        frames = e.gameManager.functions.getFrameNum();
    } catch {
        /* core gone */
    }
    return [
        `Problem: ${session?.error || "none"}`,
        `Emulator core: ${session?.core}`,
        `Build: ${session?.mode} · ${session?.version}`,
        `Frames run: ${frames}`,
        `Speed: ${session?.speed ?? "?"}%${session?.perf ? " (performance mode)" : ""}`,
        `Audio: ${[...audioContexts].map((c) => c.state).join(", ") || "none"}`,
        `Browser: ${navigator.userAgent}`,
        `Page: ${location.href}`,
    ].join("\n");
}

const CRASH_RE = /RuntimeError|table index|out of bounds|unreachable|memory access|call stack|Aborted|abort\(/i;
window.addEventListener("error", (e) => {
    const msg = e.message || String(e.error || "");
    if (session && CRASH_RE.test(msg)) showCrash(`The emulator crashed (${msg.replace(/^Uncaught\s*/, "")}).`);
});
window.addEventListener("unhandledrejection", (e) => {
    const msg = String(e.reason?.message || e.reason || "");
    if (session && CRASH_RE.test(msg)) showCrash(`The emulator crashed (${msg}).`);
});

// Detect a frozen main loop: the frame counter stops while the game isn't paused.
function watchFrames() {
    let last = -1;
    let stuckFor = 0;
    setInterval(() => {
        const e = window.EJS_emulator;
        if (!session || session.crashed || !e || !e.started) return;
        if (document.hidden || e.paused) {
            stuckFor = 0;
            return;
        }
        let n;
        try {
            n = e.gameManager.functions.getFrameNum();
        } catch {
            return showCrash("The emulator stopped running.");
        }
        stuckFor = n === last ? stuckFor + 1 : 0;
        last = n;
        if (stuckFor >= 6) showCrash("The game stopped advancing (no new frames for 6 seconds).");
    }, 1000);
}

function startEmulator(bytes, gameName, meta = {}) {
    const core = meta.core || preferredCore();
    const perf = perfMode();
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" }));
    const p0 = {};
    for (const [id, [value, value2]] of Object.entries(KEYS)) p0[id] = { value, value2 };

    Object.assign(window, {
        EJS_player: "#game",
        EJS_core: core,
        EJS_pathtodata: new URL("emulatorjs/data/", document.baseURI).pathname,
        EJS_gameUrl: url,
        EJS_gameName: gameName,
        EJS_startOnLoaded: true,
        EJS_threads: false,
        EJS_color: "#e2b84a",
        EJS_backgroundColor: "#000000",
        EJS_defaultControls: { 0: p0, 1: {}, 2: {}, 3: {} },
        EJS_defaultOptions: {
            "save-save-interval": "30",
            "save-state-location": "browser",
            ...(perf ? PERF_OPTIONS[core] : {}),
        },
    });
    session = { core, perf, mode: meta.mode || "test", version: meta.version || "test ROM" };
    watchFrames();
    startSpeedMeter();
    setState("playing");
    const s = document.createElement("script");
    s.src = "emulatorjs/data/loader.js";
    document.body.append(s);
    $("game").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function play(forcedMode, { newLevel = false, level = BOOT_ANCIENT_PLATEAU } = {}) {
    const mode = newLevel ? "remix" : (typeof forcedMode === "string" && forcedMode) || document.querySelector('input[name="mode"]:checked')?.value || "original";
    const core = $("core").value;
    setPreferredCore(core);
    try {
        let bytes = rom.original;
        if (mode === "remix") {
            const patch = manifest.patches.find((p) => p.sourceMd5 === rom.version.decompressedMd5);
            busy("Downloading remix patch…");
            const res = await fetch(`patches/${patch.file}`);
            if (!res.ok) throw new Error(`Couldn't download the remix patch (HTTP ${res.status}).`);
            const patchBytes = await res.arrayBuffer();
            // Patch a copy so the decompressed ROM stays available.
            const source = rom.decompressed.slice();
            bytes = await call({ cmd: "patch", source: source.buffer, patch: patchBytes, targetMd5: patch.targetMd5 }, [source.buffer, patchBytes]);
        }
        let gameName = `oot-${rom.version.version}-${rom.version.region}-${mode}`;
        if (newLevel) {
            if (!setBootMode(bytes, level)) {
                throw new Error("This remix build doesn't include the new level yet. Wait for the next remix build and reload.");
            }
            // A test save: keep it apart from your real remix saves.
            gameName += "-newlevel";
        }
        startEmulator(bytes, gameName, { core, mode, version: rom.version.label });
    } catch (err) {
        fail(err);
    }
}

// ---- wiring -----------------------------------------------------------------

const drop = $("drop");
$("file").addEventListener("change", (e) => onFile(e.target.files[0]));
drop.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        $("file").click();
    }
});
for (const t of ["dragenter", "dragover"]) {
    drop.addEventListener(t, (e) => {
        e.preventDefault();
        drop.classList.add("over");
    });
}
for (const t of ["dragleave", "drop"]) drop.addEventListener(t, () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => {
    e.preventDefault();
    onFile(e.dataTransfer.files[0]);
});
// Also accept a drop anywhere on the page while choosing a ROM.
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => {
    e.preventDefault();
    if (["empty", "error"].includes(document.body.dataset.state)) onFile(e.dataTransfer.files[0]);
});

$("retry").addEventListener("click", () => {
    $("file").value = "";
    setState("empty");
});
$("forget").addEventListener("click", async () => {
    await forgetRom();
    rom = null;
    $("file").value = "";
    setState("empty");
});
$("cloud-save").addEventListener("submit", saveToCloud);
$("cloud-load").addEventListener("submit", (e) => {
    e.preventDefault();
    $("cloud-load-msg").textContent = "";
    loadFromCloud($("cloud-load-pass").value);
});
$("cloud-copy").addEventListener("click", async () => {
    try {
        await navigator.clipboard.writeText($("cloud-link").value);
        $("cloud-copy").textContent = "Copied!";
    } catch {
        $("cloud-link").select();
    }
});
$("perf").addEventListener("change", (e) => setFlag("oot.perf", e.target.checked));
$("speed-meter").addEventListener("change", (e) => setFlag("oot.speed", e.target.checked));
$("speed").addEventListener("click", () => {
    $("speed").hidden = true;
    setFlag("oot.speed", false);
});
$("play").addEventListener("click", () => play());
$("play-level").addEventListener("click", () => play("remix", { newLevel: true, level: BOOT_ANCIENT_PLATEAU }));
$("play-shrine").addEventListener("click", () => play("remix", { newLevel: true, level: BOOT_EMBER_SHRINE }));
$("play-seeker").addEventListener("click", () => play("remix", { newLevel: true, level: BOOT_SEEKER_SHRINE }));
$("play-magnet").addEventListener("click", () => play("remix", { newLevel: true, level: BOOT_LODESTONE_SHRINE }));
$("play-forge").addEventListener("click", () => play("remix", { newLevel: true, level: BOOT_FORGE_SHRINE }));
$("play-time").addEventListener("click", () => play("remix", { newLevel: true, level: BOOT_TIME_TEMPLE }));
$("play-years").addEventListener("click", () => play("remix", { newLevel: true, level: BOOT_SEVEN_YEARS }));
$("play-wind").addEventListener("click", () => play("remix", { newLevel: true, level: BOOT_UPSIDE_DOWN_WIND }));
$("play-abyss").addEventListener("click", () => play("remix", { newLevel: true, level: BOOT_SWINGING_ABYSS }));
// Shortcuts on the start screen: 1 to 9 jump into levels 1 to 9.
window.addEventListener("keydown", (e) => {
    if (document.body.dataset.state !== "ready" || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
    const button = { 1: "play-level", 2: "play-shrine", 3: "play-seeker", 4: "play-magnet", 5: "play-forge", 6: "play-time", 7: "play-years", 8: "play-wind", 9: "play-abyss" }[e.key];
    if (button && !$(button).hidden) {
        e.preventDefault();
        $(button).click();
    }
});
$("crash-restart").addEventListener("click", () => restart(session.core));
$("crash-copy").addEventListener("click", async () => {
    const text = diagnostics();
    try {
        await navigator.clipboard.writeText(text);
        $("crash-copy").textContent = "Copied!";
    } catch {
        $("crash-details").textContent = text;
        $("crash-details").hidden = false;
    }
});
$("back").addEventListener("click", () => location.reload());

(async function init() {
    await loadManifest();
    renderVersions();

    // Developer hook: ?rom=<url> boots any ROM URL directly (e.g. a homebrew test ROM).
    const direct = new URLSearchParams(location.search).get("rom");
    if (direct) {
        busy("Downloading test ROM…");
        try {
            const res = await fetch(direct);
            if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${direct}`);
            startEmulator(new Uint8Array(await res.arrayBuffer()), "test-rom", { core: preferredCore(), mode: "test" });
        } catch (err) {
            fail(err);
        }
        return;
    }

    // A cloud link (#cloud=passphrase, made by "Save to cloud"): load that ROM on this device. The passphrase is
    // in the fragment, which browsers never send to the server.
    const cloud = new URLSearchParams(location.hash.slice(1)).get("cloud");
    if (cloud) {
        history.replaceState(null, "", location.pathname + location.search);
        await loadFromCloud(cloud);
        return;
    }

    const saved = await loadRom();
    if (saved) {
        try {
            await ingest(new Uint8Array(await saved.bytes.arrayBuffer()), saved.name, false);
            const auto = params.get("autostart");
            if (auto) {
                history.replaceState(null, "", location.pathname);
                const hasRemix = manifest.patches.some((p) => p.sourceMd5 === rom.version.decompressedMd5);
                await play(auto === "remix" && !hasRemix ? "original" : auto);
            }
            return;
        } catch (err) {
            console.warn("Stored ROM unusable, asking again", err);
            await forgetRom();
        }
    }
    setState("empty");
})();
