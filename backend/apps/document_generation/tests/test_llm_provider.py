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

    assert provider.config.model_alias == "qwen3.7-plus"
    assert provider.config.max_attempts == 3
    assert provider.config.retry_wait_seconds == 0.5


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
                    "section_code": "overview",
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
    assert provider.usage_records[-1].purpose == ModelCallPurpose.SECTION_REVISION
