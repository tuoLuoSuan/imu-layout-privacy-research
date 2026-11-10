"""v14b: bring the manuscript back inside the eight-page limit."""
from pathlib import Path

MAIN = Path('main.tex')
SUPP = Path('supplement.tex')


def rep(old, new, path=MAIN):
    text = path.read_text(encoding='utf-8')
    assert old in text, ('missing', old[:70])
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


TABLE_OLD = r"""\begin{table}[t]
\centering\small
\caption{Primary 32-record controls. Higher position F1 and whole-room counts indicate better recovery. All rows retain the same 0.5 m centre endpoint.}
\begin{tabular}{@{}p{.50\linewidth}rr@{}}\toprule
Arm & Centres & F1 \\\midrule
Declared side information only & 0/32 & 0.0915 \\
Older trajectory front end & 11/32 & 0.4375 \\
Raw phone and watch & 17/32 & 0.7275 \\
Reference pose, predicted actions & 26/32 & 0.9536 \\
\bottomrule\end{tabular}
\end{table}
"""
TABLE_NEW = ""

TEMP1_OLD = r"""At fixed nominal per-axis added RMS of 0.020 m/s\^{}2 for acceleration
and 0.003 rad/s for gyro, temporal structure also matters. Clean,
white-gyro, constant-gyro and slowly varying-gyro conditions recover
10/12, 11/12, 8/12 and 0/12, respectively. Slowly varying acceleration
gives 8/12. Slowly varying gyro errors can prevent the frozen front end
from detecting its required initial stationary block. Supplementary
Figure S1 and Table S6 retain the channel and correction controls.

Gated gyro-bias tracking leaves the unperturbed confirmation arm at
24/32. At severity 0.5 it changes 12/32 to 18/32 (p = 0.03125, Holm p =
0.09375), and at severity one 3/32 to 14/32 (p = 0.0034, Holm p =
0.0137). A second batch changes 13/32 to 16/32 at severity 0.5. Across
the two severity-0.5 batches, 25/64 becomes 34/64 through eleven gains
and two losses (p = 0.0225). For slowly varying gyro error in the
twelve-room diagnostic, gating restores 5/12 while retaining the clean
10/12. These results concern the evaluated error generator and frozen
front end.
"""
TEMP1_NEW = r"""At fixed nominal per-axis added RMS of 0.020 m/s\^{}2 and 0.003 rad/s,
temporal structure also matters: clean, white-gyro, constant-gyro and
slowly varying-gyro conditions recover 10/12, 11/12, 8/12 and 0/12,
because a slow gyro error can hide the initial stationary block that the
frozen front end requires. Gated bias tracking leaves the unperturbed
arm at 24/32 and changes 12/32 to 18/32 at severity 0.5 and 3/32 to
14/32 at severity one; across two severity-0.5 batches, 25/64 becomes
34/64 (p = 0.0225). These results concern the evaluated generator and
front end (Supplementary Figure S1, Tables S6 and S17).
"""

INV_OLD = r"""The inventory assumption also affects feasibility. These twelve rooms
contain four to seven instances, averaging 5.67. The correct list
recovers 7/12 with F1 0.8135. Removing one declared storage instance
yields nine proposal conflicts and mean F1 0.1965, while removing one
chair yields five conflicts and F1 0.4349. Mean true positives are 4.58,
1.08 and 2.33, respectively, distinct from mean output counts of 5.25,
1.25 and 2.92. Whole-room success is zero by definition after a
reference instance is removed from the declaration. Feasibility and
matched-instance counts therefore carry the substantive comparison.
"""
INV_NEW = r"""The inventory assumption also affects feasibility. These twelve rooms
hold four to seven instances, 5.67 on average. Dropping one declared
storage instance leaves nine proposal conflicts and F1 0.1965, dropping
one chair leaves five and 0.4349, and mean true positives fall from 4.58
to 1.08 and 2.33. Whole-room success is zero by construction once a
reference instance leaves the declaration, so feasibility and
matched-instance counts carry the comparison.
"""

S17 = r"""
\begin{minipage}{\linewidth}\subsection*{Table S17 Primary 32-record controls}
All rows retain the same 0.5 m centre endpoint; higher position F1 and
whole-room counts indicate better recovery.

\begin{center}\small\begin{tabular}{@{}p{\dimexpr\linewidth/2-2\tabcolsep\relax}p{\dimexpr\linewidth/4-2\tabcolsep\relax}p{\dimexpr\linewidth/4-2\tabcolsep\relax}@{}}\toprule
\textbf{Arm} & \textbf{Centres} & \textbf{F1} \\ \midrule
Declared side information only & 0/32 & 0.0915 \\
Older trajectory front end & 11/32 & 0.4375 \\
Raw phone and watch & 17/32 & 0.7275 \\
Reference pose, predicted actions & 26/32 & 0.9536 \\
\end{tabular}\end{center}
\end{minipage}
"""


def main():
    rep(TABLE_OLD, TABLE_NEW)
    rep(TEMP1_OLD, TEMP1_NEW)
    rep(INV_OLD, INV_NEW)
    text = SUPP.read_text(encoding='utf-8')
    marker = r"\end{document}"
    SUPP.write_text(text.replace(marker, S17 + "\n" + marker, 1), encoding='utf-8')
    print('ok')


if __name__ == '__main__':
    main()
