---
title: "What Inertial Recordings Reveal About Furniture Layout: Contact Placement, Visit Count, and Sensor Error"
---

# Abstract

We study how wearable activity reveals furniture positions when the room outline, start, inventory and nominal dimensions are known. A controlled evaluation separates ideal geometric evidence, acquisition from synthetic phone and watch streams, and a real-room case. Across 10,000 generated rooms, spatially dispersing contacts at a fixed walking route and fourteen interactions increases whole-room recovery from 39.78% to 64.70%. The paired gain is 24.92 percentage points, with a room-bootstrap 95% interval of [24.00, 25.84]. Mean room-level position F1 reaches 90.43%. Declared priors and decoder choices shift operating points on their separately evaluated room sets. On 32 held-out synthetic records, a same-generator-domain supervised dual-device chain achieves position F1 of 0.7275 and whole-room recovery in 17 records. The same decoder given only the declared outline, start and inventory recovers none of the 32 rooms. Replacing estimated pose with reference pose yields 26 successes under the same predicted actions, exposing pose-dependent downstream losses. A separate real-room production replay localises four objects with centre errors between 0.09 and 0.23 m. These measurements quantify how spatial contact placement changes conditional position disclosure and how device acquisition limits its recovery. Code repository https://github.com/tuoLuoSuan/imu-layout-privacy-research.

![How does activity distribution yield wearable evidence and position disclosure? Higher position F1 and whole-room counts indicate better results, and 72.75% and 17/32 summarise 32 synthetic records while the room, waveforms and hit icons are illustrative. The three datasets are scored separately, the watch provides contact and timing evidence, and physical clock synchronisation is unverified.](../figures/cvpr/figA_framework021.png){width=100%}

# 1 Introduction

Wearable inertial recordings contain traces of how people move around and interact with furniture. Walking constrains occupied space, sitting locates a seat region, and cabinet operation provides evidence about an accessible surface. Given room dimensions and an inventory, these observations can support estimates of furniture positions.

The privacy question that follows is quantitative. How much walking, and how many spatially distinct interactions, does an analyst need before furniture positions become identifiable? Existing work answers a neighbouring question. Walk2Map predicts floor plans, doors and furniture regions from learned trajectory-plan relationships [1]. CoGuide casts layout recovery as a spatial inverse problem and guides a diffusion model with a contrastive representation [2]. SUMMON synthesises objects that a captured motion plausibly contacted [3], and IMU4D estimates body motion and coarse scene structure from wearables [4]. These systems report whether recovery succeeds. CoGuide also varies trajectory density and noise. Our narrower comparison isolates contact placement at a fixed route and interaction count.

Activity count alone leaves the spatial distribution of observations unspecified. Repeated interactions at one location can provide different geometric evidence from the same number of spatially dispersed interactions. Reported recovery also depends on declared side information, the estimator and the quality of the acquired trajectory. We measure these factors on their corresponding evaluation sets.

We organise the evaluation into three evidence layers, each with its own fixed inputs, chain and denominator. The geometric layer measures recovery from ideal trajectories and class-level contact coordinates. The device layer evaluates generated six-axis phone and three-axis watch streams under same-domain supervision. The real-room case retains its original production chain.

A paired experiment isolates contact placement while keeping walking route, interaction count and decoder fixed. Conditional budget maps then show the recovery achieved at measured operating points. Device interventions evaluate the contribution of wrist evidence and sensitivity to temporal error structure. Finite-pool diagnostics distinguish retained individual candidates from joint compatibility and final selection.

# 2 Related work

**Layout from motion.** Walk2Map learns the relation between walked trajectories and floor plans and outputs room boundaries, doors and coarse furniture regions [1]. CoGuide treats the map as the latent variable of a spatial inverse problem and reports how recovery degrades as trajectories get sparser and noisier, which is the closest existing study to ours [2]. Both operate on trajectories given as input; neither isolates which part of a trajectory carries the layout evidence. SUMMON predicts human-object contact from motion and then synthesises a scene consistent with it, reporting separately whether a scene is physically feasible and whether it is correct [3]. We adopt that separation and report feasibility apart from accuracy.

