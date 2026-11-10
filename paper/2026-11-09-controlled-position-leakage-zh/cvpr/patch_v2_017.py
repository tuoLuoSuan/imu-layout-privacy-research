# -*- coding: utf-8 -*-
"""Build manuscript_v2_017.md: DS fact-corrected copy plus prefix-audit evidence."""
from pathlib import Path
HERE = Path(__file__).resolve().parent
src = (HERE / "manuscript_reviewed_017.md").read_text(encoding="utf-8")
a = src.index("> Fact-corrected working copy")
b = src.index("# Abstract")
src = src[:a] + src[b:]
edits = [
 ("A twelve-room visit-by-severity diagnostic remains exploratory after accounting for repeated conditions.",
  "A twelve-room visit-by-severity grid is reported as a negative identification result: room-clustered contrasts are not significant, and regenerating the same conditions with matched noise prefixes reverses the severity contrast and changes 33 of 108 cells. Relaxing the matching tolerance from 0.5 m to 1 m leaves twelve of 32 raw-input rooms unrecovered."),
 ("Visit changes also alter duration and noise realisation.",
  "Visit changes also alter duration and noise realisation: at equal integer seeds the original generators draw different noise sequences for recordings of different length, so the grid was regenerated with matched prefixes before the axis contrasts were recomputed."),
]
for old, new in edits:
    assert src.count(old) == 1, old[:40]
    src = src.replace(old, new)
anchor = "The matrix therefore leaves the effect of repeated contacts coupled to these factors and establishes no device-level activity threshold."
assert src.count(anchor) == 1
par = """

**Matching the noise prefix reverses the axis.** The handset generator drew acceleration and gyro noise from one stream in recording order, and the perturbation model consumed randomness over the whole record and centred its bias walk on the record mean. A longer recording therefore changed the noise sequence that earlier samples received. Both are fixed by explicit options that separate the per-channel streams and anchor the bias walk at the first sample; with them enabled, the first 100 s of the six-, ten- and fourteen-visit recordings of a room agree to zero for acceleration, gyro and timestamps. Regenerating all 108 cells under the matched protocol gives whole-room counts of 4/5/7, 5/6/6 and 7/7/6. The severity contrast becomes -8.33 percentage points (room-cluster p = 0.625) and the visit contrast +11.11 percentage points (p = 0.406), so the ordering seen in the first run does not survive. Between the two protocols 33 of 108 cells change hit status, 8 of them at zero severity. Twelve rooms with one realisation per cell cannot separate a contact effect from the noise draw; we report the grid as a negative result and size the next batch on the realisation spread rather than on the first run axis slope."""
src = src.replace(anchor, anchor + par)
old_c = "A general raw-IMU activity threshold remains unresolved."
assert src.count(old_c) == 1, "conclusion anchor"
src = src.replace(old_c, "Two protocols of the same grid disagree on the sign of the severity contrast, so no budget number is quoted without its protocol. A general raw-IMU activity threshold remains unresolved.")
out = HERE / "manuscript_v2_017.md"
out.write_text(src, encoding="utf-8")
print("wrote", out.name, len(src.split()), "words")