#!/usr/bin/env python3
"""Apply an X96S patch stack onto pristine sources. Run once.

Usage: apply_patches.py <target>
  target: directory suffix - patches live in patches-<target>/
          next to this script (e.g. rtl8723bs, uboot).

Runs from the SOURCES ROOT (patch -p1 paths are relative to it):
  cd ~/u-boot && python3 /path/to/apply_patches.py uboot

Applies patches-<target>/*.patch in sorted order via `git apply`
(check first, then apply). A partial/foreign tree fails loudly
instead of silently. Not idempotent: re-running on a patched tree
fails loudly by design - start from a pristine clone instead.
"""

import glob
import os
import subprocess
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    patches = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "patches-" + sys.argv[1])
    files = sorted(glob.glob(os.path.join(patches, "*.patch")))
    if not files:
        print("error: no patches in %s" % patches, file=sys.stderr)
        return 1
    for path in files:
        name = os.path.basename(path)
        check = subprocess.run(["git", "apply", "--check", path],
                               capture_output=True, text=True)
        if check.returncode != 0:
            print("error: %s does not apply:\n%s"
                  % (name, check.stderr), file=sys.stderr)
            return 1
        apply = subprocess.run(["git", "apply", path],
                               capture_output=True, text=True)
        if apply.returncode != 0:
            print("error: %s failed:\n%s"
                  % (name, apply.stderr), file=sys.stderr)
            return 1
        print("patched", name)
    print("ALL PATCHES APPLIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
