from pathlib import Path

SRC = Path('manuscript_v7_025_review.md')
DST = Path('manuscript_v8_026.md')
s = SRC.read_text(encoding='utf-8')
n = 0

def rep(old, new):
    global s, n
    if s.count(old) != 1:
        raise SystemExit('expected exactly one match, got %d for: %s' % (s.count(old), old[:80]))
    s = s.replace(old, new)
    n += 1

rep('achieves position F1 of 0.7275 and whole-room recovery in 17 records.',
    'achieves position F1 of 0.7275 and whole-room recovery in 17 records. The same decoder given only the declared outline, start and inventory recovers none of the 32 rooms.')

old_fig2 = '![How does position recovery vary across the measured activity budgets? Higher room-macro position F1 indicates better matching, and both panels display the same measurements. Each measured cell retains 10,000 controlled rooms with ideal trajectories, declared side information and the outline decoder, while hatching and hollow markers locate five unmeasured cells and lines provide reading guides without interpolation.](../figures/cvpr/fig_activity_budget025.png){width=100%}'
new_fig2 = '![How does position recovery vary across the measured activity budgets? Panel a gives room-macro position F1 for 43 measured cells, each retaining 10,000 controlled rooms with ideal trajectories, declared side information and the outline decoder. Hatching marks the five unmeasured cells. Panel b repeats the same values as a point lattice, where lines are reading guides and do not interpolate. The fixed-budget contact control is reported separately.](../figures/cvpr/fig_budget026.png){width=100%}'
rep(old_fig2, new_fig2)

old_fig4 = '![How do the replicated visit and handset-error conditions differ? Larger percentages indicate more whole-room successes, with counts shown over 36 room-repetition observations. The independent units are twelve rooms with three handset-noise repetitions each, wrist streams are fixed across repetitions, and visit count also changes duration.](../figures/cvpr/fig_visit_severity025.png){width=100%}'
new_fig4 = '![How do visit count and handset error interact on the same twelve rooms? Each cell gives whole-room recovery as a percentage and as hits over 36 room-repetition observations. Cells are means of three handset-noise realisations, wrist streams are fixed across repetitions, and visit count also changes recording duration, so the grid supports an interaction rather than a device-level activity threshold.](../figures/cvpr/fig_visits026.png){width=100%}'
rep(old_fig4, new_fig4)

anchor = 'Its nine-room gain includes pose-dependent effects on refinement and finite decoding.'
rep(anchor, anchor + '\n\n**What the declared priors alone recover.** The same directional decoder, candidate cap and support weight, fed only the room outline, start and inventory and given no signal, pose, walk point, contact, heading or event association, recovers 0 of 32 rooms with mean instance F1 0.0915. Against raw joint input the paired difference is seventeen rooms, with a paired room-bootstrap 95% interval of [34.4, 68.8] percentage points and exact McNemar p = 1.5e-5 (Supplementary Table S2). This is a control on one finite estimator, not a bound on what side information can achieve: holding the decoder fixed isolates what the inertial evidence contributes, not what an optimal prior-only solver would reach.')

rep('Supplementary Table S1 reports the separate prior-enabled development configuration.',
    'Supplementary Table S1 reports the separate prior-enabled development configuration, and Supplementary Table S2 the prior-only control.')

DST.write_text(s, encoding='utf-8')
print('replacements', n, 'lines', s.count(chr(10)) + 1)
