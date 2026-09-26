<proposed_plan>

# Phase 2: Annotation and gold evaluation set

Phase 2 creates a reliable, human-labeled dataset for evaluating the later RiskLens classifiers. The dataset will use the sentence as the modeling unit while retaining filing, block, heading-path, source-offset, and parser metadata for context and traceability.

No model training, synthetic labels, embeddings, or Qdrant integration is required in this phase. The labels must be created and reviewed by people before they are used to evaluate zero-shot, few-shot, TF-IDF, or later supervised approaches.

## Stage 1 — Version the annotation definitions

### Problem

The four intended categories can be interpreted differently if their definitions are informal. A sentence may describe a possible loss, explain an existing control, provide context for a risk, or use standard legal disclosure language. Without written definitions, two annotators may assign different labels to the same sentence.

For example:

```text
Our operations may be adversely affected by severe weather, including hurricanes and flooding.
```

This describes a possible adverse event and its consequence, so it is a `RISK_STATEMENT`.

```text
We maintain business continuity plans and backup facilities to help reduce the effect of these events.
```

This describes an action or control intended to reduce a risk, so it is a `MITIGATION`.

```text
The company operates manufacturing facilities in several regions and relies on third-party logistics providers.
```

This may support interpretation of a nearby risk without itself describing a risk or control, so it is `SUPPORTED_CONTEXT`.

```text
This Annual Report contains forward-looking statements that involve risks and uncertainties.
```

This is a recurring legal or disclosure formula and should normally be `BOILERPLATE`.

### Intended solution

Create a versioned annotation guideline that defines each label independently:

- `RISK_STATEMENT`: the sentence identifies an uncertainty, threat, vulnerability, adverse event, potential loss, or negative consequence relevant to the company.
- `MITIGATION`: the sentence identifies an action, control, process, policy, safeguard, insurance arrangement, diversification, contingency, or other measure intended to prevent, reduce, monitor, or respond to a risk.
- `SUPPORTED_CONTEXT`: the sentence provides factual or operational context that helps explain a risk or mitigation but does not itself meet either definition.
- `BOILERPLATE`: the sentence is substantially standardized legal, regulatory, introductory, or repetitive disclosure language with limited company-specific analytical value.
- `NONE_OTHER`: an internal annotation state for a sentence that does not fit the four target categories. It is not a model output category unless the project later decides to expose it.

The guideline will include positive examples, negative examples, boundary cases, and a version identifier. Definitions must be applied to the sentence text first, with its block and heading path available as context.

### Expected output

```text
annotation_guidelines_v1.md
```

The guideline records the label definitions, inclusion and exclusion rules, examples, and version history.

## Stage 2 — Define multi-label and `NONE_OTHER` rules

### Problem

A single sentence can contain more than one useful signal. Forcing every sentence into one mutually exclusive class would lose information and make mixed risk-and-control statements difficult to represent.

For example:

```text
Cybersecurity incidents could disrupt our operations, and we maintain monitoring and response procedures to limit their impact.
```

The first clause describes a risk and the second describes mitigation. Treating the entire sentence as only one class would hide part of its meaning.

### Intended solution

Use independent labels rather than a single categorical value. A sentence may have more than one positive label when both meanings are explicitly present.

Valid combinations include:

- `RISK_STATEMENT` only;
- `MITIGATION` only;
- `SUPPORTED_CONTEXT` only;
- `BOILERPLATE` only;
- `RISK_STATEMENT` + `MITIGATION`;
- `RISK_STATEMENT` + `SUPPORTED_CONTEXT`;
- `MITIGATION` + `SUPPORTED_CONTEXT`;
- `RISK_STATEMENT` + `MITIGATION` + `SUPPORTED_CONTEXT`;
- `NONE_OTHER` when none of the target labels applies.

`BOILERPLATE` should normally stand alone. If a sentence contains a meaningful company-specific risk or mitigation in addition to formulaic language, the annotator should label the meaningful signal and record the rationale rather than automatically assigning `BOILERPLATE`.

Heading information is context, not a label. A sentence under a heading such as `Cybersecurity` is not automatically a risk statement, and a heading such as `Risk Mitigation` is not sufficient by itself to assign `MITIGATION`.

An annotation record should preserve the independent labels and the review rationale:

