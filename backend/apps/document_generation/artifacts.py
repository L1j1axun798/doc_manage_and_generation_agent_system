from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile

from common.storage import LocalDocumentStorage

from .engine.contracts import RenderedArtifact, StoredArtifact
from .engine.errors import AgentError
from .models import GenerationTask


class TaskDraftArtifactStorage:
    def __init__(
        self,
        *,
        task_id: str,
        storage: LocalDocumentStorage | None = None,
    ) -> None:
        self.task_id = task_id
        self.storage = storage or LocalDocumentStorage()

    def save(self, artifact: RenderedArtifact) -> StoredArtifact:
        task = GenerationTask.objects.only(
            "status",
            "deleted_at",
            "draft_storage_path",
        ).get(pk=self.task_id)
        if task.status != GenerationTask.Status.GENERATING or task.deleted_at is not None:
            raise AgentError("TASK_CANCELLED", "编制会话已停止，禁止继续保存草稿")
        uploaded = SimpleUploadedFile(
            artifact.filename,
            artifact.content,
            content_type=artifact.media_type,
        )
        stored = self.storage.save_uploaded_file(uploaded)
        updated = GenerationTask.objects.filter(
            pk=self.task_id,
            status=GenerationTask.Status.GENERATING,
            deleted_at__isnull=True,
        ).update(
            draft_storage_path=stored.relative_path,
            draft_sha256=stored.sha256,
            draft_filename=artifact.filename,
        )
        if not updated:
            self.storage.delete(stored.relative_path)
            raise AgentError("TASK_CANCELLED", "编制会话已停止，草稿未保存")
        if task.draft_storage_path and task.draft_storage_path != stored.relative_path:
            self.storage.delete(task.draft_storage_path)
        return StoredArtifact(
            artifact_id=stored.relative_path,
            filename=artifact.filename,
            media_type=artifact.media_type,
            sha256=stored.sha256,
        )
