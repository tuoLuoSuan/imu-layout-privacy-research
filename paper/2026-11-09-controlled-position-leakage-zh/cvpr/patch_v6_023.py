
from pathlib import Path
C = Path(r'D:/Project/imu环境重建/paper/2026-11-09-controlled-position-leakage-zh') / 'cvpr'
s = (C / 'manuscript_v5_023.md').read_text(encoding='utf-8')

def rep(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, 1)

# ---------- figure 4 ----------
rep("![What is observed in the nine visit-by-severity conditions? Larger counts indicate more whole-room hits within that cell. "
    "Each cell is one synthetic realisation on the same twelve rooms, with duration and error realisation also changing with visits, "
    "so the grid does not isolate either axis.](../figures/cvpr/fig3_budget_quality021_single.png){width=100%}",
    "![How do visit count and sensor severity interact on the same twelve rooms? "
    "Cell values are mean whole-room recoveries of twelve rooms over three independently seeded realisations, so each cell rests on 36 observations. "
    "Coverage stays at 1.0 in every cell. The visit axis helps while evidence is good and reverses once the slow bias dominates, "
    "which is why the two axes are not separable in this grid.](../figures/cvpr/fig3_budget_quality023.png){width=100%}")

# ---------- grid paragraphs ----------
old86 = ("**Visits and quality at full coverage.** Twelve rooms were evaluated under all combinations of six, ten and fourteen visits "
         "and sensor severity 0, 0.5 and 1. Whole-room counts are 7/6/3, 7/6/6 and 8/7/4. Walking coverage remains 1.0. "
         "The within-room averaged severity-0 versus severity-1 contrast is +25.0 percentage points with room-cluster sign-flip p = 0.1328. "
         "The fourteen-versus-six contrast is +8.33 percentage points with p = 0.6563. Pooling the repeated conditions as 36 independent "
         "room pairs produces inappropriate p values. Record duration and common-prefix noise also change with visits despite equal integer seeds. "
         "The matrix therefore leaves the effect of repeated contacts coupled to these factors and establishes no device-level activity threshold.")
new86 = ("**Visits and error interact.** Twelve rooms were evaluated under all combinations of six, ten and fourteen visits and sensor "
         "severity 0, 0.5 and 1, three times each with independent noise seeds, giving 36 observations per cell. Walking coverage is 1.0 "
         "throughout. Whole-room hits of 36 rise with visits at severity 0 (18, 21, 23) and at severity 0.5 (16, 20, 21), and fall at "
         "severity 1 (14, 12, 11). Read the other way, severity 0 to 1 costs 1.3 of twelve rooms at six visits (Wilcoxon over the per-room "
         "counts, p = 0.44), 3.0 at ten visits (p = 0.0625) and 4.0 at fourteen visits (p = 0.0156, seven rooms worse and none better). "
         "Mean instance F1 follows the same ordering, from 0.896 at fourteen visits and zero severity to 0.402 at fourteen visits and "
         "severity 1. The mechanism is record length: every added visit lengthens the same walk, and a slow bias integrated over a longer "
         "record does more damage, so the visit axis is a joint manipulation of contact count and drift exposure rather than a controlled "
         "dose. This grid therefore supports an interaction and not a device-level activity threshold.")
rep(old86, new86)

old88 = ("**Matching the noise prefix reverses the axis.** The handset generator drew acceleration and gyro noise from one stream in "
         "recording order, and the perturbation model consumed randomness over the whole record and centred its bias walk on the record mean. "
         "A longer recording therefore changed the noise sequence that earlier samples received. Both are fixed by explicit options that "
         "separate the per-channel streams and anchor the bias walk at the first sample; with them enabled, the first 100 s of the six-, ten- "
         "and fourteen-visit recordings of a room agree to zero for acceleration, gyro and timestamps. Regenerating all 108 cells under the "
         "matched protocol gives whole-room counts of 4/5/7, 5/6/6 and 7/7/6. The severity contrast becomes -8.33 percentage points "
         "(room-cluster p = 0.625) and the visit contrast +11.11 percentage points (p = 0.406), so the ordering seen in the first run does not "
         "survive. Between the two protocols 33 of 108 cells change hit status, 8 of them at zero severity. Twelve rooms with one realisation "
         "per cell cannot separate a contact effect from the noise draw; we report the grid as a negative result and size the next batch on "
         "the realisation spread rather than on the first run axis slope.")
new88 = ("**Why the grid is regenerated.** The handset generator drew acceleration and gyro noise from one stream in recording order, and the "
         "perturbation model consumed randomness over the whole record and centred its bias walk on the record mean, so a longer recording "
         "changed the noise sequence that earlier samples received. Both are fixed by explicit options that separate the per-channel streams and "
         "anchor the bias walk at the first sample; with them enabled, the first 100 s of the six-, ten- and fourteen-visit recordings of a room "
         "agree to zero for acceleration, gyro and timestamps. Between the two protocols 33 of 108 cells change hit status, 8 of them at zero "
         "severity, and the single-realisation grid of the original run (7/6/3, 7/6/6, 8/7/4) had one cell at 4/12 that three realisations place "
         "at 3.7/12 with a different neighbour ordering. We therefore report the matched protocol with replication, and we do not read the sign "
         "of an axis from one draw.")
rep(old88, new88)

# ---------- discussion ----------
rep("The twelve-room grid carries one realisation per cell and cannot separate a contact effect from a noise draw.",
    "The twelve-room grid carries three realisations per cell, which averages the noise draw out, but record duration still grows with "
    "visits, so its visit axis is not a controlled contact count.")

# ---------- conclusion ----------
rep("Two protocols of the same grid disagree on the sign of the severity contrast, so no budget number is quoted without its protocol.",
    "In the twelve-room grid the severity cost grows with record length, from 1.3 of twelve rooms at six visits to 4.0 at fourteen "
    "(p = 0.0156), so a budget number is quoted with its record length and protocol.")

# ---------- abstract closing sentence ----------
rep("A twelve-room visit-by-severity grid does not identify either axis once noise prefixes are matched, so we report budgets only with their protocol.",
    "A twelve-room visit-by-severity grid, replicated three times per cell, shows the severity cost growing with record length, from 1.3 of twelve "
    "rooms at six visits to 4.0 at fourteen (p = 0.0156), so a budget figure is quoted with its record length and protocol.")

dst = C / 'manuscript_v6_023.md'
dst.write_text(s, encoding='utf-8')
print('written', dst, len(s))
