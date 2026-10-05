"""Minimal FDT (device tree blob) support, stdlib only."""

import struct
from typing import Any

from .errors import FixError

# A device tree node: {"name": str, "props": [(name, bytes)], ...}.
FdtNode = dict[str, Any]


def _pad4(n: int) -> int:
    return (n + 3) & ~3


def fdt_parse(blob: bytes) -> FdtNode:
    """Parse an FDT blob into nested dicts.

    Node: {"name": str, "props": [(name, bytes)], "children": [...]}.
    """
    magic, _total, off_struct, off_strings = struct.unpack(">4I", blob[:16])
    if magic != 0xD00DFEED:
        raise FixError("not a device tree blob (bad magic %08x)" % magic)
    strs = blob[off_strings:]
    pos = [off_struct]

    def cstr(at: int) -> str:
        end = blob.index(b"\x00", at)
        return blob[at:end].decode()

    def pname(off: int) -> str:
        end = strs.index(b"\x00", off)
        return strs[off:end].decode()

    def node() -> FdtNode:
        tok = struct.unpack(">I", blob[pos[0]:pos[0] + 4])[0]
        if tok != 1:
            raise FixError("FDT parse error at offset %x" % pos[0])
        name = cstr(pos[0] + 4)
        pos[0] = _pad4(pos[0] + 4 + len(name) + 1)
        props: list[tuple[str, bytes]] = []
        children: list[FdtNode] = []
        while True:
            tok = struct.unpack(">I", blob[pos[0]:pos[0] + 4])[0]
            if tok in (2, 9):
                pos[0] += 4
                break
            if tok == 1:
                children.append(node())
                continue
            if tok != 3:
                raise FixError("FDT parse error at offset %x" % pos[0])
            ln, noff = struct.unpack(">2I", blob[pos[0] + 4:pos[0] + 12])
            props.append((pname(noff), bytes(blob[pos[0] + 12:pos[0] + 12 + ln])))
            pos[0] = _pad4(pos[0] + 12 + ln)
        return {"name": name, "props": props, "children": children}

    return node()


def fdt_build(root: FdtNode) -> bytes:
    """Serialize a nested-dict tree back into an FDT blob."""
    strings: dict[str, int] = {}
    strbuf = bytearray()
    structb = bytearray()

    def pad() -> None:
        while len(structb) % 4:
            structb.append(0)

    def stroff(name: str) -> int:
        if name not in strings:
            strings[name] = len(strbuf)
            strbuf.extend(name.encode() + b"\x00")
        return strings[name]

    def emit(node: FdtNode) -> None:
        structb.extend(struct.pack(">I", 1))
        structb.extend(node["name"].encode() + b"\x00")
        pad()
        for name, raw in node["props"]:
            structb.extend(struct.pack(">I", 3))
            structb.extend(struct.pack(">I", len(raw)))
            structb.extend(struct.pack(">I", stroff(name)))
            structb.extend(raw)
            pad()
        for ch in node["children"]:
            emit(ch)
        structb.extend(struct.pack(">I", 2))

    emit(root)
    structb.extend(struct.pack(">I", 9))
    rsvmap = struct.pack(">QQ", 0, 0)
    off_struct = 40 + len(rsvmap)
    off_strings = off_struct + len(structb)
    total = off_strings + len(strbuf)
    hdr = struct.pack(">10I", 0xD00DFEED, total, off_struct, off_strings,
                      40, 17, 16, 0, len(strbuf), len(structb))
    return bytes(hdr) + bytes(rsvmap) + bytes(structb) + bytes(strbuf)


def pack_u32s(values: list[int]) -> bytes:
    return struct.pack(">%dI" % len(values), *values)


def find_prop_values(tree: FdtNode, prop: str) -> list[bytes]:
    """All values of a property anywhere in the tree."""
    found: list[bytes] = []

    def walk(node: FdtNode) -> None:
        for name, raw in node["props"]:
            if name == prop:
                found.append(raw)
        for ch in node["children"]:
            walk(ch)

    walk(tree)
    return found
