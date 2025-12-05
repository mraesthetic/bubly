import multiprocessing as mp
import os
import random
from collections import Counter
from typing import Dict, Iterable, Optional, Tuple

from game_config import GameConfig
from gamestate import GameState

CONFIG = GameConfig()
GAMESTATE = GameState(CONFIG)

WIN_BUCKET_LABELS: Iterable[str] = [
    "0",
    "(0,0.5]",
    "(0.5,1]",
    "(1,5]",
    "(5,20]",
    "(20, inf)",
]

BONUS_BUCKET_KEYS: Iterable[str] = [
    "0x",
    "0-10x",
    "10-50x",
    "50-100x",
    "100-250x",
    "250x+",
]

MODE_TRIGGER_CONFIG = {
    "base": {
        "target_regular_rate": 1.0 / 180.0,
        "target_super_rate": 1.0 / 1800.0,
        "force_regular_weight": 1.0,
        "force_super_weight": 0.10,
        "global_force_base_prob": 0.05,
    },
    "bonus_hunt": {
        "target_regular_rate": 1.0 / 70.0,
        "target_super_rate": 1.0 / 700.0,
        "force_regular_weight": 1.0,
        "force_super_weight": 0.20,
        "global_force_base_prob": 0.07,
    },
}

MODE_BET_MULTIPLIER = {
    "base": 1.0,
    "bonus_hunt": 3.0,
}


def _split_work(total: int, parts: int) -> list[int]:
    """Divide work into roughly equal integer chunks."""
    base = total // parts
    remainder = total % parts
    sizes: list[int] = []
    for i in range(parts):
        chunk = base + (1 if i < remainder else 0)
        if chunk > 0:
            sizes.append(chunk)
    return sizes


def get_trigger_config(mode: str) -> dict:
    """Return trigger configuration for the requested mode."""
    return MODE_TRIGGER_CONFIG.get(mode, MODE_TRIGGER_CONFIG["base"])


def _classify_bonus_bucket(win: float) -> str:
    if win < 0.01:
        return "0x"
    if win <= 10:
        return "0-10x"
    if win <= 50:
        return "10-50x"
    if win <= 100:
        return "50-100x"
    if win <= 250:
        return "100-250x"
    return "250x+"


def choose_forced_bonus_type(
    mode: str,
    total_spins: int,
    actual_regular_count: int,
    actual_super_count: int,
) -> str:
    """Decide whether a forced bonus should be regular or super."""
    if total_spins <= 0:
        return "regular"

    config = get_trigger_config(mode)
    target_regular_rate = config["target_regular_rate"]
    target_super_rate = config["target_super_rate"]
    rate_regular = actual_regular_count / float(total_spins)
    rate_super = actual_super_count / float(total_spins)
    reg_below_target = rate_regular < target_regular_rate * 0.9
    super_below_target = rate_super < target_super_rate * 0.9

    if reg_below_target and not super_below_target:
        return "regular"

    if super_below_target and not reg_below_target:
        if random.random() < config["force_super_weight"]:
            return "super"
        return "regular"

    total_weight = config["force_regular_weight"] + config["force_super_weight"]
    if total_weight <= 0:
        return "regular"
    threshold = config["force_super_weight"] / total_weight
    if random.random() < threshold:
        return "super"
    return "regular"


def maybe_force_bonus_globally(
    mode: str,
    total_spins: int,
    actual_regular_count: int,
    actual_super_count: int,
) -> Optional[str]:
    """Decide whether to globally force a bonus when none naturally occurred."""
    if total_spins <= 0:
        return None

    config = get_trigger_config(mode)
    target_regular_rate = config["target_regular_rate"]
    target_super_rate = config["target_super_rate"]
    rate_regular = actual_regular_count / float(total_spins)
    rate_super = actual_super_count / float(total_spins)
    deficit_regular = target_regular_rate - rate_regular
    deficit_super = target_super_rate - rate_super

    if deficit_regular <= 0 and deficit_super <= 0:
        return None

    reg_factor = max(0.0, min(1.0, deficit_regular / target_regular_rate))
    sup_factor = max(0.0, min(1.0, deficit_super / target_super_rate))
    force_factor = max(reg_factor, sup_factor)
    if force_factor <= 0.0:
        return None

    p_force = config["global_force_base_prob"] * force_factor
    if random.random() >= p_force:
        return None

    return choose_forced_bonus_type(
        mode=mode,
        total_spins=total_spins,
        actual_regular_count=actual_regular_count,
        actual_super_count=actual_super_count,
    )


