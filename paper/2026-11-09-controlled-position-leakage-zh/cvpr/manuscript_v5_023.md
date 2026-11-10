---
title: "What Inertial Recordings Reveal About Furniture Layout: Contact Placement, Visit Count, and Sensor Error"
---

# Abstract

We measure how much furniture layout an inertial recording leaks when the room outline, start, inventory and nominal dimensions are already known, and which property of the recording controls that leakage. Three evidence layers share one frozen chain. In 10,000 controlled generated rooms with 55,000 target items, replacing repeated contacts by dispersed contacts at the same route and the same fourteen interactions per room raises whole-room centre recovery from 39.78% to 64.70%, a paired gain of 24.92 percentage points with 95% interval [24.00, 25.84]; instance position F1 reaches 90.43%. The budget is not a property of the room alone. On the same 1,000 development rooms a declared desk-wall prior moves recovery from 65.1% to 82.6%, and on a separate 1,000-room confirmation set a decoder portfolio moves it from 85.1% to 94.5%. On 32 raw phone-plus-watch records from a frozen supervised chain, 17 rooms are recovered; the same predicted actions with ground-truth pose recover 26, so pose accounts for a measurable part of the device-side loss. That loss is not set by error magnitude: at equal per-axis RMS the slowly varying gyro error removes all twelve rooms while white gyro error leaves eleven. A gated gyro-bias tracker recovers 12/32 to 18/32 rooms at severity 0.5 and 3/32 to 14/32 at severity 1.0, and 25/64 to 34/64 when both batches are pooled (p=0.0225), without touching the undisturbed cell. One real dormitory replay localises four objects with centre errors of 0.09 to 0.23 m. A twelve-room visit-by-severity grid does not identify either axis once noise prefixes are matched, so we report budgets only with their protocol. Code repository https://github.com/tuoLuoSuan/imu-layout-privacy-research.

![How does activity distribution yield wearable evidence and position disclosure? Higher position F1 and whole-room counts indicate better results, and 72.75% and 17/32 summarise 32 synthetic records while the room, waveforms and hit icons are illustrative. The three datasets are scored separately, the watch provides contact and timing evidence, and physical clock synchronisation is unverified.](../figures/cvpr/figA_framework021.png){width=100%}

# 1 Introduction

An inertial measurement unit is usually described as a sensor of the person wearing it. It also records the room. Corridors constrain walking, sitting exposes the region around a seat, and opening a cabinet door requires standing at one particular face. None of this needs a camera, and all of it can be turned into a furniture position by an analyst who already holds the motion data.

The privacy question that follows is quantitative. How much walking, and how many spatially distinct interactions, does an analyst need before furniture positions become identifiable? Existing work answers a neighbouring question. Walk2Map predicts floor plans, doors and furniture regions from learned trajectory-plan relationships [1]. CoGuide casts layout recovery as a spatial inverse problem and guides a diffusion model with a contrastive representation [2]. SUMMON synthesises objects that a captured motion plausibly contacted [3], and IMU4D estimates body motion and coarse scene structure from wearables [4]. These systems report whether recovery succeeds. CoGuide also varies trajectory density and noise. Our narrower comparison isolates contact placement at a fixed route and interaction count.

Three gaps make the phrase "enough activity" untestable in that literature. Activity is collapsed into a scalar such as duration or visit count, even though the same visit count can span very different regions of the room. The resulting budget is then quoted as if it belonged to the room, although it is computed with a particular prior and a particular estimator. And geometric sufficiency is not the same as what a device obtains: a contact that would pin a cabinet face in an ideal trajectory may not survive inertial drift, a wrist channel with a loose clock, or a candidate pool that truncates at 128 entries.

This paper separates the three. We fix one room family, one inventory protocol, one decoder and one scoring rule, then intervene on a single axis at a time and report paired counts. Layer 1 uses ideal trajectories and class-level contact coordinates in 10,000 generated single rooms to measure the geometric response to walking coverage and contact placement. Layer 2 feeds raw six-axis phone and three-axis watch streams into a frozen chain and intervenes on the trajectory front end, the wrist channel, the clock alignment, the sensor error and the selection rule. Layer 3 replays the original production chain in one real room.

