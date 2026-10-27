import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def by_letter(data):
    return {p["proposal"]: p for p in data["proposals"]}


def same(expected, actual):
    """Treat equivalent answers as equal: 'not stated' (null) counts as False,
    and a licence number matches if the digits match ('ECRA/ESA #7005678' == '7005678')."""
    if expected is False and actual is None:
        return True
    if isinstance(expected, str) and isinstance(actual, str):
        digits = lambda text: "".join(ch for ch in text if ch.isdigit())
        return digits(expected) == digits(actual) != ""
    return expected == actual


def main():
    actual_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "output" / "extracted.json"
    expected = by_letter(json.loads((HERE / "fixtures" / "extracted.json").read_text(encoding="utf-8")))
    actual = by_letter(json.loads(actual_path.read_text(encoding="utf-8")))

    mismatches = 0
    for letter, exp in expected.items():
        act = actual.get(letter)
        if act is None:
            print(f"{letter}: missing from live output")
            mismatches += 1
            continue
        for field, exp_field in exp["fields"].items():
            act_field = act["fields"].get(field, {})
            if not same(exp_field["value"], act_field.get("value")):
                print(f"{letter}.{field}: expected {exp_field['value']!r}, got {act_field.get('value')!r}"
                      f"  (status {act_field.get('status')}, evidence {act_field.get('evidence')!r})")
                mismatches += 1
            elif act_field.get("status") == "unverified":
                print(f"{letter}.{field}: value matches but quote was not found in the source")
        if bool(exp["embedded_instructions"]) != bool(act.get("embedded_instructions")):
            print(f"{letter}: injection expected={bool(exp['embedded_instructions'])}, "
                  f"reported={bool(act.get('embedded_instructions'))}")
            mismatches += 1

    print(f"\n{mismatches} mismatch(es) against the expected extraction.")
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
