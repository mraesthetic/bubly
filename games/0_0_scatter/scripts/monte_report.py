import json
import sys
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parents[1]
if str(GAME_DIR) not in sys.path:
    sys.path.insert(0, str(GAME_DIR))

import sim_utils as s


def summarize_spin_mode(mode: str, spins: int = 200_000, include_bonuses: bool = True):
    res = s.run_monte_carlo(num_spins=spins, mode=mode, include_bonuses=include_bonuses)
    total_bet = res["total_bet"] or 1.0
    buckets = {
        label: {
            "count": res["wins_by_bucket"].get(label, 0),
            "pct": res["wins_by_bucket"].get(label, 0) / res["num_spins"],
        }
        for label in s.WIN_BUCKET_LABELS
    }
    data = {
        "mode": mode,
        "spins": res["num_spins"],
        "bet_per_spin": res["bet_per_spin"],
        "total_rtp": res["total_return"] / total_bet,
        "base_rtp": res["sum_base_win_no_bonus"] / total_bet,
        "regular_bonus_rtp": res["sum_regular_bonus_win"] / total_bet,
        "super_bonus_rtp": res["sum_super_bonus_win"] / total_bet,
        "hit_rate": res["hit_rate"],
        "zero_rate": res["zero_rate"],
        "win_buckets": buckets,
        "bonus_frequency": {
            "natural_regular_1_in": res["natural_regular_rate"],
            "natural_super_1_in": res["natural_super_rate"],
            "actual_regular_1_in": res["actual_regular_rate"],
            "actual_super_1_in": res["actual_super_rate"],
            "regular_trigger_1_in": res["regular_bonus_rate"],
            "super_trigger_1_in": res["super_bonus_rate"],
        },
    }
    return data


def summarize_buy_mode(mode: str, runs: int = 50_000):
    res = s.measure_buy_mode_rtp(runs, mode=mode)
    return {
        "mode": mode,
        "runs": runs,
        "rtp": res["rtp"],
        "avg_win": res["avg_win"],
        "bucket_counts": res["bucket_counts"],
    }


def main():
    summaries = [
        summarize_spin_mode("base"),
        summarize_spin_mode("bonus_hunt"),
        summarize_buy_mode("regular_buy"),
        summarize_buy_mode("super_buy"),
    ]
    for summary in summaries:
        print(f"=== {summary['mode']} ===")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

