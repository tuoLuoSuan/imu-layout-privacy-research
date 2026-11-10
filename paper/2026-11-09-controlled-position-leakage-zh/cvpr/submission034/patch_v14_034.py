"""v14: decoder and sensor-error robustness of the placement effect, plus the
budget curve, folded into the v13 manuscript and supplement."""
from pathlib import Path

MAIN = Path('main.tex')
SUPP = Path('supplement.tex')


def rep(path, old, new, count=1):
    text = path.read_text(encoding='utf-8')
    assert text.count(old) >= 1, ('missing', old[:80])
    text = text.replace(old, new, count)
    path.write_text(text, encoding='utf-8')


ABSTRACT_OLD = "gain of 28.12 points ({[}15.62, 40.62{]}, exact McNemar p = 1.2e-4)."
ABSTRACT_NEW = (r"gain of 28.12 points ({[}15.62, 40.62{]}, exact McNemar p = 1.2e-4)." "\n"
                r"Two other decoders keep that sign (+26.56 and +15.62 points, both" "\n"
                r"$p<0.02$), and so does sensor error at severity 0.5 (+17.19 points," "\n"
                r"$p=0.013$).")

PLACE_OLD = (r"Both device blocks share one" "\n"
             r"finite chain, so this estimate is conditional on its acquisition and" "\n"
             r"refinement and does not establish transfer to another decoder.")
PLACE_NEW = (r"The decoder is not the source. Decoding the same two recordings per room" "\n"
             r"with a candidate cap of 64 gives 52/64 against 35/64, +26.56 points with" "\n"
             r"$p=7.6e-5$; adding a wall-support price to that cap gives 54/64 against" "\n"
             r"44/64, +15.62 points with $p=0.013$. The sign survives all three" "\n"
             r"decoders, the magnitude does not, because a priced pool lifts the" "\n"
             r"repeated arm from 30 to 44 rooms (Fig. 6a, Table S14). Sensor error" "\n"
             r"leaves the sign as well: over the same 64 rooms at severity 0.5," "\n"
             r"dispersed placement recovers 36 and repeated placement 25, a gain of" "\n"
             r"17.19 points ({[}4.69, 29.69{]}, $p=0.013$), while mean instance F1 is" "\n"
             r"flat at 0.743 against 0.767. The benefit therefore concentrates on" "\n"
             r"rooms near the success boundary rather than raising accuracy" "\n"
             r"uniformly (Table S15).")

MIX_OLD = (r"With twelve rooms per block and one severity, these" "\n"
           r"sign counts are descriptive (Table S13).")
MIX_NEW = (r"With twelve rooms per block and one severity, these" "\n"
           r"sign counts are descriptive (Table S13)." "\n"
           "\n"
           r"\textbf{The budget bounds that gain.} Over 76 rooms with the quota held" "\n"
           r"fixed, spreading the kept contacts buys $+0.109$ mean F1 at six contacts" "\n"
           r"(30 rooms better, 7 worse, 39 equal, sign-flip $p=3.0e-5$), $+0.045$ at" "\n"
           r"eight, $+0.010$ at ten, and $-0.017$ at twelve, where the budget is" "\n"
           r"nearly the whole set (Fig. 6b, Table S16). Selecting where contacts" "\n"
           r"land is a lever only while the budget is tight; once every contact is" "\n"
           r"kept, both arms coincide by construction at 55/76.")

FIG_OLD = r"\begin{figure*}[t]" "\n" r"\centering" "\n" r"\includegraphics[width=\textwidth]{../../figures/cvpr/fig_real_cases031.pdf}"
FIG_NEW = (r"\begin{figure}[t]" "\n"
           r"\centering" "\n"
           r"\includegraphics[width=\columnwidth]{../../figures/cvpr/fig_robust034_col.pdf}" "\n"
           r"\caption{Does the placement effect depend on the decoder, on sensor" "\n"
           r"quality, or on the contact budget? Panel a gives the paired gain of" "\n"
           r"dispersed over repeated placement on 64 fresh rooms; the three decoder" "\n"
           r"rows keep the record, front end and refiners fixed, and the last row" "\n"
           r"adds severity-0.5 sensor error. Bars are room-bootstrap 95\% intervals." "\n"
           r"Panel b gives whole-room recovery against the number of contacts kept" "\n"
           r"under a fixed class quota over 76 rooms, for the most-spread and a" "\n"
           r"random selection of the same size. The two curves meet once every" "\n"
           r"contact is kept.}" "\n"
           r"\end{figure}" "\n"
           "\n"
           r"\begin{figure*}[t]" "\n" r"\centering" "\n" r"\includegraphics[width=\textwidth]{../../figures/cvpr/fig_real_cases031.pdf}")

SUPP_TAIL = Path('supplement.tex').read_text(encoding='utf-8')

