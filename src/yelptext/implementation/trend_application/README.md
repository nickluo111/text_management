# Trend and application implementation

- `sentiment.py` streams prepared reviews, applies VADER to original text, and
  maintains sector-period means, class shares, star means, and confidence
  intervals in bounded working memory.
- `pmi.py` computes independent period-level directed window marginals and
  supported PMI rankings for a configured target term.
- `comparisons.py` uses the shared tokenizer and lightweight sentence rules to
  detect review sentences that compare the current business with alternatives.

All three features are exposed through registered CLI commands; notebooks only
present their generated artifacts.
