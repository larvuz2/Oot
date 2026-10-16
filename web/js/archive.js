// Unpack ROMs that come zipped (.zip / .7z / .rar), using the extractors that
// ship with EmulatorJS (web/emulatorjs/data/compression/).

const BASE = new URL("../emulatorjs/data/compression/", import.meta.url);
const ROM_EXT = /\.(z64|n64|v64)$/i;

/** @returns {"zip"|"7z"|"rar"|null} */
export function archiveType(b) {
    if (b[0] === 0x50 && b[1] === 0x4b && [3, 5, 7].includes(b[2])) return "zip";
    if (b[0] === 0x37 && b[1] === 0x7a && b[2] === 0xbc && b[3] === 0xaf && b[4] === 0x27 && b[5] === 0x1c) return "7z";
    if (b[0] === 0x52 && b[1] === 0x61 && b[2] === 0x72 && b[3] === 0x21 && b[4] === 0x1a && b[5] === 0x07) return "rar";
    return null;
}

async function workerUrl(type) {
    if (type === "zip") return new URL("extractzip.js", BASE).href;
    if (type === "7z") return new URL("extract7z.js", BASE).href;
    // libunrar needs a small wrapper (same as EmulatorJS's compression.js).
    const [js, wasm] = await Promise.all([
        fetch(new URL("libunrar.js", BASE)).then((r) => r.text()),
        fetch(new URL("libunrar.wasm", BASE)).then((r) => r.arrayBuffer()),
    ]);
    const wasmUrl = URL.createObjectURL(new Blob([wasm], { type: "application/wasm" }));
    const script = `
        let input = [];
        Module = {
            monitorRunDependencies(left) { if (left == 0) setTimeout(() => unrar(), 100); },
            onRuntimeInitialized() {},
            locateFile() { return ${JSON.stringify(wasmUrl)}; },
        };
        ${js}
        function unrar() {
            const root = readRARContent(input.map((d) => ({ name: d.name, content: new Uint8Array(d.content) })), null, () => {});
            const rec = (e) => {
                if (!e) return;
                if (e.type === "file") postMessage({ t: 2, file: e.fullFileName, size: e.fileSize, data: e.fileContent });
                else if (e.type === "dir") Object.values(e.ls).forEach(rec);
            };
            rec(root);
            postMessage({ t: 1 });
        }
        onmessage = (e) => input.push({ name: "rom.rar", content: e.data });
    `;
    return URL.createObjectURL(new Blob([script], { type: "application/javascript" }));
}

/**
 * Extract the ROM from an archive. Picks the .z64/.n64/.v64 entry (largest if
 * several), otherwise the largest file.
 * @returns {Promise<{name: string, bytes: Uint8Array}>}
 */
export async function extractRom(bytes, type, onProgress = () => {}) {
    const worker = new Worker(await workerUrl(type));
    const files = [];
    try {
        await new Promise((resolve, reject) => {
            worker.onerror = (e) => reject(new Error(`Couldn't open the ${type} archive${e.message ? ` (${e.message})` : ""}.`));
            worker.onmessage = (e) => {
                const m = e.data;
                if (!m) return;
                if (m.t === 4 && m.total) onProgress(Math.floor((m.current / m.total) * 100));
                if (m.t === 2 && m.data) files.push({ name: m.file, bytes: new Uint8Array(m.data) });
                if (m.t === 1) resolve();
            };
            worker.postMessage(bytes);
        });
    } finally {
        worker.terminate();
    }
    const roms = files.filter((f) => ROM_EXT.test(f.name));
    const pool = roms.length ? roms : files;
    if (!pool.length) throw new Error(`The ${type} archive is empty or couldn't be read.`);
    const pick = pool.reduce((a, b) => (b.bytes.length > a.bytes.length ? b : a));
    return { name: pick.name.split("/").pop(), bytes: pick.bytes };
}
