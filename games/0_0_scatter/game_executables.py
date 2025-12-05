"""

"""

from copy import copy

from game_calculations import GameCalculations
from src.calculations.scatter import Scatter
from game_events import send_mult_info_event
from src.events.events import (
    set_win_event,
    set_total_event,
    fs_trigger_event,
    update_tumble_win_event,
    update_freespin_event,
)
from bonus_scaling import apply_bonus_scaler

MODE_BASE_PAYOUT_SCALER = {
    "base": 0.770088280684791,
    "bonus_hunt": 1.3006760418570473,
    "default": 1.0,
}


class GameExecutables(GameCalculations):
    """Game specific executable functions. Used for grouping commonly used/repeated applications."""

    def scale_bonus_wins(self, bonus_type: str, mode: str | None = None) -> None:
        """Scale total freegame win using centralized bonus scaler."""
        raw_total = getattr(self.win_manager, "freegame_wins", 0.0)
        mode_name = mode or getattr(self, "betmode", "base")
        scaled_total = apply_bonus_scaler(mode_name, bonus_type, raw_total)
        delta = scaled_total - raw_total
        if delta == 0:
            return
        self.win_manager.freegame_wins = scaled_total
        self.win_manager.running_bet_win += delta

    def apply_basegame_scaler(self) -> None:
        """Scale the current base-game spin win based on bet mode."""
        if self.gametype != self.config.basegame_type:
            return
        mode_name = getattr(self, "betmode", None)
        scale = MODE_BASE_PAYOUT_SCALER.get(mode_name, 1.0)
        if scale == 1.0:
            return
        scaled = round(self.win_manager.spin_win * scale, 2)
        self.win_manager.set_spin_win(scaled)

    def set_end_tumble_event(self):
        """After all tumbling events have finished, multiply tumble-win by sum of mult symbols."""
        if self.gametype == self.config.freegame_type:  # Only multipliers in freegame
            board_mult, mult_info = self.get_board_multipliers()
            base_tumble_win = copy(self.win_manager.spin_win)
            self.win_manager.set_spin_win(base_tumble_win * board_mult)
            if self.win_manager.spin_win > 0 and len(mult_info) > 0:
                send_mult_info_event(
                    self,
                    board_mult,
                    mult_info,
                    base_tumble_win,
                    self.win_manager.spin_win,
                )
                update_tumble_win_event(self)

        if self.win_manager.spin_win > 0:
            if self.gametype == self.config.basegame_type:
                self.apply_basegame_scaler()
            set_win_event(self)
        set_total_event(self)

    def update_freespin_amount(self, scatter_key: str = "scatter"):
        """Update current and total freespin number and emit event."""
        # Always grant a fixed number of bonus spins regardless of scatter count.
        initial_spins = 10
        self.fs_retrigger_count = 0
        self.tot_fs = min(initial_spins, self.config.max_free_spins_per_round)
        if self.gametype == self.config.basegame_type:
            basegame_trigger, freegame_trigger = True, False
        else:
            basegame_trigger, freegame_trigger = False, True
        fs_trigger_event(self, basegame_trigger=basegame_trigger, freegame_trigger=freegame_trigger)

    def update_super_bonus_amount(self, scatter_key: str = "scatter", super_scatter_key: str = "super_scatter"):
        """Update freespin counts for super bonus triggers."""
        total_bonus_symbols = self.count_special_symbols(scatter_key) + self.count_special_symbols(super_scatter_key)
        initial_spins = 10
        self.fs_retrigger_count = 0
        self.tot_fs = min(initial_spins, self.config.max_free_spins_per_round)
        if self.gametype == self.config.basegame_type:
            basegame_trigger, freegame_trigger = True, False
        else:
            basegame_trigger, freegame_trigger = False, True
        fs_trigger_event(self, basegame_trigger=basegame_trigger, freegame_trigger=freegame_trigger)

    def get_scatterpays_update_wins(self):
        """Return the board since we are assigning the 'explode' attribute."""
        aliased_syms = self._alias_super_scatter_symbols()
        try:
            self.win_data = Scatter.get_scatterpay_wins(
                self.config, self.board
            )  # Evaluate wins, self.board is modified in-place
            Scatter.record_scatter_wins(self)
            self.win_manager.tumble_win = self.win_data["totalWin"]
            self.win_manager.update_spinwin(self.win_data["totalWin"])  # Update wallet
        finally:
            self._revert_super_scatter_symbols(aliased_syms)

    def update_freespin(self) -> None:
        """Called before a new reveal during freegame."""
        self.fs += 1
        update_freespin_event(self)
        self.win_manager.reset_spin_win()
        self.tumblewin_mult = 0
        self.win_data = {}

    def run_freespin_from_base(self, scatter_key: str = "scatter") -> None:
        """Trigger the freespin function, then scale payouts."""
        super().run_freespin_from_base(scatter_key=scatter_key)
        self.scale_bonus_wins("regular", mode=getattr(self, "betmode", "base"))

    def run_super_bonus_from_base(self, scatter_key: str = "scatter", super_scatter_key: str = "super_scatter") -> None:
        """Trigger super bonus spins, currently mirroring the standard bonus flow."""
        self.super_bonus_active = True
        total_bonus_symbols = self.count_special_symbols(scatter_key) + self.count_special_symbols(super_scatter_key)
        self.record(
            {
                "kind": total_bonus_symbols,
                "symbol": super_scatter_key,
                "gametype": self.gametype,
            }
        )
        self.update_super_bonus_amount(scatter_key=scatter_key, super_scatter_key=super_scatter_key)
        self.run_freespin()
        self.scale_bonus_wins("super", mode=getattr(self, "betmode", "base"))
        self.super_bonus_active = False

    def evaluate_finalwin(self) -> None:
        """Ensure running bet win matches scaled base+free sums before final evaluation."""
        total = round(self.win_manager.basegame_wins + self.win_manager.freegame_wins, 2)
        total = min(total, self.config.wincap)
        self.win_manager.running_bet_win = total
        try:
            super().evaluate_finalwin()
        except AssertionError as exc:
            print(
                "[DEBUG FINALWIN] runningBet=",
                self.win_manager.running_bet_win,
                "base=",
                self.win_manager.basegame_wins,
                "free=",
                self.win_manager.freegame_wins,
                "wincap=",
                self.config.wincap,
            )
            raise exc

    def get_visible_scatter_count(self, scatter_name: str = "S") -> int:
        """Count scatter symbols currently visible on the board."""
        scatter_set = {scatter_name}
        scatter_set.update(self.config.special_symbols.get("scatter", []))
        return sum(
            1 for reel in self.board for symbol in reel if getattr(symbol, "name", "") in scatter_set
        )

    def get_scatter_totals(self) -> tuple[int, int]:
        """Return counts of regular and super scatters on the current board."""
        total_s = len(self.special_syms_on_board.get("scatter", []))
        total_bs = len(self.special_syms_on_board.get("super_scatter", []))
        return total_s, total_bs

    def get_natural_bonus_type(self) -> str | None:
        """Return 'super', 'regular', or None based on current scatter mix."""
        total_s, total_bs = self.get_scatter_totals()
        if total_bs == 1 and total_s >= 3:
            return "super"
        if total_bs == 0 and total_s >= 4:
            return "regular"
        return None

    def grant_bonus_retrigger_if_needed(self, scatter_name: str = "S", spins_awarded: int = 5) -> bool:
        """Check whether retrigger criteria is satisfied."""
        scatter_count = self._count_regular_bonus_scatters()
        if scatter_count >= 3:
            print(
                f"[RetriggerCheck] mode={self.betmode} gametype={self.gametype} scatters={scatter_count}"
            )
            return True
        return False

    def _count_regular_bonus_scatters(self) -> int:
        """Count regular scatter symbols currently visible on the board."""
        scatter_names = set(self.config.special_symbols.get("scatter", []))
        if not scatter_names:
            scatter_names = {"S"}
        return sum(
            1 for reel in self.board for symbol in reel if getattr(symbol, "name", "") in scatter_names
        )

    def _alias_super_scatter_symbols(self):
        aliased_symbols = []
        for reel in range(len(self.board)):
            for row in range(len(self.board[reel])):
                symbol = self.board[reel][row]
                if getattr(symbol, "name", None) == "BS":
                    aliased_symbols.append(symbol)
                    setattr(symbol, "_original_name", symbol.name)
                    symbol.name = "S"
        return aliased_symbols

    def _revert_super_scatter_symbols(self, aliased_symbols):
        for symbol in aliased_symbols:
            symbol.name = getattr(symbol, "_original_name", "BS")
            if hasattr(symbol, "_original_name"):
                delattr(symbol, "_original_name")
