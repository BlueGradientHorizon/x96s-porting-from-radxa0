"""Fix `dtbo`: inject the IR receiver overlay into dtbo.img (pure Python)."""

import struct

from ..errors import FixError
from ..fdt import fdt_build, fdt_parse
from ..ir_data import build_ir_fragments, tree_has_rc
from . import Ctx, Entries, FixResult, register


def fix_remote_dtbo(dtbo_data: bytes) -> tuple[bytes, bool, str]:
    """Inject the IR overlay into a mkdtbo dtbo.img.

    Returns (new_bytes, changed_bool, summary_str). The file size is
    preserved (zero padding), block layout untouched.
    """
    if dtbo_data[:4] != b"\xd7\xb7\xab\x1e":
        raise FixError("dtbo.img has no mkdtbo magic")
    ent_size, ent_off = struct.unpack(">2I", dtbo_data[32:40])
    blob = dtbo_data[ent_off:ent_off + ent_size]
    tree = fdt_parse(blob)
    if tree_has_rc(tree):
        return dtbo_data, False, ""
    for frag in build_ir_fragments():
        tree["children"].append(frag)
    new_blob = fdt_build(tree)
    if not tree_has_rc(fdt_parse(new_blob)):
        raise FixError("internal error: overlay rebuild lost rc node")
    out = bytearray(dtbo_data)
    if 64 + len(new_blob) > len(out):
        raise FixError("patched dtbo does not fit dtbo.img (%d > %d)"
                       % (64 + len(new_blob), len(out)))
    out[64:64 + len(new_blob)] = new_blob
    struct.pack_into(">I", out, 4, 64 + len(new_blob))
    struct.pack_into(">I", out, 32, len(new_blob))
    return bytes(out), True, "dtbo: IR receiver overlay injected"


@register("dtbo", "IR receiver overlay", ("ota", "aip"),
           ("dtbo.img",))
def fix_remote_dtbo_ctx(ctx: Ctx, entries: Entries) -> FixResult:
    """Inject the IR overlay into a mkdtbo dtbo.img (pure Python)."""
    new_bytes, changed, summary = fix_remote_dtbo(entries["dtbo.img"])
    if not changed:
        return {}, False, ""
    return {"dtbo.img": new_bytes}, True, summary
