"""Pipeline: firmware in -> fixed firmware out.

Single argument: either a recovery OTA zip or an Amlogic USB-burn
package. The type is detected by content (zip with updater-script vs
burn-package magic), reported, and only the fixes applicable to that
type run.

Fixes see CANONICAL file names ("dtbo.img", "vendor.new.dat.br",
...), transport-agnostic: each transport maps its slots onto them
(an OTA zip carries dtbo.img as-is, a burn package carries it as
dtbo.PARTITION). What a fix returns, the caller writes back through
the same map:

    OTA: dtbo, vendor-tabs, vendor-wifi-rc, vendor-wifi-ko
         -> out/<stem>-x96s-fix.zip
    AIP: dtbo (into dtbo.PARTITION)
         -> out/<stem>-<device>-x96s-fix.img

A burn package carries no vendor/system slots (those are logical
partitions inside super, delivered via the OTA zip), so vendor fixes
report N/A there instead of failing. See README.md for the proof.
"""

import argparse
import os
import re
import shutil
import zipfile

from . import amlogic
from .errors import FixError
from .ext4 import check_tools
from .fixes import FIXES
from .workdir import WorkDir

OUT_SUFFIX = "-x96s-fix"
OUT_DIR = "out"

# zip entries any OTA fix may read/replace (loaded once, then threaded
# through the fixes); canonical names ARE entry names here
FIX_TARGETS: tuple[str, ...] = ("dtbo.img", "vendor.new.dat.br",
                                "vendor.transfer.list",
                                "vendor_dlkm.new.dat.br",
                                "vendor_dlkm.transfer.list",
                                "bootloader.img")

# canonical file -> burn-package item key ("sub.main").
# env.PARTITION does not exist in the input package: a fix may
# produce it (pipeline creates the item), it is never read from it.
AIP_SLOTS: dict[str, str] = {"dtbo.img": "dtbo.PARTITION",
                             "bootloader.img": "bootloader.PARTITION",
                             "env.img": "env.PARTITION"}


def _is_recovery_zip(path: str) -> bool:
    if not zipfile.is_zipfile(path):
        return False
    with zipfile.ZipFile(path, "r") as zin:
        return ("META-INF/com/google/android/updater-script"
                in zin.namelist())


def _run_fixes(pkg_type: str, ctx: dict[str, object],
               entries: dict[str, bytes], skip: set[str]
               ) -> tuple[dict[str, bytes], list[str], list[str]]:
    """Run applicable fixes; returns (entries, applied, not_applicable).

    A fix is skipped silently only for --skip; type mismatch and
    missing files are reported explicitly (no silent-KeyError).
    """
    applied: list[str] = []
    skipped: list[str] = []
    for name, _desc, targets, needs, func in FIXES:
        if pkg_type not in targets:
            others = "+".join(t for t in targets)
            skipped.append("%s: N/A (%s-only fix)" % (name, others))
            continue
        if name in skip:
            continue
        missing = [need for need in needs if need not in entries]
        if missing:
            skipped.append("%s: N/A (needs %s, absent from this package)"
                           % (name, ", ".join(missing)))
            continue
        repl, _changed, summary = func(ctx, entries)
        entries.update(repl)
        if summary:
            applied.append(summary)
    return entries, applied, skipped


def _report(dst: str, applied: list[str], skipped: list[str]) -> int:
    print("patched: %s" % dst)
    for line in applied:
        print("  - %s" % line)
    for line in skipped:
        print("  - %s" % line)
    if not applied and not skipped:
        print("  (firmware was already fixed, copied unchanged)")
    elif not applied:
        print("  (no changes applied)")
    return 0