def simulate_single_spin(
    mode: str = "base",
    debug: bool = False,
    include_bonuses: bool = True,
    forced_context: Optional[Dict[str, int]] = None,
) -> Dict[str, object]:
    """Simulate a single spin in the requested mode using the live game logic."""
    betmode = _get_betmode(mode)
    distribution = _get_distribution(betmode)

    GAMESTATE.betmode = betmode.get_name()
    GAMESTATE.criteria = distribution.get_criteria()
    GAMESTATE.gametype = CONFIG.basegame_type
    GAMESTATE.reset_seed(random.randint(0, 1_000_000_000))

    result = _execute_spin(
        mode=mode, debug=debug, include_bonuses=include_bonuses, forced_context=forced_context
    )
    return result


def run_monte_carlo(
    num_spins: int, mode: str = "base", include_bonuses: bool = True, processes: Optional[int] = None
) -> Dict[str, object]:
    """Run many single spins and aggregate statistics for the requested mode.

    When `processes` is greater than 1 (or left as None, which defaults to CPU count),
    the workload is distributed across multiple processes for faster execution.
    """
    if processes is None:
        processes = max(1, min(os.cpu_count() or 1, num_spins))
    processes = max(1, processes)
    if processes == 1 or num_spins < processes:
        chunk_result = _run_monte_carlo_chunk(num_spins, mode, include_bonuses)
        return _finalize_monte_carlo_result([chunk_result], mode)

    chunk_sizes = _split_work(num_spins, processes)
    with mp.Pool(len(chunk_sizes)) as pool:
        chunk_results = pool.starmap(
            _run_monte_carlo_chunk, [(chunk, mode, include_bonuses) for chunk in chunk_sizes]
        )
    return _finalize_monte_carlo_result(chunk_results, mode)


def _run_monte_carlo_chunk(num_spins: int, mode: str, include_bonuses: bool) -> Dict[str, object]:
    total_return = 0.0
    sum_base_win_no_bonus = 0.0
    sum_regular_bonus_win = 0.0
    sum_super_bonus_win = 0.0
    wins_by_bucket = {label: 0 for label in WIN_BUCKET_LABELS}
    scatter_counts: Counter[int] = Counter()
    regular_bonus_triggers = 0
    super_bonus_triggers = 0
    natural_regular_triggers = 0
    natural_super_triggers = 0
    actual_regular_triggers = 0
    actual_super_triggers = 0
    hits = 0

    for spin_index in range(num_spins):
        forced_context = {
            "total_spins": spin_index + 1,
            "actual_regular_count": actual_regular_triggers,
            "actual_super_count": actual_super_triggers,
        }
        outcome = simulate_single_spin(
            mode=mode,
            include_bonuses=include_bonuses,
            forced_context=forced_context,
        )
        total_win = outcome["total_win"]
        total_return += total_win
        sum_base_win_no_bonus += outcome["base_win_no_bonus"]
        sum_regular_bonus_win += outcome["regular_bonus_win"]
        sum_super_bonus_win += outcome["super_bonus_win"]
        bucket = _classify_bucket(total_win)
        wins_by_bucket[bucket] += 1
        scatter_counts[outcome["scatter_count"]] += 1
        hits += int(outcome["hit"])
        regular_bonus_triggers += int(outcome["regular_bonus_triggered"])
        super_bonus_triggers += int(outcome["super_bonus_triggered"])
        natural_type = outcome.get("natural_bonus_type")
        if natural_type == "regular":
            natural_regular_triggers += 1
        elif natural_type == "super":
            natural_super_triggers += 1
        actual_type = outcome.get("actual_bonus_type")
        if actual_type == "regular":
            actual_regular_triggers += 1
        elif actual_type == "super":
            actual_super_triggers += 1

    zero_rate = wins_by_bucket["0"] / num_spins
    hit_rate = hits / num_spins
    total_bonus_triggers = regular_bonus_triggers + super_bonus_triggers
    regular_bonus_rate = (num_spins / regular_bonus_triggers) if regular_bonus_triggers else None
    super_bonus_rate = (num_spins / super_bonus_triggers) if super_bonus_triggers else None
    natural_regular_rate = (num_spins / natural_regular_triggers) if natural_regular_triggers else None
    natural_super_rate = (num_spins / natural_super_triggers) if natural_super_triggers else None
    actual_regular_rate = (num_spins / actual_regular_triggers) if actual_regular_triggers else None
    actual_super_rate = (num_spins / actual_super_triggers) if actual_super_triggers else None
    bet_per_spin = MODE_BET_MULTIPLIER.get(mode, 1.0)
    total_bet = num_spins * bet_per_spin

    return {
        "mode": mode,
        "num_spins": num_spins,
        "bet_per_spin": bet_per_spin,
        "total_return": total_return,
        "total_bet": total_bet,
        "wins_by_bucket": wins_by_bucket,
        "regular_bonus_triggers": regular_bonus_triggers,
        "super_bonus_triggers": super_bonus_triggers,
        "bonus_triggers": total_bonus_triggers,
        "regular_bonus_rate": regular_bonus_rate,
        "super_bonus_rate": super_bonus_rate,
        "natural_regular_triggers": natural_regular_triggers,
        "natural_super_triggers": natural_super_triggers,
        "natural_regular_rate": natural_regular_rate,
        "natural_super_rate": natural_super_rate,
        "actual_regular_triggers": actual_regular_triggers,
        "actual_super_triggers": actual_super_triggers,
        "actual_regular_rate": actual_regular_rate,
        "actual_super_rate": actual_super_rate,
        "scatter_counts": dict(scatter_counts),
        "hit_count": hits,
        "sum_base_win_no_bonus": sum_base_win_no_bonus,
        "sum_regular_bonus_win": sum_regular_bonus_win,
        "sum_super_bonus_win": sum_super_bonus_win,
    }


