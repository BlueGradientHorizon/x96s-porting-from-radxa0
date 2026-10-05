#!/usr/bin/env python3
"""fix_x96s.py - patch LineageOS radxa0* firmware for the X96S stick.

Thin entry point: all logic lives in the x96s_patcher package
(see x96s_patcher/__init__.py for the module map and how to add a fix).

Takes ONE firmware package (type is detected by content):

    recovery OTA zip .............. all fixes (dtbo IR overlay,
                                      X96S remote keymap, early wifi
                                      insmod + firmware_path chmod,
                                      RTL8723BS driver, rebuilt u-boot)
                                      -> out/<stem>-x96s-fix.zip
    Amlogic USB-burn package (AIP) .. IR overlay into dtbo.PARTITION
                                      -> out/<stem>-<device>-x96s-fix.img

A burn package carries no vendor/system slots (those are logical
partitions inside super, delivered via the OTA zip), so vendor fixes
are OTA-only. Typical flow: flash the fixed burn package with the USB
Burning Tool, boot to recovery (remote works there thanks to the
dtbo fix), sideload the fixed OTA zip, reboot.

Runs on Linux (e.g. the ubuntu-vm guest). Required tools are
checked first thing and reported if missing: debugfs/e2fsck
(package e2fsprogs) and the python3 brotli module.

Usage:
     fix_x96s.py FIRMWARE.(zip|img)  patch package (see above)
     fix_x96s.py --list              list available fixes
     fix_x96s.py --skip a,b FIRMWARE.(zip|img)
                                         patch without fixes a,b

Rules the script follows:
    - the input file is only ever read, never modified;
    - dtbo.img is patched raw (no checksums there); vendor.new.dat.br
      and vendor_dlkm.new.dat.br are modified at file level with
      debugfs (real allocation, xattrs preserved) and their
      transfer.lists are regenerated (full `new` coverage);
      updater-script is never touched;
    - the burn package is rebuilt item by item (original order,
      version and flags preserved, offsets/size/CRC recomputed);
    - all temporary files live in a directory created in the *launch*
      directory and are removed again even if patching fails;
    - only the Python standard library is used, except `brotli`
      (pip install brotli) which is needed solely for the vendor image.
"""

import sys

from x96s_patcher.cli import main

if __name__ == "__main__":
    sys.exit(main())
