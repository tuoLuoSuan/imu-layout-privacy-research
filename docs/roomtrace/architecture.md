# From wearable activity to furniture layout

RoomTrace consumes registered walking positions, class-labeled contact events,
the declared rectangular outline, furniture categories/dimensions and the
declared desk–chair relation. Its output is one axis-aligned rectangle per item.

## 1. Activity evidence

The phone contributes acceleration and angular velocity; the watch supplies
three-axis acceleration. The collection sources are in
[`collection/imu-capture-suite`](../../collection/imu-capture-suite).
[`action_features.py`](../../analysis/layout/action_features.py) and
[`action_model.py`](../../analysis/layout/action_model.py) expose the frozen
five-class phone random forest: walk, seated, lying, cabinet and other.
Its training metadata accompany the distributed model. Activity timing,
odometry and registration form the evidence interface; the synthetic layout
comparison starts at that interface.

## 2. Spatial and contact scores

The Walk-Space Prior uses six 64×64 channels: clipped nearest-walk distance,
observed-space mask and four category contact maps. Its five convolutional
blocks have widths 48/96/128/128/128; the output is a four-channel 24×24
residual. An eight-scalar metadata network accounts for room and object size.
The residual coefficient is fixed to one.

The contact kernel represents activity geometry: lying lies inside a bed
footprint, a cabinet event supports an operating face, and sitting supports a
chair center. Walking adds a free-space exclusion cost. Candidate calibration
and the spatial residual use the same room-wide candidate geometry.

## 3. Joint layout inference

Each object has 24×24 translations and two extent orientations: 1,152
candidates before boundary masking. Search retains 160 candidates per object
and a beam of 128. The two- and six-contact graph scorers use 41 node features,
eight edge features and two message-passing rounds. The 22→64→64→2 refiner
limits center displacement to half a candidate-grid step on each axis.

The deployed router reads the **actual event count**:

- K=0: calibrated local base + frozen spatial residual, joint search and the shared refiner.
- K>0: frozen contact-informed system D; the two-/six-contact heads activate at their matching counts.

True coverage, layout family, room identifiers and evaluation targets never
select the route. The module count is 528,064 parameters, including frozen
components. The archived 183 ms median is desktop single-thread CPU decoder
latency, excluding file I/O and model loading.

## 4. Exact implementation

The release preserves the original numbered scientific modules because their
bytes are bound to the checkpoint protocols. `roomtrace/` provides portable
commands around these implementations. `reproducibility/frozen088-lock.json`
and the release hashes identify the evaluated configuration. Historical scope
strings inside frozen source files reflect their creation date; the confirmed
results and operating regime are documented in this directory.
