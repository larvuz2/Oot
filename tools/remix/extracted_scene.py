"""Read scenes as the asset extractor writes them (extracted/VERSION/assets/scenes/...), for the remix tools.

Every resource is written as `TYPE SYMBOL[...] = {\\n#include "assets/.../file.inc.c"\\n};` (file names do not
always match symbols), display lists as gfxd macros (sometimes over several lines), vertices as VTX(...).
This module resolves symbols, replays display lists into triangles (with the texture and render state each one
is drawn with), and lists a room's shape entries. Used by link_level_assets.py, survey_scenes.py and
make_town.py. Nothing here writes ROM data anywhere.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]

DEF_RE = re.compile(r'^(?:static\s+)?([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*(?:\[[^\]\n]*\]\s*)*=\s*\{?\s*\n\s*#include\s+"([^"]+)"',
                    re.M)
VTX_FULL_RE = re.compile(r"VTX\(\s*(-?\w+),\s*(-?\w+),\s*(-?\w+),\s*(-?\w+),\s*(-?\w+),\s*(\w+),\s*(\w+),\s*(\w+),\s*(\w+)\s*\)")
GEO_RE = re.compile(r"gsSP(Set|Clear|Load)GeometryMode\(([^)]*)\)")
GEO2_RE = re.compile(r"gsSPGeometryMode\(([^,]*),([^)]*)\)")
SETTIMG_RE = re.compile(r"gsDPSetTextureImage\(\s*(\w+),\s*(\w+),\s*[^,]+,\s*([^)]+)\)")
TLUT_RE = re.compile(r"gsDPLoadTLUT(?:_pal16|_pal256)?\(\s*(?:[^,]+,\s*)?([^,)]+)\)")
VERTEX_RE = re.compile(r"gsSPVertex\((.*)\)")
TRI1_RE = re.compile(r"gsSP1Triangle\(\s*(\d+),\s*(\d+),\s*(\d+)")
TRI2_RE = re.compile(r"gsSP2Triangles\(\s*(\d+),\s*(\d+),\s*(\d+),\s*\d+,\s*(\d+),\s*(\d+),\s*(\d+)")
QUAD_RE = re.compile(r"gsSP1Quadrangle\(\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)")
CALL_RE = re.compile(r"gsSP(DisplayList|BranchList)\(\s*&?([^)]+?)\s*\)")
PRIM_RE = re.compile(r"gsDPSetPrimColor\(\s*[^,]+,\s*[^,]+,\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,)]+)")
ENV_RE = re.compile(r"gsDPSetEnvColor\(\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,)]+)")
MACRO_RE = re.compile(r"\b(gs[A-Z]\w*)\(")
# One display list command, wherever the extractor broke its lines (arguments may nest parentheses twice).
COMMAND_RE = re.compile(r"\b(gs[A-Z]\w*)\(((?:[^()]|\((?:[^()]|\([^()]*\))*\))*)\)")
SEGADDR_RE = re.compile(r"^\(?\s*(?:\(\w+\)\s*)?0x0?([0-9A-Fa-f])([0-9A-Fa-f]{6})\s*\)?$")


def num(s):
    return int(s, 0)


def expr(s: str) -> int:
    """Value of a small integer expression from the extracted sources (`12`, `0x1E`, `3 * 32`...)."""
    s = s.strip()
    if not re.fullmatch(r"[0-9a-fA-FxX+\-*/() ]+", s):
        raise ValueError(s)
    return int(eval(re.sub(r"\b0[xX][0-9a-fA-F]+\b", lambda m: str(int(m.group(0), 16)), s).replace("/", "//")))


def parse_vertex(args: str):
    """`&sym[index], count, v0` (or `sym`, `sym + index`) -> (sym, index, count, v0), or None."""
    parts = [p.strip() for p in args.split(",")]
    if len(parts) != 3:
        return None
    m = re.fullmatch(r"&?\s*\(?\s*(\w+)\s*(?:\[([^\]]+)\])?\s*(?:\+\s*([^)]+))?\)?", parts[0])
    try:
        return m.group(1), expr(m.group(2) or m.group(3) or "0"), expr(parts[1]), expr(parts[2])
    except (AttributeError, ValueError, SyntaxError):
        return None


def commands(text: str):
    """The display list's commands, one per item, each on one line."""
    return [f"{m.group(1)}({' '.join(m.group(2).split())})" for m in COMMAND_RE.finditer(text)]


def split_args(args: str):
    """Top-level comma-separated arguments of a command."""
    out, depth, cur = [], 0, ""
    for ch in args:
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def segment_address(arg: str):
    """(segment, offset) when a command argument is a raw segmented address like 0x08000000, else None."""
    m = SEGADDR_RE.match(arg.strip())
    if m:
        return int(m.group(1), 16), int(m.group(2), 16)
    return None