The measurements support four statements, each on its own evidence layer. First, contact placement is an intervention in its own right: with route, visit count and decoder held fixed, dispersing contacts is worth 24.92 percentage points of whole-room recovery over 10,000 rooms. Second, the budget is conditional rather than intrinsic: a declared prior and a decoder portfolio are worth 17.5 and 9.4 percentage points on their own room sets, so a recovery rate quoted without its side information and estimator is not reproducible. Third, what a device obtains is separated from what geometry allows by a measurable amount, and that separation follows the temporal structure of the sensor error rather than its RMS: a gated gyro-bias tracker recovers nine of the thirty-nine perturbed rooms that the frozen chain loses when both batches are pooled. Fourth, once every instance has a near-truth candidate in the finite pool, the remaining loss at zero severity sits in joint coverage and selection, not in proposal recall.

# 2 Related work

**Layout from motion.** Walk2Map learns the relation between walked trajectories and floor plans and outputs room boundaries, doors and coarse furniture regions [1]. CoGuide treats the map as the latent variable of a spatial inverse problem and reports how recovery degrades as trajectories get sparser and noisier, which is the closest existing study to ours [2]. Both operate on trajectories given as input; neither isolates which part of a trajectory carries the layout evidence. SUMMON predicts human-object contact from motion and then synthesises a scene consistent with it, reporting separately whether a scene is physically feasible and whether it is correct [3]. We adopt that separation and report feasibility apart from accuracy.

**Wearable scene understanding.** IMU4D estimates 4D human motion and coarse object layout from body-worn inertial sensors, mounting virtual sensors on the body with forward kinematics and adding noise [4]. IMU-HOI fuses contact with inertial motion capture and weights contact evidence over time [12]. Both make contact a modelling ingredient. We instead hold the model fixed and ask how much of the layout the contact pattern reveals as a function of where those contacts occur.

**Inertial navigation and action landmarks.** RoNIN established learned inertial odometry under real handset carrying conditions [6], and learned integrators such as IONet target the same drift problem [15]. Wearable activity sensing with a phone alone has also been shown to transfer across users [16]. ActionSLAM uses sitting, door opening and similar actions as landmarks that bound drift [5]. Our front end builds on the same idea, but the landmark content is not the object of study: we vary only how the landmarks are distributed in space. Collective landmark mapping shows that identical class labels from different people need not refer to the same instance, which motivates retaining uncertainty about event-to-instance association [13].

**Inertial privacy.** Prior work on inertial privacy asks whether gait, activity or location can be inferred from a stream. The question here is narrower and, we argue, more actionable: which furniture positions can be localised, given that the analyst already knows the outline and the item list.

# 3 Task and measurement

**Room and inventory.** Generated episodes contain four to seven target instances from bed, desk, storage and chair categories. The real room contains four scored objects and measures 2.84 by 4.045 m with a 2.09 m ceiling. Its door spans x = 0.437 to 1.212 m on the high-y wall and the known start is (0.825, 3.845) m. The analyst receives the outline, start, inventory and nominal dimensions. Positions, absolute heading and event-to-instance associations are inferred under declared room-family and interaction protocols.

**What is scored.** Predictions and references are matched one to one within category. A match is a position hit when its Euclidean centre error is at most 0.5 m. Whole-room centre recovery requires every instance to be hit with no extra or missing instances. Instance F1, decoder status and a separate endpoint requiring matched footprint IoU of at least 0.5 for every object are also reported.

**Three layers.** Layer 1 uses ideal trajectories and semantic contact coordinates. Layer 2 uses generated raw streams, a same-domain supervised segment-displacement model, phone activities, watch-only cabinet events, contact loops and finite decoding. Storage-wall trajectory repair is an additional arm used in later diagnostics. Layer 3 retains the original real-room RoNIN production chain and its declared room-specific geometry protocols. Chains, sets and denominators are reported separately.

**Statistics.** Proportions use pointwise Wilson 95% intervals [11]. Paired two-condition binary comparisons use exact McNemar tests. Paired bootstrap intervals are used where per-room paired outcomes are available. The twelve-room matrix repeats nine conditions within each room. Combined axis contrasts first average within room, then use an exact room-cluster sign-flip sensitivity test assuming independent rooms and symmetric room-level contrasts under the null. Room-cluster percentile bootstrap intervals use 50,000 resamples. Matrix tests are exploratory. Visit changes also alter duration and noise realisation: at equal integer seeds the original generators draw different noise sequences for recordings of different length, so the grid was regenerated with matched prefixes before the axis contrasts were recomputed.

