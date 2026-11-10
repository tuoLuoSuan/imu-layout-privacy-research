"""Build main.tex v12 from v11: placement transfer, prior ceiling, new figures."""
import pathlib, sys

SRC = pathlib.Path('main.tex')
DST = pathlib.Path('../submission033/main.tex')
DST.parent.mkdir(parents=True, exist_ok=True)
text = SRC.read_text(encoding='utf-8')
n = 0

def rep(old, new):
    global text, n
    assert text.count(old) == 1, (text.count(old), old[:60])
    text = text.replace(old, new)
    n += 1

# ---------------------------------------------------------------- abstract
OLD_ABS = r'''We quantify how wearable activity discloses furniture positions under
known room outlines, starts, inventories and nominal dimensions.
Separate evaluations measure ideal geometric evidence, acquisition from
synthetic phone and watch IMUs, and real-room feasibility. Across 10,000
controlled layouts, spatially dispersing contacts at the same walking
route and fourteen interactions increases whole-room centre recovery
from 39.78\% to 64.70\%. The paired gain is 24.92 percentage points with
a room-bootstrap 95\% interval of {[}24.00, 25.84{]}, and mean
room-level instance-position F1 reaches 90.43\%. Declared priors and
finite decoding shift these operating points. A chain supervised within
the same generation family recovers 17/32 held-out synthetic records
with position F1 of 0.7275. The same finite decoder given only declared
side information recovers 0/32, repeated on a second 32-room batch.
Fixed-record contact-subset controls expose dependence on evidence
selection and downstream refinement. A separate production-chain replay
localises four objects in one real room with centre errors of 0.09--0.23
m. These measurements establish how contact placement affects
conditional position disclosure and identify acquisition and decoding
failures under stated protocols.'''

NEW_ABS = r'''We quantify how wearable activity discloses furniture positions under
known room outlines, starts, inventories and nominal dimensions.
Separate evaluations measure ideal geometric evidence, acquisition from
synthetic phone and watch IMUs, and real-room feasibility. Across 10,000
controlled layouts, dispersing contacts at the same walking route and
fourteen interactions raises whole-room centre recovery from 39.78\% to
64.70\%, a paired gain of 24.92 percentage points with a room-bootstrap
95\% interval of {[}24.00, 25.84{]} and a mean room-level
instance-position F1 of 90.43\%. The same intervention end-to-end through
noisy phone and wrist streams, trajectory refiners and a frozen decoder
reproduces on 64 rooms that no earlier arm uses: 48/64 against 30/64, a
gain of 28.12 points ({[}15.62, 40.62{]}, exact McNemar p = 1.2e-4).
Declared side information alone recovers 0/32 records, and an
independent sampler over 64,000 declared-only layouts over 32 rooms
reaches F1 0.088 with four exact rooms; selecting the best draw with
reference layouts raises F1 to 0.737 with 4/32 exact, while the inertial
chain reaches 0.801 with 21/32. Fixed-record subset controls show that
selection and refinement, not contact count alone, set the operating
point. A production replay localises four objects in one real room with
centre errors of 0.09--0.23 m. Contact placement is therefore a
first-order lever that survives the device chain, and declared priors
alone do not substitute for it.'''
rep(OLD_ABS, NEW_ABS)

# ---------------------------------------------------------------- introduction, third paragraph
OLD_INTRO = r'''The answer depends on the measurement protocol. In our controlled
geometric experiment, moving fourteen contacts from repeated to
dispersed locations changes whole-room recovery by 24.92 percentage
points. On separate evaluation sets, declared near-wall structure and
finite decoding also shift recovery at a given activity budget. These
measurements define conditional operating points for a scene family,
side-information package, interaction policy and decoder. Walking
coverage uses reference free space as its denominator, so these maps
describe controlled activity budgets and require additional evidence
before they can serve as a runtime stopping rule.'''

NEW_INTRO = r'''The answer depends on the measurement protocol. In our controlled
geometric experiment, moving fourteen contacts from repeated to
dispersed locations changes whole-room recovery by 24.92 percentage
points. We then rebuilt that intervention inside the device chain, with
identical rooms, route, fourteen contacts, sensor seeds, trajectory
refiners and decoder, and the placement protocol as the only difference.
On 64 rooms that no earlier arm uses, the effect persists at 48/64
against 30/64, a gain of 28.12 points, so the geometric lever is not an
artefact of ideal trajectories. A twelve-room development block, reported
separately, is too small to resolve a difference of that sign. Declared
near-wall structure and finite decoding also shift recovery at a given
activity budget, but declared priors alone do not reproduce it: across
64,000 sampled layouts the best attainable F1 is 0.088. These
measurements define conditional operating points for a scene family,
side-information package, interaction policy and decoder. Walking
coverage uses reference free space as its denominator, so these maps
describe controlled activity budgets and require additional evidence
before they can serve as a runtime stopping rule.'''
rep(OLD_INTRO, NEW_INTRO)

