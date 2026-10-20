// "Boot straight into the new level": the remix ROM carries a small struct starting with the magic
// "RMXBOOT1" (gRemixBootConfig in src/code/z_remix_level.c). Setting the byte after it makes the game skip the
// title screen and start a test save in the Ancient Plateau.

const MAGIC = [0x52, 0x4d, 0x58, 0x42, 0x4f, 0x4f, 0x54, 0x31]; // "RMXBOOT1"

export const BOOT_NORMAL = 0;
export const BOOT_ANCIENT_PLATEAU = 1;

/** Find the boot struct in a big-endian (.z64) ROM. Returns its offset, or -1. */
export function findBootConfig(rom) {
    const first = MAGIC[0];
    for (let i = rom.indexOf(first, 0x1000); i !== -1 && i + MAGIC.length < rom.length; i = rom.indexOf(first, i + 1)) {
        let k = 1;
        while (k < MAGIC.length && rom[i + k] === MAGIC[k]) k++;
        if (k === MAGIC.length) return i;
    }
    return -1;
}

/** Set the boot mode in place. Returns false if this ROM has no boot struct (an older remix build). */
export function setBootMode(rom, mode) {
    const at = findBootConfig(rom);
    if (at < 0) return false;
    rom[at + 8] = mode;
    return true;
}
