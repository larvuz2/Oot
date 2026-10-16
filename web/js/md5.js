// MD5 over a Uint8Array (RFC 1321). WebCrypto has no MD5, and the decomp
// identifies every supported ROM by its MD5, so we carry a small, fast one.

const S = [
    7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
    5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
    4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
    6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
];

const K = new Int32Array(64);
for (let i = 0; i < 64; i++) {
    K[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 0x100000000) | 0;
}

function processBlocks(state, view, offset, count) {
    let a0 = state[0], b0 = state[1], c0 = state[2], d0 = state[3];
    const M = new Int32Array(16);
    for (let blk = 0; blk < count; blk++, offset += 64) {
        for (let j = 0; j < 16; j++) M[j] = view.getInt32(offset + j * 4, true);
        let a = a0, b = b0, c = c0, d = d0;
        for (let i = 0; i < 64; i++) {
            let f, g;
            if (i < 16) {
                f = (b & c) | (~b & d);
                g = i;
            } else if (i < 32) {
                f = (d & b) | (~d & c);
                g = (5 * i + 1) & 15;
            } else if (i < 48) {
                f = b ^ c ^ d;
                g = (3 * i + 5) & 15;
            } else {
                f = c ^ (b | ~d);
                g = (7 * i) & 15;
            }
            const t = (a + f + K[i] + M[g]) | 0;
            a = d;
            d = c;
            c = b;
            b = (b + ((t << S[i]) | (t >>> (32 - S[i])))) | 0;
        }
        a0 = (a0 + a) | 0;
        b0 = (b0 + b) | 0;
        c0 = (c0 + c) | 0;
        d0 = (d0 + d) | 0;
    }
    state[0] = a0; state[1] = b0; state[2] = c0; state[3] = d0;
}

/** @param {Uint8Array} data @returns {string} lowercase hex digest */
export function md5(data) {
    const state = new Int32Array([0x67452301, 0xefcdab89 | 0, 0x98badcfe | 0, 0x10325476]);
    const fullBlocks = Math.floor(data.length / 64);
    const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    processBlocks(state, view, 0, fullBlocks);

    const rem = data.length - fullBlocks * 64;
    const tailLen = rem < 56 ? 64 : 128;
    const tail = new Uint8Array(tailLen);
    tail.set(data.subarray(fullBlocks * 64));
    tail[rem] = 0x80;
    const tv = new DataView(tail.buffer);
    const bitLen = data.length * 8;
    tv.setUint32(tailLen - 8, bitLen >>> 0, true);
    tv.setUint32(tailLen - 4, Math.floor(bitLen / 0x100000000), true);
    processBlocks(state, tv, 0, tailLen / 64);

    let hex = "";
    const out = new DataView(state.buffer);
    for (let i = 0; i < 16; i++) hex += out.getUint8(i).toString(16).padStart(2, "0");
    return hex;
}
