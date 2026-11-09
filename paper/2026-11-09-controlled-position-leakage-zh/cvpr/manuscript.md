---
title: "What Inertial Recordings Reveal About Furniture Layout: Contact Placement, Visit Count, and Sensor Error"
---

# Abstract

Inertial recordings are now used to reconstruct the space a person walked through, but how much furniture layout such a recording actually leaks, and which property of the recording controls that leakage, is rarely measured. We treat layout recovery as a measurement instrument rather than a system to be demoed. Three layers share one frozen pipeline: 10,000 controlled single rooms with ideal trajectories and class-level contact coordinates, 32 held-out raw phone-plus-watch recordings together with four further batches of 32 for confirmation and sensory intervention, and one real dormitory room. With walking route and visit count fixed at fourteen contacts, replacing repeated contacts by dispersed ones raises whole-room recovery from 39.78% to 64.70% (+24.92 pp, paired). The budget is not a property of the room alone: the same 1,000 development rooms move from 65.1% to 82.6% when a declared desk-near-wall prior is added, and 1,000 fresh rooms move from 85.1% to 94.5% when the finite decoder is swapped. Raw recordings reach 17/32; the same predicted actions with ground-truth pose reach 26/32. A gated gyro-bias tracker recovers 12 to 18 of 32 at severity 0.5 and 3 to 14 at severity 1.0, and two batches pool to 25/64 becoming 34/64 (p=0.0225). At equal RMS, slowly varying gyro error removes all twelve rooms while equally large accelerometer error keeps eight. The single real room recovers four objects to 0.09-0.23 m, which we report as an existence case, not as validation.

![The task and the three evidence layers. (a) The single-room task: outline, start point and a five-item inventory with dimensions are known, while wall assignment, side and visiting order are not. (b), (c) Each bracket is scored on one room set; no arrow crosses two sets. The simulated layer uses an ideal trajectory with class-level contact coordinates, the device layer uses raw phone and watch streams, and the third layer reports metric error for four objects in one real room.](figures/cvpr/fig1_task_and_layers.png){width=100%}

# 1 Introduction

An inertial measurement unit is usually described as a sensor of the person wearing it. It also records the room. Corridors constrain walking, sitting exposes the region around a seat, and opening a cabinet door requires standing at one particular face. None of this needs a camera, and all of it can be turned into a furniture position by an analyst who already holds the motion data.

The privacy question that follows is quantitative. How much walking, and how many spatially distinct interactions, does an analyst need before furniture positions become identifiable? Existing work answers a neighbouring question. Walk2Map predicts floor plans, doors and furniture regions from learned trajectory-plan relationships [1]. CoGuide casts layout recovery as a spatial inverse problem and guides a diffusion model with a contrastive representation [2]. SUMMON synthesises objects that a captured motion plausibly contacted [3], and IMU4D estimates body motion and coarse scene structure from wearables [4]. These systems report whether recovery succeeds. They do not report how much activity it takes, because the amount of activity is not a variable they vary.

Three gaps make the phrase "enough activity" untestable in that literature. Activity is collapsed into a scalar such as duration or visit count, even though the same visit count can span very different regions of the room. The resulting budget is then quoted as if it belonged to the room, although it is computed with a particular prior and a particular estimator. And geometric sufficiency is not the same as what a device obtains: a contact that would pin a cabinet face in an ideal trajectory may not survive inertial drift, a wrist channel with a loose clock, or a candidate pool that truncates at 128 entries.

This paper separates the three. We fix one room family, one inventory protocol, one decoder and one scoring rule, then intervene on a single axis at a time and report paired counts. Layer 1 uses ideal trajectories and class-level contact coordinates in 10,000 generated single rooms to measure the geometric response to walking coverage and contact placement. Layer 2 feeds raw six-axis phone and three-axis watch streams into a frozen chain and intervenes on the trajectory front end, the wrist channel, the clock alignment, the sensor error and the selection rule. Layer 3 replays the original production chain in one real room.

