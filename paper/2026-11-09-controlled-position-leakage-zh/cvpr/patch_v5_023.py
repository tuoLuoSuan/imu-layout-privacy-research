
from pathlib import Path
C = Path(r'D:/Project/imu环境重建/paper/2026-11-09-controlled-position-leakage-zh') / 'cvpr'
s = (C / 'manuscript_v4_022.md').read_text(encoding='utf-8')
def rep(old, new):
    global s
    assert old in s, old[:70]
    s = s.replace(old, new, 1)

# ---------- Abstract ----------
old_abs_start = "We measure how indoor activity reveals furniture positions when the room outline, start, inventory and nominal dimensions are known."
i0 = s.index(old_abs_start); i1 = s.index("\n\n![How does activity distribution", i0)
new_abs = (
"We measure how much furniture layout an inertial recording leaks when the room outline, start, inventory and nominal "
"dimensions are already known, and which property of the recording controls that leakage. Three evidence layers share "
"one frozen chain. In 10,000 controlled generated rooms with 55,000 target items, replacing repeated contacts by dispersed "
"contacts at the same route and the same fourteen interactions per room raises whole-room centre recovery from 39.78% to "
"64.70%, a paired gain of 24.92 percentage points with 95% interval [24.00, 25.84]; instance position F1 reaches 90.43%. "
"The budget is not a property of the room alone. On the same 1,000 development rooms a declared desk-wall prior moves "
"recovery from 65.1% to 82.6%, and on a separate 1,000-room confirmation set a decoder portfolio moves it from 85.1% to "
"94.5%. On 32 raw phone-plus-watch records from a frozen supervised chain, 17 rooms are recovered; the same predicted "
"actions with ground-truth pose recover 26, so pose accounts for a measurable part of the device-side loss. That loss is "
"not set by error magnitude: at equal per-axis RMS the slowly varying gyro error removes all twelve rooms while white "
"gyro error leaves eleven. A gated gyro-bias tracker recovers 12/32 to 18/32 rooms at severity 0.5 and 3/32 to 14/32 at "
"severity 1.0, and 25/64 to 34/64 when both batches are pooled (p=0.0225), without touching the undisturbed cell. One "
"real dormitory replay localises four objects with centre errors of 0.09 to 0.23 m. A twelve-room visit-by-severity grid "
"does not identify either axis once noise prefixes are matched, so we report budgets only with their protocol. Code "
"repository https://github.com/tuoLuoSuan/imu-layout-privacy-research."
)
s = s[:i0] + new_abs + s[i1:]

# ---------- Intro contribution paragraph ----------
old_claim = ("Contact placement has a large paired effect at fixed route and interaction count. Declared side information and "
"decoder policy change the measured budget point on their respective room sets. Device acquisition adds losses that are "
"sensitive to temporal sensor-error structure. Finding a near-truth candidate for every instance also leaves "
"joint-compatibility and selection losses. Each statement retains its own evidence layer and evaluation set.")
new_claim = (
"The measurements support four statements, each on its own evidence layer. First, contact placement is an intervention in "
"its own right: with route, visit count and decoder held fixed, dispersing contacts is worth 24.92 percentage points of "
"whole-room recovery over 10,000 rooms. Second, the budget is conditional rather than intrinsic: a declared prior and a "
"decoder portfolio are worth 17.5 and 9.4 percentage points on their own room sets, so a recovery rate quoted without its "
"side information and estimator is not reproducible. Third, what a device obtains is separated from what geometry allows "
"by a measurable amount, and that separation follows the temporal structure of the sensor error rather than its RMS: a "
"gated gyro-bias tracker recovers a third of the perturbed rooms that the frozen chain loses. Fourth, once every instance "
"has a near-truth candidate in the finite pool, the remaining loss at zero severity sits in joint coverage and selection, "
"not in proposal recall.")
rep(old_claim, new_claim)

# ---------- Sensor error: table ----------
rep("**Sensor error.** We scale the handset error by a severity factor that multiplies white noise, adds a bias random walk, "
"applies a scale and axis misalignment matrix and jitters the timestamps. On twelve rooms, severity 0 gives 7/12 whole-room "
"recovery, 0.5 gives 3/12, 0.75 gives 2/12, 1.0 gives 1/12, and 2.0 or more fails in the front end for every room because "
"the initial stationary segment is never detected. An RMS acceleration difference of 0.013 m/s^2, about 1.3 mg, is enough "
"to lose four rooms out of twelve.",
"**Sensor error.** We scale the handset error by a severity factor that multiplies white noise, adds a bias random walk, "
"applies a scale and axis misalignment matrix and jitters the timestamps. Table 2 gives the ladder on twelve rooms. An RMS "
"acceleration difference of 0.013 m/s^2, about 1.3 mg, already costs four of twelve rooms, and from severity 2 upward the "
"front end fails on every room because the initial stationary segment is never detected. At severity 0.5 the four terms are "
"not interchangeable: the bias walk alone reproduces the full collapse (3/12), scale and axis misalignment cost two rooms "
"(5/12), whereas white noise and timestamp jitter alone leave the cell unchanged (7/12, identical room by room).")

