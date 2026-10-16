#!/usr/bin/env python3
"""Identify an Ocarina of Time ROM dump: which decomp VERSION / REGION it is.

    python3 tools/web/identify_rom.py path/to/rom.z64 [--github-output]

Accepts .z64/.n64/.v64 byte orders and the overdumped debug ROMs, the same way
tools/decompress_baserom.py does. With --github-output the result is appended to
$GITHUB_OUTPUT as version=, region= and label= for use in workflows.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_versions import collect  # noqa: E402


def to_big_endian(data: bytearray) -> bytearray:
    if data[0] == 0x37:  # .v64, byte-swapped
        data[0::2], data[1::2] = data[1::2], data[0::2]
    elif data[0] == 0x40:  # .n64, little-endian words
        out = bytearray(len(data))
        out[0::4], out[1::4], out[2::4], out[3::4] = data[3::4], data[2::4], data[1::4], data[0::4]
        data = out
    elif data[0] != 0x80:
        raise SystemExit("error: not an N64 ROM (unknown header byte order)")
    return data


def identify(data: bytearray) -> dict | None:
    entries = collect()
    md5 = hashlib.md5(data).hexdigest()
    for e in entries:
        if md5 in (e["compressedMd5"], e["decompressedMd5"]):
            return e
    for e in entries:
        fix = e["fix"]
        if fix and len(data) > fix["truncate"]:
            fixed = bytearray(data[: fix["truncate"]])
            for off, val in fix["patch"]:
                fixed[off] = val
            if hashlib.md5(fixed).hexdigest() == e["decompressedMd5"]:
                return e
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=Path)
    ap.add_argument("--github-output", action="store_true")
    args = ap.parse_args()

    data = to_big_endian(bytearray(args.rom.read_bytes()))
    e = identify(data)
    if e is None:
        raise SystemExit(
            f"error: unrecognised ROM (md5 {hashlib.md5(data).hexdigest()}). "
            "Supported dumps are listed in README.md."
        )
    print(f"{e['label']}: VERSION={e['version']} REGION={e['region']}")
    if args.github_output:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"version={e['version']}\nregion={e['region']}\nlabel={e['label']}\n")


if __name__ == "__main__":
    main()
