"""Independent kinematic checks; frontend compatibility is a separate result."""
import numpy as np

def required_actions_available(per_class,minimum_recall=.5):
    return all(per_class.get(name,{}).get('recall',0) is not None and
               per_class.get(name,{}).get('recall',0)>=minimum_recall
               for name in ('seated','lying','cabinet'))

def pose_derivatives(pose, time, duration, step=1e-4):
    """Second-order position differences and body angular rate at one time."""
    t=float(time);h=min(step,max(duration/4,1e-8))
    position,R=pose(t)
    if t<h:
        p1=pose(t+h)[0];p2=pose(t+2*h)[0]
        acceleration=(p2-2*p1+position)/(h*h)
        left,right=t,t+h
    elif t>duration-h:
        p1=pose(t-h)[0];p2=pose(t-2*h)[0]
        acceleration=(position-2*p1+p2)/(h*h)
        left,right=t-h,t
    else:
        acceleration=(pose(t+h)[0]-2*position+pose(t-h)[0])/(h*h)
        left,right=t-h,t+h
    derivative=(pose(right)[1]-pose(left)[1])/(right-left)
    M=R.T@derivative
    omega=np.array([M[2,1]-M[1,2],M[0,2]-M[2,0],M[1,0]-M[0,1]])/2
    return position,acceleration,omega

def physical_report(gen, gravity=9.81):
    """Check clean signals against device ground truth, independently of RoNIN."""
    t=gen['t'];R=np.asarray(gen['truth']['R']);p=np.asarray(gen['truth']['pos'])
    a=gen.get('clean_acc',gen['acc']);w=gen.get('clean_gyro',gen['gyro'])
    world=np.einsum('nij,nj->ni',R,a)+np.array([0,0,-gravity])
    dt=np.diff(t)
    # True initial device velocity; this is a generator consistency check.
    initial=(-3*p[0]+4*p[1]-p[2])/(2*dt[0])
    velocity=np.vstack([initial,initial+np.cumsum((world[:-1]+world[1:])*.5*dt[:,None],axis=0)])
    replay=np.vstack([p[0],p[0]+np.cumsum((velocity[:-1]+velocity[1:])*.5*dt[:,None],axis=0)])
    error=np.linalg.norm(replay-p,axis=1)
    orthogonal=np.max(np.abs(np.einsum('nji,njk->nik',R,R)-np.eye(3)))
    room=np.asarray(gen.get('room_m',[np.inf,np.inf]))
    outside=np.maximum(-p[:,:2],p[:,:2]-room).clip(min=0)
    return {'scope':'Clean device-motion kinematic consistency, not realism or learned-frontend validity',
            'proper_rotation':bool(orthogonal<1e-7 and np.all(np.linalg.det(R)>0.999999)),
            'finite_signals':bool(np.isfinite(a).all() and np.isfinite(w).all()),
            'acceleration_norm_max_m_s2':float(np.linalg.norm(a,axis=1).max()),
            'gyro_norm_max_rad_s':float(np.linalg.norm(w,axis=1).max()),
            'reintegration_median_m':float(np.median(error)),
            'reintegration_final_m':float(error[-1]),'reintegration_max_m':float(error.max()),
            'maximum_handset_room_violation_m':float(outside.max()),
            'passed':bool(orthogonal<1e-7 and np.isfinite(a).all() and np.isfinite(w).all() and error.max()<.1 and outside.max()<.001)}
