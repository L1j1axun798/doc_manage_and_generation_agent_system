from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from apps.document_generation.engine.contracts import (
    ModelCallPurpose,
    ParsedBlock,
    ParsedBlockType,
    ParsedDocument,
    RiskProfile,
    SectionContext,
    SourceLocator,
)
from apps.document_generation.engine.errors import AgentError
from apps.document_generation.providers.llm import (
    LLMProviderConfig,
    OpenAICompatibleLLMProvider,
    PromptCatalog,
)


def _response(content: object, *, prompt_tokens: int = 10, completion_tokens: int = 5):
    return {
        "choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


def _context() -> SectionContext:
    return SectionContext(
        section_code="overview",
        objective="编写工程概况",
        confirmed_facts=(),
        risk_profile=RiskProfile(),
    )


def _config(**updates) -> LLMProviderConfig:
    values = {
        "base_url": "https://workspace.example.com/compatible-mode/v1",
        "api_key": "test-key-not-real",
        "model_alias": "qwen-max",
        "timeout_seconds": 30,
        "max_attempts": 2,
        "retry_wait_seconds": 0,
        "input_cost_per_million": 1,
        "output_cost_per_million": 2,
        "enable_thinking": False,
    }
    values.update(updates)
    return LLMProviderConfig(**values)


def test_environment_defaults_match_deployment_examples() -> None:
    provider = OpenAICompatibleLLMProvider.from_env(
        {
            "LLM_BASE_URL": "https://workspace.example.com/compatible-mode/v1",
            "LLM_API_KEY": "test-key-not-real",
        }
    )

    assert provider.config.model_alias == "qwen3.6-plus"
    assert provider.config.max_attempts == 3
    assert provider.config.retry_wait_seconds == 0.5


def test_nested_provider_error_details_are_preserved_for_diagnosis() -> None:
    details = OpenAICompatibleLLMProvider._provider_error_details(
        403,
        {
            "request_id": "request-403",
            "error": {
                "code": "AllocationQuota.FreeTierOnly",
                "message": "Free quota is exhausted",
            },
        },
    )

    assert details == {
        "status": 403,
        "provider_code": "AllocationQuota.FreeTierOnly",
        "request_id": "request-403",
        "provider_message": "Free quota is exhausted",
    }


def test_section_schema_is_repaired_at_most_once_and_usage_is_recorded() -> None:
    calls: list[Mapping[str, object]] = []
    responses = iter(
        (
            _response({"section_code": "overview"}),
            _response(
                {
                    "section_code": "overview",
                    "title": "工程概况",
                    "paragraphs": ["按当前确认事实编写入场计划。"],
                }
            ),
        )
    )

    def transport(endpoint, headers, payload, timeout):
        calls.append(payload)
        return next(responses), f"request-{len(calls)}"

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)

    section = provider.draft_section(_context())

    assert section.title == "工程概况"
    assert len(calls) == 2
    assert calls[0]["enable_thinking"] is False
    assert calls[0]["max_tokens"] == 4096
    assert calls[0]["temperature"] == 0
    assert "原输出的校验错误" in str(calls[1]["messages"])
    assert "title" in str(calls[1]["messages"])
    assert [record.purpose for record in provider.usage_records] == [
        ModelCallPurpose.SECTION_GENERATION,
        ModelCallPurpose.SCHEMA_REPAIR,
    ]
    assert provider.usage_records[-1].request_id == "request-2"


def test_schema_failure_after_one_repair_stops() -> None:
    call_count = 0

    def transport(endpoint, headers, payload, timeout):
        nonlocal call_count
        call_count += 1
        return _response({"section_code": "overview"}), None

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)

    with pytest.raises(AgentError) as captured:
        provider.draft_section(_context())

    assert captured.value.code == "MODEL_SCHEMA_INVALID"
    assert call_count == 2


