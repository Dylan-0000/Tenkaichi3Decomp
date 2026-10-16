#!/usr/bin/env python3
"""Unpacks the Tenkaichi 4 mod's disc (TeamBT4) into loose folders for the PC build, in BT4 mode.

    port/tools/extract_disc_bt4.py <disc.iso | folder with the disc's files> [out_dir]    (out_dir default: gamedata/)

The mod's archives (DATA/PZS4US0..3.AFS) are not AFS: no header, the entries one after the other, each padded to
2048-byte sectors; the sizes (in sectors, a u16 per entry) are in BIN/DBZ4.BIN, one section per archive:
    header  u32 0, u32 L, u32 N, u32 N, then the archive's name; the table of N u16 ends at byte L of the section;
    the next section starts at the next multiple of 16.
Result: out_dir/pzs4us0/00000.bin ... pzs4us3/..., the loose disc files under out_dir/disc/ (the mod's SLUS_219.78 is
stored as disc/SLUS_216.78, the name the port reads), and out_dir/.bt4, which turns BT4 mode on (plat_mem.c).
Needs `7z` for a disc image. Nothing extracted may be committed or redistributed."""
import pathlib, shutil, struct, subprocess, sys

SECTOR = 2048

def read_tables(path):
    d = pathlib.Path(path).read_bytes()
    tables, pos = {}, 0
    while pos + 0x20 <= len(d):
        zero, length, n, n2 = struct.unpack_from("<4I", d, pos)
        if zero != 0 or n != n2 or n == 0 or length < 2 * n or pos + length > len(d):
            break
        name = d[pos + 0x10:pos + 0x20].split(b"\0")[0].decode("ascii", "replace").lower()
        tables[name] = list(struct.unpack_from(f"<{n}H", d, pos + length - 2 * n))
        pos += (length + 15) & ~15
    if not tables:
        raise SystemExit(f"{path}: no size tables found (is it the mod's BIN/DBZ4.BIN?)")
    return tables

def split_headerless(afs, table, out):
    out.mkdir(parents=True, exist_ok=True)
    total = afs.stat().st_size
    if sum(table) * SECTOR > total:
        raise SystemExit(f"{afs}: the table in DBZ4.BIN is larger than the file (wrong DBZ4.BIN for this archive?)")
    with open(afs, "rb") as f:
        for i, sectors in enumerate(table):
            (out / f"{i:05d}.bin").write_bytes(f.read(sectors * SECTOR))
    return len(table), total - sum(table) * SECTOR

def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "gamedata")
    disc = out / "disc"
    disc.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        for name in ("DATA", "BIN", "SLUS_219.78"):
            s, d = src / name, disc / name
            if not s.exists():
                raise SystemExit(f"{s}: not found")
            if s.is_dir():
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
    else:
        subprocess.run(["7z", "x", "-y", f"-o{disc}", str(src), "DATA", "BIN", "SLUS_219.78"], check=True,
                       stdout=subprocess.DEVNULL)
    tables = read_tables(disc / "BIN" / "DBZ4.BIN")
    for afs in sorted((disc / "DATA").glob("*.AFS")):
        table = tables.get(afs.name.lower())
        if table is None:
            print(f"{afs.name}: no table in DBZ4.BIN, left as it is")
            continue
        n, rest = split_headerless(afs, table, out / afs.stem.lower())
        print(f"{afs.name}: {n} files" + (f" ({rest} bytes after the last one not covered by the table)" if rest else ""))
        afs.unlink()  # the loose files replace it
    slus = disc / "SLUS_219.78"
    if slus.exists():
        slus.replace(disc / "SLUS_216.78")  # the name the port reads
    (out / ".bt4").write_text("BT4 mode: see port/src/plat_mem.c (Port_Bt4Mode)\n")
    print(f"done: {out} (BT4 mode on)")

main()
