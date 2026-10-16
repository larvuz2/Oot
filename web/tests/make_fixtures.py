#!/usr/bin/env python3
"""Build synthetic test fixtures for the web player's ROM pipeline.

Produces fake ROMs (random data, real dmadata layout, Yaz0/zlib-compressed
files) and runs the decomp's own tools/decompress_baserom.py logic on them, so
web/tests/run.mjs can check the JavaScript port is byte-identical. No game data
is involved. Requires: crunch64, ipl3checksum, pyyaml, and `flips` on PATH.

    python3 web/tests/make_fixtures.py OUT_DIR
"""

from __future__ import annotations

import json
import os
import random
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import crunch64  # noqa: E402
import ipl3checksum  # noqa: E402
from decompress_baserom import decompress_rom  # noqa: E402
import dmadata  # noqa: E402


def compressible(rng: random.Random, n: int) -> bytes:
    # Mix of runs and noise so the compressor emits literals, short and long copies.
    out = bytearray()
    while len(out) < n:
        kind = rng.random()
        if kind < 0.3:
            out += bytes([rng.randrange(256)]) * rng.randrange(1, 400)
        elif kind < 0.6 and len(out) > 16:
            start = rng.randrange(max(1, len(out) - 4000), len(out))
            ln = rng.randrange(3, 300)
            for i in range(ln):
                out.append(out[start + i] if start + i < len(out) else 0)
        else:
            out += rng.randbytes(rng.randrange(1, 64))
    return bytes(out[:n])


def make_rom(rng: random.Random, ique: bool, dmadata_start: int):
    files = []  # (data, compressed?, syms?)
    files.append((rng.randbytes(dmadata_start), False, False))  # "makerom"/boot area
    files.append((None, False, False))  # dmadata placeholder
    for i in range(12):
        size = rng.randrange(1, 40) * 0x10 * rng.randrange(1, 64)
        files.append((compressible(rng, size), rng.random() < 0.7, False))
    files.append((compressible(rng, 0x80000), True, False))  # push the ROM past the 1 MiB checksum window
    files.append((rng.randbytes(0x90000), False, False))
    files.append((bytes(0x2000), False, True))
    files.append((compressible(rng, 0x1230), True, False))
    n_entries = len(files) + 1  # + terminator
    dma_size = n_entries * 16
    files[1] = (bytes((dma_size + 15) // 16 * 16), False, False)

    vrom = 0
    prom = 0
    entries = []
    phys = bytearray()
    for data, comp, syms in files:
        vs, ve = vrom, vrom + len(data)
        vrom = (ve + 15) // 16 * 16
        if syms:
            entries.append(dmadata.DmaEntry(vs, ve, 0xFFFFFFFF, 0xFFFFFFFF))
            continue
        if comp:
            if ique:
                c = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
                blob = c.compress(data) + c.flush()
            else:
                blob = crunch64.yaz0.compress(data)
            blob += bytes((-len(blob)) % 16)
            entries.append(dmadata.DmaEntry(vs, ve, prom, prom + len(blob)))
        else:
            blob = data + bytes((-len(data)) % 16)
            entries.append(dmadata.DmaEntry(vs, ve, prom, 0))
        phys[prom:] = blob
        prom += len(blob)
    phys += bytes((-len(phys)) % 0x1000)
    for i, e in enumerate(entries):
        buf = bytearray(16)
        e.to_bin(buf)
        phys[dmadata_start + i * 16 : dmadata_start + i * 16 + 16] = buf
    phys[0:4] = b"\x80\x37\x12\x40"
    return bytearray(phys), entries


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1234)
    manifest = {"roms": [], "yaz0": [], "checksum": [], "bps": []}

    for ique in (False, True):
        dmadata_start = 0x1060
        rom, entries = make_rom(rng, ique, dmadata_start)
        expected = decompress_rom(bytearray(rom), dmadata_start, entries, ique)
        name = "rom-ique" if ique else "rom-yaz0"
        (out / f"{name}.z64").write_bytes(rom)
        (out / f"{name}.expected.z64").write_bytes(expected)
        manifest["roms"].append({"name": name, "dmadataStart": dmadata_start, "ique": ique})

    for i in range(4):
        data = compressible(rng, rng.randrange(1, 300000))
        (out / f"yaz0-{i}.bin").write_bytes(data)
        (out / f"yaz0-{i}.yaz0").write_bytes(crunch64.yaz0.compress(data))
        manifest["yaz0"].append(f"yaz0-{i}")

    for cic, kind in ((6105, ipl3checksum.CICKind.CIC_X105), (6102, ipl3checksum.CICKind.CIC_6102_7101)):
        data = rng.randbytes(0x101000)
        c0, c1 = kind.calculateChecksum(data)
        (out / f"cic-{cic}.bin").write_bytes(data)
        manifest["checksum"].append({"file": f"cic-{cic}.bin", "cic": cic, "expected": [c0, c1]})

    # BPS: a "modded" target with edits, an insertion (shift) and a size change.
    src = bytearray(compressible(rng, 3_000_000))
    tgt = bytearray(src)
    for _ in range(50):
        p = rng.randrange(len(tgt) - 100)
        tgt[p : p + 20] = rng.randbytes(20)
    ins = rng.randrange(len(tgt))
    tgt[ins:ins] = rng.randbytes(777)
    tgt += rng.randbytes(4096)
    (out / "bps-src.bin").write_bytes(src)
    (out / "bps-tgt.bin").write_bytes(tgt)
    for mode in ("--bps-delta", "--bps-linear"):
        patch = out / f"bps{mode[5:]}.bps"
        subprocess.run(
            [os.environ.get("FLIPS", "flips"), "--create", "--exact", mode, out / "bps-src.bin", out / "bps-tgt.bin", patch],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        manifest["bps"].append(patch.name)

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Fixtures written to {out}")


if __name__ == "__main__":
    main()
