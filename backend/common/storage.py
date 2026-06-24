import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from django.conf import settings


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    sha256: str
    size: int


class LocalDocumentStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or settings.FILE_STORAGE_ROOT)

    def save_uploaded_file(self, uploaded_file: object) -> StoredFile:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary_path = self.root / ".tmp" / f"{uuid4().hex}.upload"
        temporary_path.parent.mkdir(parents=True, exist_ok=True)

        sha256 = hashlib.sha256()
        size = 0
        try:
            with temporary_path.open("wb") as target:
                for chunk in uploaded_file.chunks():  # type: ignore[attr-defined]
                    size += len(chunk)
                    sha256.update(chunk)
                    target.write(chunk)

            digest = sha256.hexdigest()
            relative_path = self._build_relative_path(digest)
            final_path = self.resolve(relative_path)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary_path, final_path)
            return StoredFile(relative_path=relative_path, sha256=digest, size=size)
        except Exception:
            self.delete_path(temporary_path)
            raise

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        root = self.root.resolve()
        if root != path and root not in path.parents:
            raise ValueError("文件路径越界")
        return path

    def exists(self, relative_path: str) -> bool:
        return self.resolve(relative_path).is_file()

    def delete(self, relative_path: str) -> None:
        self.delete_path(self.resolve(relative_path))

    def delete_path(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except FileNotFoundError:
            return

    def _build_relative_path(self, digest: str) -> str:
        return str(Path(digest[:2]) / digest[2:4] / f"{uuid4().hex}.bin")
