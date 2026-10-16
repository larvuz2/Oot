// Character Studio pipeline: which fal models run, with which inputs.
// Shared by the browser (direct mode, the player's own fal key) and the Netlify
// function (server mode, keys kept in Netlify environment variables).

export const MODELS = {
    enhance: "openrouter/router",
    images: "openai/gpt-image-2.5/flare/text-to-image",
    mesh: "meshy/v7.1/image-to-3d",
    rig: "fal-ai/meshy/rigging/multi-animation",
};

export const ENHANCE_LLM = "google/gemini-2.5-flash";

export const ARCHETYPES = {
    // walk animation from Meshy's library for each kind of character
    humanoid: { walk: 106, label: "Confident walk" },
    zombie: { walk: 119, label: "Slow lurching walk" },
    mummy: { walk: 113, label: "Mummy stagger" },
    monster: { walk: 112, label: "Monster walk" },
    elderly: { walk: 553, label: "Shaky walk" },
    sneaky: { walk: 559, label: "Sneaky walk" },
    royal: { walk: 114, label: "Proud strut" },
    robot: { walk: 123, label: "Unsteady walk" },
};
export const IDLE_ANIMATION = 0;

const SYSTEM_PROMPT = `You turn a short character idea into a prompt for an image model that makes a 3D-modelling reference for a Nintendo 64 Zelda: Ocarina of Time style game.
Reply with ONLY a JSON object: {"name": short display name (max 18 chars), "archetype": one of [${Object.keys(ARCHETYPES)
    .map((a) => `"${a}"`)
    .join(",")}], "prompt": the image prompt}.
The prompt must describe ONE full-body humanoid character standing in a strict T-pose (arms straight out horizontally, palms down, legs slightly apart), front view, centered, whole body visible from head to feet, symmetrical, neutral expression, clear readable silhouette with separated limbs, simple bold shapes and flat colours suited to a low-poly 3D model, no weapons or props, plain pure-white background, no shadows, no text.
Keep it family-friendly like Ocarina of Time itself: no blood, gore, wounds, exposed bones or organs, nudity or scary realism - make monsters cartoonish.
Add concrete details about clothing, colours, materials and proportions that make the idea recognisable.`;

export function enhanceInput(idea) {
    return {
        model: ENHANCE_LLM,
        system_prompt: SYSTEM_PROMPT,
        prompt: `Character idea: ${String(idea).slice(0, 300)}`,
        temperature: 0.7,
    };
}

/** Fallback when the LLM step fails: a fixed template around the idea. */
export function templatePrompt(idea) {
    return (
        `A ${idea}, full-body 3D game character for a Nintendo 64 Zelda: Ocarina of Time style game, ` +
        "standing in a strict T-pose with arms straight out horizontally and legs slightly apart, front view, centered, " +
        "whole body visible from head to feet, symmetrical, simple bold low-poly shapes and flat colours, family-friendly, " +
        "no weapons or props, plain pure-white background, no shadows, no text."
    );
}

export function parseEnhance(output, idea) {
    try {
        const json = JSON.parse(String(output).replace(/```(json)?/g, "").trim());
        const archetype = ARCHETYPES[json.archetype] ? json.archetype : "humanoid";
        return {
            name: String(json.name || idea).slice(0, 18),
            archetype,
            prompt: String(json.prompt || templatePrompt(idea)),
        };
    } catch {
        return { name: String(idea).slice(0, 18), archetype: "humanoid", prompt: templatePrompt(idea) };
    }
}

export function imagesInput(prompt, count = 4) {
    return {
        prompt: String(prompt).slice(0, 4000),
        image_size: "square_hd",
        quality: "medium",
        num_images: Math.max(1, Math.min(4, count | 0)),
        background: "opaque",
        output_format: "png",
    };
}

export function meshInput(imageUrl) {
    return {
        image_url: imageUrl,
        model_type: "standard",
        topology: "triangle",
        target_polycount: 6000,
        pose_mode: "t-pose",
        symmetry_mode: "auto",
        should_texture: true,
        // fal's pre-check rejects harmless cartoon monsters (zombies, mummies); the prompt
        // already asks for family-friendly characters.
        enable_safety_checker: false,
    };
}

export function rigInput(modelUrl, archetype) {
    const walk = (ARCHETYPES[archetype] || ARCHETYPES.humanoid).walk;
    return { model_url: modelUrl, animation_action_ids: [IDLE_ANIMATION, walk], height_meters: 1.7 };
}

/** Pull the GLB URLs the game needs out of a rigging result. */
export function rigOutputs(result) {
    const anims = result.animations || [];
    return {
        riggedGlb: result.rigged_character_glb?.url || null,
        idleGlb: anims[0]?.animation_glb?.url || result.rigged_character_glb?.url || null,
        walkGlb: anims[1]?.animation_glb?.url || result.basic_animations?.walking_glb?.url || null,
    };
}

export function isFalQueueUrl(url) {
    try {
        const u = new URL(url);
        return u.protocol === "https:" && u.hostname === "queue.fal.run";
    } catch {
        return false;
    }
}

export function isFalMediaUrl(url) {
    try {
        const u = new URL(url);
        return u.protocol === "https:" && (u.hostname.endsWith(".fal.media") || u.hostname === "fal.media");
    } catch {
        return false;
    }
}