def _finalize_monte_carlo_result(results: Iterable[Dict[str, object]], mode: str) -> Dict[str, object]:
    aggregate = {
        "mode": mode,
        "num_spins": 0,
        "bet_per_spin": MODE_BET_MULTIPLIER.get(mode, 1.0),
        "total_return": 0.0,
        "wins_by_bucket": {label: 0 for label in WIN_BUCKET_LABELS},
        "regular_bonus_triggers": 0,
        "super_bonus_triggers": 0,
        "bonus_triggers": 0,
        "regular_bonus_rate": None,
        "super_bonus_rate": None,
        "natural_regular_triggers": 0,
        "natural_super_triggers": 0,
        "natural_regular_rate": None,
        "natural_super_rate": None,
        "actual_regular_triggers": 0,
        "actual_super_triggers": 0,
        "actual_regular_rate": None,
        "actual_super_rate": None,
        "scatter_counts": Counter(),
        "hit_count": 0,
        "sum_base_win_no_bonus": 0.0,
        "sum_regular_bonus_win": 0.0,
        "sum_super_bonus_win": 0.0,
    }

    for res in results:
        aggregate["num_spins"] += res["num_spins"]
        aggregate["bet_per_spin"] = res["bet_per_spin"]
        aggregate["total_return"] += res["total_return"]
        aggregate["regular_bonus_triggers"] += res["regular_bonus_triggers"]
        aggregate["super_bonus_triggers"] += res["super_bonus_triggers"]
        aggregate["bonus_triggers"] += res["bonus_triggers"]
        aggregate["natural_regular_triggers"] += res["natural_regular_triggers"]
        aggregate["natural_super_triggers"] += res["natural_super_triggers"]
        aggregate["actual_regular_triggers"] += res["actual_regular_triggers"]
        aggregate["actual_super_triggers"] += res["actual_super_triggers"]
        aggregate["sum_base_win_no_bonus"] += res["sum_base_win_no_bonus"]
        aggregate["sum_regular_bonus_win"] += res["sum_regular_bonus_win"]
        aggregate["sum_super_bonus_win"] += res["sum_super_bonus_win"]
        aggregate["hit_count"] += res["hit_count"]
        aggregate["scatter_counts"].update(res["scatter_counts"])
        for label in aggregate["wins_by_bucket"]:
            aggregate["wins_by_bucket"][label] += res["wins_by_bucket"].get(label, 0)

    total_bet = aggregate["num_spins"] * aggregate["bet_per_spin"]
    zero_hits = aggregate["wins_by_bucket"].get("0", 0)
    result = {
        "mode": mode,
        "num_spins": aggregate["num_spins"],
        "bet_per_spin": aggregate["bet_per_spin"],
        "total_return": aggregate["total_return"],
        "total_bet": total_bet,
        "wins_by_bucket": aggregate["wins_by_bucket"],
        "regular_bonus_triggers": aggregate["regular_bonus_triggers"],
        "super_bonus_triggers": aggregate["super_bonus_triggers"],
        "bonus_triggers": aggregate["bonus_triggers"],
        "regular_bonus_rate": (
            aggregate["num_spins"] / aggregate["regular_bonus_triggers"]
            if aggregate["regular_bonus_triggers"]
            else None
        ),
        "super_bonus_rate": (
            aggregate["num_spins"] / aggregate["super_bonus_triggers"]
            if aggregate["super_bonus_triggers"]
            else None
        ),
        "natural_regular_triggers": aggregate["natural_regular_triggers"],
        "natural_super_triggers": aggregate["natural_super_triggers"],
        "natural_regular_rate": (
            aggregate["num_spins"] / aggregate["natural_regular_triggers"]
            if aggregate["natural_regular_triggers"]
            else None
        ),
        "natural_super_rate": (
            aggregate["num_spins"] / aggregate["natural_super_triggers"]
            if aggregate["natural_super_triggers"]
            else None
        ),
        "actual_regular_triggers": aggregate["actual_regular_triggers"],
        "actual_super_triggers": aggregate["actual_super_triggers"],
        "actual_regular_rate": (
            aggregate["num_spins"] / aggregate["actual_regular_triggers"]
            if aggregate["actual_regular_triggers"]
            else None
        ),
        "actual_super_rate": (
            aggregate["num_spins"] / aggregate["actual_super_triggers"]
            if aggregate["actual_super_triggers"]
            else None
        ),
        "scatter_counts": dict(aggregate["scatter_counts"]),
        "hit_rate": aggregate["hit_count"] / aggregate["num_spins"] if aggregate["num_spins"] else 0.0,
        "zero_rate": zero_hits / aggregate["num_spins"] if aggregate["num_spins"] else 0.0,
        "sum_base_win_no_bonus": aggregate["sum_base_win_no_bonus"],
        "sum_regular_bonus_win": aggregate["sum_regular_bonus_win"],
        "sum_super_bonus_win": aggregate["sum_super_bonus_win"],
    }
    return result


