# Scatter-Pays Game

#### Summary:

* A 6-reel, 5-row pay-anywhere tumbling (cascading) game.
* 9 paying total (4 high, 5 low)
* 3 special symbols (regular scatter `S`, super scatter `BS`, multiplier `M`)

Symbols pay across three bucketed cluster sizes: 8-9, 10-11, and 12+.

| Symbol | 8-9 | 10-11 | 12+ |
| --- | --- | --- | --- |
| H1 | 10x | 25x | 50x |
| H2 | 2.5x | 10x | 25x |
| H3 | 2x | 5x | 15x |
| H4 | 1.5x | 2x | 12x |
| L1 | 1x | 1.5x | 10x |
| L2 | 0.8x | 1.2x | 8x |
| L3 | 0.5x | 1x | 5x |
| L4 | 0.4x | 0.9x | 4x |
| L5 | 0.25x | 0.75x | 2x |

#### Basegame: 

A minimum of 4 regular Scatter symbols (`S`) is required to trigger a regular bonus.
Regular bonuses always award 10 free spins once triggered; retriggers add 10 more spins.
A super bonus can also be triggered during the basegame by landing at least 3 regular Scatters and 1 `BS` symbol at the same time.
`BS` symbols substitute for regular scatters when counting scatter payouts (4→0x, 5→5x, 6+→100x).
During any bonus (regular or super), only `S` symbols can appear; `BS` is filtered out once the feature starts. Landing **3 or more** scatters in a bonus spin awards **+5** additional spins.


#### Freegame rules
Tumbles continue while wins remain on the board.
Once tumbling ends, multiplier symbols that remain on the board are summed and applied to the cumulative tumble win.
Board multipliers only apply once per spin and do not persist across spins.
Super bonuses currently share the same tumble and payout behavior as regular bonuses.

#### Super bonus
* Triggered by landing ≥3 Scatters (`S`) plus at least one `BS` symbol in a single reveal.
* Always grants 10 free spins when triggered, regardless of scatter count (retriggers still add 10 spins).
* Gameplay presently mirrors the regular bonus, but is separated so bespoke behavior can be added later.
* The `regular_buy` bet mode (100×) forces the standard bonus, while the `super_buy` bet mode (500×) guarantees a BS + 3S super entry and currently shares the same math profile.


#### Notes
Due to the potential for symbols to tumble into the active board area, there is no upper limit on the number of freegame that can be awarded.
Bonuses (regular or super) always award 10 spins up-front, and retriggers add a flat +10. The usual 'updateTotalFreeSpinAmount' function is overridden 
in the game_executables.py file to enforce this rule.
`bonus_hunt` mode (3×) plays like the base game but with increased scatter frequency to chase features.

#### Event descriptions
"winInfo" Summarises winning combinations. Includes multipliers, symbol positions, payInfo [passed for every tumble event]
"tumbleBanner" includes values from the cumulative tumble after applying board multipliers
"setWin" this the result for the entire spin (from on Reveal to the next). Applied after board has stopped tumbling
"seTotalWin" the cumulative win for a round. In the base-game this will be equal to the setWin, but in the bonus it will incrementally increase 

