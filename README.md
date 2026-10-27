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
- [prototype/extract.py](prototype/extract.py): sends each proposal to Google Gemini using the prompt in PROMPTS.md (it reads the prompt from that file, so there's one source of truth), then runs the quote and number checks
- [prototype/compare.py](prototype/compare.py): compares a live AI extraction with the expected answers and lists any differences

**Run it**

```bash
cd prototype
python score.py                         # offline: ranking from the expected extraction, no key needed

pip install -r requirements.txt         # live AI run, needs a free Gemini key
cp .env.example .env                    # then put your key in .env (https://aistudio.google.com/apikey)
# put the five proposal texts in samples/A.txt ... samples/E.txt (git-ignored: the brief
# asks that proposal text is not committed)
python extract.py                       # AI extraction  -> output/extracted.json
python compare.py                       # check the AI against the expected answers
python score.py output/extracted.json   # ranking from the AI's extraction
```

## How I used AI tools

I used Claude Code following my instructions: it generated the diagram, the JSON files (criteria, expected extraction, ranking), and first drafts of the write-up, prompt and prototype scripts, which I reviewed, ran and directed changes to. **Where I corrected the AI:** it first wired the extractor to Anthropic's paid API; I had it switched to Gemini's free tier. When I ran the live test, the output wrongly flagged correct values like "$5M" insurance and "eight installs" as ambiguous, because the AI's number check didn't understand "M" or numbers written as words. I had that check fixed. The same run showed Gemini correctly flagging that "since 2021" may partly fall outside the 5-year window, which the AI's expected answers had missed.