**Wearable scene understanding.** IMU4D estimates body motion and coarse scene structure from wearable sensors [4]. IMU-HOI predicts probabilistic hand–object contact using IMUs attached to the body and interacting object [12]. Our phone-and-watch protocol evaluates furniture positions under declared side information, with no sensor attached to the furniture.

**Inertial navigation and action landmarks.** RoNIN established learned inertial odometry under real handset carrying conditions [6], and learned integrators such as IONet target the same drift problem [15]. Wearable activity sensing with a phone alone has also been shown to transfer across users [16]. ActionSLAM uses sitting, door opening and similar actions as landmarks that bound drift [5]. Our front end builds on the same idea, but the landmark content is not the object of study: we vary only how the landmarks are distributed in space. Collective landmark mapping shows that identical class labels from different people need not refer to the same instance, which motivates retaining uncertainty about event-to-instance association [13].

**Inertial privacy.** Prior work on inertial privacy asks whether gait, activity or location can be inferred from a stream. The question here is narrower and, we argue, more actionable: which furniture positions can be localised, given that the analyst already knows the outline and the item list.

# 3 Task and measurement

**Room and inventory.** Generated episodes contain four to seven target instances from bed, desk, storage and chair categories. The real room contains four scored objects and measures 2.84 by 4.045 m with a 2.09 m ceiling. Its door spans x = 0.437 to 1.212 m on the high-y wall and the known start is (0.825, 3.845) m. The analyst receives the outline, start, inventory and nominal dimensions. Positions, absolute heading and event-to-instance associations are inferred under declared room-family and interaction protocols.

**What is scored.** Predictions and references are matched one to one within category. A match is a position hit when its Euclidean centre error is at most 0.5 m. Whole-room centre recovery requires every instance to be hit with no extra or missing instances. Instance F1, decoder status and a separate endpoint requiring matched footprint IoU of at least 0.5 for every object are also reported.

**Three layers.** Layer 1 uses ideal trajectories and semantic contact coordinates. Layer 2 uses generated raw streams, a same-domain supervised segment-displacement model, phone activities, watch-only cabinet events, contact loops and finite decoding. Storage-wall trajectory repair is an additional arm used in later diagnostics. Layer 3 retains the original real-room RoNIN production chain and its declared room-specific geometry protocols. Chains, sets and denominators are reported separately.

**Statistics.** Independent rooms are the inferential units. Single-outcome room proportions use pointwise Wilson 95% intervals [11]. Binary paired comparisons use exact McNemar tests, with paired room-bootstrap intervals where specified. The replicated matrix contains twelve rooms, nine conditions and three handset-noise realisations per condition. Wrist streams remain fixed across repetitions of each room-condition pair. Simple effects use paired Wilcoxon tests on each room's success count from zero to three. Six simple-effect tests are exploratory, with Holm sensitivity results in the statistical addendum. A post-hoc difference-in-differences contrast compares the visit effect across severities zero and one. Its room-level sign-flip analysis assumes independent rooms and symmetric contrasts under the null. Recording duration remains coupled to visit count.

# 4 Layer 1: activity budget and contact placement

**Design.** The geometric layer evaluates 10,000 generated rooms and 55,000 target items. Figure 2 shows the same 43 measured budget cells as a heatmap and a three-dimensional point lattice. The contact-placement comparison retains walking route, decoder and fourteen interactions per room. Mean distinct contact coordinates are 4.0 with repeated placement and 10.5 with dispersed placement. Walking coverage is evaluated against reference free space and describes the experimental activity budget. Supplementary Table S1 reports the separate prior-enabled development configuration, and Supplementary Table S2 the prior-only control.

