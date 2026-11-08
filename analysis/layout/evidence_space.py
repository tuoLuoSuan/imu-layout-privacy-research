"""Truth-free finite rectangle hypotheses for conditional activity experiments.

The bank is fixed before evidence. Unknown furniture remains a latent variable.
Search scores and retained hypotheses are not calibrated posterior probabilities.
"""
import math
import numpy as np

def intersect_interval(prior,event):
    lo=max(float(prior[0]),float(event[0]));hi=min(float(prior[1]),float(event[1]))
    if hi<lo:return {"status":"conflict","lo":lo,"hi":hi,"width_m":None}
    return {"status":"singleton" if hi==lo else "interval","lo":lo,"hi":hi,"width_m":hi-lo}

def containment_interval(anchors,extent,padding=0.0):
    values=np.asarray(anchors,float)
    if not len(values):return (-float("inf"),float("inf"))
    return (float(values.max()-extent-padding),float(values.min()+padding))

def interval_accuracy(interval):
    width=float(interval[1]-interval[0])
    if width<0:return {"status":"conflict","width_m":None,"minimax_center_error_m":None}
    return {"status":"singleton" if width==0 else "interval","width_m":width,
            "minimax_center_error_m":width/2}

def spatial_coverage(points,room,radius=.25,grid=.10):
    points=np.asarray(points,float)
    if not len(points):return 0.
    nx,ny=int(np.ceil(room[0]/grid)),int(np.ceil(room[1]/grid))
    xs=(np.arange(nx)+.5)*room[0]/nx;ys=(np.arange(ny)+.5)*room[1]/ny
    cells=np.stack(np.meshgrid(xs,ys),axis=-1).reshape(-1,2)
    covered=np.zeros(len(cells),bool)
    for block in np.array_split(points,max(1,int(np.ceil(len(points)/128)))):
        covered|=np.any(np.sum((cells[:,None,:]-block[None,:,:])**2,axis=2)<=radius*radius,axis=1)
    return float(covered.mean())

def make_bank(room,objects,spacing=.20):
    banks={}
    for obj,extent in objects.items():
        a,b=map(float,extent)
        orientations=[(a,b)] if abs(a-b)<1e-8 else [(a,b),(b,a)]
        boxes=[]
        for dx,dy in orientations:
            if dx>room[0] or dy>room[1]:continue
            xx=np.linspace(0,room[0]-dx,int(np.ceil((room[0]-dx)/spacing))+1)
            yy=np.linspace(0,room[1]-dy,int(np.ceil((room[1]-dy)/spacing))+1)
            x,y=np.meshgrid(xx,yy);x=x.ravel();y=y.ravel()
            boxes.append(np.column_stack([x,y,x+dx,y+dy]))
        if not boxes:raise ValueError("Furniture cannot fit supplied room")
        banks[obj]=np.unique(np.round(np.vstack(boxes),10),axis=0)
    return banks

def centres(boxes):return (boxes[:,:2]+boxes[:,2:])/2


def envelope_certificate(bounds,point,tolerance=.5):
    """Farthest corner from the actual output, conditional on truth in the envelope.

    This does not certify the observation model or continuous-space coverage of
    a finite bank. It never uses truth to decide whether to emit a point.
    """
    empty={'allow':False,'radius_upper_m':None,'condition':'True centre lies in the reported centre envelope'}
    if bounds is None or point is None:return dict(empty,status='unavailable')
    b=np.asarray(bounds,float);p=np.asarray(point,float)
    if b.shape!=(4,) or p.shape!=(2,) or not np.isfinite(b).all() or not np.isfinite(p).all() or np.any(b[2:]<b[:2]):
        return dict(empty,status='invalid')
    radius=float(np.linalg.norm(np.maximum(abs(p-b[:2]),abs(p-b[2:]))))
    return {'status':'conditional','allow':radius<=tolerance,'radius_upper_m':radius,
            'point':p.tolist(),'bounds':b.tolist(),'midpoint_radius_m':float(np.linalg.norm(b[2:]-b[:2])/2),
            'condition':empty['condition'],'not_a_calibrated_probability':True}


def bed_position_envelope(room,dimensions,anchors,padding=.2):
    """Continuous outer envelope of an axis-aligned phone-in-bed model.

    Both orientations remain possible. Coordinate padding is a conservative
    relaxation of Euclidean padding. No target position or grid is an input.
    """
    room=np.asarray(room,float);d=np.asarray(dimensions,float);a=np.asarray(anchors,float).reshape(-1,2)
    modes=[]
    for extent in np.unique(np.array([d,d[::-1]]),axis=0):
        lo=np.zeros(2);hi=room-extent
        if len(a):
            lo=np.maximum(lo,a.max(axis=0)-extent-padding)
            hi=np.minimum(hi,a.min(axis=0)+padding)
        if np.all(hi>=lo):
            modes.append({'extent_m':extent.tolist(),'q_lo_m':lo.tolist(),'q_hi_m':hi.tolist(),
                          'center_bounds_m':np.r_[lo+extent/2,hi+extent/2].tolist()})
    if not modes:return {'status':'conflict','bounds':None,'modes':[]}
    bounds=np.array([m['center_bounds_m'] for m in modes])
    return {'status':'conditional','bounds':np.r_[bounds[:,:2].min(axis=0),bounds[:,2:].max(axis=0)].tolist(),
            'modes':modes,'condition':'Known room/dimensions, correct bed labels, all phone positions within bed plus padding'}

