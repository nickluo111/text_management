"""Compatibility import surface for the vocabulary API.

The previous module stored process-wide mutable vocabulary state. Callers now own
an explicit ``Vocabulary``/``VocabularyLookup`` instance instead.
"""

from .vocabulary import (
    UNK_ID,
    UNK_TERM,
    Vocabulary,
    VocabularyEntry,
    VocabularyLookup,
)

__all__ = [
    "UNK_ID",
    "UNK_TERM",
    "Vocabulary",
    "VocabularyEntry",
    "VocabularyLookup",
]
