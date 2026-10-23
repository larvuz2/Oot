// Runs a ROM in the website's own emulator (EmulatorJS, web/) in headless Chromium and saves screenshots of
// the game at given frame numbers. Driven by tools/remix/smoke_test.py, which prepares the ROM and checks the
// pictures.
//
//   node tools/remix/smoke_capture.mjs --rom boot.z64 --out DIR [--frames 400,900,1500] [--walk-after 900]
//                                      [--core mupen64plus_next|parallel_n64] [--query perf=1]
//                                      [--inputs FRAME:INDEX:VALUE,...]
//
// --inputs presses and releases controls at given frames (EmulatorJS input indices, see KEYS in web/js/app.js:
// 0 A, 1 B, 10 L, 18/19 stick down/up, 20-23 C right/left/down/up; VALUE 1 or 0 for buttons, 0-32767 for sticks).
//
// Needs the `playwright` package (resolved from NODE_PATH or the current directory) and a Chromium it can
// launch. Writes DIR/shot-<frame>.png and DIR/capture.json ({ shots, crash, frames, log }).

import { createServer } from "node:http";
import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { join, extname, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const arg = (name, def) => {
    const i = process.argv.indexOf(`--${name}`);
    return i > 0 ? process.argv[i + 1] : def;
};
const romPath = arg("rom");
const out = arg("out");
const frames = arg("frames", "400,900,1500").split(",").map(Number);
const walkAfter = Number(arg("walk-after", "900"));
const timeoutS = Number(arg("timeout", "480"));
const core = arg("core", "");
const query = arg("query", ""); // more of the page's address options (perf=1: the website's performance mode)
const inputs = arg("inputs", "")
    .split(",")
    .filter(Boolean)
    .map((s) => s.split(":").map(Number))
    .sort((a, b) => a[0] - b[0]);
const webDir = resolve(arg("web", join(here, "../../web")));
if (!romPath || !out) {
    console.error("usage: node smoke_capture.mjs --rom ROM --out DIR [--frames a,b,c] [--walk-after N]");
    process.exit(2);
}
mkdirSync(out, { recursive: true });

const require = createRequire(join(process.cwd(), "noop.js"));
let chromium;
try {
    ({ chromium } = require("playwright"));
} catch {
    ({ chromium } = createRequire(import.meta.url)("playwright"));
}

// Static server for web/ (EmulatorJS fetches its cores over HTTP, so file:// will not do).
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
    ".json": "application/json", ".wasm": "application/wasm", ".svg": "image/svg+xml", ".png": "image/png" };
