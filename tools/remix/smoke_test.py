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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--timeout", type=int, default=480, help="seconds for the whole run")
    ap.add_argument("--no-boot-flag", action="store_true", help="run the ROM as is (to test the harness itself)")
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
    print("smoke: PASS" if ok else "smoke: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
