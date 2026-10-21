// Cloud copy of the player's ROM (Netlify Function + Netlify Blobs), so any device can load it.
//
// The browser encrypts the ROM with a key from the player's passphrase and stores it in pieces under an id
// derived from the same passphrase (web/js/cloud.js). This function only keeps those encrypted pieces: it never
// sees the passphrase, the key or the ROM itself.
//
// Environment variables (Netlify > Site configuration > Environment variables):
//   STUDIO_PASSWORD  when set, saving to the cloud asks for it too (the Character Studio's password), so only you
//                    can use the site's storage. Loading only needs the passphrase.
//
//   GET    /api/rom                    -> { passwordRequired }
//   GET    /api/rom?id=ID              -> the stored piece count, size and encrypted name (404 if none)
//   GET    /api/rom?id=ID&part=N       -> encrypted piece N
//   PUT    /api/rom?id=ID&part=N       <- encrypted piece N (site password header when required)
//   PUT    /api/rom?id=ID&meta=1       <- { parts, size, name } once every piece is stored
//   DELETE /api/rom?id=ID              -> removes the copy

const env = (name) => (globalThis.Netlify?.env?.get(name) ?? process.env[name] ?? "").trim();

const json = (status, body) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

export const MAX_PARTS = 40; // 100 MB of ROM at 2.5 MB per piece (N64 ROMs are at most 64 MB)
export const MAX_PIECE = 3_000_000; // an encrypted 2.5 MB piece, with room to spare

/** The request handler, with the storage passed in (tests use an in-memory one). */
export async function handle(req, store, sitePassword = env("STUDIO_PASSWORD")) {
    const url = new URL(req.url);
    const id = url.searchParams.get("id");
    if (!id) {
        if (req.method === "GET") return json(200, { passwordRequired: !!sitePassword });
        return json(400, { error: "Missing id." });
    }
    if (!/^[0-9a-f]{64}$/.test(id)) return json(400, { error: "Bad id." });
    const partParam = url.searchParams.get("part");
    const part = partParam === null ? null : Number(partParam);
    if (part !== null && !(Number.isInteger(part) && part >= 0 && part < MAX_PARTS)) return json(400, { error: "Bad part." });

    if (req.method === "GET") {
        if (part === null) {
            const meta = await store.get(`${id}/meta`, { type: "json" });
            return meta ? json(200, meta) : json(404, { error: "No ROM is saved with that passphrase." });
        }
        const data = await store.get(`${id}/${part}`, { type: "arrayBuffer" });
        if (!data) return json(404, { error: "Missing piece; save the ROM to the cloud again." });
        return new Response(data, { status: 200, headers: { "content-type": "application/octet-stream", "cache-control": "no-store" } });
    }

    if (req.method !== "PUT" && req.method !== "DELETE") return json(405, { error: "Method not allowed." });
    if (sitePassword && req.headers.get("x-site-password") !== sitePassword) {
        return json(401, { error: "Wrong site password (the Character Studio password)." });
    }

    if (req.method === "DELETE") {
        const meta = await store.get(`${id}/meta`, { type: "json" });
        await store.delete(`${id}/meta`);
        for (let i = 0; i < (meta?.parts || MAX_PARTS); i++) await store.delete(`${id}/${i}`);
        return json(200, { ok: true });
    }

    if (url.searchParams.get("meta")) {
        let meta;
        try {
            meta = await req.json();
        } catch {
            return json(400, { error: "Bad description." });
        }
        const { parts, size, name } = meta || {};
        if (!(Number.isInteger(parts) && parts > 0 && parts <= MAX_PARTS && Number.isInteger(size) && size > 0) ||
            typeof name !== "string" || name.length > 2000) {
            return json(400, { error: "Bad description." });
        }
        for (let i = 0; i < parts; i++) {
            if (!(await store.get(`${id}/${i}`, { type: "arrayBuffer" }))) return json(409, { error: `Piece ${i} is missing.` });
        }
        await store.setJSON(`${id}/meta`, { parts, size, name, savedAt: new Date().toISOString() });
        return json(200, { ok: true });
    }

    if (part === null) return json(400, { error: "Missing part." });
    const data = await req.arrayBuffer();
    if (data.byteLength < 29 || data.byteLength > MAX_PIECE) return json(413, { error: "Piece too big." });
    await store.set(`${id}/${part}`, data);
    return json(200, { ok: true });
}

export default async (req) => {
    const { getStore } = await import("@netlify/blobs");
    try {
        return await handle(req, getStore({ name: "cloud-roms", consistency: "strong" }));
    } catch (err) {
        return json(500, { error: `Cloud storage failed: ${err.message}` });
    }
};

export const config = { path: "/api/rom" };