def lighting_after(line, lit):
    m = GEO_RE.search(line)
    if m:
        has = "G_LIGHTING" in m.group(2)
        return {"Set": lit or has, "Clear": lit and not has, "Load": has}[m.group(1)]
    m = GEO2_RE.search(line)
    if m:
        return (lit and "G_LIGHTING" not in m.group(1)) or "G_LIGHTING" in m.group(2)
    return lit


class Field:
    """An extracted scene folder (scene and rooms): symbol -> (C type, included file), and the included files."""

    def __init__(self, ext: Path, src: Path):
        self.ext, self.src = ext, src
        self.defs = {}
        self.owner = {}  # symbol -> stem of the .c file defining it (e.g. spot01_room_0)
        for c in sorted(src.glob("*.c")):
            if c.name.endswith(".inc.c"):
                continue
            for ctype, sym, inc in DEF_RE.findall(c.read_text()):
                self.defs[sym] = (ctype, inc)
                self.owner[sym] = c.stem
        self._texts = {}
        self._vtx = {}

    def path(self, inc: str) -> Path:
        for base in (self.ext, self.src, REPO):
            if (base / inc).is_file():
                return base / inc
        return self.ext / inc

    def text(self, sym: str) -> str:
        if sym not in self._texts:
            p = self.path(self.defs[sym][1]) if sym in self.defs else None
            self._texts[sym] = p.read_text() if p is not None and p.is_file() else ""
        return self._texts[sym]

    def of_type(self, ctype: str):
        return [s for s, (t, _) in self.defs.items() if t == ctype]

    def png(self, sym: str):
        """The PNG a texture symbol is built from, or None."""
        if sym not in self.defs or not self.defs[sym][1].endswith(".inc.c"):
            return None
        p = self.path(self.defs[sym][1][: -len(".inc.c")] + ".png")
        return p if p.is_file() else None

    def texture(self, sym: str):
        """(format, RGBA image) of a texture symbol (CI textures come with their palette), or None."""
        p = self.png(sym)
        if p is None:
            return None
        return p.name.split(".")[1], Image.open(p).convert("RGBA")

    def vertices(self, sym: str):
        """Nx9 array (x, y, z, s, t, r, g, b, a) of a Vtx array, or None."""
        if sym not in self._vtx:
            rows = [[num(v) for v in m] for m in VTX_FULL_RE.findall(self.text(sym))]
            self._vtx[sym] = np.array(rows, float).reshape(-1, 9) if rows else None
        return self._vtx[sym]

    def rooms(self):
        """Stems of the room files, in order."""
        return sorted({o for o in self.owner.values() if re.search(r"_room_\d+$", o)},
                      key=lambda s: int(s.rsplit("_", 1)[1]))

    def room_entries(self, room: str):
        """The room's shape entries: dicts with center (or None), radius, opa and xlu display list symbols."""
        out = []
        for sym, (ctype, _) in self.defs.items():
            if self.owner.get(sym) != room:
                continue
            if ctype == "RoomShapeCullableEntry":
                for m in re.finditer(r"\{\s*\{\s*(-?\w+),\s*(-?\w+),\s*(-?\w+)\s*\},\s*(-?\w+),\s*&?(\w+),\s*&?(\w+)\s*\}",
                                     self.text(sym)):
                    out.append(dict(center=(num(m.group(1)), num(m.group(2)), num(m.group(3))), radius=num(m.group(4)),
                                    opa=None if m.group(5) == "NULL" else m.group(5),
                                    xlu=None if m.group(6) == "NULL" else m.group(6)))
            elif ctype == "RoomShapeDListsEntry":
                for m in re.finditer(r"\{\s*&?(\w+),\s*&?(\w+)\s*\}", self.text(sym)):
                    out.append(dict(center=None, radius=None, opa=None if m.group(1) == "NULL" else m.group(1),
                                    xlu=None if m.group(2) == "NULL" else m.group(2)))
        return out


class State:
    """RSP/RDP state while replaying: texture (tile 0), its format and size, TLUT, lighting, colors, blending."""

    def __init__(self):
        self.tex = None
        self.tex_fmt = None
        self.tex_size = None
        self.tlut = None
        self.lit = False
        self.prim = None
        self.env = None
        self.xlu = False
        self.slots = [None] * 64

    def snapshot(self):
        return dict(tex=self.tex, fmt=self.tex_fmt, size=self.tex_size, tlut=self.tlut, lit=self.lit,
                    prim=None if self.prim is None else tuple(self.prim), env=None if self.env is None else tuple(self.env),
                    xlu=self.xlu)