# 4 Layer 1: activity budget and contact placement

**Design.** The first layer evaluates 10,000 generated rooms and 55,000 target items. Figure 2 shows the same cells as a graded grid and as a three-dimensional surface. The contact-placement comparison retains the route, decoder and fourteen total interactions per room under the declared class/instance schedule. Mean distinct contact coordinates are 4.0 in the repeated arm and 10.5 in the dispersed arm. Supplementary Table S1 lists the four operating points of the budget-grid results, which use the separate development configuration with the declared desk-wall prior.

**Contact placement at fixed budget.** Under identical walking coverage and fourteen total interactions per room, repeated placement recovers 39.78% and dispersed placement 64.70%. The paired gain is 24.92 percentage points with room-level bootstrap 95% interval [24.00, 25.84]. Instance F1 for dispersed placement is 90.43%. Spatially separated contacts can exclude placements left compatible with one contact. The separate prior-enabled development grid gives 64.7% at 95%/14, 70.0% at 100%/8, 82.6% at 100%/14 and 85.1% at 100%/20. Four to seven correct positions are required simultaneously for the room endpoint.

**The budget is conditional.** A wall-property audit of 1,000 historical generated rooms finds all desks within 0.15 m of a wall and median gap 0.104 m. In the geometric development experiment, adding this declared property raises recovery from 651 to 826 on the same 1,000 rooms and desk recall from 75.87% to 87.27%. On 300 new same-family seeds, the rates are 66.0% and 84.0%. A separate 1,000-room confirmation set gives 851 hits for post64_wall40k and 945 for depth_portfolio, each with a maximum total budget of 40,000 nodes. The latter paired gain is 9.4 percentage points with bootstrap 95% interval [7.6, 11.3]. The prior and decoder comparisons retain separate room sets and conditions.

![What does each measured cell recover, and how do the 43 cells sit in depth? Higher values indicate more correct instance positions, hatched corners mark unmeasured cells, and the depth panel repeats the same cells without ticks. Each cell retains 10,000 controlled rooms with ideal trajectories and class-level contacts.](../figures/cvpr/figA1_activity_grid021.png){width=100%}

**Where the room family matters.** Of 25 exported iTHOR scenes, fifteen have the target categories and thirteen pass the geometry validity screen. The previous 11/11 operating point uses an additional restricted subset whose exclusions must be stated. The separate ProcTHOR transfer denominator already consists of 803 rectangular rooms. At 95% coverage and five interactions, 350 meet the centre endpoint (43.6%). This is a recovery rate within included rectangular rooms. The rectangular-room fraction is not estimated by 350/803.

# 5 Layer 2: what the devices actually deliver

**Frozen synthetic device chain.** The primary 32-record chain uses an ExtraTrees segment-displacement model with 300 trees, minimum leaf size two and 148 features, trained on 7,723 segments from historical rooms 0 to 19. Selection used records 11000 to 11007. Confirmation records 11100 to 11131 were excluded from selection. Phone activities, watch-only cabinet events, contact loops and directional finite decoding complete the chain. The raw records are synthetic and share the training generation domain. Later wall-repair and gyro-tracking arms are identified separately.

**Base rates.** Raw joint input gives 17/32 whole-room centre hits (53.13%, Wilson 95% [36.45, 69.13]) and mean room-level instance F1 0.7275. The older front end gives 11/32. The paired table is nine both hit, eight new-only hits, two old-only hits and thirteen both missed. The gain is 18.75 percentage points with paired bootstrap 95% [0, 37.5] and exact McNemar p = 0.1094. Removing the watch gives 9/32, with eight joint-only hits and no watch-absent-only hits (unadjusted diagnostic p = 0.0078). A ten-second watch shift gives 0/32. Ground-truth pose with the same predicted actions gives 26/32 and F1 0.9536. Its nine-room gain includes pose-dependent effects on refinement and finite decoding.

![How much does each same-set intervention change whole-room recovery? Points farther right indicate more recovered rooms relative to the corresponding baseline. Each row retains its own paired room set and denominator, with pointwise paired-room bootstrap 95% intervals.](../figures/cvpr/fig2_paired_contrasts021.png){width=100%}

