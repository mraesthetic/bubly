#!/usr/bin/env python3
"""
Deterministically rebuild reel strips for all 0_0_scatter modes.

Constraints enforced here:
* Each reel (column) contains at most one scatter symbol total.
* Base strips (also used by Hunt) support both S and BS scatters; REG/SUPER strips only allow S.
* Multiplier bombs (M) are inserted only on REG/SUPER strips.
"""

from __future__ import annotations

import csv
import random
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

ROWS_PER_REEL = 60
NUM_REELS = 6
REELS_DIR = Path(__file__).resolve().parents[1] / "reels"

SymbolColumn = List[str]


def build_weighted_column(weights: Dict[str, int], rng: random.Random) -> SymbolColumn:
    population = list(weights.keys())
    weight_values = list(weights.values())
    return rng.choices(population, weights=weight_values, k=ROWS_PER_REEL)


def strip_existing_scatters(column: SymbolColumn) -> None:
    for row_idx in range(len(column)):
        if column[row_idx] in {"S", "BS"}:
            column[row_idx] = "L1"


def place_symbol(column: SymbolColumn, row: int, symbol: str) -> None:
    if not 0 <= row < ROWS_PER_REEL:
        raise ValueError(f"row {row} is outside reel bounds")
    column[row] = symbol


def validate_columns(
    columns: List[SymbolColumn], *, allow_super_scatter: bool, mode_name: str
) -> None:
    for reel_idx, column in enumerate(columns):
        scatter_count = column.count("S")
        super_scatter_count = column.count("BS")
        if scatter_count > 1:
            raise ValueError(f"{mode_name}: reel {reel_idx} has {scatter_count} S symbols.")
        if super_scatter_count > 1:
            raise ValueError(f"{mode_name}: reel {reel_idx} has {super_scatter_count} BS symbols.")
        if scatter_count + super_scatter_count > 1:
            raise ValueError(f"{mode_name}: reel {reel_idx} contains both S and BS symbols.")
        if super_scatter_count and not allow_super_scatter:
            raise ValueError(f"{mode_name}: reel {reel_idx} illegally contains BS.")


def write_reel_file(mode: str, columns: List[SymbolColumn]) -> None:
    REELS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REELS_DIR / f"{mode}.csv"
    with output_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        for row_idx in range(ROWS_PER_REEL):
            writer.writerow([columns[reel_idx][row_idx] for reel_idx in range(NUM_REELS)])


def summarize(columns: List[SymbolColumn]) -> str:
    counts = Counter()
    for column in columns:
        counts.update(column)
    ordered = ", ".join(f"{symbol}:{counts[symbol]}" for symbol in sorted(counts))
    return ordered


def build_mode(mode_name: str, config: dict) -> None:
    rng = random.Random(config["seed"])
    columns = [build_weighted_column(config["weights"], rng) for _ in range(NUM_REELS)]

    for reel_idx, scatter_info in config["scatter_map"].items():
        strip_existing_scatters(columns[reel_idx])
        place_symbol(columns[reel_idx], scatter_info["row"], scatter_info["symbol"])

    for reel_idx, rows in config.get("multiplier_rows", {}).items():
        for row in rows:
            if columns[reel_idx][row] in {"S", "BS"}:
                raise ValueError(
                    f"{mode_name}: multiplier row {row} on reel {reel_idx} conflicts with a scatter."
                )
            place_symbol(columns[reel_idx], row, "M")

    validate_columns(columns, allow_super_scatter=config["allow_super_scatter"], mode_name=mode_name)
    write_reel_file(mode_name, columns)
    print(f"{mode_name}: {summarize(columns)}")


def main():
    modes = {
        "BASE": {
            "seed": 73,
            "weights": {
                "H1": 6,
                "H2": 5,
                "H3": 4,
                "H4": 4,
                "L1": 10,
                "L2": 9,
                "L3": 8,
                "L4": 8,
                "L5": 6,
            },
            "scatter_map": {
                0: {"symbol": "S", "row": 5},
                1: {"symbol": "S", "row": 15},
                2: {"symbol": "S", "row": 25},
                3: {"symbol": "S", "row": 35},
                4: {"symbol": "S", "row": 45},
                5: {"symbol": "BS", "row": 10},
            },
            "allow_super_scatter": True,
        },
        "REG": {
            "seed": 907,
            "weights": {
                "H1": 5,
                "H2": 5,
                "H3": 5,
                "H4": 4,
                "L1": 6,
                "L2": 6,
                "L3": 5,
                "L4": 5,
                "L5": 4,
            },
            "scatter_map": {
                0: {"symbol": "S", "row": 6},
                1: {"symbol": "S", "row": 16},
                2: {"symbol": "S", "row": 26},
                3: {"symbol": "S", "row": 36},
                4: {"symbol": "S", "row": 46},
                5: {"symbol": "S", "row": 56},
            },
            "multiplier_rows": {
                0: [12, 42],
                2: [8, 32],
                3: [22],
                4: [18, 48],
                5: [28],
            },
            "allow_super_scatter": False,
        },
        "SUPER": {
            "seed": 1337,
            "weights": {
                "H1": 5,
                "H2": 5,
                "H3": 4,
                "H4": 4,
                "L1": 5,
                "L2": 5,
                "L3": 5,
                "L4": 4,
                "L5": 4,
            },
            "scatter_map": {
                0: {"symbol": "S", "row": 5},
                1: {"symbol": "S", "row": 15},
                2: {"symbol": "S", "row": 25},
                3: {"symbol": "S", "row": 35},
                4: {"symbol": "S", "row": 45},
                5: {"symbol": "S", "row": 55},
            },
            "multiplier_rows": {
                0: [9, 33, 49],
                1: [13, 39],
                2: [23, 53],
                3: [17, 37],
                4: [27, 47],
                5: [31, 51],
            },
            "allow_super_scatter": False,
        },
    }

    for mode_name, config in modes.items():
        build_mode(mode_name, config)


if __name__ == "__main__":
    main()

