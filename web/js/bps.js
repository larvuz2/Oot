// BPS patch application (https://github.com/Alcaro/Flips/blob/master/bps_spec.md).
// Remix builds are published as BPS deltas against the decompressed retail ROM,
// so the site never ships Nintendo's data: players supply their own cartridge dump.

import { crc32 } from "./crc32.js";

export class BpsError extends Error {}

function readU32LE(b, o) {
    return (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0;
}

/** Parse just the header so callers can check sizes/CRCs before applying. */
export function bpsInfo(patch) {
    if (patch.length < 4 + 3 + 12 || patch[0] !== 0x42 || patch[1] !== 0x50 || patch[2] !== 0x53 || patch[3] !== 0x31) {
        throw new BpsError("Not a BPS patch");
    }
    let p = 4;
    const varint = () => {
        let data = 0;
        let shift = 1;
        for (;;) {
            if (p >= patch.length) throw new BpsError("Truncated BPS patch");
            const x = patch[p++];
            data += (x & 0x7f) * shift;
            if (x & 0x80) return data;
            shift *= 128;
            data += shift;
        }
    };
    const sourceSize = varint();
    const targetSize = varint();
    const metaSize = varint();
    const metadata = new TextDecoder().decode(patch.subarray(p, p + metaSize));
    p += metaSize;
    const end = patch.length - 12;
    return {
        sourceSize,
        targetSize,
        metadata,
        actionsStart: p,
        sourceCrc: readU32LE(patch, end),
        targetCrc: readU32LE(patch, end + 4),
        patchCrc: readU32LE(patch, end + 8),
    };
}

/**
 * @param {Uint8Array} source
 * @param {Uint8Array} patch
 * @returns {Uint8Array} target
 */
export function applyBps(source, patch) {
    const info = bpsInfo(patch);
    const end = patch.length - 12;
    if (crc32(patch, 0, patch.length - 4) !== info.patchCrc) throw new BpsError("BPS patch file is corrupt");
    if (source.length !== info.sourceSize) {
        throw new BpsError(`Patch expects a ${info.sourceSize}-byte ROM, got ${source.length} bytes`);
    }
    if (crc32(source) !== info.sourceCrc) throw new BpsError("Patch was made for a different ROM");

    const target = new Uint8Array(info.targetSize);
    let p = info.actionsStart;
    let out = 0;
    let srcRel = 0;
    let tgtRel = 0;
    const varint = () => {
        let data = 0;
        let shift = 1;
        for (;;) {
            const x = patch[p++];
            data += (x & 0x7f) * shift;
            if (x & 0x80) return data;
            shift *= 128;
            data += shift;
        }
    };

    while (p < end) {
        const data = varint();
        const cmd = data % 4;
        const len = Math.floor(data / 4) + 1;
        if (out + len > target.length) throw new BpsError("BPS patch writes past end of target");
        switch (cmd) {
            case 0: // SourceRead
                target.set(source.subarray(out, out + len), out);
                out += len;
                break;
            case 1: // TargetRead
                target.set(patch.subarray(p, p + len), out);
                p += len;
                out += len;
                break;
            case 2: { // SourceCopy
                const d = varint();
                srcRel += (d & 1 ? -1 : 1) * Math.floor(d / 2);
                target.set(source.subarray(srcRel, srcRel + len), out);
                srcRel += len;
                out += len;
                break;
            }
            case 3: { // TargetCopy (may overlap the region being written)
                const d = varint();
                tgtRel += (d & 1 ? -1 : 1) * Math.floor(d / 2);
                for (let i = 0; i < len; i++) target[out++] = target[tgtRel++];
                break;
            }
        }
    }
    if (out !== target.length) throw new BpsError("BPS patch did not fill the target ROM");
    if (crc32(target) !== info.targetCrc) throw new BpsError("Patched ROM failed its checksum");
    return target;
}
