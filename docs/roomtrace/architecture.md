# From wearable activity to furniture layout

The decoder places one axis-aligned rectangle per item. It takes walking
points and class-labeled contacts in room coordinates, the declared room
rectangle, the furniture list with sizes, and a desk–chair relation flag.

## 1. Activity evidence

The phone records acceleration and angular velocity. The watch records
three-axis acceleration. The collection sources are in
[`collection/imu-capture-suite`](../../collection/imu-capture-suite).
[`action_features.py`](../../analysis/layout/action_features.py) and
[`action_model.py`](../../analysis/layout/action_model.py) expose the frozen
five-class phone random forest: walk, seated, lying, cabinet and other.
The model comes with its training metadata. The synthetic comparison starts
with the registered walking points and contact events that the recording
pipeline would supply.

## 2. Spatial and contact scores

The Walk-Space Prior uses six 64×64 channels: clipped nearest-walk distance,
observed-space mask and four category contact maps. Its five convolutional
blocks have widths 48/96/128/128/128; the output is a four-channel 24×24
residual. An eight-scalar metadata network accounts for room and object size.
The residual coefficient is fixed to one.

The contact kernel scores placements using the geometry of each activity.
A lying contact should fall inside a bed footprint. Opening a cabinet gives
evidence about its operating face, and sitting gives evidence about the chair
center. Walking penalizes obstructions. The calibrated candidate scorer and
spatial residual score the same candidate geometry.

## 3. Joint layout inference

For each item the search starts with 24×24 positions in each of two
orientations, or 1,152 candidates before it masks boxes outside the room.
It keeps 160 candidates per object
and a beam of 128. The two- and six-contact graph scorers use 41 node features,
eight edge features and two message-passing rounds. The 22→64→64→2 refiner
limits center displacement to half a candidate-grid step on each axis.

The decoder selects the route by counting the events in the input.

- K=0: calibrated local base + frozen spatial residual, joint search and the shared refiner.
- K>0: frozen contact-informed system D; the two-/six-contact heads activate at their matching counts.

Coverage, layout family, room IDs and reference boxes stay in the evaluation
files. The decoder has 528,064 parameters including frozen components. On one
desktop CPU thread, the archived median was 183 ms with the files and model
already loaded.

## 4. Exact implementation

Run the numbered modules through the commands in `roomtrace/`. The
checkpoints expect the original module bytes. See
`reproducibility/frozen088-lock.json` and the release hashes for the evaluated
configuration, and the [evaluation protocol](protocol.md) for confirmed results.
