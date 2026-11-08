"""Truth-free selection heuristics and constructive desk-ambiguity witnesses.

Boundary support is an estimator heuristic: walking near a proposed outline
does not prove furniture is there. The witness instead checks that two
different full layouts satisfy the SAME declared observations and geometry.
Neither operation accesses target positions. Production IMU entry is unchanged.
"""
import itertools
import numpy as np
from scipy.spatial import cKDTree
from . import multi_instance as M


def outline_cost(boxes,room,path):
    boxes=np.asarray(boxes,float);room=np.asarray(room,float);path=np.asarray(path,float).reshape(-1,2)
    if not len(path):return np.zeros(len(boxes))
    tree=cKDTree(path);cost=np.zeros(len(boxes));weight=np.zeros(len(boxes))
    for side in range(4):
        axis=0 if side<2 else 1;tangent=1-axis;sign=-1 if side%2==0 else 1
        for t in [.1,.3,.5,.7,.9]:
            p=boxes[:,:2]+(boxes[:,2:]-boxes[:,:2])*.5
            p[:,tangent]=boxes[:,tangent]+t*(boxes[:,tangent+2]-boxes[:,tangent])
            p[:,axis]=boxes[:,axis if sign<0 else axis+2]+sign*.15
            valid=np.all((p>=.15)&(p<=room-.15),axis=1)
            distance=tree.query(p)[0];cost+=valid*np.minimum(distance,.6);weight+=valid
    return np.divide(cost,weight,out=np.full(len(boxes),.6),where=weight>0)


def rerank_pools(pools,room,path,policy):
    out={}
    for name,(boxes,masks,energy) in pools.items():
        if policy=='legacy':e=energy.copy()
        elif policy=='support_mean':
            c=(boxes[:,:2]+boxes[:,2:])/2;e=np.linalg.norm(c-c.mean(axis=0),axis=1)
        elif policy in ['outline','outline_joint']:e=outline_cost(boxes,room,path)+energy
        else:raise ValueError('Unknown selection policy')
        out[name]=(boxes,masks,e)
    return out


def minimum_cost_search(inventory,pools,targets,counts,node_limit=20000):
    """Optional branch-and-bound on exactly the same finite candidate CSP.

    Retains a feasible incumbent when the budget is exhausted. Its objective
    is a declared selection heuristic, not a probability or a truth error.
    """
    names=[e['id'] for e in inventory];compat={};covers={};nodes=0;limit_hit=False
    best=None;best_cost=np.inf;full=(1<<len(targets))-1
    for name,(boxes,masks,energy) in pools.items():
        covers[name]=[sum(1<<j for j,m in enumerate(masks) if int(m)&(1<<t)) for t in range(len(targets))]
    for a,b in itertools.combinations(names,2):
        if {M.category(a),M.category(b)}=={'desk','chair'}:continue
        aa=pools[a][0];bb=pools[b][0]
        inter=np.maximum(0,np.minimum(aa[:,None,2:],bb[None,:,2:])-np.maximum(aa[:,None,:2],bb[None,:,:2]))
        area=np.minimum(np.prod(aa[:,2:]-aa[:,:2],axis=1)[:,None],np.prod(bb[:,2:]-bb[:,:2],axis=1)[None,:])
        valid=np.prod(inter,axis=2)<=1e-8*np.maximum(area,1e-12)
        compat[a,b]=[sum(1<<int(j) for j in np.flatnonzero(row)) for row in valid]
        compat[b,a]=[sum(1<<int(j) for j in np.flatnonzero(row)) for row in valid.T]
    def indices(mask):
        while mask:
            bit=mask&-mask;yield bit.bit_length()-1;mask^=bit
    def search(domains,placed,covered,cost):
        nonlocal nodes,limit_hit,best,best_cost
        nodes+=1
        if nodes>node_limit:limit_hit=True;return
        domains=dict(domains);changed=True
        while changed:
            changed=False
            for t in indices(full&~covered):
                providers=[n for n,d in domains.items() if d&covers[n][t]]
                if not providers:return
                if len(providers)==1:
                    name=providers[0];new=domains[name]&covers[name][t]
                    if new!=domains[name]:domains[name]=new;changed=True
        lower=cost+sum(min(float(pools[n][2][i]) for i in indices(d)) for n,d in domains.items())
        if lower>=best_cost-1e-12:return
        if not domains:
            if covered==full:best=dict(placed);best_cost=cost
            return
        for a,b in itertools.combinations(domains,2):
            if (a,b) in compat and not any(compat[a,b][i]&domains[b] for i in indices(domains[a])):return
        name=min(domains,key=lambda n:domains[n].bit_count());boxes,masks,energy=pools[name]
        for i in sorted(indices(domains[name]),key=lambda j:(float(energy[j]),-(int(masks[j])&~covered).bit_count())):
            remaining={};valid=True
            for other,d in domains.items():
                if other==name:continue
                d=d&compat[name,other][i] if (name,other) in compat else d
                if not d:valid=False;break
                remaining[other]=d
            if valid:search(remaining,{**placed,name:i},covered|int(masks[i]),cost+float(energy[i]))
            if limit_hit:return
    search({n:(1<<len(pools[n][0]))-1 for n in names},{},0,0.)
    if best is None:return {'status':'search_budget_exhausted' if limit_hit else 'proposal_conflict','boxes':{},'search_nodes':nodes,'candidate_counts':counts}
    return {'status':'ok','boxes':{n:pools[n][0][i] for n,i in best.items()},'candidate_counts':counts,
        'search_nodes':nodes,'objective':float(best_cost),'candidate_objective_optimal':not limit_hit,'search_budget_exhausted_with_incumbent':limit_hit}


