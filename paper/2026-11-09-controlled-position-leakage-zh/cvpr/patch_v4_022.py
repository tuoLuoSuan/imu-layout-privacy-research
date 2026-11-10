
import re
from pathlib import Path
C = Path(r'D:/Project/imu环境重建/paper/2026-11-09-controlled-position-leakage-zh') / 'cvpr'
src = (C / 'manuscript_v3_021.md').read_text(encoding='utf-8')

src = src.replace(
    "Supplementary Figures S1 and S2 give the cell-wise and three-dimensional views of the same measured activity-budget data.",
    "Figure 2 shows the same cells as a graded grid and as a three-dimensional surface.")

fig = ("![What does each measured cell recover, and how do the 43 cells sit in depth? Higher values indicate more "
       "correct instance positions, hatched corners mark unmeasured cells, and the depth panel repeats the same cells "
       "without ticks. Each cell retains 10,000 controlled rooms with ideal trajectories and class-level contacts.]"
       "(../figures/cvpr/figA1_activity_grid021.png){width=100%}")
anchor = "The budget-grid results in Table 1 use the separate development configuration with the declared desk-wall prior."
src = src.replace(anchor,
    anchor.replace("The budget-grid results in Table 1 use",
                   "Supplementary Table S1 lists the four operating points of the budget-grid results, which use")
    + "\n\n" + fig)

lines = src.split('\n')
out, i = [], 0
dropped = 0
while i < len(lines):
    ln = lines[i]
    if ln.startswith(': Table 1.'):
        i += 1
        while i < len(lines) and (lines[i].strip() == '' or lines[i].startswith('|')):
            i += 1; dropped += 1
        continue
    out.append(ln); i += 1
src = '\n'.join(out)
src = re.sub(r'\n{3,}', '\n\n', src)
src = src.replace('(Fig. 4)', '(Fig. 5)')
assert '| Operating point' not in src and ': Table 1.' not in src and '(Fig. 5)' in src
(C / 'manuscript_v4_022.md').write_text(src, encoding='utf-8')
print('lines', len(src.split('\n')), 'dropped', dropped)
print([l[:60] for l in src.split('\n') if 'figA1' in l])
