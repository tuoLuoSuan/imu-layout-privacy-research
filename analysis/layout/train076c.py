"""Training variant 076c: dense (soft-target) supervision and a packed-row cache.

The model, data contract and checkpoint format are unchanged; only the loss and
the cached feature packing differ, so eval076 can load these checkpoints.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import linear_sum_assignment

from .recovery076_data import CATEGORIES, dump, load_rows, pack, read, sha
from .recovery076c_model import EvidenceDecoder076c, decode, objective as objective_nll
from .recovery076_eval import aggregate, failed_score, score


def validation(model, rows):
    model.eval(); result = []
    with torch.inference_mode():
        for row in rows:
            s = row['sample']
            if s is None:
                r = failed_score()
            else:
                batch = pack([s]); r = score(decode(model(batch), batch)[0], row['truth'])
            result.append({'id': row['row']['id'], 'usable': s is not None, **r})
    return aggregate(result), result


def objective_soft(outputs, batch, truths, sigma=.35):
    """Dense cross-entropy against a Gaussian target over the candidate field."""
    logp = torch.log_softmax(outputs['energy'], -1)
    losses = []
    for b, truth in enumerate(truths):
        for category in range(4):
            slots = torch.where(batch['valid'][b] & (batch['category'][b] == category))[0]
            target = [box for name, box in truth.items() if name.split('#')[0] == CATEGORIES[category]]
            if len(target) != len(slots):
                raise ValueError('Inventory and training truth counts disagree')
            if not len(target):
                continue
            boxes = torch.as_tensor(np.asarray(target), dtype=logp.dtype)
            centre = (boxes[:, :2] + boxes[:, 2:]) / 2
            extent = boxes[:, 2:] - boxes[:, :2]
            xyz = batch['centres'][b, slots]
            size = batch['sizes'][b, slots]
            distance = (xyz[:, :, None] - centre[None, None]).square().sum(-1)
            distance = distance + .25 * (size[:, :, None] - extent[None, None]).square().sum(-1)
            distance = distance.masked_fill(~batch['candidate_valid'][b, slots, :, None], 1e6)
            cost = distance.amin(1).detach().cpu().numpy()
            row, col = linear_sum_assignment(cost)
            weight = torch.exp(-.5 * distance / sigma ** 2)
            weight = weight / weight.sum(1, keepdim=True).clamp(min=1e-9)
            paired = torch.stack([-(weight[s, :, i] * logp[b, slots[s]]).sum()
                                  for s, i in zip(row.tolist(), col.tolist())])
            losses.append(paired.mean())
    if not losses:
        raise ValueError('Empty target set')
    return torch.stack(losses).mean()


def cached_rows(manifest, grid, cache=None):
    path = Path(cache) if cache else Path(manifest).parent / ('packed-g%d.pt' % grid)
    key = {'manifest_sha256': sha(manifest), 'grid': grid}
    if path.exists():
        saved = torch.load(path, map_location='cpu', weights_only=False)
        if saved.get('key') == key:
            print(json.dumps({'cache': str(path), 'rows': len(saved['rows'])}), flush=True)
            return saved['rows']
    rows = load_rows(manifest, {'train', 'validation'}, grid)
    torch.save({'key': key, 'rows': rows}, path)
    print(json.dumps({'cache_written': str(path), 'rows': len(rows)}), flush=True)
    return rows


def main():
    p = argparse.ArgumentParser(); p.add_argument('--manifest', required=True); p.add_argument('--out', required=True)
    p.add_argument('--seed', type=int, default=7601); p.add_argument('--width', type=int, default=96)
    p.add_argument('--grid', type=int, default=24); p.add_argument('--epochs', type=int, default=40)
    p.add_argument('--batch-size', type=int, default=8); p.add_argument('--threads', type=int, default=8)
    p.add_argument('--validate-every', type=int, default=5); p.add_argument('--lr', type=float, default=.002)
    p.add_argument('--objective', choices=['soft', 'nll'], default='soft'); p.add_argument('--sigma', type=float, default=.35)
    p.add_argument('--cache', default=None); p.add_argument('--rotate', action='store_true')
    a = p.parse_args()
    if min(a.epochs, a.batch_size, a.threads, a.validate_every, a.width) < 1 or a.lr <= 0:
        p.error('Positive training settings required')
    out = Path(a.out); out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(a.threads); torch.manual_seed(a.seed); rng = np.random.default_rng(a.seed)
    rows = cached_rows(a.manifest, a.grid, a.cache)
    training = [r for r in rows if r['row']['split'] == 'train' and r['sample'] is not None]
    valid = [r for r in rows if r['row']['split'] == 'validation']
    if not training or not valid:
        raise ValueError('Nonempty explicit train/validation required; no fallback to test')
    protocol = {'args': vars(a), 'manifest_sha256': sha(a.manifest),
                'source_sha256': {f: sha(Path(__file__).with_name(f)) for f in
                                  ('train076c.py', 'recovery076c_model.py', 'recovery076_data.py',
                                   'recovery076_eval.py', 'recovery076_augment.py')},
                'training_ids': [r['row']['id'] for r in training],
                'validation_ids': [r['row']['id'] for r in valid],
                'selection': 'validation whole-room centre rate, then footprint, then F1, then earliest epoch'}
    dump(out / 'protocol.json', protocol)
    dump(out / 'architecture.json', {'model': 'EvidenceDecoder076', 'width': a.width, 'grid': a.grid,
                                     'objective': a.objective, 'sigma': a.sigma})
    model = EvidenceDecoder076c(a.width)
    optim = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optim, a.epochs)
    best = None; started = time.monotonic()
    with (out / 'epochs.jsonl').open('w', encoding='utf-8') as log:
        for epoch in range(1, a.epochs + 1):
            model.train(); total = 0.
            order = rng.permutation(len(training))
            for begin in range(0, len(training), a.batch_size):
                selected = [training[i] for i in order[begin:begin + a.batch_size]]
                batch = pack([r['sample'] for r in selected]); truths = [r['truth'] for r in selected]
                if a.rotate:
                    from .recovery076_augment import rotate_batch
                    batch, truths = rotate_batch(batch, truths, int(rng.integers(4)))
                optim.zero_grad(set_to_none=True)
                outputs = model(batch)
                loss = objective_soft(outputs, batch, truths, a.sigma) if a.objective == 'soft' \
                    else objective_nll(outputs, batch, truths)
                if not torch.isfinite(loss):
                    raise FloatingPointError('Nonfinite loss; no row discarded')
                loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 2.); optim.step()
                total += float(loss.detach()) * len(selected)
            scheduler.step()
            report = {'epoch': epoch, 'loss': total / len(training), 'elapsed_seconds': time.monotonic() - started}
            if epoch == 1 or epoch % a.validate_every == 0 or epoch == a.epochs:
                stats, details = validation(model, valid); report['validation'] = stats
                key = (stats['whole_room'], stats['whole_footprint'], stats['f1'])
                if best is None or key > best:
                    best = key
                    torch.save({'state_dict': model.state_dict(), 'width': a.width, 'grid': a.grid, 'epoch': epoch,
                                'seed': a.seed, 'manifest_sha256': sha(a.manifest), 'architecture': 'evidence076c-v1',
                                'source_sha256': protocol['source_sha256'],
                                'seen_groups': sorted({r['row']['group'] for r in rows}),
                                'seen_fingerprints': sorted({r['row']['fingerprint'] for r in rows}),
                                'scope': read(a.manifest)['protocol']['scope']}, out / 'best.pt')
                    dump(out / 'validation-best.json', {'epoch': epoch, 'summary': stats, 'rows': details})
            log.write(json.dumps(report) + '\n'); log.flush(); print(json.dumps(report), flush=True)
    dump(out / 'complete.json', {'status': 'training_completed', 'seconds': time.monotonic() - started,
                                 'test_evaluated': False, 'best_sha256': sha(out / 'best.pt')})


if __name__ == '__main__':
    main()