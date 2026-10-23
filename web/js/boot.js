// "Boot straight into a new level": the remix ROM carries a small struct starting with the magic
// "RMXBOOT1" (gRemixBootConfig in src/code/z_remix_level.c). Setting the byte after it makes the game skip the
// title screen and start a test save in that level (include/remix_level.h: REMIX_BOOT_*).

const MAGIC = [0x52, 0x4d, 0x58, 0x42, 0x4f, 0x4f, 0x54, 0x31]; // "RMXBOOT1"

export const BOOT_NORMAL = 0;
export const BOOT_ANCIENT_PLATEAU = 1; // level 1
export const BOOT_EMBER_SHRINE = 5; // level 2: dropping into the Ember Shrine from its hole
export const BOOT_SEEKER_SHRINE = 6; // level 3: the Seeker's Shrine (with nothing but the sword)
export const BOOT_LODESTONE_SHRINE = 7; // level 4: the Lodestone Shrine (Magnesis)
export const BOOT_FORGE_SHRINE = 10; // level 5: the Forge Shrine (Magnesis and fire)
export const BOOT_TIME_TEMPLE = 12; // level 6: the Temple of Two Truths (the Song of Time, child and adult)
export const BOOT_SEVEN_YEARS = 16; // level 7: the Shrine of Seven Years (the Master Sword's pedestal)

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
