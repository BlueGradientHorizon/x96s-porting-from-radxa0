"""Fix `vendor-wifi-ko`: RTL8723BS driver over dhd.ko in vendor_dlkm."""

import os

from .. import PROJECT_ROOT
from ..errors import FixError
from ..ext4 import FixOp
from ..vendor_img import patch_vendor_image
from . import Ctx, Entries, FixResult, register

WIFI_KO_CANDIDATES: tuple[str, ...] = (
    "8723bs-4.9.337.ko",
)
_WIFI_KO_CACHE: bytes | None = None


def _load_wifi_ko() -> bytes:
    """Read the rebuilt 8723bs.ko payload, searched next to CWD/root."""
    global _WIFI_KO_CACHE
    if _WIFI_KO_CACHE is not None:
        return _WIFI_KO_CACHE
    tried: list[str] = []
    search_dirs = [os.getcwd(), PROJECT_ROOT]
    for base in search_dirs:
        for rel in WIFI_KO_CANDIDATES:
            path = os.path.join(base, rel)
            tried.append(path)
            if os.path.isfile(path):
                with open(path, "rb") as handle:
                    _WIFI_KO_CACHE = handle.read()
                if not _WIFI_KO_CACHE.startswith(b"\x7fELF"):
                    raise FixError("wifi payload is not an ELF module: %s"
                                   % path)
                return _WIFI_KO_CACHE
    raise FixError("wifi payload not found (tried: %s); build 8723bs.ko "
                   "from source (see README.md) and place it at "
                   "8723bs-4.9.337.ko" % ", ".join(tried))


@register("vendor-wifi-ko", "RTL8723BS driver", ("ota",),
           ("vendor_dlkm.new.dat.br", "vendor_dlkm.transfer.list"))
def fix_vendor_dlkm_wifi_ko_ctx(ctx: Ctx, entries: Entries) -> FixResult:
    """Overwrite dhd.ko (Broadcom, useless on X96S) with 8723bs.ko."""
    ko = _load_wifi_ko()

    def already_fixed(cur: bytes) -> bool:
        return cur == ko

    ops: list[FixOp] = [("lib/modules/dhd.ko", ko, already_fixed, None, None)]
    repl, changed, summary = patch_vendor_image(
        ctx["work_dir"], entries, "vendor_dlkm.new.dat.br",
        "vendor_dlkm.transfer.list", ops,
        ["dhd.ko -> 8723bs driver"])
    return repl, changed, summary
