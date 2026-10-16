// Heavy ROM work (MD5, Yaz0, BPS) runs off the main thread so the page stays responsive.

import { prepareRom } from "./rom.js";
import { applyBps } from "./bps.js";
import { md5 } from "./md5.js";

self.onmessage = async (e) => {
    const { id, cmd } = e.data;
    try {
        if (cmd === "prepare") {
            const r = await prepareRom(new Uint8Array(e.data.bytes), (msg) => self.postMessage({ id, progress: msg }));
            const original = r.original.slice();
            self.postMessage(
                { id, result: { version: r.version, format: r.format, original, decompressed: r.decompressed } },
                [original.buffer, r.decompressed.buffer],
            );
        } else if (cmd === "patch") {
            self.postMessage({ id, progress: "Applying remix patch…" });
            const out = applyBps(new Uint8Array(e.data.source), new Uint8Array(e.data.patch));
            if (e.data.targetMd5) {
                self.postMessage({ id, progress: "Verifying remix…" });
                const h = md5(out);
                if (h !== e.data.targetMd5) throw new Error(`Remix ROM checksum mismatch (${h})`);
            }
            self.postMessage({ id, result: out }, [out.buffer]);
        } else {
            throw new Error(`Unknown command ${cmd}`);
        }
    } catch (err) {
        self.postMessage({ id, error: err && err.message ? err.message : String(err) });
    }
};
