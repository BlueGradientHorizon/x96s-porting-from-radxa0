"""Shared helper for the vendor-image fixes (brotli + replace + relist)."""

from .ext4 import (FixOp, make_transfer_list, replace_files_in_image,
                   require_brotli)


def patch_vendor_image(work_dir: str, entries: dict[str, bytes],
                       dat_name: str, list_name: str, ops: list[FixOp],
                       descs: list[str]
                       ) -> tuple[dict[str, bytes], bool, str]:
    """File-level fix of one vendor image.

    ops: [(img_path, new_data, skip_check, create_defaults,
    append_suffix)] (see replace_files_in_image). Returns replacements
    for the .new.dat.br and its .transfer.list (regenerated).
    """
    brotli = require_brotli()
    raw = brotli.decompress(entries[dat_name])
    new_raw, changed = replace_files_in_image(work_dir, dat_name[:-3], raw,
                                              ops)
    if not changed:
        return {}, False, ""
    return {dat_name: brotli.compress(new_raw, quality=6),
            list_name: make_transfer_list(new_raw)}, True, \
        "%s: %s" % (dat_name[:-len(".new.dat.br")], ", ".join(descs))