def summarize_base_results(results: Dict[str, object]) -> None:
    """Print a short summary for base-mode Monte Carlo output."""
    num_spins = results["num_spins"]
    sum_base = results["sum_base_win_no_bonus"]
    sum_regular = results["sum_regular_bonus_win"]
    sum_super = results["sum_super_bonus_win"]
    total_bet = results.get("total_bet", num_spins)
    rtp_base = sum_base / total_bet if total_bet else 0.0
    rtp_regular = sum_regular / total_bet if total_bet else 0.0
    rtp_super = sum_super / total_bet if total_bet else 0.0
    rtp_total = (sum_base + sum_regular + sum_super) / total_bet if total_bet else 0.0
    print(f"Estimated base RTP (no bonus): {rtp_base:.4f}x")
    print(f"Estimated regular bonus RTP: {rtp_regular:.4f}x")
    print(f"Estimated super bonus RTP: {rtp_super:.4f}x")
    print(f"Total RTP: {rtp_total:.4f}x")
    print(f"Hit rate: {results['hit_rate']:.2%}")
    print(f"Zero-win rate: {results['zero_rate']:.2%}")
    print("Win bucket frequencies:")
    for label in WIN_BUCKET_LABELS:
        count = results["wins_by_bucket"].get(label, 0)
        print(f"  {label}: {count} ({count / num_spins:.2%})")

    regular_triggers = results["regular_bonus_triggers"]
    super_triggers = results["super_bonus_triggers"]
    if regular_triggers:
        print(f"Estimated regular bonus rate: 1 in {results['regular_bonus_rate']:.1f}")
    else:
        print(f"Estimated regular bonus rate: >{num_spins} spins (no triggers)")
    if super_triggers:
        print(f"Estimated super bonus rate: 1 in {results['super_bonus_rate']:.1f}")
    else:
        print(f"Estimated super bonus rate: >{num_spins} spins (no triggers)")
    natural_reg = results.get("natural_regular_triggers")
    natural_sup = results.get("natural_super_triggers")
    if natural_reg is not None:
        if natural_reg:
            print(f"Natural regular trigger rate: 1 in {results['natural_regular_rate']:.1f}")
        else:
            print(f"Natural regular trigger rate: >{num_spins} spins (no natural hits)")
    if natural_sup is not None:
        if natural_sup:
            print(f"Natural super trigger rate: 1 in {results['natural_super_rate']:.1f}")
        else:
            print(f"Natural super trigger rate: >{num_spins} spins (no natural hits)")
    actual_reg = results.get("actual_regular_triggers")
    actual_sup = results.get("actual_super_triggers")
    if actual_reg:
        print(f"Actual regular bonus rate: 1 in {results['actual_regular_rate']:.1f}")
    else:
        print(f"Actual regular bonus rate: >{num_spins} spins (none)")
    if actual_sup:
        print(f"Actual super bonus rate: 1 in {results['actual_super_rate']:.1f}")
    else:
        print(f"Actual super bonus rate: >{num_spins} spins (none)")


