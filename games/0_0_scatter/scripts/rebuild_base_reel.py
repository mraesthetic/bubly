"""
Utility to rebuild BASE.csv with controlled symbol counts.

Constraints:
- Preserve S/BS counts within ±10% of the current totals.
- Reduce total H1–H4 count to ~30–40% of current.
- Enforce max vertical run length for identical symbols.
- Favor L3/L4/L5 as common lows; include L1/L2 sparingly.
"""

from __future__ import annotations

import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Sequence

BASE_PATH = Path(__file__).resolve().parents[1] / "reels" / "BASE.csv"
COLUMNS = 6
MAX_VERTICAL_RUN = 2  # prefer <=2 identical per column

LOW_SYMBOLS = ["L1", "L2", "L3", "L4", "L5"]
HIGH_SYMBOLS = ["H1", "H2", "H3", "H4"]
SCATTERS = ["S", "BS"]


def read_strip(path: Path) -> List[List[str]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            entries = [entry.strip() for entry in line.split(",")]
            assert len(entries) == COLUMNS, f"Row must have {COLUMNS} symbols: {entries}"
            rows.append(entries)
    return rows


def count_symbols(rows: Sequence[Sequence[str]]) -> Counter:
    counts = Counter()
    for row in rows:
        counts.update(row)
    return counts


def plan_counts(original: Counter) -> Counter:
    plan = Counter()
    total_high = sum(original[h] for h in HIGH_SYMBOLS)
    target_high = int(total_high * random.uniform(0.30, 0.40))
    # Evenly distribute high counts among types (may adjust later)
    high_share = max(1, target_high // len(HIGH_SYMBOLS))
    for sym in HIGH_SYMBOLS:
        plan[sym] = high_share
    # Adjust remainder
    while sum(plan[h] for h in HIGH_SYMBOLS) < target_high:
        plan[random.choice(HIGH_SYMBOLS)] += 1

    # maintain scatter counts within ±10%
    for scatter in SCATTERS:
        original_count = original[scatter]
        lower = int(original_count * 0.9)
        upper = int(original_count * 1.1) or 1
        plan[scatter] = random.randint(lower, max(lower, upper))

    # remaining slots go to lows
    total_cells = len(rows) * COLUMNS
    used = sum(plan.values())
    remaining = total_cells - used
    base_lows = ["L3", "L4", "L5", "L3", "L4", "L5", "L5", "L4", "L3", "L2", "L1"]

    while remaining > 0:
        sym = random.choice(base_lows)
        plan[sym] += 1
        remaining -= 1
    return plan


def generate_strip(rows: int, counts: Counter) -> List[List[str]]:
    """Fill a strip row-by-row enforcing vertical constraints."""
    strip = [[None for _ in range(COLUMNS)] for _ in range(rows)]
    column_runs = [([]) for _ in range(COLUMNS)]

    def can_place(col: int, sym: str) -> bool:
        run = column_runs[col]
        if len(run) >= MAX_VERTICAL_RUN and all(r == sym for r in run[-MAX_VERTICAL_RUN:]):
            return False
        return True

    available = []
    for sym, ct in counts.items():
        available.extend([sym] * ct)
    random.shuffle(available)

    for r in range(rows):
        for c in range(COLUMNS):
            placed = False
            random.shuffle(available)
            for idx, sym in enumerate(list(available)):
                if can_place(c, sym):
                    strip[r][c] = sym
                    available.pop(idx)
                    column_runs[c].append(sym)
                    placed = True
                    break
            if not placed:
                # fallback: relax run constraint for lows
                for idx, sym in enumerate(list(available)):
                    if sym not in HIGH_SYMBOLS or len(available) <= 1:
                        strip[r][c] = sym
                        available.pop(idx)
                        column_runs[c].append(sym)
                        placed = True
                        break
            if not placed:
                raise RuntimeError("Could not place symbol while respecting constraints.")
    return strip


def write_strip(path: Path, rows: List[List[str]]) -> None:
    text = "\n".join(",".join(row) for row in rows)
    print(text)


if __name__ == "__main__":
    random.seed(0)
    rows = read_strip(BASE_PATH)
    original_counts = count_symbols(rows)
    plan = plan_counts(original_counts)
    new_strip = generate_strip(len(rows), plan)
    write_strip(BASE_PATH, new_strip)

