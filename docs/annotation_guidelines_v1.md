# RiskLens Item 1A Annotation Guidelines

Version: `v1`

## Purpose

These guidelines define the labels used to create the Phase 2 human-annotated gold dataset for SEC Form 10-K Item 1A sentences.

The purpose of annotation is to identify useful analyst-facing signals in each sentence while preserving the sentence's original filing context and provenance. The labels are applied to sentence content, not inferred solely from a heading or block type.

## Annotation unit

The sentence is the primary annotation unit. Annotators should review the available context when needed, including:

- the complete sentence text;
- neighboring sentences;
- the containing block;
- the hierarchical `heading_path`;
- filing and company metadata;
- the sentence's source offsets.

Each annotation must remain traceable to its source record using the stable `sentence_id`, filing ID, block ID where available, and half-open source offsets `[start, end)` against the original Item 1A text.

Headings and block types provide context, but they do not automatically determine a sentence label. For example, a sentence under a `Cybersecurity` heading is not automatically a `RISK_STATEMENT`.

## Target labels

### `RISK_STATEMENT`

Assign `RISK_STATEMENT` when the sentence identifies or describes a relevant:

- uncertainty or possible adverse event;
- threat, vulnerability, or exposure;
- potential loss, harm, disruption, or negative consequence;
- condition that could adversely affect the company, its operations, finances, compliance, reputation, customers, employees, or other stakeholders.

The risk may be stated directly or conditionally. It does not need to use the word “risk.”

#### Positive examples

```text
Our operations may be adversely affected by severe weather, including hurricanes and flooding.
```

```text
Cybersecurity incidents could disrupt our operations and result in the loss of confidential information.
```

```text
We depend on third-party suppliers, and disruptions at those suppliers could delay production.
```

#### Not sufficient by itself

```text
The company operates manufacturing facilities in several regions.
```

This is factual context unless the surrounding sentence or clause identifies a potential adverse consequence.

## `MITIGATION`

Assign `MITIGATION` when the sentence identifies an action, control, process, policy, safeguard, arrangement, or capability intended to:

- prevent or reduce a risk;
- monitor or detect a risk;
- prepare for or respond to an adverse event;
- limit the impact of a loss or disruption;
- provide resilience, continuity, insurance, diversification, or alternative capacity.

The sentence does not need to claim that the mitigation is fully effective. A stated attempt or capability can qualify.

#### Positive examples

```text
We maintain business continuity plans and backup facilities to help reduce the effect of these events.
```

```text
We use monitoring tools and response procedures to detect and address cybersecurity incidents.
```

```text
We seek alternative sources where practical to reduce our dependence on individual suppliers.
```

#### Not sufficient by itself

```text
We operate facilities in several regions.
```

Geographic diversity may be relevant context, but it should receive `MITIGATION` only when the sentence presents it as reducing, managing, or responding to a risk.

## `SUPPORTED_CONTEXT`

Assign `SUPPORTED_CONTEXT` when the sentence provides factual or operational information that helps an analyst interpret a nearby risk or mitigation but does not itself meet either definition.

This may include information about:

- business activities and operating structure;
- products, services, markets, customers, or suppliers;
- locations and geographic exposure;
- dependencies, resources, processes, or capabilities;
- relevant figures, names, dates, or conditions.

#### Positive examples

```text
The company operates manufacturing facilities in several regions and relies on third-party logistics providers.
```

```text
Our customers include government agencies, healthcare providers, and financial institutions.
```

Context may co-occur with a risk or mitigation when the sentence explicitly contains that signal. Do not use `SUPPORTED_CONTEXT` as a substitute for an applicable risk or mitigation label.

## `BOILERPLATE`

Assign `BOILERPLATE` when the sentence is substantially standardized legal, regulatory, introductory, or repetitive disclosure language with limited company-specific analytical value.

Typical examples include:

- forward-looking statement disclaimers;
- generic statements about risks and uncertainties;
- standard incorporation or regulatory language;
- repeated disclosure formulas that do not identify a specific company risk or control.

#### Positive example

```text
This Annual Report contains forward-looking statements that involve risks and uncertainties.
```

#### Important boundary rule

Do not assign `BOILERPLATE` merely because a sentence uses formal legal language. If it contains a meaningful company-specific risk or mitigation, label the meaningful signal and record the rationale.

`BOILERPLATE` will normally stand alone. If a sentence contains meaningful company-specific risk or mitigation content, assign the meaningful label or labels and record why the sentence is not treated as only boilerplate.

## `NONE_OTHER`

Use `NONE_OTHER` internally when none of the four target labels applies.

`NONE_OTHER` is useful for preventing forced labels during annotation. It is not one of the four primary analyst-facing categories unless the project later decides to expose it as a model output.

Use `NONE_OTHER` when the sentence is, for example:

- a neutral transition with no useful risk or mitigation signal;
- an administrative statement unrelated to the target categories;
- too incomplete to support one of the target labels after reviewing context;
- factual text that does not materially support interpretation of a risk or mitigation.

Annotators should record a short rationale for unusual or ambiguous `NONE_OTHER` decisions.

## Multi-label and `NONE_OTHER` rules

### Independent labels

