// N64 IPL3 header checksum (the two words at ROM offset 0x10). After the ROM is
// decompressed the boot code would reject the old values, so they are recomputed
// exactly like tools/decompress_baserom.py does via the ipl3checksum package.

const SEEDS = {
    6102: 0xf8ca4ddc, // also 7101 (iQue)
    6105: 0xdf26f436, // also 7105 ("X105")
};

const START = 0x1000;
const LENGTH = 0x100000;

/**
 * @param {Uint8Array} rom big-endian (.z64) ROM
 * @param {6102|6105} cic
 * @returns {[number, number]}
 */
export function n64Checksum(rom, cic) {
    const seed = SEEDS[cic];
    if (seed === undefined) throw new Error(`Unsupported CIC ${cic}`);
    const v = new DataView(rom.buffer, rom.byteOffset, rom.byteLength);
    let t1 = seed, t2 = seed, t3 = seed, t4 = seed, t5 = seed, t6 = seed;
    for (let i = START; i < START + LENGTH; i += 4) {
        const d = v.getUint32(i);
        const sum = (t6 + d) >>> 0;
        if (sum < t6) t4 = (t4 + 1) >>> 0;
        t6 = sum;
        t3 = (t3 ^ d) >>> 0;
        const sh = d & 0x1f;
        const r = sh === 0 ? d : ((d << sh) | (d >>> (32 - sh))) >>> 0;
        t5 = (t5 + r) >>> 0;
        if (t2 > d) t2 = (t2 ^ r) >>> 0;
        else t2 = (t2 ^ t6 ^ d) >>> 0;
        if (cic === 6105) t1 = (t1 + (v.getUint32(0x750 + (i & 0xff)) ^ d)) >>> 0;
        else t1 = (t1 + (t5 ^ d)) >>> 0;
    }
    return [(t6 ^ t4 ^ t3) >>> 0, (t5 ^ t2 ^ t1) >>> 0];
}

export function updateN64Checksum(rom, cic) {
    const [c0, c1] = n64Checksum(rom, cic);
    const v = new DataView(rom.buffer, rom.byteOffset, rom.byteLength);
    v.setUint32(0x10, c0);
    v.setUint32(0x14, c1);
}