**Prior placement on later batches.** On two additional synthetic batches, frozen011 recovers 21/32 and 20/32. Storage-wall trajectory correction gives 23/32 and 22/32, a pooled 41/64 to 45/64 change with exact McNemar p = 0.289. wall013 gives 22/32 and 21/32. Its filter constrains additional categories, includes a chair-distance condition and falls back when a pool becomes empty. The compared arms differ in prior content and implementation as well as placement. A matched-prior comparison is required to isolate placement alone.

**Sensor error.** We scale the handset error by a severity factor that multiplies white noise, adds a bias random walk, applies a scale and axis misalignment matrix and jitters the timestamps. Table 2 gives the ladder on twelve rooms. An RMS acceleration difference of 0.013 m/s^2, about 1.3 mg, already costs four of twelve rooms, and from severity 2 upward the front end fails on every room because the initial stationary segment is never detected. At severity 0.5 the four terms are not interchangeable: the bias walk alone reproduces the full collapse (3/12), scale and axis misalignment cost two rooms (5/12), whereas white noise and timestamp jitter alone leave the cell unchanged (7/12, identical room by room).

**Tracking the bias recovers most of it.** The front end estimates the gyro bias once, from reliable stationary samples throughout the record, and never updates it. A tracker that re-estimates the bias offline and applies a correction only when drift exceeds 1.5 standard errors or the initial offset exceeds 0.006 rad/s leaves the clean cell untouched and recovers the perturbed cells. On a new batch of 32 rooms: severity 0 stays at 24/32, severity 0.5 moves from 12/32 to 18/32 (p=0.03125, Holm 0.09375), severity 1.0 moves from 3/32 to 14/32 (p=0.0034, Holm 0.0137), and severity 2.0 stays at 0/32. A second batch reproduces the direction (13 to 16 of 32), and pooling 64 rooms gives 25/64 to 34/64 (+14.06 pp, p=0.0225). The accelerator also carries handset bias, but correcting it unconditionally costs the clean cell: the version without gating drops from 10/12 to 8/12 while only lifting the slow-drift cell to 6/12.

: Table 2. Whole-room recovery against handset severity on the same twelve rooms, and single-term attribution at severity 0.5. Severity scales all four error terms together, so the row entries are not single-variable effects; the attribution rows apply one term at a time at severity 0.5.

| Condition | Acceleration RMS difference (m/s^2) | Whole-room recovery |
|---|---|---|
| severity 0 | 0 | 7/12 |
| severity 0.5 | 0.0132 | 3/12 |
| severity 1.0 | 0.0315 | 1/12 |
| severity 2.0 | 0.0872 | 0/12 |
| bias walk alone, s=0.5 | 0.0132 | 3/12 |
| scale and misalignment alone, s=0.5 | 0.0132 | 5/12 |
| white noise alone, s=0.5 | 0.0132 | 7/12 |
| timestamp jitter alone, s=0.5 | 0.0132 | 7/12 |

**Equal RMS, different structure.** Holding the per-axis RMS fixed at 0.020 m/s^2 for acceleration and 0.003 rad/s for gyro, we apply white, constant-offset and slowly varying (integrated) errors on each channel and on both. Whole-room recovery over twelve rooms is 10/12 clean, 11/12 white gyro, 7/12 white acceleration, 7/12 white both, 8/12 constant gyro, 8/12 constant acceleration, 9/12 constant both, 0/12 slowly varying gyro, 8/12 slowly varying acceleration and 0/12 slowly varying both (Fig. 5). The slowly varying gyro arm destroys the recording before layout reasoning starts: the sliding gyro RMS never falls below the 0.009 rad/s stationarity gate, so the first acceptable stationary block moves from 0 s to 42.35 s and the pipeline raises "initial stable handset period required". Path length inflates to 2.94 times the truth in that arm and to 1.03 under the gated tracker, which restores 5/12 and 4/12 in the two slow-drift cells.

![What is observed in the nine visit-by-severity conditions? Larger counts indicate more whole-room hits within that cell. Each cell is one synthetic realisation on the same twelve rooms, with duration and error realisation also changing with visits, so the grid does not isolate either axis.](../figures/cvpr/fig3_budget_quality021_single.png){width=100%}

**Visits and quality at full coverage.** Twelve rooms were evaluated under all combinations of six, ten and fourteen visits and sensor severity 0, 0.5 and 1. Whole-room counts are 7/6/3, 7/6/6 and 8/7/4. Walking coverage remains 1.0. The within-room averaged severity-0 versus severity-1 contrast is +25.0 percentage points with room-cluster sign-flip p = 0.1328. The fourteen-versus-six contrast is +8.33 percentage points with p = 0.6563. Pooling the repeated conditions as 36 independent room pairs produces inappropriate p values. Record duration and common-prefix noise also change with visits despite equal integer seeds. The matrix therefore leaves the effect of repeated contacts coupled to these factors and establishes no device-level activity threshold.

