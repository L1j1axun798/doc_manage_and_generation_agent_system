from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ValidationError
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_fixed

from apps.document_generation.engine.contracts import (
    FactCandidate,
    FactExtractionResponse,
    GeneratedSection,
    ModelCallPurpose,
    ModelUsageRecord,
    ParsedDocument,
    SectionContext,
    ValidationIssue,
)
from apps.document_generation.engine.errors import AgentError

LLMTransport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float],
    tuple[Mapping[str, Any], str | None],
]
SchemaModel = TypeVar("SchemaModel", bound=BaseModel)
RETRYABLE_MODEL_ERRORS = frozenset(
    {
        "MODEL_TIMEOUT",
        "MODEL_RATE_LIMITED",
        "MODEL_SERVICE_UNAVAILABLE",
    }
)


@dataclass(frozen=True)
class LLMProviderConfig:
    base_url: str
    api_key: str
    model_alias: str
    timeout_seconds: float = 60
    max_attempts: int = 3
    retry_wait_seconds: float = 0.5
    input_cost_per_million: float = 0
    output_cost_per_million: float = 0
    enable_thinking: bool | None = None
    max_tokens: int = 4096
    temperature: float = 0

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ValueError("LLM_BASE_URL must use HTTPS")
        if not self.api_key:
            raise ValueError("LLM_API_KEY is required")
        if not self.model_alias:
            raise ValueError("LLM_MODEL is required")
        if self.timeout_seconds <= 0 or self.max_attempts <= 0:
            raise ValueError("LLM timeout and max attempts must be positive")
        if self.retry_wait_seconds < 0:
            raise ValueError("LLM retry wait must not be negative")
        if self.input_cost_per_million < 0 or self.output_cost_per_million < 0:
            raise ValueError("LLM token costs must not be negative")
        if self.max_tokens <= 0:
            raise ValueError("LLM max tokens must be positive")
        if not 0 <= self.temperature <= 2:
            raise ValueError("LLM temperature must be between 0 and 2")


class PromptCatalog:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[1] / "prompts"

    def fact_extraction(self) -> tuple[str, str]:
        return "fact_extraction/v1", self._read("fact_extraction/v1.md")

    def section_generation(self) -> tuple[str, str]:
        return "section_generation/v1", self._read("section_generation/v1.md")

    def section_revision(self) -> tuple[str, str]:
        return "section_revision/v1", self._read("section_revision/v1.md")

    def schema_repair(self) -> tuple[str, str]:
        return "schema_repair/v1", self._read("schema_repair/v1.md")

    def _read(self, relative_path: str) -> str:
        path = (self.root / relative_path).resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError as exc:
            raise ValueError("prompt path escapes prompt root") from exc
        return path.read_text(encoding="utf-8")


