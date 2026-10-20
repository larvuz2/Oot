#!/usr/bin/env python3
"""Boot a remix ROM straight into the Ancient Plateau in the website's own emulator and check it runs.

Sets the "boot into the new level" switch in a copy of the ROM (the same one the website's button uses, see
include/remix_level.h), runs it in EmulatorJS (web/) in headless Chromium through tools/remix/smoke_capture.mjs,
takes screenshots at a few frames (holding the stick forward after the second, so Link runs) and reports:
  - whether the player reported a crash or a stall,
  - whether each screenshot is not blank,
  - whether the picture changes over time (the game did not freeze),
  - a 48x27 thumbnail of each shot as hex, so a log reader can see roughly what was on screen.

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


def set_boot_flag(rom: bytearray) -> int:
    i = rom.find(MAGIC)
    if i < 0:
        raise SystemExit("smoke: RMXBOOT1 not found in the ROM (built without z_remix_level.c?)")
    rom[i + 8] = 1
    return i


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
        ra, sp = u32(ctx + 0xE0 + 4), u32(ctx + 0xD0 + 4)
        exc = (cause >> 2) & 0x1F
        fault = bool(flags & 2) or (exc not in (0,) and state == 1)
        crashed |= fault
        print(f"smoke:   thread {u32(t + 0x14):>3} {names.get(t, hex(t)):<16} pri {pri:<3} state {state} flags {flags} "
              f"pc {func_at(funcs, pc)} ra {func_at(funcs, ra)}"
              + (f"  CRASHED: {EXC.get(exc, exc)} at 0x{bad:08X}" if fault else ""))
        t = u32(t + 0xC)
    print("smoke:   a thread crashed" if crashed else "smoke:   no crashed thread")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--timeout", type=int, default=480, help="seconds for the whole run")
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
    (out / "boot.z64").write_bytes(rom)

    # The website ships two N64 cores; like a player would, try the other one if the first crashes.
    cap = {}
    for core in ("mupen64plus_next", "parallel_n64"):
        print(f"smoke: running in {core}")
        cmd = ["node", str(HERE / "smoke_capture.mjs"), "--rom", str(out / "boot.z64"), "--out", str(out / core),
               "--frames", ",".join(map(str, SHOTS)), "--walk-after", str(SHOTS[1]), "--timeout", str(args.timeout),
               "--core", core]
        try:
            p = subprocess.run(cmd, timeout=args.timeout + 60, capture_output=True, text=True)
            print((p.stdout + p.stderr).rstrip())
        except subprocess.TimeoutExpired:
            print("smoke: the capture script hung")
        f = out / core / "capture.json"
        cap = json.loads(f.read_text()) if f.exists() else {}
        if cap.get("crash"):
            print(f"smoke: CRASH reported by the player in {core}: {cap['crash']}")
        if cap.get("crash") or len(cap.get("shots", [])) < len(SHOTS):
            print(f"smoke: reached frame {cap.get('frames')}; last browser log lines:")
            for line in [x for x in cap.get("log", []) if "Translation not found" not in x][-25:]:
                print("  | " + line)
        if not cap.get("crash"):
            break
    (out / "boot.z64").unlink(missing_ok=True)

    shots = [Path(s["file"]) for s in cap.get("shots", [])]
    print(f"smoke: {len(shots)} screenshot(s)")
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
        thumb = img.resize((48, 27), Image.BILINEAR)
        print(f"smoke-thumb {i} 48x27 " + thumb.tobytes().hex())
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
    if not ok and not args.no_boot_flag:
        # Control run: the same ROM booting normally (N64 logo, title screen). Pictures there but not in the level
        # means the level boot is at fault; none there either means the emulator setup is.
        print("smoke: control run without the boot flag:")
        (out / "control.z64").write_bytes(args.rom.read_bytes())
        p = subprocess.run(["node", str(HERE / "smoke_capture.mjs"), "--rom", str(out / "control.z64"), "--out",
                            str(out / "control"), "--frames", "300,700", "--walk-after", "99999", "--timeout", "240"],
                           capture_output=True, text=True)
        print((p.stdout + p.stderr).rstrip())
        (out / "control.z64").unlink(missing_ok=True)
        for f in sorted((out / "control").glob("shot-*.png")):
            img = Image.open(f).convert("RGB")
            colors = len(img.resize((160, 120)).getcolors(160 * 120) or [])
            print(f"smoke: control {f.name} mean={tuple(round(c) for c in ImageStat.Stat(img).mean)} colors={colors}")
            print(f"smoke-thumb control-{f.stem} 48x27 " + img.resize((48, 27), Image.BILINEAR).tobytes().hex())
    for f in out.rglob("state-*.bin"):
        f.unlink()
    print("smoke: PASS" if ok else "smoke: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
