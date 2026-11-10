from pathlib import Path
MAIN = Path('main.tex')
OLD = (r"sign-flip p = 0.125. The same grid on a second block of twelve rooms" "\n"
       r"(11700--11711, one realisation, fresh noise seeds) keeps every sign:" "\n"
       r"4 rooms gain from more visits at severity zero against none that lose," "\n"
       r"severity costs 6 rooms at ten and at fourteen visits, and the" "\n"
       r"interaction stays negative in 3 rooms with none positive, at" "\n"
       r"sign-flip $p=0.25$ (Table S18). Visits also lengthen the recording, so" "\n"
       r"interpreting a separate contact-count effect requires further controls.")
NEW = (r"sign-flip p = 0.125. A second block of twelve rooms (11700--11711, one" "\n"
       r"realisation) keeps every sign: more visits help 4 rooms at severity zero" "\n"
       r"and hurt none, severity still costs 6 rooms, and the interaction stays" "\n"
       r"negative in 3 rooms at $p=0.25$ (Table S18). Visits also lengthen the" "\n"
       r"recording, so a separate contact-count effect needs further controls.")
t = MAIN.read_text(encoding='utf-8')
assert OLD in t
MAIN.write_text(t.replace(OLD, NEW, 1), encoding='utf-8')
print('ok')
