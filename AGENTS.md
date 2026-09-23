# AGENTS.md

## Project purpose

RiskLens processes SEC Form 10-K Item 1A risk-factor disclosures to help analysts identify risk statements, mitigation, supporting context, and boilerplate. The project values traceable evidence, reproducibility, and useful analyst output over unnecessary ML/AI complexity.

## Scope and permission rules

- Keep implementations simple and focused on the requested issue or phase.
- Do not over-engineer the ML, AI, data, or retrieval system.
- Do not modify, create, delete, or rename any file without explicit user permission or a direct implementation request.
- A direct implementation request applies only to the files and scope named in that request.
- Before modifying files, inspect the relevant repository surfaces and existing user changes.
- Do not commit, push, merge, reset, or otherwise alter Git history. The repository owner handles commits and merges.
- Do not make destructive changes or overwrite raw data without explicit instruction.

## Required change report

After every approved file change, report concisely:

- what changed;
- files affected;
- verification performed;
- recommended branch name;
- suggested commit message;
- whether a feature branch is recommended.

For each stage or feature, state the branch recommendation before or alongside the implementation handoff. Use the project workflow:

```text
main
  <- dev
      <- feature branches
```

Feature branches merge into `dev`, and validated work merges from `dev` into `main`. The user performs those operations.

## Project conventions

- Raw SEC-derived filings belong under `data/extracted_filings/` and are immutable source inputs.
- Derived datasets belong under `data/` with clear provenance.
- Reusable application code belongs under `src/`.
- Runnable processing entry points belong under `scripts/`.
- Configuration belongs under `configs/`.
- Secrets must come from environment variables and must never be committed.
- Tests belong under `tests/` and should validate behavior and data contracts.
- Documentation should explain data flow, assumptions, reproducibility, and operational decisions.

## Data and provenance rules

The logical data levels are:

1. filing metadata;
2. structured Item 1A blocks with headings and source offsets;
3. sentence records with stable IDs, text, offsets, labels, probabilities, and model metadata.

Every block, sentence, prediction, and future vector must retain a path to its filing. Preserve both original and normalized sentence text. Use half-open source offsets `[start, end)` against the original Item 1A text. Record parser warnings rather than silently discarding uncertain boundaries.

The source hash, parser version, normalization version, and model version must be retained wherever derived data is produced.

## Modeling rules

- Treat `RISK_STATEMENT` and `MITIGATION` as independent labels; mixed sentences are valid.
- Keep `SUPPORTED_CONTEXT` and `BOILERPLATE` independently represented.
- An internal `NONE_OTHER` state may prevent forced labels during annotation.
- Establish a TF-IDF baseline before relying on an LLM or embedding model.
- Store all model probabilities and apply display thresholds later.
- Keep human gold labels separate from synthetic LLM labels.
- Evaluate with company-held-out splits to reduce issuer and wording leakage.
- Report per-label precision, recall, F1, PR-AUC, calibration, thresholded precision, and qualitative errors.
- Do not present predictions as verified facts; always show source evidence and confidence.

## Testing expectations

Tests should cover, as applicable:

- valid and invalid filing records;
- stable IDs and deterministic reruns;
- headings, paragraphs, bullets, and sentence boundaries;
- SEC abbreviations, numbers, citations, and punctuation;
- source-offset and provenance integrity;
- duplicate and missing metadata detection;
- company-held-out evaluation without leakage;
- prediction schema and probability ranges;
- retrieval filters and source-text fidelity.

Before reporting completion, run focused checks relevant to the change and state any checks that could not be run.

## Implementation discipline

1. Inspect before changing.
2. Confirm the requested scope.
3. Make the smallest coherent change.
4. Preserve unrelated user work.
5. Verify the result.
6. Report the change, branch recommendation, and commit message.

Do not add entity extraction, summarization, vector search, or extra infrastructure unless it supports a concrete analyst workflow or the requested implementation phase.
