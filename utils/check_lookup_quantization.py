import argparse
from pathlib import Path


def assert_quantized(lut_path: Path) -> None:
    """Ensure every payout value in a lookup table is snapped to 0.10x increments."""
    lut_path = lut_path.expanduser().resolve()
    if not lut_path.exists():
        raise FileNotFoundError(f"Lookup table not found: {lut_path}")

    bad_rows = []
    total_rows = 0
    with lut_path.open("r", encoding="UTF-8") as handle:
        for line_number, line in enumerate(handle, 1):
            total_rows += 1
            line = line.strip()
            if not line:
                continue
            try:
                _, _, payout = line.split(",")
            except ValueError as exc:
                raise RuntimeError(f"Malformed lookup row on line {line_number}: {line}") from exc
            payout_cents = int(round(float(payout)))
            if payout_cents % 10 != 0:
                bad_rows.append((line_number, payout_cents))

    if bad_rows:
        sample = ", ".join(f"(line {ln}: {val})" for ln, val in bad_rows[:5])
        raise AssertionError(
            f"{lut_path} contains {len(bad_rows)} non-quantized payouts. "
            f"First offenders: {sample}"
        )
    print(f"{lut_path} OK — {total_rows} rows quantized to 0.10x increments.")


def main():
    parser = argparse.ArgumentParser(description="Verify lookup payouts are 0.10x quantized.")
    parser.add_argument("lookup_path", help="Path to lookUpTable_<mode>.csv")
    args = parser.parse_args()
    assert_quantized(Path(args.lookup_path))


if __name__ == "__main__":
    main()

