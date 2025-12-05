import random

from game_executables import *
from src.events.events import update_freespin_event, reveal_event
from src.calculations.statistics import get_random_outcome


class GameStateOverride(GameExecutables):
    """
    This class is is used to override or extend universal state.py functions.
    e.g: A specific game may have custom book properties to reset
    """

    SCATTER_BLOCKER_SYMBOLS = ("L3", "L4", "L5", "L2")

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
        if distribution_conditions.get("force_super_bonus") and self.gametype == self.config.basegame_type:
            self._ensure_super_bonus_mix()
        self._enforce_scatter_per_reel_limit()
        if emit_event:
            reveal_event(self)

    def tumble_game_board(self):
        super().tumble_game_board()
        self._enforce_scatter_per_reel_limit()
        distribution_conditions = self.get_current_distribution_conditions()
        if distribution_conditions.get("force_super_bonus") and self.gametype == self.config.basegame_type:
            self._ensure_super_bonus_mix()

    def assign_special_sym_function(self):
        self.special_symbol_functions = {"M": [self.assign_mult_property]}

    def assign_mult_property(self, symbol):
        """Use betmode conditions to assign multiplier attribute to multiplier symbol."""
        super_bonus_active = getattr(self, "super_bonus_active", False)
        multiplier_weights = self.config.get_multiplier_pool(self.gametype, super_bonus_active)
        multiplier_value = get_random_outcome(multiplier_weights)
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

    def _clamp_super_bonus_multipliers(self):
        """Replace any low-tier multipliers during super bonus spins."""
        min_super_mult = min(self.config.super_multiplier_weights.keys())
        adjusted = 0
        for reel in self.board:
            for symbol in reel:
                if symbol.check_attribute("multiplier"):
                    mult_value = symbol.get_attribute("multiplier")
                    if mult_value < min_super_mult:
                        adjusted += 1
                        replacement = get_random_outcome(self.config.super_multiplier_weights)
                        symbol.assign_attribute({"multiplier": replacement})
        if adjusted > 0:
            print(
                f"[SuperMultSanitize] mode={self.betmode} adjusted {adjusted} multipliers below {min_super_mult}x."
            )

    def _enforce_scatter_per_reel_limit(self):
        """Ensure no reel ever shows more than one scatter-family symbol."""
        scatter_symbols = {"S", "BS"}
        replacements_made = False
        for reel_idx in range(self.config.num_reels):
            entries = [
                {"row": row_idx, "name": symbol.name}
                for row_idx, symbol in enumerate(self.board[reel_idx])
                if symbol.name in scatter_symbols
            ]
            if len(entries) <= 1:
                continue
            keep_entry = next((entry for entry in entries if entry["name"] == "BS"), None)
            if keep_entry is None:
                keep_entry = max(entries, key=lambda entry: entry["row"])
            for entry in entries:
                if entry is keep_entry:
                    continue
                replacement_name = self._get_scatter_blocker_symbol()
                self.board[reel_idx][entry["row"]] = self.create_symbol(replacement_name)
                replacements_made = True
        if replacements_made:
            self.get_special_symbols_on_board()

    def _get_scatter_blocker_symbol(self) -> str:
        """Return a filler symbol to replace illegal duplicate scatters."""
        return random.choice(self.SCATTER_BLOCKER_SYMBOLS)
