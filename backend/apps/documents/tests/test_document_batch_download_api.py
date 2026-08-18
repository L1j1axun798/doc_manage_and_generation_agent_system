from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.access.models import DocumentGrant
from apps.audit.models import AuditLog
from apps.documents.archive_download_cancellation import (
    archive_download_is_canceled,
    clear_archive_download_cancel,
)
from apps.documents.models import Document
from apps.documents.services import (
    ARCHIVE_COPY_CHUNK_SIZE,
    BATCH_DOWNLOAD_MAX_BYTES,
    ArchiveDownloadCanceled,
    build_folder_download_zip,
)
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


def create_document(
    client,
    *,
    folder: Folder,
    title: str,
    filename: str,
    content: bytes,
    access_level: str | None = None,
):
    payload = {
        "folder": folder.id,
        "title": title,
        "file": upload_file(filename, content),
    }
    if access_level is not None:
        payload["access_level"] = access_level
    response = client.post(
        "/api/v1/documents/",
        payload,
    )
    assert response.status_code == 201
    return response.json()


def response_body(response) -> bytes:
    body = b"".join(response.streaming_content)
    response.close()
    return body


@pytest.mark.django_db
def test_archive_download_cancel_endpoint_records_user_scoped_cancel(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    client.force_login(admin)
    download_id = uuid4()

    response = client.post(
        "/api/v1/documents/archive-download-cancel/",
        {"download_id": str(download_id)},
        content_type="application/json",
    )

    assert response.status_code == 204
    assert archive_download_is_canceled(user_id=admin.pk, download_id=download_id)
    clear_archive_download_cancel(user_id=admin.pk, download_id=download_id)


@pytest.mark.django_db
def test_folder_download_stops_when_cooperative_cancel_was_requested(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    folder = Folder.objects.create(
        name="资料",
        code="DOWNLOAD-CANCEL-ROOT",
        is_system_root=True,
        created_by=admin,
    )
    client.force_login(admin)
    create_document(
        client,
        folder=folder,
        title="报告",
        filename="report.pdf",
        content=b"content",
    )
    download_id = uuid4()
    cancel_response = client.post(
        "/api/v1/documents/archive-download-cancel/",
        {"download_id": str(download_id)},
        content_type="application/json",
    )
    assert cancel_response.status_code == 204

    response = client.post(
        "/api/v1/documents/folder-download/",
        {"folder": folder.pk, "download_id": str(download_id)},
        content_type="application/json",
    )

    assert response.status_code == 409
    assert not archive_download_is_canceled(user_id=admin.pk, download_id=download_id)


@pytest.mark.django_db
def test_folder_download_checks_cancel_state_between_large_file_chunks(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    folder = Folder.objects.create(
        name="资料",
        code="DOWNLOAD-CHUNK-CANCEL-ROOT",
        is_system_root=True,
        created_by=admin,
    )
    client.force_login(admin)
    document_data = create_document(
        client,
        folder=folder,
        title="大文件",
        filename="large.pdf",
        content=b"x" * (ARCHIVE_COPY_CHUNK_SIZE * 2 + 1),
    )
    document = Document.objects.select_related("current_version").get(pk=document_data["id"])
    cancel_checks = 0

    def is_canceled():
        nonlocal cancel_checks
        cancel_checks += 1
        return cancel_checks >= 3

    with pytest.raises(ArchiveDownloadCanceled):
        build_folder_download_zip(
            actor=admin,
            root_folder=folder,
            folders=[folder],
            documents=[document],
            is_canceled=is_canceled,
        )

    assert cancel_checks == 3


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
    second_folder = Folder.objects.create(project=project, name="资料二", created_by=admin)
    second = create_document(
        client,
        folder=second_folder,
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
    operator = make_user("operator", User.Role.PROJECT_MANAGER)
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
def test_batch_download_accepts_legacy_windows_storage_paths(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    folder = Folder.objects.create(name="资料", created_by=admin)
    client.force_login(admin)
    document_data = create_document(
        client,
        folder=folder,
        title="报告",
        filename="report.pdf",
        content=b"content",
    )
    document = Document.objects.select_related("current_version").get(pk=document_data["id"])
    version = document.current_version
    assert version is not None
    version.storage_path = version.storage_path.replace("/", "\\")
    version.save(update_fields=["storage_path"])

    response = client.post(
        "/api/v1/documents/batch-download/",
        {"document_ids": [document.id]},
        content_type="application/json",
    )

    assert response.status_code == 200
    with ZipFile(BytesIO(response_body(response))) as archive:
        assert archive.read("report.pdf") == b"content"


@pytest.mark.django_db
def test_batch_download_rejects_document_without_download_grant(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator)
    client.force_login(admin)
    document = create_document(
        client,
        folder=folder,
        title="A",
        filename="a.pdf",
        content=b"a",
    )
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/batch-download/",
        {"document_ids": [document["id"]]},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert AuditLog.objects.filter(action="document.batch_download", result="denied").exists()


@pytest.mark.django_db
def test_batch_download_allows_document_with_download_grant(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    client.force_login(admin)
    document = create_document(
        client,
        folder=folder,
        title="A",
        filename="a.pdf",
        content=b"a",
    )
    DocumentGrant.objects.create(
        document_id=document["id"],
        user=operator,
        can_download=True,
        created_by=admin,
    )
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/batch-download/",
        {"document_ids": [document["id"]]},
        content_type="application/json",
    )

    assert response.status_code == 200
    with ZipFile(BytesIO(response_body(response))) as archive:
        assert archive.read("a.pdf") == b"a"


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


@pytest.mark.django_db
def test_folder_download_preserves_root_and_nested_folder_hierarchy(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    root = Folder.objects.create(
        name="资料根目录",
        code="DOWNLOAD-ROOT",
        is_system_root=True,
        created_by=admin,
    )
    child = Folder.objects.create(parent=root, name="子目录", created_by=admin)
    grandchild = Folder.objects.create(parent=child, name="孙目录", created_by=admin)
    client.force_login(admin)
    create_document(
        client,
        folder=root,
        title="根文件",
        filename="root.pdf",
        content=b"root",
    )
    create_document(
        client,
        folder=child,
        title="子文件",
        filename="report.pdf",
        content=b"child",
    )
    create_document(
        client,
        folder=grandchild,
        title="孙文件",
        filename="report.pdf",
        content=b"grandchild",
    )

    response = client.post(
        "/api/v1/documents/folder-download/",
        {"folder": root.id},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response["X-Archive-Document-Count"] == "3"
    assert "filename*=UTF-8''" in response["Content-Disposition"]
    with ZipFile(BytesIO(response_body(response))) as archive:
        assert sorted(archive.namelist()) == [
            "资料根目录/root.pdf",
            "资料根目录/子目录/report.pdf",
            "资料根目录/子目录/孙目录/report.pdf",
        ]
        assert archive.read("资料根目录/root.pdf") == b"root"
        assert archive.read("资料根目录/子目录/report.pdf") == b"child"
        assert archive.read("资料根目录/子目录/孙目录/report.pdf") == b"grandchild"
    assert AuditLog.objects.filter(
        action="document.folder_download",
        result="success",
    ).exists()


@pytest.mark.django_db
def test_folder_download_is_not_limited_by_legacy_20_file_batch_limit(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    root = Folder.objects.create(
        name="全部资料",
        code="DOWNLOAD-ROOT",
        is_system_root=True,
        created_by=admin,
    )
    client.force_login(admin)
    for index in range(21):
        create_document(
            client,
            folder=root,
            title=f"资料-{index}",
            filename=f"document-{index}.pdf",
            content=f"content-{index}".encode(),
        )

    response = client.post(
        "/api/v1/documents/folder-download/",
        {"folder": root.id},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response["X-Archive-Document-Count"] == "21"
    with ZipFile(BytesIO(response_body(response))) as archive:
        assert len(archive.namelist()) == 21


@pytest.mark.django_db
def test_folder_download_includes_public_documents_for_data_operator(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    root = Folder.objects.create(
        name="公共资料",
        code="DOWNLOAD-ROOT",
        is_system_root=True,
        created_by=admin,
    )
    first_folder = Folder.objects.create(parent=root, name="资料一", created_by=admin)
    second_folder = Folder.objects.create(parent=root, name="资料二", created_by=admin)
    client.force_login(admin)
    create_document(
        client,
        folder=first_folder,
        title="公开文件一",
        filename="first.pdf",
        content=b"first",
    )
    create_document(
        client,
        folder=second_folder,
        title="公开文件二",
        filename="second.pdf",
        content=b"second",
    )
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/folder-download/",
        {"folder": root.id},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response["X-Archive-Document-Count"] == "2"
    with ZipFile(BytesIO(response_body(response))) as archive:
        assert sorted(archive.namelist()) == [
            "公共资料/资料一/first.pdf",
            "公共资料/资料二/second.pdf",
        ]
        assert archive.read("公共资料/资料一/first.pdf") == b"first"
        assert archive.read("公共资料/资料二/second.pdf") == b"second"


@pytest.mark.django_db
def test_folder_download_includes_only_own_staff_documents_for_data_operator(
    client, tmp_path, settings
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    staff_root = Folder.objects.create(
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    own_folder = Folder.objects.create(parent=staff_root, name="operator", created_by=admin)
    other_folder = Folder.objects.create(parent=staff_root, name="other", created_by=admin)
    client.force_login(admin)
    create_document(
        client,
        folder=own_folder,
        title="本人资质",
        filename="staff.pdf",
        content=b"staff",
    )
    create_document(
        client,
        folder=other_folder,
        title="他人资质",
        filename="other-staff.pdf",
        content=b"other-staff",
    )
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/folder-download/",
        {"folder": staff_root.id},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response["X-Archive-Document-Count"] == "1"
    with ZipFile(BytesIO(response_body(response))) as archive:
        assert archive.namelist() == ["人员资质/operator/staff.pdf"]
        assert archive.read("人员资质/operator/staff.pdf") == b"staff"


@pytest.mark.django_db
def test_folder_download_rejects_folder_outside_user_scope(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(name="隐藏项目", code="P-HIDDEN", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/folder-download/",
        {"folder": folder.id},
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_folder_download_groups_equivalent_project_roots(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    public_root = Folder.objects.create(
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        is_system_root=True,
        created_by=admin,
    )
    project = Project.objects.create(name="风场项目", code="P001", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator)
    project_root = Folder.objects.create(
        project=project,
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        created_by=admin,
    )
    child = Folder.objects.create(
        project=project, parent=project_root, name="报审版", created_by=admin
    )
    client.force_login(admin)
    document = create_document(
        client,
        folder=child,
        title="方案",
        filename="方案.docx",
        content=b"solution",
    )
    DocumentGrant.objects.create(
        document_id=document["id"],
        user=operator,
        can_download=True,
        created_by=admin,
    )
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/folder-download/",
        {"folder": public_root.id},
        content_type="application/json",
    )

    assert response.status_code == 200
    with ZipFile(BytesIO(response_body(response))) as archive:
        expected_path = "技术方案/P001 风场项目/报审版/方案.docx"
        assert archive.namelist() == [expected_path]
        assert archive.read(expected_path) == b"solution"


@pytest.mark.django_db
def test_center_download_includes_standard_roots_and_excludes_legacy_dev_root(
    client, tmp_path, settings
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    company_root = Folder.objects.create(
        name="公司资质",
        code="PUBLIC-COMPANY",
        is_system_root=True,
        sort_order=1,
        created_by=admin,
    )
    company_child = Folder.objects.create(
        parent=company_root,
        name="证照",
        created_by=admin,
    )
    Folder.objects.create(
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        is_system_root=True,
        sort_order=2,
        created_by=admin,
    )
    project = Project.objects.create(name="风场项目", code="P001", created_by=admin)
    project_root = Folder.objects.create(
        project=project,
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        created_by=admin,
    )
    project_child = Folder.objects.create(
        project=project,
        parent=project_root,
        name="报审版",
        created_by=admin,
    )
    legacy_root = Folder.objects.create(
        name="开发公共资料",
        code="DEV_PUBLIC",
        is_system_root=True,
        sort_order=0,
        created_by=admin,
    )
    client.force_login(admin)
    create_document(
        client,
        folder=company_child,
        title="营业执照",
        filename="license.pdf",
        content=b"license",
    )
    create_document(
        client,
        folder=project_child,
        title="方案",
        filename="方案.docx",
        content=b"solution",
    )
    create_document(
        client,
        folder=legacy_root,
        title="开发示例",
        filename="dev-demo.pdf",
        content=b"legacy-dev-data",
    )

    response = client.post(
        "/api/v1/documents/center-download/",
        {},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response["X-Archive-Document-Count"] == "2"
    with ZipFile(BytesIO(response_body(response))) as archive:
        assert sorted(archive.namelist()) == [
            "公司资质/证照/license.pdf",
            "技术方案/P001 风场项目/报审版/方案.docx",
        ]
        assert archive.read("公司资质/证照/license.pdf") == b"license"
        assert archive.read("技术方案/P001 风场项目/报审版/方案.docx") == b"solution"
    assert AuditLog.objects.filter(
        action="document.center_download",
        resource_type="DocumentCenter",
        resource_id="all",
        result="success",
    ).exists()


@pytest.mark.django_db
def test_center_download_includes_public_docs_and_only_own_staff_docs(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    first_root = Folder.objects.create(
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        is_system_root=True,
        created_by=admin,
    )
    second_root = Folder.objects.create(
        name="报告模板",
        code="PUBLIC-REPORT-TEMPLATE",
        is_system_root=True,
        created_by=admin,
    )
    staff_root = Folder.objects.create(
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    own_folder = Folder.objects.create(parent=staff_root, name="operator", created_by=admin)
    client.force_login(admin)
    create_document(
        client,
        folder=first_root,
        title="公共文件一",
        filename="public1.pdf",
        content=b"public1",
    )
    create_document(
        client,
        folder=second_root,
        title="公共文件二",
        filename="public2.pdf",
        content=b"public2",
    )
    create_document(
        client,
        folder=own_folder,
        title="本人资质",
        filename="staff.pdf",
        content=b"staff",
    )
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/center-download/",
        {},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response["X-Archive-Document-Count"] == "3"
    with ZipFile(BytesIO(response_body(response))) as archive:
        assert sorted(archive.namelist()) == [
            "人员资质/operator/staff.pdf",
            "技术方案/public1.pdf",
            "报告模板/public2.pdf",
        ]
        assert archive.read("人员资质/operator/staff.pdf") == b"staff"
        assert archive.read("技术方案/public1.pdf") == b"public1"
        assert archive.read("报告模板/public2.pdf") == b"public2"


@pytest.mark.django_db
def test_center_download_includes_project_documents_without_membership_for_data_operator(
    client, tmp_path, settings
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    public_root = Folder.objects.create(
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        is_system_root=True,
        created_by=admin,
    )
    project = Project.objects.create(name="全量项目", code="P-ALL", created_by=admin)
    project_root = Folder.objects.create(
        project=project,
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        created_by=admin,
    )
    project_folder = Folder.objects.create(
        project=project,
        parent=project_root,
        name="项目文件",
        created_by=admin,
    )
    client.force_login(admin)
    create_document(
        client,
        folder=project_folder,
        title="未加入项目资料",
        filename="project-secret.pdf",
        content=b"project-secret",
        access_level=Document.AccessLevel.RESTRICTED,
    )
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/center-download/",
        {},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response["X-Archive-Document-Count"] == "1"
    with ZipFile(BytesIO(response_body(response))) as archive:
        assert len(archive.namelist()) == 1
        assert archive.namelist()[0].endswith("/project-secret.pdf")
        assert archive.read(archive.namelist()[0]) == b"project-secret"
    assert public_root.is_system_root is True


@pytest.mark.django_db
def test_center_download_excludes_other_staff_documents_for_data_operator(
    client, tmp_path, settings
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    staff_root = Folder.objects.create(
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    own_folder = Folder.objects.create(parent=staff_root, name="operator", created_by=admin)
    other_folder = Folder.objects.create(parent=staff_root, name="other", created_by=admin)
    client.force_login(admin)
    create_document(
        client,
        folder=own_folder,
        title="本人资质",
        filename="staff.pdf",
        content=b"staff",
    )
    create_document(
        client,
        folder=other_folder,
        title="他人资质",
        filename="other-staff.pdf",
        content=b"other-staff",
    )
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/center-download/",
        {},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response["X-Archive-Document-Count"] == "1"
    with ZipFile(BytesIO(response_body(response))) as archive:
        assert archive.namelist() == ["人员资质/operator/staff.pdf"]
