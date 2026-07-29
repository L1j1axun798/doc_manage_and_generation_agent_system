from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import transaction
from django.db.models import Max

from .engine.contracts import TraceEvent, TraceStatus, WorkflowStage
from .models import GenerationTask, GenerationTraceEvent

TOOL_TITLES = {
    "queue_fact_extraction": "事实提取任务已进入队列",
    "load_source_documents": "读取当前项目的入场前置资料",
    "parse_source_document": "解析入场前置资料",
    "extract_fact_candidates": "模型识别项目事实",
    "merge_fact_candidates": "合并事实并检查来源冲突",
    "wait_for_fact_confirmation": "等待人工确认关键项目事实",
    "validate_generation_request": "核对编制任务输入",
    "validate_fact_set": "校验已确认事实及其来源",
    "build_risk_profile": "建立当前项目风险画像",
    "select_clause_blocks": "匹配已批准的四措两案条款",
    "retrieve_reference_sections": "RAG检索已批准参考章节",
    "rag_context_ready": "RAG参考内容已装入本章上下文",
    "build_section_context": "组织本章事实、条款和参考资料",
    "draft_document_section": "模型编写本章初稿",
    "revise_document_section": "模型按校验意见修订本章",
    "normalize_section_provenance": "整理本章引用来源",
    "normalize_revised_section_provenance": "整理修订稿引用来源",
    "validate_document_section": "执行本章确定性规则校验",
    "revalidate_document_section": "复核已有章节",
    "revalidate_revised_section": "复核模型修订稿",
    "persist_generated_section": "保存本章草稿",
    "persist_revalidated_section": "保存复核后的章节",
    "reuse_persisted_section": "复用已生成且仍有效的章节",
    "discard_invalid_persisted_section": "丢弃不再适用的旧章节",
    "render_word_document": "按已批准版式生成Word",
    "publish_document_version": "保存可审核的Word草稿",
    "complete_generation": "四措两案初稿生成完成",
    "stop_workflow": "编制工作流已停止",
    "cancel_generation_task": "用户已停止当前编制会话",
}

MODEL_TOOLS = {
    "extract_fact_candidates",
    "draft_document_section",
    "revise_document_section",
}
RAG_TOOLS = {"retrieve_reference_sections", "rag_context_ready"}

EXTRACT_PROGRESS = {
    WorkflowStage.INITIALIZED.value: 10,
    WorkflowStage.PARSING.value: 12,
    WorkflowStage.EXTRACTING_FACTS.value: 16,
    WorkflowStage.VALIDATING_FACTS.value: 18,
    WorkflowStage.COMPLETED.value: 20,
}
GENERATE_PROGRESS = {
    WorkflowStage.INITIALIZED.value: 40,
    WorkflowStage.PARSING.value: 42,
    WorkflowStage.VALIDATING_FACTS.value: 45,
    WorkflowStage.BUILDING_RISK_PROFILE.value: 48,
    WorkflowStage.SELECTING_CLAUSES.value: 52,
    WorkflowStage.RETRIEVING_REFERENCES.value: 58,
    WorkflowStage.GENERATING_SECTIONS.value: 68,
    WorkflowStage.VALIDATING_SECTIONS.value: 78,
    WorkflowStage.RENDERING.value: 84,
    WorkflowStage.STORING.value: 88,
    WorkflowStage.COMPLETED.value: 90,
}


def event_type_for_tool(tool: str) -> str:
    if tool in MODEL_TOOLS:
        return GenerationTraceEvent.EventType.MODEL
    if tool in RAG_TOOLS:
        return GenerationTraceEvent.EventType.RAG
    if tool.startswith(("validate_", "build_", "select_", "parse_", "render_", "publish_")):
        return GenerationTraceEvent.EventType.TOOL
    return GenerationTraceEvent.EventType.SYSTEM


class TaskWorkflowRecorder:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id

    def __call__(self, event: TraceEvent) -> None:
        self.emit(
            stage=event.stage.value,
            tool=event.tool,
            status=event.status.value,
            detail=event.detail or "",
        )

    @transaction.atomic
    def emit(
        self,
        *,
        stage: str,
        tool: str,
        status: str,
        title: str | None = None,
        detail: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> GenerationTraceEvent:
        task = GenerationTask.objects.select_for_update().get(pk=self.task_id)
        if task.status == GenerationTask.Status.CANCELLED and tool != "cancel_generation_task":
            raise TaskExecutionCancelled("编制会话已由用户停止")
        current = (
            GenerationTraceEvent.objects.filter(task=task).aggregate(value=Max("sequence"))["value"]
            or 0
        )
        row = GenerationTraceEvent.objects.create(
            task=task,
            sequence=current + 1,
            stage=stage,
            event_type=event_type_for_tool(tool),
            tool=tool,
            status=status,
            title=title or TOOL_TITLES.get(tool, tool.replace("_", " ")),
            detail=detail[:2000],
            metadata=dict(metadata or {}),
        )
        progress_map = (
            EXTRACT_PROGRESS
            if task.operation == GenerationTask.Operation.EXTRACT
            else GENERATE_PROGRESS
        )
        next_progress = progress_map.get(stage)
        if (
            status != TraceStatus.FAILED.value
            and next_progress is not None
            and next_progress > task.progress
        ):
            task.progress = next_progress
            task.save(update_fields=["progress", "updated_at"])
        return row


class TaskExecutionCancelled(RuntimeError):
    pass
