from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.folders.defaults import STANDARD_PUBLIC_ROOTS, StandardFolderDefinition
from apps.folders.models import Folder
from apps.projects.models import Project
from apps.projects.services import (
    get_or_create_archive_year_folder,
    get_or_create_project_archive_folder,
    project_archive_folder_code,
)

from .models import Document


@dataclass(frozen=True)
class ArchivedDocumentFolderRepair:
    document_id: int
    project_id: int
    title: str
    source_folder_id: int
    source_path: str
    target_folder_id: int | None
    target_path: str


def repair_archived_document_folders(*, dry_run: bool = True) -> list[ArchivedDocumentFolderRepair]:
    repairs: list[ArchivedDocumentFolderRepair] = []
    documents = (
        Document.objects.filter(
            project__status=Project.Status.ARCHIVED,
            deleted_at__isnull=True,
        )
        .select_related(
            "project",
            "project__archived_by",
            "project__created_by",
            "folder",
            "folder__parent",
        )
        .order_by("id")
    )

    with transaction.atomic():
        for document in documents:
            project = document.project
            if project is None or project.archived_at is None:
                continue

            archive_container = _existing_archive_container(project)
            if archive_container and _is_descendant_of(document.folder, archive_container):
                continue

            actor = project.archived_by or project.created_by
            source_path = _folder_path(document.folder)

            if dry_run:
                target_folder = None
                target_path = _planned_target_path(project=project, source_folder=document.folder)
            else:
                archive_year_folder = get_or_create_archive_year_folder(
                    actor=actor,
                    year=project.archived_at.year,
                )
                archive_container = get_or_create_project_archive_folder(
                    actor=actor,
                    archive_year_folder=archive_year_folder,
                    project=project,
                )
                target_folder = _ensure_target_folder(
                    project=project,
                    archive_container=archive_container,
                    source_folder=document.folder,
                    actor=actor,
                )
                target_path = _folder_path(target_folder)
                if document.folder_id != target_folder.id:
                    document.folder = target_folder
                    document.save(update_fields=["folder", "updated_at"])

            repairs.append(
                ArchivedDocumentFolderRepair(
                    document_id=document.id,
                    project_id=project.id,
                    title=document.title,
                    source_folder_id=document.folder_id,
                    source_path=source_path,
                    target_folder_id=target_folder.id if target_folder else None,
                    target_path=target_path,
                )
            )

    return repairs


def _existing_archive_container(project: Project) -> Folder | None:
    return Folder.objects.filter(
        project=project,
        code=project_archive_folder_code(project),
        is_active=True,
    ).first()


def _ensure_target_folder(
    *,
    project: Project,
    archive_container: Folder,
    source_folder: Folder,
    actor: Any,
) -> Folder:
    chain = _folder_chain(source_folder)
    root_index, root_definition = _find_standard_root(chain)
    if root_definition is not None:
        current = _ensure_project_archive_root(
            project=project,
            archive_container=archive_container,
            definition=root_definition,
            actor=actor,
        )
        folders_to_copy = chain[root_index + 1 :]
    else:
        current = archive_container
        folders_to_copy = chain

    for source in folders_to_copy:
        current = _ensure_child_folder(project=project, parent=current, source=source, actor=actor)

    return current


def _ensure_project_archive_root(
    *,
    project: Project,
    archive_container: Folder,
    definition: StandardFolderDefinition,
    actor: Any,
) -> Folder:
    folder = (
        Folder.objects.filter(project=project, parent=archive_container, code=definition.code)
        .order_by("id")
        .first()
    )
    if folder is None:
        folder = (
            Folder.objects.filter(project=project, code=definition.code)
            .order_by("id")
            .first()
        )

    if folder is None:
        return Folder.objects.create(
            project=project,
            parent=archive_container,
            name=definition.name,
            code=definition.code,
            sort_order=definition.sort_order,
            is_active=True,
            created_by=actor,
        )

    changed_fields: list[str] = []
    if folder.parent_id != archive_container.id:
        folder.parent = archive_container
        changed_fields.append("parent")
    if folder.name != definition.name:
        folder.name = definition.name
        changed_fields.append("name")
    if folder.code != definition.code:
        folder.code = definition.code
        changed_fields.append("code")
    if not folder.is_active:
        folder.is_active = True
        changed_fields.append("is_active")
    if changed_fields:
        folder.save(update_fields=[*changed_fields, "updated_at"])
    return folder


def _ensure_child_folder(*, project: Project, parent: Folder, source: Folder, actor: Any) -> Folder:
    folder = (
        Folder.objects.filter(project=project, parent=parent, name=source.name)
        .order_by("id")
        .first()
    )
    if folder is None:
        return Folder.objects.create(
            project=project,
            parent=parent,
            name=source.name,
            code=source.code,
            sort_order=source.sort_order,
            is_active=True,
            created_by=source.created_by or actor,
        )

    if not folder.is_active:
        folder.is_active = True
        folder.save(update_fields=["is_active", "updated_at"])
    return folder


def _planned_target_path(*, project: Project, source_folder: Folder) -> str:
    chain = _folder_chain(source_folder)
    root_index, root_definition = _find_standard_root(chain)
    names = [f"{project.code} {project.name}"]
    if root_definition is not None:
        names.append(root_definition.name)
        names.extend(folder.name for folder in chain[root_index + 1 :])
    else:
        names.extend(folder.name for folder in chain)
    return " / ".join(names)


def _find_standard_root(
    chain: list[Folder],
) -> tuple[int, StandardFolderDefinition | None]:
    for index, folder in enumerate(chain):
        definition = _standard_definition_for(folder)
        if definition is not None:
            return index, definition
    return -1, None


def _standard_definition_for(folder: Folder) -> StandardFolderDefinition | None:
    for definition in STANDARD_PUBLIC_ROOTS:
        if folder.code == definition.code or folder.name in definition.names:
            return definition
    return None


def _folder_chain(folder: Folder) -> list[Folder]:
    chain = [folder]
    seen = {folder.id}
    parent = folder.parent
    while parent is not None and parent.id not in seen:
        chain.append(parent)
        seen.add(parent.id)
        parent = parent.parent
    return list(reversed(chain))


def _folder_path(folder: Folder) -> str:
    return " / ".join(item.name for item in _folder_chain(folder))


def _is_descendant_of(folder: Folder, ancestor: Folder) -> bool:
    current: Folder | None = folder
    seen: set[int] = set()
    while current is not None and current.id not in seen:
        if current.id == ancestor.id:
            return True
        seen.add(current.id)
        current = current.parent
    return False
