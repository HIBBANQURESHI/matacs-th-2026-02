"""Deterministic scoring and ranking.

Takes the admin criteria (criteria.json) and the AI extraction output
(fixtures/extracted.json or the output of extract.py) and produces the
ranking in ranking.json format. No AI is used here: the same inputs always
give the same output.

Usage:
    python score.py                       # uses fixtures/extracted.json
    python score.py path/to/extracted.json
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def linear(value, full_marks_at, zero_at):
    """0..1 on a straight line between zero_at and full_marks_at, clamped."""
    if value is None:
        return 0.0
    fraction = (value - zero_at) / (full_marks_at - zero_at)
    return max(0.0, min(1.0, fraction))


def val(fields, key):
    return fields[key]["value"]


def check_mandatory(fields):
    """Return a list of failed mandatory criteria (empty list = pass)."""
    failures = []
    if not (val(fields, "bidder_holds_ontario_licence") and val(fields, "licence_number")):
        failures.append("bidder does not hold a stated Ontario electrical contractor licence")
    if not val(fields, "wsib_clearance"):
        failures.append("WSIB clearance not confirmed")
    if (val(fields, "liability_insurance_cad") or 0) < 5_000_000:
        failures.append("$5M liability insurance not confirmed")
    return failures


def check_project_limits(fields, project):
    """Hard project limits. Returns (ineligible_reasons, flag_reasons)."""
    ineligible, flags = [], []
    price = val(fields, "total_price_cad")
    weeks = val(fields, "completion_weeks")
    if price is None:
        flags.append("no total price stated")
    elif price > project["budget_ceiling_cad"]:
        ineligible.append("price is over the budget ceiling")
    if weeks is None:
        flags.append("no committed completion time, so the 16-week limit cannot be confirmed")
    elif weeks > project["max_weeks"]:
        ineligible.append("completion time is over 16 weeks")
    return ineligible, flags


def score_criterion(criterion, fields):
    """Return points (0..weight) for one weighted criterion."""
    scale = criterion["scale"]
    if scale == "linear":
        fraction = linear(val(fields, criterion["input"]),
                          criterion["full_marks_at"], criterion["zero_at"])
    elif scale == "composite":
        fraction = sum(
            part["share"] * linear(val(fields, part["input"]), part["full_marks_at"], 0)
            for part in criterion["parts"]
        )
    elif scale == "checklist":
        items = criterion["items"]
        fraction = sum(1 for item in items if val(fields, item)) / len(items)
    else:
        raise ValueError(f"unknown scale {scale}")
    return round(fraction * criterion["weight"], 2)


def evaluate(proposal, criteria):
    fields = proposal["fields"]
    result = {"proposal": proposal["proposal"], "breakdown": {}, "flags": [], "ineligible": []}

    result["ineligible"] += check_mandatory(fields)
    over_limits, limit_flags = check_project_limits(fields, criteria["project"])
    result["ineligible"] += over_limits
    result["flags"] += limit_flags

    if proposal["embedded_instructions"]:
        where = ", ".join(e["location"] for e in proposal["embedded_instructions"])
        result["flags"].append(f"contains instructions aimed at the AI reviewer ({where}); ignored")

    unverified = [k for k, f in fields.items() if f["status"] == "unverified"]
    if unverified:
        result["flags"].append(f"evidence quote not found in source for {', '.join(unverified)}")

    for criterion in criteria["weighted"]:
        result["breakdown"][criterion["id"]] = score_criterion(criterion, fields)
    result["score"] = round(sum(result["breakdown"].values()), 1)

    result["ambiguous"] = [k for k, f in fields.items() if f["status"] == "ambiguous"]
    return result


def reason_for(r):
    b = r["breakdown"]
    parts = (f"exp {b['experience']}/30, price {b['price']}/25, time {b['timeline']}/15, "
             f"warranty {b['warranty']}/15, team {b['team_approach']}/15")
    if r["ineligible"]:
        return f"Fails mandatory/limit check: {'; '.join(r['ineligible'])}. Not scored."
    if r["flags"]:
        note = f" Also: {', '.join(r['ambiguous'])} ambiguous." if r["ambiguous"] else ""
        return (f"Held for reviewer: {'; '.join(r['flags'])}. "
                f"Provisional score {r['score']} ({parts}).{note}")
    note = f" Reviewer check: {', '.join(r['ambiguous'])} ambiguous." if r["ambiguous"] else ""
    return f"Passes all gates; {parts}.{note}"


def rank(results):
    eligible = [r for r in results if not r["ineligible"] and not r["flags"]]
    # Ties break on proposal letter so the order is always reproducible;
    # a reviewer resolves genuine ties.
    eligible.sort(key=lambda r: (-r["score"], r["proposal"]))
    positions = {r["proposal"]: i + 1 for i, r in enumerate(eligible)}

    output = []
    for r in sorted(results, key=lambda r: (positions.get(r["proposal"], 99), r["proposal"])):
        if r["ineligible"]:
            status, rank_, score = "ineligible", None, None
        elif r["flags"]:
            status, rank_, score = "flagged", None, None
        else:
            status, rank_, score = "ranked", positions[r["proposal"]], r["score"]
        output.append({"proposal": r["proposal"], "rank": rank_, "status": status,
                       "score": score, "reason": reason_for(r)})
    return output


def main():
    extracted_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "fixtures" / "extracted.json"
    criteria = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))
    extracted = json.loads(extracted_path.read_text(encoding="utf-8"))
    results = [evaluate(p, criteria) for p in extracted["proposals"]]
    print(json.dumps(rank(results), indent=2))


if __name__ == "__main__":
    main()
