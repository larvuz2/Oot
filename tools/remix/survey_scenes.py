#!/usr/bin/env python3
"""Survey the game's town scenes for buildings the Ancient Plateau can reuse (run after `make setup`).

For each scene (Kakariko Village, Market, Lon Lon Ranch, Kokiri Forest...) and each of its rooms, replays every
room-shape entry (the chunks a room is drawn in) and reports what it is: where, how big, how many triangles,
how much floor and wall, which textures. With --render, also draws a top-down map of each room with the entries
numbered, and a close-up of each entry (three.js in headless Chromium), then puts them on contact sheets.

Only pictures and numbers come out (the geometry used for drawing stays in a temporary folder), so the result
can be shared like screenshots.

    python3 tools/remix/survey_scenes.py --version ntsc-1.2 --out /tmp/survey --render
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from extracted_scene import Field, replay  # noqa: E402

SCENES = {
    "kakariko": "assets/scenes/overworld/spot01",
    "market": "assets/scenes/misc/market_day",
    "lon_lon": "assets/scenes/overworld/spot20",
    "kokiri": "assets/scenes/overworld/spot04",
    "castle": "assets/scenes/overworld/spot15",
    "graveyard": "assets/scenes/overworld/spot02",
    "zora_river": "assets/scenes/overworld/spot03",
    "lake": "assets/scenes/overworld/spot06",
    "gerudo_valley": "assets/scenes/overworld/spot09",
    "colossus": "assets/scenes/overworld/spot11",
    "fortress": "assets/scenes/overworld/spot12",
    "death_mountain": "assets/scenes/overworld/spot16",
    "sacred_meadow": "assets/scenes/overworld/spot05",
    "lost_woods": "assets/scenes/overworld/spot10",
    "zora_domain": "assets/scenes/overworld/spot07",
    "zora_fountain": "assets/scenes/overworld/spot08",
    "wasteland": "assets/scenes/overworld/spot13",
    "crater": "assets/scenes/overworld/spot17",
    "goron_city": "assets/scenes/overworld/spot18",
    "hyrule_field": "assets/scenes/overworld/spot00",
}
# The scenes a branch test build surveys (the first five were surveyed for the first town)
SURVEY_DEFAULT = "graveyard,zora_river,lake,gerudo_valley,colossus,fortress,death_mountain"


def collect(field: Field, dls):
    """Replay display lists into mesh groups keyed by (texture, lit, translucent)."""
    groups = {}
    stats = {}
    for dl in dls:
        if dl is None:
            continue

        def on_tri(v, st, dl=dl):
            key = (st["tex"], st["lit"], st["xlu"], st["size"])
            g = groups.setdefault(key, dict(pos=[], st=[], col=[]))
            g["pos"].append(v[:, :3])
            g["st"].append(v[:, 3:5])
            g["col"].append(v[:, 5:9])

        replay(field, dl, on_tri, stats)
    return groups, stats


def measure(groups):
    pos = [p for g in groups.values() for p in g["pos"]]
    if not pos:
        return None
    tris = np.array(pos)  # N x 3 x 3
    pts = tris.reshape(-1, 3)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    ny = np.divide(n[:, 1], 2 * area, out=np.zeros_like(area), where=area > 0)
    return dict(tris=len(tris), lo=pts.min(0).round().tolist(), hi=pts.max(0).round().tolist(),
                floor=float(area[ny > 0.75].sum()), wall=float(area[np.abs(ny) < 0.55].sum()),
                roof=float(area[(ny >= 0.55) & (ny <= 0.75)].sum()))


def texture_data(field: Field, sym):
    if sym is None or sym.startswith("seg:"):
        return None
    got = field.texture(sym)
    if got is None:
        return None
    fmt, img = got
    buf = io.BytesIO()
    img.save(buf, "PNG")
    a = np.array(img)
    return dict(fmt=fmt, w=img.size[0], h=img.size[1], mean=[int(x) for x in a[..., :3].reshape(-1, 3).mean(0)],
                url="data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())


def survey_scene(name: str, ext: Path, rel: str, work: Path, report: list):
    src = ext / rel
    if not src.is_dir():
        report.append(f"## {name}: {rel} not found\n")
        return []
    field = Field(ext, src)
    rooms = field.rooms()
    report.append(f"## {name} ({rel}): {len(rooms)} rooms\n")
    jobs = []
    for room in rooms:
        entries = field.room_entries(room)
        report.append(f"### {room}: {len(entries)} entries\n")
        if not entries:
            report.append(f"(shape: {field.room_shape_sample(room)})\n")
        report.append("| # | center | radius | tris | box min | box max | floor | wall | roof | textures | segments |")
        report.append("|---|---|---|---|---|---|---|---|---|---|---|")
        data = dict(scene=name, room=room, entries=[], textures={})
        for i, e in enumerate(entries):
            groups, stats = collect(field, [e["opa"], e["xlu"]])
            m = measure(groups)
            texs = sorted({k[0] for k in groups if k[0]})
            for t in texs:
                if t not in data["textures"]:
                    data["textures"][t] = texture_data(field, t)
            segs = sorted(stats.get("segment textures", set()) | stats.get("segment calls", set()))
            if m:
                report.append(f"| {i} | {e['center']} | {e['radius']} | {m['tris']} | {m['lo']} | {m['hi']} | "
                              f"{m['floor'] / 1e3:.0f}k | {m['wall'] / 1e3:.0f}k | {m['roof'] / 1e3:.0f}k | "
                              f"{len(texs)}: " + ", ".join(
                                  f"{t}"
                                  f"({(data['textures'].get(t) or {}).get('fmt', '?')} "
                                  f"{(data['textures'].get(t) or {}).get('w', '?')}x{(data['textures'].get(t) or {}).get('h', '?')})"
                                  for t in texs[:8]) + f" | {' '.join(segs)} |")
            else:
                report.append(f"| {i} | {e['center']} | {e['radius']} | 0 | | | | | | | {' '.join(segs)} |")
            data["entries"].append(dict(
                index=i, center=e["center"], radius=e["radius"], measure=m,
                groups=[dict(tex=k[0], lit=k[1], xlu=k[2], pos=np.concatenate(g["pos"]).reshape(-1).round(1).tolist(),
                             st=np.concatenate(g["st"]).reshape(-1).tolist(),
                             col=np.concatenate(g["col"]).reshape(-1).astype(int).tolist()) for k, g in groups.items()]))
            if stats.get("samples"):
                report.append(f"<!-- entry {i} unread: {stats['samples'][:2]} -->")
        report.append("")
        f = work / f"{name}-{room}.json"
        f.write_text(json.dumps(data))
        jobs.append((f.name, len(entries), [en["measure"] for en in data["entries"]]))
    return jobs


def ground_textures(ext: Path, names, out: Path, per_scene=5):
    """A sheet of the textures each scene covers the most floor with (tiled, tinted the way the scene draws them),
    to choose ground textures from."""
    tiles, labels = [], []
    work = Path(tempfile.mkdtemp(prefix="ground-"))
    for name in names:
        src = ext / SCENES.get(name, name)
        if not src.is_dir():
            continue
        field = Field(ext, src)
        area = {}
        for room in field.rooms():
            for e in field.room_entries(room):
                for dl in (e["opa"], e["xlu"]):
                    if dl is None:
                        continue

                    def on_tri(v, st):
                        if not st["tex"] or st["tex"].startswith("seg:"):
                            return
                        p = v[:, :3]
                        n = np.cross(p[1] - p[0], p[2] - p[0])
                        a = np.linalg.norm(n) / 2
                        if a < 1 or n[1] / (2 * a) < 0.75:
                            return
                        rec = area.setdefault(st["tex"], [0.0, np.zeros(3), 0.0])
                        rec[0] += a
                        if not st["lit"]:
                            rec[1] += v[:, 5:8].mean(0) * a
                            rec[2] += a

                    replay(field, dl, on_tri, {})
        ranked = sorted(area.items(), key=lambda kv: -kv[1][0])
        print(f"ground: {name}: {len(field.rooms())} rooms, {len(ranked)} floor textures: "
              + ", ".join(f"{s} {a / 1e3:.0f}k" for s, (a, _, _) in ranked[:per_scene]))
        rank = 0
        for sym, (a, col, w) in ranked:
            got = field.texture(sym)
            if got is None:
                continue
            fmt, img = got
            arr = np.array(img).astype(float)
            if fmt.startswith(("i4", "i8", "ia")) and w > 0:
                arr[..., :3] *= (col / w / 255.0)
            tile = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGB")
            big = Image.new("RGB", (tile.size[0] * 4, tile.size[1] * 4))
            for i in range(4):
                for j in range(4):
                    big.paste(tile, (i * tile.size[0], j * tile.size[1]))
            f = work / f"{name}-{rank}.png"
            big.resize((360, 270), Image.NEAREST).save(f)
            tiles.append(f)
            labels.append(f"{name} #{rank} {sym}\n{fmt} {img.size[0]}x{img.size[1]} floor {a / 1e3:.0f}k")
            rank += 1
            if rank >= per_scene:
                break
    if tiles:
        for page in range(0, len(tiles), 40):
            contact_sheet(tiles[page:page + 40], labels[page:page + 40], out / f"ground-textures-{page // 40 + 1}.png")
    shutil.rmtree(work, ignore_errors=True)


def contact_sheet(shots, labels, out: Path, cols=5, tile=(360, 270)):
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile[0], rows * (tile[1] + 34)), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for k, (shot, label) in enumerate(zip(shots, labels)):
        x, y = (k % cols) * tile[0], (k // cols) * (tile[1] + 34)
        if shot.exists():
            sheet.paste(Image.open(shot).convert("RGB").resize(tile), (x, y + 34))
        for j, line in enumerate(label.split("\n")[:2]):
            d.text((x + 6, y + 3 + j * 15), line, fill=(235, 235, 235))
    sheet.save(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="ntsc-1.2")
    ap.add_argument("--extracted", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--scenes", default=SURVEY_DEFAULT, help="comma-separated: " + ", ".join(SCENES))
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--ground", help="comma-separated scenes: a sheet of their main floor textures, nothing else")
    args = ap.parse_args()
    ext = args.extracted or HERE.parents[1] / "extracted" / args.version
    args.out.mkdir(parents=True, exist_ok=True)
    if args.ground:
        ground_textures(ext, args.ground.split(","), args.out)
        print(f"survey: wrote {args.out}")
        return
    work = Path(tempfile.mkdtemp(prefix="survey-"))
    report = ["# Town scenes survey\n", "Sizes in world units (Link is about 50 tall). Areas in thousands of square "
              "units. Floor: faces up; wall: vertical; roof: in between.\n"]
    all_jobs = []
    for name in args.scenes.split(","):
        all_jobs += survey_scene(name, ext, SCENES.get(name, name), work, report)
    (args.out / "survey.md").write_text("\n".join(report))
    print("\n".join(report))

    if args.render and all_jobs:
        shutil.copy(HERE / "survey_view.html", work / "index.html")
        shots_dir = work / "shots"
        shots_dir.mkdir()
        plan = []
        for fname, n, measures in all_jobs:
            plan.append(dict(file=fname, entry="all", mode="top", out=f"{fname[:-5]}-map.png"))
            plan.append(dict(file=fname, entry="all", mode="iso", out=f"{fname[:-5]}-overview.png"))
            for i in range(n):
                if measures[i]:
                    plan.append(dict(file=fname, entry=i, mode="iso", out=f"{fname[:-5]}-e{i:02d}.png"))
        (work / "plan.json").write_text(json.dumps(plan))
        p = subprocess.run(["node", str(HERE / "survey_render.mjs"), str(work), str(shots_dir)], capture_output=True,
                           text=True, timeout=3600)
        print(p.stdout[-3000:], p.stderr[-3000:])
        for fname, n, measures in all_jobs:
            stem = fname[:-5]
            for kind in ("map", "overview"):
                if (shots_dir / f"{stem}-{kind}.png").exists():
                    shutil.copy(shots_dir / f"{stem}-{kind}.png", args.out / f"{stem}-{kind}.png")
            idx = [i for i in range(n) if measures[i]]
            labels = []
            for i in idx:
                m = measures[i]
                size = np.subtract(m["hi"], m["lo"]).astype(int).tolist()
                labels.append(f"#{i}  {m['tris']} tris  size {size[0]}x{size[1]}x{size[2]}\n"
                              f"floor {m['floor'] / 1e3:.0f}k wall {m['wall'] / 1e3:.0f}k roof {m['roof'] / 1e3:.0f}k")
            for page in range(0, len(idx), 30):
                contact_sheet([shots_dir / f"{stem}-e{i:02d}.png" for i in idx[page : page + 30]],
                              labels[page : page + 30], args.out / f"{stem}-entries-{page // 30 + 1}.png")
    shutil.rmtree(work, ignore_errors=True)
    print(f"survey: wrote {args.out}")


if __name__ == "__main__":
    main()
