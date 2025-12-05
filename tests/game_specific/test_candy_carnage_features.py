import math
import sys
from importlib import import_module
from pathlib import Path

import pytest

GAME_DIR = Path(__file__).resolve().parents[2] / "games" / "0_0_scatter"
if str(GAME_DIR) not in sys.path:
    sys.path.insert(0, str(GAME_DIR))

buy_templates = import_module("games.0_0_scatter.buy_templates")
REGULAR_BUY_REVEAL_TEMPLATES = buy_templates.REGULAR_BUY_REVEAL_TEMPLATES
SUPER_BUY_REVEAL_TEMPLATES = buy_templates.SUPER_BUY_REVEAL_TEMPLATES

game_config_module = import_module("games.0_0_scatter.game_config")
GameConfig = game_config_module.GameConfig

gamestate_module = import_module("games.0_0_scatter.gamestate")
GameState = gamestate_module.GameState

events_module = import_module("src.events.events")

from src.calculations.scatter import Scatter
from src.write_data.write_data import quantize_payout_cents


@pytest.fixture(scope="module")
def game_config():
    return GameConfig()


@pytest.fixture
def gamestate(game_config):
    return GameState(game_config)


def test_quantize_payout_cents_snaps_to_tenth():
    assert quantize_payout_cents(0.01) == 0
    assert quantize_payout_cents(0.04) == 0
    assert quantize_payout_cents(1.234) == 120
    assert quantize_payout_cents(25.05) == 2500
    assert quantize_payout_cents(99.99) == 10000


def test_multiplier_pool_separates_super(game_config):
    base_pool = game_config.get_multiplier_pool(game_config.basegame_type)
    regular_free_pool = game_config.get_multiplier_pool(game_config.freegame_type)
    super_pool = game_config.get_multiplier_pool(game_config.freegame_type, super_bonus_active=True)

    assert set(base_pool.keys()) == set(regular_free_pool.keys())
    assert set(super_pool.keys()) == {20, 25, 50, 100, 500, 1000}
    assert all(mult < 20 for mult in base_pool if mult < 20)
    assert all(mult >= 20 for mult in super_pool)


def test_super_bonus_board_sanitizer_removes_bs_and_low_bombs(gamestate):
    gamestate.gametype = gamestate.config.freegame_type
    gamestate.super_bonus_active = True
    gamestate.betmode = "super_buy"
    board = []
    for reel_idx in range(gamestate.config.num_reels):
        column = []
        for _ in range(gamestate.config.num_rows[reel_idx]):
            column.append(gamestate.create_symbol("L1"))
        board.append(column)

    # Inject a BS and a low-multiplier bomb.
    board[0][0] = gamestate.create_symbol("BS")
    bomb = gamestate.create_symbol("M")
    bomb.assign_attribute({"multiplier": 5})
    board[1][0] = bomb
    gamestate.board = board
    gamestate.get_special_symbols_on_board()

    gamestate._sanitize_bonus_board()

    scatter_positions = gamestate.special_syms_on_board.get("super_scatter", [])
    assert len(scatter_positions) == 0

    for reel in gamestate.board:
        for symbol in reel:
            if symbol.check_attribute("multiplier"):
                assert symbol.get_attribute("multiplier") >= 20


def test_retrigger_counts_regular_scatters_only(gamestate):
    gamestate.betmode = "super_buy"
    gamestate.gametype = gamestate.config.freegame_type
    gamestate.board = []
    for reel_idx in range(gamestate.config.num_reels):
        column = []
        for _ in range(gamestate.config.num_rows[reel_idx]):
            column.append(gamestate.create_symbol("L1"))
        gamestate.board.append(column)

    # Place S on three different reels.
    for reel_idx in range(3):
        gamestate.board[reel_idx][0] = gamestate.create_symbol("S")

    assert gamestate.grant_bonus_retrigger_if_needed() is True

    # Replace one S with BS, leaving only two S.
    gamestate.board[0][0] = gamestate.create_symbol("BS")
    assert gamestate.grant_bonus_retrigger_if_needed() is False


def _assert_template_properties(config, template, expected_scatter_count, expected_bs_count):
    gamestate = GameState(config)
    scatter_total = 0
    super_total = 0
    seen_symbols = set()

    for reel_idx, column in enumerate(template):
        assert len(column) == config.num_rows[reel_idx]
        scatter_on_reel = 0
        for symbol_name in column:
            seen_symbols.add(symbol_name)
            if symbol_name == "S":
                scatter_total += 1
                scatter_on_reel += 1
            elif symbol_name == "BS":
                super_total += 1
                scatter_on_reel += 1
        assert scatter_on_reel <= 1, "At most one scatter per reel in templates."

    assert scatter_total == expected_scatter_count
    assert super_total == expected_bs_count
    assert seen_symbols - {"S", "BS"} != set(), "Templates should include non-scatter symbols."

    # Evaluate scatter pay using live Scatter logic.
    board = []
    for reel_idx, column in enumerate(template):
        board.append([gamestate.create_symbol(symbol_name) for symbol_name in column])
    win_data = Scatter.get_scatterpay_wins(config, board)
    assert math.isclose(win_data["totalWin"], 0.0), "Buy templates must not award base wins."


def test_regular_buy_templates_are_safe(game_config):
    for template in REGULAR_BUY_REVEAL_TEMPLATES:
        _assert_template_properties(game_config, template, expected_scatter_count=4, expected_bs_count=0)


def test_super_buy_templates_are_safe(game_config):
    for template in SUPER_BUY_REVEAL_TEMPLATES:
        _assert_template_properties(game_config, template, expected_scatter_count=3, expected_bs_count=1)


def test_regular_buy_flow_uses_templates(monkeypatch, gamestate):
    triggered = {"regular": False}

    def fake_run_freespin(self):
        triggered["regular"] = True

    monkeypatch.setattr(GameState, "run_freespin_from_base", fake_run_freespin)
    monkeypatch.setattr(GameState, "draw_board", lambda self, *_, **__: None)
    monkeypatch.setattr(gamestate_module, "reveal_event", lambda *_: None)
    monkeypatch.setattr(
        GameState,
        "get_current_distribution_conditions",
        lambda self: {"force_freegame": False, "force_super_bonus": False},
    )
    gamestate.betmode = "regular_buy"
    gamestate.criteria = "freegame"
    gamestate._run_buy_entry_spin("regular_buy")
    assert triggered["regular"] is True


def test_super_buy_flow_uses_templates(monkeypatch, gamestate):
    triggered = {"super": False}

    def fake_run_super(self):
        triggered["super"] = True

    monkeypatch.setattr(GameState, "run_super_bonus_from_base", fake_run_super)
    monkeypatch.setattr(GameState, "draw_board", lambda self, *_, **__: None)
    monkeypatch.setattr(gamestate_module, "reveal_event", lambda *_: None)
    monkeypatch.setattr(
        GameState,
        "get_current_distribution_conditions",
        lambda self: {"force_freegame": False, "force_super_bonus": False},
    )
    gamestate.betmode = "super_buy"
    gamestate.criteria = "freegame"
    gamestate._run_buy_entry_spin("super_buy")
    assert triggered["super"] is True

