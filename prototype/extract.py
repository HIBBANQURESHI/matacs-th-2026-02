"""AI extraction step (the only step that calls a model).

Reads each proposal text file in samples/ (not committed: put the text of
proposals A-E there as A.txt ... E.txt), sends it with the prompt from
PROMPTS.md, runs the code checks from PROMPTS.md section 4, and writes
output/extracted.json in the same shape as fixtures/extracted.json.

Usage:
    pip install -r requirements.txt
    cp .env.example .env   # add your key
    python extract.py
    python score.py output/extracted.json
"""

import hashlib
import json
import os
import re
from pathlib import Path

import anthropic

HERE = Path(__file__).parent
MODEL = "claude-opus-5-5"
INJECTION_PATTERNS = [
    r"ignore (all |any )?previous", r"automated review", r"rank (it|this|us) first",
    r"full marks", r"pre-?approved", r"note to (the )?(ai|reviewer|system)",
]


def load_env():
    env_file = HERE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def system_prompt():
    """Use the system prompt exactly as written in PROMPTS.md (single source of truth)."""
    text = (HERE.parent / "PROMPTS.md").read_text(encoding="utf-8")
    section = text.split("## 1.", 1)[1]
    return re.search(r"```text\n(.*?)```", section, re.S).group(1).strip()


def user_prompt(criteria, proposal_id, file_name, body):
    project = criteria["project"]
    fields = "\n".join(f"- {f['id']} ({f['type']}): {f['instruction']}"
                       for f in criteria["extraction_fields"])
    return (
        f"Category: {criteria['category']}\n"
        f"Project facts set by the admin: budget ceiling ${project['budget_ceiling_cad']:,} CAD, "
        f"complete within {project['max_weeks']} weeks of award\n"
        f"Evaluation date: {project['evaluation_date']}\n\n"
        f"Extract these fields:\n\n{fields}\n\n"
        f'<proposal id="{proposal_id}" source_file="{file_name}">\n{body}\n</proposal>'
    )


def output_schema(criteria):
    json_type = {"boolean": "boolean", "string": "string", "number": "number", "integer": "integer"}
    field_props = {
        f["id"]: {
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "status", "evidence"],
            "properties": {
                "value": {"anyOf": [{"type": json_type[f["type"]]}, {"type": "null"}]},
                "status": {"type": "string", "enum": ["found", "not_found", "ambiguous"]},
                "evidence": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            },
        }
        for f in criteria["extraction_fields"]
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["proposal", "fields", "embedded_instructions", "notes"],
        "properties": {
            "proposal": {"type": "string"},
            "fields": {"type": "object", "additionalProperties": False,
                       "required": list(field_props), "properties": field_props},
            "embedded_instructions": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["location", "summary"],
                "properties": {"location": {"type": "string"}, "summary": {"type": "string"}}}},
            "notes": {"type": "array", "items": {"type": "string"}},
        },
    }


def normalise(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def verify(result, body):
    """Code checks from PROMPTS.md section 4. Marks fields the reviewer must look at."""
    source = normalise(body)
    for field in result["fields"].values():
        quote = field.get("evidence")
        if quote and normalise(quote) not in source:
            field["status"] = "unverified"
        value = field.get("value")
        if quote and isinstance(value, (int, float)) and not isinstance(value, bool):
            digits = re.sub(r"[^\d]", "", quote)
            if str(int(value)) not in digits and field["status"] != "unverified":
                # e.g. "12 months" converted to 52 weeks: keep, but send to reviewer
                field["status"] = "ambiguous"
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, body, re.I) and not result["embedded_instructions"]:
            result["embedded_instructions"].append(
                {"location": "keyword scan", "summary": f"matched '{pattern}'; AI did not report it"})
    return result


def extract_one(client, criteria, path):
    body = path.read_text(encoding="utf-8")
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low",
                       "format": {"type": "json_schema", "schema": output_schema(criteria)}},
        system=system_prompt(),
        messages=[{"role": "user", "content": user_prompt(criteria, path.stem, path.name, body)}],
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"{path.name}: stopped with {response.stop_reason}; send to reviewer")
    text = next(block.text for block in response.content if block.type == "text")
    result = verify(json.loads(text), body)
    result["proposal"] = path.stem
    result["_audit"] = {
        "model": response.model,
        "source_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "criteria_version": criteria["criteria_version"],
        "prompt_sha256": hashlib.sha256(system_prompt().encode("utf-8")).hexdigest(),
        "usage": {"input_tokens": response.usage.input_tokens,
                  "output_tokens": response.usage.output_tokens},
    }
    return result


def main():
    load_env()
    criteria = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))
    files = sorted((HERE / "samples").glob("*.txt"))
    if not files:
        raise SystemExit("Put proposal text files in prototype/samples/ (A.txt ... E.txt)")
    client = anthropic.Anthropic()
    results = [extract_one(client, criteria, path) for path in files]
    out_dir = HERE / "output"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "extracted.json").write_text(
        json.dumps({"proposals": results}, indent=2), encoding="utf-8")
    print(f"Wrote {out_dir / 'extracted.json'} for {len(results)} proposals")


if __name__ == "__main__":
    main()