def _get_betmode(mode: str):
    for bm in CONFIG.bet_modes:
        if bm.get_name() == mode:
            return bm
    raise ValueError(f"Unknown bet mode '{mode}'")


def _get_distribution(betmode, criteria: str = "freegame"):
    distributions = betmode.get_distributions()
    for dist in distributions:
        if dist.get_criteria() == criteria:
            return dist
    return distributions[0]


def _execute_spin(
    mode: str,
    debug: bool = False,
    include_bonuses: bool = True,
    forced_context: Optional[Dict[str, int]] = None,
) -> Dict[str, object]:
    GAMESTATE.repeat = True
    scatter_count = 0
    regular_scatter = 0
    super_scatter = 0
    triggered_bonus = False
    triggered_regular = False
    triggered_super = False
    debug_board = None
    natural_bonus_type = None

    while GAMESTATE.repeat:
        GAMESTATE.reset_book()
        GAMESTATE.draw_board()
        GAMESTATE.get_special_symbols_on_board()
        scatter_count, regular_scatter, super_scatter = _count_initial_scatters()
        natural_bonus_type = GAMESTATE.get_natural_bonus_type()
        if debug:
            debug_board = _format_board(GAMESTATE.board_string(GAMESTATE.board))

        GAMESTATE.get_scatterpays_update_wins()
        GAMESTATE.emit_tumble_win_events()
        while GAMESTATE.win_data["totalWin"] > 0 and not GAMESTATE.wincap_triggered:
            GAMESTATE.tumble_game_board()
            GAMESTATE.get_scatterpays_update_wins()
            GAMESTATE.emit_tumble_win_events()

        GAMESTATE.set_end_tumble_event()
        GAMESTATE.win_manager.update_gametype_wins(GAMESTATE.gametype)
    distribution_conditions = GAMESTATE.get_current_distribution_conditions()
    bonus_type_detected = None
    if GAMESTATE.should_trigger_super_bonus() and GAMESTATE.check_super_bonus_entry():
        bonus_type_detected = "super"
    elif GAMESTATE.check_fs_condition() and GAMESTATE.check_freespin_entry():
        bonus_type_detected = "regular"

    forced_bonus = False
    if forced_context and bonus_type_detected is not None:
        forced_bonus = (
            distribution_conditions.get("force_freegame")
            or distribution_conditions.get("force_super_bonus")
            or bonus_type_detected != natural_bonus_type
        )

    bonus_type_to_run = bonus_type_detected
    if forced_bonus and forced_context:
        bonus_type_to_run = choose_forced_bonus_type(
            mode=mode,
            total_spins=max(forced_context.get("total_spins", 0), 1),
            actual_regular_count=forced_context.get("actual_regular_count", 0),
            actual_super_count=forced_context.get("actual_super_count", 0),
        )

    if (
        bonus_type_to_run is None
        and forced_context is not None
        and natural_bonus_type is None
    ):
        global_forced_type = maybe_force_bonus_globally(
            mode=mode,
            total_spins=max(forced_context.get("total_spins", 0), 1),
            actual_regular_count=forced_context.get("actual_regular_count", 0),
            actual_super_count=forced_context.get("actual_super_count", 0),
        )
        if global_forced_type:
            bonus_type_to_run = global_forced_type

    if include_bonuses:
        if bonus_type_to_run == "super":
            triggered_super = True
            triggered_bonus = True
            GAMESTATE.run_super_bonus_from_base()
        elif bonus_type_to_run == "regular":
            triggered_regular = True
            triggered_bonus = True
            GAMESTATE.run_freespin_from_base()
    else:
        if bonus_type_to_run == "super":
            triggered_super = True
            triggered_bonus = True
        elif bonus_type_to_run == "regular":
            triggered_regular = True
            triggered_bonus = True

        GAMESTATE.evaluate_finalwin()
        GAMESTATE.check_repeat()

    GAMESTATE.imprint_wins()
    GAMESTATE.library.clear()
    GAMESTATE.recorded_events = {}

    base_win = GAMESTATE.win_manager.basegame_wins
    bonus_win = GAMESTATE.win_manager.freegame_wins
    total_win = base_win + (bonus_win if include_bonuses else 0.0)

    result = {
        "total_win": total_win,
        "hit": total_win > 0,
        "bonus_triggered": triggered_bonus,
        "regular_bonus_triggered": triggered_regular,
        "super_bonus_triggered": triggered_super,
        "scatter_count": scatter_count,
        "regular_scatter_count": regular_scatter,
        "super_scatter_count": super_scatter,
        "base_win": base_win,
        "bonus_win": bonus_win,
        "base_win_no_bonus": base_win,
        "regular_bonus_win": bonus_win if triggered_regular else 0.0,
        "super_bonus_win": bonus_win if triggered_super else 0.0,
        "natural_bonus_type": natural_bonus_type,
        "actual_bonus_type": "super" if triggered_super else "regular" if triggered_regular else None,
    }
    if debug:
        result["board"] = debug_board
    return result


