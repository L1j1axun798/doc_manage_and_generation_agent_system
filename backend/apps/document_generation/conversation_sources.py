from __future__ import annotations

from typing import Any

from .engine.contracts import SourceDocument

USER_PROMPT_SOURCE_VERSION_ID = 0
USER_PROMPT_MIME_TYPE = "application/x-wind-doc-agent-prompt"


def prompt_source_document(task: Any) -> SourceDocument | None:
    context = task.conversation_context or {}
    initial_message = str(context.get("initial_message", "")).strip()
    if not initial_message:
        return None
    personnel = context.get("personnel", [])
    personnel_names = "、".join(
        str(item.get("name", "")).strip()
        for item in personnel
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    )
    lines = [
        f"项目名称：{task.project.name}",
        f"项目编码：{task.project.code}",
        f"用户本次编制要求：{initial_message}",
    ]
    if personnel_names:
        lines.append(f"用户本次选择人员：{personnel_names}")
    return SourceDocument(
        document_version_id=USER_PROMPT_SOURCE_VERSION_ID,
        filename="用户本次编制要求.prompt",
        mime_type=USER_PROMPT_MIME_TYPE,
        content="\n".join(lines).encode("utf-8"),
    )
