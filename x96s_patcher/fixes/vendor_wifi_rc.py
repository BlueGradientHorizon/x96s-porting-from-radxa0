"""Fix `vendor-wifi-rc`: run the wifi dispatcher early.

The Broadcom vendor HAL (libwifi-hal.so) enumerates interfaces ONCE at
its startup (~t=7) and a late load is adopted never (proven). So the
driver must exist by ~t=10-15. `wait` blocks on the SDIO bus dir
(kernel-side, no polling in our code), then `start` fires the oneshot
service which detects the card by VID:PID, insmods the one matching
driver (all built as internal modname `dhd`: the HAL hardcodes
/sys/module/dhd/...) and chmods firmware_path. The chmod is mandatory:
during configureChip the HAL WRITES firmware_path as user wifi; 0644
gives EACCES (proven live). 0666 as a module_param does NOT compile
(VERIFY_OCTAL_PERMISSIONS), hence chmod after insmod, inside the
dispatcher (same behavior as the old static insmod, now selected).

Why a service and not `exec` (proven live 2026-10-06, two flashes):
both `exec /vendor/bin/x96s_wifi` and the modern
`exec - root root -- ...` form are SILENTLY SKIPPED by init in
`on boot` on this tree (wait runs, no service line, no error, no
denial — the other working execs all live in on-property contexts).
A defined oneshot service + `start` is the standard mechanism with
fully visible logging instead.

Why seclabel vendor_modprobe (proven live 2026-10-06 via ctl.start):
a bare service dies with "incorrect label or no domain transition
from u:r:init:s0" — generic vendor_file has none. The vendor policy
provides exactly one module-loader domain: init→vendor_modprobe
transition, entrypoint vendor_toolbox_exec, sys_module caps, kmsg
write, vendor_file read. The dispatcher needs nothing else: VID:PID
matching moves into each driver's module_init (fail -ENODEV when
absent) once a second driver exists, and the firmware_path chmod
stays in init (second wait+chmod above) — vendor_modprobe has no
sysfs, and the old static rc proved init's chmod works.
"""

from ..errors import FixError
from ..ext4 import FixOp
from ..vendor_img import patch_vendor_image
from . import Ctx, Entries, FixResult, register

WIFI_RC_IDLE = (b"service x96s_wifi /vendor/bin/x96s_wifi\n"
                b"    user root\n"
                b"    group root\n"
                b"    seclabel u:r:vendor_modprobe:s0\n"
                b"    oneshot\n"
                b"\n"
                b"on boot\n"
                b"    wait /sys/bus/sdio/devices 10\n"
                b"    start x96s_wifi\n"
                # start() is async: wait for the loaded driver's HAL knob
                # (kernel inotify, no polling) before init chmods it.
                # The chmod stays in init: the old static insmod+chmod
                # proved init can do it; vendor_modprobe has no sysfs.
                b"    wait /sys/module/dhd/parameters/firmware_path 10\n"
                b"    chmod 0666 /sys/module/dhd/parameters/firmware_path\n")

# NOTE: idempotency is plain byte equality with this blob, so an
# updated rc re-patches automatically on the next run. Earlier shapes
# (all replaced for cause, all re-patchable):
WIFI_KNOWN_OLD = (
    # original LOS static insmod (worked, single-driver)
    b"on boot\n    insmod /vendor/lib/modules/dhd.ko ",
    # interim bare exec (Android 15 init silently skips it in on boot)
    (b"on boot\n"
     b"    wait /sys/bus/sdio/devices 10\n"
     b"    exec /vendor/bin/x96s_wifi\n"),
    # interim modern exec (same silent skip in on boot here)
    (b"on boot\n"
     b"    wait /sys/bus/sdio/devices 10\n"
     b"    exec - root root -- /vendor/bin/x96s_wifi\n"),
)


@register("vendor-wifi-rc", "wifi dispatcher early exec",
          ("ota",), ("vendor.new.dat.br", "vendor.transfer.list"))
def fix_vendor_wifi_rc_ctx(ctx: Ctx, entries: Entries) -> FixResult:
    """Wait for SDIO enumeration, exec the dispatcher (HAL timing)."""

    def skip(cur: bytes) -> bool:
        if cur == WIFI_RC_IDLE:
            return True
        if cur in WIFI_KNOWN_OLD or cur.startswith(WIFI_KNOWN_OLD[0]):
            return False
        raise FixError("unexpected wifi init rc content, "
                       "refusing to patch")

    ops: list[FixOp] = [("etc/init/hw/init.amlogic.wifi_buildin.rc",
                         WIFI_RC_IDLE, skip, None, None)]
    repl, changed, summary = patch_vendor_image(
        ctx["work_dir"], entries, "vendor.new.dat.br",
        "vendor.transfer.list", ops,
        ["wifi dispatcher early exec"])
    return repl, changed, summary
