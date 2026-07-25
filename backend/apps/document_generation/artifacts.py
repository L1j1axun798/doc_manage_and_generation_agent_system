from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile

from common.storage import LocalDocumentStorage

from .engine.contracts import RenderedArtifact, StoredArtifact
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
        uploaded = SimpleUploadedFile(
            artifact.filename,
            artifact.content,
            content_type=artifact.media_type,
        )
        stored = self.storage.save_uploaded_file(uploaded)
        old_path = (
            GenerationTask.objects.filter(pk=self.task_id)
            .values_list("draft_storage_path", flat=True)
            .first()
        )
        GenerationTask.objects.filter(pk=self.task_id).update(
            draft_storage_path=stored.relative_path,
            draft_sha256=stored.sha256,
            draft_filename=artifact.filename,
        )
        if old_path and old_path != stored.relative_path:
            self.storage.delete(old_path)
        return StoredArtifact(
            artifact_id=stored.relative_path,
            filename=artifact.filename,
            media_type=artifact.media_type,
            sha256=stored.sha256,
        )
