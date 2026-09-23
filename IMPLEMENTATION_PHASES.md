# RiskLens Implementation Phases

RiskLens follows a simple branch workflow:

```text
main
  <- dev
      <- feature branches
```

Feature branches merge into `dev`; validated work merges from `dev` into `main`. The repository owner performs commits and merges. Each phase below identifies whether a feature branch is recommended and provides a suggested branch and commit message.

## Phase 0 — Repository and data foundation

### Objective

Make the current ingestion path reproducible and define the source-of-truth and manifest contract.

### Stages

1. Consolidate duplicate CIK and CSV-building logic.
2. Treat raw extracted JSON as immutable input.
3. Validate required filing metadata and source links.
4. Add source hashes, parser/normalization versions, and record counts to a manifest.
5. Keep CSV as an export while preparing normalized tables as the modeling boundary.

### Outputs

- Reproducible ingestion command.
- Filing manifest.
- Validation diagnostics.
- Documented raw-to-derived data flow.

### Tests and validation

- Valid and malformed JSON records.
- Duplicate filings and missing metadata.
- Empty Item 1A values.
- Source URL and filename consistency.
- Repeat-run determinism.

### Exit criteria

The same raw inputs produce the same manifest and filing records, and raw data is never silently overwritten.

**Feature branch:** Yes — `feature/data-foundation`  
**Suggested commit:** `feat: establish reproducible filing data foundation`

## Phase 1 — Structured Item 1A parsing

### Objective

Convert full Item 1A text into traceable filing, block, and sentence records.

### Stages

1. Extract `item_1A` from each raw filing.
2. Normalize line endings only and preserve the original string.
3. Detect headings and maintain heading paths.
4. Split paragraphs, bullet groups, and list items.
5. Segment sentences with SEC-aware rules.
6. Attach half-open source offsets and parser diagnostics.
7. Generate stable IDs and export normalized tables.

### Outputs

- Filing records.
- Block records.
- Sentence records.
- Parser diagnostics.
- Dataset profiling report.

### Tests and validation

- Uppercase and title-like headings.
- Numbered and bulleted lists.
- `U.S.`, `Inc.`, `e.g.`, decimals, percentages, citations, and parentheses.
- Source substring recovery from every offset.
- Stable IDs on repeated runs.
- Boundary uncertainty reporting.

### Exit criteria

Every sentence maps to exactly one filing and block, can be recovered from the original text, and is inspectable under its heading path.

**Feature branch:** Yes — `feature/item1a-parser`  
**Suggested commit:** `feat: add deterministic Item 1A block and sentence parser`

## Phase 2 — Annotation and gold set

### Objective

Create a reliable human-labeled evaluation set before using generated labels.

### Stages

1. Version definitions for `RISK_STATEMENT`, `MITIGATION`, `SUPPORTED_CONTEXT`, and `BOILERPLATE`.
2. Define multi-label and `NONE_OTHER` rules.
3. Sample approximately 500 sentences across companies, industries, headings, lengths, bullets, and ambiguity.
4. Annotate and adjudicate disagreements.
5. Split by company into training, development, and held-out test sets.
6. Freeze the test set and record the split manifest.

### Outputs

- Annotation guidelines.
- Gold annotations.
- Company split manifest.
- Label prevalence and disagreement report.

### Tests and validation

- No company leakage across splits.
- Every annotation references a valid sentence.
- Labels are valid and independently represented.
- Adjudicated examples cover mixed and ambiguous cases.

### Exit criteria

The held-out test set is isolated from prompt examples and synthetic labels, with documented annotation rules and provenance.

**Feature branch:** Yes — `feature/gold-annotations`  
**Suggested commit:** `data: add versioned Item 1A gold annotation set`

## Phase 3 — Transparent baseline

### Objective

Establish a simple, measurable classification baseline.

### Stages

1. Build TF-IDF features from sentence text.
2. Train one-vs-rest logistic regression models.
3. Optionally compare a linear SVM.
4. Calibrate scores where practical.
5. Save preprocessing, labels, configuration, and model version.
6. Produce quantitative and qualitative error reports.
7. Measure precision at analyst-facing thresholds.

### Outputs

- Baseline model artifact.
- Evaluation report.
- Threshold report.
- False-positive and false-negative examples.

### Tests and validation

- Company-held-out evaluation.
- Probability range and schema validation.
- Reproducible training with fixed configuration.
- Per-label precision, recall, F1, PR-AUC, calibration, and exact multi-label match.

### Exit criteria

The baseline can be trained and evaluated repeatably, and its errors are understandable enough to guide parser or label improvements.