def _count_initial_scatters() -> Tuple[int, int, int]:
    regular = len(GAMESTATE.special_syms_on_board.get("scatter", []))
    super_scatter = len(GAMESTATE.special_syms_on_board.get("super_scatter", []))
    return regular + super_scatter, regular, super_scatter


def _classify_bucket(win: float) -> str:
    if win == 0:
        return "0"
    if 0 < win <= 0.5:
        return "(0,0.5]"
    if 0.5 < win <= 1:
        return "(0.5,1]"
    if 1 < win <= 5:
        return "(1,5]"
    if 5 < win <= 20:
        return "(5,20]"
    return "(20, inf)"


def _format_board(board_columns) -> str:
    column_strings = ["[" + ",".join(col) + "]" for col in board_columns]
    return " | ".join(column_strings)


def debug_sample_spins(num_spins: int = 20, mode: str = "base") -> None:
    """Print detailed information for a handful of spins to verify accounting."""
    for i in range(num_spins):
        outcome = simulate_single_spin(mode=mode, debug=True)
        print(
            f"Spin {i+1}: bet=1.0 board={outcome.get('board')}"
            f" base_win={outcome['base_win']:.2f} bonus_win={outcome['bonus_win']:.2f}"
            f" total={outcome['total_win']:.2f} "
            f"regular_bonus={outcome['regular_bonus_triggered']} super_bonus={outcome['super_bonus_triggered']}"
        )


def _play_bonus_round(bonus_type: str, mode: str = "base") -> dict:
    """Run a single bonus round (regular or super) and return detailed stats."""
    assert bonus_type in {"regular", "super"}
    GAMESTATE.reset_seed(random.randint(0, 1_000_000_000))
    GAMESTATE.reset_book()
    if mode in {"regular_buy", "super_buy", "base", "bonus_hunt"}:
        betmode_name = mode
    else:
        betmode_name = "super_buy" if bonus_type == "super" else "regular_buy"
    GAMESTATE.betmode = betmode_name
    GAMESTATE.criteria = "freegame"
    GAMESTATE.refresh_special_syms()
    if bonus_type == "super":
        GAMESTATE.special_syms_on_board["scatter"] = [{"reel": i, "row": 0} for i in range(3)]
        GAMESTATE.special_syms_on_board["super_scatter"] = [{"reel": 3, "row": 0}]
        GAMESTATE.super_bonus_active = True
        GAMESTATE.update_super_bonus_amount()
    else:
        GAMESTATE.special_syms_on_board["scatter"] = [{"reel": i, "row": 0} for i in range(4)]
        GAMESTATE.special_syms_on_board["super_scatter"] = []
        GAMESTATE.super_bonus_active = False
        GAMESTATE.update_freespin_amount()
    GAMESTATE.run_freespin()
    win_amount = GAMESTATE.win_manager.freegame_wins
    spins_played = GAMESTATE.fs
    retriggers = getattr(GAMESTATE, "fs_retrigger_count", 0)
    GAMESTATE.super_bonus_active = False
    return {"win": win_amount, "spins": spins_played, "retriggers": retriggers}


