from __future__ import annotations

import argparse
import tarfile
from pathlib import Path, PurePosixPath


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a UTF-8-safe deployment archive."
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve(strict=True)
    entries = [
        line.strip()
        for line in args.manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not entries:
        raise ValueError("Release manifest is empty")

    with tarfile.open(args.output, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        for entry in entries:
            archive_path = PurePosixPath(entry)
            if archive_path.is_absolute() or ".." in archive_path.parts:
                raise ValueError(f"Unsafe manifest path: {entry}")
            source = root.joinpath(*archive_path.parts)
            resolved_source = source.resolve(strict=True)
            if not resolved_source.is_relative_to(root):
                raise ValueError(f"Manifest path leaves the repository: {entry}")
            if not source.is_file():
                raise ValueError(f"Manifest entry is not a file: {entry}")
            archive.add(source, arcname=archive_path.as_posix(), recursive=False)


if __name__ == "__main__":
    main()
