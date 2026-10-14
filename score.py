#!/usr/bin/env python3
"""
Count the evidence out of a run log. ← UNIT 4

    python score.py results/run_..._before.md

run_eval.py deliberately leaves the Verdict column blank, because deciding
what counts as a pass depends on criteria I wrote. This script does not decide
anything either — it counts the evidence lines run_eval already printed, so
that "4 of 5" is a number I read rather than a number I eyeballed across
thirteen hundred lines of output. The verdicts in README.md are mine.

Note on `ids_consistent` for the impossible-query scenario: there are no ids
to compare on that path, because it stops before an item is selected. It
prints False there for want of anything to compare, not because state broke.
"""

import re
import sys


def summarise(path: str) -> None:
    text = open(path, encoding="utf-8").read()
    print(f"##### {path}")
    for block in re.split(r"^### ", text, flags=re.M)[1:]:
        name = block.split("\n")[0]
        cards = re.findall(
            r"- card: sentences=(\d+) price_as_numeral=(\w+) platform_named=(\w+)", block
        )
        openings = re.findall(r"- card opening: (.*)", block)
        ids = re.findall(
            r"- ids: search_results\[0\]=(\S+) selected_item=(\S+) handoff_ids=(\{[^}]*\})",
            block,
        )
        stops = len(re.findall(r"- stopped early: yes", block))
        over = re.findall(r"over_ceiling=(\d+)", block)

        print(f"{name}")
        print(
            f"  stopped_early={stops}/5"
            f"  numeral={[c[1] for c in cards]}"
            f"  sentences={[c[0] for c in cards]}"
        )
        print(
            f"  distinct_openings={len(set(openings))}/{len(openings)}"
            f"  over_ceiling={over}"
            f"  ids_consistent={all(a == b and b in c for a, b, c in ids) if ids else None}"
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for argument in sys.argv[1:]:
        summarise(argument)