def simulate_freegame_only(num_triggers: int, mode: str = "regular") -> float:
    """Simulate only the freegame portion (regular or super) assuming a trigger already occurred."""
    assert mode in {"regular", "super"}
    total = 0.0
    for _ in range(num_triggers):
        total += _play_bonus_round("super" if mode == "super" else "regular")["win"]
    return total / num_triggers if num_triggers else 0.0


def measure_regular_bonus_ev(num_triggers: int = 5000, mode: str = "base") -> dict:
    """Measure regular bonus EV by running standalone regular bonuses."""
    bucket_counts = {key: 0 for key in BONUS_BUCKET_KEYS}
    total_win = 0.0
    total_spins = 0.0
    total_retriggers = 0.0
    for _ in range(num_triggers):
        result = _play_bonus_round("regular", mode=mode)
        win = result["win"]
        total_win += win
        total_spins += result["spins"]
        total_retriggers += result["retriggers"]
        bucket_counts[_classify_bonus_bucket(win)] += 1
    avg_win = total_win / num_triggers if num_triggers else 0.0
    avg_spins = total_spins / num_triggers if num_triggers else 0.0
    avg_retriggers = total_retriggers / num_triggers if num_triggers else 0.0
    return {
        "avg_win": avg_win,
        "avg_spins": avg_spins,
        "avg_retriggers": avg_retriggers,
        "bucket_counts": bucket_counts,
        "num_triggers": num_triggers,
    }


def measure_super_bonus_ev(num_triggers: int = 3000, mode: str = "base") -> dict:
    """Measure super bonus EV by running standalone super bonuses."""
    bucket_counts = {key: 0 for key in BONUS_BUCKET_KEYS}
    total_win = 0.0
    total_spins = 0.0
    total_retriggers = 0.0
    for _ in range(num_triggers):
        result = _play_bonus_round("super", mode=mode)
        win = result["win"]
        total_win += win
        total_spins += result["spins"]
        total_retriggers += result["retriggers"]
        bucket_counts[_classify_bonus_bucket(win)] += 1
    avg_win = total_win / num_triggers if num_triggers else 0.0
    avg_spins = total_spins / num_triggers if num_triggers else 0.0
    avg_retriggers = total_retriggers / num_triggers if num_triggers else 0.0
    return {
        "avg_win": avg_win,
        "avg_spins": avg_spins,
        "avg_retriggers": avg_retriggers,
        "bucket_counts": bucket_counts,
        "num_triggers": num_triggers,
    }


def measure_buy_mode_rtp(num_buys: int, mode: str, processes: Optional[int] = None) -> dict:
    """Measure RTP for a buy mode by simulating standalone bonuses."""
    assert mode in {"regular_buy", "super_buy"}
    if processes is None:
        processes = max(1, min(os.cpu_count() or 1, num_buys))
    processes = max(1, processes)
    if processes == 1 or num_buys < processes:
        chunk = _measure_buy_mode_chunk(num_buys, mode)
        return _finalize_buy_results([chunk], mode)

    chunk_sizes = _split_work(num_buys, processes)
    with mp.Pool(len(chunk_sizes)) as pool:
        chunks = pool.starmap(_measure_buy_mode_chunk, [(chunk, mode) for chunk in chunk_sizes])
    return _finalize_buy_results(chunks, mode)


def _measure_buy_mode_chunk(num_buys: int, mode: str) -> dict:
    bonus_type = "super" if mode == "super_buy" else "regular"
    bet_cost = 500.0 if bonus_type == "super" else 100.0
    total_win = 0.0
    bucket_counts = {key: 0 for key in BONUS_BUCKET_KEYS}
    for _ in range(num_buys):
        result = _play_bonus_round(bonus_type, mode=mode)
        win = result["win"]
        total_win += win
        bucket_counts[_classify_bonus_bucket(win)] += 1
    return {"runs": num_buys, "total_win": total_win, "bet_cost": bet_cost, "bucket_counts": bucket_counts}


