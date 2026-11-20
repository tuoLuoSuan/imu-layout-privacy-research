# Registered real-dorm example

This example starts with 128 walking points and five contacts exported from a 56.45 s dorm recording. The observation gives their room coordinates, the outline and the furniture list. The reference file gives the four measured footprints in meters. Credit the RoomTrace contributors and name this example when reporting results from it.

From the repository root, with the [pinned environment](../../README.md#reproduce-the-paper-table) installed:

```bash
python -m roomtrace download
python -m tools.replay_registered_layout --observation examples/registered-dorm/observation.json --reference examples/registered-dorm/reference.json --out output/registered-dorm.json
```

The expected result is four center matches within 0.5 m and a mean center error of **0.14264 m** (**0.143 m** in the paper). The decoder reads the observation and uses the archived five-contact route. The scorer reads the reference after decoding. [Reproduction guide](../../docs/roomtrace/paper-artifacts.md#registered-room-replay)

See [RoomTrace licensing](../../LICENSING.md) for the terms of the release assets.
