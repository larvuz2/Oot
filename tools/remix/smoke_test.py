#!/usr/bin/env python3
"""Boot a remix ROM straight into the Ancient Plateau in mupen64plus (headless) and check it runs.

Sets the "boot into the new level" switch in a copy of the ROM (the same one the website's button uses, see
include/remix_level.h), runs the emulator under Xvfb, takes screenshots at a few frames and reports:
  - whether each screenshot exists and is not blank,
  - whether the picture changes over time (the game did not freeze),
  - a 48x27 thumbnail of each shot as hex, so a log reader can see roughly what was on screen.

    python3 tools/remix/smoke_test.py --rom build/ntsc-1.2/oot-ntsc-1.2.z64 --out /tmp/smoke

Needs: mupen64plus-ui-console, mupen64plus-rsp-hle, a video plugin (glide64mk2), xvfb, Mesa, Pillow.
Exit status is 0 when the level rendered and kept moving, 1 otherwise.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

MAGIC = b"RMXBOOT1"
SHOTS = [240, 600, 1200]  # VI frames (60 per second)


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
    ap.add_argument("--gfx", default="mupen64plus-video-glide64mk2")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    out = args.out
    shutil.rmtree(out, ignore_errors=True)
    (out / "cfg").mkdir(parents=True)
    (out / "data").mkdir()
    rom = bytearray(args.rom.read_bytes())
    at = set_boot_flag(rom)
    (out / "boot.z64").write_bytes(rom)
    print(f"smoke: boot flag set at ROM offset 0x{at:X}")

    exe = shutil.which("mupen64plus") or "/usr/games/mupen64plus"
    cmd = ["xvfb-run", "-a", "-s", "-screen 0 640x480x24", exe, "--noosd", "--nospeedlimit", "--nosaveoptions",
           "--configdir", str(out / "cfg"), "--datadir", str(out / "data"), "--gfx", args.gfx,
           "--rsp", "mupen64plus-rsp-hle", "--audio", "dummy", "--input", "dummy", "--emumode", "2",
           "--testshots", ",".join(map(str, SHOTS)), "--sshotdir", str(out), str(out / "boot.z64")]
    env = dict(os.environ, SDL_AUDIODRIVER="dummy")
    try:
        p = subprocess.run(cmd, env=env, timeout=args.timeout, capture_output=True, text=True)
        log = p.stdout + p.stderr
        print(f"smoke: emulator exited with {p.returncode}")
    except subprocess.TimeoutExpired as e:
        log = (e.stdout or b"").decode(errors="replace") + (e.stderr or b"").decode(errors="replace")
        print("smoke: emulator timed out")
    (out / "emulator.log").write_text(log)
    for line in log.splitlines()[-15:]:
        print("  | " + line)

    shots = sorted(out.glob("*.png"), key=lambda q: q.stat().st_mtime)
    print(f"smoke: {len(shots)} screenshot(s)")
    ok = len(shots) >= 2
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
