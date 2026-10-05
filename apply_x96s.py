"""Apply all X96S patches to a pristine rtl8723bs tree. Run once.

Usage: python3 apply_x96s.py ~/8723bs
Verifies every replacement (asserts), so a partial/foreign tree fails
loudly instead of silently. Handles CRLF and LF sources.
Not idempotent: re-running on an already patched tree fails loudly
by design (anchors are gone after the first run) — start from a
pristine clone instead.
"""
import sys

DRV = sys.argv[1].rstrip("/")


Q = chr(34)
NL = None  # detected per file


def read(p):
    with open(p, newline="") as f:
        d = f.read()
    nl = "\r\n" if "\r\n" in d else "\n"
    return d, nl


# ---------------------------------------------------------------- procfs --
p = DRV + "/os_dep/linux/rtw_proc.c"
d, NL = read(p)
subs = [
    ("struct proc_ops", "struct file_operations"),
    (".proc_open", ".open"),
    (".proc_read", ".read"),
    (".proc_lseek", ".llseek"),
    (".proc_release", ".release"),
    (".proc_write", ".write"),
]
for old, new in subs:
    assert old in d, old
    d = d.replace(old, new)
assert "struct proc_ops" not in d  # type must be gone; identifier names stay
with open(p, "w", newline="") as f:
    f.write(d)
print("patched", p, "(procfs port)")

# ------------------------------------------------------------------ sdio --
p = DRV + "/os_dep/linux/sdio_intf.c"
d, NL = read(p)


# 1. extern decls after the INTEL_BYT ifdef
# (blank line before that #endif, matches verified tree).
# Only forward decls: no new #includes needed (msleep/jiffies come
# from headers the file already includes).
blank_anchor = '#include "rtw_android.h"' + NL + "#endif"
assert d.count(blank_anchor) == 1
d = d.replace(blank_anchor,
              '#include "rtw_android.h"' + NL + NL + "#endif")
old_inc = ("#endif /* CONFIG_PLATFORM_INTEL_BYT */" + NL)
assert d.count(old_inc) >= 1
# anchor on the first occurrence that follows rtw_android.h include
i = d.index('#include "rtw_android.h"')
j = d.index(old_inc, i)
decls = (
    "/* X96S: platform wifi power + MMC rescan (see module_init below). */" + NL
    + "extern int extern_wifi_set_enable(int is_on);" + NL
    + "extern void sdio_reinit(void);" + NL)
d = d[:j] + old_inc + NL + decls + d[j + len(old_inc):]

# 2. power/rescan helper + call (single-shot register). Power DOWN
# first like stock usb_power_control does, then up + rescan.
# No sleeps: sdio_reinit() ends in a synchronous flush_work, so by
# the time it returns the rescan is complete (exp. B tests this live).
anchor_entry = "static int rtw_drv_entry(void)" + NL
assert d.count(anchor_entry) == 1, "entry anchor: %d" % d.count(anchor_entry)
helpers = (
    "static void x96s_power_and_rescan(void)" + NL
    + "{" + NL
    + "\textern_wifi_set_enable(0);" + NL
    + "\textern_wifi_set_enable(1);" + NL
    + "\tsdio_reinit();" + NL
    + "}" + NL + NL)
d = d.replace(anchor_entry, helpers + anchor_entry)

anchor_reg = "\tret = sdio_register_driver(&sdio_drvpriv.r871xs_drv);" + NL
assert d.count(anchor_reg) == 1, "reg anchor: %d" % d.count(anchor_reg)
d = d.replace(anchor_reg, "\tx96s_power_and_rescan();" + NL + anchor_reg)

# 4. dummy Broadcom-compat knob: the vendor HAL opens
# /sys/module/dhd/parameters/firmware_path for WRITE during chip config
# (module is named dhd via Makefile rule below). NOTE: 0666 does NOT
# compile (VERIFY_OCTAL_PERMISSIONS rejects world-writable params), so
# the node stays 0644 and init.rc chmods it to 0666 right after insmod
# (see vendor-wifi-rc in fix_x96s.py) — the HAL runs as user wifi and
# 0644 gives EACCES on open (proven live 2026-10-03).
# Written value is ignored, firmware is built into the driver.
p2 = DRV + "/os_dep/linux/os_intfs.c"
d2, NL2 = read(p2)
anchor_fw = "module_param(rtw_lowrate_two_xmit, int, 0644);" + NL2
assert d2.count(anchor_fw) == 1, "fw anchor: %d" % d2.count(anchor_fw)
fw = ("/* X96S: see section 4 above. */" + NL2
      + "static char *firmware_path = " + Q + Q + ";" + NL2
      + "module_param(firmware_path, charp, 0644);" + NL2)
d2 = d2.replace(anchor_fw, anchor_fw + fw)
with open(p2, "w", newline="") as f:
    f.write(d2)
print("patched", p2, "(firmware_path compat knob)")

# ----------------------------------------------------------------- module --
# name the module dhd (not 8723bs): the vendor HAL hardcodes
# /sys/module/dhd/... paths. Objects keep building under their own
# names; only the link target is renamed.
p3 = DRV + "/Makefile"
d3, NL3 = read(p3)
anchor_t = "obj-$(CONFIG_RTL8723BS) := $(MODULE_NAME).o" + NL3
assert d3.count(anchor_t) == 1, "target anchor: %d" % d3.count(anchor_t)
d3 = d3.replace(anchor_t,
                "obj-$(CONFIG_RTL8723BS) := dhd.o" + NL3
                + "dhd-y := $(8723bs-y)" + NL3)
with open(p3, "w", newline="") as f:
    f.write(d3)
print("patched", p3, "(modname dhd)")

with open(p, "w", newline="") as f:
    f.write(d)
print("patched", p, "(x96s power/rescan)")
print("ALL PATCHES APPLIED")
