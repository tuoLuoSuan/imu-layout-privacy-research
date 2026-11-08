"""Continuous, conservative position sets for declared geometric evidence.

No truth, finite candidate bank, learned ranking or wall identity is accepted.
The union includes both axis-aligned orientations and all storage operation faces.
Bed/chair Euclidean padding is conservatively relaxed to coordinate intervals.
Walk exclusion removes open rectangles in minimum-corner parameter space.
Certificates are conditional on correct labels, known sizes/registration and the
declared error bounds; they are not statistically calibrated IMU guarantees.
"""
import numpy as np

EPS=1e-10


def intersect_regions(regions,options):
    regions=np.asarray(regions,float).reshape(-1,4)
    options=np.asarray(options,float).reshape(-1,4)
    if not len(regions) or not len(options):return np.empty((0,4))
    lo=np.maximum(regions[:,None,:2],options[None,:,:2])
    hi=np.minimum(regions[:,None,2:],options[None,:,2:])
    out=np.concatenate([lo,hi],axis=2).reshape(-1,4)
    keep=np.all(out[:,:2]<=out[:,2:],axis=1)
    return np.unique(out[keep],axis=0)


def subtract_open(regions,cut):
    """Remove an OPEN rectangle, retaining all valid edges and singleton sets."""
    r=np.asarray(regions,float).reshape(-1,4)
    if not len(r):return r
    a,b,c,d=np.asarray(cut,float)
    if a>=c or b>=d:return r
    touched=(r[:,2]>a)&(r[:,0]<c)&(r[:,3]>b)&(r[:,1]<d)
    base=r[touched];pieces=[r[~touched]]
    for axis,limit,upper in [(0,a,True),(0,c,False),(1,b,True),(1,d,False)]:
        ids=(base[:,axis]<=limit)&(base[:,axis+2]>=limit)
        v=base[ids].copy()
        if not len(v):continue
        if axis==1:
            v[:,0]=np.maximum(v[:,0],a);v[:,2]=np.minimum(v[:,2],c)
        v[:,axis+2 if upper else axis]=limit
        pieces.append(v[np.all(v[:,:2]<=v[:,2:],axis=1)])
    return np.concatenate(pieces,axis=0) if pieces else np.empty((0,4))


def _event_options(obj,point,size,padding,reach):
    x,y=point;w,h=size;p=padding+EPS
    if obj=='chair':
        return [[x-w/2-p,y-h/2-p,x-w/2+p,y-h/2+p]]
    if obj=='bed':return [[x-w-p,y-h-p,x+p,y+p]]
    if obj=='cab':
        return [[x+reach-p,y-h-p,x+reach+p,y+p],
                [x-w-reach-p,y-h-p,x-w-reach+p,y+p],
                [x-w-p,y+reach-p,x+p,y+reach+p],
                [x-w-p,y-h-reach-p,x+p,y-h-reach+p]]
    return [[-np.inf,-np.inf,np.inf,np.inf]]


def object_region(room,dimensions,obj,events,path,padding=.20,reach=.60,
                  path_margin=.08,use_path=True,max_regions=20000,walk_clearance_m=0.):
    """Return an outer envelope of all feasible centres under the declared model.

    Resource limits only skip constraints and widen the result; never prune
    unknown regions to manufacture a small certificate.
    """
    room=np.asarray(room,float);dimensions=np.asarray(dimensions,float)
    if room.shape!=(2,) or dimensions.shape!=(2,) or np.any(room<=0) or np.any(dimensions<=0):
        raise ValueError('Positive two-dimensional room and object size required')
    if padding<0 or reach<0 or path_margin<0 or walk_clearance_m<0 or max_regions<1:raise ValueError('Invalid bound or region budget')
    effective_margin=path_margin-walk_clearance_m
    path=np.asarray(path,float).reshape(-1,2)
    if not np.isfinite(path).all():raise ValueError('Non-finite walk point')
    modes=[];relaxed=False
    for size in np.unique(np.array([dimensions,dimensions[::-1]]),axis=0):
        if np.any(size>room):continue
        regions=np.array([[0.,0.,*(room-size)]])
        for event in events:
            if event['object']!=obj:continue
            point=np.asarray(event['pos'],float)
            if point.shape!=(2,) or not np.isfinite(point).all():raise ValueError('Non-finite contact')
            proposed=intersect_regions(regions,_event_options(obj,point,size,padding,reach))
            if len(proposed)>max_regions:relaxed=True;continue
            regions=proposed
            if not len(regions):break
        if use_path and len(regions):
            w,h=size
            # Margin is the legacy interior tolerance, not a measured human radius.
            for x,y in np.unique(path,axis=0):
                proposed=subtract_open(regions,[x-w+effective_margin+EPS,y-h+effective_margin+EPS,
                                                x-effective_margin-EPS,y-effective_margin-EPS])
                if len(proposed)>max_regions:relaxed=True;break
                regions=proposed
                if not len(regions):break
        if len(regions):modes.append({'dimensions':size.tolist(),'q_regions':regions})
    if not modes:
        return {'status':'conflict','point_m':None,'center_bounds_m':None,'radius_upper_m':None,
                'modes':[],'relaxed_by_budget':relaxed,'bounds_sound_if_model_conditions_hold':True}
    lows=[];highs=[]
    for mode in modes:
        r=mode['q_regions'];half=np.array(mode['dimensions'])/2
        lows.append(r[:,:2].min(axis=0)+half);highs.append(r[:,2:].max(axis=0)+half)
    lo=np.min(lows,axis=0);hi=np.max(highs,axis=0);point=(lo+hi)/2
    return {'status':'outer_supported','point_m':point,'center_bounds_m':np.r_[lo,hi],
            'radius_upper_m':float(np.linalg.norm(hi-lo)/2),'modes':modes,
            'region_count':sum(len(m['q_regions']) for m in modes),'relaxed_by_budget':relaxed,
            'bounds_sound_if_model_conditions_hold':True,
            'model':'Known room/sizes; two axis orientations; all operation-face modes; conservative padding; no overlap or desk-chair relation required'}


def contains_box(result,box):
    box=np.asarray(box,float);size=box[2:]-box[:2]
    for mode in result['modes']:
        if not np.allclose(mode['dimensions'],size,atol=1e-8):continue
        r=mode['q_regions'];q=box[:2]
        if np.any(np.all(q>=r[:,:2]-EPS,axis=1)&np.all(q<=r[:,2:]+EPS,axis=1)):return True
    return False