The four target labels are independently applicable. Do not force a sentence into one mutually exclusive class when it clearly contains more than one signal.

Valid target-label combinations include:

- `RISK_STATEMENT` only;
- `MITIGATION` only;
- `SUPPORTED_CONTEXT` only;
- `BOILERPLATE` only;
- `RISK_STATEMENT` + `MITIGATION`;
- `RISK_STATEMENT` + `SUPPORTED_CONTEXT`;
- `MITIGATION` + `SUPPORTED_CONTEXT`;
- `RISK_STATEMENT` + `MITIGATION` + `SUPPORTED_CONTEXT`.

The labels should describe the sentence's explicit content. A heading, neighboring sentence, or analyst interpretation may provide context, but must not create a label that is absent from the sentence.

### Mixed risk and mitigation

Assign both labels when the same sentence explicitly identifies a possible adverse consequence and an action intended to prevent, reduce, monitor, or respond to it.

```text
Our dependence on third-party suppliers could result in delays, although we seek alternative sources where practical.
```

Labels:

```json
["RISK_STATEMENT", "MITIGATION"]
```

Do not choose one label based on which clause appears first. If the sentence contains separate signals, preserve both signals.

### Context combined with a target signal

Add `SUPPORTED_CONTEXT` when the sentence also provides factual or operational context that supports the risk or mitigation signal.

```text
We operate data centers in several regions, which helps us maintain service during a localized outage.
```

Possible labels:

```json
["MITIGATION", "SUPPORTED_CONTEXT"]
```

The context label should not be added merely because every risk or mitigation has surrounding facts. Add it when the sentence itself contains meaningful supporting context.

### Boilerplate precedence

`BOILERPLATE` normally stands alone because its purpose is to identify low-value standardized language. Do not combine it with another label solely because the sentence contains generic words such as “risk” or “uncertainty.”

If a sentence contains both formulaic language and a specific company-related risk or mitigation, assign the meaningful target label or labels instead of using `BOILERPLATE` as a catch-all.

### `NONE_OTHER`

Set `none_other` to `true` only when none of the four target labels applies. In that case, the target `labels` array must be empty:

```json
{
  "labels": [],
  "none_other": true,
  "rationale": "The sentence is a neutral transition and contains no target signal."
}
```

`NONE_OTHER` must not be combined with any target label. If at least one target label applies, set `none_other` to `false`.

## Boundary guidance

### Risk versus context

```text
The company relies on third-party logistics providers.
```

This is normally `SUPPORTED_CONTEXT`.

```text
Disruptions at third-party logistics providers could delay delivery to customers.
```

This is `RISK_STATEMENT`.

### Risk versus mitigation

```text
Cybersecurity incidents could disrupt our operations.
```

This is `RISK_STATEMENT`.

```text
We maintain monitoring and incident-response procedures.
```

This is `MITIGATION`.

### Mixed content

```text
Our dependence on third-party suppliers could result in delays, although we seek alternative sources where practical.
```

This contains both a possible adverse consequence and an action intended to reduce that exposure. Assign both `RISK_STATEMENT` and `MITIGATION`.

### Heading context

```text
Heading path: Risk Factors > Cybersecurity
Sentence: We operate data centers in several locations.
```

The heading suggests relevant context, but it does not by itself make the sentence a risk statement. The sentence should be labeled according to its content.

## Annotation record requirements

Each annotation should preserve the following information where available:

```json
{
  "sentence_id": "sentence-000123",
  "filing_id": "1002910-10-K-2022",
  "block_id": "block-000006",
  "labels": ["RISK_STATEMENT"],
  "none_other": false,
  "annotator_id": "annotator_01",
  "guideline_version": "v1",
  "rationale": "The sentence describes a possible operational disruption.",
  "source_offsets": {
    "start": 18420,
    "end": 18478
  }
}
```

The sentence text, original and normalized forms, heading path, block type, and parser diagnostics should remain available through the linked Phase 1 records rather than being copied inconsistently into annotation files.

For a multi-label record, include every applicable target label in the `labels` array. For a `NONE_OTHER` record, use an empty `labels` array and set `none_other` to `true`.

## Versioning and change control

- This document is version `v1`.
- Changes to label definitions or boundary rules require a new guideline version.
- Existing annotations must retain the guideline version used to create them.
- A revised guideline must not silently alter the meaning of already adjudicated labels.
- New examples may be added without changing the version only when they clarify an existing rule and do not change prior decisions.

## Stage 1 completion criteria

Stage 1 is complete when:

- all four target labels are defined;
- `NONE_OTHER` is defined as an internal annotation state;
- inclusion and exclusion guidance is provided;
- positive, negative, and boundary examples are documented;
- heading context is explicitly separated from sentence labels;
- annotation provenance and versioning requirements are recorded.

## Stage 2 completion criteria

Stage 2 is complete when:

- labels are treated as independent rather than mutually exclusive;
- valid mixed-label combinations are documented;
- risk-and-mitigation sentences have an explicit dual-label rule;
- `BOILERPLATE` precedence is documented;
- `NONE_OTHER` is mutually exclusive with target labels;
- annotation records represent empty, single-label, and multi-label cases consistently;
- headings and neighboring context cannot create labels absent from the sentence.