**Contact placement at fixed budget.** Under identical walking coverage and fourteen total interactions per room, repeated placement recovers 39.78% and dispersed placement 64.70%. The paired gain is 24.92 percentage points with room-level bootstrap 95% interval [24.00, 25.84]. Instance F1 for dispersed placement is 90.43%. Spatially separated contacts can exclude placements left compatible with one contact. The separate prior-enabled development grid gives 64.7% at 95%/14, 70.0% at 100%/8, 82.6% at 100%/14 and 85.1% at 100%/20. Four to seven correct positions are required simultaneously for the room endpoint.

**The budget is conditional.** A wall-property audit of 1,000 historical generated rooms finds all desks within 0.15 m of a wall and median gap 0.104 m. In the geometric development experiment, adding this declared property raises recovery from 651 to 826 on the same 1,000 rooms and desk recall from 75.87% to 87.27%. On 300 new same-family seeds, the rates are 66.0% and 84.0%. A separate 1,000-room confirmation set gives 851 hits for post64_wall40k and 945 for depth_portfolio, each with a maximum total budget of 40,000 nodes. The latter paired gain is 9.4 percentage points with bootstrap 95% interval [7.6, 11.3]. The prior and decoder comparisons retain separate room sets and conditions.

![How does position recovery vary across the measured activity budgets? Panel a gives room-macro position F1 for 43 measured cells, each retaining 10,000 controlled rooms with ideal trajectories, declared side information and the outline decoder. Hatching marks the five unmeasured cells. Panel b repeats the same values as a point lattice, where lines are reading guides and do not interpolate. The fixed-budget contact control is reported separately.](../figures/cvpr/fig_budget026.png){width=100%}

**Where the room family matters.** Of 25 exported iTHOR scenes, fifteen have the target categories and thirteen pass the geometry validity screen. The previous 11/11 operating point uses an additional restricted subset whose exclusions must be stated. The separate ProcTHOR transfer denominator already consists of 803 rectangular rooms. At 95% coverage and five interactions, 350 meet the centre endpoint (43.6%). This is a recovery rate within included rectangular rooms. The rectangular-room fraction is not estimated by 350/803.

# 5 Layer 2: what the devices actually deliver

**Frozen synthetic device chain.** The primary 32-record chain uses an ExtraTrees segment-displacement model with 300 trees, minimum leaf size two and 148 features, trained on 7,723 segments from historical rooms 0 to 19. Selection used records 11000 to 11007. Confirmation records 11100 to 11131 were excluded from selection. Phone activities, watch-only cabinet events, contact loops and directional finite decoding complete the chain. The raw records are synthetic and share the training generation domain. Later wall-repair and gyro-tracking arms are identified separately.

**Base rates.** Raw joint input gives 17/32 whole-room centre hits (53.13%, Wilson 95% [36.45, 69.13]) and mean room-level instance F1 0.7275. The older front end gives 11/32. The paired table is nine both hit, eight new-only hits, two old-only hits and thirteen both missed. The gain is 18.75 percentage points with paired bootstrap 95% [0, 37.5] and exact McNemar p = 0.1094. Removing the watch gives 9/32, with eight joint-only hits and no watch-absent-only hits (unadjusted diagnostic p = 0.0078). A ten-second watch shift gives 0/32. Ground-truth pose with the same predicted actions gives 26/32 and F1 0.9536. Its nine-room gain includes pose-dependent effects on refinement and finite decoding.

**What the declared priors alone recover.** The same directional decoder, candidate cap and support weight, fed only the room outline, start and inventory and given no signal, pose, walk point, contact, heading or event association, recovers 0 of 32 rooms with mean instance F1 0.0915. Against raw joint input the paired difference is seventeen rooms, with a paired room-bootstrap 95% interval of [34.4, 68.8] percentage points and exact McNemar p = 1.5e-5 (Supplementary Table S2). This is a control on one finite estimator, not a bound on what side information can achieve: holding the decoder fixed isolates what the inertial evidence contributes, not what an optimal prior-only solver would reach.

