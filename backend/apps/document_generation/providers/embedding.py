from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_fixed

from apps.document_generation.engine.errors import AgentError

EmbeddingTransport = Callable[
    [str, Mapping[str, str], Mapping[str, object], float],
    tuple[Mapping[str, Any], str | None],
]


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    base_url: str
    api_key: str
    model_alias: str
    dimension: int
    timeout_seconds: float
    batch_size: int = 10
    max_attempts: int = 3
    retry_wait_seconds: float = 0.5

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ValueError("EMBEDDING_BASE_URL must use HTTPS")
        if not self.api_key:
            raise ValueError("EMBEDDING_API_KEY is required")
        if not self.model_alias:
            raise ValueError("EMBEDDING_MODEL is required")
        if self.dimension <= 0 or self.timeout_seconds <= 0:
            raise ValueError("Embedding dimension and timeout must be positive")
        if not 1 <= self.batch_size <= 10:
            raise ValueError("Embedding batch size must be between 1 and 10")
        if self.max_attempts <= 0 or self.retry_wait_seconds < 0:
            raise ValueError("Embedding retry configuration is invalid")


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        config: EmbeddingProviderConfig,
        *,
        transport: EmbeddingTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or self._urllib_transport
        self.last_request_id: str | None = None

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        transport: EmbeddingTransport | None = None,
    ) -> OpenAICompatibleEmbeddingProvider:
        values = os.environ if env is None else env
        config = EmbeddingProviderConfig(
            base_url=values.get("EMBEDDING_BASE_URL", ""),
            api_key=values.get("EMBEDDING_API_KEY", ""),
            model_alias=values.get("EMBEDDING_MODEL", "text-embedding-v4"),
            dimension=int(values.get("EMBEDDING_DIMENSION", "1024")),
            timeout_seconds=float(values.get("EMBEDDING_TIMEOUT_SECONDS", "30")),
            batch_size=int(values.get("EMBEDDING_BATCH_SIZE", "10")),
            max_attempts=int(values.get("EMBEDDING_MAX_ATTEMPTS", "3")),
            retry_wait_seconds=float(values.get("EMBEDDING_RETRY_WAIT_SECONDS", "0.5")),
        )
        return cls(config, transport=transport)

    @property
    def model_alias(self) -> str:
        return self.config.model_alias

    @property
    def dimension(self) -> int:
        return self.config.dimension

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if not texts:
            return ()
        if any(not text.strip() for text in texts):
            raise AgentError("EMBEDDING_INPUT_INVALID", "Embedding输入不得为空")
        vectors: list[tuple[float, ...]] = []
        for start in range(0, len(texts), self.config.batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self.config.batch_size]))
        return tuple(vectors)

    def _embed_batch(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        endpoint = self.config.base_url.rstrip("/")
        if not endpoint.endswith("/embeddings"):
            endpoint += "/embeddings"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload: Mapping[str, object] = {
            "model": self.config.model_alias,
            "input": list(texts),
            "dimensions": self.config.dimension,
            "encoding_format": "float",
        }
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
                "EMBEDDING_REQUEST_FAILED",
                "Embedding服务调用失败",
                details={"exception_type": type(exc).__name__},
            ) from exc
        if response is None:
            raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding服务没有返回响应")
        self.last_request_id = request_id
        data = response.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding响应数量不一致")
        if any(not isinstance(item, Mapping) for item in data):
            raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding响应条目结构无效")
        indices = [item.get("index") for item in data]
        if any(not isinstance(index, int) for index in indices):
            raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding响应索引无效")
        if set(indices) != set(range(len(texts))) or len(set(indices)) != len(indices):
            raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding响应索引无效")
        ordered = sorted(data, key=lambda item: item.get("index", -1))
        vectors: list[tuple[float, ...]] = []
        for item in ordered:
            vector = item.get("embedding")
            if not isinstance(vector, list) or len(vector) != self.dimension:
                raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding响应维度不一致")
            try:
                normalized_vector = tuple(float(value) for value in vector)
            except (TypeError, ValueError) as exc:
                raise AgentError(
                    "EMBEDDING_RESPONSE_INVALID",
                    "Embedding响应包含非数值向量",
                ) from exc
            if any(not math.isfinite(value) for value in normalized_vector):
                raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding响应包含非有限数值")
            vectors.append(normalized_vector)
        return tuple(vectors)

    @staticmethod
    def _is_retryable(exception: BaseException) -> bool:
        return isinstance(exception, AgentError) and exception.code in {
            "EMBEDDING_RATE_LIMITED",
            "EMBEDDING_SERVICE_UNAVAILABLE",
            "EMBEDDING_TIMEOUT",
        }

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
                code = "EMBEDDING_RATE_LIMITED"
            elif 500 <= exc.code:
                code = "EMBEDDING_SERVICE_UNAVAILABLE"
            else:
                code = "EMBEDDING_REQUEST_REJECTED"
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
            raise AgentError(code, "Embedding服务返回错误", details=details) from exc
        except TimeoutError as exc:
            raise AgentError("EMBEDDING_TIMEOUT", "Embedding服务调用超时") from exc
        except URLError as exc:
            raise AgentError("EMBEDDING_SERVICE_UNAVAILABLE", "Embedding服务不可用") from exc
        try:
            payload_value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding响应不是JSON") from exc
        if not isinstance(payload_value, Mapping):
            raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding响应结构无效")
        return payload_value, request_id
