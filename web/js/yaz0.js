// Yaz0 decompression, the format Ocarina of Time uses for most ROM files.
// Mirrors crunch64.yaz0.decompress as used by tools/decompress_baserom.py.

/**
 * @param {Uint8Array} src  bytes starting with the "Yaz0" magic
 * @returns {Uint8Array}
 */
export function yaz0Decompress(src) {
    if (src[0] !== 0x59 || src[1] !== 0x61 || src[2] !== 0x7a || src[3] !== 0x30) {
        throw new Error("Not Yaz0 data");
    }
    const size = ((src[4] << 24) | (src[5] << 16) | (src[6] << 8) | src[7]) >>> 0;
    const dst = new Uint8Array(size);
    let s = 16;
    let d = 0;
    let header = 0;
    let bits = 0;
    while (d < size) {
        if (bits === 0) {
            header = src[s++];
            bits = 8;
        }
        if (header & 0x80) {
            dst[d++] = src[s++];
        } else {
            const b1 = src[s++];
            const b2 = src[s++];
            let back = d - (((b1 & 0x0f) << 8) | b2) - 1;
            let len = b1 >> 4;
            if (len === 0) {
                len = src[s++] + 0x12;
            } else {
                len += 2;
            }
            if (back < 0 || d + len > size) throw new Error("Corrupt Yaz0 data");
            // Byte-by-byte: the source run may overlap the bytes being written.
            for (let i = 0; i < len; i++) dst[d++] = dst[back++];
        }
        header = (header << 1) & 0xff;
        bits--;
    }
    return dst;
}