def _contact(boxes,event,padding,reach):
    p=np.asarray(event["pos"],float)
    obj=event["object"]
    if obj=="chair":
        distance=np.linalg.norm(centres(boxes)-p,axis=1)
        return distance<=padding,distance/max(padding,1e-9)
    if obj=="bed":
        # Phone is on/in the bed footprint; no invented foot-point or bed-centre equality.
        outside=np.maximum(boxes[:,:2]-p,p-boxes[:,2:]).clip(min=0)
        distance=np.linalg.norm(outside,axis=1)
        return distance<=padding,np.zeros(len(boxes))
    if obj=="cab":
        # Unknown operation face: union of the four exterior front-face modes.
        dx=np.stack([boxes[:,0]-p[0],p[0]-boxes[:,2],boxes[:,1]-p[1],p[1]-boxes[:,3]],axis=1)
        along=np.stack([(p[1]>=boxes[:,1]-padding)&(p[1]<=boxes[:,3]+padding)]*2+
                       [(p[0]>=boxes[:,0]-padding)&(p[0]<=boxes[:,2]+padding)]*2,axis=1)
        residual=np.where(along& (dx>=-padding),abs(dx-reach),np.inf).min(axis=1)
        return residual<=padding,residual/max(padding,1e-9)
    return np.ones(len(boxes),bool),np.zeros(len(boxes))

def _path_bad(boxes,path,margin):
    bad=np.zeros(len(boxes),bool)
    if not len(path):return bad
    for part in np.array_split(path,max(1,int(np.ceil(len(path)/128)))):
        x,y=part[:,0],part[:,1]
        bad|=np.any((x>boxes[:,0,None]+margin)&(x<boxes[:,2,None]-margin)&
                    (y>boxes[:,1,None]+margin)&(y<boxes[:,3,None]-margin),axis=1)
    return bad

def _prior_cost(boxes,room,training):
    if training is None or not len(training):return np.zeros(len(boxes))
    p=centres(boxes)/np.asarray(room)
    # Fixed development bandwidth; leave the target whole scene out.
    dist=np.sum((p[:,None,:]-np.asarray(training)[None,:,:])**2,axis=2)
    density=np.exp(-dist/(2*.20**2)).mean(axis=1)
    return -np.log(np.maximum(density,1e-12))

def _overlap(first,second):
    intersection=np.maximum(0,np.minimum(first[2:],second[2:])-np.maximum(first[:2],second[:2]))
    return float(np.prod(intersection)/max(1e-9,min(np.prod(first[2:]-first[:2]),np.prod(second[2:]-second[:2]))))