def _patch_ota(args: argparse.Namespace, src: str) -> int:
    stem = os.path.basename(src)
    if stem.lower().endswith(".zip"):
        stem = stem[:-4]
    dst = os.path.join(os.getcwd(), OUT_DIR, stem + OUT_SUFFIX + ".zip")
    if os.path.abspath(dst) == src:
        raise FixError("refusing to overwrite the input file")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    check_tools()
    with WorkDir() as work:
        with zipfile.ZipFile(src, "r") as zin:
            names = zin.namelist()
            entries = {name: zin.read(name) for name in FIX_TARGETS
                       if name in names}
            ctx: dict[str, object] = {"work_dir": work.path}
            entries, applied, skipped = _run_fixes("ota", ctx, entries,
                                                   args.skip)
            tmp_out = os.path.join(work.path, "out.zip")
            with zipfile.ZipFile(tmp_out, "w") as zout:
                for info in zin.infolist():
                    data = entries.get(info.filename, zin.read(info.filename))
                    if info.is_dir():
                        zout.writestr(info, b"")
                        continue
                    out_info = zipfile.ZipInfo(info.filename, info.date_time)
                    out_info.compress_type = info.compress_type
                    out_info.external_attr = info.external_attr
                    out_info.create_system = info.create_system
                    zout.writestr(out_info, data)
        with zipfile.ZipFile(tmp_out, "r") as check:
            if check.testzip() is not None:
                raise FixError("internal error: output zip is corrupt")
        shutil.copy(tmp_out, dst)
    return _report(dst, applied, skipped)


def _aip_device(image: amlogic.AmlImage) -> str:
    """Device codename from the dtbo build footer (radxa0, ...).

    The fingerprint is NOT part of the FDT tree - the build system
    appends "com.android.build.dtbo.fingerprint\\0<value>" after the
    entry - so search the raw bytes.
    """
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


def _patch_aip(args: argparse.Namespace, src: str, raw: bytes) -> int:
    image = amlogic.parse(raw)  # validates magic + CRC + structure
    print("detected: Amlogic burn package (v%d, %d items)"
          % (image.version, len(image.items)))
    if image.version != 1:
        raise FixError("unsupported burn-package version v%d "
                       "(only v1 tested, refusing)" % image.version)
    stem = os.path.basename(src)
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    device = _aip_device(image)
    dst = os.path.join(os.getcwd(), OUT_DIR,
                       "%s-%s%s.img" % (stem, device, OUT_SUFFIX))
    if os.path.abspath(dst) == src:
        raise FixError("refusing to overwrite the input file")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with WorkDir() as work:
        by_key = {"%s.%s" % (it.sub, it.main): it.data
                  for it in image.items}
        entries = {canon: by_key[slot] for canon, slot in AIP_SLOTS.items()
                   if slot in by_key}
        ctx: dict[str, object] = {"work_dir": work.path}
        entries, applied, skipped = _run_fixes("aip", ctx, entries,
                                               args.skip)
        for canon, new_data in entries.items():
            if canon not in AIP_SLOTS:
                raise FixError("internal error: fix returned unknown "
                               "file %s" % canon)
            sub, main = AIP_SLOTS[canon].rsplit(".", 1)
            item = amlogic.find(image, sub, main)
            if item is None:
                # produced by a fix (e.g. env): append a new item
                image.items.append(amlogic.AmlItem(
                    sub, main, amlogic.FILE_TYPE_GENERIC, 0, 0, 0, 0,
                    new_data))
                continue
            if item.data == new_data:
                continue
            if item.verify != 0:
                raise FixError("%s.%s carries VERIFY, refusing to rewrite "
                               "without it" % (sub, main))
            if len(new_data) > len(item.data):
                raise FixError("%s.%s grew (%d -> %d), refusing: "
                               "the eMMC slot has a fixed size"
                               % (sub, main, len(item.data), len(new_data)))
            item.data = new_data
            item.is_backup = 0
            item.backup_id = 0
        out = amlogic.build(image)
        amlogic.parse(out)  # re-validate: magic + CRC + structure
        with open(dst, "wb") as handle:
            handle.write(out)
    return _report(dst, applied, skipped)


def cmd_patch(args: argparse.Namespace) -> int:
    src = os.path.abspath(args.firmware)
    if not os.path.isfile(src):
        raise FixError("file not found: %s" % args.firmware)
    if _is_recovery_zip(src):
        print("detected: recovery OTA package")
        return _patch_ota(args, src)
    with open(src, "rb") as handle:
        raw = handle.read()
    if amlogic.is_package(raw):
        return _patch_aip(args, src, raw)
    raise FixError("not a firmware package: neither a recovery zip "
                   "(no updater-script) nor an Amlogic burn image "
                   "(bad magic): %s" % args.firmware)