The measurements support four statements. First, contact placement is an intervention that is independent of visit count: with route and visits held fixed, dispersion alone is worth +24.92 pp in whole-room recovery, and extra visits at fixed placement buy far less. Second, the budget point is conditional. A declared prior and a decoder portfolio move the same 1,000-room estimate by +17.5 pp and +9.4 pp, so a recovery rate quoted without its side information and its estimator is not reproducible. Third, geometric sufficiency and device acquisition differ by a measurable amount, and that difference is dominated by the temporal structure of the sensor error rather than by its RMS. Fourth, after the pool is shown to contain a near-truth candidate for every ground-truth instance, the remaining loss at severity zero sits in coverage and selection, not in proposal recall; seven selection criteria that we tried do not transfer across batches.


# 2 Related work

**Layout from motion.** Walk2Map learns the relation between walked trajectories and floor plans and outputs room boundaries, doors and coarse furniture regions [1]. CoGuide treats the map as the latent variable of a spatial inverse problem and reports how recovery degrades as trajectories get sparser and noisier, which is the closest existing study to ours [2]. Both operate on trajectories given as input; neither isolates which part of a trajectory carries the layout evidence. SUMMON predicts human-object contact from motion and then synthesises a scene consistent with it, reporting separately whether a scene is physically feasible and whether it is correct [3]. We adopt that separation and report feasibility apart from accuracy.

**Wearable scene understanding.** IMU4D estimates 4D human motion and coarse object layout from body-worn inertial sensors, mounting virtual sensors on the body with forward kinematics and adding noise [4]. IMU-HOI fuses contact with inertial motion capture and weights contact evidence over time [12]. Both make contact a modelling ingredient. We instead hold the model fixed and ask how much of the layout the contact pattern reveals as a function of where those contacts occur.

**Inertial navigation and action landmarks.** RoNIN established learned inertial odometry under real handset carrying conditions [6]. ActionSLAM uses sitting, door opening and similar actions as landmarks that bound drift [5]. Our front end builds on the same idea, but the landmark content is not the object of study: we vary only how the landmarks are distributed in space. Collective landmark mapping shows that identical class labels from different people need not refer to the same instance, which is the failure mode we avoid by keeping instance identity inside one recording [13].

**Inertial privacy.** Prior work on inertial privacy asks whether gait, activity or location can be inferred from a stream. The question here is narrower and, we argue, more actionable: which furniture positions can be localised, given that the analyst already knows the outline and the item list.

# 3 Task and measurement

**Room and inventory.** Every episode is one rectangular room drawn from a controlled generator. The production room, which also seeds the real recording, measures 2.84 by 4.045 m with a 2.09 m ceiling, a door on the high-y wall spanning x from 0.390 to 1.165 m, and a start point at (0.825, 3.845). An episode contains four classes and five instances: a bed (height 0.50 m), a desk (0.75), a cabinet (1.80) and a chair (0.45). The analyst is given the outline, the start point and the inventory with per-item dimensions. Wall assignment, side, and visiting order are withheld. This side-information split is what makes the task a layout-recovery problem rather than a room-shape problem.

**What is scored.** A room counts as recovered only when every instance is correct (whole-room recovery). An instance is correct when its predicted centre falls inside a tolerance window tied to the class, with the default window 0.5 m. We also report instance F1 over all predicted and ground-truth instances, feasibility (a solution was returned at all) and whole-room IoU at 0.5. Reporting feasibility separately matters: a decoder can return a feasible solution for all rooms and still be wrong in most of them, which is exactly the pattern SUMMON reports for a model without its contact loss [3].

**Three layers.** Layer 1 replaces the inertial front end by an ideal trajectory and gives contacts as class-level coordinates, so that only geometry is measured. Layer 2 uses the frozen production chain on raw streams: RoNIN-based displacement segments, contact-loop refinement, storage wall-gap refinement and a finite candidate decoder. Layer 3 replays one real room end to end. A layer is never pooled with another; each figure panel and each bracket names its own room set.

