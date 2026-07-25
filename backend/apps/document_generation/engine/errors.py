from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import GenerationTrace


class AgentError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})


class SourceUnsupportedError(AgentError):
    def __init__(self, message: str) -> None:
        super().__init__("SOURCE_UNSUPPORTED", message)


class SourcePurposeMismatchError(AgentError):
    def __init__(self, message: str) -> None:
        super().__init__("SOURCE_PURPOSE_MISMATCH", message)


class TemplateInvalidError(AgentError):
    def __init__(self, message: str) -> None:
        super().__init__("TEMPLATE_INVALID", message)


class FactsIncompleteError(AgentError):
    def __init__(self, missing_fields: list[str]) -> None:
        super().__init__(
            "FACTS_INCOMPLETE",
            "缺少入场四措两案必填事实",
            details={"missing_fields": missing_fields},
        )


class IdempotencyConflictError(AgentError):
    def __init__(self) -> None:
        super().__init__("IDEMPOTENCY_CONFLICT", "同一幂等键对应了不同输入")


class WorkflowExecutionError(AgentError):
    def __init__(self, cause: AgentError, trace: GenerationTrace) -> None:
        super().__init__(cause.code, cause.message, details=cause.details)
        self.trace = trace
        self.__cause__ = cause