```json
{
  "sentence_id": "sentence-000123",
  "labels": ["RISK_STATEMENT", "MITIGATION"],
  "none_other": false,
  "guideline_version": "v1",
  "annotator_id": "annotator_01",
  "rationale": "The sentence states a possible disruption and describes response controls."
}
```

### Expected output

The guideline will contain the multi-label policy, precedence guidance for boilerplate, `NONE_OTHER` rules, and examples of mixed sentences. The annotation schema will support zero, one, or several target labels without changing the source sentence record.

## Stage 3 — Sample approximately 500 sentences

### Problem

A purely random sample may overrepresent long ordinary paragraphs and underrepresent headings, bullets, short warnings, parser uncertainty, and sentences that are difficult to classify. A gold set that is easy to annotate will not reveal whether the later system works for the situations analysts actually encounter.

### Intended solution

Create a deterministic, reviewable sample of approximately 500 sentences from the current Phase 1 outputs. Sampling should be stratified across:

- companies and filings;
- industries or available SIC/company metadata;
- heading paths and heading types;
- block types, including headings, paragraphs, bullet groups, and list items;
- sentence length and punctuation patterns;
- inline bullet groups and list-like sentences;
- parser boundary uncertainty;
- heading-candidate decisions and heading reasons;
- sentences likely to contain risk, mitigation, context, boilerplate, and ambiguous cases;
- both ordinary and unusual source-offset or formatting patterns.

The sample must retain its original sentence ID and filing provenance. Sampling must occur before annotation, and it must not rewrite the source filings or derived Phase 1 records.

### Expected output

An annotation-candidate dataset with fields such as:

```json
{
  "sample_id": "sample-000123",
  "sentence_id": "sentence-000123",
  "filing_id": "1002910-10-K-2022",
  "company_name": "Example Corp",
  "heading_path": ["Risk Factors", "Cybersecurity"],
  "block_type": "paragraph",
  "sentence_text": "Cybersecurity incidents could disrupt our operations.",
  "source_start": 18420,
  "source_end": 18478,
  "boundary_uncertain": false,
  "heading_decision": "accepted"
}
```

The sample manifest records the sampling rule, source dataset version, random seed if used, selected sentence IDs, and coverage counts. No labels are added at this stage.

## Stage 4 — Annotate and adjudicate disagreements

### Problem

Risk and mitigation language is often indirect. Annotators may disagree about whether a sentence describes an actual risk, merely provides context, contains a control, or is boilerplate. Disagreement is especially likely for multi-label sentences and sentences with uncertain parser boundaries.

For example:

```text
Our dependence on third-party suppliers could result in delays, although we seek alternative sources where practical.
```

This should be reviewed for both `RISK_STATEMENT` and `MITIGATION`; the final decision should not be made by an arbitrary single-label rule.

### Intended solution

Annotate each sampled sentence using the versioned guideline. Each record should include:

- the stable `sentence_id`;
- the selected labels;
- `NONE_OTHER` status when applicable;
- annotator identity;
- guideline version;
- rationale or notes for ambiguous decisions;
- review status;
- final adjudicated labels where review was required.

Use a primary annotation pass and a second review for multi-label, `NONE_OTHER`, uncertain-boundary, and disputed cases. If two annotations disagree, adjudicate the record and preserve the original annotations and the final decision rather than silently replacing them.

Annotation must be based on the sentence and its available context. The annotator may view the filing, block text, heading path, neighboring sentences, and source offsets, but must not treat a heading as an automatic label.

### Expected output

Versioned annotation records and a disagreement report:

```json
{
  "sentence_id": "sentence-000123",
  "annotator_labels": {
    "annotator_01": ["RISK_STATEMENT"],
    "annotator_02": ["RISK_STATEMENT", "MITIGATION"]
  },
  "adjudicated_labels": ["RISK_STATEMENT", "MITIGATION"],
  "adjudication_status": "resolved",
  "guideline_version": "v1",
  "notes": "The second clause describes seeking alternative suppliers."
}
```

The report should summarize agreement, disagreement types, label prevalence, multi-label frequency, and examples requiring guideline clarification.

## Stage 5 — Split by company for evaluation

### Problem

Splitting individual sentences randomly can place nearly identical wording, company-specific terminology, and repeated disclosures from one company in both training and test sets. This would make performance look better than generalization to an unseen company.

