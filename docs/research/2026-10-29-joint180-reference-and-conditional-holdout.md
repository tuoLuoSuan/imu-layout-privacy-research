# Joint 180-second capture: reference passes, conditional holdout completed

The new stationary echo reference passes the original frozen definition in all
seven prespecified four-second windows. No threshold, clustering distance or
window was relaxed. The earlier many-candidate diagnosis used a different
component grid, omitted the candidate height gate and analyzed longer windows.

| Visit | Unique / structurally valid frames | Multiple candidates |
|---|---:|---:|
| A1 | 39/39 | 0 |
| B1 | 32/38 | 0 |
| C1 | 38/40 | 0 |
| A2 | 38/38 | 0 |
| C2 | 40/40 | 0 |
| B2 | 40/40 | 0 |
| A3 | 39/39 | 0 |

The independent replay covers 1,778 point-cloud frames. The two held-out empty
windows have maximum novelty of approximately 0.02834% and 0.04169%, below the
original 0.1% gate. The original packed-key/union-find implementation separately
matches all 421 primary/empty frames in novelty, candidate counts and reported
centroids. A whole-window union is not substituted for framewise uniqueness.

## Same-session transport and fixed frontends

The complete phone/watch export passes its manifests, checksums, watch-block
CRCs and session linkage. It contains 29,224 accelerometer rows, 29,225 gyroscope
rows and 3,252 watch samples. The requested watch duration was 300 seconds; it
was manually stopped after approximately 213 seconds, while the phone recording
lasted approximately 247 seconds. Requested duration alone does not establish
or invalidate evaluation coverage.

Both previously fixed frontends process the same exported phone session with
the same frozen feature preparation: 4,918 windows each, no training and no
radar input. Only A1/B1 fit evaluation-side alignment; five later visits are held
out. Under an explicitly unverified equal-system-UTC interpretation:

| Frontend | Alignment | Conditional held-out echo RMS | Maximum |
|---|---|---:|---:|
| RoNIN | Rigid, nominal model scale | 0.3532 m | 0.4188 m |
| RoNIN | Positive similarity, scale fitted on A1/B1 | 0.4266 m | 0.6468 m |
| EqNIO | Rigid, nominal model scale | 1.1355 m | 1.3806 m |
| EqNIO | Positive similarity, scale fitted on A1/B1 | 1.6229 m | 2.3643 m |

These are conditional model-to-echo differences, not validated physical phone
position errors or an architecture-level ranking. Two-point similarity fit is
exactly determined; its zero training residual is not evidence of accuracy.
Echo centroids and pocket phones are different reference objects.

Nine clock scenarios from -3 to +3 seconds, three controls and two alignments
were fully retained for both frontends: 108 rows. The scenario range is not a
measured clock-error bound and no best offset is selected using held-out error.
Rigid RoNIN RMS spans 0.35318-0.35482 m and EqNIO spans 1.13398-1.14789 m in
these scenarios. An independent analytic two-point calculation matches all
reported holdout rows within 1.5e-14 m.

## Simulation and remaining evidence

The existing fixed four-region simulation is not waiting for another radar
recording. Its 1,152 conditions with 1,440 trials each were recounted, including
1,658,880 four-class posterior vectors and 648 frozen-core cross-checks. Metric
differences are below 3e-16 and core probability differences below 3e-15. Its
original near-chance stop condition remains; the noise grid was not extended.

Conditional simulations and observed holdout diagnostics can proceed together.
Neither the new RMS nor an earlier echo revisit difference is a validated
physical error bound or a directly interchangeable simulation epsilon.

The remaining timing link is an independently observed capture-time radar-host
to phone clock interval. Existing phone/watch software exchanges and a separate
computer/VM probe do not by themselves supply it. A later measurement cannot
retroactively certify that capture-time offset. Physical synchronization, phone
accuracy, room registration, true-room ranking and generalization remain
unvalidated. No additional human recording is requested by this update.

Raw recordings, per-frame spatial coordinates, device logs and authentication
configuration remain local. This repository update contains only this aggregate
report and its explicit source-admission entry.