**Matching the noise prefix reverses the axis.** The handset generator drew acceleration and gyro noise from one stream in recording order, and the perturbation model consumed randomness over the whole record and centred its bias walk on the record mean. A longer recording therefore changed the noise sequence that earlier samples received. Both are fixed by explicit options that separate the per-channel streams and anchor the bias walk at the first sample; with them enabled, the first 100 s of the six-, ten- and fourteen-visit recordings of a room agree to zero for acceleration, gyro and timestamps. Regenerating all 108 cells under the matched protocol gives whole-room counts of 4/5/7, 5/6/6 and 7/7/6. The severity contrast becomes -8.33 percentage points (room-cluster p = 0.625) and the visit contrast +11.11 percentage points (p = 0.406), so the ordering seen in the first run does not survive. Between the two protocols 33 of 108 cells change hit status, 8 of them at zero severity. Twelve rooms with one realisation per cell cannot separate a contact effect from the noise draw; we report the grid as a negative result and size the next batch on the realisation spread rather than on the first run axis slope.

![How do temporal structure and sensor channel affect recovery at equal nominal added RMS? Higher bars indicate more whole-room hits and absent bars denote unrun conditions. Conditions retain the same twelve synthetic records and the frozen counts for each front end.](../figures/cvpr/fig4_error_spectra021.png){width=100%}

**Residual loss and finite candidates.** A separate 32-room diagnostic batch contains at least one retained near-truth candidate for each reference instance. Restricting these finite domains using evaluation-time truth yields fully correct feasible solutions for 28/32 rooms, versus 24/32 for the deployed arm. Some restricted pools cannot cover predicted contact targets, while others contain incompatible boxes. This is a truth-assisted finite-pool diagnostic. Costly event deletion makes all rooms feasible but recovers 23. Candidate cap 64 gives 25/23/18 against 24/23/17 across three batches, including a tie on the middle batch. The reported paired 64-room comparison is 49 versus 47 with p = 0.625. Proposal recall, joint compatibility and selection remain distinct sources of loss.

![Do within-batch changes under selection criteria replicate across batches? More whole-room hits indicate better recovery within a batch, and a dash denotes an unrun condition. Each batch contains 32 records, with baselines of 24/32, 23/32 and 17/32 for A, B and C.](../figures/cvpr/fig5_selection_criteria021_single.png){width=100%}

# 6 Layer 3: one real room

The real-room evidence uses the original RoNIN and phone-activity production chain with its declared room-specific relations. Four scored centre errors are 0.1117 m for bed, 0.1079 m for desk, 0.0907 m for cabinet and 0.2333 m for chair. The solver selects a room registration of 170 degrees. IoU near 0.244 belongs to the chair object. A separate watch-driven cabinet replay retains four centre hits across seven software clock shifts within plus or minus two seconds. Physical clock synchronisation remains unaccepted. This reused development room provides a real-input feasibility case for its production chain.

![What does the real-room case establish, and how do synthetic records fail? Higher F1 and smaller centre errors indicate better position results, with 0.25 m controlling annotation and 0.5 m retained for matching. The real production replay is an n=1 existence case with unverified physical clock synchronisation, 0.244 is the chair IoU, and the four post-hoc synthetic examples use the frozen 32-record selection batch.](../figures/cvpr/figC_real_and_failures021.png){width=100%}

# 7 Implementation

**Interventions.** Every layer-2 intervention changes exactly one block: the pose source, the wrist channel, the clock shift, the sensor error generator, the bias tracker, or the selection rule. Where a comparison touches two blocks we say so in the text, and we do not report it as a single-variable effect. The decoder and the front end are described with the layers that use them.

**Reproduction.** The repository records model metadata, commands and derived evaluations. The 016 matrix cache retains aggregate per-room scores but does not retain all boxes, matches or pose traces. Counts and pairing can be recalculated from rows, and independent centre-match verification requires replay of saved raw inputs. Local access to weights, generated streams and real raw recordings is described separately from code availability.

# 8 Discussion