def _finalize_buy_results(chunks: Iterable[dict], mode: str) -> dict:
    total_runs = 0
    total_win = 0.0
    bet_cost = None
    bucket_counts = {key: 0 for key in BONUS_BUCKET_KEYS}
    for chunk in chunks:
        total_runs += chunk["runs"]
        total_win += chunk["total_win"]
        bet_cost = chunk["bet_cost"]
        for key in bucket_counts:
            bucket_counts[key] += chunk["bucket_counts"].get(key, 0)
    total_bet = total_runs * (bet_cost or 0.0)
    rtp = total_win / total_bet if total_bet else 0.0
    avg_win = total_win / total_runs if total_runs else 0.0
    return {"mode": mode, "rtp": rtp, "avg_win": avg_win, "bucket_counts": bucket_counts}


def _format_trigger_rate(rate: float | None, num_spins: int) -> str:
    if rate is None:
        return f"> {num_spins}"
    return f"{rate:.1f}"


def run_full_math_report() -> None:
    """Print a concise RTP summary for base, hunt, and buy modes."""
    modes = [
        ("base", True, 20_000),
        ("bonus_hunt", True, 20_000),
    ]
    print("=== Candy Carnage 1000 – Monte Carlo Summary ===")
    for mode, include_bonuses, spins in modes:
        results = run_monte_carlo(num_spins=spins, mode=mode, include_bonuses=include_bonuses)
        bet_mult = MODE_BET_MULTIPLIER.get(mode, 1.0)
        base_slice = results["sum_base_win_no_bonus"] / results["total_bet"]
        regular_slice = results["sum_regular_bonus_win"] / results["total_bet"]
        super_slice = results["sum_super_bonus_win"] / results["total_bet"]
        total_rtp = base_slice + regular_slice + super_slice
        natural_reg = results.get("natural_regular_rate")
        natural_sup = results.get("natural_super_rate")
        actual_reg = results.get("actual_regular_rate")
        actual_sup = results.get("actual_super_rate")
        print(f"\nMode: {mode}")
        print(f"  Bet multiplier: {bet_mult}x")
        print(f"  Base-only RTP:   {base_slice:.4f}")
        print(f"  Regular bonus:   {regular_slice:.4f}")
        print(f"  Super bonus:     {super_slice:.4f}")
        print(f"  Total RTP:       {total_rtp:.4f}")
        print("")
        print(f"  Hit rate:        {results['hit_rate']:.2%}")
        print(f"  Zero-win:        {results['zero_rate']:.2%}")
        print("")
        print(
            f"  Natural regular: 1 in {_format_trigger_rate(natural_reg, spins)}"
        )
        print(f"  Natural super:   1 in {_format_trigger_rate(natural_sup, spins)}")
        print(f"  Actual regular:  1 in {_format_trigger_rate(actual_reg, spins)}")
        print(f"  Actual super:    1 in {_format_trigger_rate(actual_sup, spins)}")

    print("\n=== Buy Modes ===")
    buy_modes = [
        ("regular_buy", 5_000, 100.0),
        ("super_buy", 5_000, 500.0),
    ]
    for mode, num_buys, cost in buy_modes:
        stats = measure_buy_mode_rtp(num_buys=num_buys, mode=mode)
        buckets = {key: 0 for key in BONUS_BUCKET_KEYS}
        bonus_type = "super" if mode == "super_buy" else "regular"
        for _ in range(num_buys):
            result = _play_bonus_round(bonus_type, mode=mode)
            buckets[_classify_bonus_bucket(result["win"])] += 1
        print(f"\nMode: {mode}")
        print(f"  Buy cost:    {cost:.0f}x")
        print(f"  RTP:         {stats['rtp']:.4f}")
        print(f"  Avg win:     {stats['avg_win']:.2f}x")
        print(f"  Buckets:")
        for key in BONUS_BUCKET_KEYS:
            count = buckets[key]
            pct = count / num_buys if num_buys else 0.0
            print(f"    {key:<8} {count:>5} ({pct:>6.2%})")

