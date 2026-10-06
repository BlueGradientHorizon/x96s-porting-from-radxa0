"""ext4 surgery with the real filesystem driver (not byte surgery).

vendor.new.dat.br / vendor_dlkm.new.dat.br are plain ext4 images whose
transfer.lists contain only `new` commands (full-OTA style, no hashes),
so block layout and image size are free to change: files are replaced
with debugfs (proper allocation, modes and xattrs preserved), the fs
is verified with e2fsck, and the transfer.list is regenerated with
full `new` coverage. updater-script references only file names and
is never modified.
"""

import os
import re
import shutil
import struct
import subprocess
from collections.abc import Callable
from types import ModuleType
from typing import Any

from .errors import FixError

# One file operation inside an image:
# (img_path, new_data, already_fixed(data)->bool,
#  create_defaults, append_suffix).
# new_data None + append_suffix None (both None, skip unused) means
# DELETE: remove the file (missing file = already done, skipped).
FixOp = tuple[str, bytes | None,
              Callable[[bytes], bool] | None,
              tuple[str, int, int, list[tuple[str, bytes]]] | None,
              bytes | None]

# debugfs `write` creates files as 0770; the type bits must be re-added
# via `sif` (there is no chmod in debugfs).
_IFREG = 0o100000


def check_tools() -> None:
    """Fail fast with a clear message if a required tool is missing."""
    missing = [t for t in ("debugfs", "e2fsck") if shutil.which(t) is None]
    try:
        import brotli  # type: ignore[import]  # noqa: F401
    except ImportError:
        missing.append("python3-brotli")
    if missing:
        raise FixError(
            "missing tools: %s (install with: "
            "sudo apt install e2fsprogs python3-brotli)" % ", ".join(missing))


def run_tool(*args: str, merge_stderr: bool = False) -> str:
    """Run a local tool, return stdout text.

    debugfs prints request errors to stderr while exiting 0, so its
    callers must pass merge_stderr=True (the shared bad-line scanner
    in debugfs_request then sees them).
    """
    try:
        proc = subprocess.run(
            args, stdout=subprocess.PIPE, timeout=300,
            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE)
    except FileNotFoundError:
        raise FixError("tool not found: %s" % args[0])
    except subprocess.TimeoutExpired:
        raise FixError("tool timed out: %s" % args[0])
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        tail = "; ".join(err[-3:]) if err else "exit %d" % proc.returncode
        raise FixError("%s: %s" % (args[0], tail))
    return proc.stdout.decode("utf-8", "replace")


def debugfs_request(work_dir: str, image_name: str, req_lines: list[str],
                    write_mode: bool) -> str:
    """Run debugfs requests from a request file in the work dir.

    Returns stdout. Any suspicious line (Usage/missing file/error) is
    treated as failure even if debugfs exits 0.
    """
    req_file = os.path.join(work_dir, "req.txt")
    with open(req_file, "w", newline="\n") as handle:
        handle.write("\n".join(req_lines) + "\n")
    cmd = ["debugfs"]
    if write_mode:
        cmd.append("-w")
    cmd += ["-f", req_file, os.path.join(work_dir, image_name)]
    out = run_tool(*cmd, merge_stderr=True)
    bad = [ln for ln in out.splitlines()
             if re.search(r"(?i)(usage:|no such file|not found|couldn.t|"
                          r"error|failed|invalid|no space|no free|enospc|"
                          r"disk full|filesystem full)", ln)
             and "debugfs " not in ln]
    if bad:
        raise FixError("debugfs: %s" % "; ".join(bad[:3]))
    return out


def e2fsck_check(work_dir: str, image_name: str) -> None:
    """Verify the image is clean (read-only check, must exit 0)."""
    run_tool("e2fsck", "-n", "-f", os.path.join(work_dir, image_name))


def _parse_stat(out: str) -> tuple[str, int, int]:
    """Parse one debugfs `stat` block -> (mode_octal, uid, gid)."""
    mode = re.search(r"Mode:\s+(\d+)", out)
    user = re.search(r"User:\s+(\d+)\s+Group:\s+(\d+)", out)
    if "Type: regular" not in out or not mode or not user:
        raise FixError("debugfs stat: not a regular file:\n%s" % out[-500:])
    return mode.group(1), int(user.group(1)), int(user.group(2))


