"""Amlogic USB-burn package (AIP) support: parse + rebuild, stdlib only.

Format (reverse-engineered by the ampack project, reimplemented here so
the patcher stays dependency-free):

    header (64 bytes, little-endian):
        crc32   u32  reflected CRC32 of bytes [4:], init 0xFFFFFFFF,
                     NO final xor (i.e. zlib.crc32(data) ^ 0xFFFFFFFF)
        version u32  1 (v1, 32-byte type fields) or 2 (v2, 256-byte)
        magic   u32  0x27B51956
        size    u64  total file size
        align   u32  data alignment (4, LOS uses 4, stock uses 8)
        count   u32  number of item infos
        reserve 36 bytes, zero
    item info (128 bytes v1 / 576 bytes v2):
        id, file_type, coff_in_item (u32,u32,u64), off_in_image (u64),
        size (u64), main_type[LEN], sub_type[LEN] (C strings),
        verify (u32), is_backup (u16), backup_id (u16), reserve 24 bytes
    body: item data blobs at off_in_image, zero-padded to align
    (except VERIFY items, which the packer appends tightly with no
    padding - proven by unaligned VERIFY offsets in stock packages).

Item identity is (sub, main), e.g. ("dtbo", "PARTITION") or
("DDR", "USB"). PARTITION items may be followed by a 48-byte VERIFY
item ("sha1sum <40 hex>"); LOS packages carry none (verify == 0
everywhere). Identical data may share one offset (backup); the writer
trusts the parsed flags verbatim instead of re-deriving them (the
vendor packer shares offsets even for differing data, so byte
equality would reproduce it wrongly).

The writer preserves the input item ORDER (not ampack's sorted
order), the input version/align/flags, and recomputes
offsets, size and CRC. Parsing + rebuilding an untouched image is
byte-identical (verified live on LOS v1 packages).
"""

import struct
import zlib
from dataclasses import dataclass, field

from .errors import FixError

MAGIC = 0x27B51956
HEAD_SIZE = 64
_V1_TYPE_LEN = 32
_V2_TYPE_LEN = 256
_V1_INFO_SIZE = 4 + 4 + 8 + 8 + 8 + _V1_TYPE_LEN + _V1_TYPE_LEN + 4 + 2 + 2 + 24
_V2_INFO_SIZE = 4 + 4 + 8 + 8 + 8 + _V2_TYPE_LEN + _V2_TYPE_LEN + 4 + 2 + 2 + 24
_SPARSE_MAGIC = b":\xff&\xed"
FILE_TYPE_SPARSE = 254
FILE_TYPE_GENERIC = 0


@dataclass
class AmlItem:
    """One package item: names, flags (copied verbatim) and data."""

    sub: str
    main: str
    file_type: int
    verify: int
    is_backup: int
    backup_id: int
    coff_in_item: int
    data: bytes = field(repr=False)


@dataclass
class AmlImage:
    """Parsed burn package: version/align preserved, order preserved."""

    version: int
    align: int
    items: list[AmlItem]


def _info_layout(version: int) -> tuple[int, int]:
    if version == 1:
        return _V1_TYPE_LEN, _V1_INFO_SIZE
    if version == 2:
        return _V2_TYPE_LEN, _V2_INFO_SIZE
    raise FixError("unsupported Amlogic image version: %d" % version)


def _cstr(raw: bytes) -> str:
    try:
        return raw.split(b"\x00")[0].decode("ascii")
    except UnicodeDecodeError:
        raise FixError("corrupt Amlogic image (bad item name)")


def package_crc(data_without_crc: bytes) -> int:
    """Header CRC: reflected CRC32, init 0xFFFFFFFF, no final xor."""
    return zlib.crc32(data_without_crc) ^ 0xFFFFFFFF


def is_package(data: bytes) -> bool:
    """True if data starts with the Amlogic burn-package magic."""
    return len(data) >= 12 and struct.unpack("<I", data[8:12])[0] == MAGIC