# ---------------------------------------------------------------- contributions
OLD_CON = r'''We contribute a paired contact-placement intervention over 10,000
controlled layouts, conditional budget maps retaining partial and
whole-room endpoints, and device controls separating acquisition,
feasibility and selection. The three layers retain separate chains and
denominators. Device training and testing use the same generation
family, and real-input feasibility uses one development room.'''
NEW_CON = r'''We contribute a paired contact-placement intervention over 10,000
controlled layouts, an end-to-end replication of that intervention on 64
unseen rooms of the device chain, conditional budget maps retaining
partial and whole-room endpoints, and device controls separating
acquisition, feasibility and selection. The three layers retain separate
chains and denominators. Device training and testing use the same
generation family, and real-input feasibility uses one development room.'''
rep(OLD_CON, NEW_CON)

# ---------------------------------------------------------------- figure 2
OLD_F2 = r'''\includegraphics[width=\textwidth]{../../figures/cvpr/fig_budget031.pdf}
\caption{Activity budgets determine different measured position-recovery levels
under a fixed geometric protocol. Panel a gives room-macro position F1,
and panel b shows the same 43 cells in depth, with higher values
indicating more recovered positions. Each measured cell retains 10,000
controlled rooms, five cells are unmeasured, and connecting lines guide
reading without interpolation.}'''
NEW_F2 = r'''\includegraphics[width=\textwidth]{../../figures/cvpr/fig_budget032.pdf}
\caption{Activity budgets set the operating level under a fixed geometric
protocol. Panel a gives room-macro position F1 for all 43 measured cells,
each resting on 10,000 controlled rooms, with hatching for the five
unmeasured cells. Panel b replots the full-coverage column against
interaction count, where three more interactions buy 3.3 points once
coverage is complete. Values are F1, not whole-room counts.}'''
rep(OLD_F2, NEW_F2)

# ---------------------------------------------------------------- new subsection: placement transfer
OLD_AFTER_TABLE = r'''\subsection{Evidence selection within fixed
recordings}\label{evidence-selection-within-fixed-recordings}'''
NEW_SUB = r'''\subsection{Placement transfers to the device
chain}\label{placement-transfers-to-the-device-chain}

The geometric intervention changes only where contacts land. We rebuilt
it inside the Layer-2 chain: identical room, route, fourteen contacts,
handset and wrist seeds, refiners and decoder, with the placement
protocol as the only difference. The twelve development rooms give 7/12
(mean F1 0.8135) for dispersed placement and 8/12 (0.8379) for repeated
placement, a difference of \$-\$8.33 points with exact McNemar p = 1.0.
At that size the block cannot resolve an effect of the geometric
magnitude. A fresh block of 64 rooms, which no earlier arm in this paper
reports on, separates the two protocols: dispersed placement recovers
48/64 (75.0\%, F1 0.9304) and repeated placement 30/64 (46.9\%,
0.8354). Twenty rooms succeed under dispersed placement only, against
two under repeated placement only, giving a paired gain of 28.12 points
with room-bootstrap 95\% interval {[}15.62, 40.62{]} and exact McNemar p
= 1.2e-4 (Fig. 3). Pooling all 76 rooms gives 55/76 against 38/76,
+22.37 points ({[}10.53, 34.21{]}, p = 9.1e-4). The sign and magnitude
match the geometric experiment, and the twelve-room block was
underpowered rather than contradictory. Both device blocks share one
finite chain, so this estimate is conditional on its acquisition and
refinement and does not establish transfer to another decoder.

\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{../../figures/cvpr/fig_placement033.pdf}
\caption{Contact placement transfers from the geometric protocol to the
device chain. Panel a gives paired room outcomes for 64 rooms under
dispersed and repeated placement with the same route, fourteen contacts,
seeds, refiners and decoder. Panel b compares the paired effect with the
10,000-room geometric experiment and with the twelve-room development
block, with room-bootstrap 95\% intervals. Dispersed placement gains 28.1
points on the fresh block and loses 8.3 points on the underpowered
twelve-room block.}
\end{figure*}

\subsection{Evidence selection within fixed
recordings}\label{evidence-selection-within-fixed-recordings}'''
rep(OLD_AFTER_TABLE, NEW_SUB)