S14 = r"""
\begin{minipage}{\linewidth}\subsection*{Table S14 Placement under three decoders}
Both placement protocols of one room share the record, the front end, the two
refiners, the priors and the walk mask; only the decoder changes. {\tt base}
uses a candidate cap of 128, {\tt basec64} a cap of 64, and {\tt p10c64} the
same cap with wall and support prices ($\lambda=10$). Intervals are paired
room-bootstrap 95\% intervals over 64 fresh rooms.

\begin{center}\small\begin{tabular}{@{}p{\dimexpr\linewidth/5-2\tabcolsep\relax}p{\dimexpr\linewidth/5-2\tabcolsep\relax}p{\dimexpr\linewidth/5-2\tabcolsep\relax}p{\dimexpr\linewidth/5-2\tabcolsep\relax}p{\dimexpr\linewidth/5-2\tabcolsep\relax}@{}}\toprule
\textbf{Decoder} & \textbf{Dispersed} & \textbf{Repeated} & \textbf{Gain} & \textbf{Exact $p$} \\ \midrule
{\tt base}, cap 128 & 48/64 & 30/64 & +28.12 {[}15.62, 40.62{]} & 1.2e-4 \\
{\tt basec64}, cap 64 & 52/64 & 35/64 & +26.56 {[}15.62, 39.06{]} & 7.6e-5 \\
{\tt p10c64}, priced & 54/64 & 44/64 & +15.62 {[}4.69, 26.56{]} & 0.013 \\
\end{tabular}\end{center}
\end{minipage}
"""

S15 = r"""
\begin{minipage}{\linewidth}\subsection*{Table S15 Placement under sensor error}
Severity 0.5 applies the joint handset perturbation (white noise, bias walk,
scale and axis misalignment, timestamp jitter) with the same 14 contacts and
the {\tt base} decoder on rooms 11700--11763. The first 32 rooms are reported
alone to show how the interval narrows as the block grows.

\begin{center}\small\begin{tabular}{@{}p{\dimexpr\linewidth/6-2\tabcolsep\relax}p{\dimexpr\linewidth/6-2\tabcolsep\relax}p{\dimexpr\linewidth/6-2\tabcolsep\relax}p{\dimexpr\linewidth/6-2\tabcolsep\relax}p{\dimexpr\linewidth/6-2\tabcolsep\relax}p{\dimexpr\linewidth/6-2\tabcolsep\relax}@{}}\toprule
\textbf{Rooms} & \textbf{Dispersed} & \textbf{Repeated} & \textbf{Gain} & \textbf{Exact $p$} & \textbf{F1} \\ \midrule
32 & 19/32 & 13/32 & +18.75 {[}0.00, 37.50{]} & 0.109 & 0.746 / 0.751 \\
64 & 36/64 & 25/64 & +17.19 {[}4.69, 29.69{]} & 0.013 & 0.743 / 0.767 \\
\end{tabular}\end{center}
\end{minipage}
"""

S16 = r"""
\begin{minipage}{\linewidth}\subsection*{Table S16 Whole-room recovery against the contact budget}
The class quota is held fixed while the budget $k$ changes. Random arms average
three seeds inside each room before any cross-room statistic, so the paired
difference equals the difference of the two arm means. At $k=14$ both arms
keep every contact and coincide by construction.

\begin{center}\small\begin{tabular}{@{}p{\dimexpr\linewidth/7-2\tabcolsep\relax}p{\dimexpr\linewidth/7-2\tabcolsep\relax}p{\dimexpr\linewidth/7-2\tabcolsep\relax}p{\dimexpr\linewidth/7-2\tabcolsep\relax}p{\dimexpr\linewidth/7-2\tabcolsep\relax}p{\dimexpr\linewidth/7-2\tabcolsep\relax}p{\dimexpr\linewidth/7-2\tabcolsep\relax}@{}}\toprule
\textbf{$k$} & \textbf{Dispersed} & \textbf{Random} & \textbf{$\Delta$F1} & \textbf{95\% interval} & \textbf{Better/worse} & \textbf{$p$} \\ \midrule
6 & 45/76 & 30.3/76 & +0.109 & {[}0.060, 0.159{]} & 30/7 & 3.0e-5 \\
8 & 47/76 & 35.7/76 & +0.045 & {[}0.011, 0.076{]} & 27/4 & 0.009 \\
10 & 49/76 & 45.0/76 & +0.010 & {[}-0.020, 0.037{]} & 16/8 & 0.51 \\
12 & 51/76 & 52.7/76 & -0.017 & {[}-0.043, 0.006{]} & 7/8 & 0.21 \\
14 & 55/76 & 55/76 & 0 & -- & 0/0 & -- \\
\end{tabular}\end{center}
\end{minipage}
"""


def main():
    rep(MAIN, ABSTRACT_OLD, ABSTRACT_NEW)
    rep(MAIN, PLACE_OLD, PLACE_NEW)
    rep(MAIN, MIX_OLD, MIX_NEW)
    rep(MAIN, FIG_OLD, FIG_NEW)
    marker = r"\end{document}"
    text = SUPP.read_text(encoding='utf-8')
    assert marker in text
    text = text.replace(marker, S14 + S15 + S16 + "\n" + marker, 1)
    SUPP.write_text(text, encoding='utf-8')
    print('patched', len(MAIN.read_text(encoding='utf-8')), len(SUPP.read_text(encoding='utf-8')))


if __name__ == '__main__':
    main()
