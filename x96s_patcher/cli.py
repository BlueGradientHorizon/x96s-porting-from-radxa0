"""Command-line front-end for the patcher."""

import argparse
import sys

from .errors import FixError
from .fixes import FIXES
from .pipeline import cmd_patch


def cmd_list(_args: argparse.Namespace) -> int:
    print("fixes (ota = recovery OTA zip, aip = Amlogic USB-burn package):")
    for name, desc, targets, _needs, _func in FIXES:
        print("  %-14s [%-7s] %s" % (name, "+".join(targets), desc))
    print("output: out/<stem>-x96s-fix.zip (ota) or")
    print("        out/<stem>-<device>-x96s-fix.img (aip),")
    print("        next to the launch directory")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Patch LineageOS radxa0 firmware for the X96S stick: "
                    "either a recovery OTA zip or an Amlogic USB-burn "
                    "package (type is detected). Output is ready to flash.")
    parser.add_argument("firmware", nargs="?",
                        help="firmware package to patch (.zip or .img)")
    parser.add_argument("--list", action="store_true",
                        help="list available fixes")
    parser.add_argument("--skip", default="",
                        help="comma-separated fix names to skip "
                             "(see --list), e.g. --skip vendor-wifi-rc,"
                             "vendor-wifi-ko")
    args = parser.parse_args(argv)
    args.skip = set(s for s in args.skip.split(",") if s)
    unknown = args.skip - set(name for name, _d, _t, _n, _f in FIXES)
    if unknown:
        parser.error("unknown fix names: %s" % ", ".join(sorted(unknown)))
    if args.list:
        return cmd_list(args)
    try:
        if not args.firmware:
            parser.print_usage(sys.stderr)
            return 2
        return cmd_patch(args)
    except FixError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
