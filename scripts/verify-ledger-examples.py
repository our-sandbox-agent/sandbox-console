#!/usr/bin/env python3
"""Check hand-calculated contract projections, not a production event reducer."""
import json
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path


def check(case):
    totals, costs, last_end = {}, {}, {}
    uncertain_ms = 0
    for row in case["segments"]:
        start, end, quantity = row["start_ms"], row["end_ms"], row["quantity"]
        assert all(type(v) is int for v in (start, end, quantity))
        assert 0 <= start <= end and quantity >= 0
        key = (row["resource"], row["meter"])
        assert start >= last_end.get(key, 0), "overlapping resource segments"
        last_end[key] = end
        certainty = row.get("certainty", "confirmed")
        assert certainty in ("confirmed", "uncertain")
        if certainty == "uncertain":
            uncertain_ms += end - start
            continue
        bucket = row["bucket"]
        if bucket[:4].isdigit():
            for instant in (start, end - 1):
                assert datetime.fromtimestamp(instant / 1000, timezone.utc).strftime("%Y-%m") == bucket[:7]
        units = quantity * (end - start)
        totals[bucket] = totals.get(bucket, 0) + units
        if "rate" in row:
            numerator, denominator = row["rate"]
            assert type(numerator) is int and type(denominator) is int
            assert numerator >= 0 and denominator > 0
            costs[bucket] = costs.get(bucket, Fraction()) + Fraction(units * numerator, denominator)
    rounded = {key: (2 * value.numerator + value.denominator) // (2 * value.denominator)
               for key, value in costs.items()}
    assert totals == case["expected_units"], (totals, case["expected_units"])
    assert rounded == case.get("expected_minor", {}), rounded
    assert uncertain_ms == case.get("expected_uncertain_resource_ms", 0), uncertain_ms


if __name__ == "__main__":
    source = Path(__file__).resolve().parents[1] / "docs/contracts/ledger-examples.json"
    examples = json.loads(source.read_text())
    assert len({case["name"] for case in examples}) == len(examples)
    for example in examples:
        check(example)
        print("PASS", example["name"])
    print(f"{len(examples)} contract examples passed (no runtime/billing integration).")
