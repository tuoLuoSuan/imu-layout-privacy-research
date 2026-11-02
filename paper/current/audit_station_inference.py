from pathlib import Path
import json,hashlib,itertools,math
import numpy as np
from scipy.stats import binomtest
P=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text('utf-8'))
def rate(n,d):return dict(numerator=int(n) if int(n)==n else float(n),denominator=int(d),value=float(n/d))
def holm(vals):
 ix=np.argsort(vals);out=np.zeros(len(vals));last=0.
 for rank,i in enumerate(ix):last=max(last,min(1,(len(vals)-rank)*vals[i]));out[i]=last
 return out.tolist()
d=load(P/'source-data/pilot-display.json');old=load(P/'source-data/pilot-audit.json');vis=d['feature_distances']['visits']
markers=sorted({v['declared_marker'] for v in vis});labels=np.array([markers.index(v['declared_marker']) for v in vis]);rounds=np.array([v['round'] for v in vis]);nn={}
for arm in ['phone','watch','joint']:
 a=np.array(d['feature_distances']['matrices'][arm],float);np.fill_diagonal(a,np.inf);ix=a.argmin(axis=1)
 ref=next(r for r in old['nn'] if r['arm']==arm)
 assert ix.tolist()==[r['neighbor'] for r in ref['nearest']],arm
 assert int(np.sum(labels[ix]==labels))==ref['declared_marker_accuracy']['numerator']
 assert all(np.count_nonzero(a[i]==a[i,ix[i]])==1 for i in range(16)),arm
 nn[arm]=ix
idx=[np.flatnonzero(rounds==r) for r in ['R1','R2']]
perms=[np.array(sorted(set(itertools.permutations(labels[ix].tolist()))),dtype=np.int8) for ix in idx]
assert [len(p) for p in perms]==[560,560]
lab=np.empty((560*560,16),np.int8);lab[:,idx[0]]=np.repeat(perms[0],560,axis=0);lab[:,idx[1]]=np.tile(perms[1],(560,1))
rows=[]
for arm in ['phone','watch','joint']:
 observed=int(np.sum(labels[nn[arm]]==labels));scores=np.sum(lab==lab[:,nn[arm]],axis=1);tail=int(np.sum(scores>=observed));counts=np.bincount(scores,minlength=17)
 rows.append(dict(arm=arm,observed=rate(observed,16),nearest=nn[arm].tolist(),null_distribution=[rate(int(n),len(lab)) for n in counts],null_mean=rate(float(scores.sum()),len(lab)*16),null_hit_quantiles95=np.quantile(scores,[.025,.975],method='inverted_cdf').tolist(),p_exact=rate(tail,len(lab)),binomial_independence_counterfactual_p=binomtest(observed,16,.225,alternative='greater').pvalue))
hp=holm([r['p_exact']['value'] for r in rows]);hb=holm([r['binomial_independence_counterfactual_p'] for r in rows])
for r,a,b in zip(rows,hp,hb):r['p_holm']=a;r['binomial_counterfactual_holm']=b
files=[P/'EXPLORATORY-PERMUTATION-PROTOCOL.md',P/'source-data/pilot-display.json',P/'source-data/pilot-audit.json',Path(__file__)]
out=dict(post_hoc=True,independent_observations_assumed=False,conditions='fixed directed neighbor graphs, declaration counts fixed separately within R1 and R2',permutations=len(lab),rows=rows,within_round_exchangeability='exploratory assumption; does not remove route/time/cue confounding',inputs=[dict(name=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files])
(P/'station-permutation-replay.json').write_bytes((json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
print(json.dumps([dict(arm=r['arm'],hits=r['observed']['numerator'],p=r['p_exact']['value'],holm=r['p_holm'],null_mean=r['null_mean']['value'],binomial=r['binomial_independence_counterfactual_p']) for r in rows],ensure_ascii=False))