def desk_witness(layout,pools,tolerance=.5):
    """One valid alternative suffices for a conditional minimax lower bound.

Only an unobserved desk is moved; all observed contacts and other furniture
remain fixed. Projected desk/chair overlap uses the existing benchmark rule.
    Distances must ignore same-class label switches. Up to eight farthest
    named-slot proposals per desk are checked; this is a bounded search.
    No witness found is NOT an identifiability certificate.
"""
    best=None
    for name,box in layout.items():
        if M.category(name)!='desk' or name not in pools:continue
        bank=np.asarray(pools[name],float).reshape(-1,4);valid=np.ones(len(bank),bool)
        for other,b in layout.items():
            if other==name or M.category(other)=='chair':continue
            inter=np.maximum(0,np.minimum(bank[:,2:],np.asarray(b)[2:])-np.maximum(bank[:,:2],np.asarray(b)[:2]))
            area=np.minimum(np.prod(bank[:,2:]-bank[:,:2],axis=1),np.prod(np.asarray(b)[2:]-np.asarray(b)[:2]))
            valid&=np.prod(inter,axis=1)<=1e-8*np.maximum(area,1e-12)
        ids=np.flatnonzero(valid)
        if not len(ids):continue
        c=(np.asarray(box)[:2]+np.asarray(box)[2:])/2;distance=np.linalg.norm((bank[ids,:2]+bank[ids,2:])/2-c,axis=1)
        from .permutation_witness import witness
        for j in np.argsort(-distance)[:8]:
            gap=float(distance[j])
            if gap<=2*tolerance+1e-8:break
            alternative={k:np.asarray(v).tolist() for k,v in layout.items()};alternative[name]=bank[ids[j]].tolist()
            check=witness(layout,alternative,tolerance);separation=check['matching_invariant_separation_m']
            if check['certified'] and (best is None or separation>best['separation_m']):
                best={'object':name,'separation_m':separation,'named_slot_displacement_m':gap,
                    'same_class_permutation_invariant':True,'conditional_minimax_error_lower_m':separation/2,
                    'layout_a':{k:np.asarray(v).tolist() for k,v in layout.items()},'layout_b':alternative}
    return best or {'found':False,'meaning':'Bounded search found no witness; does not certify identifiability'}
