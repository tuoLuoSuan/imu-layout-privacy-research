"""Shared publication style for the CVPR figures (top-venue defaults).

One palette, one type scale, one export helper.  Every figure module imports
this so the panels look like one paper instead of five.
"""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

INK = '#1F2A37'        # body text and axes
MUTED = '#6B7C8A'      # secondary text
GRID = '#DCE3E8'
PANEL = '#F7F9FA'

BLUE = '#2F6E9E'
AMBER = '#C98B2E'
GREEN = '#3F8F6B'
PURPLE = '#7E6BA8'
GREY = '#9AA5AD'

PALETTE = [BLUE, AMBER, GREEN, PURPLE, GREY]
CMAP = LinearSegmentedColormap.from_list(
    'paper_teal', ['#F2F7F8', '#C3DCDF', '#83B6BA', '#4A9297', '#0B6167'])

ROOT = Path('D:/Project/imu环境重建')
PAPER = ROOT / 'paper/2026-11-09-controlled-position-leakage-zh'
FIGDIR = PAPER / 'figures/cvpr'
DATA = PAPER / 'source-data/cvpr'


def use_style(size=7.0):
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': size,
        'axes.titlesize': size + 1.2,
        'axes.labelsize': size + .4,
        'xtick.labelsize': size,
        'ytick.labelsize': size,
        'legend.fontsize': size,
        'text.color': INK,
        'axes.labelcolor': INK,
        'axes.edgecolor': INK,
        'xtick.color': INK,
        'ytick.color': INK,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.linewidth': .6,
        'axes.grid': False,
        'grid.color': GRID,
        'grid.linewidth': .5,
        'legend.frameon': False,
        'pdf.fonttype': 42,
        'svg.fonttype': 'none',
        'figure.dpi': 120,
    })


def panel_label(ax, text, x=-.10, y=1.06, size=None):
    ax.text(x, y, text, transform=ax.transAxes, fontsize=size or plt.rcParams['font.size'] + 1.4,
            fontweight='bold', color=INK, va='bottom', ha='left')


def save(fig, stem, width_mm=None, height_mm=None):
    """Write pdf/svg/png(600)/tiff(lzw) next to the manuscript figures."""
    fig.set_size_inches(width_mm / 25.4, height_mm / 25.4)
    out = []
    for ext, kw in (('pdf', {}), ('svg', {}), ('png', {'dpi': 600}), ('tiff', {'dpi': 600,
                    'pil_kwargs': {'compression': 'tiff_lzw'}})):
        path = FIGDIR / f'{stem}.{ext}'
        fig.savefig(path, bbox_inches='tight', pad_inches=.02, **kw)
        out.append(path)
    return out
