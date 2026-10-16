#!/usr/bin/env python3
"""Publish a remix build to the web player as a BPS patch.

Diffs the decomp's baserom-decompressed.z64 against the freshly built ROM, writes
web/patches/oot-<version>-<region>.bps and records it in web/patches/manifest.json.
Only the delta is published; players supply their own ROM.

    python3 tools/web/make_patch.py --version ntsc-1.0 --region US \\
        --target build/ntsc-1.0/oot-ntsc-1.0.z64 [--flips path/to/flips] [--title "My Remix"]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_versions import collect  # noqa: E402


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--source", type=Path, help="default: baseroms/<version>/baserom-decompressed.z64")
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--flips", default="flips")
    ap.add_argument("--title", default="Remix")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "web" / "patches")
    args = ap.parse_args()

    source = args.source or ROOT / "baseroms" / args.version / "baserom-decompressed.z64"
    entry = next((e for e in collect() if e["version"] == args.version and e["region"] == args.region), None)
    if entry is None:
        raise SystemExit(f"error: unknown version/region {args.version}/{args.region}")
    source_md5 = md5(source)
    if source_md5 != entry["decompressedMd5"]:
        raise SystemExit(f"error: {source} has md5 {source_md5}, expected {entry['decompressedMd5']}")
    target_md5 = md5(args.target)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    name = f"oot-{args.version}-{args.region}.bps"
    patch = args.out_dir / name
    subprocess.run([args.flips, "--create", "--exact", "--bps-delta", source, args.target, patch], check=True)

    # Round-trip check: applying the patch must reproduce the built ROM exactly.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "roundtrip.z64"
        subprocess.run([args.flips, "--apply", "--exact", patch, source, out], check=True, stdout=subprocess.DEVNULL)
        if md5(out) != target_md5:
            raise SystemExit("error: patch round-trip produced a different ROM")

    manifest_path = args.out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"patches": []}
    patches = [p for p in manifest.get("patches", []) if p.get("sourceMd5") != source_md5]
    patches.append(
        {
            "title": args.title,
            "version": args.version,
            "region": args.region,
            "label": entry["label"],
            "file": name,
            "size": patch.stat().st_size,
            "sourceMd5": source_md5,
            "targetMd5": target_md5,
            "commit": git_commit(),
            "builtAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        }
    )
    manifest["patches"] = sorted(patches, key=lambda p: p["file"])
    manifest_path.write_text(json.dumps(manifest, indent=4) + "\n")
    print(f"Wrote {patch.relative_to(ROOT) if patch.is_relative_to(ROOT) else patch} ({patch.stat().st_size} bytes), target md5 {target_md5}")


if __name__ == "__main__":
    main()