const rom = readFileSync(romPath);
const server = createServer((req, res) => {
    const url = new URL(req.url, "http://x");
    if (url.pathname === "/__smoke/boot.z64") {
        res.writeHead(200, { "content-type": "application/octet-stream", "content-length": rom.length });
        return res.end(rom);
    }
    let p = join(webDir, decodeURIComponent(url.pathname));
    if (!p.startsWith(webDir)) return res.writeHead(403).end();
    if (existsSync(p) && statSync(p).isDirectory()) p = join(p, "index.html");
    if (!existsSync(p)) return res.writeHead(404).end();
    res.writeHead(200, { "content-type": TYPES[extname(p)] || "application/octet-stream" });
    res.end(readFileSync(p));
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}`;

const result = { shots: [], crash: null, frames: 0, log: [] };
const browser = await chromium.launch({
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--autoplay-policy=no-user-gesture-required"],
});
const finish = async (code) => {
    writeFileSync(join(out, "capture.json"), JSON.stringify(result, null, 1));
    await browser.close().catch(() => {});
    server.close();
    process.exit(code);
};
const watchdog = setTimeout(() => {
    result.log.push(`timed out after ${timeoutS} s`);
    console.log(`capture: timed out after ${timeoutS} s at frame ${result.frames}`);
    finish(1);
}, timeoutS * 1000);

try {
    const page = await browser.newPage({ viewport: { width: 960, height: 900 } });
    page.on("console", (m) => {
        if (result.log.length < 400) result.log.push(`[${m.type()}] ${m.text()}`);
    });
    page.on("pageerror", (e) => result.log.push(`[pageerror] ${e.message}`));
    await page.goto(`${base}/?rom=${encodeURIComponent(base + "/__smoke/boot.z64")}${core ? `&core=${core}` : ""}${query ? `&${query}` : ""}`);
    const frameNum = () =>
        page.evaluate(() => {
            try {
                return window.EJS_emulator.gameManager.functions.getFrameNum();
            } catch {
                return -1;
            }
        });
    const crashed = () => page.evaluate(() => (document.getElementById("crash")?.hidden === false ? document.getElementById("crash-msg").textContent : null));

    const t0 = Date.now();
    let walking = false;
    let lastFrame = -2;
    let lastChange = Date.now();
    for (const target of frames) {
        for (;;) {
            const n = await frameNum();
            result.frames = Math.max(result.frames, n);
            if (n !== lastFrame) {
                lastFrame = n;
                lastChange = Date.now();
            } else if (n > 0 && Date.now() - lastChange > 45000) {
                result.crash = `the emulator stopped at frame ${n} (no new frame for 45 s)`;
                console.log(`capture: ${result.crash}`);
                clearTimeout(watchdog);
                await finish(1);
            }
            const c = await crashed();
            if (c) {
                result.crash = c;
                console.log(`capture: the player reported a crash at frame ${n}: ${c}`);
                clearTimeout(watchdog);
                await page.screenshot({ path: join(out, "crash.png") });
                await finish(1);
            }
            if (!walking && n >= walkAfter) {
                // Hold the control stick forward: Link runs, the camera follows (proves input and movement).
                walking = await page.evaluate(() => {
                    try {
                        window.EJS_emulator.gameManager.simulateInput(0, 19, 0x7fff);
                        return true;
                    } catch {
                        return false;
                    }
                });
                console.log(`capture: holding the stick forward from frame ${n} (${walking ? "ok" : "input API missing"})`);
            }
            while (inputs.length && n >= inputs[0][0]) {
                const [at, index, value] = inputs.shift();
                const ok = await page.evaluate(
                    ([i, v]) => {
                        try {
                            window.EJS_emulator.gameManager.simulateInput(0, i, v);
                            return true;
                        } catch {
                            return false;
                        }
                    },
                    [index, value],
                );
                console.log(`capture: input ${index}=${value} at frame ${n} (asked for ${at}${ok ? "" : ", input API missing"})`);
            }
            if (n >= target) break;
            await page.waitForTimeout(inputs.length ? 60 : 250);
        }
        const file = join(out, `shot-${target}.png`);
        const canvas = page.locator("#game canvas").first();
        await ((await canvas.count()) ? canvas : page.locator("#game")).screenshot({ path: file });
        const secs = (Date.now() - t0) / 1000;
        // Emulator state (holds the console's RAM): smoke_test.py reads the game's threads out of it.
        const state = join(out, `state-${target}.bin`);
        const b64 = await page.evaluate(() => {
            try {
                const s = window.EJS_emulator.gameManager.getState();
                let bin = "";
                for (let i = 0; i < s.length; i += 0x8000) bin += String.fromCharCode.apply(null, s.subarray(i, i + 0x8000));
                return btoa(bin);
            } catch (e) {
                return "";
            }
        });
        if (b64) writeFileSync(state, Buffer.from(b64, "base64"));
        result.shots.push({ frame: target, file, seconds: secs, state: b64 ? state : null });
        console.log(`capture: frame ${target} after ${secs.toFixed(1)} s -> ${file}`);
    }
    clearTimeout(watchdog);
    await finish(0);
} catch (e) {
    result.log.push(`[capture] ${e.stack || e}`);
    console.log(`capture: ${e.message || e}`);
    clearTimeout(watchdog);
    await finish(1);
}
