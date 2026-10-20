"""Restyle textures borrowed from other scenes so they match the Ancient Plateau (used by make_town.py).

Each texture keeps its size, alpha and detail (planks, tiles, stone joints: its brightness pattern) and gets
the colors of an Ancient Plateau material through a gradient map, chosen from what the texture looks like and
where it is used: pale walls become blue-grey Sheikah stone with faint teal veins, wood becomes dark
weathered wood, roofs become teal slate, windows glow teal, metal turns to bronze, plants stay as they are.
"""

from __future__ import annotations

import colorsys

import numpy as np

# (dark, mid, light) colors of each material
PALETTES = {
    "plaster": ((46, 52, 64), (116, 126, 140), (196, 204, 212)),
    "stone": ((34, 38, 46), (84, 92, 104), (156, 164, 176)),
    "wood": ((30, 26, 26), (74, 64, 60), (136, 120, 108)),
    "roof": ((18, 34, 42), (40, 82, 92), (92, 160, 166)),
    "window": ((8, 34, 44), (40, 150, 170), (150, 245, 255)),
    "metal": ((54, 34, 18), (150, 92, 40), (236, 172, 92)),
    "cloth": ((40, 30, 48), (110, 70, 120), (196, 150, 196)),
}
KEEP = ("plant", "dirt")


def classify(rgb_mean, fmt: str, usage: dict, has_alpha: bool, name: str = "") -> str:
    """Material class of a texture from its mean color and how it is used (usage: floor, wall, roof areas)."""
    r, g, b = (float(v) / 255 for v in rgb_mean)
    h, light, sat = colorsys.rgb_to_hls(r, g, b)
    hue = h * 360
    floor, wall, roof = usage.get("floor", 0), usage.get("wall", 0), usage.get("roof", 0)
    lname = name.lower()
    if "window" in lname or "seg:" in lname:
        return "window"
    if roof > max(wall, floor) * 0.8 and roof > 0:  # whatever its color, it covers roofs
        return "roof"
    if sat > 0.22 and 70 <= hue <= 170 and light > 0.12:
        return "plant"
    if fmt.startswith(("i4", "i8", "ia")) and not has_alpha:
        return "stone"
    if 15 <= hue <= 50 and sat > 0.18 and light < 0.55:
        return "dirt" if floor > 2 * (wall + roof) else "wood"
    if light > 0.58 and sat < 0.3:
        return "plaster"
    if 180 <= hue <= 260 and sat > 0.2:
        return "roof"
    if 0 <= hue < 15 or hue > 330:
        return "cloth" if sat > 0.35 else "wood"
    return "stone"


def gradient(lum: np.ndarray, pal) -> np.ndarray:
    """Map brightness 0..1 through dark -> mid -> light."""
    dark, mid, light = (np.array(c, float) for c in pal)
    t = np.clip(lum, 0, 1)[..., None]
    lo = dark + (mid - dark) * np.clip(t * 2, 0, 1)
    hi = mid + (light - mid) * np.clip(t * 2 - 1, 0, 1)
    return np.where(t < 0.5, lo, hi)


def restyle(rgba: np.ndarray, cls: str, seed: int = 0) -> np.ndarray:
    """New RGBA uint8 array, same size and alpha, in the colors of the material class."""
    a = rgba.astype(float)
    if cls in KEEP:
        out = a.copy()
        if cls == "dirt":  # a little cooler, like the Plateau's paths
            out[..., :3] = out[..., :3] * np.array([0.92, 0.95, 1.0])
        return np.clip(out, 0, 255).astype(np.uint8)
    lum = (a[..., 0] * 0.3 + a[..., 1] * 0.59 + a[..., 2] * 0.11) / 255
    opaque = a[..., 3] >= 128
    if opaque.any():  # stretch the contrast so every texture uses its whole palette
        lo, hi = np.percentile(lum[opaque], 3), np.percentile(lum[opaque], 97)
        if hi - lo > 0.04:
            lum = (lum - lo) / (hi - lo) * 0.9 + 0.05
    out = gradient(lum, PALETTES[cls])
    if cls == "plaster":
        out = _veins(out, seed)
    res = np.concatenate([out, a[..., 3:4]], -1)
    return np.clip(np.round(res), 0, 255).astype(np.uint8)


def _veins(rgb: np.ndarray, seed: int) -> np.ndarray:
    """Faint teal circuit lines (straight runs with right-angle turns) over stone, like the Plateau's monoliths."""
    h, w = rgb.shape[:2]
    rng = np.random.default_rng(seed)
    mask = np.zeros((h, w))
    for _ in range(max(1, (w * h) // 1024)):
        y, x = int(rng.integers(h)), int(rng.integers(w))
        for _seg in range(3):
            if rng.random() < 0.5:
                x2 = int(np.clip(x + rng.integers(-w // 2, w // 2), 0, w - 1))
                mask[y, min(x, x2) : max(x, x2) + 1] = 1
                x = x2
            else:
                y2 = int(np.clip(y + rng.integers(-h // 2, h // 2), 0, h - 1))
                mask[min(y, y2) : max(y, y2) + 1, x] = 1
                y = y2
    teal = np.array([70, 200, 215], float)
    return rgb * (1 - 0.45 * mask[..., None]) + teal * 0.45 * mask[..., None]
