"""076c: identical local contact kernel, but the walking-clearance weight becomes
a learned, support-gated parameter so unobserved slots get their own prior.
No new input fields are introduced; the contract is unchanged.
"""
import torch
from torch import nn
from torch.nn import functional as F

from .recovery076_data import FIELDS, CATEGORIES
from .recovery076_model import decode, _iou, objective  # noqa: F401  (re-exported for eval)


class EvidenceDecoder076c(nn.Module):
    def __init__(self, width=96):
        super().__init__(); self.width = width
        self.kernel = nn.Sequential(nn.Linear(10, width), nn.SiLU(), nn.Linear(width, width),
                                    nn.SiLU(), nn.Linear(width, 5))
        nn.init.zeros_(self.kernel[-1].weight); nn.init.zeros_(self.kernel[-1].bias)

    def forward(self, batch):
        if set(batch) != set(FIELDS):
            raise ValueError('Unexpected model input fields')
        c, size = batch['centres'], batch['sizes']
        ev = batch['events']; category = batch['category']; valid = batch['valid']
        B, S, L, _ = c.shape; K = ev.shape[1]
        typ = F.one_hot(category, 4).to(c.dtype)[:, :, None].expand(-1, -1, K, -1)
        cls = ev[:, None, :, 2:5].expand(-1, S, -1, -1)
        dim = size[:, :, 0, None].expand(-1, -1, K, -1)
        spread = ev[:, None, :, 8:9].expand(-1, S, -1, -1)
        params = self.kernel(torch.cat([typ, cls, dim, spread], -1))
        offset = .75 * torch.tanh(params[..., :2])
        heading = ev[:, :, 5:7]; has = ev[:, :, 7:8]
        default = torch.zeros_like(heading); default[..., 0] = 1.
        axis = heading * has + default * (1 - has); side = torch.stack([-axis[..., 1], axis[..., 0]], -1)
        shift = offset[..., :1] * axis[:, None] + offset[..., 1:] * side[:, None]
        point = ev[:, None, :, 0:2] + shift
        delta = point[:, :, None] - c[:, :, :, None]
        absdelta = delta.abs(); half = size[:, :, :, None] / 2
        outside = (absdelta - half).clamp(min=0).norm(dim=-1)
        residual = torch.where(category[:, :, None, None] == 0, outside,
                   torch.where(category[:, :, None, None] == 1, (outside - .60).abs(),
                   torch.where(category[:, :, None, None] == 2, (outside - .40).abs(), delta.norm(dim=-1))))
        sigma = .06 + .34 * torch.sigmoid(params[..., 2]) + ev[:, None, :, 8].clamp(max=.5)
        score = -.5 * (residual / sigma[:, :, None]) ** 2
        forward = -(delta * axis[:, None, None]).sum(-1)
        directional = ((category == 1) | (category == 2))[:, :, None, None] * has[:, None, :, 0][:, :, None]
        score = score - directional * F.relu(-forward) / .20
        score = score + params[..., 3].clamp(-3, 3)[:, :, None]
        wanted = torch.tensor([1, 2, 0, 0], device=c.device)[category]
        compatible = (ev[:, :, 2:5].argmax(-1)[:, None] == wanted[:, :, None]) & batch['event_valid'][:, None]
        compatible = compatible & ((category != 2)[:, :, None] | batch['desk_relation'][:, None, None])
        compatible = compatible & valid[:, :, None]
        has_support = compatible.any(-1)
        masked = score.masked_fill(~compatible[:, :, None], -1e4)
        energy = torch.logsumexp(masked, -1) - compatible.sum(-1).clamp(min=1).log()[:, :, None]
        energy = torch.where(has_support[:, :, None], energy, torch.zeros_like(energy))
        learned = (4. * torch.sigmoid(params[..., 4])).mean(-1)
        clearance = torch.where(has_support, torch.full_like(learned, 6.), learned)
        energy = energy - clearance[:, :, None] * batch['walk_cost']
        energy = energy.masked_fill(~batch['candidate_valid'] & valid[:, :, None], -1e4)
        return {'log_prob': energy.log_softmax(-1), 'energy': energy, 'has_contact_support': has_support}
