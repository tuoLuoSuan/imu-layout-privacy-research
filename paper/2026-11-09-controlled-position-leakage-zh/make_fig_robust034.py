"""Figure: the placement effect under decoder choice and sensor error, plus
the contact-budget curve.

Panel a plots the paired gain of dispersed over repeated placement with room
bootstrap intervals for four conditions.  Panel b plots whole-room recovery
against the contact budget with the class quota pinned, for the dispersed and
the random selection of the same size.

Sources
  output/layout-recon/placement034/paired034.json
  output/layout-recon/placement034b/paired64.json
  output/layout-recon/budget_curve034.json
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import figstyle032 as S

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent


def load(rel):
    return json.loads((REPO / rel).read_text())


def main(stacked=False):
    S.use_style(7.0)
    dec = load("output/layout-recon/placement034/paired034.json")["blocks"]
    sev = load("output/layout-recon/placement034b/paired64.json")
    curve = load("output/layout-recon/budget_curve034.json")["k"]

    fig = plt.figure()
    if stacked:
        ax_a = fig.add_axes([0.315, 0.590, 0.655, 0.310])
        ax_b = fig.add_axes([0.315, 0.180, 0.655, 0.310])
    else:
        ax_a = fig.add_axes([0.255, 0.27, 0.30, 0.62])
        ax_b = fig.add_axes([0.665, 0.27, 0.30, 0.62])

    rows = [
        ("base, cap 128", dec["base"]["fresh64"], S.BLUE),
        ("base, cap 64", dec["basec64"]["fresh64"], S.BLUE),
        ("priced, cap 64", dec["p10c64"]["fresh64"], S.BLUE),
        ("base, severity 0.5", sev, S.AMBER),
    ]
    y = np.arange(len(rows))[::-1]
    for yi, (label, block, colour) in zip(y, rows):
        delta = block["delta_pp"]
        lo, hi = block.get("boot", block.get("boot95"))
        ax_a.plot([lo, hi], [yi, yi], color=colour, lw=1.6, solid_capstyle='round')
        ax_a.plot([delta], [yi], 'o', color=colour, ms=5.2)
        ax_a.text(hi + 1.6, yi, f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}",
                  va='center', ha='left', fontsize=7.2, color=S.INK)
    ax_a.axvline(0, color=S.GREY, lw=.8, zorder=0)
    ax_a.set_yticks(y)
    ax_a.set_yticklabels([r[0] for r in rows], fontsize=7.2)
    ax_a.set_xlim(-6, 50)
    ax_a.set_xlabel("Dispersed minus repeated (percentage points)")
    ax_a.set_ylim(-.6, len(rows) - .4)
    ax_a.grid(axis='x', color=S.GRID, lw=.6)
    ax_a.set_axisbelow(True)
    for side in ('top', 'right'):
        ax_a.spines[side].set_visible(False)
    S.panel_label(ax_a, 'a', x=-.62 if not stacked else -.40, y=1.04)

    ks = sorted(int(k) for k in curve)
    disp = [curve[str(k)]["hits_disperse"] / curve[str(k)]["n_rooms"] * 100 for k in ks]
    rand = [curve[str(k)]["hits_random"] / curve[str(k)]["n_rooms"] * 100 for k in ks]
    ax_b.plot(ks, disp, '-o', color=S.BLUE, ms=4.4, lw=1.4, label='most spread')
    ax_b.plot(ks, rand, '-o', color=S.AMBER, ms=4.4, lw=1.4, label='at random')
    gap6 = disp[0] - rand[0]
    ax_b.annotate(f"{gap6:+.0f} pts", (6, (disp[0] + rand[0]) / 2), textcoords='offset points',
                  xytext=(16, 0), ha='left', fontsize=6.6, color=S.MUTED)
    ax_b.set_xticks(ks)
    ax_b.set_xlabel("Contacts kept per room")
    ax_b.set_ylabel("Whole-room recovery (%)")
    ax_b.set_ylim(28, 82)
    ax_b.legend(frameon=False, fontsize=6.8, loc='lower right', handlelength=1.4)
    ax_b.grid(axis='y', color=S.GRID, lw=.6)
    ax_b.set_axisbelow(True)
    for side in ('top', 'right'):
        ax_b.spines[side].set_visible(False)
    S.panel_label(ax_b, 'b', x=-.22 if not stacked else -.14, y=1.04)

    if stacked:
        fig.text(0.02, 0.055, "a: 64 fresh rooms, clean sensors unless marked; bars are 95% intervals.", fontsize=5.8, color=S.MUTED)
        fig.text(0.02, 0.022, "b: 76 rooms with the class quota pinned.", fontsize=5.8, color=S.MUTED)
        out = S.save(fig, 'fig_robust034_col', width_mm=88, height_mm=116)
    else:
        fig.text(0.01, 0.075,
                 "a, 64 fresh rooms, 14 contacts, sensors clean unless marked; bars are room-bootstrap 95% intervals.",
                 fontsize=6.3, color=S.MUTED)
        fig.text(0.01, 0.022,
                 "b, 76 rooms with the class quota pinned; the two curves meet once every contact is kept.",
                 fontsize=6.3, color=S.MUTED)
        out = S.save(fig, 'fig_robust034', width_mm=174, height_mm=62)
    print(out)


if __name__ == '__main__':
    import sys
    main(stacked='stacked' in sys.argv)
