#!/usr/bin/env python3
"""Build an Amlogic burn package with mainline U-Boot in the bootloader slot.

Takes a LOS burn package (radxa0 or radxa0_tab) and an Armbian image for
Radxa Zero, replaces ONLY the bootloader slot with the mainline FIP from
the Armbian image head. Everything else stays byte-identical to the LOS
original (same order/version/align/flags, CRC recomputed).

Usage:
    python3 make_mainline_uboot_aip.py <los_aip.img> <armbian.img>

Output:
    out/aml_install_package-uboot-mainline-<device>.img
    (device comes from the dtbo fingerprint: radxa0 / radxa0_tab)

Notes:
  - The bootloader FILE is programmed by the tool starting at eMMC
    sector 1 (GXL_START_BLK=1, see docs/7-armbian.md), so it must start
    with the BL2 header at byte 0. An MBR must NOT be prepended here;
    sector 0 is written live with dd after flashing (same doc).
  - Safety: the FIP's DDR entries (TOC e0-e2) must match the LOS
    package's - they carry the board DRAM init. Mismatch = refusal.
  - Only verify-free v1 packages are accepted (a v2 VERIFY hash would
    go stale); refuse to overwrite the input file.
"""

import os
import re
import struct
import sys
from typing import NoReturn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from x96s_patcher import amlogic  # noqa: E402
from x96s_patcher.errors import FixError  # noqa: E402

OUT_DIR = "out"
OUT_TEMPLATE = "aml_install_package-uboot-mainline-%s.img"

_FIP_TOC_MAGIC = struct.pack("<I", 0xAA640001)
_FIP_HEAD_OFF = 0x200  # Armbian head: 512B MBR, then the FIP
_FIP_TOC_OFF = 0x10010  # TOC position relative to FIP start (fip-radxa-zero)
_MBR_MAGIC = b"\x55\xaa"


def _fail(msg: str) -> NoReturn:
    raise FixError(msg)


def _aip_device(image: amlogic.AmlImage) -> str:
    """Device codename from the dtbo build footer (same as patcher)."""
    item = amlogic.find(image, "dtbo", "PARTITION")
    if item is None:
        return "unknown"
    match = re.search(rb"com\.android\.build\.dtbo\.fingerprint\x00([^\x00]+)",
                      item.data)
    if not match:
        return "unknown"
    dev = re.search(r"lineage_([^/]+)/([^:]+)",
                    match.group(1).decode("ascii", "replace"))
    return dev.group(2) if dev else "unknown"


def _mainline_fip(arm_path: str, slot_len: int) -> bytes:
    """Extract the mainline FIP sized exactly to the bootloader slot."""
    with open(arm_path, "rb") as handle:
        handle.seek(0)
        mbr = handle.read(512)
        if mbr[510:512] != _MBR_MAGIC:
            _fail("not an Armbian disk image (no MBR magic): %s" % arm_path)
        handle.seek(_FIP_HEAD_OFF)
        fip = handle.read(slot_len)
    if len(fip) != slot_len:
        _fail("Armbian image too small for a %d-byte FIP" % slot_len)
    if fip.count(_FIP_TOC_MAGIC) != 1 or \
            fip.find(_FIP_TOC_MAGIC) != _FIP_TOC_OFF:
        _fail("FIP table not where fip-radxa-zero puts it "
              "(no AA640001 at FIP+0x10010)")
    return fip


def _check_dram(fip: bytes, los_bl: bytes) -> None:
    """DDR TOC entries (e0-e2) must match: same DRAM init or refusal."""
    for e in range(3):
        off = _FIP_TOC_OFF + 16 + e * 40
        if fip[off:off + 40] != los_bl[off:off + 40]:
            _fail("DDR blob entry e%d differs from the LOS bootloader "
                  "(different DRAM init - refusing to brick)" % e)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print((__doc__ or "").strip().splitlines()[0])
        print("usage: python3 make_mainline_uboot_aip.py "
              "<los_aip.img> <armbian.img>")
        return 2
    los_path, arm_path = argv[1], argv[2]
    for path in (los_path, arm_path):
        if not os.path.isfile(path):
            _fail("file not found: %s" % path)

    with open(los_path, "rb") as handle:
        image = amlogic.parse(handle.read())
    print("LOS package: v%d, %d items" % (image.version, len(image.items)))
    if any(it.verify != 0 for it in image.items):
        _fail("package carries VERIFY hashes (v2-style) - replacement "
              "would invalidate them, refusing")
    bl = amlogic.find(image, "bootloader", "PARTITION")
    if bl is None:
        _fail("no bootloader.PARTITION slot in %s" % los_path)

    fip = _mainline_fip(arm_path, len(bl.data))
    _check_dram(fip, bl.data)

    if bl.data == fip and not bl.is_backup:
        print("bootloader already mainline, rebuilding anyway")
    bl.data = fip
    bl.is_backup = 0
    bl.backup_id = 0
    bl.coff_in_item = 0

    device = _aip_device(image)
    dst = os.path.join(os.getcwd(), OUT_DIR, OUT_TEMPLATE % device)
    if os.path.abspath(dst) == os.path.abspath(los_path):
        _fail("refusing to overwrite the input file")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    out = amlogic.build(image)
    with open(dst, "wb") as handle:
        handle.write(out)

    # verify by re-parsing
    check = amlogic.parse(out)
    assert len(check.items) == len(image.items)
    again = amlogic.find(check, "bootloader", "PARTITION")
    assert again is not None and again.data == fip and not again.is_backup
    print("OK: %s (%d bytes, bootloader -> mainline FIP, rest unchanged)"
          % (dst, len(out)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except FixError as err:
        print("error: %s" % err)
        sys.exit(1)
