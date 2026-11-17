"""083 lightweight CNN producing a zero-initialised residual over 24x24 candidate cells."""
import torch
from torch import nn


def _block(cin, cout, stride=1):
    return nn.Sequential(nn.Conv2d(cin, cout, 3, stride, 1), nn.GroupNorm(8, cout), nn.SiLU())


class SpatialResidual083(nn.Module):
    """fields (1,6,64,64) -> per-candidate residual; zero-initialised at construction."""

    def __init__(self, cells=24, width=(48, 96, 128, 128), scalars=8):
        super().__init__()
        c1, c2, c3, c4 = width
        self.trunk = nn.Sequential(
            _block(6, c1), _block(c1, c2, 2), _block(c2, c3, 2), _block(c3, c4), _block(c4, c4))
        self.head = nn.Conv2d(c4, 4, 1)
        nn.init.zeros_(self.head.weight); nn.init.zeros_(self.head.bias)
        self.scalar = nn.Sequential(nn.Linear(scalars, 64), nn.SiLU(), nn.Linear(64, 1))
        nn.init.zeros_(self.scalar[-1].weight); nn.init.zeros_(self.scalar[-1].bias)
        self.cells = cells

    def residual(self, fields, scal, cat_of, cell_of):
        z = self.trunk(fields)
        z = torch.nn.functional.adaptive_avg_pool2d(z, (self.cells, self.cells))
        m = self.head(z).reshape(4, self.cells * self.cells)
        idx = cat_of * (self.cells * self.cells) + cell_of
        return m.reshape(-1).gather(0, idx) + self.scalar(scal).reshape(-1)