# ---------------------------------------------------------------- figure 4
OLD_F4 = r'''\includegraphics[width=\textwidth]{../../figures/cvpr/fig_evidence_selection031.pdf}
\caption{Contact availability and contact selection affect a fixed inference
chain under different controls. Panel a reports whole-room success over
36 observations per cell from twelve rooms and three handset-noise
realisations, while panel b reports position F1 and whole-room counts
for one fixed record per room, with three random subsets and a
truth-assisted diagnostic. Higher scores indicate better recovery, wrist
streams remain fixed in panel a, and the exploratory interaction test
has p = 0.125.}'''
NEW_F4 = r'''\includegraphics[width=\textwidth]{../../figures/cvpr/fig_evidence032.pdf}
\caption{Contact availability and contact selection under different controls.
Panel a reports whole-room success over 36 observations per cell from
twelve rooms and three handset-noise realisations; the interaction is
exploratory, with p = 0.125. Panel b holds one record per room and varies
only which six contacts reach the refiners and decoder, against all
fourteen and against a truth-assisted diagnostic. Cells are success
counts, not F1.}'''
rep(OLD_F4, NEW_F4)

# hardcoded figure numbers after inserting placement as Fig. 3
rep('(Fig. 3a)', '(Fig. 4a)')
rep('(Fig. 3b)', '(Fig. 4b)')

# ---------------------------------------------------------------- prior ceiling
OLD_PRIOR = r'''68.8{]} percentage points and exact McNemar p = 1.5e-5. A second 32-room
set gives 0/32 and F1 0.0793, compared with its stored raw arm's 21/32
and 0.8013 (p = 9.5e-7). This post-hoc ablation retains one finite
estimator's candidate ordering and search behaviour. Evaluating stronger
side-information-only estimators remains necessary to quantify the
attainable disclosure from priors alone.'''
NEW_PRIOR = r'''68.8{]} percentage points and exact McNemar p = 1.5e-5. A second 32-room
set gives 0/32 and F1 0.0793, compared with its stored raw arm's 21/32
and 0.8013 (p = 9.5e-7). This post-hoc ablation retains one finite
estimator's candidate ordering and search behaviour.

\textbf{Limit of the estimator or of the priors?} An independent sampler
draws 2,000 layouts per room from the declared inventory, dimensions,
non-overlap, wall-clearance and support constraints, and reproduces the
ablation: F1 0.0878 with 4/64,000 exact recoveries over the same 32
rooms. The failure is therefore not specific to one decoder. Selecting
the best of the 2,000 draws per room with reference layouts gives F1
0.7371 and 4/32 exact rooms, and that ceiling falls as inventories grow:
0.950 for four items (4/5 rooms), 0.725 for five (0/13), 0.716 for six
(0/14) and 0.595 for seven (0/12). Above five items, 78,000 draws contain
no exact room (Fig. 5). Declared priors in this family support
approximate placement at best, and the inertial chain's 21/32 on the same
rooms is what supplies exactness. The ceiling belongs to one sampling
family rather than to all prior-only inference.'''
rep(OLD_PRIOR, NEW_PRIOR)

# ---------------------------------------------------------------- figure 5 (prior)
OLD_TABLE_ANCHOR = r'''\begin{table}[t]
\centering\small
\caption{Primary 32-record controls.'''
NEW_F5 = r'''\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{../../figures/cvpr/fig_prior033.pdf}
\caption{What declared side information can recover without inertial
evidence. Panel a compares one finite decoder fed only outline, start and
inventory with an independent 2,000-draw sampler on the same 32 rooms,
together with a sampler draw selected using reference layouts and the
inertial chain. Panel b reports that truth-assisted ceiling against
inventory size, where it drops from 0.950 at four items to 0.595 at
seven. Both panels share one room set and one declared input package.}
\end{figure*}

\begin{table}[t]
\centering\small
\caption{Primary 32-record controls.'''
rep(OLD_TABLE_ANCHOR, NEW_F5)

DST.write_text(text, encoding='utf-8')
print('replacements', n, 'lines', len(text.splitlines()))
