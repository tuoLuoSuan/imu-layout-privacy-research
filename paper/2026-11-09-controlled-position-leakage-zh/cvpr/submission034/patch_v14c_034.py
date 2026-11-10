"""v14c: replication of the grid on a second block of twelve rooms."""
from pathlib import Path

MAIN = Path('main.tex')
SUPP = Path('supplement.tex')

OLD = (r"sign-flip p = 0.125. Visits also lengthen the recording, so interpreting" "\n"
       r"a separate contact-count effect requires further controls.")
NEW = (r"sign-flip p = 0.125. The same grid on a second block of twelve rooms" "\n"
       r"(11700--11711, one realisation, fresh noise seeds) keeps every sign:" "\n"
       r"4 rooms gain from more visits at severity zero against none that lose," "\n"
       r"severity costs 6 rooms at ten and at fourteen visits, and the" "\n"
       r"interaction stays negative in 3 rooms with none positive, at" "\n"
       r"sign-flip $p=0.25$ (Table S18). Visits also lengthen the recording, so" "\n"
       r"interpreting a separate contact-count effect requires further controls.")

S18 = r"""
\begin{minipage}{\linewidth}\subsection*{Table S18 Grid replication on a second room block}
Rooms 11700--11711, one realisation per cell, prefix-matched noise and offset
3000, decoded with the same chain as the main grid. Whole-room hits out of 12
rooms.

\begin{center}\small\begin{tabular}{@{}p{\dimexpr\linewidth/4-2\tabcolsep\relax}p{\dimexpr\linewidth/4-2\tabcolsep\relax}p{\dimexpr\linewidth/4-2\tabcolsep\relax}p{\dimexpr\linewidth/4-2\tabcolsep\relax}@{}}\toprule
\textbf{Visits} & \textbf{Severity 0} & \textbf{0.5} & \textbf{1} \\ \midrule
6 & 7/12 & 6/12 & 4/12 \\
10 & 10/12 & 7/12 & 4/12 \\
14 & 11/12 & 6/12 & 5/12 \\
\midrule
\multicolumn{4}{@{}l}{Visits 6 to 14 at severity 0: 4 better, 0 worse, $p=0.125$} \\
\multicolumn{4}{@{}l}{Severity 0 to 1 at 10 and 14 visits: 0 better, 6 worse, $p=0.031$} \\
\multicolumn{4}{@{}l}{Difference-in-differences: 3 negative, 9 zero, mean $-0.25$ rooms, $p=0.25$} \\
\end{tabular}\end{center}
\end{minipage}
"""


def main():
    text = MAIN.read_text(encoding='utf-8')
    assert OLD in text
    MAIN.write_text(text.replace(OLD, NEW, 1), encoding='utf-8')
    t = SUPP.read_text(encoding='utf-8')
    marker = r"\end{document}"
    SUPP.write_text(t.replace(marker, S18 + "\n" + marker, 1), encoding='utf-8')
    print('ok')


if __name__ == '__main__':
    main()
