// Remember the player's ROM in their own browser (IndexedDB) so they only pick it once.
// Nothing is uploaded anywhere. Every call fails soft: private windows may block storage.

const DB = "oot-web-remix";
const STORE = "files";

function open() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB, 1);
        req.onupgradeneeded = () => req.result.createObjectStore(STORE);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

async function run(mode, fn) {
    const db = await open();
    try {
        return await new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, mode);
            const req = fn(tx.objectStore(STORE));
            tx.oncomplete = () => resolve(req && req.result);
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error);
        });
    } finally {
        db.close();
    }
}

export async function loadRom() {
    try {
        return (await run("readonly", (s) => s.get("rom"))) || null;
    } catch {
        return null;
    }
}

export async function saveRom(name, bytes) {
    try {
        await run("readwrite", (s) => s.put({ name, bytes: new Blob([bytes]) }, "rom"));
        return true;
    } catch {
        return false;
    }
}

export async function forgetRom() {
    try {
        await run("readwrite", (s) => s.delete("rom"));
    } catch {
        /* ignore */
    }
}
