"""Fix `vendor-wifi-dispatch`: dispatcher binary + VID:PID map.

Puts /vendor/bin/x96s_wifi (static, no libc — see dispatcher/) and the
generated /vendor/etc/wifi/x96s_wifi.map into the vendor image. The
binary is labeled vendor_toolbox_exec (entrypoint for the
vendor_modprobe domain init transitions into — generic vendor_file
has no transition and the service dies; proven live via ctl.start).
The map is a plain config (vendor_configs_file, like its neighbors).
Modes mirror the stock neighbors (0755 binary, 0644 config).
"""

from ..ext4 import FixOp
from ..vendor_img import patch_vendor_image
from ..wifi_drivers import (DISPATCHER_IMAGE_PATH, DISPATCHER_PAYLOAD,
                             MAP_IMAGE_PATH, build_map, load_payload,
                             selinux_xattr)
from . import Ctx, Entries, FixResult, register


@register("vendor-wifi-dispatch", "wifi dispatcher binary + VID:PID map",
          ("ota",), ("vendor.new.dat.br", "vendor.transfer.list"))
def fix_vendor_wifi_dispatch_ctx(ctx: Ctx, entries: Entries
                                 ) -> FixResult:
    """Deploy the dispatcher and its map."""
    disp = load_payload(DISPATCHER_PAYLOAD, "wifi dispatcher")
    amap = build_map()

    def skip_disp(cur: bytes) -> bool:
        return cur == disp

    def skip_map(cur: bytes) -> bool:
        return cur == amap

    ops: list[FixOp] = [
        (DISPATCHER_IMAGE_PATH, disp, skip_disp,
         ("0755", 0, 0,
          [selinux_xattr("u:object_r:vendor_toolbox_exec:s0")]), None),
        (MAP_IMAGE_PATH, amap, skip_map,
         ("0644", 0, 0,
          [selinux_xattr("u:object_r:vendor_configs_file:s0")]), None),
    ]
    repl, changed, summary = patch_vendor_image(
        ctx["work_dir"], entries, "vendor.new.dat.br",
        "vendor.transfer.list", ops,
        ["x96s_wifi dispatcher", "VID:PID map"])
    return repl, changed, summary
