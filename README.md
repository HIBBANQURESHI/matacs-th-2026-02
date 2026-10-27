# AI Proposal Triage: Design

- **Name:** Hibban Qureshi <!-- TODO: confirm full legal name -->
- **Reference:** MATACS-TH-2026-02
- **Time actually spent:** TODO (e.g. "about 75 minutes")

## In one line

AI reads each proposal and pulls out facts, each with a quote from the PDF. Plain code applies the admin's pass/fail checks and scoring formulas. A person reviews anything flagged and makes the award.

| Rank | Proposal | Status | Score | Why, in short |
|---|---|---|---|---|
| 1 | A | ranked | 73.3 | Most experience, full team marks, 12 weeks |
| 2 | E | ranked | 61.2 | Best warranty, full team marks, fewer installs |
| – | D | flagged | – | No committed schedule; 16-week limit can't be confirmed |
| – | C | flagged | – | Hidden instruction telling the AI to rank it first |
| – | B | ineligible | – | Bidder doesn't hold the Ontario electrical licence |

## Files

| File | What it is |
|---|---|
| [diagram/process-flow.png](diagram/process-flow.png) | Flow from upload to ranked output; colour shows AI steps, code/rule steps and human checkpoints |
| [WRITEUP.md](WRITEUP.md) | Answers to the five questions, plus my assumptions |
| [PROMPTS.md](PROMPTS.md) | The extraction prompt, output schema, and the code checks run on every AI reply |
| [ranking.json](ranking.json) | Expected ranking of proposals A–E |
| [prototype/](prototype/) | Optional: runnable scorer + AI extraction script |

### Prototype

- [prototype/criteria.json](prototype/criteria.json): the admin's criteria for this category as data (fields, mandatory checks, weights, scales)
- [prototype/score.py](prototype/score.py): deterministic checks, scoring and ranking. Runs with no API key:
  `python prototype/score.py` → prints the ranking, from [prototype/fixtures/extracted.json](prototype/fixtures/extracted.json) (the expected AI extraction for A–E)
- [prototype/extract.py](prototype/extract.py): sends each proposal to Claude using the prompt in PROMPTS.md (it reads the prompt from that file, so there's one source of truth) and runs the quote and number checks. Needs `pip install -r prototype/requirements.txt` and a key in `prototype/.env` (see [.env.example](prototype/.env.example)). Proposal text goes in `prototype/samples/` (git-ignored, since the brief asks that proposal text not be committed). **I did not run this against the live API.** The fixture file is my hand-checked expected output.

## How I used AI tools

<!-- TODO: rewrite in your own words, 2-3 sentences, and add a real example of
where you disagreed with or corrected the AI. Do not submit this placeholder. -->

I used Claude (Claude Code) to help draft the files, the prototype scripts and the diagram, and I reviewed and edited every part myself. **Where I disagreed with the AI:** TODO, describe a real correction you made. Some options: a scoring scale you changed; whether D should be ranked or flagged; whether C's weekly progress reports should count as monitoring.