![How much does each same-set intervention change whole-room recovery? Points farther right indicate more recovered rooms relative to the corresponding baseline. Each row retains its own paired room set and denominator, with pointwise paired-room bootstrap 95% intervals.](../figures/cvpr/fig2_paired_contrasts021.png){width=100%}

**Prior placement on later batches.** On two additional synthetic batches, frozen011 recovers 21/32 and 20/32. Storage-wall trajectory correction gives 23/32 and 22/32, a pooled 41/64 to 45/64 change with exact McNemar p = 0.289. wall013 gives 22/32 and 21/32. Its filter constrains additional categories, includes a chair-distance condition and falls back when a pool becomes empty. The compared arms differ in prior content and implementation as well as placement. A matched-prior comparison is required to isolate placement alone.

**Sensor error.** We scale the handset error by a severity factor that multiplies white noise, adds a bias random walk, applies a scale and axis misalignment matrix and jitters the timestamps. Table 2 gives the ladder on twelve rooms. An RMS acceleration difference of 0.013 m/s^2, about 1.3 mg, already costs four of twelve rooms, and from severity 2 upward the front end fails on every room because the initial stationary segment is never detected. At severity 0.5 the four terms are not interchangeable: the bias walk alone reproduces the full collapse (3/12), scale and axis misalignment cost two rooms (5/12), whereas white noise and timestamp jitter alone leave the cell unchanged (7/12, identical room by room).

**Gated bias tracking recovers part of the loss.** The tracker estimates time-varying gyro bias offline and applies correction when drift exceeds 1.5 standard errors or the initial offset exceeds 0.006 rad/s. On the 32-record confirmation set, severity zero remains at 24/32. Severity 0.5 changes from 12/32 to 18/32 (p = 0.03125, Holm-adjusted p = 0.09375). Severity one changes from 3/32 to 14/32 (p = 0.0034, Holm-adjusted p = 0.0137), while severity two remains at 0/32. A second batch changes from 13/32 to 16/32 at severity 0.5. Across both batches, the net change is 25/64 to 34/64, with eleven gains and two losses (exact McNemar p = 0.0225). Unconditional correction also changes the clean condition from 10/12 to 8/12, while reaching 6/12 under slowly varying error.

: Table 2. Whole-room recovery against handset severity on the same twelve rooms, and single-term attribution at severity 0.5. Severity scales all four error terms together, so the row entries are not single-variable effects; the attribution rows apply one term at a time at severity 0.5. Their per-arm acceleration RMS values were not supplied in this table and are left unreported.

| Condition | Acceleration RMS difference (m/s^2) | Whole-room recovery |
|---|---|---|
| severity 0 | 0 | 7/12 |
| severity 0.5 | 0.0132 | 3/12 |
| severity 1.0 | 0.0315 | 1/12 |
| severity 2.0 | 0.0872 | 0/12 |
| bias walk alone, s=0.5 | — | 3/12 |
| scale and misalignment alone, s=0.5 | — | 5/12 |
| white noise alone, s=0.5 | — | 7/12 |
| timestamp jitter alone, s=0.5 | — | 7/12 |

**Equal RMS, different structure.** Holding the per-axis RMS fixed at 0.020 m/s^2 for acceleration and 0.003 rad/s for gyro, we apply white, constant-offset and slowly varying (integrated) errors on each channel and on both. Whole-room recovery over twelve rooms is 10/12 clean, 11/12 white gyro, 7/12 white acceleration, 7/12 white both, 8/12 constant gyro, 8/12 constant acceleration, 9/12 constant both, 0/12 slowly varying gyro, 8/12 slowly varying acceleration and 0/12 slowly varying both (Fig. 5). Slowly varying gyro error can prevent the frozen front end from identifying the required initial stationary block. The archived gate examples and their record-specific timings are reported separately. The path summaries 2.94 and 1.03 use different available-path subsets and different summary statistics. The gated tracker restores 5/12 and 4/12 in the two slowly varying-error conditions.

