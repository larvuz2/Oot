// Unit tests for the web player's ROM pipeline. Compares the JS implementations
// against Node's crypto and against fixtures produced by the decomp's own Python
// tooling (see make_fixtures.py).
//
//   python3 web/tests/make_fixtures.py /tmp/fx && node web/tests/run.mjs /tmp/fx

import { createHash, randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { md5 } from "../js/md5.js";
import { crc32 } from "../js/crc32.js";
import { yaz0Decompress } from "../js/yaz0.js";
import { n64Checksum } from "../js/n64crc.js";
import { applyBps } from "../js/bps.js";
import { decompressRom, toBigEndian } from "../js/rom.js";
import { parseEnhance, rigOutputs, rigInput, imagesInput, isFalMediaUrl, isFalQueueUrl } from "../js/studio-pipeline.js";

const dir = process.argv[2];
if (!dir) {
    console.error("usage: node web/tests/run.mjs FIXTURE_DIR");
    process.exit(2);
}
const read = (f) => new Uint8Array(readFileSync(join(dir, f)));
const nodeMd5 = (b) => createHash("md5").update(b).digest("hex");
const manifest = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));

let failures = 0;
function check(name, ok, detail = "") {
    console.log(`${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : "  " + detail}`);
    if (!ok) failures++;
}
function equal(a, b) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
}

// MD5 across block-boundary lengths and a large buffer.
for (const n of [0, 1, 55, 56, 63, 64, 65, 119, 120, 1000, 5_000_003]) {
    const b = new Uint8Array(randomBytes(n));
    check(`md5 len=${n}`, md5(b) === nodeMd5(b));
}

// CRC32 vs. known vector.
check("crc32 '123456789'", crc32(new TextEncoder().encode("123456789")) === 0xcbf43926);

// Byte-order normalisation.
{
    const z = new Uint8Array(randomBytes(0x2000));
    z.set([0x80, 0x37, 0x12, 0x40]);
    const v = z.slice();
    for (let i = 0; i < v.length; i += 2) [v[i], v[i + 1]] = [v[i + 1], v[i]];
    const n = z.slice();
    for (let i = 0; i < n.length; i += 4) [n[i], n[i + 1], n[i + 2], n[i + 3]] = [n[i + 3], n[i + 2], n[i + 1], n[i]];
    check("byteorder v64", toBigEndian(v) === "v64" && equal(v, z));
    check("byteorder n64", toBigEndian(n) === "n64" && equal(n, z));
    check("byteorder z64", toBigEndian(z.slice()) === "z64");
}

for (const name of manifest.yaz0) {
    const out = yaz0Decompress(read(`${name}.yaz0`));
    check(`yaz0 ${name}`, equal(out, read(`${name}.bin`)));
}

for (const c of manifest.checksum) {
    const got = n64Checksum(read(c.file), c.cic);
    check(`cic ${c.cic} checksum`, got[0] === c.expected[0] && got[1] === c.expected[1], `${got} vs ${c.expected}`);
}

for (const name of manifest.bps) {
    const out = applyBps(read("bps-src.bin"), read(name));
    check(`bps ${name}`, equal(out, read("bps-tgt.bin")));
}

for (const r of manifest.roms) {
    const out = await decompressRom(read(`${r.name}.z64`), { dmadataStart: r.dmadataStart, ique: r.ique });
    const exp = read(`${r.name}.expected.z64`);
    check(`decompressRom ${r.name}`, equal(out, exp), `md5 ${nodeMd5(out)} vs ${nodeMd5(exp)}, len ${out.length} vs ${exp.length}`);
}

// Character Studio pipeline helpers.
{
    const e = parseEnhance('```json\n{"name":"Mummy","archetype":"mummy","prompt":"a mummy in T-pose"}\n```', "mummy");
    check("studio parseEnhance fenced JSON", e.name === "Mummy" && e.archetype === "mummy" && e.prompt === "a mummy in T-pose");
    const f = parseEnhance("not json", "a robot");
    check("studio parseEnhance fallback", f.archetype === "humanoid" && f.prompt.includes("a robot") && f.prompt.includes("T-pose"));
    check("studio unknown archetype -> humanoid", parseEnhance('{"archetype":"dragon","prompt":"x"}', "d").archetype === "humanoid");
    check("studio rig walk by archetype", JSON.stringify(rigInput("u", "zombie").animation_action_ids) === "[0,119]");
    check("studio images clamp", imagesInput("p", 99).num_images === 4 && imagesInput("p", 0).num_images === 1);
    const r = rigOutputs({ rigged_character_glb: { url: "r" }, animations: [{ animation_glb: { url: "i" } }, { animation_glb: { url: "w" } }] });
    check("studio rigOutputs", r.idleGlb === "i" && r.walkGlb === "w" && r.riggedGlb === "r");
    check("studio url checks", isFalMediaUrl("https://v3b.fal.media/x.glb") && !isFalMediaUrl("https://evil.com/x") && isFalQueueUrl("https://queue.fal.run/a") && !isFalQueueUrl("http://queue.fal.run/a"));
}

if (failures) {
    console.error(`${failures} test(s) failed`);
    process.exit(1);
}
console.log("All web pipeline tests passed");
