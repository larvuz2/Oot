// CRC-32 (IEEE 802.3), used by the BPS patch format.

const TABLE = new Uint32Array(256);
for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    TABLE[n] = c >>> 0;
}

/** @param {Uint8Array} data @returns {number} unsigned 32-bit CRC */
export function crc32(data, start = 0, end = data.length) {
    let crc = 0xffffffff;
    for (let i = start; i < end; i++) crc = TABLE[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
}
