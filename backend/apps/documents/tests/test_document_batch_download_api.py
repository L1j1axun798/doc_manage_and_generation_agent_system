from io import BytesIO
from zipfile import ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditLog
from apps.documents.models import Document
from apps.documents.services import BATCH_DOWNLOAD_MAX_BYTES
from apps.folders.models import Folder
from apps.projects.models import Project, ProjectMember

User = get_user_model()


def make_user(username: str, role: str):
    return User.objects.create_user(
        username=username,
        password="Password123!",
        real_name=username,
        role=role,
    )


def upload_file(name: str, content: bytes):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def create_document(client, *, folder: Folder, title: str, filename: str, content: bytes):
    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "title": title,
            "access_level": Document.AccessLevel.INTERNAL,
            "file": upload_file(filename, content),
        },
    )
    assert response.status_code == 201
    return response.json()


def response_body(response) -> bytes:
    body = b"".join(response.streaming_content)
    response.close()
    return body


@pytest.mark.django_db
def test_batch_download_returns_zip_and_deduplicates_filenames(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    client.force_login(admin)
    first = create_document(
        client,
        folder=folder,
        title="A",
        filename="report.pdf",
        content=b"one",
    )
    second = create_document(
        client,
        folder=folder,
        title="B",
        filename="report.pdf",
        content=b"two",
    )

    response = client.post(
        "/api/v1/documents/batch-download/",
        {"document_ids": [first["id"], second["id"]]},
        content_type="application/json",
    )

    assert response.status_code == 200
    with ZipFile(BytesIO(response_body(response))) as archive:
        names = sorted(archive.namelist())
        assert names == ["report (2).pdf", "report.pdf"]
        assert archive.read("report.pdf") == b"one"
        assert archive.read("report (2).pdf") == b"two"
    assert AuditLog.objects.filter(action="document.batch_download", result="success").exists()


@pytest.mark.django_db
def test_batch_download_rejects_any_unauthorized_document(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    visible_project = Project.objects.create(name="可见项目", code="P001", created_by=admin)
    hidden_project = Project.objects.create(name="隐藏项目", code="P002", created_by=admin)
    visible_folder = Folder.objects.create(project=visible_project, name="资料", created_by=admin)
    hidden_folder = Folder.objects.create(project=hidden_project, name="资料", created_by=admin)
    ProjectMember.objects.create(project=visible_project, user=operator)
    client.force_login(admin)
    visible = create_document(
        client,
        folder=visible_folder,
        title="A",
        filename="a.pdf",
        content=b"a",
    )
    hidden = create_document(
        client,
        folder=hidden_folder,
        title="B",
        filename="b.pdf",
        content=b"b",
    )
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/batch-download/",
        {"document_ids": [visible["id"], hidden["id"]]},
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_batch_download_rejects_over_20_documents(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    client.force_login(admin)

    response = client.post(
        "/api/v1/documents/batch-download/",
        {"document_ids": list(range(1, 22))},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_batch_download_rejects_total_size_over_limit(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder, title="A", filename="a.pdf", content=b"a")
    version = Document.objects.get(pk=document["id"]).current_version
    assert version is not None
    version.file_size = BATCH_DOWNLOAD_MAX_BYTES + 1
    version.save(update_fields=["file_size"])

    response = client.post(
        "/api/v1/documents/batch-download/",
        {"document_ids": [document["id"]]},
        content_type="application/json",
    )

    assert response.status_code == 413