def parse(data: bytes) -> AmlImage:
    """Parse a burn package; raises FixError if magic/CRC is bad."""
    if len(data) < HEAD_SIZE:
        raise FixError("not an Amlogic burn package (too small)")
    crc, version, magic, size, align, count = struct.unpack("<IIIQII",
                                                            data[:28])
    if magic != MAGIC:
        raise FixError("not an Amlogic burn package (bad magic %08x)"
                       % magic)
    if size != len(data):
        raise FixError("Amlogic image size mismatch (header %d != file %d)"
                       % (size, len(data)))
    if package_crc(data[4:]) != crc:
        raise FixError("Amlogic image CRC mismatch (package is corrupt)")
    type_len, info_size = _info_layout(version)
    items = []
    seen = set()
    for i in range(count):
        off = HEAD_SIZE + i * info_size
        (iid, ftype, coff, ioff, isize) = struct.unpack(
            "<IIQQQ", data[off:off + 32])
        if iid != i:
            raise FixError("Amlogic image item %d out of order" % i)
        main = _cstr(data[off + 32:off + 32 + type_len])
        sub = _cstr(data[off + 32 + type_len:off + 32 + 2 * type_len])
        verify, is_backup, backup_id = struct.unpack(
            "<IHH", data[off + 32 + 2 * type_len:off + 40 + 2 * type_len])
        if (sub, main) in seen:
            raise FixError("duplicate Amlogic image item %s.%s" % (sub, main))
        seen.add((sub, main))
        items.append(AmlItem(sub, main, ftype, verify, is_backup,
                             backup_id, coff, data[ioff:ioff + isize]))
    return AmlImage(version, align, items)


def find(image: AmlImage, sub: str, main: str) -> AmlItem | None:
    """Find an item by (sub, main); None if absent."""
    for item in image.items:
        if item.sub == sub and item.main == main:
            return item
    return None


def _align_up(n: int, align: int) -> int:
    return (n + align - 1) // align * align


def build(image: AmlImage) -> bytes:
    """Rebuild a package: original order/version/align/flags preserved.

    Offsets, total size and CRC are recomputed. Backup items reuse
    their source's offset (flags trusted verbatim); fresh items are
    laid out sequentially, zero-padded to align - except VERIFY items,
    which are appended tightly with no padding (packer rule, proven
    by unaligned VERIFY offsets in stock images).
    """
    type_len, info_size = _info_layout(image.version)
    if image.align < 4 or image.align % 4:
        raise FixError("bad Amlogic image alignment: %d" % image.align)
    offsets: list[int] = []
    body = bytearray()
    body_off = _align_up(HEAD_SIZE + info_size * len(image.items),
                         image.align)
    for idx, item in enumerate(image.items):
        if item.is_backup:
            if item.backup_id >= idx:
                raise FixError("corrupt backup reference in %s.%s"
                               % (item.sub, item.main))
            offsets.append(offsets[item.backup_id])
            continue
        pos = body_off + len(body)
        if item.main != "VERIFY":
            pos = _align_up(pos, image.align)
            body.extend(b"\x00" * (pos - (body_off + len(body))))
        body.extend(item.data)
        offsets.append(pos)
    # serialize
    head_infos = bytearray(HEAD_SIZE + info_size * len(image.items))
    struct.pack_into("<IIIQII", head_infos, 0, 0, image.version, MAGIC,
                     body_off + len(body), image.align, len(image.items))
    for idx, item in enumerate(image.items):
        off = HEAD_SIZE + idx * info_size
        ftype = (FILE_TYPE_SPARSE
                 if item.data.startswith(_SPARSE_MAGIC)
                 else FILE_TYPE_GENERIC)
        struct.pack_into("<IIQQQ", head_infos, off, idx, ftype,
                         item.coff_in_item, offsets[idx], len(item.data))
        main_b = item.main.encode("ascii")
        sub_b = item.sub.encode("ascii")
        if len(main_b) >= type_len or len(sub_b) >= type_len:
            raise FixError("Amlogic item name too long: %s.%s"
                           % (item.sub, item.main))
        head_infos[off + 32:off + 32 + len(main_b)] = main_b
        head_infos[off + 32 + type_len:off + 32 + type_len + len(sub_b)] = sub_b
        struct.pack_into("<IHH", head_infos, off + 32 + 2 * type_len,
                         item.verify, item.is_backup, item.backup_id)
    out = bytes(head_infos) + bytes(body)
    struct.pack_into("<I", head_infos, 0, package_crc(out[4:]))
    return bytes(head_infos) + bytes(body)