def _parse_ea_list(out: str) -> list[str]:
    """Parse debugfs `ea_list` output -> [attr names]."""
    return re.findall(r"^\s+(\S+)\s+\(\d+\)", out, re.M)


def replace_files_in_image(work_dir: str, image_name: str, raw: bytes,
                           ops: list[FixOp]) -> tuple[bytes, bool]:
    """Replace files (or append a suffix) inside a raw ext4 image.

    ops: list of (img_path, new_data, already_fixed(data)->bool,
    create_defaults, append_suffix). new_data None + append_suffix
    set appends suffix to current contents (skip if already there).
    create_defaults is None (file must exist, its mode/uid/gid/xattrs
    are preserved) or (mode, uid, gid, [(attr, value)]) for a new
    file. The fs must be e2fsck-clean afterwards.
    Returns (new_raw, changed_bool).
    """
    img_path = os.path.join(work_dir, image_name)
    with open(img_path, "wb") as handle:
        handle.write(raw)
    # pass 1 (read-only): stat + xattr names + current contents for
    # replace-ops; plain `ls` of the parent dir for create-ops and
    # delete-ops. Staging files are named by op index (not position),
    # so skipped ops can't shift the others.
    req: list[str] = []
    reps: list[int] = []
    creates: list[int] = []
    deletes: list[int] = []
    for idx, (path, new, _skip, cdef, suffix) in enumerate(ops):
        if cdef is not None:
            creates.append(idx)
            continue
        if new is None and suffix is None:
            deletes.append(idx)
            continue
        reps.append(idx)
        req += ["stat " + path, "ea_list " + path,
                "dump %s %s/cur%d.bin" % (path, work_dir, idx)]
    out = debugfs_request(work_dir, image_name, req, False)
    blocks = re.split(r"(?m)^Inode: \d+", out)
    if len(blocks) - 1 != len(reps):
        raise FixError("debugfs stat: unexpected output")
    # wanted entries: [op_idx, path, new_data, mode, uid, gid,
    #                  [attr names], [staged value files], is_new].
    wanted: list[list[Any]] = []
    for idx, ((path, new_data, skip, _cdef, suffix), block) in enumerate(zip(
            [ops[i] for i in reps], blocks[1:])):
        oidx = reps[idx]
        with open(os.path.join(work_dir, "cur%d.bin" % oidx),
                  "rb") as handle:
            cur = handle.read()
        if suffix is not None:
            if suffix in cur:
                continue
            new_data = cur + suffix
        elif skip is not None and skip(cur):
            continue
        # NOTE: files may grow (debugfs allocates properly, unlike the
        # old in-place surgery); ENOSPC fails loudly in debugfs itself.
        mode, uid, gid = _parse_stat(block)
        wanted.append([oidx, path, new_data, mode, uid, gid,
                       _parse_ea_list(block), [], False])
    for oidx in creates:
        path, new_data, _skip, cdef, _suffix = ops[oidx]
        parent = path.rsplit("/", 1)[0] or "/"
        base = path.rsplit("/", 1)[-1]
        ls_out = debugfs_request(work_dir, image_name, ["ls " + parent], False)
        if re.search(r"\b%s\b" % re.escape(base), ls_out):
            # present: compare contents, refuse to clobber differences
            debugfs_request(work_dir, image_name,
                            ["dump %s %s/cur%d.bin" % (path, work_dir, oidx)],
                            False)
            with open(os.path.join(work_dir, "cur%d.bin" % oidx),
                      "rb") as handle:
                if handle.read() != new_data:
                    raise FixError("%s exists with other contents, refusing"
                                   % path)
            continue
        assert cdef is not None
        mode, uid, gid, eas = cdef
        vals: list[str] = []
        for ea_no, (_ea, val) in enumerate(eas):
            ef = os.path.join(work_dir, "ea%d.bin" % (oidx * 10 + ea_no))
            with open(ef, "wb") as handle:
                handle.write(val)
            vals.append(ef)
        wanted.append([oidx, path, new_data, mode, uid, gid,
                       [ea for ea, _v in eas], vals, True])
    if not wanted and not deletes:
        return raw, False
    # pass 2 (read-only): stage xattr values aside before rm
    # (create-ops already staged theirs above)
    req = []
    for oidx, path, _new, _m, _u, _g, eas, vals, is_new in wanted:
        if is_new:
            continue
        for ea_no, ea in enumerate(eas):
            vals.append(os.path.join(work_dir, "ea%d.bin" % (oidx * 10 +
                                                              ea_no)))
            req.append("ea_get -f %s %s %s" % (work_dir + "/ea%d.bin" %
                                              (oidx * 10 + ea_no), path, ea))
    if req:
        debugfs_request(work_dir, image_name, req, False)
    # pass 3 (write): deletes first (they fund the free space the
    # creates need), then rm + write + restore mode/owner/xattrs.
    # A missing delete target is already-done, not an error.
    deleted_any = False
    for oidx in deletes:
        path = ops[oidx][0]
        try:
            debugfs_request(work_dir, image_name, ["rm " + path], True)
            deleted_any = True
        except FixError:
            parent = path.rsplit("/", 1)[0] or "/"
            base = path.rsplit("/", 1)[-1]
            ls_out = debugfs_request(work_dir, image_name,
                                     ["ls " + parent], False)
            if re.search(r"\b%s\b" % re.escape(base), ls_out):
                raise
    req = []
    for oidx, path, new_data, mode, uid, gid, eas, vals, is_new in wanted:
        with open(os.path.join(work_dir, "new%d.bin" % oidx),
                  "wb") as handle:
            handle.write(new_data)
        if not is_new:
            req.append("rm " + path)
        req.append("write %s/new%d.bin %s" % (work_dir, oidx, path))
        req.append("sif %s mode 0%o" % (path, _IFREG | int(mode, 8) & 0o7777))
        if (uid, gid) != (0, 0):
            req.append("sif %s uid %d" % (path, uid))
            req.append("sif %s gid %d" % (path, gid))
        for ea_no, (ea, _val) in enumerate(zip(eas, vals)):
            req.append("ea_set -f %s %s %s" % (work_dir + "/ea%d.bin" %
                                              (oidx * 10 + ea_no), path, ea))
    if req:
        debugfs_request(work_dir, image_name, req, True)
    if not wanted and not deleted_any:
        return raw, False
    e2fsck_check(work_dir, image_name)
    # pass 4 (read-only): verify patched contents byte-for-byte,
    # and deleted files are really gone.
    req = ["dump %s %s/out%d.bin" % (w[1], work_dir, w[0])
           for w in wanted]
    debugfs_request(work_dir, image_name, req, False)
    for oidx, path, new_data, _m, _u, _g, _e, _v, _w in wanted:
        with open(os.path.join(work_dir, "out%d.bin" % oidx),
                  "rb") as handle:
            if handle.read() != new_data:
                raise FixError("verify failed for %s" % path)
    for oidx in deletes:
        path = ops[oidx][0]
        parent = path.rsplit("/", 1)[0] or "/"
        base = path.rsplit("/", 1)[-1]
        ls_out = debugfs_request(work_dir, image_name, ["ls " + parent],
                                 False)
        if re.search(r"\b%s\b" % re.escape(base), ls_out):
            raise FixError("verify failed (still present): %s" % path)
    with open(img_path, "rb") as handle:
        return handle.read(), True


def make_transfer_list(raw: bytes) -> bytes:
    """Full-`new`-coverage transfer list for a raw image.

    Total comes from the FILE size, not s_blocks_count: AOSP images
    are padded past the filesystem end and the stock list covers the
    padding too (we reproduce that 1:1).
    """
    log_bs = struct.unpack("<I", raw[1024 + 24:1024 + 28])[0]
    bs = 1024 << log_bs
    total, rest = divmod(len(raw), bs)
    if rest:
        raise FixError("image size is not a whole number of blocks")
    lines = ["4", str(total), "0", "0"]
    pos = 0
    while pos < total:
        nxt = min(pos + 1024, total)
        lines.append("new 2,%d,%d" % (pos, nxt))
        pos = nxt
    return ("\n".join(lines) + "\n").encode()


def require_brotli() -> ModuleType:
    try:
        import brotli  # type: ignore[import]
    except ImportError:
        raise FixError("python module 'brotli' is required for the vendor "
                       "fix (pip install brotli)")
    return brotli
