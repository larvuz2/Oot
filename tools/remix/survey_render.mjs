// Screenshots for tools/remix/survey_scenes.py: serves DIR (index.html, the room JSON files, plan.json) and
// renders each planned view to OUT_DIR. Needs the `playwright` package (NODE_PATH) and a Chromium.
//
//   node tools/remix/survey_render.mjs DIR OUT_DIR

import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { join, extname } from "node:path";

const [dir, outDir] = process.argv.slice(2);
const require = createRequire(join(process.cwd(), "noop.js"));
const { chromium } = require("playwright");
const types = { ".html": "text/html", ".json": "application/json" };
const server = createServer((req, res) => {
    const p = join(dir, decodeURIComponent(new URL(req.url, "http://x").pathname));
    if (!p.startsWith(dir) || !existsSync(p)) return res.writeHead(404).end();
    res.writeHead(200, { "content-type": types[extname(p)] || "application/octet-stream" });
    res.end(readFileSync(p));
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 960, height: 720 } });
page.on("pageerror", (e) => console.log("pageerror", e.message));
const plan = JSON.parse(readFileSync(join(dir, "plan.json"), "utf8"));
let n = 0;
for (const job of plan) {
    try {
        await page.goto(`${base}/index.html?file=${job.file}&entry=${job.entry}&mode=${job.mode}`);
        await page.waitForFunction(() => document.title !== "loading", null, { timeout: 60000 });
        await page.screenshot({ path: join(outDir, job.out) });
        n++;
    } catch (e) {
        console.log(`render ${job.out}: ${e.message}`);
    }
}
console.log(`rendered ${n}/${plan.length}`);
await browser.close();
server.close();
