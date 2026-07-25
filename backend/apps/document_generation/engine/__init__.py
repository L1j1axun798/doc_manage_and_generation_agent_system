"""Pure-Python core for the entry four-measures-two-plans Agent."""

from .contracts import (
    DOCUMENT_PURPOSE,
    ConfirmedFact,
    FactCandidate,
    GeneratedSection,
    GenerationRequest,
    GenerationResult,
    GenerationTrace,
    ParsedBlock,
    ParsedDocument,
    SourceDocument,
    SourceLocator,
)
from .orchestrator import GenerationOrchestrator

__all__ = [
    "DOCUMENT_PURPOSE",
    "ConfirmedFact",
    "FactCandidate",
    "GeneratedSection",
    "GenerationOrchestrator",
    "GenerationRequest",
    "GenerationResult",
    "GenerationTrace",
    "ParsedBlock",
    "ParsedDocument",
    "SourceDocument",
    "SourceLocator",
]
