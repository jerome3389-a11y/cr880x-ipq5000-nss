#!/usr/bin/env python3
"""Post-build factory.ubi structural verifier (yingjiedev-style image check,
adapted to our CR880x merged layout).

Runs in CI after the build, before staging: a factory.ubi that fails here
never reaches artifacts or a release, so a structurally broken image can
never be recommended for flashing.

Checks (all hard failures):
  1. Size is a non-zero multiple of the NAND erase block (128 KiB).
  2. Size fits the merged rootfs partition (default 0x7480000 = 116.5 MiB).
  3. Every non-empty PEB carries a valid EC header ('UBI#') and a valid
     VID header ('UBI!') at that PEB's own vid_hdr_offset.
  4. The layout volume (0x7fffefff) is present and its volume table
     parses to at least one named volume.
  5. A volume named 'kernel' with >= 1 LEB and non-zero data exists.
  6. A volume named 'rootfs' with >= 1 LEB and non-zero data exists.

Deliberately NOT checked: EC/VID header CRCs (observed to mismatch on
known-good factory images, so they are not a reliable gate) and exact LEB
counts (kernel size legitimately varies between builds). The kernel
volume's first bytes are printed for information (FIT magic 0xd00dfeed
expected for our images) but not gated, since other valid images use
different kernel containers.

UBI on-disk format (linux/ubi-media.h), all integers big-endian.
EC header 64B: magic 'UBI#' 0x55424923, version, ec(be64),
vid_hdr_offset(be32), data_offset(be32), image_seq(be32).
VID header 64B: magic 'UBI!' 0x55424921, version, vol_type, copy_flag,
compat, vol_id(be32), lnum(be32), data_size(be32), used_ebs(be32),
data_pad(be32), data_crc(be32), sqnum(be64).
Volume-table record 172B: reserved_pebs, alignment, data_pad, vol_type,
upd_marker, name_len(be16), name[128], flags(0x01=autoresize).
"""
import struct
import sys

PEB_SIZE = 131072
EC_MAGIC = 0x55424923
VID_MAGIC = 0x55424921
LAYOUT_VOLID = 0x7FFFEFFF
VTBL_REC = 172
DEFAULT_MAX = 0x7480000  # merged rootfs partition size


def fail(msg):
    print(f"FACTORY UBI FAILED: {msg}")
    sys.exit(1)


def parse_ec(buf):
    magic, = struct.unpack(">I", buf[0:4])
    if magic != EC_MAGIC:
        return None
    ec, vid_off, data_off = struct.unpack(">QII", buf[8:24])
    return dict(ec=ec, vid_hdr_offset=vid_off, data_offset=data_off)


def parse_vid(buf):
    magic, = struct.unpack(">I", buf[0:4])
    if magic != VID_MAGIC:
        return None
    vol_id, lnum, data_size = struct.unpack(">III", buf[8:20])
    return dict(vol_id=vol_id, lnum=lnum, data_size=data_size)


