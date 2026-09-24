<proposed_plan>
# Phase 1: Structured Item 1A parsing approach

Phase 1 will convert each raw `item_1A` field into traceable filing, block, and sentence records. It will not classify text or add embeddings yet.

## Stage 1 — Extract `item_1A`

### Problem

The raw JSON contains filing metadata and one large `item_1A` text field.

Example:

```text
{
  "cik": 1013237,
  "company": "FACTSET RESEARCH SYSTEMS INC",
  "filing_date": "2023-10-27",
  "item_1A": "ITEM 1A. RISK FACTORS\n..."
}
```

### Intended solution

Read the raw JSON as the source of truth and create a filing-level record containing metadata plus the complete original Item 1A text.

### Expected output

```json
{
  "filing_id": "stable-filing-id",
  "cik": "1013237",
  "company": "FACTSET RESEARCH SYSTEMS INC",
  "filing_date": "2023-10-27",
  "period_of_report": "2023-08-31",
  "item_1a_text": "ITEM 1A. RISK FACTORS\n..."
}
```

No text will be discarded at this stage.

## Stage 2 — Normalize line endings only

### Problem

The current filings contain inconsistent formatting such as tabs, line breaks, and spacing:

```text
ITEM 1A.\tRISK FACTORS\r\n\r\nWe face risks...
```

### Intended solution

Keep the original text unchanged and create a controlled modeling version:

- convert `\r\n` and `\r` to `\n`;
- preserve tabs and other meaningful characters initially;
- do not lowercase, rewrite punctuation, or remove content.

### Expected output

```json
{
  "raw_text": "ITEM 1A.\tRISK FACTORS\r\n\r\nWe face risks...",
  "text": "ITEM 1A.\tRISK FACTORS\n\nWe face risks...",
  "normalization_status": "line_endings_only"
}
```

The raw text remains available for auditability.

## Stage 3 — Detect headings and build heading paths

### Problem

Item 1A contains headings mixed with regular text:

```text
ITEM 1A. RISK FACTORS

REGULATORY AND LEGISLATIVE RISKS

We are subject to extensive regulation of our businesses.
```

Some filings use:

```text
ITEM 1A.RISK FACTORS
```

or:

```text
ITEM 1A.\tRISK FACTORS
```

### Intended solution

Use several signals together:

- known Item 1A patterns;
- uppercase or title-like short lines;
- numbered section patterns;
- lines surrounded by blank lines;
- formatting and length;
- known risk-factor heading patterns.

A line that looks like a risk-factor title becomes a heading. A normal sentence such as `We are subject to extensive regulation...` remains paragraph text.

### Expected output

```json
{
  "heading": "REGULATORY AND LEGISLATIVE RISKS",
  "heading_path": [
    "ITEM 1A. RISK FACTORS",
    "REGULATORY AND LEGISLATIVE RISKS"
  ],
  "block_type": "heading",
  "block_order": 1
}
```

If heading detection is uncertain, the parser will retain the line as text and create a diagnostic rather than silently making a potentially wrong decision.

## Stage 4 — Split paragraphs, bullets, and list items

### Problem

Risk disclosures contain paragraphs and bullet lists embedded in the same text:

```text
We face risks associated with our global operations.

Our global operations include:
• Foreign Currency Exchange: Approximately 31% of sales were outside the U.S.
• Interest Rates and Inflation: Higher rates could increase financial risk.
• Anti-Bribery: We operate in jurisdictions with anti-bribery requirements.
```

### Intended solution

Identify:

- blank-line paragraph boundaries;
- bullet markers such as `•`, `-`, and `▪`;
- numbered list markers;
- continuation lines belonging to the same bullet;
- headings that update the current heading path.

### Expected output

```json
[
  {
    "block_type": "paragraph",
    "heading_path": ["ITEM 1A. RISK FACTORS"],
    "raw_block_text": "We face risks associated with our global operations."
  },
  {
    "block_type": "bullet_group",
    "heading_path": ["ITEM 1A. RISK FACTORS"],
    "raw_block_text": "Our global operations include:"
  },
  {
    "block_type": "list_item",
    "is_bullet": true,
    "heading_path": ["ITEM 1A. RISK FACTORS"],
    "raw_block_text": "Foreign Currency Exchange: Approximately 31% of sales were outside the U.S."
  }
]
```

The parser will not classify bullets yet. It will only preserve their structure.

## Stage 5 — Segment sentences

### Problem

Naive splitting on periods would incorrectly split SEC text:

