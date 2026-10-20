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
            if self.owner.get(sym) != room or ctype not in ("RoomShapeCullableEntry", "RoomShapeDListsEntry"):
                continue
            for item in brace_items(uncomment(self.text(sym))):
                inner = brace_items(item)
                if ctype == "RoomShapeCullableEntry" and inner:
                    try:
                        center = tuple(expr(v) for v in split_args(inner[0])[:3])
                    except (ValueError, SyntaxError):
                        continue
                    rest = split_args(item[item.rindex("}") + 1 :].strip().lstrip(","))
                    if len(rest) < 3:
                        continue
                    try:
                        radius = expr(rest[0])
                    except (ValueError, SyntaxError):
                        radius = None
                    dls = rest[1:3]
                else:
                    center, radius, dls = None, None, split_args(item)[:2]
                dls = [d.strip().lstrip("&").strip() for d in dls] + [None, None]
                out.append(dict(center=center, radius=radius,
                                opa=None if dls[0] in (None, "NULL", "0") else dls[0],
                                xlu=None if dls[1] in (None, "NULL", "0") else dls[1]))
        return out

    def room_shape_sample(self, room: str):
        """Start of the room's shape entries file, to fix the parser if a format is not understood."""
        for sym, (ctype, _) in self.defs.items():
            if self.owner.get(sym) == room and ctype.startswith("RoomShape"):
                return f"{ctype} {sym}: " + " ".join(self.text(sym).split())[:300]
        types = sorted({t for s, (t, _) in self.defs.items() if self.owner.get(s) == room})
        return f"no RoomShape definition; types in {room}: {types}"


class State:
    """RSP/RDP state while replaying: texture (tile 0), its format and size, TLUT, lighting, colors, blending."""

    def __init__(self):
        self.tex = None
        self.tex_fmt = None
        self.tex_size = None
        self.tex_tile = None  # (cms, cmt, masks, maskt, shifts, shiftt) of the render tile
        self.tex_scale = (0xFFFF, 0xFFFF)
        self.tlut = None
        self.lit = False
        self.prim = None
        self.env = None
        self.xlu = False
        self.slots = [None] * 64

    def snapshot(self):
        return dict(tex=self.tex, fmt=self.tex_fmt, size=self.tex_size, tile=self.tex_tile, scale=self.tex_scale,
                    tlut=self.tlut, lit=self.lit,
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
                st.tex_tile = tuple(a[5:11]) if len(a) >= 11 else None
            else:
                _set_texture(st, stats, a[0], a[1], a[3], a[4], a[2])
                st.tex_tile = tuple(a[6:12]) if len(a) >= 12 else None
            continue
        if line.startswith("gsSPTexture("):
            a = split_args(line[len("gsSPTexture(") : -1])
            try:
                st.tex_scale = (expr(a[0]), expr(a[1]))
            except (ValueError, SyntaxError, IndexError):
                pass
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


def uncomment(text: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


def macro_calls(text: str, name: str):
    """The argument text of each call of a macro, with nested parentheses."""
    out = []
    for m in re.finditer(r"\b" + name + r"\(", text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        out.append(text[m.end() : i - 1])
    return out


def brace_items(text: str):
    """Contents of each top-level {...} group in text (an array's elements, a struct's fields)."""
    out, depth, start = [], 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                out.append(text[start:i])
    return out


def collision(field: Field):
    """The scene's collision: (vertices Nx3, polys [(type, (i0, i1, i2), flags_text)], surface types
    [(args of SURFACETYPE0, args of SURFACETYPE1)]), or None. Normals and distances are left out: they are
    recomputed after moving the polygons."""
    hdrs = field.of_type("CollisionHeader")
    if not hdrs:
        return None
    # the arrays the (first) collision header points at
    names = re.findall(r"\b[A-Za-z_]\w*\b", field.text(hdrs[0]))
    pick = lambda t: next((n for n in names if field.defs.get(n, ("",))[0] == t), None) or next(iter(field.of_type(t)), None)
    vsym, psym, ssym = pick("Vec3s"), pick("CollisionPoly"), pick("SurfaceType")
    if not (vsym and psym and ssym):
        return None
    verts = np.array([[num(a), num(b), num(c)] for a, b, c in
                      re.findall(r"\{\s*(-?\w+),\s*(-?\w+),\s*(-?\w+)\s*,?\s*\}", uncomment(field.text(vsym)))], float)
    polys = []
    for item in brace_items(uncomment(field.text(psym))):
        parts = brace_items(item)  # { vertex ids }, { normal }
        head = item.split("{", 1)[0]
        tm = re.match(r"\s*(\w+)", head)
        if not parts or tm is None:
            continue
        vs, flags = [], []
        for arg in split_args(parts[0]):
            mm = re.match(r"COLPOLY_VTX\(\s*(\w+)\s*,\s*(.*)\)$", arg)
            if mm:
                vs.append(num(mm.group(1)))
                flags.append(mm.group(2).strip())
            elif re.fullmatch(r"\w+", arg):
                vs.append(num(arg))
        if len(vs) >= 3:
            polys.append((num(tm.group(1)), tuple(vs[:3]), flags[0] if flags else "0"))
    s0 = [" ".join(x.split()) for x in macro_calls(uncomment(field.text(ssym)), "SURFACETYPE0")]
    s1 = [" ".join(x.split()) for x in macro_calls(uncomment(field.text(ssym)), "SURFACETYPE1")]
    surfaces = [(split_args(a), split_args(b)) for a, b in zip(s0, s1)]
    return verts, polys, surfaces
