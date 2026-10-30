"""Optional, opt-in contextual POS tagging for the shared pipeline.

POS tagging is intentionally separate from stable token classification. The
canonical pipeline does not instantiate this class.
"""

from __future__ import annotations

from collections.abc import Sequence

from .models import ClassifiedToken


POS_TAGS = frozenset(
    {
        "pos:noun",
        "pos:verb",
        "pos:adjective",
        "pos:adverb",
        "pos:determiner",
        "pos:conjunction",
        "pos:adposition",
        "pos:pronoun",
        "pos:particle",
        "pos:other",
    }
)


def _coarse_pos(treebank_tag: str) -> str:
    if treebank_tag.startswith("NN"):
        return "pos:noun"
    if treebank_tag.startswith("VB"):
        return "pos:verb"
    if treebank_tag.startswith("JJ"):
        return "pos:adjective"
    if treebank_tag.startswith("RB"):
        return "pos:adverb"
    if treebank_tag == "DT":
        return "pos:determiner"
    if treebank_tag == "CC":
        return "pos:conjunction"
    if treebank_tag == "IN":
        return "pos:adposition"
    if treebank_tag.startswith("PRP") or treebank_tag.startswith("WP"):
        return "pos:pronoun"
    if treebank_tag in {"RP", "TO"}:
        return "pos:particle"
    return "pos:other"


class PosTagger:
    """Add namespaced NLTK POS tags to word occurrences only."""

    VERSION = "nltk-treebank-coarse-v1"

    def tag(self, tokens: Sequence[ClassifiedToken]) -> list[ClassifiedToken]:
        word_positions = [
            index for index, token in enumerate(tokens) if "word" in token.tags
        ]
        if not word_positions:
            return list(tokens)
        word_terms = [tokens[index].term for index in word_positions]
        try:
            import nltk

            tagged = nltk.pos_tag(word_terms)
        except LookupError as exc:
            raise RuntimeError(
                "NLTK POS data are not installed. Run "
                "`python -m nltk.downloader averaged_perceptron_tagger`."
            ) from exc

        result = list(tokens)
        for index, (_, treebank_tag) in zip(word_positions, tagged, strict=True):
            token = result[index]
            result[index] = ClassifiedToken(
                term=token.term,
                tags=token.tags | {_coarse_pos(treebank_tag)},
            )
        return result

    def fingerprint(self) -> str:
        return f"nltk-pos|{self.VERSION}"
