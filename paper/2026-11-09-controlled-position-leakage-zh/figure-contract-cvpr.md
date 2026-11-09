# CVPR figure contract

Target: CVPR (two-column, letter, 0.75 in margins, 3.25 in column width).
Every figure is built by `make_figures_cvpr.py --lang en|zh` from frozen JSON; no
inference, no score tuning, no hand-typed numbers that a JSON already holds.

## Argument the figure set has to carry

Knowing the floor outline, the start point and the inventory (class + dimensions),
how much of the furniture layout leaks from a fixed walk plus activity, and what
changes that leakage: the geometry evidence we hand the decoder, or the sensor
evidence we manage to extract. The paper's answer is ordered. Contact placement
moves the leakage more than visit count; the leakage is conditional on the
evidence the pipeline actually gets, not on the information that exists in
principle; and what remains at the end of the chain is selection among
near-truth candidates, not missing candidates.

## Fig. 1 (double column) Schematic + three-layer ladder

Core conclusion: the study measures leakage at three evidence levels, and each
level answers a different question.
Evidence: simulated 10,000 rooms (contact dispersal), 1,000 dev + 1,000 new rooms
(prior, decoder), 32 raw dual-device records, one real room.
Prototype: schematic-led composite. Panel a hero (task), panel b the ladder.
Rule: a connector exists only inside a set that was scored on the same rooms.
No arrow crosses two different room sets. Panel c is an error axis in metres and
is never drawn on the hit-rate axis.

## Fig. 2 (single column) Paired contrasts, forest plot

Core conclusion: every lever that moves whole-room recovery is a same-set
contrast, and the device-side levers are as large as the simulated ones.
Evidence: six contrasts, Newcombe hybrid score intervals on the two proportions
(paired bootstrap unavailable where only totals were frozen), exact McNemar where
pairs exist (reported in the caption, not drawn).
Prototype: quantitative grid, one axis, zero line.
Rule: no pooled "average gain"; each row keeps its own n and its own layer colour.

## Fig. 3 (single column) Budget x quality matrix

Core conclusion: visits barely move recovery; sensor severity moves it a lot,
and the 10-visit / severity-1 cell is not monotone.
Evidence: 12 rooms x 3 visits x 3 severities, 108 regenerated rooms, paired
McNemar by room (11:2, p=0.0225 vs 6:3, p=0.508).
Prototype: quantitative grid, heat map hero + two marginal strips.
Rule: annotate counts, never interpolate; the cells are a grid, not a surface.

## Fig. 4 (single column) Same RMS, three spectra

Core conclusion: identical per-axis RMS produces 10/12 to 0/12 depending only on
the temporal structure of the error, and a gated gyro tracker recovers the
slow-drift case without touching the clean case.
Evidence: 12 rooms, frozen front end vs gated tracker vs unconditional tracker.
Prototype: quantitative grid, grouped bars + reference lines.
Rule: the three shapes share one RMS by construction; say so in the axis label.

## Fig. 5 (single column) Selection criteria do not replicate

Core conclusion: seven truth-free selection criteria were tried on three frozen
batches; none of them reproduces outside the batch it was tuned on.
Evidence: batches A (11500-11531 s=0), B (11200-11231 s=0), C (11600-11631 s=0.5).
Prototype: quantitative grid, dot plot with unmeasured cells left empty.
Rule: empty means not run, not zero; the panel says "n.r." explicitly.

## Fig. 6 (double column) Four rooms, truth vs prediction

Core conclusion: the residual failures are near-truth candidate choices (one
object off by tens of centimetres, or two objects swapping) rather than a wrong
room-scale solution.
Evidence: 11500 (all correct), 11509 / 11523 (one or two objects wrong),
11531 (no proposal survives the hard-cover search).
Prototype: image-plate-like small multiples of 2D layouts.
Rule: prediction solid, truth dashed, per-object centre error printed.

## Export contract

figsize in mm, Arial 7 pt, `pdf.fonttype=42`, `svg.fonttype='none'`,
top/right spines off, `axes.linewidth 0.8`, legend frame off, white background.
Each figure writes pdf + svg + png (600 dpi) + tiff (300 dpi, LZW) and a
`source-data/cvpr/figN.csv` with every plotted number.
Multi-panel figures call `require_matplotlib_panel_alignment(..., strict=True)`
at render time and store the JSON report beside the figure.
