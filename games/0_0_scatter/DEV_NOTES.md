# Candy Carnage 1000 – Working Notes

Use this sheet to keep core constraints in one place while iterating.

## Global Targets
- **Base bet scaling**: Player selects stake (0.20, 0.40, 1.00…). All payouts, buy prices, and the 25 000× cap scale linearly.
- **Max win**: 25 000× base bet. Any payout above this is clamped, wincap event fires, feature ends.
- **Overall RTP**: 96.2 % (weighted sum of all modes).

### RTP Slice Intent (approx.)
| Mode | Rough Share |
|------|-------------|
| Base spins | ~60 % |
| Bonus Hunt | ~5–8 % |
| Regular free spins (natural + buys) | ~18–20 % |
| Super free spins (natural + buys) | ~8–10 % |
| Slack / rounding | ~0.2–1 % |

Expose these as config knobs but enforce the ~96.2 % total.

## Reel / Symbol Rules
- Dedicated reel files per mode:
  - `BASE.csv` → base spins (also used for `bonus_hunt`)
  - `REG.csv` → regular free spins / `regular_buy`
  - `SUPER.csv` → super free spins / `super_buy`
- **Scatter constraint**: each reel contains at most **one** scatter (`S`) or super scatter (`BS`). A reel never has both, and no second scatter can tumble into a reel that already shows one.
- `BS` counts as a scatter for payouts and requires `S`+`BS` to trigger the super bonus but **never** appears once a bonus starts (free-spin reels only contain `S`).

## Scatter Payouts / Triggers
- 4 scatters → 0 × (feature entry only)
- 5 scatters → 5 ×
- 6+ scatters → 100 ×
- `BS` substitutes for `S` when counting these payouts.
- Free spins always award 10 spins upfront; landing **3+** scatters during a bonus spin awards **+5** extra spins.

## Buy Modes
- `bonus_hunt`: 3× cost, reuses `BASE` reels but with higher scatter weighting in distributions.
- `regular_buy`: 100× cost, guarantees ≥4 scatters via `REG` reels.
- `super_buy`: 500× cost, guarantees BS + 3×S via `SUPER` reels.

## Misc Reminders
- Multiplier bombs (`M`) only appear during free spins, include `bomb: true` and `multiplier`.
- Progress logging added in `state.py` prints `[mode] thread X progress: Y/Z` every ~20 % of each worker’s load—useful for long runs.
- Keep an eye on distribution settings (`force_freegame`, `force_super_bonus`) so they remain attainable with the current reel layouts.