def test_flat_section_list_is_safely_normalized_without_second_model_call() -> None:
    call_count = 0

    def transport(endpoint, headers, payload, timeout):
        nonlocal call_count
        call_count += 1
        return (
            _response(
                {
                    "section_code": "overview",
                    "title": "工程概况",
                    "lists": ["入场前确认作业条件", "组织安全交底"],
                }
            ),
            "flat-list-request",
        )

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)

    section = provider.draft_section(_context())

    assert section.lists == (("入场前确认作业条件", "组织安全交底"),)
    assert call_count == 1


def test_model_cannot_change_system_selected_section_code() -> None:
    def transport(endpoint, headers, payload, timeout):
        return (
            _response(
                {
                    "section_code": "technical_measures",
                    "title": "工程概况",
                    "paragraphs": ["正文保持不变。"],
                }
            ),
            "wrong-section-code-request",
        )

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)

    section = provider.draft_section(_context())

    assert section.section_code == "overview"
    assert section.paragraphs == ("正文保持不变。",)


def test_duplicate_provenance_is_safely_normalized_without_rewriting_body() -> None:
    call_count = 0
    body = "入场前技术准备正文不得被结构修复缩短。" * 200

    def transport(endpoint, headers, payload, timeout):
        nonlocal call_count
        call_count += 1
        return (
            _response(
                {
                    "section_code": "technical_measures",
                    "title": "技术措施",
                    "paragraphs": [body],
                    "used_fact_fields": ["site_name", "site_name"],
                    "used_clause_ids": ["clause-1", "clause-1"],
                }
            ),
            "duplicate-provenance-request",
        )

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)

    section = provider.draft_section(_context())

    assert section.paragraphs == (body,)
    assert section.used_fact_fields == ("site_name",)
    assert section.used_clause_ids == ("clause-1",)
    assert call_count == 1


def test_harmless_extra_schema_fields_are_removed_without_rewriting_body() -> None:
    call_count = 0
    body = "入场前计划正文必须原样保留。" * 200

    def transport(endpoint, headers, payload, timeout):
        nonlocal call_count
        call_count += 1
        return (
            _response(
                {
                    "section_code": "overview",
                    "title": "工程概况",
                    "paragraphs": [body],
                    "unexpected_summary": "不得进入契约",
                    "citations": [
                        {
                            "source_document_version_id": 134,
                            "locator": {
                                "paragraph_index": 1,
                                "text_quote": "依据" * 150,
                                "unexpected_locator": "ignored",
                            },
                            "unexpected_citation": "ignored",
                        }
                    ],
                }
            ),
            "extra-fields-request",
        )

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)

    section = provider.draft_section(_context())

    assert section.paragraphs == (body,)
    assert len(section.citations[0].locator.text_quote or "") == 200
    assert call_count == 1


def test_qwen_object_arrays_are_normalized_without_model_rewrite() -> None:
    call_count = 0
    body = "入场前计划正文必须完整保留。" * 200

    def transport(endpoint, headers, payload, timeout):
        nonlocal call_count
        call_count += 1
        return (
            _response(
                {
                    "section_code": "overview",
                    "title": "工程概况",
                    "paragraphs": [
                        {"content": "（一）项目基本信息和工作范围"},
                        {"content": body},
                    ],
                    "lists": None,
                    "tables": None,
                    "citations": None,
                    "used_fact_fields": [
                        {
                            "field": "project_name",
                            "value": "当前项目",
                            "fact_field": "project_name",
                        }
                    ],
                    "used_clause_ids": None,
                    "missing_items": None,
                    "warnings": None,
                }
            ),
            "qwen-object-arrays-request",
        )

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)

    section = provider.draft_section(_context())

    assert section.paragraphs == ("（一）项目基本信息和工作范围", body)
    assert section.used_fact_fields == ("project_name",)
    assert section.lists == ()
    assert section.citations == ()
    assert call_count == 1


