// Recognise and decompress a player's Ocarina of Time ROM dump in the browser.
// This is a port of tools/decompress_baserom.py: the output is byte-identical to
// the decomp's baseroms/<version>/baserom-decompressed.z64, which is what remix
// patches are generated against.

import { md5 } from "./md5.js";
import { yaz0Decompress } from "./yaz0.js";
import { updateN64Checksum } from "./n64crc.js";
import { VERSIONS } from "./versions.js";

export class RomError extends Error {}

/** Convert .v64 (byte-swapped) and .n64 (little-endian) dumps to .z64 order, in place. */
export function toBigEndian(rom) {
    if (rom.length < 0x1000 || rom.length % 4 !== 0) throw new RomError("This file is too small or oddly sized to be an N64 ROM.");
    const b0 = rom[0];
    if (b0 === 0x80) return "z64";
    if (b0 === 0x37) {
        for (let i = 0; i < rom.length; i += 2) {
            const t = rom[i];
            rom[i] = rom[i + 1];
            rom[i + 1] = t;
        }
        return "v64";
    }
    if (b0 === 0x40) {
        for (let i = 0; i < rom.length; i += 4) {
            let t = rom[i];
            rom[i] = rom[i + 3];
            rom[i + 3] = t;
            t = rom[i + 1];
            rom[i + 1] = rom[i + 2];
            rom[i + 2] = t;
        }
        return "n64";
    }
    throw new RomError("This doesn't look like an N64 ROM (unknown header).");
}

async function inflateRaw(data) {
    const stream = new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    return new Uint8Array(await new Response(stream).arrayBuffer());
}

/**
 * Port of decompress_rom(): rebuild the ROM with every DMA file stored
 * uncompressed at its virtual address.
 */
export async function decompressRom(rom, version) {
    const v = new DataView(rom.buffer, rom.byteOffset, rom.byteLength);
    const entries = [];
    for (let off = version.dmadataStart; ; off += 16) {
        const e = [v.getUint32(off), v.getUint32(off + 4), v.getUint32(off + 8), v.getUint32(off + 12)];
        if (e[0] === 0 && e[1] === 0 && e[2] === 0 && e[3] === 0) break;
        entries.push(e);
    }
    if (entries.length === 0) throw new RomError("ROM has no DMA table");

    const lastEnd = entries[entries.length - 1][1];
    const size = Math.ceil(lastEnd / 0x1000) * 0x1000;
    let maxEnd = size;
    for (const [vs, ve, ps, pe] of entries) {
        const isSyms = ps === 0xffffffff && pe === 0xffffffff;
        if (!isSyms) maxEnd = Math.max(maxEnd, ve);
    }
    const out = new Uint8Array(maxEnd);
    const outView = new DataView(out.buffer);
    const newDma = [];

    for (const [vs, ve, ps, pe] of entries) {
        if (ps === 0xffffffff && pe === 0xffffffff) {
            newDma.push([vs, ve, ps, pe]);
            continue;
        }
        let data;
        if (pe !== 0) {
            const src = rom.subarray(ps, pe);
            data = version.ique ? await inflateRaw(src) : yaz0Decompress(src);
        } else {
            data = rom.subarray(ps, ps + (ve - vs));
        }
        out.set(data, vs);
        newDma.push([vs, ve, vs, 0]);
    }
    newDma.forEach((e, i) => {
        const o = version.dmadataStart + i * 16;
        outView.setUint32(o, e[0]);
        outView.setUint32(o + 4, e[1]);
        outView.setUint32(o + 8, e[2]);
        outView.setUint32(o + 12, e[3]);
    });
    updateN64Checksum(out, version.ique ? 6102 : 6105);
    return out;
}

function applyFix(rom, fix) {
    const fixed = rom.slice(0, Math.min(rom.length, fix.truncate));
    for (const [off, val] of fix.patch) fixed[off] = val;
    return fixed;
}

/**
 * Identify a dump and produce the decomp's baserom-decompressed.z64 for it.
 * @param {Uint8Array} file raw bytes as loaded (any byte order)
 * @param {(msg: string) => void} [progress]
 * @returns {Promise<{version: object, original: Uint8Array, decompressed: Uint8Array, format: string}>}
 */
export async function prepareRom(file, progress = () => {}) {
    const rom = file;
    progress("Checking byte order…");
    const format = toBigEndian(rom);

    progress("Identifying ROM…");
    const hash = md5(rom);
    let version = VERSIONS.find((x) => x.compressedMd5 === hash);
    let alreadyDecompressed = false;
    let original = rom;
    if (!version) {
        version = VERSIONS.find((x) => x.decompressedMd5 === hash);
        alreadyDecompressed = !!version;
    }
    if (!version) {
        // Debug ROM dumps carry an overdump that the decomp strips first.
        const tried = new Set();
        for (const cand of VERSIONS) {
            if (!cand.fix || rom.length <= cand.fix.truncate) continue;
            const key = JSON.stringify(cand.fix);
            if (tried.has(key)) continue;
            tried.add(key);
            const fixed = applyFix(rom, cand.fix);
            const h = md5(fixed);
            const match = VERSIONS.find((x) => JSON.stringify(x.fix) === key && x.decompressedMd5 === h);
            if (match) {
                version = match;
                original = fixed;
                alreadyDecompressed = true;
                break;
            }
        }
    }
    if (!version) {
        throw new RomError(
            `Unrecognised ROM (MD5 ${hash}). Use an unmodified dump of one of the versions listed below - ` +
                "ROM hacks, randomizer outputs and Virtual Console extracts won't match.",
        );
    }

    let decompressed = original;
    if (!alreadyDecompressed) {
        progress(`Decompressing ${version.label}…`);
        decompressed = await decompressRom(original, version);
        progress("Verifying…");
        const h = md5(decompressed);
        if (h !== version.decompressedMd5) {
            throw new RomError(`Decompression produced an unexpected result (${h}). Please report this.`);
        }
    }
    return { version, original, decompressed, format };
}
