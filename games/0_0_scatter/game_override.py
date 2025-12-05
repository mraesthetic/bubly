import random

from game_executables import *
from src.events.events import update_freespin_event, reveal_event
from src.calculations.statistics import get_random_outcome


class GameStateOverride(GameExecutables):
    """
    This class is is used to override or extend universal state.py functions.
    e.g: A specific game may have custom book properties to reset
    """

    def reset_book(self):
        # Reset global values used across multiple projects
        super().reset_book()
        # Reset parameters relevant to local game only
        self.tumble_win = 0
        self.super_bonus_active = False
        self.fs_retrigger_count = 0

    def reset_fs_spin(self):
        super().reset_fs_spin()
        self.fs_retrigger_count = 0

    def draw_board(self, emit_event: bool = True, trigger_symbol: str = "scatter"):
        super().draw_board(emit_event=False, trigger_symbol=trigger_symbol)
        self.get_special_symbols_on_board()
        distribution_conditions = self.get_current_distribution_conditions()
        if distribution_conditions.get("force_super_bonus"):
            self._ensure_super_bonus_mix()
        if emit_event:
            reveal_event(self)

    def assign_special_sym_function(self):
        self.special_symbol_functions = {"M": [self.assign_mult_property]}

    def assign_mult_property(self, symbol):
        """Use betmode conditions to assign multiplier attribute to multiplier symbol."""
        multiplier_value = get_random_outcome(
            self.get_current_distribution_conditions()["mult_values"][self.gametype]
        )
        symbol.assign_attribute({"multiplier": multiplier_value})

    def check_game_repeat(self):
        """Verify final win matches required betmode conditions."""
        if self.repeat == False:
            win_criteria = self.get_current_betmode_distributions().get_win_criteria()
            if win_criteria is not None and self.final_win != win_criteria:
                self.repeat = True

    def _ensure_super_bonus_mix(self):
        """Convert one scatter to BS so forced super bonuses have BS + S mix."""
        super_positions = self.special_syms_on_board.get("super_scatter", [])
        scatter_positions = self.special_syms_on_board.get("scatter", [])
        if super_positions:
            return
        if not scatter_positions:
            return
        target = random.choice(scatter_positions)
        reel, row = target["reel"], target["row"]
        self.board[reel][row] = self.create_symbol("BS")
        self.get_special_symbols_on_board()
