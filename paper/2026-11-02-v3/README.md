# Manuscript v3: figures and reproducible source data

Current manuscript: [paper.md](paper.md). This version has seven redesigned figure plates, an explicit threat model, separate limitations and conclusions, and 44 verified bibliographic records. Chinese and English vector figures carry identical data.

The main action display is the native T3 eight-class task, 67/71 (94.37%). Historical nine-class confirmation and same-T second-look evaluations remain separate. The 52.46% identity result assumes supplied coordinates, true grouping, a specified Brownian process and a closed catalog. It is not a measured real-room ranking.

## Reproduce

Install NumPy and Matplotlib in your own Python environment. Run `python build_figures.py --language en` or `--language zh`. Run `python reproduce_intervals.py source-data intervals.json` to reproduce all 27 frozen-score means and house-bootstrap intervals. No raw recordings or model fitting are required for these steps.

`audit_station_inference.py` additionally needs SciPy; it reproduces the exploratory exact within-round label-allocation audit. The portable copy adjusts only the source-data directory. The fixed nearest-neighbor graph and output statistics remain unchanged. Full counts and the protocol are supplied.

## Version and scope

Repository: https://github.com/tuoLuoSuan/imu-layout-privacy-research

Manuscript snapshot: `paper-figures-v3-20261102`. Current PDF/DOCX and vector assets are attached to that prerelease. The repository is public by the author's instruction. Raw video, phone/watch exports, LiDAR bags, model weights and signing material are not distributed.

Saved-score aggregation, original-record replay and figure redraws are different scopes. The supplementary source binds historical results to their original audit records; a portable replot is not an independent rerun of every attack matcher. Human author and institutional details remain to be finalized before submission.
