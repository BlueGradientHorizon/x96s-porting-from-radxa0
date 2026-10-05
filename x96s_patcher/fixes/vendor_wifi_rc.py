"""Fix `vendor-wifi-rc`: early plain insmod + firmware_path chmod.

The Broadcom vendor HAL (libwifi-hal.so) enumerates interfaces ONCE at
its startup (~t=7) and wifi_wait_for_driver_ready gives the driver only
~10s to appear; a late load is adopted never (proven). So the driver
must exist by ~t=10-15. Chip flakiness at t≈7 is covered by
SelfRecovery retries (proven rmmod/insmod cycles). No
services/scripts/loops. The chmod is mandatory: during configureChip
the HAL WRITES /sys/module/dhd/parameters/firmware_path as user wifi;
0644 gives EACCES (proven live). 0666 as a module_param does NOT
compile (VERIFY_OCTAL_PERMISSIONS), hence chmod here, right after
insmod.
"""

from ..errors import FixError
from ..ext4 import FixOp
from ..vendor_img import patch_vendor_image
from . import Ctx, Entries, FixResult, register

WIFI_RC_IDLE = (b"on boot\n"
                b"    insmod /vendor/lib/modules/dhd.ko\n"
                b"    chmod 0666 /sys/module/dhd/parameters/firmware_path\n")

# NOTE: idempotency is plain byte equality with this blob, so an
# updated rc re-patches automatically on the next run.
WIFI_OLD_RC_PREFIX = b"on boot\n    insmod /vendor/lib/modules/dhd.ko "


@register("vendor-wifi-rc", "early wifi insmod + firmware_path chmod",
           ("ota",), ("vendor.new.dat.br", "vendor.transfer.list"))
def fix_vendor_wifi_rc_ctx(ctx: Ctx, entries: Entries) -> FixResult:
    """Early plain insmod (HAL adopts interfaces at its startup)."""

    def skip(cur: bytes) -> bool:
        if cur == WIFI_RC_IDLE:
            return True
        if not cur.startswith(WIFI_OLD_RC_PREFIX):
            raise FixError("unexpected wifi init rc content, "
                           "refusing to patch")
        return False

    ops: list[FixOp] = [("etc/init/hw/init.amlogic.wifi_buildin.rc",
                         WIFI_RC_IDLE, skip, None, None)]
    repl, changed, summary = patch_vendor_image(
        ctx["work_dir"], entries, "vendor.new.dat.br",
        "vendor.transfer.list", ops,
        ["early wifi insmod + firmware_path chmod"])
    return repl, changed, summary