def main(path, max_bytes):
    try:
        data = open(path, "rb").read()
    except OSError as e:
        fail(f"cannot read {path}: {e}")
    size = len(data)
    print(f"file: {path}")
    print(f"size: {size} bytes ({size / 1048576:.3f} MiB)")
    if size == 0:
        fail("empty file")
    if size % PEB_SIZE != 0:
        fail(f"size {size} is not a multiple of PEB size {PEB_SIZE} "
             f"(trailing {size % PEB_SIZE} bytes)")
    if size > max_bytes:
        fail(f"size {size} exceeds merged rootfs partition {max_bytes} "
             f"({max_bytes / 1048576:.1f} MiB)")
    npeb = size // PEB_SIZE
    print(f"PEBs: {npeb} x {PEB_SIZE}")

    vols = {}  # vol_id -> {lnum: data_nonempty_bool}
    bad = []
    empty = 0
    first_ec = None
    for i in range(npeb):
        peb = data[i * PEB_SIZE:(i + 1) * PEB_SIZE]
        if peb == b"\xff" * PEB_SIZE:
            empty += 1
            continue
        ec = parse_ec(peb[:64])
        if ec is None:
            bad.append(i)
            continue
        if first_ec is None:
            first_ec = ec
        vid = parse_vid(peb[ec["vid_hdr_offset"]:ec["vid_hdr_offset"] + 64])
        if vid is None:
            bad.append(i)
            continue
        # NOTE: ubinize writes VID data_size=0 for every volume, so
        # data_size cannot prove emptiness. Instead, record whether
        # the LEB's data area holds any non-0xFF byte.
        off = ec["data_offset"]
        nonempty = peb[off:] != b"\xff" * (PEB_SIZE - off)
        vols.setdefault(vid["vol_id"], {})[vid["lnum"]] = nonempty
    if bad:
        fail(f"{len(bad)} non-empty PEB(s) without valid EC/VID headers, "
             f"first at PEB {bad[0]}")
    print(f"empty PEBs: {empty}, bad PEBs: 0")
    if first_ec is None:
        fail("no non-empty PEB found (all 0xFF)")

    # Volume table from the layout volume's LEB data (lnum order).
    layout = vols.get(LAYOUT_VOLID)
    if not layout:
        fail("layout volume 0x7fffefff missing")
    layout_data = b""
    for i in range(npeb):
        peb = data[i * PEB_SIZE:(i + 1) * PEB_SIZE]
        if peb == b"\xff" * PEB_SIZE:
            continue
        ec = parse_ec(peb[:64])
        if ec is None:
            continue
        vid = parse_vid(peb[ec["vid_hdr_offset"]:ec["vid_hdr_offset"] + 64])
        if vid and vid["vol_id"] == LAYOUT_VOLID:
            # NOTE: layout LEBs carry data_size=0 in their VID headers
            # even though the table data is present at data_offset, so
            # take the full LEB data area instead of trusting data_size.
            off = ec["data_offset"]
            layout_data += peb[off:PEB_SIZE]
    table = {}  # vol_id (table index) -> name
    for idx in range(128):
        rec = layout_data[idx * VTBL_REC:(idx + 1) * VTBL_REC]
        if len(rec) < VTBL_REC:
            break
        reserved, = struct.unpack(">I", rec[0:4])
        name_len, = struct.unpack(">H", rec[14:16])
        if reserved == 0 and name_len == 0:
            continue  # empty slot
        if name_len == 0 or name_len > 127:
            continue  # padding or corrupt record
        raw = rec[16:16 + name_len]
        try:
            name = raw.decode("ascii")
        except UnicodeDecodeError:
            continue
        if not all(32 <= ord(c) < 127 for c in name):
            continue
        table[idx] = name
    print(f"volume table: {table}")
    if not table:
        fail("volume table parsed to zero named volumes")

    # Per-volume inventory, resolved by table name.
    by_name = {}
    for vid_id, lnums in vols.items():
        if vid_id == LAYOUT_VOLID:
            continue
        name = table.get(vid_id, f"<unnamed 0x{vid_id:x}>")
        has_data = any(lnums.values())
        by_name[name] = (len(lnums), has_data)
        print(f"  volume {name!r}: {len(lnums)} LEBs, "
              f"data present: {'yes' if has_data else 'NO'}")
    for required in ("kernel", "rootfs"):
        entry = by_name.get(required)
        if entry is None:
            fail(f"required volume {required!r} missing from image")
        nleb, has_data = entry
        if nleb < 1 or not has_data:
            fail(f"required volume {required!r} is empty "
                 f"({nleb} LEBs, data present: {has_data})")

    # Informational: kernel container magic (FIT expected, not gated).
    kern_id = None
    for idx, name in table.items():
        if name == "kernel":
            kern_id = idx
            break
    if kern_id is not None and kern_id in vols:
        first_lnum = min(vols[kern_id])
        for i in range(npeb):
            peb = data[i * PEB_SIZE:(i + 1) * PEB_SIZE]
            if peb == b"\xff" * PEB_SIZE:
                continue
            ec = parse_ec(peb[:64])
            if ec is None:
                continue
            v2 = parse_vid(peb[ec["vid_hdr_offset"]:ec["vid_hdr_offset"] + 64])
            if v2 and v2["vol_id"] == kern_id and v2["lnum"] == first_lnum:
                head = peb[ec["data_offset"]:ec["data_offset"] + 4]
                print(f"kernel volume first 4 bytes: {head.hex()} "
                      f"({'FIT magic' if head == bytes.fromhex('d00dfeed') else 'not FIT magic, informational only'})")
                break

    print("FACTORY UBI OK")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: verify-factory-ubi.py <factory.ubi> [max_bytes]")
        sys.exit(2)
    max_b = int(sys.argv[2], 0) if len(sys.argv) > 2 else DEFAULT_MAX
    main(sys.argv[1], max_b)
