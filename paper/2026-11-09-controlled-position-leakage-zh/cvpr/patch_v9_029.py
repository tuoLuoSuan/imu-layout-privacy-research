"""v8 -> v9: second prior-only set, feasibility vs correctness, the two
controls that bracket visit count against duration, and inventory error."""
import json
from pathlib import Path

SRC = Path('manuscript_v8_026.md')
DST = Path('manuscript_v9_029.md')
text = SRC.read_text(encoding='utf-8')
applied = []


def rep(old, new):
    global text
    assert text.count(old) == 1, (text.count(old), old[:80])
    text = text.replace(old, new)
    applied.append(old[:60])


rep('The same decoder given only the declared outline, start and inventory recovers none of the 32 rooms.',
    'The same decoder given only the declared outline, start and inventory recovers none of the 32 rooms, '
    'and none of a further independent 32 rooms where the stored raw arm recovers 21.')

rep('Recording duration remains coupled to visit count.',
    'Recording duration remains coupled to visit count, and two follow-up controls bracket that coupling: '
    'one holds the recording fixed and cuts the contacts, the other holds the contact count and lengthens '
    'the recording. Decoder solve status is reported apart from correctness.')

rep('This is a control on one finite estimator, not a bound on what side information can achieve: '
    'holding the decoder fixed isolates what the inertial evidence contributes, not what an optimal '
    'prior-only solver would reach.',
    'This is a control on one finite estimator, not a bound on what side information can achieve: '
    'holding the decoder fixed isolates what the inertial evidence contributes, not what an optimal '
    'prior-only solver would reach. A second independent 32-room set repeats the result: 0 of 32 rooms '
    'with mean instance F1 0.0793, against 21 of 32 and F1 0.8013 for that set\'s own stored raw arm. '
    'The paired difference is 21 rooms, with a room-bootstrap 95% interval of [50.0, 81.3] percentage '
    'points and exact McNemar p = 9.5e-7 (Supplementary Table S3). The two sets are reported separately '
    'rather than pooled, because their raw arms were frozen at different times and carry different '
    'denominators.')

rep('Visit count changes both contact count and recording duration, leaving the individual '
    'contributions of contact accumulation and drift exposure unresolved.',
    '''Visit count changes both contact count and recording duration. Two controls separate the moves.

**Contacts move the visit axis.** Holding one fourteen-visit recording fixed and thinning its qualified contacts to six, the full fourteen contacts recover 7 of 12 rooms with mean F1 0.8135, the first six recover 4 of 12 with 0.7274, a dispersed six recover 5 of 12 with 0.7028, three random six-contact draws recover 8 of 36 with 0.6435, and an oracle six that is allowed to look at the true object identity recovers 4 of 12 with 0.7960. Eight contacts are therefore worth three rooms at identical duration, while choosing which eight are kept changes mean F1 by up to 0.07 and changes no room outcome.

**Beyond fourteen contacts the axis saturates.** Lengthening the recording to twenty visits and keeping fourteen contacts recovers 8 of 12 rooms, the same as keeping all twenty, and dispersed and oracle fourteen are also 8 of 12. The whole-room gains over the stored fourteen-visit record are one room, which is the scale of a single room. Twenty contacts add nothing over fourteen once the recording is that long. Read together, the six-to-fourteen gain in the grid is mostly a contact-count gain, and extra drift exposure at fixed contact count buys at most one room. The oracle arms are accuracy controls, not reported systems: they place a larger share of the right boxes (F1 0.7960 and 0.8671 against 0.7274 and 0.7917) without recovering more rooms.

**Feasible is not correct.** Across the 324 replicated rows the decoder returns a solution in 266 (82.1%) and recovers the room in 156 (48.1%). Of the 266 solved rows, 110 are wrong: every declared item is placed consistently and at least one instance is still missed. The shortfall concentrates at zero severity, where 105 of 108 rows solve, 62 are right and 43 are internally consistent but wrong. The 58 rows that fail to solve never recover the room; they split into 45 proposal conflicts, 11 exhausted search budgets and 2 empty proposal pools. A solve rate and a recovery rate therefore answer different questions, and both are reported.

**A wrong inventory is not a small perturbation.** Editing only the declared list on the same twelve records, with the front end, refiners, candidate cap and support weight unchanged, the correct five-item inventory recovers 7 of 12 rooms with F1 0.8135 and places 4.58 of 5 declared items. Declaring no cabinet leaves four items, places 1.08 of 4 and produces nine proposal conflicts; merging the two chairs into one leaves four items, places 2.33 of 4 and produces five conflicts. Whole-room recovery is zero in both edited arms by construction, because the reference still contains the missing instance. The loss is therefore reported as feasibility: most rooms stop yielding any placement at all, rather than drifting by a few centimetres. The paper assumes the declared inventory is right, and this control shows what that assumption buys.''')

rep('These conditions define the scope of the reported recovery rates.',
    'The declared inventory is treated as correct throughout, and editing it removes the solution in '
    'most rooms rather than shifting it. These conditions define the scope of the reported recovery rates.')

DST.write_text(text, encoding='utf-8')
print(json.dumps({'src': str(SRC), 'dst': str(DST), 'replacements': len(applied), 'lines': len(text.splitlines())}, indent=1))