**What the numbers are not.** Five edges bound every rate above. The 10,000-room layer comes from one procedural family, and only 43.6% of the separate ProcTHOR test set is rectangular, so the geometric results describe controlled single rooms rather than apartments. The device layer uses 32 held-out synthetic records from the same generation domain as its supervised training, and at that size a two-room gain is not significant under exact McNemar, which is why we pool batches. Contacts are recovered at class level by a model trained on four handset carrying conditions, and no cross-device or cross-carrier study exists yet. The twelve-room grid carries one realisation per cell and cannot separate a contact effect from a noise draw. The real-room case is one reused development room, so it demonstrates that the production chain runs end to end and not that it generalises. All reported rates therefore retain their estimator and side-information conditions.

The strongest intervention retains the walking route, interaction count and decoder while changing contact placement. Device diagnostics then measure how temporal error structure and finite decoding affect acquisition and use of that evidence. Matched-prior placement and duration-controlled, prefix-consistent budget experiments would isolate the mechanisms left coupled in current comparisons.

# 9 Conclusion

At a fixed route and fourteen interactions per room, dispersed contact placement raises whole-room centre recovery by 24.92 percentage points on the declared generated family. Side information and finite decoding shift measured operating points on separately reported sets. Frozen raw dual-device input gives 17/32 on same-generator-domain synthetic records. A separate real production chain localises four objects in one room. Two protocols of the same grid disagree on the sign of the severity contrast, so no budget number is quoted without its protocol. A general raw-IMU activity threshold remains unresolved.

# References

[1] C. Mura, R. Pajarola, K. Schindler, and N. Mitra. Walk2Map: Extracting floor plans from indoor walk trajectories. Computer Graphics Forum, 40:375-388, 2021.

[2] S. Basu et al. Contrastive diffusion guidance for spatial inverse problems. arXiv:2509.26489v2, 2025.

[3] S. Ye, Y. Wang, J. Li, D. Park, C. K. Liu, H. Xu, and J. Wu. Scene synthesis from human motion. In SIGGRAPH Asia Conference Papers, 2022.

[4] H.-Y. Hsu, T. Cheng, J. Wen, A. G. Schwing, and S. Wang. IMU4D: 4D human-object understanding from wearable IMUs. arXiv:2604.21926v2, 2026.

[5] M. Hardegger, D. Roggen, S. Mazilu, and G. Troster. ActionSLAM: Using location-related actions as landmarks in pedestrian SLAM. In IPIN, 2012.

[6] S. Herath, H. Yan, and Y. Furukawa. RoNIN: Robust neural inertial navigation in the wild. In ICRA, pages 3146-3152, 2020.

[7] E. Kolve et al. AI2-THOR: An interactive 3D environment for visual AI. arXiv:1712.05474, 2017.

[8] M. Deitke et al. ProcTHOR: Large-scale embodied AI using procedural generation. arXiv:2206.06994, 2022.

[9] L. Breiman. Random forests. Machine Learning, 45:5-32, 2001.

[10] P. Geurts, D. Ernst, and L. Wehenkel. Extremely randomized trees. Machine Learning, 63:3-42, 2006.

[11] E. B. Wilson. Probable inference, the law of succession, and statistical inference. Journal of the American Statistical Association, 22:209-212, 1927.

[12] L. Lin, S. Xia, Z. Lai, L. Sun, J. Yang, and L. Pei. IMU-HOI: A symbiotic framework for coherent human-object interaction and motion capture via contact-conscious inertial fusion. Accepted CVPR version supplied locally. Year and proceedings metadata require verification.

[13] R. Yonetani and K. Hara. Map as a by-product: Collective landmark mapping from IMU data and user-provided texts in situated tasks. PACM IMWUT, 9(3):146, 2025.

[14] R. G. Newcombe. Improved confidence intervals for the difference between binomial proportions based on paired data. Statistics in Medicine, 17:2635-2650, 1998.

[15] C. Chen, C. X. Lu, A. Markham, and N. Trigoni. IONet: Learning to cure the curse of drift in inertial odometry. In AAAI Conference on Artificial Intelligence, 2018.

[16] V. Mollyn, K. Ahuja, D. Verma, C. Harrison, and M. Goel. SAMoSA: Sensing activities with motion and subsampled audio. Proceedings of the ACM on Interactive, Mobile, Wearable and Ubiquitous Technologies, 6(3), 2022.