**Statistics.** Proportions carry Wilson intervals [11]. Paired changes are tested with the exact McNemar test on discordant rooms, and differences of paired proportions carry Newcombe hybrid-score intervals [14]. When we compare four severity levels at once we add a Holm correction and report both raw and corrected values. Bootstrap intervals are reported where the metric is a mean over instances rather than a count of rooms.

# 4 Layer 1: activity budget and contact placement

**Design.** The first layer generates 10,000 single rooms and 55,000 target items. Walking coverage is varied over a grid, and contact placement is varied at fixed coverage: in the repeated arm, the agent visits the same contact point on an object fourteen times; in the dispersed arm it visits fourteen distinct positions on the same object faces, with the same route length and the same number of interactions. Both arms are scored by the same decoder.

**Dispersion, not repetition.** Under identical coverage and fourteen visits, the repeated arm recovers 39.78% of rooms and the dispersed arm 64.70%, a paired gain of +24.92 pp with a 95% interval of 24.00 to 25.84 (10,000 rooms). Instance F1 rises to 90.43%. The mechanism is visible in the per-class numbers: repeated contact constrains a face but leaves the tangential position free, while a second contact at a different point on the same face resolves the remaining degree of freedom. Adding more visits at the same placement saturates quickly: the 95%/14 operating point is 64.7%, 100%/8 is 70.0%, 100%/14 is 82.6% and 100%/20 is 85.1% (Table 1). Four to seven objects must be correct simultaneously, so the whole-room metric is a conjunction and rises more slowly than any per-class recall.

: Table 1. Whole-room recovery on 1,000 development rooms at four operating points of the layer-1 decoder. Tolerance is the per-class centre window; contacts is the number of interactions per room.

| Operating point | Tol. (m) | Contacts | Whole-room (%) | Wilson 95% |
|---|---|---|---|---|
| 95%/14 | 0.14 | 14 | 64.7 | 61.7-67.6 |
| 100%/8 | 0.08 | 8 | 70.0 | - |
| 100%/14 | 0.14 | 14 | 82.6 | 80.1-84.8 |
| 100%/20 | 0.20 | 20 | 85.1 | - |

**The budget is conditional.** Two interventions move the same estimate without touching the recording. A declared desk-near-wall prior, measured on 5,500 items from 1,000 rooms where 100% of desks lie within 0.15 m of a wall and the median gap is 0.104 m, raises whole-room recovery on the same 1,000 rooms from 65.1% to 82.6% (+17.5 pp), and desk recall from 75.8% to 87.3%. On 300 external rooms the same prior lifts 66.0% to 84.0%. A decoder portfolio, which keeps the candidate limit fixed at 128 and picks among decoding strategies, lifts 1,000 fresh rooms from 85.1% to 94.5% (+9.4 pp, Wilson 92.91-95.75). Neither number is wrong; both are conditional. A recovery rate quoted as a property of "how much activity is needed" hides the prior and the estimator that produced it.

**Where the room family matters.** The controlled generator follows the iTHOR/ProcTHOR family [7, 8]. Of 25 candidate iTHOR rooms, 15 admit a four-class inventory and 13 pass a normality screen, leaving 11 rooms in the constrained set; all 11 reach the 95%/5 operating point, so the layer-1 conclusion is not an artefact of one room. In ProcTHOR, only 350 of 803 rooms (43.6%) are rectangular with a usable exterior outline, which bounds how far this family generalises: the fifth operating point of Table 1 belongs to the 11 iTHOR rooms, not to arbitrary apartments.

# 5 Layer 2: what the devices actually deliver

**Frozen chain.** The device layer runs the production pipeline unchanged: a learned displacement model on six-axis phone data, contact-loop refinement that closes revisit loops at cabinet doors and chairs, storage wall-gap refinement, and a finite candidate decoder that solves a per-instance axis-constrained coverage problem. Nothing in this chain is retrained for any experiment in this section. The recordings are 32 held-out long sessions with paired phone and watch streams; none participated in model selection.

