You are now in Base-Only Tuning Mode for my 6×5 cluster/tumble slot.
The bonus engine is capped and working, but for this phase we want to tune only the base game RTP (no free-spin EV included).

Ground truth / invariants

We have a 6×5 grid with reels sourced from BASE.csv.

Each reel has 258 stops.

Allowed symbols on reels: H1,H2,H3,H4,L1,L2,L3,L4,L5,S,BS.

Paytable, tumble logic, and bonus logic are correct and must not be changed in this mode.

We can run run_monte_carlo(num_spins, mode="base") which now returns:

rtp_base_no_bonus

rtp_regular_bonus

rtp_super_bonus

rtp_total

hit-rate, zero-win, bucket frequencies, scatter histogram, bonus trigger rates.

There is also a simulate_freegame_only helper, but for this phase we are ignoring free-game EV.

Target for this phase

We want to tune the base-only RTP to roughly:

rtp_base_no_bonus ≈ 0.40 (40% of bet per spin),
with a base feel similar to Sweet Bonanza 1000:

Hit-rate around 50–65% (including dust).

Zero-win (true dead spins) around 35–50%.

Win buckets, as % of spins, roughly:

0: 35–50%

(0,0.5]: 15–25%

(0.5,1]: 10–20%

(1,5]: 8–15%

(5,20]: 1–4%

(20, ∞): 0.01–0.2%

We are not tuning bonus EV yet. For this phase, regular/super trigger rates are informative but not optimization targets.

STEP 1 – Confirm baseline (base-only)

Add, if not already present, an include_bonuses: bool = True flag to run_monte_carlo.

When include_bonuses=False:

Still draw natural scatters, and detect regular/super triggers.

Do not enter the free-spin loop; treat regular_bonus_win and super_bonus_win as 0.

rtp_base_no_bonus must always be computed as:

rtp_base_no_bonus = sum_base_win_no_bonus / num_spins


independent of include_bonuses.

Run:

results = run_monte_carlo(50_000, mode="base", include_bonuses=False)


Print a concise summary:

rtp_base_no_bonus

hit-rate, zero-win rate

bucket distribution

global scatter histogram (0/1/2/3/4+ scatters), even though bonuses are disabled.

Do not change any reels yet. This step is pure measurement.

After printing the summary, analyze it in text:

Compare current rtp_base_no_bonus and bucket frequencies to the targets above.

Identify exactly how we’re off (e.g. “too many mid/big hits, too few dust/small”).

STEP 2 – Global symbol density analysis

Next, analyze the global symbol distribution of BASE.csv:

For each reel (1–6), compute counts of:

H1,H2,H3,H4 (premiums)

L1,L2,L3,L4,L5 (lows)

S,BS (scatters)

Summarize:

per-reel highs/lows/scatter counts and percentages

global highs/lows/scatters across all 6×258 = 1548 stops.

Compare global densities to a target density range for base:

Lows: 65–70% of stops

Highs: 25–30% of stops

Scatters: 2–3% of stops (we’ll refine later for triggers)

Do not edit reels yet. Just output a short analysis explaining:

How far highs are above the 25–30% band.

How far lows are below the 65–70% band.

Whether S/BS density looks roughly sane or obviously too low/high for ~1-in-170 / ~1-in-1600.

STEP 3 – Propose first-pass nerf (counts only)

Now propose a first-pass global nerf to push base-only RTP down, by rebalancing high vs low symbols.
Rules for this first pass:

We are editing counts only, not order yet.

Total stops per reel must remain 258.

For this pass, keep S and BS counts per reel unchanged.

We are allowed to change each non-scatter symbol’s count on a reel by up to ±30 copies (this is a large, blunt pass).

Objective:

Push global highs (sum of H1–H4) into the 25–30% range.

Push global lows into 65–70%.

Prefer shifting H→L2/L3/L5 (to create more dust/small clusters and more dead space).

Do not worry about perfect RTP yet; just bring us out of the “3.26× base RTP” insanity and into a plausible density band.

Output:

A table of old vs proposed new counts per reel:

Reel k: H1/H2/H3/H4, L1–L5, S, BS (old → new)

Global highs/lows/scatter totals & percentages before vs after.

A brief explanation of your design choices (e.g. “Reels 1–3 more low-heavy, reels 4–6 still hold more premiums but less than before”).

Do not rebuild the ordered strips yet. Wait for approval of these counts.

STEP 4 – Rebuild BASE.csv with new counts (after approval)

After I approve the new per-reel counts, rebuild the ordered strips:

For each reel separately:

Construct a 258-stop ordered list using the approved counts.

Keep S and BS positions the same as in the original BASE.csv (same row indices), and only adjust non-scatter symbols around them.

Avoid more than 3 identical symbols in a row, unless preserving a special row like all L5.

Maintain some “texture”: don’t fully randomize; keep bands of lows and highs similar to the original look but much more low-heavy.

After all 6 reels are rebuilt, output the new BASE.csv.

Also output a short checklist:

Reel count = 6

Stops per reel = 258

Symbol set ⊆ {H1,H2,H3,H4,L1,L2,L3,L4,L5,S,BS}

Per-reel counts match the approved new counts

S/BS positions preserved.

STEP 5 – Re-test with new BASE strips (base-only)

With the new BASE.csv in place:

Run:

results = run_monte_carlo(100_000, mode="base", include_bonuses=False)


Print:

rtp_base_no_bonus

hit-rate, zero-win rate

full bucket distribution

scatter histogram.

Compare to the target ranges at the top of this prompt and tell me:

Which metrics moved in the right direction.

Which metrics are still far off.

Whether we need another global nerf (more highs→lows), or if we can move to finer per-reel ±10 adjustments.

Stop after printing this analysis. Do not auto-apply further changes until asked.