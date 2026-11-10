"""Split the decoder status from the outcome on the stored 324-row grid.

SUMMON separates "physically feasible", "plausible" and "correctly recovered".
The layout decoder already carries a status, so this module cross-tabulates
status against whole-room success over the three realisations of the visit by
severity grid. Counts only: no inference is re-run.
"""
import argparse
import collections
import json
from pathlib import Path


def load(root):
    rows = []
    for offset in (0, 1000, 2000):
        for path in sorted(Path(root).glob(f'off{offset}/*/multi-*/result.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            rows.append({'offset': offset, 'room': record.get('room'), 'visits': record.get('visits'),
                         'severity': record.get('severity'), 'status': record.get('status'),
                         'all_instances_hit': bool(record.get('all_instances_hit')), 'f1': record.get('f1')})
    return rows


def table(rows):
    out = collections.Counter((str(r['status']), r['all_instances_hit']) for r in rows)
    return {f'{k[0]}|{k[1]}': v for k, v in sorted(out.items())}


def main(root, output):
    rows = load(root)
    if not rows:
        raise SystemExit('no rows found under ' + root)
    ok = [r for r in rows if r['status'] == 'ok']
    hit = [r for r in rows if r['all_instances_hit']]
    summary = {'n': len(rows), 'status_ok': len(ok), 'hit': len(hit),
               'ok_and_hit': sum(1 for r in ok if r['all_instances_hit']),
               'ok_and_miss': sum(1 for r in ok if not r['all_instances_hit']),
               'not_ok_and_hit': sum(1 for r in rows if r['status'] != 'ok' and r['all_instances_hit']),
               'status_counts': dict(collections.Counter(str(r['status']) for r in rows)),
               'cross_tab': table(rows),
               'by_severity': {}}
    for severity in sorted({float(r['severity']) for r in rows}):
        sub = [r for r in rows if abs(float(r['severity']) - severity) < 1e-9]
        summary['by_severity'][f'{severity:g}'] = {
            'n': len(sub), 'status_ok': sum(1 for r in sub if r['status'] == 'ok'),
            'hit': sum(1 for r in sub if r['all_instances_hit']),
            'ok_and_miss': sum(1 for r in sub if r['status'] == 'ok' and not r['all_instances_hit'])}
    payload = {'protocol': {'root': str(root), 'source': 'stored result.json only, no inference'},
               'summary': summary, 'rows': rows}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=1), encoding='utf-8')
    print(json.dumps(summary, indent=1))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='output/layout-recon/matrix023')
    parser.add_argument('--out', default='output/layout-recon/status028/status028.json')
    a = parser.parse_args()
    main(a.root, a.out)