**Base rates.** On those 32 recordings, whole-room recovery is 17/32 (53.13%, Wilson 36.45-69.13), with instance F1 0.7275. Removing the watch stream gives 9/32; shifting the wrist stream by 10 s gives 0/32. The wrist channel contributes, and a plausible-looking shift is enough to erase it. When the front end is replaced by ground-truth pose while the predicted actions are kept, recovery is 26/32 (81.25%) with F1 0.9536. The paired tables are 9 correct-only-new, 8 correct-only-old and 2 both-wrong for the raw comparison (+18.75 pp, p=0.1094) and 8 versus 0 for the desk-removal ablation (+25 pp, p=0.0078). The second comparison is the sharper one. Desks are the only class without a contact channel in the decoder, so removing them isolates trace accuracy from contact logic.

![Every lever is a same-set contrast. Each row keeps its own room set and its own denominator; intervals are Newcombe hybrid-score intervals on paired proportions.](figures/cvpr/fig2_paired_contrasts.png){width=68%}

**Two more batches, and a prior that helps only when it enters the trajectory.** Two further batches of 32 held-out recordings give 21/32 and 20/32 on the same chain, which puts the base rate in the low sixties and shows the first batch was not a lucky draw. A declared storage near-wall prior, applied as a trajectory residual rather than a candidate filter, moves them to 23/32 and 22/32; pooled over 64 recordings this is 64.06% against 70.31% (exact McNemar p=0.289). The same prior expressed as a candidate-set filter does not help: it costs 2 rooms on the pooled batches, and in the room where the two disagree the filtered arm keeps five correct boxes and replaces a near-truth storage box with one displaced by 3.07 m. All 396 ground-truth boxes in these batches satisfy the prior bound, so the loss is not a wrong prior; it is that an approximate but correct box inside a truncated candidate pool can be deleted before selection. Priors belong in the observation residual, where they can be outvoted, rather than in the admissible set, where they cannot.

**Sensor error.** We scale the handset error by a severity factor that multiplies white noise, adds a bias random walk, applies a scale and axis misalignment matrix and jitters the timestamps. On twelve rooms, severity 0 gives 7/12 whole-room recovery, 0.5 gives 3/12, 0.75 gives 2/12, 1.0 gives 1/12, and 2.0 or more fails in the front end for every room because the initial stationary segment is never detected. An RMS acceleration difference of 0.013 m/s^2, about 1.3 mg, is enough to lose four rooms out of twelve.

**Tracking the bias recovers most of it.** The front end estimates the gyro bias once, from the first stationary block, and never updates it. A tracker that re-estimates the bias offline and applies a correction only when drift exceeds 1.5 standard errors or the initial offset exceeds 0.006 rad/s leaves the clean cell untouched and recovers the perturbed cells. On a new batch of 32 rooms: severity 0 stays at 24/32, severity 0.5 moves from 12/32 to 18/32 (p=0.03125, Holm 0.09375), severity 1.0 moves from 3/32 to 14/32 (p=0.0034, Holm 0.0137), and severity 2.0 stays at 0/32. A second batch reproduces the direction (13 to 16 of 32), and pooling 64 rooms gives 25/64 to 34/64 (+14.06 pp, p=0.0225). The accelerator also carries handset bias, but correcting it unconditionally costs the clean cell: the version without gating drops from 10/12 to 8/12 while only lifting the slow-drift cell to 6/12.