**Feature branch:** Yes — `feature/tfidf-baseline`  
**Suggested commit:** `feat: add multi-label TF-IDF classification baseline`

## Phase 4 — Zero-shot and few-shot comparison

### Objective

Determine whether LLM classification adds enough value to justify cost and complexity.

### Stages

1. Define and version a structured-output prompt.
2. Run zero-shot classification on the fixed evaluation sample.
3. Run few-shot classification using only training/development examples.
4. Validate and store parsed outputs, raw responses, model metadata, and prompt version.
5. Compare with the TF-IDF baseline on identical test data.

### Outputs

- Zero-shot evaluation.
- Few-shot evaluation.
- Cost/latency and invalid-output report.
- Comparative model report.

### Tests and validation

- Fixed labels and prompts.
- No held-out test examples in demonstrations.
- Invalid structured responses counted explicitly.
- Per-label and high-confidence precision comparisons.

### Exit criteria

The selected approach is justified by analyst usefulness, reliability, and cost—not by aggregate accuracy alone.

**Feature branch:** Yes — `feature/llm-evaluation`  
**Suggested commit:** `feat: benchmark zero-shot and few-shot classification`

## Phase 5 — Synthetic data, only if justified

### Objective

Increase training volume only when evaluation shows that more data is necessary.

### Stages

1. Generate candidate labels for unlabeled sentences.
2. Store synthetic labels separately with generator and prompt metadata.
3. Human-audit a stratified sample.
4. Remove or correct systematic errors.
5. Compare models with and without synthetic data on the untouched test set.

### Outputs

- Synthetic annotation dataset.
- Audit report.
- Ablation comparison.

### Tests and validation

- No synthetic examples in the gold test.
- Synthetic provenance on every record.
- Label-specific audit results.
- Held-out improvement or analyst-precision improvement.

### Exit criteria

Synthetic data is retained only if it produces measurable held-out or analyst-facing benefit.

**Feature branch:** Yes, only if approved — `feature/synthetic-labels`  
**Suggested commit:** `data: add audited synthetic training annotations`

## Phase 6 — Analyst-facing evidence output

### Objective

Make predictions useful for review before adding a vector database.

### Stages

1. Classify one company filing at a time.
2. Store all label probabilities and model metadata.
3. Filter and rank high-confidence evidence at presentation time.
4. Group findings under block headings.
5. Show nearby context sentences on demand.
6. Add low-confidence and contradictory cases to a review queue.
7. Export analyst results for review and future annotation.

### Outputs

- Sentence prediction dataset.
- Analyst evidence report.
- Configurable threshold output.
- Review queue.

### Tests and validation

- Every result links to source text and offsets.
- Threshold changes do not require re-inference.
- Risk and mitigation can both be displayed for one sentence.
- Repeated boilerplate can be identified and de-emphasized.

### Exit criteria

An analyst can understand why a sentence was surfaced and can trace it to its original filing and block.

**Feature branch:** Yes — `feature/analyst-evidence-output`  
**Suggested commit:** `feat: add traceable analyst evidence output`

## Phase 7 — Embeddings and hybrid retrieval

### Objective

Support semantic search over validated risk and mitigation evidence.

### Stages

1. Define analyst query examples and retrieval acceptance cases.
2. Embed relevant sentence records while retaining all metadata.
3. Add keyword and semantic search.
4. Add filters for company, period, label, industry, and confidence.
5. Group or penalize near-duplicate boilerplate.
6. Introduce Qdrant only after the data and retrieval contracts stabilize.
7. Test persistence, re-indexing, and embedding-version compatibility.

### Outputs

- Embedding index.
- Hybrid retrieval interface.
- Query evaluation set.
- Source-evidence search results.

### Tests and validation

- Correct metadata filtering.
- Source text and block context fidelity.
- Semantic, keyword, and hybrid retrieval comparison.
- Re-indexing without losing sentence identity.
- No unsupported generated claims in results.

### Exit criteria

Representative analyst queries return relevant, traceable source sentences with predictable filters and manageable duplication.

**Feature branch:** Yes — `feature/hybrid-retrieval`  
**Suggested commit:** `feat: add validated hybrid risk evidence retrieval`

## Cross-phase rules

- Do not randomly split sentences when company-specific wording can leak.
- Do not treat model-generated labels as ground truth.
- Do not discard low-confidence predictions from storage.
- Do not add entity extraction without a concrete analyst filter or workflow.
- Do not introduce Qdrant before the sentence-level schema is stable.
- Do not begin a later phase until the previous phase’s exit criteria are met.
