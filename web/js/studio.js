import {
    MODELS,
    ARCHETYPES,
    enhanceInput,
    parseEnhance,
    templatePrompt,
    imagesInput,
    meshInput,
    rigInput,
    rigOutputs,
} from "./studio-pipeline.js";

const $ = (id) => document.getElementById(id);
const API = "/api/studio";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---- persisted state (generation costs money; survive reloads) ----------------

const store = {
    get(k, d = null) {
        try {
            const v = localStorage.getItem(`studio.${k}`);
            return v === null ? d : JSON.parse(v);
        } catch {
            return d;
        }
    },
    set(k, v) {
        try {
            localStorage.setItem(`studio.${k}`, JSON.stringify(v));
        } catch {
            /* storage blocked */
        }
    },
};
let state = store.get("state", {});
const save = () => store.set("state", state);

// ---- backend: Netlify function (server keys) or the player's own fal key ------

const backend = {
    mode: null, // "server" | "direct" | null
    publish: false,
    password: store.get("password", ""),
    falKey: store.get("falKey", ""),

    async init() {
        try {
            const res = await fetch(API, { cache: "no-store" });
            if (res.ok) {
                const cfg = await res.json();
                this.publish = cfg.publish;
                if (cfg.server && cfg.passwordSet) this.mode = "server";
                else if (cfg.server) this.serverNote = "FAL_KEY is set but STUDIO_PASSWORD isn't, so the server keys are locked.";
            }
        } catch {
            /* static hosting without functions */
        }
        if (!this.mode) this.mode = this.falKey ? "direct" : null;
    },

    async server(action, payload = {}) {
        const res = await fetch(API, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ action, password: this.password, ...payload }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        return data;
    },

    async direct(url, body) {
        const res = await fetch(url, {
            method: body ? "POST" : "GET",
            headers: { authorization: `Key ${this.falKey}`, "content-type": "application/json" },
            body: body ? JSON.stringify(body) : undefined,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            const d = Array.isArray(data.detail) ? data.detail.map((x) => x.msg).join("; ") : data.detail;
            throw new Error(`fal ${res.status}: ${d || "request failed"}`);
        }
        return data;
    },

    /** Start a job; returns {statusUrl, responseUrl}. */
    async submit(step, args) {
        if (this.mode === "server") return this.server(step, args);
        const inputs = {
            enhance: () => [MODELS.enhance, enhanceInput(args.idea)],
            images: () => [MODELS.images, imagesInput(args.prompt, args.count)],
            mesh: () => [MODELS.mesh, meshInput(args.imageUrl)],
            rig: () => [MODELS.rig, rigInput(args.modelUrl, args.archetype)],
        }[step]();
        const r = await this.direct(`https://queue.fal.run/${inputs[0]}`, inputs[1]);
        return { statusUrl: r.status_url, responseUrl: r.response_url };
    },

    async poll(job) {
        if (this.mode === "server") return this.server("poll", job);
        const st = await this.direct(job.statusUrl);
        if (st.status !== "COMPLETED") return { done: false, status: st.status, position: st.queue_position ?? null };
        return { done: true, result: await this.direct(job.responseUrl) };
    },

    /** Submit (or resume) a job and wait for its result, reporting progress. */
    async run(step, args, onProgress, resumeJob) {
        const job = resumeJob || (await this.submit(step, args));
        state.pending = { step, args, job };
        save();
        const t0 = Date.now();
        for (;;) {
            const r = await this.poll(job);
            if (r.done) {
                state.pending = null;
                save();
                return r.result;
            }
            const secs = Math.round((Date.now() - t0) / 1000);
            onProgress(r.status === "IN_QUEUE" ? `queued${r.position != null ? ` (#${r.position + 1})` : ""}` : "working", secs);
            await sleep(step === "enhance" || step === "images" ? 1500 : 5000);
        }
    },
};

// ---- UI helpers -----------------------------------------------------------------

function status(id, text, isError = false) {
    const el = $(id);
    el.textContent = text;
    el.classList.toggle("error", isError);
}

function setBusy(busy) {
    for (const id of ["generate", "regenerate", "build", "publish"]) $(id).disabled = busy;
    if (!busy) refreshButtons();
}

function refreshButtons() {
    const ready = !!backend.mode;
    $("generate").disabled = !ready;
    $("regenerate").disabled = !ready;
    $("build").disabled = !ready || state.selected == null || !state.images?.length;
    $("publish").disabled = !ready || !state.rig?.walkGlb;
}

function renderSetup() {
    const text = $("mode-text");
    $("password-row").hidden = true;
    $("key-row").hidden = true;
    if (backend.mode === "server") {
        text.textContent = backend.password
            ? `Using this site's fal key (server). ${backend.publish ? '"Add to game" commits automatically.' : 'GITHUB_TOKEN isn\'t set, so "Add to game" gives you a file to upload.'}`
            : "This site has a fal key set up. Enter the studio password to use it.";
        $("password-row").hidden = !!backend.password;
    } else {
        text.textContent =
            (backend.serverNote ? backend.serverNote + " " : "") +
            (backend.falKey
                ? "Using your own fal key, stored only in this browser."
                : "No server key is set up for this site. Paste your fal.ai API key (stays in this browser), or ask the site owner to set FAL_KEY and STUDIO_PASSWORD in Netlify.");
        $("key-row").hidden = !!backend.falKey;
    }
    refreshButtons();
}

function renderEnhanced() {
    const e = state.enhanced;
    $("prompt-details").hidden = !e;
    if (!e) return;
    $("prompt").value = e.prompt;
    $("char-meta").textContent = `— ${e.name} · ${ARCHETYPES[e.archetype]?.label || e.archetype}`;
}

function renderImages() {
    const box = $("images");
    box.replaceChildren(
        ...(state.images || []).map((url, i) => {
            const b = document.createElement("button");
            b.type = "button";
            b.setAttribute("aria-pressed", String(state.selected === i));
            b.setAttribute("aria-label", `Concept ${i + 1}`);
            const img = document.createElement("img");
            img.src = url;
            img.alt = `Concept ${i + 1}`;
            img.loading = "lazy";
            b.append(img);
            b.addEventListener("click", () => {
                state.selected = i;
                state.mesh = null;
                state.rig = null;
                save();
                renderImages();
                renderPreview();
                refreshButtons();
            });
            return b;
        }),
    );
}

function renderPreview() {
    const r = state.rig;
    $("preview").hidden = !r;
    if (!r) return;
    $("viewer").src = r.walkGlb || r.idleGlb;
    $("download-glb").href = r.riggedGlb || r.walkGlb;
}

// ---- steps ------------------------------------------------------------------------

async function generate(fromPrompt) {
    setBusy(true);
    try {
        if (!fromPrompt) {
            const idea = $("idea").value.trim();
            if (!idea) return;
            state = { idea };
            save();
            renderImages();
            renderPreview();
            status("idea-status", "Writing a detailed prompt…");
            try {
                const out = await backend.run("enhance", { idea }, () => {});
                state.enhanced = parseEnhance(out.output, idea);
            } catch (err) {
                console.warn("Prompt enhancement failed, using template", err);
                state.enhanced = { name: idea.slice(0, 18), archetype: "humanoid", prompt: templatePrompt(idea) };
            }
            save();
            renderEnhanced();
        } else {
            state.enhanced.prompt = $("prompt").value.trim();
        }
        status("idea-status", "Drawing 4 concepts in T-pose with GPT Image 2.5…");
        const out = await backend.run("images", { prompt: state.enhanced.prompt, count: 4 }, (s, secs) =>
            status("idea-status", `Drawing 4 concepts with GPT Image 2.5… ${s}, ${secs}s`),
        );
        state.images = (out.images || []).map((im) => im.url);
        state.selected = null;
        state.mesh = null;
        state.rig = null;
        save();
        renderImages();
        status("idea-status", "Pick the concept you like best, then build it in step 2.");
    } catch (err) {
        status("idea-status", err.message, true);
    } finally {
        setBusy(false);
    }
}

async function build() {
    setBusy(true);
    // A job that was still running when the page was closed is picked up instead of paid for again.
    const pending = state.pending;
    const resume = (step) => (pending && pending.step === step ? pending.job : undefined);
    try {
        const imageUrl = state.images[state.selected];
        if (!state.mesh) {
            const out = await backend.run("mesh", { imageUrl }, (s, secs) =>
                status("build-status", `Step 1/2: building the 3D model (Meshy)… ${s}, ${Math.floor(secs / 60)}m ${secs % 60}s (usually ~3 min)`),
            resume("mesh"));
            state.mesh = { modelGlb: out.model_glb.url, thumbnail: out.thumbnail?.url || null };
            save();
        }
        const archetype = state.enhanced?.archetype || "humanoid";
        const out = await backend.run("rig", { modelUrl: state.mesh.modelGlb, archetype }, (s, secs) =>
            status("build-status", `Step 2/2: rigging + idle and "${ARCHETYPES[archetype].label}" animations… ${s}, ${secs}s (usually ~1 min)`),
        resume("rig"));
        state.rig = rigOutputs(out);
        save();
        renderPreview();
        status("build-status", "Done! Spin it around, try Idle and Walk, then add it to the game.");
    } catch (err) {
        status("build-status", err.message, true);
    } finally {
        setBusy(false);
    }
}

function characterJson() {
    return {
        name: state.enhanced?.name || state.idea || "Custom",
        archetype: state.enhanced?.archetype || "humanoid",
        prompt: state.enhanced?.prompt || "",
        image: state.images[state.selected],
        modelGlb: state.mesh?.modelGlb,
        ...state.rig,
    };
}

async function publish() {
    setBusy(true);
    try {
        if (backend.mode === "server" && backend.publish) {
            status("publish-status", "Adding to the repo…");
            const r = await backend.server("publish", { character: characterJson() });
            const link = document.createElement("a");
            link.href = r.actions;
            link.textContent = "watch the build";
            status("publish-status", "Added! The Remix build is converting it now (~15 min) - ");
            $("publish-status").append(link, ". Reload the game when it's done.");
        } else {
            const blob = new Blob([JSON.stringify(characterJson(), null, 2) + "\n"], { type: "application/json" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "character.json";
            a.click();
            status(
                "publish-status",
                'Downloaded character.json. On GitHub, open the repo, go to the folder assets/remix_character, choose "Add file → Upload files", upload it to replace the old one and commit to main. The Remix build does the rest (~15 min).',
            );
        }
    } catch (err) {
        status("publish-status", err.message, true);
    } finally {
        setBusy(false);
    }
}

// ---- wiring -------------------------------------------------------------------------

$("idea-form").addEventListener("submit", (e) => {
    e.preventDefault();
    generate(false);
});
$("regenerate").addEventListener("click", () => generate(true));
$("build").addEventListener("click", build);
$("publish").addEventListener("click", publish);
$("show-idle").addEventListener("click", () => state.rig && ($("viewer").src = state.rig.idleGlb));
$("show-walk").addEventListener("click", () => state.rig && ($("viewer").src = state.rig.walkGlb));
$("password-save").addEventListener("click", async () => {
    backend.password = $("password").value;
    try {
        await backend.server("check");
        store.set("password", backend.password);
        renderSetup();
    } catch (err) {
        $("mode-text").textContent = err.message;
    }
});
$("key-save").addEventListener("click", () => {
    backend.falKey = $("fal-key").value.trim();
    if (!backend.falKey) return;
    store.set("falKey", backend.falKey);
    backend.mode = "direct";
    renderSetup();
});

(async function init() {
    await backend.init();
    renderSetup();
    if (state.idea) $("idea").value = state.idea;
    renderEnhanced();
    renderImages();
    renderPreview();
    refreshButtons();
    // Resume a job that was running when the page was closed.
    if (state.pending && backend.mode && (backend.mode === "direct" || backend.password)) {
        const { step, args, job } = state.pending;
        const target = step === "mesh" || step === "rig" ? "build-status" : "idea-status";
        status(target, "Resuming…");
        if (step === "mesh" || step === "rig") {
            build();
        } else {
            setBusy(true);
            backend
                .run(step, args, () => {}, job)
                .then((out) => {
                    if (step === "images") {
                        state.images = (out.images || []).map((im) => im.url);
                        save();
                        renderImages();
                    }
                    status(target, "Pick the concept you like best, then build it in step 2.");
                })
                .catch((err) => status(target, err.message, true))
                .finally(() => setBusy(false));
        }
    }
})();
