import os
import random
import sys

GAME_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if GAME_DIR not in sys.path:
    sys.path.insert(0, GAME_DIR)

from game_config import GameConfig
from gamestate import GameState


def run_sim(num_spins=10):
    cfg = GameConfig()
    gs = GameState(cfg)
    for mode in cfg.bet_modes:
        if mode._name == "regular_buy":
            betmode = mode
            break
    else:
        raise RuntimeError("regular_buy not found")

    cfg.target_betmode = betmode._name
    gs.betmode = betmode._name
    gs.criteria = betmode._distributions[0]._criteria
    gs.gametype = cfg.basegame_type
    gs.repeat = False
    for spin in range(num_spins):
        gs.reset_book()
        gs.criteria = betmode._distributions[0]._criteria
        gs.draw_board()
        gs.get_special_symbols_on_board()
        s_count = len(gs.special_syms_on_board.get("scatter", []))
        bs_count = len(gs.special_syms_on_board.get("super_scatter", []))
        print(f"Spin {spin}: S={s_count}, BS={bs_count}")


if __name__ == "__main__":
    run_sim()
