# Candy Carnage 1000 - Complete Backend Specification

This is the **definitive** specification for the backend. Follow this exactly.

---

## Table of Contents
1. [Game Overview](#game-overview)
2. [Symbol Definitions](#symbol-definitions)
3. [Paytable](#paytable)
4. [Board Structure](#board-structure)
5. [Position Structure (CRITICAL)](#position-structure-critical)
6. [Bet Modes](#bet-modes)
7. [All Event Types](#all-event-types)
8. [Event Sequences](#event-sequences)
9. [Win Levels](#win-levels)
10. [Scatter Payouts](#scatter-payouts)

---

## Game Overview

- **Grid**: 6 reels × 5 visible rows (30 total positions)
- **Scatter Pays (Anywhere Pays)**: 8+ of the same symbol ANYWHERE on the board wins
- **NO adjacency required** - symbols can be scattered anywhere, just need 8+ of same type
- **Tumble Mechanic**: Winning symbols explode, new symbols fall from above
- **Free Spins**: Triggered by 4+ scatter symbols (S or BS)
- **Multiplier Bombs**: Only appear during free spins
- **Max Win**: 25,000× bet
- **RTP**: 96.2%

**This is a "Scatter Pays" game like Sweet Bonanza - NOT a cluster game!**

---

## Symbol Definitions

### Regular Symbols
| Name | Type |
|------|------|
| `H1` | High pay 1 (highest) |
| `H2` | High pay 2 |
| `H3` | High pay 3 |
| `H4` | High pay 4 |
| `L1` | Low pay 1 |
| `L2` | Low pay 2 |
| `L3` | Low pay 3 |
| `L4` | Low pay 4 |
| `L5` | Low pay 5 (lowest) |

### Special Symbols
| Name | Type | Notes |
|------|------|-------|
| `S` | Scatter | Triggers free spins (4+) |
| `BS` | Super Scatter | Triggers SUPER free spins when combined with 3+ S |
| `M` | Multiplier Bomb | **Only in free spins**. MUST have `multiplier` field |

### Symbol Object Structure

```json
// Regular symbol
{ "name": "H1" }

// Scatter
{ "name": "S", "scatter": true }

// Super Scatter
{ "name": "BS", "scatter": true }

// Multiplier Bomb (ONLY IN FREE SPINS)
{ "name": "M", "bomb": true, "multiplier": 25 }
```

**CRITICAL**: Multiplier bombs (`M`) MUST always include:
- `"bomb": true`
- `"multiplier": <number>` (never 0, never omitted)

### Valid Multiplier Values

| Tier | Values | Visual |
|------|--------|--------|
| Low | 2, 3, 4, 5, 6, 8, 10 | Green bomb |
| Mid | 12, 15, 20, 25, 50 | Purple bomb |
| High | 100, 500, 1000 | Gold bomb |

**Regular Bonus**: Can use any multiplier value (2-1000)
**Super Bonus**: Minimum 20× (so: 20, 25, 50, 100, 500, 1000)

---

## Paytable

All values are multipliers of the base bet amount.

| Symbol | 8 symbols | 9 symbols | 10-11 symbols | 12+ symbols |
|--------|-----------|-----------|---------------|-------------|
| **H1** | 10× | 10× | 25× | 50× |
| **H2** | 2.5× | 2.5× | 10× | 25× |
| **H3** | 2× | 2× | 5× | 15× |
| **H4** | 1.5× | 1.5× | 2× | 12× |
| **L1** | 1× | 1× | 1.5× | 10× |
| **L2** | 0.8× | 0.8× | 1.2× | 8× |
| **L3** | 0.5× | 0.5× | 1× | 5× |
| **L4** | 0.4× | 0.4× | 0.9× | 4× |
| **L5** | 0.25× | 0.25× | 0.75× | 2× |

**Example**: 10× L3 symbols at 1.00 bet = 1.00 × 1.0 = 1.00 win

---

## Board Structure

The board has **7 rows per reel** (5 visible + 2 padding):

```
Index 0: Top padding (above visible area)
Index 1: Visible row 1 (top)
Index 2: Visible row 2
Index 3: Visible row 3
Index 4: Visible row 4
Index 5: Visible row 5 (bottom)
Index 6: Bottom padding (below visible area)
```

**In `reveal.board`**: Send all 7 symbols per reel (including padding).

- Each reel strip contains at most **one** scatter symbol (`S` or `BS`). A reel never hosts both, and no extra scatter can tumble into a reel that already shows one.
- Reel files are mode-specific:
  - `BASE.csv` → standard base spins (also shared by `bonus_hunt`).
  - `REG.csv` → regular free spins / `regular_buy` (contains multiplier bombs).
  - `SUPER.csv` → super free spins / `super_buy` (dedicated `BS` reel + denser multipliers).

---

## Position Structure (CRITICAL)

```json
{
  "reel": 0-5,    // 0 = leftmost reel, 5 = rightmost
  "row": 1-5     // 1 = top visible row, 5 = bottom visible row
}
```

### ⚠️ CRITICAL: Row Indexing

**Positions in events (`winInfo`, `tumbleBoard`, `freeSpinTrigger`, `boardMultiplierInfo`) use VISIBLE row indices 1-5, NOT array indices 0-6.**

| Row Description | Array Index in `board` | Position Value in Events |
|-----------------|------------------------|--------------------------|
| Top padding | 0 | N/A (never in positions) |
| Top visible | 1 | **1** |
| Second visible | 2 | **2** |
| Middle visible | 3 | **3** |
| Fourth visible | 4 | **4** |
| Bottom visible | 5 | **5** |
| Bottom padding | 6 | N/A (never in positions) |

**If you use 0-4 for visible rows, clusters will appear one row ABOVE where they should be!**

---

## Bet Modes

| Mode | Cost Multiplier | Description |
|------|-----------------|-------------|
| `base` | 1× | Normal gameplay |
| `bonus_hunt` | 3× | Bonus-hunt spins (uses `BASE` strips with higher scatter weighting) |
| `regular_buy` | 100× | Buy regular bonus (guaranteed 4+ scatters) |
| `super_buy` | 500× | Buy super bonus (guaranteed BS + 3S) |

Each bet mode is wired to the reel set listed in the Board Structure section (with `bonus_hunt` sharing the `BASE` strips), ensuring scatter limits and guarantees are enforced at the strip level.

---

### Buy Bonus

Same as free spin trigger, but initial `reveal` board has guaranteed scatters.

---

## Scatter Payouts

| Count | Payout |
|-------|--------|
| 4 | 0× (just triggers feature) |
| 5 | 5× |
| 6 | 100× |

`BS` symbols count as standard scatters for these payout thresholds.

---

## Critical Rules Summary

1. **Every spin ends with `finalWin`** - NO EXCEPTIONS
2. **Row indices in positions are 1-5** (visible rows), NOT 0-4
3. **`M` symbols MUST have `bomb: true` and `multiplier: <number>`**
4. **`updateTumbleWin.amount` is CUMULATIVE**, not incremental
5. **`boardMultiplierInfo` only fires once per spin**, on first tumble with bombs
6. **After every `tumbleBoard`**: check for more wins (8+ same symbol) → if none, send `setTotalWin` → `finalWin`
7. **Board in `reveal` has 7 symbols per reel** (including padding)
8. **All amounts are in integer cents** (e.g., $1.50 = 150)
9. **SCATTER PAYS**: 8+ of same symbol ANYWHERE wins - NO adjacency required!

---

## Quick Validation Checklist

Before sending events, verify:

- [ ] Every spin ends with `finalWin`
- [ ] Position rows are 1-5 (not 0-4)
- [ ] `reveal.board` has 6 reels × 7 symbols each
- [ ] `M` symbols have `bomb: true` and `multiplier` field
- [ ] `updateTumbleWin.amount` is cumulative
- [ ] Event indices are sequential starting from 0
- [ ] `gameType` is `"basegame"` or `"freegame"` (not "freeSpins")
- [ ] Win amounts are integers (cents, not dollars)
- [ ] Wins trigger when 8+ of same symbol appear ANYWHERE (scatter pays)

