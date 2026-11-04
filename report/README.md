# Integrated Report — Markdown Review Draft

This directory is the content-review version of the report. It deliberately remains in Markdown until the methods, results, interpretation, and contribution record are approved. The final LaTeX document will use the same section order and one shared bibliography.

## Abstract (draft)

This project builds a reproducible text-management and analysis pipeline for the Yelp Open Dataset. A custom Yelp-oriented tokenizer supports full-corpus Zipf and Heaps analyses, a persistent review-level inverted index with TF-IDF cosine and BM25 ranking, and longitudinal sentiment and term-association analysis. The full corpus contains 6,990,280 reviews; search evaluation uses a deterministic 50,000-review sample. Zipf behavior is strongest in the high-frequency vocabulary, while Heaps fitting shows sublinear vocabulary growth with exponent 0.533. TF-IDF and BM25 produce materially different Top-10 rankings across six exploratory queries, particularly because of document-length normalization and OR matching. Trend analysis finds comparatively stable positive sentiment for Italian Restaurants, a marked decline for Fast Food, and a persistent but gradually reweighted vocabulary around the target term `service`. Results are descriptive and reproducible, with explicit limitations on relevance evaluation, causal interpretation, and incomplete 2022 data.

## Contributions

The final report should contain this contribution record once, before the technical sections. It should not be repeated in Sections 3.1--3.3.

| Member / team | Contribution |
|---|---|
| Group A — names to be supplied | Shared reviewer/tokenizer integration; tokenizer evaluation; full-corpus CF/DF vocabulary; Zipf and Heaps implementation, experiments, and presentation artifacts. |
| Group B — names to be supplied | Persistent inverted index; TF-IDF cosine and BM25 ranking; validation tests; six-query comparison and BM25 sensitivity analysis. |
| Group C — names to be supplied | Sector sentiment analysis; PMI term co-occurrence drift; window/support sensitivity analysis; trend figures and interpretation. |
| Whole group | System integration, configuration, CLI validation, notebook presentation, report review, and final editing. |

## Technical Sections

1. [3.1 Dataset Analysis: Empirical Laws and Custom Tokenization](3.1_dataset_analysis.md) — based on Group A's supplied report, with its reserved tokenizer subsection completed from the validated tokenizer artifacts.
2. [3.2 Search Engine: TF-IDF Cosine and BM25](3.2_search_engine.md) — based on Group B's supplied report, with current configuration, artifact sizes, test counts, notebook behavior, and reproduction commands synchronized.
3. [3.3 Trend Analysis](3.3_trend_analysis.md) — completes the existing PMI analysis with the full-corpus sector sentiment method, results, uncertainty, limitations, and a combined interpretation.

## Items Needed Before Final Submission

- Replace the Group A/B/C placeholders with member names and agreed individual contributions.
- Confirm the abstract after the three technical sections are approved.
- Deduplicate the three reference lists into one bibliography during LaTeX conversion.
- Apply the required report template and verify the final page limit only after Markdown content is approved.

