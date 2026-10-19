"""Fetch the versioned CC-BY-4.0 DataHub release; never execute its notebooks."""
from __future__ import annotations

import hashlib
import io
import json
import struct
import time
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECORD_URL = "https://zenodo.org/api/records/11003967"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "LSD-visual-severity-research/1.0"}),
        timeout=90,
    )


class RemoteArchive(io.RawIOBase):
    """Seekable public ZIP index using verified HTTP Range responses."""

    def __init__(self, url: str, length: int):
        self.url, self.length, self.position = url, length, 0

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else (self.position if whence == 1 else self.length) + offset
        return self.position

    def read(self, size=-1):
        end = self.length if size < 0 else min(self.length, self.position + size)
        if self.position >= end:
            return b""
        data = read_range(self.url, self.position, end - 1)
        self.position = end
        return data


def read_range(url: str, start: int, end: int) -> bytes:
    request = urllib.request.Request(url, headers={
        "User-Agent": "LSD-visual-severity-research/1.0", "Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(request, timeout=120) as response:
        expected = f"bytes {start}-{end}/"
        if response.status != 206 or not response.headers.get("Content-Range", "").startswith(expected):
            raise RuntimeError("Server did not honor requested archive range.")
        data = response.read()
    if len(data) != end - start + 1:
        raise RuntimeError("Incomplete archive range.")
    return data


def selective_download(raw: Path, record: dict, entry: dict) -> None:
    url = entry["links"]["self"]
    remote = RemoteArchive(url, entry["size"])
    with zipfile.ZipFile(remote) as source:
        entries = [item for item in source.infolist() if "__MACOSX" not in item.filename]
    (raw / "outer_archive_listing.json").write_text(
        json.dumps([item.filename for item in entries], indent=2), encoding="utf-8")
    wanted = [item for item in entries if item.filename.endswith("lumpy_unbalanced.zip")]
    if len(wanted) != 1:
        raise RuntimeError("Expected exactly one unbalanced archive.")
    item = wanted[0]
    print(f"Selected {item.filename}: {item.compress_size / 1e6:.1f} MB to transfer", flush=True)
    header = read_range(url, item.header_offset, item.header_offset + 29)
    values = struct.unpack("<4s5H3I2H", header)
    if values[0] != b"PK\x03\x04":
        raise RuntimeError("Invalid local ZIP header.")
    offset = item.header_offset + 30 + values[-2] + values[-1]
    target = raw / "lumpy_unbalanced.zip"
    chunks = raw / "ranges"
    chunks.mkdir(exist_ok=True)
    chunk_size = 4 * 1024 * 1024
    pieces = [(i, start, min(start + chunk_size, item.compress_size) - 1)
              for i, start in enumerate(range(0, item.compress_size, chunk_size))]

    def get_piece(piece):
        index, start, end = piece
        path = chunks / f"unbalanced_{index:03d}.part"
        if path.exists() and path.stat().st_size == end - start + 1:
            return path
        for attempt in range(3):
            try:
                path.write_bytes(read_range(url, offset + start, offset + end))
                print(f"Data range {index + 1}/{len(pieces)} complete", flush=True)
                return path
            except Exception:
                if attempt == 2:
                    raise
        raise AssertionError("unreachable")

    if not target.exists():
        with ThreadPoolExecutor(max_workers=8) as pool:
            paths = list(pool.map(get_piece, pieces))
        decoder = zlib.decompressobj(-15) if item.compress_type == zipfile.ZIP_DEFLATED else None
        if item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise RuntimeError("Unsupported outer member compression.")
        partial = target.with_suffix(".zip.part")
        crc, size = 0, 0
        with partial.open("wb") as handle:
            for path in paths:
                with path.open("rb") as piece:
                    while block := piece.read(1024 * 1024):
                        output = decoder.decompress(block) if decoder else block
                        handle.write(output)
                        crc = zlib.crc32(output, crc)
                        size += len(output)
            if decoder:
                output = decoder.flush()
                handle.write(output)
                crc = zlib.crc32(output, crc)
                size += len(output)
        if size != item.file_size or crc != item.CRC:
            raise RuntimeError("Unbalanced archive member CRC/size mismatch.")
        partial.replace(target)
    crc, size = 0, 0
    with target.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            crc = zlib.crc32(block, crc)
            size += len(block)
    if crc != item.CRC or size != item.file_size:
        raise RuntimeError("Cached unbalanced archive member CRC/size mismatch.")
    with zipfile.ZipFile(target) as inner:
        bad = inner.testzip()
        if bad:
            raise RuntimeError(f"Corrupt inner image member: {bad}")
        names = inner.namelist()
        (raw / "inner_archive_listing.json").write_text(json.dumps(names, indent=2), encoding="utf-8")
        print("Unbalanced entries:", len(names), "examples:", json.dumps(names[:20]), flush=True)
    metadata = record["metadata"]
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    provenance = {"record": "https://zenodo.org/records/11003967", "doi": metadata["doi"],
                  "license": metadata["license"]["id"], "creators": metadata["creators"],
                  "outer_publisher_md5": entry["checksum"], "outer_checksum_verified": False,
                  "retrieval": "HTTP ranges of selected member; complete outer archive was not downloaded",
                  "selected_member": item.filename, "member_crc32": f"{item.CRC:08x}",
                  "member_crc32_verified": True, "inner_member_crcs_verified": True,
                  "selected_sha256": sha256(target), "selected_bytes": target.stat().st_size}
    (artifacts / "source_provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    # The notebooks are source evidence only. Never import or execute them.
    for info in entries:
        if info.filename.endswith(("lumpy_multi_DL_imbal.ipynb", "lumpy_multi_ML_imbal.ipynb")):
            local = raw / Path(info.filename).name
            if not local.exists():
                with zipfile.ZipFile(RemoteArchive(url, entry["size"])) as source:
                    local.write_bytes(source.read(info.filename))
    print("Selected dataset verified and source provenance recorded.", flush=True)


def main() -> None:
    raw = ROOT / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    with fetch(RECORD_URL) as response:
        record = json.load(response)
    (raw / "zenodo_record.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    metadata = record["metadata"]
    if metadata.get("access_right") != "open" or metadata.get("license", {}).get("id") != "cc-by-4.0":
        raise RuntimeError("Unexpected access/license metadata; review the release before downloading.")
    entry = next(item for item in record["files"] if item["key"] == "LumpySkinDisease_DataHub.zip")
    import sys
    if "--full-archive" not in sys.argv:
        selective_download(raw, record, entry)
        return
    archive = raw / entry["key"]
    expected = entry["checksum"].removeprefix("md5:")
    valid = False
    if archive.exists():
        with archive.open("rb") as handle:
            valid = hashlib.file_digest(handle, "md5").hexdigest() == expected
    if not valid:
        partial = archive.with_suffix(".zip.part")
        received = 0
        last_log = time.monotonic()
        digest = hashlib.md5()
        with fetch(entry["links"]["self"]) as response, partial.open("wb") as handle:
            while chunk := response.read(4 * 1024 * 1024):
                handle.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if time.monotonic() - last_log > 10:
                    print(f"Download {received / 1e6:.1f}/{entry['size'] / 1e6:.1f} MB", flush=True)
                    last_log = time.monotonic()
        if received != entry["size"] or digest.hexdigest() != expected:
            raise RuntimeError("Dataset size/checksum mismatch; partial file retained for inspection.")
        partial.replace(archive)
    print(f"Verified archive: {archive.name}, MD5 {expected}", flush=True)
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        print("Archive files:", json.dumps(names[:40]), flush=True)
        for name in names:
            if "__MACOSX" in name:
                continue
            if name.endswith("lumpy_unbalanced.zip"):
                target = raw / "lumpy_unbalanced.zip"
                if not target.exists():
                    with source.open(name) as src, target.open("wb") as dst:
                        while chunk := src.read(4 * 1024 * 1024):
                            dst.write(chunk)
                with zipfile.ZipFile(target) as inner:
                    inner_names = inner.namelist()
                    (raw / "inner_archive_listing.json").write_text(json.dumps(inner_names, indent=2), encoding="utf-8")
                    print("Unbalanced archive:", len(inner_names), "entries; examples:", json.dumps(inner_names[:25]), flush=True)
            elif "/code/" in name and name.endswith(".ipynb"):
                target = raw / Path(name).name
                if not target.exists():
                    target.write_bytes(source.read(name))
    provenance = {
        "record": "https://zenodo.org/records/11003967",
        "doi": metadata["doi"], "license": metadata["license"]["id"],
        "creators": metadata["creators"], "archive_md5": expected,
        "archive_sha256": sha256(archive), "archive_bytes": archive.stat().st_size,
        "selected_member": "lumpy_unbalanced.zip",
        "restriction": "Research visual severity only; no clinical grading inference.",
    }
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "source_provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print("Source metadata and unbalanced archive ready.", flush=True)


if __name__ == "__main__":
    main()