class OpenAICompatibleLLMProvider:
    def __init__(
        self,
        config: LLMProviderConfig,
        *,
        transport: LLMTransport | None = None,
        prompt_catalog: PromptCatalog | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or self._urllib_transport
        self.prompt_catalog = prompt_catalog or PromptCatalog()
        self.usage_records: list[ModelUsageRecord] = []

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        transport: LLMTransport | None = None,
        prompt_catalog: PromptCatalog | None = None,
    ) -> OpenAICompatibleLLMProvider:
        values = os.environ if env is None else env
        return cls(
            LLMProviderConfig(
                base_url=values.get("LLM_BASE_URL", ""),
                api_key=values.get("LLM_API_KEY", ""),
                model_alias=values.get("LLM_MODEL", "qwen3.7-plus"),
                timeout_seconds=float(values.get("LLM_TIMEOUT_SECONDS", "60")),
                max_attempts=int(values.get("LLM_MAX_ATTEMPTS", "3")),
                retry_wait_seconds=float(values.get("LLM_RETRY_WAIT_SECONDS", "0.5")),
                input_cost_per_million=float(values.get("LLM_INPUT_COST_PER_MILLION", "0")),
                output_cost_per_million=float(values.get("LLM_OUTPUT_COST_PER_MILLION", "0")),
                enable_thinking=_optional_bool(values.get("LLM_ENABLE_THINKING")),
                max_tokens=int(values.get("LLM_MAX_TOKENS", "4096")),
                temperature=float(values.get("LLM_TEMPERATURE", "0")),
            ),
            transport=transport,
            prompt_catalog=prompt_catalog,
        )

    @property
    def model_alias(self) -> str:
        return self.config.model_alias

    def extract_facts(
        self,
        documents: Sequence[ParsedDocument],
    ) -> Sequence[FactCandidate]:
        version, instructions = self.prompt_catalog.fact_extraction()
        facts: list[FactCandidate] = []
        for document in documents:
            prompt = f"{instructions}\n\n来源文档结构化内容：\n" + json.dumps(
                document.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            )
            response = self._generate_schema(
                prompt=prompt,
                schema=FactExtractionResponse,
                purpose=ModelCallPurpose.FACT_EXTRACTION,
                prompt_version=version,
            )
            for fact in response.facts:
                if fact.source_document_version_id != document.document_version_id:
                    raise AgentError(
                        "MODEL_FACT_SOURCE_INVALID",
                        "候选事实引用了当前来源之外的文档版本",
                    )
                if not self._locator_exists(fact, document):
                    raise AgentError(
                        "MODEL_FACT_SOURCE_INVALID",
                        "候选事实缺少可核验的来源定位",
                    )
            facts.extend(response.facts)
        return tuple(facts)

    @staticmethod
    def _locator_exists(
        fact: FactCandidate,
        document: ParsedDocument,
    ) -> bool:
        locator = fact.locator
        if locator.paragraph_index is None and locator.table_index is None and locator.page is None:
            return False
        return any(
            (
                locator.paragraph_index is not None
                and locator.paragraph_index == block.locator.paragraph_index
            )
            or (
                locator.table_index is not None and locator.table_index == block.locator.table_index
            )
            or (
                locator.page is not None
                and locator.page == block.locator.page
                and (
                    locator.paragraph_index is None
                    or locator.paragraph_index == block.locator.paragraph_index
                )
            )
            for block in document.blocks
        )

    def draft_section(self, context: SectionContext) -> GeneratedSection:
        version, instructions = self.prompt_catalog.section_generation()
        prompt = f"{instructions}\n\n章节上下文：\n" + json.dumps(
            context.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )
        return self._generate_schema(
            prompt=prompt,
            schema=GeneratedSection,
            purpose=ModelCallPurpose.SECTION_GENERATION,
            prompt_version=version,
        )

    def revise_section(
        self,
        context: SectionContext,
        section: GeneratedSection,
        issues: Sequence[ValidationIssue],
    ) -> GeneratedSection:
        version, instructions = self.prompt_catalog.section_revision()
        prompt = (
            f"{instructions}\n\n章节上下文：\n"
            + json.dumps(
                context.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n\n待修订章节：\n"
            + section.model_dump_json()
            + "\n\n必须解决的确定性校验错误：\n"
            + json.dumps(
                [issue.model_dump(mode="json") for issue in issues],
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return self._generate_schema(
            prompt=prompt,
            schema=GeneratedSection,
            purpose=ModelCallPurpose.SECTION_REVISION,
            prompt_version=version,
        )

    def repair_structured_output(self, raw_output: str) -> GeneratedSection:
        return self._repair_once(raw_output, GeneratedSection)

    def _generate_schema(
        self,
        *,
        prompt: str,
        schema: type[SchemaModel],
        purpose: ModelCallPurpose,
        prompt_version: str,
    ) -> SchemaModel:
        raw_output = self._chat(
            prompt=prompt,
            purpose=purpose,
            prompt_version=prompt_version,
        )
        try:
            return self._validate_schema_output(raw_output, schema)
        except (ValidationError, ValueError):
            return self._repair_once(raw_output, schema)

    def _repair_once(
        self,
        raw_output: str,
        schema: type[SchemaModel],
    ) -> SchemaModel:
        version, instructions = self.prompt_catalog.schema_repair()
        prompt = (
            f"{instructions}\n\n目标Schema：\n"
            f"{json.dumps(schema.model_json_schema(), ensure_ascii=False, sort_keys=True)}"
            f"\n\n待修复输出：\n{raw_output}"
        )
        repaired = self._chat(
            prompt=prompt,
            purpose=ModelCallPurpose.SCHEMA_REPAIR,
            prompt_version=version,
        )
        try:
            return self._validate_schema_output(repaired, schema)
        except (ValidationError, ValueError) as exc:
            raise AgentError("MODEL_SCHEMA_INVALID", "模型输出修复一次后仍不符合Schema") from exc

    @staticmethod
    def _validate_schema_output(
        raw_output: str,
        schema: type[SchemaModel],
    ) -> SchemaModel:
        payload = json.loads(raw_output)
        if schema is GeneratedSection and isinstance(payload, dict):
            list_groups = payload.get("lists")
            if (
                isinstance(list_groups, list)
                and list_groups
                and all(isinstance(item, str) for item in list_groups)
            ):
                payload = {**payload, "lists": [list_groups]}
        return schema.model_validate(payload)

    def _chat(
        self,
        *,
        prompt: str,
        purpose: ModelCallPurpose,
        prompt_version: str,
    ) -> str:
        endpoint = self.config.base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, object] = {
            "model": self.config.model_alias,
            "messages": [
                {
                    "role": "system",
                    "content": "严格按提供的业务约束输出JSON，不执行任何外部操作。",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if self.config.enable_thinking is not None:
            payload["enable_thinking"] = self.config.enable_thinking
        attempt_number = 0
        response: Mapping[str, Any] | None = None
        request_id: str | None = None
        retrying = Retrying(
            stop=stop_after_attempt(self.config.max_attempts),
            wait=wait_fixed(self.config.retry_wait_seconds),
            retry=retry_if_exception(self._is_retryable),
            reraise=True,
        )
        try:
            for attempt in retrying:
                with attempt:
                    attempt_number = attempt.retry_state.attempt_number
                    response, request_id = self.transport(
                        endpoint,
                        headers,
                        payload,
                        self.config.timeout_seconds,
                    )
        except AgentError:
            raise
        except Exception as exc:
            raise AgentError(
                "MODEL_REQUEST_FAILED",
                "模型服务调用失败",
                details={"exception_type": type(exc).__name__},
            ) from exc
        if response is None:
            raise AgentError("MODEL_RESPONSE_INVALID", "模型服务没有返回响应")
        content = self._response_content(response)
        prompt_tokens, completion_tokens = self._usage(response)
        estimated_cost = (
            prompt_tokens * self.config.input_cost_per_million
            + completion_tokens * self.config.output_cost_per_million
        ) / 1_000_000
        self.usage_records.append(
            ModelUsageRecord(
                purpose=purpose,
                model_alias=self.model_alias,
                prompt_version=prompt_version,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost=estimated_cost,
                request_id=request_id,
                retry_count=max(0, attempt_number - 1),
            )
        )
        return content

    @staticmethod
    def _is_retryable(exception: BaseException) -> bool:
        return isinstance(exception, AgentError) and exception.code in RETRYABLE_MODEL_ERRORS

    @staticmethod
    def _response_content(response: Mapping[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise AgentError("MODEL_RESPONSE_INVALID", "模型响应choices结构无效")
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise AgentError("MODEL_RESPONSE_INVALID", "模型响应choice结构无效")
        message = choice.get("message")
        if not isinstance(message, Mapping):
            raise AgentError("MODEL_RESPONSE_INVALID", "模型响应message结构无效")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AgentError("MODEL_RESPONSE_INVALID", "模型响应正文为空")
        return content

    @staticmethod
    def _usage(response: Mapping[str, Any]) -> tuple[int, int]:
        usage = response.get("usage", {})
        if not isinstance(usage, Mapping):
            raise AgentError("MODEL_RESPONSE_INVALID", "模型usage结构无效")
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        if (
            not isinstance(prompt_tokens, int)
            or not isinstance(completion_tokens, int)
            or prompt_tokens < 0
            or completion_tokens < 0
        ):
            raise AgentError("MODEL_RESPONSE_INVALID", "模型Token统计无效")
        return prompt_tokens, completion_tokens

    @staticmethod
    def _urllib_transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> tuple[Mapping[str, Any], str | None]:
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                content = response.read()
                request_id = response.headers.get("x-request-id")
        except HTTPError as exc:
            if exc.code == 429:
                code = "MODEL_RATE_LIMITED"
            elif 500 <= exc.code:
                code = "MODEL_SERVICE_UNAVAILABLE"
            else:
                code = "MODEL_REQUEST_REJECTED"
            details: dict[str, object] = {"status": exc.code}
            try:
                error_payload = json.loads(exc.read())
                if isinstance(error_payload, Mapping):
                    provider_code = error_payload.get("code")
                    request_id = error_payload.get("request_id")
                    if isinstance(provider_code, str):
                        details["provider_code"] = provider_code
                    if isinstance(request_id, str):
                        details["request_id"] = request_id
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            raise AgentError(code, "模型服务返回错误", details=details) from exc
        except TimeoutError as exc:
            raise AgentError("MODEL_TIMEOUT", "模型服务调用超时") from exc
        except URLError as exc:
            raise AgentError("MODEL_SERVICE_UNAVAILABLE", "模型服务不可用") from exc
        try:
            payload_value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AgentError("MODEL_RESPONSE_INVALID", "模型响应不是JSON") from exc
        if not isinstance(payload_value, Mapping):
            raise AgentError("MODEL_RESPONSE_INVALID", "模型响应结构无效")
        return payload_value, request_id


def _optional_bool(value: str | None) -> bool | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("LLM_ENABLE_THINKING must be true or false")
