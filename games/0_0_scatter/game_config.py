import os
from src.config.config import Config
from src.config.distributions import Distribution
from src.config.betmode import BetMode


class GameConfig(Config):
    """Load all game specific parameters and elements"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        super().__init__()
        self.game_id = "0_0_scatter"
        self.game_name = "sample_scatter"
        self.provider_numer = 0
        self.working_name = "Sample scatter pay (pay anywhere)"
        self.wincap = 25000.0
        self.win_type = "scatter"
        self.rtp = 0.9620
        self.construct_paths()
        self.max_free_spins_per_round = 20
        self.max_freegame_retriggers = 2

        # Game Dimensions
        self.num_reels = 6
        # Optionally include variable number of rows per reel
        self.num_rows = [5] * self.num_reels
        # Board and Symbol Properties
        low_range = (8, 9)
        mid_range = (10, 11)
        high_range = (12, 36)
        pay_group = {
            (low_range, "H1"): 10.0,
            (mid_range, "H1"): 25.0,
            (high_range, "H1"): 50.0,
            (low_range, "H2"): 2.5,
            (mid_range, "H2"): 10.0,
            (high_range, "H2"): 25.0,
            (low_range, "H3"): 2.0,
            (mid_range, "H3"): 5.0,
            (high_range, "H3"): 15.0,
            (low_range, "H4"): 1.5,
            (mid_range, "H4"): 2.0,
            (high_range, "H4"): 12.0,
            (low_range, "L1"): 1.0,
            (mid_range, "L1"): 1.5,
            (high_range, "L1"): 10.0,
            (low_range, "L2"): 0.8,
            (mid_range, "L2"): 1.2,
            (high_range, "L2"): 8.0,
            (low_range, "L3"): 0.5,
            (mid_range, "L3"): 1.0,
            (high_range, "L3"): 5.0,
            (low_range, "L4"): 0.4,
            (mid_range, "L4"): 0.9,
            (high_range, "L4"): 4.0,
            (low_range, "L5"): 0.25,
            (mid_range, "L5"): 0.75,
            (high_range, "L5"): 2.0,
            ((4, 4), "S"): 0.0,
            ((5, 5), "S"): 5.0,
            ((6, 36), "S"): 100.0,
        }
        self.paytable = self.convert_range_table(pay_group)

        base_multiplier_weights = {
            2:   900,
            3:   700,
            4:   550,
            5:   350,
            6:   250,
            8:   100,
            10:   60,
            12:   45,
            15:   40,
            20:   30,
            25:   27,
            50:    15,
            100:   7,
            500:   2,
            1000:  1,
        }
        self.multiplier_weights = {
            self.basegame_type: base_multiplier_weights,
            self.freegame_type: dict(base_multiplier_weights),
        }
        self.super_multiplier_weights = {
            20: 150,
            25: 65,
            50: 11,
            100: 3,
            500: 2,
            1000: 1,
        }

        self.include_padding = True
        self.special_symbols = {
            "scatter": ["S"],
            "super_scatter": ["BS"],
            "multiplier": ["M"],
            "wild": [],
        }

        self.freespin_triggers = {
            self.basegame_type: {
                4: 10,
                5: 10,
                6: 10,
                7: 10,
                8: 10,
                9: 10,
                10: 10,
            },
            self.freegame_type: {
                2: 10,
                3: 10,
                4: 10,
                5: 10,
                6: 10,
                7: 10,
                8: 10,
                9: 10,
                10: 10,
            },
        }
        self.anticipation_triggers = {
            self.basegame_type: min(self.freespin_triggers[self.basegame_type].keys()) - 1,
            self.freegame_type: min(self.freespin_triggers[self.freegame_type].keys()) - 1,
        }
        # Reels
        reels = {
            "BASE": "BASE.csv",
            "REG": "REG.csv",
            "SUPER": "SUPER.csv",
        }
        self.reels = {}
        for r, f in reels.items():
            self.reels[r] = self.read_reels_csv(os.path.join(self.reels_path, f))

        self.padding_reels[self.basegame_type] = self.reels["BASE"]
        self.padding_reels[self.freegame_type] = self.reels["REG"]
        self.bet_modes = [
            BetMode(
                name="base",
                cost=1.0,
                rtp=self.rtp,
                max_win=self.wincap,
                auto_close_disabled=False,
                is_feature=True,
                is_buybonus=False,
                distributions=[
                    Distribution(
                        criteria="freegame",
                        quota=0.1,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BASE": 1},
                                self.freegame_type: {"REG": 1},
                            },
                            "scatter_triggers": {4: 5, 5: 1},
                            "mult_values": self.multiplier_weights,
                            "force_wincap": False,
                            "force_freegame": False,
                            "force_super_bonus": False,
                        },
                    ),
                    Distribution(
                        criteria="0",
                        quota=0.4,
                        win_criteria=0.0,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BASE": 1},
                                self.freegame_type: {"REG": 1},
                            },
                            "mult_values": self.multiplier_weights,
                            "force_wincap": False,
                            "force_freegame": False,
                        },
                    ),
                    Distribution(
                        criteria="basegame",
                        quota=0.5,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BASE": 1},
                                self.freegame_type: {"REG": 1},
                            },
                            "mult_values": self.multiplier_weights,
                            "force_wincap": False,
                            "force_freegame": False,
                        },
                    ),
                ],
            ),
            BetMode(
                name="bonus_hunt",
                cost=3.0,
                rtp=self.rtp,
                max_win=self.wincap,
                auto_close_disabled=False,
                is_feature=True,
                is_buybonus=False,
                distributions=[
                    Distribution(
                        criteria="freegame",
                        quota=0.2,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BASE": 1},
                                self.freegame_type: {"REG": 1},
                            },
                            "scatter_triggers": {4: 5, 5: 1},
                            "mult_values": self.multiplier_weights,
                            "force_wincap": False,
                            "force_freegame": False,
                        },
                    ),
                    Distribution(
                        criteria="0",
                        quota=0.4,
                        win_criteria=0.0,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BASE": 1},
                                self.freegame_type: {"REG": 1},
                            },
                            "mult_values": self.multiplier_weights,
                            "force_wincap": False,
                            "force_freegame": False,
                        },
                    ),
                    Distribution(
                        criteria="basegame",
                        quota=0.4,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BASE": 1},
                                self.freegame_type: {"REG": 1},
                            },
                            "mult_values": self.multiplier_weights,
                            "force_wincap": False,
                            "force_freegame": False,
                        },
                    ),
                ],
            ),
            BetMode(
                name="regular_buy",
                cost=100,
                rtp=self.rtp,
                max_win=self.wincap,
                auto_close_disabled=False,
                is_feature=False,
                is_buybonus=True,
                distributions=[
                    Distribution(
                        criteria="freegame",
                        quota=0.999,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BASE": 1},
                                self.freegame_type: {"REG": 1},
                            },
                            "scatter_triggers": {4: 10, 5: 5, 6: 1},
                            "mult_values": self.multiplier_weights,
                            "force_wincap": False,
                            "force_freegame": True,
                            "force_super_bonus": False,
                        },
                    ),
                ],
            ),
            BetMode(
                name="super_buy",
                cost=500,
                rtp=self.rtp,
                max_win=self.wincap,
                auto_close_disabled=False,
                is_feature=False,
                is_buybonus=True,
                distributions=[
                    Distribution(
                        criteria="freegame",
                        quota=0.999,
                        conditions={
                            "reel_weights": {
                                self.basegame_type: {"BASE": 1},
                                self.freegame_type: {"SUPER": 1},
                            },
                            "scatter_triggers": {4: 10, 5: 5, 6: 1},
                            "mult_values": self.multiplier_weights,
                            "force_wincap": False,
                            "force_freegame": True,
                            "force_super_bonus": True,
                        },
                    ),
                ],
            ),
        ]

    def get_multiplier_pool(self, gametype: str, super_bonus_active: bool = False) -> dict[int, int]:
        """Return the appropriate multiplier weights for current context."""
        if super_bonus_active and gametype == self.freegame_type:
            return self.super_multiplier_weights
        return self.multiplier_weights[gametype]