**Equal RMS, different structure.** Holding the per-axis RMS fixed at 0.020 m/s^2 for acceleration and 0.003 rad/s for gyro, we apply white, constant-offset and slowly varying (integrated) errors on each channel and on both. Whole-room recovery over twelve rooms is 10/12 clean, 11/12 white gyro, 7/12 white acceleration, 7/12 white both, 8/12 constant gyro, 8/12 constant acceleration, 9/12 constant both, 0/12 slowly varying gyro, 8/12 slowly varying acceleration and 0/12 slowly varying both (Fig. 4). The slowly varying gyro arm destroys the recording before layout reasoning starts: the sliding mean square of the gyro signal never falls below the 0.009 rad/s stationarity gate, so the first acceptable stationary block moves from 0 s to 42.35 s and the pipeline raises "initial stable handset period required". Path length inflates to 2.94 times the truth in that arm and to 1.03 under the gated tracker, which restores 5/12 and 6/12 in the two slow-drift cells.

![Same RMS, three temporal structures, twelve rooms. Bars count recovered rooms; the three series are the frozen front end and two bias trackers.](figures/cvpr/fig4_error_spectra.png){width=68%}

**Budget against quality.** To test whether activity and evidence can be traded, we ran a 3 by 3 paired grid on twelve rooms: visits per room at 6, 10 and 14, crossed with sensor severity 0, 0.5 and 1, each cell regenerated independently. Route coverage is 1.0 in every cell, so what changes is repetition and contact count, not reachable space. Whole-room recovery is 7, 6, 3 for six visits; 7, 6, 6 for ten; and 8, 7, 4 for fourteen. Raising severity from 0 to 1 loses 11 rooms against 2 in the other direction (p=0.0225); raising visits from 6 to 14 gains 6 against 3 (p=0.508). Within this range, evidence quality is the larger lever, and the two axes do not compose into a smooth surface: the ten-visit, severity-1 cell beats the fourteen-visit one.

![Activity budget against evidence quality on twelve paired rooms. Cell values are recovered rooms out of twelve; marginals are percentage points.](figures/cvpr/fig3_budget_quality.png){width=68%}

**Where the residual loss sits.** With a read-only probe that records every candidate pool the joint search receives, we find that all 32 rooms contain, for every ground-truth instance, at least one candidate within 0.5 m of the truth. Restricting each instance domain to those near-truth candidates makes 28 rooms feasible and fully correct; the remaining four (11518, 11523, 11529, 11531) stay in conflict, two of them because 19 ground-truth targets are never covered by any near-truth candidate and two because the near-truth boxes are mutually incompatible under the non-overlap constraint. The ceiling of this hard-coverage formulation is therefore 28/32, while the frozen arm recovers 24/32. Allowing events to be dropped at a price makes all 32 rooms feasible and recovers 23, converting conflicts into feasible but wrong solutions. Seven selection criteria, applied to the same cached pools, do not replicate: the tight candidate limit of 64 is the only rule that gains on all three batches (25, 23 and 18 against 24, 23 and 17), while an ensemble over ten noisy decodings, a cross-cut agreement rule, a soft-coverage search, an interval residual, an in-band re-ranking and a priced prior each gain on one batch and lose or tie on another (Fig. 5). Pooled over 64 rooms the best rule reaches 49 against 47 (p=0.625). Selection is not where the remaining nine rooms are.

![Selection criteria on three batches of 32 rooms. Missing markers were not run on that batch; each batch keeps its own base rate.](figures/cvpr/fig5_selection_criteria.png){width=68%}

# 6 Layer 3: one real room

The production chain also runs on the single real room from which the generator was written: a dormitory room of 2.84 by 4.045 m with five items in four classes, recorded on a handset and a watch during a scripted walk with actions at the bed, desk, cabinet and chair. Replayed end to end, the chain places the four scored objects with centre errors of 0.1117 m (bed), 0.1079 m (desk), 0.0907 m (cabinet) and 0.2333 m (chair), at a global rotation of 170 degrees that the room frame cannot observe, with whole-room IoU 0.244. Seven software clock offsets of plus or minus 2 s all keep four of four objects within 0.25 m, so this room does not test synchronisation. We report it as an existence case: one room, one walk, one recording, no repetition and no cross-room validation.

