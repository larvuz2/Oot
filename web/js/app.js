import { VERSIONS } from "./versions.js";
import { loadRom, saveRom, forgetRom } from "./storage.js";
import { archiveType, extractRom } from "./archive.js";

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
};

function startEmulator(bytes, gameName) {
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" }));
    const p0 = {};
    for (const [id, [value, value2]] of Object.entries(KEYS)) p0[id] = { value, value2 };

    Object.assign(window, {
        EJS_player: "#game",
        EJS_core: "n64",
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
        },
    });
    setState("playing");
    const s = document.createElement("script");
    s.src = "emulatorjs/data/loader.js";
    document.body.append(s);
    $("game").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function play() {
    const mode = document.querySelector('input[name="mode"]:checked')?.value || "original";
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
        startEmulator(bytes, `oot-${rom.version.version}-${rom.version.region}-${mode}`);
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
$("play").addEventListener("click", play);
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
            startEmulator(new Uint8Array(await res.arrayBuffer()), "test-rom");
        } catch (err) {
            fail(err);
        }
        return;
    }

    const saved = await loadRom();
    if (saved) {
        try {
            await ingest(new Uint8Array(await saved.bytes.arrayBuffer()), saved.name, false);
            return;
        } catch (err) {
            console.warn("Stored ROM unusable, asking again", err);
            await forgetRom();
        }
    }
    setState("empty");
})();