def infer(room,banks,path,events,use_path=True,use_actions=True,prior=None,padding=.20,
          reach=.60,path_margin=.08,candidate_limit=48,beam_width=48,desk_reach=None):
    """No truth argument is accepted. All arms use the same bank and target list."""
    path=np.asarray(path,float).reshape(-1,2)
    objects={};pools={}
    for obj,bank in banks.items():
        valid=np.ones(len(bank),bool);cost=np.zeros(len(bank))
        if use_actions:
            repetitions=sum(event['object']==obj for event in events)
            for event in events:
                if event["object"]==obj:
                    keep,energy=_contact(bank,event,padding,reach)
                    valid&=keep;cost+=np.minimum(energy,100)**2/max(1,repetitions)
        if use_actions and desk_reach is not None and obj=="desk":
            # Desk has no interaction class of its own. Sitting at a desk is the only
            # activity that points at it, so the seated anchors bound how far the box
            # can be.  This is a modelling assumption, not an observation.
            for event in events:
                if event["object"]!="chair":
                    continue
                p=np.asarray(event["pos"],float)
                outside=np.maximum(bank[:,:2]-p,p-bank[:,2:]).clip(min=0)
                valid&=np.linalg.norm(outside,axis=1)<=desk_reach
        if use_path and obj in ("desk","cab"):
            valid&=~_path_bad(bank,path,path_margin)
        selected=bank[valid]
        if not len(selected):
            objects[obj]={"n":0,"status":"conflict","center_diameter_m":None,
                          "center_envelope_m":None,"support_boxes":[]}
            continue
        cc=centres(selected);width=np.ptp(cc,axis=0)
        objects[obj]={"n":len(selected),"status":"supported","center_diameter_m":float(np.linalg.norm(width)),
                      "center_bounds_m":np.r_[cc.min(axis=0),cc.max(axis=0)].tolist(),
                      "diameter_definition":"axis-aligned centre-envelope diagonal, conservative upper bound",
                      "center_envelope_m":[float(v) for v in width],
                      "minimax_box_radius_upper_m":float(np.linalg.norm(width)/2),
                      "support_boxes":selected}
        energy=cost[valid]+_prior_cost(selected,room,None if prior is None else prior.get(obj))
        # Prefer a feasible bank member near the supported centres when costs tie.
        energy+=.001*np.linalg.norm(cc-cc.mean(axis=0),axis=1)
        order=np.argsort(energy,kind="stable")
        best=order[:candidate_limit//2]
        other=order[candidate_limit//2:]
        diverse=other[np.linspace(0,len(other)-1,min(len(other),candidate_limit-len(best))).astype(int)] if len(other) else []
        ids=np.unique(np.r_[best,diverse].astype(int))
        pools[obj]=[(selected[i],float(energy[i])) for i in ids]
    if any(r["n"]==0 for r in objects.values()):
        return {"status":"conflict","objects":objects,"boxes":{},"candidates":[]}
    # Joint beam, fixed across arms. Pair overlap is a soft cost; desk/chair projection overlap is allowed.
    beam=[(0.,{})]
    for obj in [key for key in ("cab","bed","desk","chair") if key in pools]:
        expanded=[]
        candidate_boxes=np.asarray([box for box,_ in pools[obj]])
        candidate_energy=np.asarray([energy for _,energy in pools[obj]])
        candidate_area=np.prod(candidate_boxes[:,2:]-candidate_boxes[:,:2],axis=1)
        for score,placed in beam:
            penalty=np.zeros(len(candidate_boxes))
            for name,other in placed.items():
                if {name,obj}=={'desk','chair'}:continue
                intersection=np.maximum(0,np.minimum(candidate_boxes[:,2:],other[2:])-
                                         np.maximum(candidate_boxes[:,:2],other[:2]))
                area=float(np.prod(other[2:]-other[:2]))
                penalty+=np.prod(intersection,axis=1)/np.maximum(1e-9,np.minimum(candidate_area,area))*8
            costs=score+candidate_energy+penalty
            expanded.extend((float(value),dict(placed,**{obj:box})) for box,value in zip(candidate_boxes,costs))
        expanded.sort(key=lambda v:v[0]);beam=expanded[:beam_width]
    return {"status":"ok","objects":objects,"boxes":beam[0][1],
            "candidates":[b for _,b in beam],
            "search_scope":"finite bank plus bounded joint beam; not posterior sampling",
            "candidate_limit":candidate_limit,"beam_width":beam_width}

def evaluate(result,truth,tolerance=.5):
    """Evaluator only. A missing object counts as failure, not as zero error."""
    errors={obj:None for obj in truth}
    supported={obj:False for obj in truth}
    widths={obj:None for obj in truth}
    radii={obj:None for obj in truth};covered={obj:False for obj in truth}
    for obj,target in truth.items():
        target=np.asarray(target)
        if obj in result.get("boxes",{}):
            errors[obj]=float(np.linalg.norm((target[:2]+target[2:])/2-
                                            (result["boxes"][obj][:2]+result["boxes"][obj][2:])/2))
        row=result["objects"].get(obj,{})
        boxes=row.get("support_boxes",[])
        if len(boxes):
            cc=centres(np.asarray(boxes));tc=(target[:2]+target[2:])/2
            dist=np.linalg.norm(cc-tc,axis=1)
            supported[obj]=bool(dist.min()<=tolerance)
            widths[obj]=row["center_diameter_m"]
            bounds=np.r_[cc.min(axis=0),cc.max(axis=0)]
            covered[obj]=bool(np.all(tc>=bounds[:2]-1e-9) and np.all(tc<=bounds[2:]+1e-9))
            if obj in result.get('boxes',{}):
                b=np.asarray(result['boxes'][obj]);point=(b[:2]+b[2:])/2
                radii[obj]=envelope_certificate(bounds,point,tolerance)['radius_upper_m']
    all_hit=all(v is not None and v<=tolerance for v in errors.values())
    same_candidate=any(all(obj in b and np.linalg.norm(
        (np.asarray(b[obj])[:2]+np.asarray(b[obj])[2:])/2-
        (np.asarray(target)[:2]+np.asarray(target)[2:])/2)<=tolerance
        for obj,target in truth.items()) for b in result.get("candidates",[]))
    return {"center_error_m":errors,"support_hit":supported,"center_diameter_upper_m":widths,
            "conditional_radius_upper_m":radii,"truth_center_in_envelope":covered,
            "full_point_hit":all_hit,"same_candidate_hit":same_candidate,
            "all_support_hit":all(supported.values())}

def stable_threshold(rows,x_key="coverage",hit_key="success_rate",target=.80,following=2):
    """First measured point that passes and has the requested subsequent passing points."""
    ordered=sorted(rows,key=lambda r:r[x_key])
    for i,row in enumerate(ordered):
        window=ordered[i:i+following+1]
        if len(window)==following+1 and all(v[hit_key]>=target for v in window):
            return {"value":float(row[x_key]),"observed_grid":True,"confirmation_points":len(window)}
    return None
