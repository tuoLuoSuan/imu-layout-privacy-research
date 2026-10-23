# Fixed-window development baseline v3

An explicitly exploratory companion to `paired_session`, not an alternate route
to its formal 16-session calibration contract.

`core.fixed_window` selects `[20,55)` seconds from **each device's recording
start**, using independently recorded metadata bounds. It preserves source times
and rejects unsupported records; it does not establish a shared clock or a task
phase. Whole-session statistics remain a reported comparator.

`fit_development` accepts exactly one balanced pair of two historical development
sessions. Its fixed L2 logistic recipe uses training-only mean and SD. A different
day's pair is predicted without passing labels to the predictor. Source SHA, ID,
and block overlap are rejected. Models are explicitly marked non-formal. This
tiny recipe can be extremely unstable when the two training points are close;
all probabilities and both leave-pair directions must be reported, not selected.

Outputs are development diagnostics even when sessions do not overlap: their
data, labels, and task design were already inspected. Existing duration and
reference failures are not retroactively accepted. Development Brier must not
replace the formal `phone_only_brier=null` or its independent ceiling check.

Run local counterexamples with:

```text
python -m unittest discover -s analysis/fixed_window_dev/tests -v
```

No device actions, new recordings, XGBoost, layout inference, or formal batch
release are provided by this module. Protocol details are in
`docs/protocols/2026-10-23-fixed-window-development-method-v3.md`.
