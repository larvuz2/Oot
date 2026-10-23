#!/usr/bin/env python3
"""Boot a remix ROM straight into the Ancient Plateau in the website's own emulator and check it runs.

Sets the "boot into the new level" switch in a copy of the ROM (the same one the website's button uses, see
include/remix_level.h), runs it in EmulatorJS (web/) in headless Chromium through tools/remix/smoke_capture.mjs,
takes screenshots at a few frames (holding the stick forward after the second, so Link runs) and reports:
  - whether the player reported a crash or a stall,
  - whether each screenshot is not blank,
  - whether the picture changes over time (the game did not freeze),
  - a 96x54 thumbnail of each shot as hex, so a log reader can see roughly what was on screen.

    python3 tools/remix/smoke_test.py --rom build/ntsc-1.2/oot-ntsc-1.2.z64 --out /tmp/smoke

Needs: node, the `playwright` npm package (NODE_PATH or current directory) with a Chromium, Pillow.
Exit status is 0 when the level rendered and kept moving, 1 otherwise.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

HERE = Path(__file__).resolve().parent
MAGIC = b"RMXBOOT1"
SHOTS = [400, 900, 1500]  # emulator frames (60 per second)


BOOT_ANCIENT, BOOT_HYRULE_FIELD, BOOT_ISLAND_VIEW, BOOT_POOL_VIEW, BOOT_SHRINE, BOOT_SEEKER = 1, 2, 3, 4, 5, 6  # include/remix_level.h
BOOT_MAGNET, BOOT_MAGNET_TEST, BOOT_MAGNET_CHEST, BOOT_FORGE, BOOT_FORGE_TEST = 7, 8, 9, 10, 11
# EmulatorJS input indices (web/js/app.js KEYS)
IN_A, IN_L, IN_STICK_DOWN, IN_STICK_UP, IN_C_UP = 0, 10, 18, 19, 23


def set_boot_flag(rom: bytearray, mode: int = BOOT_ANCIENT) -> int:
    i = rom.find(MAGIC)
    if i < 0:
        raise SystemExit("smoke: RMXBOOT1 not found in the ROM (built without z_remix_level.c?)")
    rom[i + 8] = mode
    return i


def capture(rom: bytes, out: Path, frames, core: str, timeout: int, walk_after=None, query="", inputs=()) -> dict:
    """Run the ROM in the website's player (smoke_capture.mjs); returns its capture.json."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "rom.z64").write_bytes(rom)
    cmd = ["node", str(HERE / "smoke_capture.mjs"), "--rom", str(out / "rom.z64"), "--out", str(out),
           "--frames", ",".join(map(str, frames)), "--walk-after", str(walk_after or 10**9), "--timeout", str(timeout),
           "--core", core] + (["--query", query] if query else []) + \
        (["--inputs", ",".join(f"{f}:{i}:{v}" for f, i, v in inputs)] if inputs else [])
    try:
        p = subprocess.run(cmd, timeout=timeout + 60, capture_output=True, text=True)
        print((p.stdout + p.stderr).rstrip())
    except subprocess.TimeoutExpired:
        print("smoke: the capture script hung")
    (out / "rom.z64").unlink(missing_ok=True)
    f = out / "capture.json"
    cap = json.loads(f.read_text()) if f.exists() else {}
    if cap.get("crash"):
        print(f"smoke: CRASH reported by the player in {core}: {cap['crash']}")
    if cap.get("crash") or len(cap.get("shots", [])) < len(frames):
        print(f"smoke: reached frame {cap.get('frames')}; last browser log lines:")
        for line in [x for x in cap.get("log", []) if "Translation not found" not in x][-15:]:
            print("  | " + line)
    return cap


def describe(name: str, cap: dict):
    for shot in cap.get("shots", []):
        img = Image.open(shot["file"]).convert("RGB")
        colors = len(img.resize((160, 120)).getcolors(160 * 120) or [])
        print(f"smoke: {name} frame {shot['frame']}: mean={tuple(round(c) for c in ImageStat.Stat(img).mean)} "
              f"colors={colors}{' BLANK' if colors < 12 else ''}")
        print(f"smoke-thumb {name}-{shot['frame']} 96x54 " + img.resize((96, 54), Image.BILINEAR).tobytes().hex())
    speed(name, cap)


