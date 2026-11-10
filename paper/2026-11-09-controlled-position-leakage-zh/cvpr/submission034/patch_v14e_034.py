from pathlib import Path
MAIN = Path('main.tex')
t = MAIN.read_text(encoding='utf-8')
old_begin = r"\begin{figure}[t]" "\n" r"\centering" "\n" r"\includegraphics[width=\columnwidth]{../../figures/cvpr/fig_robust034_col.pdf}"
new_begin = r"\begin{figure*}[t]" "\n" r"\centering" "\n" r"\includegraphics[width=\textwidth]{../../figures/cvpr/fig_robust034.pdf}"
assert old_begin in t
t = t.replace(old_begin, new_begin, 1)
old_end = r"contact is kept.}" "\n" r"\end{figure}"
new_end = r"contact is kept.}" "\n" r"\end{figure*}"
assert old_end in t
t = t.replace(old_end, new_end, 1)
MAIN.write_text(t, encoding='utf-8')
print('ok')
