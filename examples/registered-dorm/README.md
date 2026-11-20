# Registered real-dorm example

This example contains the declared room outline and four-item inventory, 128 walking points and five class-labeled contacts registered in the room frame. The reference JSON gives the four ground-truth furniture footprints in meters. Credit the RoomTrace contributors and identify this registered example when reporting a result based on these files.

From the repository root, with the [pinned environment](../../README.md#reproduce-the-paper-table) installed:

```bash
python -m roomtrace download
python -m tools.replay_registered_layout --observation examples/registered-dorm/observation.json --reference examples/registered-dorm/reference.json --out output/registered-dorm.json
```

The expected result is four center matches within 0.5 m and a mean matched center error of **0.14264 m** (**0.143 m** in the paper). The decoder uses the archived five-contact route described in the [reproduction guide](../../docs/roomtrace/paper-artifacts.md#registered-room-replay). The observation is the decoder input. The reference is used after decoding to calculate errors.

The example begins at registered spatial evidence from the 56.45 s recording. Its files contain the declared room geometry and positions in the room coordinate frame. See [RoomTrace licensing](../../LICENSING.md) for the terms of the other release assets.