![How do visit count and handset error interact on the same twelve rooms? Each cell gives whole-room recovery as a percentage and as hits over 36 room-repetition observations. Cells are means of three handset-noise realisations, wrist streams are fixed across repetitions, and visit count also changes recording duration, so the grid supports an interaction rather than a device-level activity threshold.](../figures/cvpr/fig_visits026.png){width=100%}

**Replicated visit and handset-error conditions.** Twelve fixed rooms were evaluated at six, ten and fourteen visits and handset severity zero, 0.5 and one. Three handset-noise realisations give 36 observations per cell, with shared prefixes across visit budgets and fixed wrist streams across repetitions. Whole-room hits are 18/16/14, 21/20/12 and 23/21/11. Coverage remains 1.0. Increasing visits from six to fourteen changes mean success by +13.89 percentage points at severity zero and −8.33 points at severity one. A post-hoc room-level difference-in-differences contrast is −22.22 points (sign-flip p = 0.125). The observed ordering remains exploratory. Visit count changes both contact count and recording duration, leaving the individual contributions of contact accumulation and drift exposure unresolved. Mean position F1 at fourteen visits is 0.896 at severity zero and 0.402 at severity one.

**Repeated-noise protocol.** Per-channel random streams and an initial-sample bias reference preserve shared handset prefixes across visit budgets. The earlier legacy-versus-prefix comparison used two single-realisation grids. That historical comparison changed 33 of 108 room-condition outcomes, including eight at zero severity. It is separate from the current 324-episode replicated matrix. Full counts, simple-effect tests and generation details are reported in the statistical addendum.

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

**Scope of the evidence.** The 10,000 layouts come from one controlled procedural family. The separate ProcTHOR transfer evaluation recovers 350 of 803 included rectangular rooms, or 43.6%, at 95% coverage and five interactions. Synthetic device records share a generation domain with supervised training. The primary 32-record new-versus-old whole-room comparison has p = 0.1094. The replicated grid retains twelve independent rooms, fixed wrist signals and a duration-dependent visit protocol. A reused real room provides an existence case for its separate production chain. These conditions define the scope of the reported recovery rates.

The strongest intervention retains the walking route, interaction count and decoder while changing contact placement. Device diagnostics then measure how temporal error structure and finite decoding affect acquisition and use of that evidence. Matched-prior placement and duration-controlled, prefix-consistent budget experiments would isolate the mechanisms left coupled in current comparisons.

# 9 Conclusion

At a fixed route and fourteen interactions per room, dispersed contact placement increases whole-room recovery by 24.92 percentage points on the controlled generated family. Declared priors and finite decoding shift operating points on their respective evaluation sets. Raw dual-device input achieves position F1 of 0.7275 and 17/32 whole-room successes on same-domain synthetic records. A separate production replay localises four objects in one real room. The activity maps quantify conditional position disclosure, while device diagnostics show how imperfect acquisition and finite estimation constrain recovery. A general raw-IMU activity threshold remains unresolved.

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

[12] L. Lin, S. Xia, Z. Lai, L. Sun, J. Yang, and L. Pei. IMU-HOI: A symbiotic framework for coherent human-object interaction and motion capture via contact-conscious inertial fusion. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition, pages 42901–42910, 2026.

[13] R. Yonetani and K. Hara. Map as a by-product: Collective landmark mapping from IMU data and user-provided texts in situated tasks. PACM IMWUT, 9(3):146, 2025.

[14] R. G. Newcombe. Improved confidence intervals for the difference between binomial proportions based on paired data. Statistics in Medicine, 17:2635-2650, 1998.

[15] C. Chen, C. X. Lu, A. Markham, and N. Trigoni. IONet: Learning to cure the curse of drift in inertial odometry. In AAAI Conference on Artificial Intelligence, 2018.

[16] V. Mollyn, K. Ahuja, D. Verma, C. Harrison, and M. Goel. SAMoSA: Sensing activities with motion and subsampled audio. Proceedings of the ACM on Interactive, Mobile, Wearable and Ubiquitous Technologies, 6(3), 2022.
