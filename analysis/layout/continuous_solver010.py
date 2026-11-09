"""Continuous-coordinate MILP diagnostic for noisy variable-inventory inputs.

Same position/contact semantics, with explicitly conservative coordinate-wise
contact bounds. No target positions, class-instance IDs or reference ranking.
Region selection is discrete; position within each region stays continuous.
"""
import itertools,warnings
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix
from .continuous_regions import object_region,intersect_regions
from .recovery010 import wall_regions
from .selection_diagnostics import outline_cost


class Program:
    def __init__(self):self.cost=[];self.lo=[];self.hi=[];self.integer=[];self.rows=[];self.lower=[];self.upper=[]
    def var(self,lo=0.,hi=np.inf,integer=False,cost=0.):
        k=len(self.cost);self.cost.append(cost);self.lo.append(lo);self.hi.append(hi);self.integer.append(int(integer));return k
    def row(self,terms,lo=-np.inf,hi=np.inf):self.rows.append(terms);self.lower.append(lo);self.upper.append(hi)
    def when(self,terms,big,selector,lo=-np.inf,hi=np.inf):
        if np.isfinite(lo):self.row({**terms,selector:terms.get(selector,0)-big},lo=lo-big)
        if np.isfinite(hi):self.row({**terms,selector:terms.get(selector,0)+big},hi=hi+big)
    def absolute(self,terms,target,weight):
        u=self.var(cost=weight);self.row({**terms,u:-1},hi=target);self.row({k:-v for k,v in terms.items()}|{u:-1},hi=-target)
    def run(self,seconds):
        matrix=lil_matrix((len(self.rows),len(self.cost)))
        for i,row in enumerate(self.rows):
            for k,v in row.items():matrix[i,k]=v
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',message='Unrecognized options detected.*')
            return milp(self.cost,integrality=self.integer,bounds=Bounds(self.lo,self.hi),constraints=LinearConstraint(matrix.tocsr(),self.lower,self.upper),options={'time_limit':seconds,'node_limit':20000,'mip_rel_gap':.02,'threads':1})


def solve(room,inventory,events,path,padding=.30,walk_margin=.05,seconds=15.):
    room=np.asarray(room,float);path=np.asarray(path,float).reshape(-1,2);big=float(max(room)*3+3);p=Program();objects={};region_counts={}
    for event in events:
        if set(event)!={'object','pos'} or event['object'] not in ['bed','chair','cab']:raise ValueError('Only observed class and position accepted')
    for entry in inventory:
        name=entry['id'];cls=entry['category'];hard=[e for e in events if e['object']==cls] if cls=='bed' else []
        base=object_region(room,entry['dimensions'],cls,hard,path,padding=padding,path_margin=max(0.,walk_margin),use_path=cls in ['desk','cab'])
        choices=[]
        for mode in base['modes']:
            size=np.asarray(mode['dimensions']);regions=mode['q_regions']
            if cls=='desk':regions=intersect_regions(regions,wall_regions(size,room,.15,True))
            choices.extend((r,size) for r in regions)
        if not choices:return {'status':'continuous_domain_empty','boxes':{},'object':name,'search_nodes':0}
        q=[p.var(0,float(room[a])) for a in [0,1]];w=[p.var(0,float(room[a])) for a in [0,1]];selectors=[]
        midboxes=np.array([np.r_[(r[:2]+r[2:])/2,(r[:2]+r[2:])/2+s] for r,s in choices]);costs=outline_cost(midboxes,room,path)
        for (region,size),cost in zip(choices,costs):
            b=p.var(0,1,True,float(cost));selectors.append(b)
            for a in [0,1]:p.when({q[a]:1.},big,b,lo=region[a],hi=region[a+2])
        p.row({b:1. for b in selectors},lo=1,hi=1)
        for a in [0,1]:
            p.row({w[a]:1.}|{b:-float(size[a]) for b,(_,size) in zip(selectors,choices)},lo=0,hi=0)
            p.row({q[a]:1.,w[a]:1.},hi=float(room[a]))
            p.absolute({q[a]:1.,w[a]:.5},float(base['point_m'][a]),.001)
        objects[name]=(cls,q,w);region_counts[name]=len(choices)
    for event in events:
        cls=event['object'];point=event['pos']
        if cls=='bed':continue
        assigned=[];residual=p.var(0,big,cost=.3)
        for name,(category,q,w) in objects.items():
            if category!=cls:continue
            for side in range(1 if cls=='chair' else 4):
                b=p.var(0,1,True);assigned.append(b)
                if cls=='chair':
                    for a in [0,1]:
                        p.when({q[a]:1.,w[a]:.5},big,b,lo=point[a]-padding,hi=point[a]+padding)
                        p.when({q[a]:1.,w[a]:.5,residual:-1.},big,b,hi=point[a])
                        p.when({q[a]:-1.,w[a]:-.5,residual:-1.},big,b,hi=-point[a])
                else:
                    a=0 if side<2 else 1;other=1-a;goal=point[a]+.6 if side%2==0 else point[a]-.6;terms={q[a]:1.}
                    if side%2:terms[w[a]]=1.
                    p.when(terms,big,b,lo=goal-padding,hi=goal+padding)
                    p.when({q[other]:1.},big,b,hi=point[other]+padding)
                    p.when({q[other]:1.,w[other]:1.},big,b,lo=point[other]-padding)
                    p.when(terms|{residual:-1.},big,b,hi=goal)
                    p.when({k:-v for k,v in terms.items()}|{residual:-1.},big,b,hi=-goal)
        if not assigned:return {'status':'missing_inventory_class','boxes':{},'search_nodes':0}
        p.row({b:1. for b in assigned},lo=1,hi=1)
    for (_,a),(_,b) in itertools.combinations(objects.items(),2):
        ca,qa,wa=a;cb,qb,wb=b
        if {ca,cb}=={'desk','chair'}:continue
        separated=[]
        for first,fw,second in [(qa,wa,qb),(qb,wb,qa)]:
            for axis in [0,1]:
                d=p.var(0,1,True);separated.append(d);p.when({first[axis]:1.,fw[axis]:1.,second[axis]:-1.},big,d,hi=1e-8)
        p.row({b:1. for b in separated},lo=1)
    r=p.run(seconds)
    boxes={} if r.x is None else {name:np.r_[[r.x[k] for k in q],[r.x[u]+r.x[v] for u,v in zip(q,w)]].tolist() for name,(_,q,w) in objects.items()}
    gap=getattr(r,'mip_gap',None)
    return {'status':'ok' if boxes else 'continuous_infeasible' if r.status==2 else 'continuous_budget','boxes':boxes,'search_nodes':int(getattr(r,'mip_node_count',0) or 0),'region_counts':region_counts,'optimal_objective':r.status==0,'mip_gap':float(gap) if gap is not None else None,'scope':'MILP with continuous box positions, coordinate-wise outer contact bounds, all class events, unknown assignment, near-wall desk prior; no exact calibrated guarantee'}
