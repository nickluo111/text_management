"""Lazy access to lexical resources used by shared token classification."""

from __future__ import annotations

from functools import lru_cache


CONJUNCTIONS = frozenset(
    {"and", "or", "but", "if", "because", "so", "as", "than", "while", "whereas"}
)


@lru_cache(maxsize=1)
def load_nltk_stop_words() -> frozenset[str]:
    """Load NLTK's English stopword list without downloading at import time."""

    try:
        from nltk.corpus import stopwords

        words = stopwords.words("english")
    except LookupError as exc:
        raise RuntimeError(
            "NLTK stopwords are not installed. Run "
            "`python -m nltk.downloader stopwords` during environment setup."
        ) from exc
    return frozenset(word.casefold() for word in words)


def __getattr__(name: str) -> frozenset[str]:
    """Lazily provide the two names used by the original Group A scripts."""

    if name == "NLTK_STOPWORDS":
        return load_nltk_stop_words()
    if name == "STOP_WORDS":
        return load_nltk_stop_words() - CONJUNCTIONS
    raise AttributeError(name)