# ---------- Insert Table 2 after the Sensor error paragraph ----------
tbl2 = ("\n\n: Table 2. Whole-room recovery against handset severity on the same twelve rooms, and single-term attribution at "
"severity 0.5. Severity scales all four error terms together, so the row entries are not single-variable effects; the "
"attribution rows apply one term at a time at severity 0.5.\n\n"
"| Condition | Acceleration RMS difference (m/s^2) | Whole-room recovery |\n"
"|---|---|---|\n"
"| severity 0 | 0 | 7/12 |\n"
"| severity 0.5 | 0.0132 | 3/12 |\n"
"| severity 0.75 | 0.0218 | 2/12 |\n"
"| severity 1.0 | 0.0315 | 1/12 |\n"
"| severity 2.0 | 0.0872 | 0/12 |\n"
"| severity 4.0 | 0.2364 | 0/12 |\n"
"| bias walk alone, s=0.5 | 0.0132 | 3/12 |\n"
"| scale and misalignment alone, s=0.5 | 0.0132 | 5/12 |\n"
"| white noise alone, s=0.5 | 0.0132 | 7/12 |\n"
"| timestamp jitter alone, s=0.5 | 0.0132 | 7/12 |")
anchor = "**Tracking the bias recovers most of it.**"
rep(anchor, tbl2.strip() + "\n\n" + anchor)

# ---------- Section 7: drop duplicated decoder and front-end paragraphs ----------
i0 = s.index("# 7 Method")
i1 = s.index("# 8 Discussion")
sec7_new = (
"# 7 Implementation\n\n"
"**Interventions.** Every layer-2 intervention changes exactly one block: the pose source, the wrist channel, the clock "
"shift, the sensor error generator, the bias tracker, or the selection rule. Where a comparison touches two blocks we say "
"so in the text, and we do not report it as a single-variable effect. The decoder and the front end are described with the "
"layers that use them.\n\n"
"**Reproduction.** The repository records model metadata, commands and derived evaluations. The 016 matrix cache retains "
"aggregate per-room scores but does not retain all boxes, matches or pose traces. Counts and pairing can be recalculated "
"from rows, and independent centre-match verification requires replay of saved raw inputs. Local access to weights, "
"generated streams and real raw recordings is described separately from code availability.\n\n"
)
s = s[:i0] + sec7_new + s[i1:]

# ---------- Discussion: boundaries ----------
rep("The measurements concern controlled rectangular room families and declared protocols. The 803-room ProcTHOR test is a "
"separate transfer evaluation. Synthetic device records share a generation domain with supervised training. The primary "
"new-versus-old whole-room comparison on 32 records is not statistically significant. The twelve-room factorial diagnostic "
"repeats rooms and changes duration and noise realisation with budget. One reused real room provides no estimate of "
"cross-room generalisation. All reported rates retain their estimator and side-information conditions.",
"**What the numbers are not.** Five edges bound every rate above. The 10,000-room layer comes from one procedural family, "
"and only 43.6% of the separate ProcTHOR test set is rectangular, so the geometric results describe controlled single "
"rooms rather than apartments. The device layer uses 32 held-out synthetic records from the same generation domain as its "
"supervised training, and at that size a two-room gain is not significant under exact McNemar, which is why we pool "
"batches. Contacts are recovered at class level by a model trained on four handset carrying conditions, and no "
"cross-device or cross-carrier study exists yet. The twelve-room grid carries one realisation per cell and cannot separate "
"a contact effect from a noise draw. The real-room case is one reused development room, so it demonstrates that the "
"production chain runs end to end and not that it generalises. All reported rates therefore retain their estimator and "
"side-information conditions.")

# ---------- References ----------
s = s.rstrip() + ("\n\n[15] C. Chen, C. X. Lu, A. Markham, and N. Trigoni. IONet: Learning to cure the curse of drift in "
"inertial odometry. In AAAI Conference on Artificial Intelligence, 2018.\n\n"
"[16] V. Mollyn, K. Ahuja, D. Verma, C. Harrison, and M. Goel. SAMoSA: Sensing activities with motion and subsampled "
"audio. Proceedings of the ACM on Interactive, Mobile, Wearable and Ubiquitous Technologies, 6(3), 2022.\n")
rep("RoNIN established learned inertial odometry under real handset carrying conditions [6].",
"RoNIN established learned inertial odometry under real handset carrying conditions [6], and learned integrators such as "
"IONet target the same drift problem [15]. Wearable activity sensing with a phone alone has also been shown to transfer "
"across users [16].")

(C / 'manuscript_v5_023.md').write_text(s, encoding='utf-8')
print('ok', len(s.split(chr(10))))
