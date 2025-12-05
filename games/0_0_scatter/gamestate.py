from game_override import GameStateOverride
from src.calculations.scatter import Scatter


class GameState(GameStateOverride):
    """Gamestate for a single spin"""

    def run_spin(self, sim: int, simulation_seed=None):
        self.reset_seed(sim)
        self.repeat = True
        while self.repeat:
            self.reset_book()
            self.draw_board()

            self.get_scatterpays_update_wins()
            self.emit_tumble_win_events()  # Transmit win information

            while self.win_data["totalWin"] > 0 and not (self.wincap_triggered):
                self.tumble_game_board()
                self.get_scatterpays_update_wins()
                self.emit_tumble_win_events()  # Transmit win information

            self.set_end_tumble_event()
            self.win_manager.update_gametype_wins(self.gametype)

            if self.should_trigger_super_bonus() and self.check_super_bonus_entry():
                self.run_super_bonus_from_base()
            elif self.check_fs_condition() and self.check_freespin_entry():
                self.run_freespin_from_base()

            self.evaluate_finalwin()
            self.check_repeat()

        self.imprint_wins()

    def run_freespin(self):
        self.reset_fs_spin()
        while (
            self.fs < self.tot_fs
            and self.fs < self.config.max_free_spins_per_round
        ):
            self.update_freespin()
            self.draw_board()

            self.get_scatterpays_update_wins()
            self.emit_tumble_win_events()  # Transmit win information

            while self.win_data["totalWin"] > 0 and not (self.wincap_triggered):
                self.tumble_game_board()

                self.get_scatterpays_update_wins()
                self.emit_tumble_win_events()  # Transmit win information

            self.set_end_tumble_event()
            retrigger_ready = self.grant_bonus_retrigger_if_needed()
            self.win_manager.update_gametype_wins(self.gametype)

            if retrigger_ready:
                self.update_fs_retrigger_amt()

        self.end_freespin()

    def should_trigger_super_bonus(self) -> bool:
        """Check if the board qualifies for a super bonus trigger."""
        if self.repeat:
            return False
        if self.get_current_distribution_conditions().get("force_super_bonus"):
            return True
        return self.get_natural_bonus_type() == "super"

    def check_super_bonus_entry(self) -> bool:
        """Validate that criteria allows a super bonus trigger."""
        if self.get_current_distribution_conditions().get("force_super_bonus"):
            return True
        return self.get_natural_bonus_type() == "super"
