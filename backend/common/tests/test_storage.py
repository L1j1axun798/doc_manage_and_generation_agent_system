from pathlib import PurePosixPath

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from common.storage import LocalDocumentStorage


def test_storage_paths_are_posix_and_resolve_legacy_windows_separators(tmp_path):
    storage = LocalDocumentStorage(root=tmp_path)
    stored = storage.save_uploaded_file(SimpleUploadedFile("report.pdf", b"content"))

    assert "\\" not in stored.relative_path
    assert PurePosixPath(stored.relative_path).parts[:2] == (stored.sha256[:2], stored.sha256[2:4])

    legacy_path = stored.relative_path.replace("/", "\\")
    assert storage.exists(legacy_path)
    assert storage.resolve(legacy_path) == storage.resolve(stored.relative_path)


@pytest.mark.parametrize(
    "unsafe_path",
    ["../outside.bin", "..\\outside.bin", "/tmp/file", "C:\\file.bin"],
)
def test_storage_rejects_unsafe_paths_after_separator_normalization(tmp_path, unsafe_path):
    storage = LocalDocumentStorage(root=tmp_path)

    with pytest.raises(ValueError, match="文件路径越界"):
        storage.resolve(unsafe_path)
