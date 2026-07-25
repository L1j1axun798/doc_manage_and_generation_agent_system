from __future__ import annotations

from collections.abc import Mapping

import pytest

from apps.document_generation.engine.errors import AgentError
from apps.document_generation.providers.embedding import (
    EmbeddingProviderConfig,
    OpenAICompatibleEmbeddingProvider,
)


def test_openai_compatible_embedding_provider_uses_env_and_preserves_order() -> None:
    captured: dict[str, object] = {}

    def transport(endpoint, headers, payload, timeout):
        captured.update(
            {
                "endpoint": endpoint,
                "authorization": headers["Authorization"],
                "payload": payload,
                "timeout": timeout,
            }
        )
        return (
            {
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
            "request-id-1",
        )

    provider = OpenAICompatibleEmbeddingProvider.from_env(
        {
            "EMBEDDING_BASE_URL": "https://workspace.example.com/compatible-mode/v1",
            "EMBEDDING_API_KEY": "test-key-not-real",
            "EMBEDDING_MODEL": "text-embedding-v4",
            "EMBEDDING_DIMENSION": "2",
            "EMBEDDING_TIMEOUT_SECONDS": "12",
        },
        transport=transport,
    )

    vectors = provider.embed(["文本A", "文本B"])

    assert vectors == ((1.0, 0.0), (0.0, 1.0))
    assert captured["endpoint"] == ("https://workspace.example.com/compatible-mode/v1/embeddings")
    assert captured["authorization"] == "Bearer test-key-not-real"
    assert captured["payload"] == {
        "model": "text-embedding-v4",
        "input": ["文本A", "文本B"],
        "dimensions": 2,
        "encoding_format": "float",
    }
    assert captured["timeout"] == 12
    assert provider.last_request_id == "request-id-1"


@pytest.mark.parametrize(
    ("base_url", "api_key"),
    [
        ("http://insecure.example.com/v1", "key"),
        ("https://secure.example.com/v1", ""),
    ],
)
def test_embedding_config_rejects_insecure_or_missing_secret(
    base_url: str,
    api_key: str,
) -> None:
    with pytest.raises(ValueError):
        EmbeddingProviderConfig(
            base_url=base_url,
            api_key=api_key,
            model_alias="text-embedding-v4",
            dimension=1024,
            timeout_seconds=30,
        )


def test_embedding_provider_rejects_invalid_response_without_logging_secret() -> None:
    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout: float,
    ):
        return {"data": [{"index": 0, "embedding": [1.0]}]}, None

    provider = OpenAICompatibleEmbeddingProvider(
        EmbeddingProviderConfig(
            base_url="https://workspace.example.com/v1",
            api_key="test-key-not-real",
            model_alias="text-embedding-v4",
            dimension=2,
            timeout_seconds=30,
        ),
        transport=transport,
    )

    with pytest.raises(AgentError) as captured:
        provider.embed(["文本"])

    assert captured.value.code == "EMBEDDING_RESPONSE_INVALID"
    assert "test-key-not-real" not in str(captured.value)


@pytest.mark.parametrize(
    "data",
    [
        ["not-an-object"],
        [{"index": 0, "embedding": [1.0, 0.0]}, {"index": 0, "embedding": [0.0, 1.0]}],
        [{"index": 0, "embedding": [float("nan"), 0.0]}],
    ],
)
def test_embedding_provider_rejects_malformed_indices_and_non_finite_values(
    data: list[object],
) -> None:
    def transport(
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout: float,
    ):
        return {"data": data}, None

    provider = OpenAICompatibleEmbeddingProvider(
        EmbeddingProviderConfig(
            base_url="https://workspace.example.com/v1",
            api_key="test-key-not-real",
            model_alias="text-embedding-v4",
            dimension=2,
            timeout_seconds=30,
        ),
        transport=transport,
    )
    texts = ["文本A", "文本B"] if len(data) == 2 else ["文本"]

    with pytest.raises(AgentError) as captured:
        provider.embed(texts)

    assert captured.value.code == "EMBEDDING_RESPONSE_INVALID"


def test_embedding_provider_does_not_replace_explicit_empty_env(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://unexpected.example.com/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "unexpected-key")

    with pytest.raises(ValueError):
        OpenAICompatibleEmbeddingProvider.from_env({})


def test_embedding_provider_batches_to_service_limit_and_preserves_global_order() -> None:
    batches: list[list[str]] = []

    def transport(endpoint, headers, payload, timeout):
        values = list(payload["input"])
        batches.append(values)
        return (
            {
                "data": [
                    {"index": index, "embedding": [float(index), 1.0]}
                    for index, _ in enumerate(values)
                ]
            },
            f"request-{len(batches)}",
        )

    provider = OpenAICompatibleEmbeddingProvider(
        EmbeddingProviderConfig(
            base_url="https://workspace.example.com/v1",
            api_key="test-key-not-real",
            model_alias="text-embedding-v4",
            dimension=2,
            timeout_seconds=30,
            batch_size=2,
        ),
        transport=transport,
    )

    vectors = provider.embed(["A", "B", "C"])

    assert batches == [["A", "B"], ["C"]]
    assert vectors == ((0.0, 1.0), (1.0, 1.0), (0.0, 1.0))
    assert provider.last_request_id == "request-2"


def test_embedding_provider_retries_transient_failure() -> None:
    attempts = 0

    def transport(endpoint, headers, payload, timeout):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AgentError("EMBEDDING_SERVICE_UNAVAILABLE", "temporary")
        return {"data": [{"index": 0, "embedding": [1.0, 0.0]}]}, "request-2"

    provider = OpenAICompatibleEmbeddingProvider(
        EmbeddingProviderConfig(
            base_url="https://workspace.example.com/v1",
            api_key="test-key-not-real",
            model_alias="text-embedding-v4",
            dimension=2,
            timeout_seconds=30,
            retry_wait_seconds=0,
        ),
        transport=transport,
    )

    assert provider.embed(["A"]) == ((1.0, 0.0),)
    assert attempts == 2
