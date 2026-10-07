"""x96s_patcher - modular LineageOS firmware patcher for the X96S stick.

Patches LineageOS radxa0/radxa0_tab firmware zips (dtbo IR overlay,
X96S remote keymap, RTL8723BS wifi driver + dispatcher, RTL8723BS
bluetooth) into flashable out/<name>-x96s-fix.zip. See README.md
for the full story.

Layout:

    errors.py       FixError - the single failure type (message to user)
    workdir.py      WorkDir - temp dir in the launch dir, always cleaned
    fdt.py          minimal FDT parse/serialize, stdlib only
    ir_data.py      stock IR keymaps, fixed remote.tab2, DTBO fragments
    ext4.py         debugfs/e2fsck/brotli machinery for vendor images
    vendor_img.py   patch_vendor_image - shared helper for vendor fixes
    amlogic.py      Amlogic USB-burn package parse/rebuild (AIP)
    fixes/          one module per fix, self-registering (see below)
    pipeline.py     package in -> package out (type-detected)
    cli.py          argparse front-end (cmd_list, main)

Adding a new fix:

    1. create x96s_patcher/fixes/my_fix.py with
       func(ctx, entries) -> (replacements, changed, summary)
       (ctx carries work_dir; entries maps CANONICAL file names to
       bytes - "dtbo.img", "vendor.new.dat.br", ... - regardless of
       package type; the pipeline maps each transport's slots onto
       them, and writes replacements back through the same map);
    2. decorate it with @register("my-fix", "human description",
       ("ota",) and/or ("aip",)) - targets are the package types
       the fix applies to (recovery OTA zip / burn package);
    3. import the module in x96s_patcher/fixes/__init__.py -
       import order IS run order.

Nothing else needs touching.
"""

import os

# Project root (payloads live next to the launch dir, not in the package).
PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
