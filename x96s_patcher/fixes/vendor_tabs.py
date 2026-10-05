"""Fix `vendor-tabs`: X96S remote keymap inside vendor.new.dat.br."""

from ..ext4 import FixOp
from ..ir_data import FIXED_TAB2
from ..vendor_img import patch_vendor_image
from . import Ctx, Entries, FixResult, register


@register("vendor-tabs", "X96S remote keymap", ("ota",),
           ("vendor.new.dat.br", "vendor.transfer.list"))
def fix_vendor_tabs_ctx(ctx: Ctx, entries: Entries) -> FixResult:
    """Replace remote.tab2 inside vendor.new.dat.br with the fixed one."""
    fixed = FIXED_TAB2.encode()

    def already_fixed(cur: bytes) -> bool:
        return cur == fixed

    ops: list[FixOp] = [("etc/remote.tab2", fixed, already_fixed, None, None)]
    repl, changed, summary = patch_vendor_image(
        ctx["work_dir"], entries, "vendor.new.dat.br",
        "vendor.transfer.list", ops,
        ["remote.tab2 replaced with X96S keymap"])
    return repl, changed, summary
