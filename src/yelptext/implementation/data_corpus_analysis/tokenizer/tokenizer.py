"""Regex-based tokenization for the shared implementation.

Tokenization deliberately does not depend on a vocabulary. Vocabulary lookup,
type filtering, and optional POS tagging are separate pipeline stages.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass

try:  # Keep Group A's existing file-based analysis scripts working.
    from .models import TokenSpan
except ImportError:  # pragma: no cover - compatibility for direct file loading
    from models import TokenSpan


TOKENIZER_VERSION = "2.0.0"

URL_PATTERN = r"(?:https?://|www\.)[^\s<>()]+"
EMAIL_PATTERN = r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+"
EMOTICON_PATTERN = (
    r"(?:¯\\_\(ツ\)_/¯|\^_[\^~]|[oO]_[oO]|"
    r"[xX][dD]|[Tt]_[Tt]|\._\.|[:;=8][\-^']?[)(/\\DPpOo])"
)
NUMBER_PATTERN = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?(?:/\d+)?)"
QUANTITY_PATTERN = rf"(?:{NUMBER_PATTERN}\+)"
MONEY_PATTERN = (
    rf"(?:[$€£¥][ \t]?{NUMBER_PATTERN}|"
    rf"{NUMBER_PATTERN}[$€£¥]|"
    rf"{NUMBER_PATTERN}¢)"
)
PERCENTAGE_PATTERN = rf"(?:{NUMBER_PATTERN}\+?[ \t]?%)"
TEMPERATURE_PATTERN = rf"(?:{NUMBER_PATTERN}°[fFcC]?)"
NUMERIC_TOKEN_PATTERN = (
    rf"(?:[$€£¥][ \t]?{NUMBER_PATTERN}|"
    rf"{NUMBER_PATTERN}(?:[$€£¥¢]|\+?[ \t]?%|°[fFcC]?|\+)?)"
)
HASHTAG_PATTERN = r"#[^\W\d_]\w*"
WORD_PATTERN = r"[^\W\d_]+(?:'[^\W\d_]+)*(?:')?"

# The emoji expression covers flags, keycaps, skin tones, variation selectors,
# and zero-width-joiner sequences without treating every astral character as emoji.
_EMOJI_BASE = (
    r"[\u00a9\u00ae\u203c\u2049\u2122\u2139\u2194-\u2199"
    r"\u21a9-\u21aa\u231a-\u231b\u2328\u23cf\u23e9-\u23f3"
    r"\u23f8-\u23fa\u24c2\u25aa-\u25ab\u25b6\u25c0"
    r"\u25fb-\u25fe\u2600-\u27bf\u2934-\u2935\u2b05-\u2b07"
    r"\u2b1b-\u2b1c\u2b50\u2b55\u3030\u303d\u3297\u3299"
    r"\U0001F000-\U0001FAFF]"
)
_EMOJI_MODIFIER = r"[\U0001F3FB-\U0001F3FF]"
_EMOJI_COMPONENT = rf"{_EMOJI_BASE}\ufe0f?{_EMOJI_MODIFIER}?"
EMOJI_PATTERN = (
    rf"(?:[\U0001F1E6-\U0001F1FF]{{2}}|"
    rf"[0-9#*]\ufe0f?\u20e3|"
    rf"{_EMOJI_COMPONENT}(?:\u200d{_EMOJI_COMPONENT})*)"
)

TOKEN_PATTERN = re.compile(
    "|".join(
        (
            URL_PATTERN,
            EMAIL_PATTERN,
            EMOTICON_PATTERN,
            EMOJI_PATTERN,
            NUMERIC_TOKEN_PATTERN,
            HASHTAG_PATTERN,
            WORD_PATTERN,
            r"[!?#]",
        )
    ),
    flags=re.IGNORECASE | re.UNICODE,
)

EMOJI_REGEX = re.compile(rf"^(?:{EMOJI_PATTERN})$", re.UNICODE)
_NORMALIZATION_TRANSLATION = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "`": "'",
        "´": "'",
        "？": "?",
        "！": "!",
        "＃": "#",
    }
)
_CURRENCY_PREFIXES = frozenset("$€£¥")


@dataclass(frozen=True, slots=True)
class TokenizerConfig:
    lowercase: bool = True
    normalize_unicode: bool = True
    normalize_apostrophes: bool = True
    normalize_width_punctuation: bool = True


class RegexTokenizer:
    """Deterministic tokenizer whose output is independent of corpus state."""

    def __init__(self, config: TokenizerConfig | None = None) -> None:
        self.config = config or TokenizerConfig()

    def normalize(self, text: str) -> str:
        if self.config.normalize_unicode:
            text = unicodedata.normalize("NFC", text)
        if self.config.normalize_apostrophes and self.config.normalize_width_punctuation:
            text = text.translate(_NORMALIZATION_TRANSLATION)
        elif self.config.normalize_apostrophes:
            text = text.translate(str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"}))
        elif self.config.normalize_width_punctuation:
            text = text.translate(str.maketrans({"？": "?", "！": "!", "＃": "#"}))
        if self.config.lowercase:
            text = text.lower()
        return text

    def tokenize(self, text: str) -> list[str]:
        if not text:
            return []

        normalized = self.normalize(text)
        tokens: list[str] = []
        for match in TOKEN_PATTERN.finditer(normalized):
            token = match.group(0)
            is_url = (
                token.startswith(("http://", "https://", "www."))
                if self.config.lowercase
                else token.lower().startswith(("http://", "https://", "www."))
            )
            if is_url:
                stripped = token.rstrip(".,!?;:")
                suffix = token[len(stripped) :]
                if stripped:
                    tokens.append(stripped)
                tokens.extend(char for char in suffix if char in "!?")
                continue
            if token[0] in _CURRENCY_PREFIXES:
                token = token.replace(" ", "").replace("\t", "")
            elif token[-1] in _CURRENCY_PREFIXES and token[0].isdigit():
                token = token[-1] + token[:-1].replace(" ", "").replace("\t", "")
            elif token.endswith(("%", "¢")):
                token = token.replace(" ", "").replace("\t", "")
            elif token.endswith("'"):
                token = token[:-1]
            tokens.append(token)
        return tokens

    def tokenize_with_spans(self, text: str) -> list[TokenSpan]:
        """Return terms and offsets for auditing against normalized text."""

        if not text:
            return []

        normalized = self.normalize(text)
        tokens: list[TokenSpan] = []
        for match in TOKEN_PATTERN.finditer(normalized):
            token = match.group(0)
            is_url = (
                token.startswith(("http://", "https://", "www."))
                if self.config.lowercase
                else token.lower().startswith(("http://", "https://", "www."))
            )
            if is_url:
                # Sentence punctuation is not part of a URL. Preserve ! and ? as
                # separate tokens because the current tokenizer policy keeps them.
                stripped = token.rstrip(".,!?;:")
                suffix = token[len(stripped) :]
                if stripped:
                    tokens.append(
                        TokenSpan(stripped, match.start(), match.start() + len(stripped))
                    )
                for offset, char in enumerate(suffix, start=len(stripped)):
                    if char in "!?":
                        start = match.start() + offset
                        tokens.append(TokenSpan(char, start, start + 1))
            else:
                if token[0] in _CURRENCY_PREFIXES:
                    token = token.replace(" ", "").replace("\t", "")
                elif token[-1] in _CURRENCY_PREFIXES and token[0].isdigit():
                    token = token[-1] + token[:-1].replace(" ", "").replace("\t", "")
                elif token.endswith(("%", "¢")):
                    token = token.replace(" ", "").replace("\t", "")
                elif token.endswith("'"):
                    token = token[:-1]
                tokens.append(TokenSpan(token, match.start(), match.end()))
        return tokens

    def fingerprint(self) -> str:
        payload = {
            "version": TOKENIZER_VERSION,
            "config": asdict(self.config),
        }
        return "regex-tokenizer|" + json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )


def our_tokenizer(text: str, skiptype: list[str] | None = None) -> list[str]:
    """Backward-compatible facade for Group A's original function."""

    tokenizer = RegexTokenizer()
    tokens = tokenizer.tokenize(text)
    if not skiptype:
        return tokens

    from .classification import TokenClassifier, TokenFilter

    classified = TokenClassifier().classify(tokens)
    return [item.term for item in TokenFilter(skiptype).filter(classified)]
