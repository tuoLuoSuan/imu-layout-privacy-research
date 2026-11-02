"""Reproduce all reported intervals from anonymized house-level source data."""
from pathlib import Path
import json,argparse
import numpy as np
def main(source,out):
 data=json.loads((source/'per-house-top1.json').read_text('utf-8'))
 refs=json.loads((source/'score-intervals.json').read_text('utf-8'))
 fam=np.array(data['families']);rng=np.random.default_rng(refs['seed'])
 draws=np.concatenate([rng.choice(np.flatnonzero(fam==f),size=(1000,100),replace=True) for f in data['family_order']],axis=1)
 rows=[]
 for row in refs['rows']:
  x=np.array(data['conditions'][row['condition']]);ci=np.quantile(x[draws].mean(axis=1),[.025,.975]);v=float(x.mean())
  assert np.max(abs(ci-row['house_bootstrap95']))<1e-12
  assert abs(v-row['rate']['value'])<1e-12
  rows.append(dict(condition=row['condition'],house_bootstrap95=ci.tolist(),rate=dict(numerator=float(x.sum()*4),denominator=2400,value=v)))
 report=dict(conditions=len(rows),houses=len(fam),routes_per_house=data['routes_per_house'],all_means_and_intervals_match=True,rows=rows)
 out.write_bytes((json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
 print('Reproduced',len(rows),'means and intervals; all match within 1e-12.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('out',type=Path);a=p.parse_args();main(a.source,a.out)
