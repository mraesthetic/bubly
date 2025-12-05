"""Main file for generating results for sample ways-pay game."""

import os
from gamestate import GameState
from game_config import GameConfig
from game_optimization import OptimizationSetup
from optimization_program.run_script import OptimizationExecution
from utils.game_analytics.run_analysis import create_stat_sheet
from utils.rgs_verification import execute_all_tests
from src.state.run_sims import create_books
from src.write_data.write_configs import generate_configs

if __name__ == "__main__":

    aws_fast = os.getenv("AWS_FAST", "").lower() in {"1", "true", "yes"}
    if aws_fast:
        num_threads = min(os.cpu_count() or 32, 32)
        rust_threads = num_threads * 2
        batching_size = 5000
        compression = True
        profiling = False
        sims_per_mode = 1000
    else:
        num_threads = 10
        rust_threads = 20
        batching_size = 10000
        compression = True
        profiling = False
        sims_per_mode = 10000

    num_sim_args = {
        "base": 500000,
        "bonus_hunt": 500000,
        "regular_buy": 500000,
        "super_buy": 500000,
    }

    run_conditions = {
        "run_sims": True,
        "run_optimization": True,
        "run_analysis": True,
        "run_format_checks": True,
    }
    target_modes = ["base", "bonus_hunt", "regular_buy", "super_buy"] # "bonus_hunt", "regular_buy", "super_buy"]

    config = GameConfig()
    gamestate = GameState(config)
    if run_conditions["run_optimization"] or run_conditions["run_analysis"]:
        optimization_setup_class = OptimizationSetup(config)

    if run_conditions["run_sims"]:
        create_books(
            gamestate,
            config,
            num_sim_args,
            batching_size,
            num_threads,
            compression,
            profiling,
        )

    generate_configs(gamestate)

    if run_conditions["run_optimization"]:
        OptimizationExecution().run_all_modes(config, target_modes, rust_threads)
        generate_configs(gamestate)

    if run_conditions["run_analysis"]:
        custom_keys = [{"symbol": "scatter"}]
        create_stat_sheet(gamestate, custom_keys=custom_keys)

    if run_conditions["run_format_checks"]:
        execute_all_tests(config)
