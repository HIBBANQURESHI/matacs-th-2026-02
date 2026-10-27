# Design write-up

**The idea in one line:** AI reads, code scores, people decide. See the [flow diagram](diagram/process-flow.png).

**Sample result** ([ranking.json](ranking.json)): **A** 1st (73.3), **E** 2nd (61.2). **D** is flagged (no committed schedule). **C** is flagged (contains instructions aimed at the AI). **B** is ineligible (the bidder doesn't hold the electrical licence itself).

## 1. AI vs. rules

| Step | Who | Why |
|---|---|---|
| Read PDF, hash file | Code | Mechanical |
| Pull facts from free text (price, weeks, *who* holds the licence, warranty years, named lead) | **AI** | Proposals word things differently: "all-in", "since 2021", "confirmed after award". Reading that is AI's strength. |
| Check the AI's output: schema, quote exists in PDF, number in quote, injection keywords | Code | Catches AI mistakes cheaply |
| Mandatory checks, $260k and 16-week limits | Code | Yes/no rules must never be "probably" |
| Weighted scoring | Code | Admin-defined formula, e.g. price: full marks at ≤ $182k, zero at $260k |
| Rank and write reasons | Code | Built from the points and the quotes |
| Award | Person | Accountability |

**Where I drew the line:** the AI answers *"what does the proposal say?"*, never *"how good is it?"*. Every criterion here can be measured (a count, dollars, weeks, years, a checklist), so a formula is more reliable than a model. If a future criterion needs judgement, the admin writes a yes/no checklist and the AI answers each item with a quote. The AI never gives a free-form score.

## 2. Consistency and explainability

- **Scoring is repeatable:** it depends only on the extracted facts and the criteria version. Ranking the same facts twice gives identical results. Ties break by proposal letter.
- **The AI step can vary between runs, so I don't rely on it.** The extracted facts are stored, keyed by file hash, prompt version and model. Re-ranking reuses them with no new AI call. A fixed prompt, a forced JSON schema and one proposal per call keep fresh runs close. A regression test re-extracts the five samples and alerts if anything changes.
- **Explainable:** for each proposal the reviewer sees criterion → fact → quote (with page) → formula → points. For example, A's timeline gets 7.5/15 because the proposal says *12 weeks*, on a scale of 8 weeks = full marks and 16 weeks = zero.

## 3. Human in the loop

1. **Admin:** defines criteria, weights and scales. Code enforces that weights add up to 100%. Each save creates a new version.
2. **Reviewer checkpoint:** receives every flagged or ineligible proposal and every `unverified` or `ambiguous` field. The reviewer can correct a fact (code then re-scores without calling the AI), clear a flag, or override a rank. Every override needs a written reason. Ineligible bids are listed too, so a bad extraction can't quietly drop a bidder.
3. **Award:** always a person. The output is labelled "recommendation".

**Audit log (append-only):** file hashes, extracted text, criteria version, prompt version, model ID, the AI's raw JSON, check results, points per criterion, flags, every edit and override (old value, new value, who, when, why), and the final list.

## 4. Changing criteria

- Criteria are **versioned, never edited in place**. Each batch is locked to the version it was scored under, and the report shows that version.
- After an edit, existing batches keep their result, marked *"newer criteria available"*. A reviewer can re-score with one click. Facts are stored, so a weight or scale change needs no AI call.
- If the edit **adds a new fact** (e.g. "Canadian-made panels"), only that field is extracted again.
- Once a batch has been **awarded**, it is locked. Changing the rules after the decision needs a new evaluation.
- Both versions and both rankings stay in the log.

## 5. Risks and safeguards

| Risk | Safeguard |
|---|---|
| **Wrong extraction** (e.g. "12 months" read as 12 weeks) | Quote must appear word for word in the PDF; the number must appear in the quote; unit conversions go to the reviewer; regression test on known answers |
| **Made-up facts** | "Not stated" is allowed and scores 0. A value without a real quote is held as `unverified`. |
| **Prompt injection** (C) | Proposal text is marked as untrusted data, and the AI is told to report embedded instructions, not obey them. A keyword scan backs this up. Since the AI can't score, an injection could at most plant facts, and the quote check catches those. Any hit flags the proposal for a person. |
| **Vague wording** (B "to be confirmed", D "TBD") | The bidder must hold each requirement itself, at bid time. Missing hard-limit info means flagged, never assumed. |
| **Bias** (brand, writing style, length) | The AI never compares proposals or scores them. Formulas use only facts. Bidder names can be hidden during extraction. Override patterns are reviewed regularly. |
| **Scanned PDFs** | Little or no text → OCR, then the reviewer confirms. Never silently skipped. |
| **Cost** | One small AI call per proposal, cached by file hash. Re-scoring is free. Batch size is capped. |
| **Over-trust** | Labelled "recommendation". The list can't be finalised until a person has opened each flagged item. |

## Assumptions

- "Last 5 years" is counted back from the evaluation date. C says "since 2020", so its count is marked `ambiguous` rather than guessed.
- The $260k ceiling and the 16-week limit are hard limits. A proposal over either is ineligible; one that doesn't state them (D) is flagged.
- Scales such as "8 weeks = full marks" and "12+ installs = full marks" are my examples of what an admin would set. They are not given in the brief.
- "Monitoring" means system performance monitoring after install. C's weekly progress reports don't count.
- Flagged proposals get `rank` and `score` set to null. The provisional score is in the reason for context.