def speed(name: str, cap: dict):
    """Emulation speed between the first and last screenshot (60 frames a second = 100%; on CI's software GPU
    every run is slow, so compare runs with each other, not with 100%)."""
    shots = cap.get("shots", [])
    if len(shots) >= 2 and shots[-1]["seconds"] > shots[0]["seconds"]:
        fps = (shots[-1]["frame"] - shots[0]["frame"]) / (shots[-1]["seconds"] - shots[0]["seconds"])
        print(f"smoke: {name} speed {fps:.1f} frames/s ({fps / 60 * 100:.0f}% of full speed)")


EXC = {0: "interrupt", 1: "TLB mod", 2: "TLB load miss", 3: "TLB store miss", 4: "address error (load)",
       5: "address error (store)", 6: "bus error (fetch)", 7: "bus error (data)", 8: "syscall", 9: "breakpoint",
       10: "reserved instruction", 11: "coprocessor unusable", 12: "overflow", 13: "trap", 15: "FPU exception",
       23: "watch"}


def load_symbols(elf: Path):
    out = subprocess.run(["mips-linux-gnu-nm", "-n", str(elf)], capture_output=True, text=True).stdout
    syms = {}
    funcs = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3:
            addr = int(parts[0], 16)
            syms[parts[2]] = addr
            if parts[1] in "Tt" and addr >= 0x80000000:
                funcs.append((addr, parts[2]))
    return syms, funcs


def func_at(funcs, addr):
    best = None
    for a, name in funcs:
        if a > addr:
            break
        best = (a, name)
    if best is None or addr - best[0] > 0x4000:
        return f"0x{addr:08X} (overlay or unknown)"
    return f"{best[1]}+0x{addr - best[0]:X}"


def console_ram(state: bytes, rom: bytes, syms):
    """The console's 8 MB of RAM from an emulator state (big-endian), found by looking for the start of the code
    segment as the game loaded it."""
    rs, vs = syms.get("_codeSegmentRomStart"), syms.get("_codeSegmentStart")
    if rs is None or vs is None:
        return None
    pat = rom[rs + 0x40 : rs + 0x80]
    swapped = b"".join(pat[i : i + 4][::-1] for i in range(0, len(pat), 4))
    for p, swap in ((pat, False), (swapped, True)):
        off = state.find(p)
        if off >= 0:
            base = off - ((vs + 0x40) & 0x7FFFFF)
            ram = state[base : base + 0x800000]
            if swap:
                ram = b"".join(ram[i : i + 4][::-1] for i in range(0, len(ram), 4))
            return ram
    return None


