"""Fix `bootloader`: rebuilt u-boot with the cold-boot update window.

The stock bootloader flashes WorldCup for ~750ms on every cold boot
(`run try_auto_burn;` in the cold_boot branch of switch_bootmode);
the LOS one dropped that call - and the call lives in SAVED env, so
rebuilt defaults alone never heal old installs. This fix replaces
the bootloader in both package types with a locally rebuilt u-boot
(LineageOS/android_hardware_amlogic_u-boot @ fd4a7d4, board
g12a_radxa0_v1, plus a C-hook in board_late_init doing the same
700/750 window past any env; see README.md):
OTA carries it as bootloader.img, the burn package as
bootloader.PARTITION. FIP structure is identical (same UUIDs/order/
offsets, only the BL33 body differs); the image is smaller than the
slot, so it fits the fixed-size eMMC partition.
"""

import os
import struct

from .. import PROJECT_ROOT
from ..errors import FixError
from . import Ctx, Entries, FixResult, register

BOOTLOADER_CANDIDATES: tuple[str, ...] = (
    "bootloader-x96s.bin",
)
_BOOTLOADER_CACHE: bytes | None = None

# FIP table-of-contents magic (must appear near the start)
_FIP_TOC_MAGIC = struct.pack("<I", 0xAA640001)


def _load_bootloader() -> bytes:
    """Read the rebuilt u-boot FIP payload, searched next to CWD/root."""
    global _BOOTLOADER_CACHE
    if _BOOTLOADER_CACHE is not None:
        return _BOOTLOADER_CACHE
    tried: list[str] = []
    search_dirs = [os.getcwd(), PROJECT_ROOT]
    for base in search_dirs:
        for rel in BOOTLOADER_CANDIDATES:
            path = os.path.join(base, rel)
            tried.append(path)
            if os.path.isfile(path):
                with open(path, "rb") as handle:
                    _BOOTLOADER_CACHE = handle.read()
                if _FIP_TOC_MAGIC not in _BOOTLOADER_CACHE[:0x20000]:
                    raise FixError("bootloader payload has no FIP table: %s"
                                   % path)
                return _BOOTLOADER_CACHE
    raise FixError("bootloader payload not found (tried: %s); build u-boot "
                   "from source (see README.md) and place it at "
                   "bootloader-x96s.bin" % ", ".join(tried))


@register("bootloader", "rebuilt u-boot with update window",
           ("ota", "aip"), ("bootloader.img",))
def fix_bootloader_ctx(ctx: Ctx, entries: Entries) -> FixResult:
    """Replace the bootloader with the rebuilt one (with update window)."""
    blob = _load_bootloader()
    if entries["bootloader.img"] == blob:
        return {}, False, ""
    return {"bootloader.img": blob}, True, \
        "bootloader -> rebuilt u-boot (cold-boot update window)"