![Four rooms, truth against prediction. Numbers are instance F1; annotations inside boxes are centre errors above 0.25 m. The four cases are all-correct, one displaced object, two wrong objects, and a room where no proposal survives.](figures/cvpr/fig6_qualitative_rooms.png){width=100%}

# 7 Method

**Decoder.** For each instance, the front end emits contact events with class labels and estimated positions. Each event defines an axis interval on the object, obtained by projecting the observation onto the instance frame and taking the per-axis intersection with intervals inferred from the outline and the inventory dimensions. Candidate placements are the boxes whose extent is compatible with every event they cover; a candidate scores by the total energy of the events it explains. The joint problem is a set-cover over events with a non-overlap compatibility constraint between instances, solved by a branch-and-bound search with a node limit of 20,000 and a candidate limit of 128 per instance. Search returns infeasible when a coverage constraint cannot be met, which we report as proposal conflict rather than as a wrong answer.

**Front end.** Phone six-axis and watch three-axis streams are resampled to a common clock, segmented into stationary and moving periods by a 0.4 s sliding window on acceleration variance, gyro magnitude and gravity norm, and integrated by the learned displacement model between stationary anchors. Contact loops close revisits at cabinet doors and chairs; the storage refinement applies the near-wall residual to the trajectory, not to the candidate set.

**Interventions.** Every layer-2 intervention changes exactly one block: the pose source, the wrist channel, the clock shift, the sensor error generator, the bias tracker, or the selection rule. Where a comparison touches two blocks we say so in the text, and we do not report it as a single-variable effect.

**Reproduction.** All numbers in this paper come from cached run records that store per-room boxes, per-arm scores and the exact command line. Layout tests (169) pass on the frozen tree; the code, the frozen checkpoints and the run records are listed in the repository.

# 8 Discussion

The measurements have clear edges. The 10,000 rooms come from one procedural family, and only 43.6% of ProcTHOR rooms are rectangular, so the geometry results describe controlled singles, not apartments. The device layer has 32 recordings per batch, which makes exact McNemar tests insensitive: a gain of two to three rooms is not significant, and we say so instead of pooling batches until it is. The single real room validates the plumbing, not the generalisation. Contact events are class-level and come from a model trained on four handset-carrying conditions; a cross-device or cross-carrier study is missing. And nothing here is a formal privacy guarantee: we measure recovery rates of a concrete estimator, which is weaker than a bound on what any estimator can do.

Within those edges, three practical consequences follow. A study that reports how much activity is needed should report the contact distribution and the side information that produced it, because both move the answer by more than the sensor improvement does. Sensor effort is better spent on the temporal structure of the error than on its RMS: a gated bias tracker that costs nothing on clean data recovers more rooms than a small reduction in white noise would. And priors should enter the observation residual, since in the admissible set they can remove the approximate but correct box that the search needed.

# 9 Conclusion

Furniture layout leaks through contact placement, and the amount of leakage depends on where the contacts fall, not only on how many there are. Measured on the same route and the same visit count, dispersion is worth +24.92 pp; measured on the same rooms, a declared prior and a decoder portfolio are worth +17.5 pp and +9.4 pp; measured on the same recordings, ground-truth pose is worth 9 rooms out of 32 and a gated gyro tracker 7. The three layers make the phrase "enough activity" conditional and checkable, and they show where the next gain has to come from: the nine rooms still lost at severity zero are lost in coverage and selection, not in the candidate pool.

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

[12] L. Lin, S. Xia, Z. Lai, L. Sun, J. Yang, and L. Pei. IMU-HOI: A symbiotic framework for coherent human-object interaction and motion capture via contact-conscious inertial fusion. In ICCV, 2025.

[13] R. Yonetani and K. Hara. Map as a by-product: Collective landmark mapping from IMU data and user-provided texts in situated tasks. PACM IMWUT, 9(3):146, 2025.

[14] R. G. Newcombe. Improved confidence intervals for the difference between binomial proportions based on paired data. Statistics in Medicine, 17:2635-2650, 1998.