### Intended solution

Split at the company level, never at the individual sentence level. A practical initial arrangement for approximately 14 companies is:

- approximately 8 companies for training;
- approximately 3 companies for development/validation;
- approximately 3 companies for held-out testing.

The exact allocation should preserve reasonable industry and filing-year coverage where possible. Every sentence from a company must remain in the same split. The held-out companies must not be used for prompt examples, guideline examples derived from the test set, synthetic-label generation, threshold selection, or feature tuning.

### Expected output

A split manifest with explicit company membership and dataset provenance:

```json
{
  "split_version": "v1",
  "train_companies": ["Company A", "Company B"],
  "development_companies": ["Company C"],
  "test_companies": ["Company D"],
  "sentence_assignment_rule": "all sentences from one company stay in one split",
  "source_sample_version": "sample-v1"
}
```

The manifest should also record the number of filings, blocks, sentences, and labels in each split so that accidental leakage or severe imbalance can be detected.

## Stage 6 — Freeze the test set and record provenance

### Problem

Evaluation becomes unreliable if test labels, company membership, or annotation rules change while models and prompts are being developed. The test set could also be accidentally used to create examples or synthetic training data.

### Intended solution

Freeze the held-out test sentences, adjudicated labels, company split, source dataset version, and guideline version after review. Changes require a new version rather than an in-place rewrite.

The frozen test set must remain separate from:

- few-shot prompt examples;
- model training data;
- synthetic labels;
- threshold tuning;
- feature selection;
- error-driven reannotation performed after model evaluation.

Record hashes or equivalent provenance references for the source records and annotation artifacts. Validate that every annotation points to an existing sentence and that the sentence text, source offsets, filing ID, company, and heading path remain traceable.

### Expected output

- A versioned gold annotation dataset;
- a frozen company-held-out test set;
- a split and provenance manifest;
- label prevalence and disagreement reports;
- validation results confirming valid IDs, labels, offsets, and company assignments.

## Heading context during annotation

Headings are useful signals for later models, but they are not labels. The annotation interface and exported records should show:

- original heading text;
- normalized heading text;
- hierarchical `heading_path`;
- heading level and type;
- deterministic heading decision and reasons;
- the block and filing containing the sentence.

Annotators should use this information to understand the sentence, while labeling the sentence’s actual content. A sentence under a risk-related heading must not automatically become `RISK_STATEMENT`, and a sentence under a mitigation-related heading must not automatically become `MITIGATION`.

The sample and disagreement reports should retain heading metadata so later evaluation can compare model behavior with and without heading features. Rule-based heading decisions and uncertainty should be treated as reproducible metadata and diagnostics, not as ground-truth labels.

## End-to-end example

### Source context

```text
Heading path: Risk Factors > Cybersecurity
Block type: paragraph
Sentence ID: sentence-000123
Sentence offsets: [18420, 18478)
Sentence: Cybersecurity incidents could disrupt our operations.
```

### Gold annotation

```json
{
  "sentence_id": "sentence-000123",
  "labels": ["RISK_STATEMENT"],
  "none_other": false,
  "heading_path": ["Risk Factors", "Cybersecurity"],
  "source_offsets": {
    "start": 18420,
    "end": 18478
  },
  "guideline_version": "v1",
  "annotation_status": "adjudicated"
}
```

The sentence can later be used for evaluation, but its heading context and source location remain available for auditability and feature experiments.

## Acceptance criteria

Phase 2 is complete when:

- versioned definitions exist for all four target labels and `NONE_OTHER`;
- multi-label annotation rules are documented with boundary examples;
- approximately 500 sentences are sampled with reproducible provenance;
- the sample covers relevant companies, industries, blocks, headings, lists, lengths, and parser uncertainty;
- annotations are reviewed and disagreements are adjudicated;
- every annotation references a valid stable sentence ID and source location;
- train, development, and test sets are split by company;
- the held-out test set is frozen and excluded from prompt examples and synthetic data;
- label prevalence, disagreement, and coverage reports are available;
- heading metadata is preserved as context but is not used as an automatic label;
- no raw filing data or Phase 1 derived data is overwritten by annotation work.

**Recommended feature branch:** `feature/gold-annotations`

**Suggested commit message:** `data: add versioned Item 1A gold annotation set`

</proposed_plan>
