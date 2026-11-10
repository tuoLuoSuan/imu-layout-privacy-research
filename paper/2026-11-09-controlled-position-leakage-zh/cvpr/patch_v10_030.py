"""Apply the contact-confidence result (030) to the v9 manuscript.

SRC  cvpr/manuscript_v9_029.md
DST  cvpr/manuscript_v10_030.md
SUPP cvpr/supplement_v9_029.md -> cvpr/supplement_v10_030.md
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'manuscript_v9_029.md'
DST = ROOT / 'manuscript_v10_030.md'
SUPP_SRC = ROOT / 'supplement_v9_029.md'
SUPP_DST = ROOT / 'supplement_v10_030.md'

PARA = (
    '**Contact confidence is not event length.** The confidence idea is worth one control: '
    'not every detected contact is equally trustworthy, so a quality score could thin them. '
    'Holding the fourteen-visit recording fixed, ranking contacts by how long the event lasted '
    'and keeping the longest eleven, nine and six recovers 4, 0 and 0 of 12 rooms with mean F1 '
    '0.7786, 0.6431 and 0.5486. Random subsets of the same sizes, three seeds each, recover 19 of '
    '36, 17 of 36 and 14 of 36 room observations with mean F1 0.8026, 0.7630 and 0.7422. Room by '
    'room the six-contact duration arm is worse than its own random draws in 9 of 12 rooms and '
    'better in 2. Duration turns out to be a category proxy: cabinets produce the longest events, '
    'so the six-contact arm keeps 4.6 cabinet contacts on average and no lying contact at all, '
    'against 1.9 lying contacts under random, which concentrates the evidence on one wall. Two '
    'further signals are unavailable rather than unhelpful. All 14 contacts of all 12 rooms '
    'reproduce across the three handset-noise realisations at 80% temporal overlap, so replication '
    'agreement has no spread to select on, and cross-source agreement is defined only for cabinets, '
    'where the fusion design discards the phone side. Contact usefulness in this chain is spatial. '
    '(Supplementary Table S5.)'
)

TABLE = """Table S5. Contact confidence as event duration, at one fixed fourteen-visit recording and severity zero. Every arm keeps the same front end, refiners and decoder; only which qualified contacts reach them changes. Counts are whole-room hits over 12 rooms, and the random rows pool three seeds per count. Cabinet events last longest, so duration ranking keeps cabinets and drops lying contacts.

| Arm | Contacts kept | Whole-room hits | Mean F1 | Mean contact duration (s) |
| --- | --- | --- | --- | --- |
| All contacts | 14 | 7 | 0.8135 | 10.41 |
| Longest 11 | 11 | 4 | 0.7786 | 10.97 |
| Random 11 (three seeds) | 11 | 19/36 | 0.8026 | 10.3-10.4 |
| Longest 9 | 9 | 0 | 0.6431 | 11.35 |
| Random 9 (three seeds) | 9 | 17/36 | 0.7630 | 10.3-10.5 |
| Longest 6 | 6 | 0 | 0.5486 | 11.74 |
| Random 6 (three seeds) | 6 | 14/36 | 0.7422 | 10.2-10.6 |
"""


def rep(text, old, new, count=1):
    assert text.count(old) == count, (old[:60], text.count(old))
    return text.replace(old, new)


def main():
    text = SRC.read_text(encoding='utf-8')
    anchor = ('Read together, the six-to-fourteen gain in the grid is mostly a contact-count gain, '
              'and extra drift exposure at fixed contact count buys at most one room. The oracle arms '
              'are accuracy controls, not reported systems: they place a larger share of the right '
              'boxes (F1 0.7960 and 0.8671 against 0.7274 and 0.7917) without recovering more rooms.')
    text = rep(text, anchor, anchor + '\n\n' + PARA)
    DST.write_text(text, encoding='utf-8')

    supp = SUPP_SRC.read_text(encoding='utf-8')
    supp = supp.rstrip() + '\n\n' + TABLE
    SUPP_DST.write_text(supp, encoding='utf-8')

    print(json.dumps({'lines': len(text.splitlines()), 'paragraphs_added': 1,
                      'supplement_lines': len(supp.splitlines())}))


if __name__ == '__main__':
    main()