def test_transient_model_error_retries_and_calculates_cost() -> None:
    call_count = 0

    def transport(endpoint, headers, payload, timeout):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise AgentError("MODEL_TIMEOUT", "timeout")
        return (
            _response(
                {"section_code": "overview", "title": "工程概况"},
                prompt_tokens=100,
                completion_tokens=50,
            ),
            "request-retry",
        )

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)

    provider.draft_section(_context())

    assert call_count == 2
    assert provider.usage_records[0].retry_count == 1
    assert provider.usage_records[0].estimated_cost == pytest.approx(0.0002)


def test_fact_extraction_uses_structured_schema() -> None:
    def transport(endpoint, headers, payload, timeout):
        return (
            _response(
                {
                    "facts": [
                        {
                            "field": "site_name",
                            "value": "当前风电场",
                            "value_type": "string",
                            "source_document_version_id": 134,
                            "locator": {"paragraph_index": 1},
                            "confidence": 0.9,
                        }
                    ]
                }
            ),
            "fact-request",
        )

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)

    document = ParsedDocument(
        document_version_id=134,
        filename="开发样本.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content_sha256="1" * 64,
        title="入场四措两案",
        blocks=(
            ParsedBlock(
                block_id="134:p:1",
                block_type=ParsedBlockType.PARAGRAPH,
                text="当前风电场",
                locator=SourceLocator(paragraph_index=1),
            ),
        ),
    )

    facts = provider.extract_facts((document,))

    assert len(facts) == 1
    assert facts[0].field == "site_name"


def test_fact_extraction_prompt_declares_canonical_required_fields() -> None:
    version, prompt = PromptCatalog().fact_extraction()

    assert version == "fact_extraction/v2"
    assert "work_scope" in prompt
    assert "inspection_component_codes" in prompt
    assert "inspection_method_codes" in prompt
    assert "risk_evidence_items" in prompt


def test_fact_extraction_rejects_source_version_not_in_current_document() -> None:
    def transport(endpoint, headers, payload, timeout):
        return (
            _response(
                {
                    "facts": [
                        {
                            "field": "site_name",
                            "value": "错误历史场站",
                            "value_type": "string",
                            "source_document_version_id": 999,
                            "locator": {"paragraph_index": 1},
                            "confidence": 0.9,
                        }
                    ]
                }
            ),
            "fact-request",
        )

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)
    document = ParsedDocument(
        document_version_id=134,
        filename="开发样本.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content_sha256="1" * 64,
        title="入场四措两案",
        blocks=(
            ParsedBlock(
                block_id="134:p:1",
                block_type=ParsedBlockType.PARAGRAPH,
                text="当前风电场",
                locator=SourceLocator(paragraph_index=1),
            ),
        ),
    )

    with pytest.raises(AgentError) as captured:
        provider.extract_facts((document,))

    assert captured.value.code == "MODEL_FACT_SOURCE_INVALID"


def test_persistent_rate_limit_stops_after_configured_attempts_without_secret() -> None:
    call_count = 0

    def transport(endpoint, headers, payload, timeout):
        nonlocal call_count
        call_count += 1
        raise AgentError("MODEL_RATE_LIMITED", "rate limited")

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)

    with pytest.raises(AgentError) as captured:
        provider.draft_section(_context())

    assert captured.value.code == "MODEL_RATE_LIMITED"
    assert call_count == 2
    assert "test-key-not-real" not in str(captured.value)


def test_section_revision_has_separate_usage_purpose() -> None:
    def transport(endpoint, headers, payload, timeout):
        return (
            _response(
                {
                    "section_code": "technical_measures",
                    "title": "工程概况",
                    "paragraphs": ["修订后的入场计划。"],
                }
            ),
            "revision-request",
        )

    provider = OpenAICompatibleLLMProvider(_config(), transport=transport)
    draft = provider.draft_section(_context())
    revised = provider.revise_section(_context(), draft, ())

    assert revised.paragraphs == ("修订后的入场计划。",)
    assert revised.section_code == "overview"
    assert provider.usage_records[-1].purpose == ModelCallPurpose.SECTION_REVISION
