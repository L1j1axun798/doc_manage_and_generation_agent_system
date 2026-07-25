from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import environ  # noqa: E402

from apps.document_generation.engine.errors import AgentError  # noqa: E402
from apps.document_generation.providers.embedding import (  # noqa: E402
    OpenAICompatibleEmbeddingProvider,
)
from apps.document_generation.providers.health import check_providers  # noqa: E402
from apps.document_generation.providers.llm import (  # noqa: E402
    OpenAICompatibleLLMProvider,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Document Agent LLM and Embedding connectivity without printing secrets."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=BACKEND_ROOT / ".env",
    )
    args = parser.parse_args(argv)
    env_file = args.env_file.resolve()
    if not env_file.is_file():
        print(f"[FAIL] provider env file does not exist: {env_file}")
        return 1
    environ.Env.read_env(env_file, overwrite=False)
    try:
        result = check_providers(
            llm_provider=OpenAICompatibleLLMProvider.from_env(),
            embedding_provider=OpenAICompatibleEmbeddingProvider.from_env(),
        )
    except AgentError as exc:
        print(
            "[FAIL] Document Agent provider healthcheck: "
            f"code={exc.code}, details={exc.details}"
        )
        return 1
    except Exception as exc:
        print(f"[FAIL] Document Agent provider healthcheck: {type(exc).__name__}: {exc}")
        return 1
    print(
        "[PASS] Document Agent providers: "
        f"llm={result['llm_model']}, embedding={result['embedding_model']}, "
        f"dimension={result['embedding_dimension']}, "
        f"elapsed_seconds={result['elapsed_seconds']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
