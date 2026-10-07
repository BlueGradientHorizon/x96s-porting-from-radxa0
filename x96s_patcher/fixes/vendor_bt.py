"""Fix `vendor-bt`: Realtek RTL8723BS bluetooth (H5 UART) userspace stack.

The LOS vendor image ships a Broadcom-only libbt-vendor.so: it talks
BCM protocol into the Realtek combo chip, gets no answer, and the
fluoride stack aborts in HciHal (5 crashes per boot, proven 2026-10-07).
This fix transplants the stock RTK vendor lib (same 32-bit ABI as the
LOS vendor userspace, H5 + 8723BS firmware download): proven live via
bind-mount — chip id 0x8723, rtl8723bs_fw load OK, 115200 -> 1500000,
stack ON with the chip address, EIR up, no crash.

Deploys: lib/libbt-vendor.so (replaced, mode/xattrs preserved),
etc/bluetooth/rtkbt.conf + firmware/rtl8723bs_fw + firmware/rtl8723bs_config
(created 0644 with neighbor labels), and deletes the dead Broadcom
.hcd files (the RTK lib never reads them; their removal funds the
space, same precedent as the dead dhd.ko in vendor-wifi-ko).
"""

import os

from .. import PROJECT_ROOT
from ..errors import FixError
from ..ext4 import FixOp
from ..vendor_img import patch_vendor_image
from ..wifi_drivers import load_payload, selinux_xattr
from . import Ctx, Entries, FixResult, register

_RTK_LIB_IMAGE_PATH = "lib/libbt-vendor.so"
_RTK_LIB_PAYLOAD = "bt_fw/libbt-vendor.so"
_CONF_IMAGE_PATH = "etc/bluetooth/rtkbt.conf"
_CONF_PAYLOAD = "bt_fw/rtkbt.conf"
_FW_IMAGE_PATH = "firmware/rtl8723bs_fw"
_FW_PAYLOAD = "bt_fw/rtl8723bs_fw"
_CFGSW_IMAGE_PATH = "firmware/rtl8723bs_config"
_CFGSW_PAYLOAD = "bt_fw/rtl8723bs_config"

_CONF_XATTR = selinux_xattr("u:object_r:vendor_configs_file:s0")
_FW_XATTR = selinux_xattr("u:object_r:vendor_file:s0")

# Dead Broadcom firmware on X96S (RTK lib never reads .hcd).
_BCM_HCDS = (
    "4343.hcd",
    "BCM20702.hcd",
    "BCM20703A2.hcd",
    "BCM2076.hcd",
    "BCM4330.hcd",
    "BCM43430B0.hcd",
    "BCM4345C0.hcd",
    "BCM4345C5.hcd",
    "BCM4350.hcd",
    "BCM4354.hcd",
    "BCM4359C0.hcd",
    "BCM4362A1.hcd",
    "BCM4362A2.hcd",
    "bcm43241b4.hcd",
    "bcm43341b0.hcd",
    "bcm4335c0.hcd",
    "bcm43569a2.hcd",
)


def _read_repo_file(relpath: str, desc: str) -> bytes:
    for base in (os.getcwd(), PROJECT_ROOT):
        path = os.path.join(base, relpath)
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                return handle.read()
    raise FixError("%s not found (looked for %s next to CWD and repo root); "
                   "it ships with the repo" % (desc, relpath))


def _skip_eq(data: bytes):
    def skip(cur: bytes) -> bool:
        return cur == data
    return skip


@register("vendor-bt", "RTL8723BS bluetooth (RTK H5 stack)",
          ("ota",), ("vendor.new.dat.br", "vendor.transfer.list"))
def fix_vendor_bt_ctx(ctx: Ctx, entries: Entries) -> FixResult:
    """Replace the Broadcom BT vendor lib with the stock RTK one."""
    rtk_lib = load_payload(_RTK_LIB_PAYLOAD, "RTK bluetooth vendor lib")
    conf = _read_repo_file(_CONF_PAYLOAD, "rtkbt.conf")
    fw = _read_repo_file(_FW_PAYLOAD, "rtl8723bs_fw")
    cfg = _read_repo_file(_CFGSW_PAYLOAD, "rtl8723bs_config")
    ops: list[FixOp] = [
        (_RTK_LIB_IMAGE_PATH, rtk_lib, _skip_eq(rtk_lib), None, None),
        (_CONF_IMAGE_PATH, conf, _skip_eq(conf), ("0644", 0, 0, [_CONF_XATTR]),
         None),
        (_FW_IMAGE_PATH, fw, _skip_eq(fw), ("0644", 0, 0, [_FW_XATTR]), None),
        (_CFGSW_IMAGE_PATH, cfg, _skip_eq(cfg), ("0644", 0, 0, [_FW_XATTR]),
         None),
    ]
    descs = ["libbt-vendor.so -> RTK H5", "rtkbt.conf",
             "rtl8723bs_fw", "rtl8723bs_config"]
    for hcd in _BCM_HCDS:
        ops.append(("etc/bluetooth/" + hcd, None, None, None, None))
    descs.append("%d dead BCM .hcd removed" % len(_BCM_HCDS))
    repl, changed, summary = patch_vendor_image(
        ctx["work_dir"], entries, "vendor.new.dat.br",
        "vendor.transfer.list", ops, descs)
    return repl, changed, summary
