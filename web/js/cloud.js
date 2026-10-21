// Keep the player's ROM in this site's cloud storage so any device can load it, locked with a passphrase.
//
// Everything secret stays in the browser: the passphrase is stretched (PBKDF2) into an AES key and a storage id.
// The ROM is cut into pieces small enough for a Netlify Function request, each piece is encrypted (AES-GCM) and
// stored under that id (netlify/functions/rom.mjs). The server only ever sees the id and encrypted bytes: without
// the passphrase nobody can find or read the ROM.

export const API = "/api/rom";
export const PART_SIZE = 2_500_000; // bytes of ROM per request (Netlify Functions take up to 6 MB, sent as base64)
const SALT = new TextEncoder().encode("ocarina-web-remix/cloud-rom/v1");
const ITERATIONS = 200_000;

const hex = (bytes) => [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");

/** AES key and storage id (64 hex characters) for a passphrase. */
export async function deriveKeys(passphrase) {
    const text = String(passphrase).normalize("NFC").trim();
    const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(text), "PBKDF2", false, ["deriveBits"]);
    const bits = new Uint8Array(
        await crypto.subtle.deriveBits({ name: "PBKDF2", salt: SALT, iterations: ITERATIONS, hash: "SHA-256" }, base, 512),
    );
    const key = await crypto.subtle.importKey("raw", bits.slice(0, 32), "AES-GCM", false, ["encrypt", "decrypt"]);
    return { key, id: hex(bits.slice(32)) };
}

/** 12-byte random IV, then the AES-GCM ciphertext (with its tag). */
export async function encrypt(key, bytes) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, bytes));
    const out = new Uint8Array(12 + ct.length);
    out.set(iv);
    out.set(ct, 12);
    return out;
}

export async function decrypt(key, data) {
    const d = new Uint8Array(data);
    return new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: d.slice(0, 12) }, key, d.slice(12)));
}

const b64 = (bytes) => btoa(String.fromCharCode(...bytes));
const unb64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

async function request(url, init, fetchImpl) {
    const res = await fetchImpl(url, init);
    if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try {
            msg = (await res.json()).error || msg;
        } catch {
            /* not JSON */
        }
        const err = new Error(msg);
        err.status = res.status;
        throw err;
    }
    return res;
}

/** { passwordRequired } from the server. */
export async function cloudInfo(fetchImpl = fetch) {
    return (await request(API, {}, fetchImpl)).json();
}

/** Encrypt and store the ROM; onProgress(fraction). sitePassword is needed when the site has one. */
export async function uploadRom(passphrase, name, bytes, { sitePassword = "", onProgress = () => {}, fetchImpl = fetch } = {}) {
    const { key, id } = await deriveKeys(passphrase);
    const data = new Uint8Array(bytes);
    const parts = Math.max(1, Math.ceil(data.length / PART_SIZE));
    const headers = { "content-type": "application/octet-stream", "x-site-password": sitePassword };
    for (let i = 0; i < parts; i++) {
        const piece = await encrypt(key, data.subarray(i * PART_SIZE, (i + 1) * PART_SIZE));
        await request(`${API}?id=${id}&part=${i}`, { method: "PUT", headers, body: piece }, fetchImpl);
        onProgress((i + 1) / parts);
    }
    // the file name is encrypted too; the piece count and size let the download check it got everything
    const meta = { parts, size: data.length, name: b64(await encrypt(key, new TextEncoder().encode(name))) };
    await request(`${API}?id=${id}&meta=1`, {
        method: "PUT", headers: { ...headers, "content-type": "application/json" }, body: JSON.stringify(meta),
    }, fetchImpl);
    return id;
}

/** { name, bytes } of the ROM stored with this passphrase, or null if there is none. */
export async function downloadRom(passphrase, { onProgress = () => {}, fetchImpl = fetch } = {}) {
    const { key, id } = await deriveKeys(passphrase);
    let meta;
    try {
        meta = await (await request(`${API}?id=${id}`, {}, fetchImpl)).json();
    } catch (err) {
        if (err.status === 404) return null;
        throw err;
    }
    const out = new Uint8Array(meta.size);
    let at = 0;
    for (let i = 0; i < meta.parts; i++) {
        const res = await request(`${API}?id=${id}&part=${i}`, {}, fetchImpl);
        const piece = await decrypt(key, await res.arrayBuffer());
        out.set(piece, at);
        at += piece.length;
        onProgress((i + 1) / meta.parts);
    }
    if (at !== meta.size) throw new Error("The cloud copy is incomplete; save it to the cloud again.");
    const name = new TextDecoder().decode(await decrypt(key, unb64(meta.name)));
    return { name, bytes: out };
}

export async function deleteRom(passphrase, { sitePassword = "", fetchImpl = fetch } = {}) {
    const { id } = await deriveKeys(passphrase);
    await request(`${API}?id=${id}`, { method: "DELETE", headers: { "x-site-password": sitePassword } }, fetchImpl);
}