def replay(field: Field, dl: str, on_triangle, stats=None, state=None, depth=0):
    """Walk a display list (following calls into other lists of the scene), calling on_triangle(verts, state)
    for each triangle: verts is a 3x9 array (x, y, z, s, t, r, g, b, a) and state a State.snapshot() dict.
    stats (a dict) collects counters, the commands seen and raw segment references."""
    stats = stats if stats is not None else {}
    st = state or State()

    def count(key, n=1):
        stats[key] = stats.get(key, 0) + n

    if depth > 16:
        return st
    for line in commands(field.text(dl)):
        mac = MACRO_RE.match(line)
        if mac:
            stats.setdefault("macros", {})[mac.group(1)] = stats.setdefault("macros", {}).get(mac.group(1), 0) + 1
        st.lit = lighting_after(line, st.lit)
        if "XLU" in line and ("RenderMode" in line or "OtherMode" in line):
            st.xlu = True
        elif "OPA" in line and ("RenderMode" in line or "OtherMode" in line):
            st.xlu = False
        m = CALL_RE.match(line)
        if m:
            target = m.group(2).strip()
            if target in field.defs:
                replay(field, target, on_triangle, stats, st, depth + 1)
            else:
                seg = segment_address(target)
                if seg:
                    stats.setdefault("segment calls", set()).add(f"0x{seg[0]:02X}{seg[1]:06X}")
                count("calls to unknown lists")
            if m.group(1) == "BranchList":
                return st
            continue
        m = PRIM_RE.match(line)
        if m:
            try:
                st.prim = tuple(expr(m.group(i)) for i in (1, 2, 3, 4))
            except (ValueError, SyntaxError):
                pass
            continue
        m = ENV_RE.match(line)
        if m:
            try:
                st.env = tuple(expr(m.group(i)) for i in (1, 2, 3, 4))
            except (ValueError, SyntaxError):
                pass
            continue
        m = TLUT_RE.match(line)
        if m and "TLUT" in line:
            st.tlut = m.group(1).strip()
            continue
        if line.startswith(("gsDPLoadTextureBlock", "gsDPLoadMultiBlock")):
            name, a = line[: line.index("(")], split_args(line[line.index("(") + 1 : -1])
            four = name.endswith("_4b")
            if name.startswith("gsDPLoadMultiBlock"):
                if a[2] not in ("G_TX_RENDERTILE", "0"):
                    continue  # second texture of a two-texture material
                a = [a[0]] + a[3:]
            if four:
                _set_texture(st, stats, a[0], a[1], a[2], a[3], "G_IM_SIZ_4b")
            else:
                _set_texture(st, stats, a[0], a[1], a[3], a[4], a[2])
            continue
        m = SETTIMG_RE.match(line)
        if m and "TLUT" not in m.group(3):
            st.tex = m.group(3).strip()
            count("texture loads")
            continue
        m = VERTEX_RE.match(line)
        if m:
            v = parse_vertex(m.group(1))
            arr = field.vertices(v[0]) if v else None
            if v is None or arr is None:
                count("vertex loads not understood")
                if v and segment_address(v[0]) is None and len(stats.setdefault("samples", [])) < 6:
                    stats["samples"].append(line[:120])
                st.slots = [None] * 64
                continue
            count("vertex loads")
            _, start, n, v0 = v
            for k in range(n):
                if v0 + k < len(st.slots):
                    st.slots[v0 + k] = arr[start + k] if start + k < len(arr) else None
            continue
        tris = []
        m = TRI2_RE.match(line)
        if m:
            g = [int(x) for x in m.groups()]
            tris = [g[:3], g[3:]]
        elif (m := QUAD_RE.match(line)) is not None:
            q = [int(x) for x in m.groups()]
            tris = [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
        elif (m := TRI1_RE.match(line)) is not None:
            tris = [[int(x) for x in m.groups()]]
        for t in tris:
            count("triangles")
            if any(i >= len(st.slots) or st.slots[i] is None for i in t):
                count("triangles with unknown vertices")
                continue
            on_triangle(np.array([st.slots[i] for i in t]), st.snapshot())
    return st


def _set_texture(st, stats, img, fmt, w, h, siz):
    seg = segment_address(img)
    if seg:
        stats.setdefault("segment textures", set()).add(f"0x{seg[0]:02X}{seg[1]:06X}")
        st.tex = f"seg:0x{seg[0]:02X}{seg[1]:06X}"
    else:
        st.tex = img
    st.tex_fmt = f"{fmt}/{siz}"
    try:
        st.tex_size = (expr(w), expr(h))
    except (ValueError, SyntaxError, TypeError):
        st.tex_size = None
    stats["texture loads"] = stats.get("texture loads", 0) + 1


def references(field: Field, sym: str, seen=None):
    """Every symbol of the scene a resource uses, directly or not (display lists, vertices, textures, TLUTs)."""
    seen = seen if seen is not None else set()
    if sym in seen or sym not in field.defs:
        return seen
    seen.add(sym)
    if field.defs[sym][0] == "Gfx":
        for name in set(re.findall(r"\b[A-Za-z_]\w*\b", field.text(sym))):
            if name in field.defs:
                references(field, name, seen)
    return seen
