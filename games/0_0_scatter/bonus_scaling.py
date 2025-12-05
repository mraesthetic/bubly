"""Centralized bonus payout scaling logic."""

BONUS_PAYOUT_SCALER = {
    "default": {
        "regular": 0.023769511972257826,
        "super": 0.07667584507179943,
    },
    "bonus_hunt": {
        "regular": 0.05764881982447366,
        "super": 0.18596393491765695,
    },
    "regular_buy": {
        "regular": 0.05891462798471398,
    },
    "super_buy": {
        "super": 0.3228842209264001,
    },
}


def get_bonus_scaler(mode: str, bonus_type: str) -> float:
    """Fetch the scaler for a mode/bonus combination."""
    mode_cfg = BONUS_PAYOUT_SCALER.get(mode)
    if isinstance(mode_cfg, dict) and bonus_type in mode_cfg:
        return mode_cfg[bonus_type]
    return BONUS_PAYOUT_SCALER["default"][bonus_type]


def apply_bonus_scaler(mode: str, bonus_type: str, amount: float) -> float:
    """Return the scaled bonus win amount."""
    scale = get_bonus_scaler(mode, bonus_type)
    if scale == 1.0:
        return round(amount, 2)
    return round(amount * scale, 2)

