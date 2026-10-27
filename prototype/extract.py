"""AI extraction step (the only step that calls a model).

Reads each proposal text file in samples/ (not committed: put the text of
proposals A-E there as A.txt ... E.txt), sends it with the prompt from
PROMPTS.md, runs the code checks from PROMPTS.md section 4, and writes
output/extracted.json in the same shape as fixtures/extracted.json.

Usage:
    pip install -r requirements.txt
    cp .env.example .env   # add your free Gemini key (https://aistudio.google.com/apikey)
    python extract.py
    python score.py output/extracted.json
"""

import hashlib
import json
import os
import re
from pathlib import Path

from google import genai
from google.genai import types

HERE = Path(__file__).parent
DEFAULT_MODEL = "gemini-2.5-flash"
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


def extract_one(client, model, criteria, path):
    body = path.read_text(encoding="utf-8")
    config = types.GenerateContentConfig(
        system_instruction=system_prompt(),
        temperature=0,   # as repeatable as the model allows
        seed=7,
        response_mime_type="application/json",
        response_json_schema=output_schema(criteria),
    )
    prompt = user_prompt(criteria, path.stem, path.name, body)
    for attempt in (1, 2):   # retry once, then hand to the reviewer
        response = client.models.generate_content(model=model, contents=prompt, config=config)
        try:
            result = json.loads(response.text)
            break
        except (TypeError, json.JSONDecodeError):
            if attempt == 2:
                raise RuntimeError(f"{path.name}: no valid JSON after retry; send to reviewer")
    result = verify(result, body)
    result["proposal"] = path.stem
    usage = response.usage_metadata
    result["_audit"] = {
        "model": model,
        "source_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "criteria_version": criteria["criteria_version"],
        "prompt_sha256": hashlib.sha256(system_prompt().encode("utf-8")).hexdigest(),
        "usage": {"input_tokens": usage.prompt_token_count if usage else None,
                  "output_tokens": usage.candidates_token_count if usage else None},
    }
    return result


def main():
    load_env()
    criteria = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))
    files = sorted((HERE / "samples").glob("*.txt"))
    if not files:
        raise SystemExit("Put proposal text files in prototype/samples/ (A.txt ... E.txt)")
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Set GEMINI_API_KEY in prototype/.env (see .env.example)")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    results = []
    for path in files:
        print(f"Extracting {path.name} with {model}...")
        results.append(extract_one(client, model, criteria, path))
    out_dir = HERE / "output"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "extracted.json").write_text(
        json.dumps({"proposals": results}, indent=2), encoding="utf-8")
    print(f"Wrote {out_dir / 'extracted.json'} for {len(results)} proposals")


if __name__ == "__main__":
    main()