def report_threads(state_path: Path, rom: bytes, elf: Path):
    """Where each of the game's threads stopped, and whether one of them crashed."""
    syms, funcs = load_symbols(elf)
    ram = console_ram(state_path.read_bytes(), rom, syms)
    if ram is None:
        print("smoke: could not find the console's RAM in the emulator state")
        return
    u32 = lambda a: int.from_bytes(ram[a & 0x7FFFFF : (a & 0x7FFFFF) + 4], "big")
    names = {a: n for n, a in syms.items()}
    if "gSaveContext" in syms:
        print(f"smoke:   entrance index 0x{u32(syms['gSaveContext']):X}")
    t = u32(syms["__osActiveQueue"]) if "__osActiveQueue" in syms else 0
    crashed = False
    for _ in range(40):
        if not (0x80000000 <= t < 0x80800000):
            break
        pri = u32(t + 4)
        if pri == 0xFFFFFFFF:
            break
        state, flags = u32(t + 0x10) >> 16, u32(t + 0x10) & 0xFFFF
        ctx = t + 0x20
        pc, cause, bad = u32(ctx + 0xFC), u32(ctx + 0x100), u32(ctx + 0x104)
        ra = u32(ctx + 0xE0 + 4)
        exc = (cause >> 2) & 0x1F
        fault = bool(flags & 2) or (exc not in (0,) and state == 1)
        crashed |= fault
        print(f"smoke:   thread {u32(t + 0x14):>3} {names.get(t, hex(t)):<16} pri {pri:<3} state {state} flags {flags} "
              f"pc {func_at(funcs, pc)} ra {func_at(funcs, ra)}"
              + (f"  CRASHED: {EXC.get(exc, exc)} at 0x{bad:08X}" if fault else ""))
        t = u32(t + 0xC)
    print("smoke:   a thread crashed" if crashed else "smoke:   no crashed thread")
    for name, label in (("sZeldaArena", "actor memory (Zelda arena)"), ("gSystemArena", "system heap")):
        arena = syms.get(name)
        if not arena:
            continue
        # N64 layout (include/libc64/os_malloc.h): Arena { head, start, size, allocFailures }, nodes of 0x30
        node, free, used, largest, n = u32(arena), 0, 0, 0, 0
        while 0x80000000 <= node < 0x80800000 and n < 4000:
            magic_free = u32(node)
            size = u32(node + 4)
            if (magic_free >> 16) != 0x7373:
                break
            if magic_free & 0xFFFF:
                free += size
                largest = max(largest, size)
            else:
                used += size
            node = u32(node + 8)
            n += 1
        fails = ram[(arena + 0xC) & 0x7FFFFF]
        print(f"smoke:   {label}: {used // 1024} KB used, {free // 1024} KB free (largest block {largest // 1024} KB), "
              f"{n} blocks, {fails} failed allocations")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--timeout", type=int, default=300, help="seconds per emulator run")
    ap.add_argument("--no-boot-flag", action="store_true", help="run the ROM as is (to test the harness itself)")
    ap.add_argument("--elf", type=Path, help="the ROM's ELF: report the game's threads from the emulator state")
    args = ap.parse_args()

    out = args.out
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    rom = bytearray(args.rom.read_bytes())
    if not args.no_boot_flag:
        at = set_boot_flag(rom)
        print(f"smoke: boot flag set at ROM offset 0x{at:X}")

    # The website ships two N64 cores; like a player would, try the other one if the first fails.
    cap = {}
    for core in ("mupen64plus_next", "parallel_n64"):
        print(f"smoke: running in {core}")
        cap = capture(bytes(rom), out / core, SHOTS, core, args.timeout, walk_after=SHOTS[1])
        if not cap.get("crash") and len(cap.get("shots", [])) == len(SHOTS):
            break

    shots = [Path(s["file"]) for s in cap.get("shots", [])]
    print(f"smoke: {len(shots)} screenshot(s)")
    speed("level", cap)
    ok = len(shots) == len(SHOTS) and not cap.get("crash")
    moved = None
    prev = None
    for i, path in enumerate(shots):
        img = Image.open(path).convert("RGB")
        stat = ImageStat.Stat(img)
        colors = len(img.resize((160, 120)).getcolors(160 * 120) or [])
        blank = colors < 12
        moved = None
        if prev is not None:
            a = img.resize((96, 54)).tobytes()
            b = prev.resize((96, 54)).tobytes()
            moved = sum(abs(x - y) for x, y in zip(a, b)) / len(a)
        print(f"smoke: shot {i} {path.name} {img.size[0]}x{img.size[1]} mean={tuple(round(c) for c in stat.mean)} "
              f"colors={colors}{' BLANK' if blank else ''}" + (f" change={moved:.1f}" if moved is not None else ""))
        thumb = img.resize((96, 54), Image.BILINEAR)
        print(f"smoke-thumb {i} 96x54 " + thumb.tobytes().hex())
        if blank:
            ok = False
        prev = img
    if len(shots) >= 2 and moved is not None and moved < 0.5:
        print("smoke: the last two shots are identical: the game may be frozen")
        ok = False
    if args.elf and args.elf.exists():
        for shot in cap.get("shots", []):
            if shot.get("state"):
                print(f"smoke: game threads at frame {shot['frame']}:")
                try:
                    report_threads(Path(shot["state"]), bytes(rom), args.elf)
                except Exception as e:  # diagnostics only
                    print(f"smoke:   could not read them ({e})")
    if not args.no_boot_flag and ok:
        # Views of the floating island (on top of it, and at the pool under its waterfall): pictures to look at,
        # and the same crash and memory checks.
        for name, mode in (("island-view", BOOT_ISLAND_VIEW), ("pool-view", BOOT_POOL_VIEW)):
            print(f"smoke: {name}")
            vrom = bytearray(args.rom.read_bytes())
            set_boot_flag(vrom, mode)
            vcap = capture(bytes(vrom), out / name, [400, 700], "mupen64plus_next", 240)
            describe(name, vcap)
            last = [s for s in vcap.get("shots", []) if s.get("state")]
            if vcap.get("crash"):
                ok = False
            if args.elf and args.elf.exists() and last:
                print(f"smoke: {name} at frame {last[-1]['frame']}:")
                try:
                    report_threads(Path(last[-1]["state"]), bytes(vrom), args.elf)
                except Exception as e:  # diagnostics only
                    print(f"smoke:   could not read them ({e})")
    if not args.no_boot_flag and ok:
        # Level 2: dropping into the Ember Shrine through its hole, then walking from the arrival chamber into the
        # hall (pictures, crash and memory checks)
        # (and level 3, the Seeker's Shrine, the same way)
        for name, mode in (("shrine", BOOT_SHRINE), ("seeker", BOOT_SEEKER), ("magnet", BOOT_MAGNET),
                           ("forge", BOOT_FORGE)):
            print(f"smoke: {name}")
            srom = bytearray(args.rom.read_bytes())
            set_boot_flag(srom, mode)
            scap = capture(bytes(srom), out / name, [300, 600, 1000], "mupen64plus_next", args.timeout, walk_after=420)
            describe(name, scap)
            if scap.get("crash") or len(scap.get("shots", [])) < 3:
                ok = False
            last = [s for s in scap.get("shots", []) if s.get("state")]
            if args.elf and args.elf.exists() and last:
                print(f"smoke: {name} at frame {last[-1]['frame']}:")
                try:
                    report_threads(Path(last[-1]["state"]), bytes(srom), args.elf)
                except Exception as e:  # diagnostics only
                    print(f"smoke:   could not read them ({e})")
    if not args.no_boot_flag and ok:
        # Level 4's new item: Magnesis, and level 5's fire basket. With the rune found, Link faces the iron slab in the north doorway: hold L
        # (grab), C-Up (lift), pull the stick back (bring it out of the doorway), let go (drop). Then, from a fresh
        # start in front of the rune's chest: A opens it and Link holds up the Magnesis Rune (the fal-made model).
        runs = (("magnesis", BOOT_MAGNET_TEST, [420, 520, 640, 760],
                 [(440, IN_L, 1), (460, IN_C_UP, 0x7FFF), (510, IN_C_UP, 0), (530, IN_STICK_DOWN, 0x7FFF),
                  (620, IN_STICK_DOWN, 0), (700, IN_L, 0)]),
                ("rune-chest", BOOT_MAGNET_CHEST, [420, 760, 900, 1020, 1150],
                 [(440, IN_A, 1), (480, IN_A, 0), (520, IN_A, 1), (550, IN_A, 0)]),
                # Level 5: the burning basket (lit by its eternal torch), carried by Magnesis to the first gate's
                # torch: the torch lights and the gate rises
                ("forge-flame", BOOT_FORGE_TEST, [420, 520, 640, 760],
                 [(440, IN_L, 1), (470, IN_STICK_UP, 0x7FFF), (580, IN_STICK_UP, 0), (640, IN_L, 0)]))
        for name, mode, frames, inputs in runs:
            print(f"smoke: {name}")
            mrom = bytearray(args.rom.read_bytes())
            set_boot_flag(mrom, mode)
            mcap = capture(bytes(mrom), out / name, frames, "mupen64plus_next", args.timeout, inputs=inputs)
            describe(name, mcap)
            if mcap.get("crash") or len(mcap.get("shots", [])) < len(frames):
                ok = False
    if not args.no_boot_flag and ok:
        # The website's performance mode (tablets and phones): the level boots and draws in it too.
        print("smoke: perf-mode")
        pcap = capture(bytes(rom), out / "perf-mode", SHOTS, "mupen64plus_next", args.timeout, walk_after=SHOTS[1],
                       query="perf=1&speed=1")
        describe("perf-mode", pcap)
        if pcap.get("crash") or len(pcap.get("shots", [])) < len(SHOTS):
            ok = False
    if not args.no_boot_flag:
        # Control: the same quick boot into Hyrule Field (memory to compare with; and if it shows pictures while
        # the new level does not, the level is at fault).
        print("smoke: control: the same quick boot into Hyrule Field")
        hf = bytearray(args.rom.read_bytes())
        set_boot_flag(hf, BOOT_HYRULE_FIELD)
        hcap = capture(bytes(hf), out / "control-hyrule-field", [400, 900], "mupen64plus_next", 240)
        describe("control-hyrule-field", hcap)
        last = [s for s in hcap.get("shots", []) if s.get("state")]
        if args.elf and args.elf.exists() and last:
            print(f"smoke: Hyrule Field at frame {last[-1]['frame']}:")
            try:
                report_threads(Path(last[-1]["state"]), bytes(hf), args.elf)
            except Exception as e:  # diagnostics only
                print(f"smoke:   could not read them ({e})")
    if not ok and not args.no_boot_flag:
        # The game booting normally (N64 logo, title screen): no pictures there either means the emulator setup.
        print("smoke: control 2: normal boot")
        describe("control-normal", capture(args.rom.read_bytes(), out / "control-normal", [300, 700],
                                           "mupen64plus_next", 240))
    for f in out.rglob("state-*.bin"):
        f.unlink()
    print("smoke: PASS" if ok else "smoke: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
