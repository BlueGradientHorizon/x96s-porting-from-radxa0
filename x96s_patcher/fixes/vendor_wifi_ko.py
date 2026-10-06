"""Fix `vendor-wifi-ko`: X96S wifi drivers + drop of the dead dhd.ko.

Deploys every WIFI_DRIVERS payload under its own name (all built with
internal modname `dhd`; only the dispatcher-selected one loads, so no
collision) and deletes the stock Broadcom dhd.ko (dead weight on X96S,
~6.9MB — its removal funds the room for ~3 drivers total).
"""

from ..ext4 import FixOp
from ..vendor_img import patch_vendor_image
from ..wifi_drivers import (WIFI_DRIVERS, load_payload, selinux_xattr)
from . import Ctx, Entries, FixResult, register

_KO_XATTR = selinux_xattr("u:object_r:vendor_file:s0")


def _skip_eq(data: bytes):
    def skip(cur: bytes) -> bool:
        return cur == data
    return skip


@register("vendor-wifi-ko", "X96S wifi drivers, drop dead dhd.ko",
          ("ota",), ("vendor_dlkm.new.dat.br", "vendor_dlkm.transfer.list"))
def fix_vendor_dlkm_wifi_ko_ctx(ctx: Ctx, entries: Entries) -> FixResult:
    """Deploy the driver set, delete the Broadcom dhd.ko."""
    ops: list[FixOp] = []
    descs: list[str] = []
    for _vid, _pid, img_path, payload in WIFI_DRIVERS:
        ko = load_payload(payload, "wifi driver")
        ops.append((img_path, ko, _skip_eq(ko),
                    ("0644", 0, 0, [_KO_XATTR]), None))
        descs.append("%s -> %s" % (payload, img_path))
    ops.append(("lib/modules/dhd.ko", None, None, None, None))
    descs.append("dhd.ko removed")
    repl, changed, summary = patch_vendor_image(
        ctx["work_dir"], entries, "vendor_dlkm.new.dat.br",
        "vendor_dlkm.transfer.list", ops, descs)
    return repl, changed, summary
