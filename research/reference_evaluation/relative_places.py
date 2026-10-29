"""Relative-place ranking. Scoring never receives site identities or room pose."""
import itertools
import numpy as np

TOL=1e-12


def same_pair_labels(labels):
    labels=np.asarray(labels)
    i,j=np.triu_indices(len(labels),1)
    return labels[i]==labels[j]


def score_positions(points):
    p=np.asarray(points,float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<3 or not np.isfinite(p).all():
        raise ValueError('At least three finite unaligned XY event points required')
    d=np.linalg.norm(p[:,None,:]-p[None,:,:],axis=2)
    i,j=np.triu_indices(len(p),1)
    norm=float(np.sqrt(np.mean(d[i,j]**2)))
    normalized=d/norm if norm>0 else np.zeros_like(d)
    previous=[[]]
    for k in range(1,len(p)):
        # Tie tolerance must not depend on coordinates of a later visit.
        v=d[k,:k]
        history_scale=float(np.sqrt(np.mean(v*v)))
        v=v/history_scale if history_scale>0 else np.zeros_like(v)
        previous.append(np.flatnonzero(np.isclose(v,v.min(),atol=TOL,rtol=0)).tolist())
    return dict(pair_indices=np.c_[i,j],pair_scores=-normalized[i,j],normalized_distances=normalized,
                nearest_prior_ties=previous,predicted_site_count=None)


def auc(scores,positive):
    scores=np.asarray(scores,float);positive=np.asarray(positive,bool)
    if scores.ndim!=1 or positive.shape!=scores.shape or not np.isfinite(scores).all():
        raise ValueError('Matching finite pair scores and binary references required')
    a,b=scores[positive],scores[~positive]
    if not len(a) or not len(b):return None
    delta=a[:,None]-b[None,:]
    return float(np.mean((delta>TOL)+.5*np.isclose(delta,0,atol=TOL,rtol=0)))


def average_precision(scores,positive):
    scores=np.asarray(scores,float);positive=np.asarray(positive,bool)
    if not np.count_nonzero(positive):return None
    order=np.argsort(-scores,kind='stable');s=scores[order];p=positive[order]
    total=int(p.sum());tp=0;seen=0;result=0.;k=0
    while k<len(s):
        end=k+1
        while end<len(s) and abs(s[end]-s[k])<=TOL:end+=1
        new=int(p[k:end].sum());tp+=new;seen+=end-k
        result+=(new/total)*(tp/seen);k=end
    return float(result)


def evaluate(scored,labels):
    labels=np.asarray(labels)
    if len(labels)!=len(scored['nearest_prior_ties']):raise ValueError('Reference length differs')
    positive=same_pair_labels(labels)
    retrieval=[]
    for k,choices in enumerate(scored['nearest_prior_ties']):
        relevant=[i for i in range(k) if labels[i]==labels[k]]
        if not relevant:continue
        reward=sum(i in relevant for i in choices)/len(choices)
        retrieval.append(dict(visit_index=k+1,predicted_previous_indices=[i+1 for i in choices],
                              correct_previous_indices=[i+1 for i in relevant],fractional_correct=reward))
    return dict(pair_auc=auc(scored['pair_scores'],positive),
                pair_average_precision=average_precision(scored['pair_scores'],positive),
                same_pairs=int(positive.sum()),different_pairs=int((~positive).sum()),
                revisit_queries=len(retrieval),nearest_prior_fractional_correct=float(np.mean([r['fractional_correct'] for r in retrieval])) if retrieval else None,
                retrieval=retrieval,predicted_site_count=None)


def partitions_322():
    result=[]
    for triple in itertools.combinations(range(7),3):
        remaining=[i for i in range(7) if i not in triple]
        for pair in itertools.combinations(remaining,2):
            other=[i for i in remaining if i not in pair]
            if min(pair)>min(other):continue
            labels=np.zeros(7,dtype=int);labels[list(pair)]=1;labels[other]=2
            result.append(labels)
    return result


def assignment_rank(scored,labels):
    observed=auc(scored['pair_scores'],same_pair_labels(labels))
    values=np.array([auc(scored['pair_scores'],same_pair_labels(p)) for p in partitions_322()])
    count=int(np.sum(values>=observed-TOL))
    return dict(reference_assignments=len(values),at_least_observed=count,rank_fraction=count/len(values),
                auc_quantiles=np.quantile(values,[0,.5,.95,1]).tolist(),
                population_p_value=None,exchangeability_of_visits_verified=False)
