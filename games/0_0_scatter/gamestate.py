from typing import Dict, List, Optional, Tuple

from game_override import GameStateOverride
from src.events.events import reveal_event


class GameState(GameStateOverride):
    """Gamestate for a single spin"""

    BUY_MODES = {"regular_buy", "super_buy"}

    def run_spin(self, sim: int, simulation_seed=None):
        self.reset_seed(sim)
        if self.betmode in self.BUY_MODES:
            self._run_buy_entry_spin(self.betmode)
            return

        self.repeat = True
        while self.repeat:
            self.reset_book()
            self.draw_board()

            self.get_scatterpays_update_wins()
            self.emit_tumble_win_events()  # Transmit win information

            pending_bonus_type = self._determine_pending_bonus_type()

            if pending_bonus_type is None:
                while self.win_data["totalWin"] > 0 and not (self.wincap_triggered):
                    self.tumble_game_board()
                    self.get_scatterpays_update_wins()
                    self.emit_tumble_win_events()  # Transmit win information
            else:
                self._log_scatter_bonus_debug(pending_bonus_type)

            self.set_end_tumble_event()
            self.win_manager.update_gametype_wins(self.gametype)

            if pending_bonus_type == "super":
                if self.check_super_bonus_entry():
                    self.run_super_bonus_from_base()
            elif pending_bonus_type == "regular":
                if self.check_freespin_entry():
                    self.run_freespin_from_base()
            else:
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

    def _determine_pending_bonus_type(self) -> Optional[str]:
        if self.should_trigger_super_bonus():
            return "super"
        if self.check_fs_condition():
            return "regular"
        return None

    def _log_scatter_bonus_debug(self, pending_bonus_type: str) -> None:
        scatter_count, super_count = self._get_scatter_counts()
        total_scatter = scatter_count + super_count
        scatter_symbol_names = set(self.config.special_symbols.get("scatter", []))
        scatter_symbol_names.update(self.config.special_symbols.get("super_scatter", []))
        scatter_win = sum(
            win["win"] for win in self.win_data["wins"] if win["symbol"] in scatter_symbol_names
        )
        scatter_positions = list(self.special_syms_on_board.get("scatter", [])) + list(
            self.special_syms_on_board.get("super_scatter", [])
        )
        assert not any(
            self.board[pos["reel"]][pos["row"]].check_attribute("explode") for pos in scatter_positions
        ), "Scatter symbols must remain on board during a bonus trigger spin."

        if total_scatter >= 4 or getattr(self, "scatter_debug_logging", False):
            print(
                "[ScatterDebug] mode={mode} bonus={bonus} scatters={count} scatter_win={scatter_win:.2f} "
                "spin_total={spin_total:.2f}".format(
                    mode=self.betmode,
                    bonus=pending_bonus_type,
                    count=total_scatter,
                    scatter_win=scatter_win,
                    spin_total=self.win_data["totalWin"],
                )
            )

    def _run_buy_entry_spin(self, betmode: str) -> None:
        self.reset_book()
        self.draw_board(emit_event=False)
        layout = (
            [
                {"reel": 0, "row": 0, "symbol": "S"},
                {"reel": 1, "row": 0, "symbol": "S"},
                {"reel": 2, "row": 0, "symbol": "S"},
                {"reel": 3, "row": 0, "symbol": "S"},
            ]
            if betmode == "regular_buy"
            else [
                {"reel": 0, "row": 0, "symbol": "S"},
                {"reel": 1, "row": 0, "symbol": "S"},
                {"reel": 2, "row": 0, "symbol": "S"},
                {"reel": 3, "row": 0, "symbol": "BS"},
            ]
        )
        self._build_buy_entry_board(layout)
        self.get_special_symbols_on_board()
        reveal_event(self)
        scatter_count, super_count = self._get_scatter_counts()

        if betmode == "regular_buy":
            assert scatter_count == 4 and super_count == 0, "regular_buy requires exactly 4 scatters."
            print(f"[BuyEntry] regular_buy scatters={scatter_count} super_scatters={super_count}")
            if self.check_freespin_entry():
                self.run_freespin_from_base()
        else:
            assert (
                scatter_count == 3 and super_count == 1
            ), "super_buy requires 3 scatters plus exactly 1 BS."
            print(f"[BuyEntry] super_buy scatters={scatter_count} super_scatters={super_count}")
            if self.check_super_bonus_entry():
                self.run_super_bonus_from_base()

        self.evaluate_finalwin()
        self.check_repeat()
        self.imprint_wins()

    def _build_buy_entry_board(self, layout: List[Dict[str, object]]) -> None:
        filler_symbol = getattr(self, "buy_entry_filler_symbol", "L1")
        self.board = [
            [self.create_symbol(filler_symbol) for _ in range(self.config.num_rows[reel_idx])]
            for reel_idx in range(self.config.num_reels)
        ]
        for placement in layout:
            reel = placement["reel"]
            row = placement["row"]
            symbol_name = placement["symbol"]
            self.board[reel][row] = self.create_symbol(symbol_name)

    def _get_scatter_counts(self) -> Tuple[int, int]:
        regular = len(self.special_syms_on_board.get("scatter", []))
        super_scatter = len(self.special_syms_on_board.get("super_scatter", []))
        return regular, super_scatter
