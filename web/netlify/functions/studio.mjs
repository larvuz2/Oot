// Character Studio backend (Netlify Function).
//
// Environment variables (Netlify > Site configuration > Environment variables):
//   FAL_KEY          your fal.ai key - image, 3D and rigging calls run with it, never sent to browsers
//   STUDIO_PASSWORD  required: visitors must enter it before anything is generated (protects your fal credits)
//   GITHUB_TOKEN     optional: fine-grained token with "Contents: read and write" on the repo, lets
//                    "Add to game" commit the character so the Remix build puts it in the ROM
//   GITHUB_REPO      optional, default "larvuz2/Oot"; GITHUB_BRANCH optional, default "main"

import {
    MODELS,
    enhanceInput,
    imagesInput,
    meshInput,
    rigInput,
    isFalQueueUrl,
    isFalMediaUrl,
    ARCHETYPES,
} from "../../js/studio-pipeline.js";

const env = (name) => (globalThis.Netlify?.env?.get(name) ?? process.env[name] ?? "").trim();

const json = (status, body) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

async function fal(url, body) {
    const res = await fetch(url, {
        method: body ? "POST" : "GET",
        headers: { authorization: `Key ${env("FAL_KEY")}`, "content-type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    let data;
    try {
        data = JSON.parse(text);
    } catch {
        data = { detail: text.slice(0, 500) };
    }
    if (!res.ok) {
        const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : data.detail || text;
        throw new Error(`fal ${res.status}: ${String(detail).slice(0, 400)}`);
    }
    return data;
}

const submit = (model, input) => fal(`https://queue.fal.run/${model}`, input).then((r) => ({ statusUrl: r.status_url, responseUrl: r.response_url }));

async function poll({ statusUrl, responseUrl }) {
    if (!isFalQueueUrl(statusUrl) || !isFalQueueUrl(responseUrl)) throw new Error("Bad request URL");
    const st = await fal(statusUrl);
    if (st.status !== "COMPLETED") return { done: false, status: st.status, position: st.queue_position ?? null };
    return { done: true, result: await fal(responseUrl) };
}

async function publish(character) {
    const token = env("GITHUB_TOKEN");
    if (!token) throw new Error("GITHUB_TOKEN is not set in Netlify, so the character can't be added automatically.");
    const repo = env("GITHUB_REPO") || "larvuz2/Oot";
    const branch = env("GITHUB_BRANCH") || "main";
    const c = {
        name: String(character.name || "Custom").slice(0, 18),
        archetype: ARCHETYPES[character.archetype] ? character.archetype : "humanoid",
        prompt: String(character.prompt || "").slice(0, 4000),
        image: character.image,
        modelGlb: character.modelGlb,
        riggedGlb: character.riggedGlb,
        idleGlb: character.idleGlb,
        walkGlb: character.walkGlb,
        createdAt: new Date().toISOString(),
    };
    for (const key of ["image", "idleGlb", "walkGlb"]) {
        if (!isFalMediaUrl(c[key])) throw new Error(`Missing or unexpected ${key} URL`);
    }
    const path = "assets/remix_character/character.json";
    const api = `https://api.github.com/repos/${repo}/contents/${path}`;
    const headers = { authorization: `Bearer ${token}`, accept: "application/vnd.github+json", "user-agent": "oot-web-remix-studio" };
    const existing = await fetch(`${api}?ref=${encodeURIComponent(branch)}`, { headers });
    const sha = existing.ok ? (await existing.json()).sha : undefined;
    const res = await fetch(api, {
        method: "PUT",
        headers,
        body: JSON.stringify({
            message: `Character Studio: add "${c.name}" to the game`,
            content: Buffer.from(JSON.stringify(c, null, 2) + "\n").toString("base64"),
            branch,
            sha,
        }),
    });
    if (!res.ok) throw new Error(`GitHub ${res.status}: ${(await res.text()).slice(0, 300)}`);
    const out = await res.json();
    return { commit: out.commit?.html_url || null, actions: `https://github.com/${repo}/actions` };
}

export default async (req) => {
    if (req.method === "GET") {
        return json(200, { server: !!env("FAL_KEY"), passwordSet: !!env("STUDIO_PASSWORD"), publish: !!env("GITHUB_TOKEN") });
    }
    if (req.method !== "POST") return json(405, { error: "Method not allowed" });

    let body;
    try {
        body = await req.json();
    } catch {
        return json(400, { error: "Bad JSON" });
    }
    if (!env("FAL_KEY")) return json(503, { error: "FAL_KEY is not set in Netlify." });
    if (!env("STUDIO_PASSWORD")) return json(503, { error: "Set STUDIO_PASSWORD in Netlify to protect your fal credits." });
    if (body.password !== env("STUDIO_PASSWORD")) return json(401, { error: "Wrong studio password." });

    try {
        switch (body.action) {
            case "check":
                return json(200, { ok: true });
            case "enhance":
                return json(200, await submit(MODELS.enhance, enhanceInput(body.idea || "")));
            case "images":
                return json(200, await submit(MODELS.images, imagesInput(body.prompt || "", body.count)));
            case "mesh":
                if (!isFalMediaUrl(body.imageUrl)) return json(400, { error: "Unexpected image URL" });
                return json(200, await submit(MODELS.mesh, meshInput(body.imageUrl)));
            case "rig":
                if (!isFalMediaUrl(body.modelUrl)) return json(400, { error: "Unexpected model URL" });
                return json(200, await submit(MODELS.rig, rigInput(body.modelUrl, body.archetype)));
            case "poll":
                return json(200, await poll(body));
            case "publish":
                return json(200, await publish(body.character || {}));
            default:
                return json(400, { error: "Unknown action" });
        }
    } catch (err) {
        return json(502, { error: err.message || String(err) });
    }
};

export const config = { path: "/api/studio" };
