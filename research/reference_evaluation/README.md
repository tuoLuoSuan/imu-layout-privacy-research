# Offline reference evaluation

Generic evaluator-side utilities for stationary echo references and conservative
candidate association. No raw recordings, body/room coordinates, device addresses,
deployment tools or model weights are included.

## Run

```sh
python -m pip install -r research/reference_evaluation/requirements.txt
python -m unittest discover -s research/reference_evaluation -p 'test_*.py' -v
python research/reference_evaluation/demo.py --output synthetic-demo.json
```

The demo is entirely synthetic and is never a device result. Dependencies are
NumPy and SciPy; no ROS or hardware connection is required.

## Contract

- Unique voxel coordinates and exact Chebyshev distance against a separate empty
  reference; 26-neighbor cell connectivity merges all points sharing a cell.
- Every qualifying component is retained. Ambiguity cannot be silently resolved
  by choosing the largest component. Missing observations are not interpolation.
- Clock/session identities and independent observed software anchor intervals
  are explicit. No first-frame alignment, extrapolation or trajectory-derived
  time fit. Piecewise-affine clock behavior remains a supplied assumption.
- Exactly two distinct visits may fit a positive 2D similarity; all other visits
  remain held out. Also report the rigid nominal-unit result. Two distinct point
  correspondences suffice for an orientation-preserving 2D similarity; a third
  off-line point is useful as a held-out geometry check, not a prerequisite to
  solving rotation.
- An echo centroid is a different reference object from a foot, body center or
  pocket phone. Software admission never asserts physical clock validation or
  absolute phone localization accuracy.

See the aggregate reference-readiness report under docs/research. This code does
not change the attacker's information set, classifiers or frozen capture tools.
