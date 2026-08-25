"""Normalize a source distribution into a byte-reproducible tar.gz container."""

from __future__ import annotations

import argparse
import copy
import gzip
import io
import os
import tarfile
from pathlib import Path


def normalize_sdist(source: Path, destination: Path, *, epoch: int) -> None:
    if epoch < 0:
        raise ValueError("epoch must be >= 0")
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with (
        tarfile.open(source, mode="r:gz") as archive,
        destination.open("wb") as raw,
        gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            compresslevel=9,
            mtime=epoch,
        ) as compressed,
        tarfile.open(
            fileobj=compressed,
            mode="w",
            format=tarfile.PAX_FORMAT,
        ) as normalized,
    ):
        members = sorted(archive.getmembers(), key=lambda member: member.name)
        for member in members:
            info = copy.copy(member)
            info.mtime = epoch
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.pax_headers = {}
            payload: io.BytesIO | None = None
            if member.isfile():
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise RuntimeError(f"cannot read sdist member: {member.name}")
                data = extracted.read()
                info.size = len(data)
                payload = io.BytesIO(data)
            normalized.addfile(info, payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--epoch",
        type=int,
        default=int(os.environ.get("SOURCE_DATE_EPOCH", "0")),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    normalize_sdist(args.source, args.destination, epoch=args.epoch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
