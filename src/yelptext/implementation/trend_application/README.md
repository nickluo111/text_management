# Trend and application implementation

- `sentiment.py` streams prepared reviews, applies VADER to original text, and
  maintains sector-period means, class shares, star means, and confidence
  intervals in bounded working memory.
- `pmi.py` computes independent period-level directed window marginals and
  supported PMI rankings for a configured target term.

The comparison application is the remaining component and will be added here
behind the public interface and registered CLI command.