```text
Our exposure includes the U.S. market, e.g. through foreign subsidiaries. We may be affected by currency changes.

We work with FactSet Research Systems, Inc. and other partners.
```

It could also break on:

- `U.S.`;
- `e.g.`;
- `Inc.`;
- decimal numbers;
- percentages;
- citations;
- abbreviations;
- parenthetical text.

### Intended solution

Use an SEC-aware sentence segmenter that protects common abbreviations, decimals, citations, and initials before splitting. Each sentence remains associated with its source block.

### Expected output

```json
[
  {
    "sentence_order": 0,
    "text": "Our exposure includes the U.S. market, e.g. through foreign subsidiaries.",
    "block_type": "paragraph"
  },
  {
    "sentence_order": 1,
    "text": "We may be affected by currency changes.",
    "block_type": "paragraph"
  },
  {
    "sentence_order": 2,
    "text": "We work with FactSet Research Systems, Inc. and other partners.",
    "block_type": "paragraph"
  }
]
```

The first sentence must not be split after `U.S.` or `e.g.`, and the second example must not be split after `Inc.`.

## Stage 6 — Attach offsets and parser diagnostics

### Problem

Analysts must be able to trace a sentence back to the exact original filing text. The parser may also encounter uncertain boundaries.

Example:

```text
Our results may be adversely affected by inflation.However, the impact is difficult to predict.
```

The missing space makes the boundary uncertain.

### Intended solution

Store half-open offsets against the original Item 1A text:

```text
[start_offset, end_offset)
```

Preserve both the exact source substring and normalized modeling text.

### Expected output

```json
{
  "raw_text": "Our results may be adversely affected by inflation.",
  "text": "Our results may be adversely affected by inflation.",
  "start_offset": 842,
  "end_offset": 891,
  "boundary_uncertain": false
}
```

For the malformed example:

```json
{
  "text": "Our results may be adversely affected by inflation.However, the impact is difficult to predict.",
  "boundary_uncertain": true,
  "diagnostic": "possible_sentence_boundary_without_whitespace"
}
```

The parser will retain uncertain text and flag it for review instead of dropping or silently rewriting it.

## Stage 7 — Generate stable IDs and export tables

### Problem

The pipeline needs reproducible records that can later connect annotations, predictions, and vectors to the original filing.

### Intended solution

Generate deterministic IDs from source identity and offsets:

```text
filing_id   = hash(CIK + accession + filing type + reporting period)
block_id    = hash(filing_id + block offsets + block type)
sentence_id = hash(block_id + sentence offsets + sentence order)
```

Export separate logical tables:

```text
filings.csv
blocks.csv
sentences.csv
parser_diagnostics.csv
```

### Expected output

```json
{
  "sentence_id": "sentence-8f31...",
  "filing_id": "filing-a102...",
  "block_id": "block-42bd...",
  "sentence_order": 3,
  "heading_path": [
    "ITEM 1A. RISK FACTORS",
    "REGULATORY AND LEGISLATIVE RISKS"
  ],
  "text": "Failure to obtain required permits could adversely affect our operations.",
  "start_offset": 1218,
  "end_offset": 1302
}
```

Re-running the parser on unchanged input should produce the same IDs and ordering.

## End-to-end example

### Input

```text
ITEM 1A. RISK FACTORS

CYBERSECURITY RISKS

Cybersecurity incidents could disrupt our operations. We use access controls,
monitoring, and incident-response procedures to reduce this risk.
```

### Output

```text
Filing
└── Block: CYBERSECURITY RISKS
    ├── Sentence 1:
    │   "Cybersecurity incidents could disrupt our operations."
    └── Sentence 2:
        "We use access controls, monitoring, and incident-response procedures
        to reduce this risk."
```

At this point:

- Sentence 1 is only structured text.
- Sentence 2 is only structured text.
- Classification as `RISK_STATEMENT` or `MITIGATION` happens in a later phase.
- Both sentences retain filing, block, order, and source-offset information.

## Phase 1 acceptance criteria

Phase 1 is complete when:

- all current raw Item 1A filings can be parsed;
- every sentence maps to exactly one filing and block;
- headings and heading paths are preserved;
- bullets and paragraphs remain distinguishable;
- SEC abbreviations and numbers do not cause obvious sentence breaks;
- every sentence can be recovered from original source offsets;
- uncertain boundaries produce diagnostics;
- repeated parsing produces stable IDs;
- filing, block, sentence, and diagnostic outputs can be inspected independently.
</proposed_plan>
