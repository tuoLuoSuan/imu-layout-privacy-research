"""083 training: frozen 077 logits + zero-init spatial residual, 2,000 updates, one seed."""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
import numpy as np, torch
from torch import nn
from analysis.layout.recovery076_data import pack
from analysis.layout.eval077 import load_checkpoint as load077
from analysis.layout.recovery083_fields import fields, scalar_features, CATS
from analysis.layout.recovery083_model import SpatialResidual083

p = argparse.ArgumentParser()
p.add_argument('--steps', type=int, default=2000)
p.add_argument('--batch', type=int, default=4)
p.add_argument('--threads', type=int, default=12)
p.add_argument('--out', required=True)
p.add_argument('--seed', type=int, default=8301)
a = p.parse_args()
torch.manual_seed(a.seed); np.random.seed(a.seed); torch.set_num_threads(a.threads)

ROOT = Path('output/layout-recon')
rows = torch.load(ROOT/'recovery076/main400/packed-g24.pt', map_location='cpu', weights_only=False)['rows']
train = [r for r in rows if r['sample'] is not None and r['row']['split'] == 'train']
by_budget = {}
for r in train:
    by_budget.setdefault(int(r['row'].get('contacts_requested') or 0), []).append(r)
budgets = sorted(by_budget)
print(json.dumps({'train_cells': len(train), 'budgets': {k: len(v) for k, v in by_budget.items()}}), flush=True)
teacher, saved = load077(ROOT/'recovery077/main400-calibration/calibrated.pt')
strength = float(saved.get('score_strength', 1.))
model = SpatialResidual083(); opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
print(json.dumps({'params': sum(x.numel() for x in model.parameters())}), flush=True)


def cell_tensors(r):
    b = pack([r['sample']]); obs = r['sample']['observation']
    with torch.inference_mode():
        o = teacher(b, strength=strength)
    logp = (o['log_prob'][0] if 'log_prob' in o else o['energy'][0].log_softmax(-1)).detach()
    f = torch.from_numpy(fields(obs))[None]
    cats = b['category'][0].numpy(); valid = b['valid'][0].numpy(); cv = b['candidate_valid'][0].numpy()
    centres = b['centres'][0].numpy(); sizes = b['sizes'][0].numpy()
    w, h = obs['room']
    cell_ix = np.clip((centres[..., 0] / w * 24).astype(np.int64), 0, 23)
    cell_iy = np.clip((centres[..., 1] / h * 24).astype(np.int64), 0, 23)
    cell_of = cell_iy * 24 + cell_ix
    scal = np.stack([[scalar_features(obs, int(cats[s]), sizes[s, i]) for i in range(centres.shape[1])]
                     for s in range(len(cats))]).astype(np.float32)
    truth = {k: np.asarray(v, np.float32) for k, v in r['truth'].items()}
    return dict(b=b, obs=obs, logp=logp, f=f, cats=cats, valid=valid, cv=cv, centres=centres,
                sizes=sizes, cell_of=cell_of, scal=scal, truth=truth)


def labels(t):
    """one label per matched (slot, truth) pair; same-class one-to-one by centre distance."""
    out = []
    for cat in range(4):
        slots = [s for s in range(len(t['cats'])) if int(t['cats'][s]) == cat and bool(t['valid'][s])]
        keys = [k for k in sorted(t['truth']) if k.split('#')[0] == CATS[cat]]
        if not slots or not keys:
            continue
        tc = np.stack([[(t['truth'][k][0] + t['truth'][k][2]) / 2, (t['truth'][k][1] + t['truth'][k][3]) / 2] for k in keys])
        rep = []
        for s in slots:
            idx = np.flatnonzero(t['cv'][s])
            j = int(idx[int(np.argmax(t['logp'][s, idx].numpy()))])
            rep.append([t['centres'][s, j, 0], t['centres'][s, j, 1]])
        sc = np.stack(rep)
        cost = np.linalg.norm(sc[:, None, :] - tc[None, :, :], axis=-1)
        for _ in range(min(len(slots), len(keys))):
            i, j = np.unravel_index(np.argmin(cost), cost.shape)
            out.append((slots[i], keys[j])); cost[i, :] = 1e9; cost[:, j] = 1e9
    return out


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / max(ua, 1e-9)


def loss_cell(t):
    pairs = labels(t)
    if not pairs:
        return None
    total = 0.0; n = 0
    for slot, key in pairs:
        idx = np.flatnonzero(t['cv'][slot])
        if not len(idx):
            continue
        c = torch.from_numpy(np.stack([[t['centres'][slot, i, 0], t['centres'][slot, i, 1]] for i in idx]))
        s = torch.from_numpy(np.stack([t['sizes'][slot, i] for i in idx]))
        cat_of = torch.full((len(idx),), int(t['cats'][slot]), dtype=torch.long)
        cell_of = torch.from_numpy(t['cell_of'][slot, idx])
        scal = torch.from_numpy(t['scal'][slot, idx])
        res = model.residual(t['f'], scal, cat_of, cell_of)
        logits = t['logp'][slot, idx] + res
        tb = t['truth'][key]
        boxes = np.stack([[t['centres'][slot, i, 0]-t['sizes'][slot, i, 0]/2, t['centres'][slot, i, 1]-t['sizes'][slot, i, 1]/2,
                           t['centres'][slot, i, 0]+t['sizes'][slot, i, 0]/2, t['centres'][slot, i, 1]+t['sizes'][slot, i, 1]/2] for i in idx])
        ov = np.array([iou(bb, tb) for bb in boxes], np.float32)
        if ov.max() > 0:
            lab = int(np.argmax(ov))
        else:
            cc = np.stack([[(bb[0]+bb[2])/2, (bb[1]+bb[3])/2] for bb in boxes])
            tc = np.array([(tb[0]+tb[2])/2, (tb[1]+tb[3])/2])
            lab = int(np.argmin(np.linalg.norm(cc - tc, axis=1)))
        ce = nn.functional.cross_entropy(logits[None], torch.tensor([lab]))
        total = total + ce + 0.5 * (1.0 - float(ov[lab]))
        n += 1
    return total / max(n, 1)


t0 = time.monotonic(); history = []
for step in range(1, a.steps + 1):
    model.train(); opt.zero_grad()
    losses = []
    for _ in range(a.batch):
        budget = budgets[np.random.randint(len(budgets))]
        r = by_budget[budget][np.random.randint(len(by_budget[budget]))]
        t = cell_tensors(r)
        l = loss_cell(t)
        if l is not None:
            losses.append(l)
    if not losses:
        continue
    loss = torch.stack(losses).mean()
    loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5.0); opt.step()
    if step % 100 == 0:
        history.append({'step': step, 'loss': round(float(loss), 4), 'sec': round(time.monotonic()-t0, 1)})
        print(json.dumps(history[-1]), flush=True)
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
torch.save({'state_dict': model.state_dict(), 'seed': a.seed, 'steps': a.steps, 'history': history}, out/'model-083.pt')
(out/'config.json').write_text(json.dumps({'seed': a.seed, 'steps': a.steps, 'batch': a.batch, 'lr': 1e-3,
    'threads': a.threads, 'width': [48, 96, 128, 128], 'cells': 24, 'fields': 6, 'reach': 0.35,
    'sigma': 0.15, 'strength': strength, 'params': sum(x.numel() for x in model.parameters())}), encoding='utf-8')
print('DONE', flush=True)