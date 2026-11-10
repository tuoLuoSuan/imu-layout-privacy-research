"""C2 handset motion for the explicit controlled contact contract.

Scene truth plans motion only; it is never decoder input. This model has
distance-coupled steps and plausible wrist articulation, but is not a human
musculoskeletal or cabinet hinge simulator. Posture encoding is declared.
"""
import heapq, math
import numpy as np
from scipy.spatial.transform import Rotation
from .sim_motion import basis_from_up,U_UP,G
from .contact_contract import CONTRACT


def s5(u):
    u=np.clip(u,0,1);return u**3*(10-15*u+6*u*u)


def clear(a,b,boxes):
    for box in boxes:
        low=np.asarray(box[:2])-.07;high=np.asarray(box[2:])+.07;lo,hi=0.,1.
        for k in range(2):
            d=b[k]-a[k]
            if abs(d)<1e-10:
                if not low[k]<a[k]<high[k]:lo=2.;break
            else:
                x,y=sorted([(low[k]-a[k])/d,(high[k]-a[k])/d]);lo=max(lo,x);hi=min(hi,y)
        if lo<hi and hi>0 and lo<1:return False
    return True


def route(a,b,scene):
    obstacles=[v for k,v in scene['gt'].items() if k.split('#')[0] in ('desk','cab')]
    vertices=[np.asarray(a),np.asarray(b)];room=np.array([scene['W'],scene['L']])
    for box in obstacles:
        for x in [box[0]-.09,box[2]+.09]:
            for y in [box[1]-.09,box[3]+.09]:
                if 0<x<room[0] and 0<y<room[1]:vertices.append(np.array([x,y]))
    distances={0:0.};parents={};queue=[(0.,0)]
    while queue:
        cost,i=heapq.heappop(queue)
        if cost>distances[i]+1e-9:continue
        if i==1:
            ids=[1]
            while ids[-1]!=0:ids.append(parents[ids[-1]])
            return [vertices[j] for j in ids[::-1]]
        for j,v in enumerate(vertices):
            if i==j or not clear(vertices[i],v,obstacles):continue
            c=cost+float(np.linalg.norm(vertices[i]-v))
            if c<distances.get(j,np.inf):distances[j]=c;parents[j]=i;heapq.heappush(queue,(c,j))
    raise ValueError('Declared contact route is not executable')


def targets(scene):
    gt={k.split('#')[0]:np.asarray(b) for k,b in scene['gt'].items()}
    centre=lambda b:(b[:2]+b[2:])/2
    chair=centre(gt['chair']);desk=gt['desk'];delta=centre(desk)-chair
    desk_axis=int(np.argmin(desk[2:]-desk[:2]));toward=np.zeros(2);toward[desk_axis]=np.sign(delta[desk_axis])
    cab=gt['cab'];cc=centre(cab);room=np.array([scene['W'],scene['L']]);cabaxis=int(np.argmin(cab[2:]-cab[:2]));out=np.eye(2)[cabaxis]*(1 if cc[cabaxis]<room[cabaxis]/2 else -1)
    depth=(cab[2:]-cab[:2])[cabaxis];cabphone=cc+out*(depth/2+CONTRACT['cabinet_phone_reach_m'])
    bed=gt['bed'];axis=int(np.argmax(bed[2:]-bed[:2]));u=np.eye(2)[axis]*(1 if room[axis]-bed[axis+2]<bed[axis] else -1)
    length=bed[axis+2]-bed[axis];liephone=centre(bed)+u*(CONTRACT['lying_phone_from_foot_m']-length/2)
    return [('seated',chair,toward),('cabinet',cabphone,-out),('lying',liephone,u)]


def script(scene,peak_speed=.65):
    result=[];time=0.;pos=np.array(scene['S'],float);heading=np.array([0.,1.])
    def add(duration,label,target,h):
        nonlocal time,pos,heading
        result.append({'start':time,'end':time+duration,'label':label,'a':pos.copy(),'b':np.array(target),'heading':np.array(h)})
        time+=duration;pos=np.array(target);heading=np.array(h)
    add(5.,'other',pos,heading)
    for label,target,h in targets(scene)+[('other',np.array(scene['S']),heading)]:
        way=route(pos,target,scene)
        for a,b in zip(way,way[1:]):
            d=b-a;length=float(np.linalg.norm(d))
            if length<1e-5:continue
            hwalk=d/length;add(2.,'other',a,hwalk)
            add(max(2.,1.875*length/peak_speed),'walk',b,hwalk)
        add(10. if label=='cabinet' else 9. if label in ('lying','seated') else 5.,label,target,h)
        if label!='other':add(3.,'other',target,h)
    return result


def generate(scene,seed=7,peak_speed=.65,fs=120.,wrist='medium',calibration=False,script_override=None,noise_streams='legacy'):
    if noise_streams not in ('legacy', 'independent-v1'):
        raise ValueError('noise_streams must be legacy or independent-v1')
    segs=script_override if script_override is not None else script(scene,peak_speed) if not calibration else [
      {'start':0.,'end':5.,'label':'other','a':np.array([1.,1.]),'b':np.array([1.,1.]),'heading':np.array([1.,0.])},
      {'start':5.,'end':5.+1.875*10/peak_speed,'label':'walk','a':np.array([1.,1.]),'b':np.array([11.,1.]),'heading':np.array([1.,0.])},
      {'start':5.+1.875*10/peak_speed,'end':10.+1.875*10/peak_speed,'label':'other','a':np.array([11.,1.]),'b':np.array([11.,1.]),'heading':np.array([1.,0.])}]
    n=int(math.ceil(segs[-1]['end']*fs));t=np.arange(n)/fs;pos=np.zeros((n,3));rot=np.zeros((n,3,3));labels=np.empty(n,dtype='<U10');phase_offset=0.;lastR=None;lastheight=1.05
    height={'walk':1.05,'other':1.05,'seated':.65,'lying':.60,'cabinet':1.0};pose={'walk':'walk','other':'stand','seated':'sit','lying':'lie','cabinet':'reach'}
    wrist_amp={'weak':.15,'medium':.30}[wrist]
    for seg in segs:
        ids=np.flatnonzero((t>=seg['start'])&(t<seg['end']));local=t[ids]-seg['start'];u=local/(seg['end']-seg['start']);smooth=s5(u);label=seg['label'];labels[ids]=label
        direction=seg['heading'];yaw=math.atan2(direction[1],direction[0])-math.pi/2
        Rtarget=Rotation.from_euler('z',yaw).as_matrix()@basis_from_up(U_UP[pose[label]])
        previous=Rtarget if lastR is None else lastR;rv=Rotation.from_matrix(previous.T@Rtarget).as_rotvec();blend=s5(local/.8)
        rot[ids]=previous@Rotation.from_rotvec(blend[:,None]*rv).as_matrix();lastR=Rtarget
        pos[ids,:2]=seg['a']+(seg['b']-seg['a'])*smooth[:,None]
        pos[ids,2]=lastheight+(height[label]-lastheight)*blend;lastheight=height[label]
        if label=='walk':
            length=float(np.linalg.norm(seg['b']-seg['a']));phase=2*np.pi*(phase_offset+length*smooth)/.50
            gate=np.sin(np.pi*u)**2;pos[ids,2]+=.025*gate*np.sin(phase)
            side=np.array([-direction[1],direction[0]]);pos[ids,:2]+=.02*gate[:,None]*np.cos(phase)[:,None]*side+.06*gate[:,None]*np.sin(phase)[:,None]*direction
            rot[ids]=rot[ids]@Rotation.from_euler('xyz',np.c_[.04*gate*np.sin(phase),.10*gate*np.sin(phase+.3),.03*gate*np.sin(phase+.7)]).as_matrix();phase_offset+=length
        # Cabinet motion belongs to the LEFT watch wrist. The RIGHT handset
        # remains held still rather than acting as the handle-pulling hand.
    dt=1/fs;velocity=np.gradient(pos,dt,axis=0,edge_order=2);acceleration=np.gradient(velocity,dt,axis=0,edge_order=2)
    derivative=np.gradient(rot,dt,axis=0,edge_order=2);body=np.einsum('nji,njk->nik',rot,derivative)
    gyro=np.c_[body[:,2,1]-body[:,1,2],body[:,0,2]-body[:,2,0],body[:,1,0]-body[:,0,1]]/2
    clean_acc=np.einsum('nji,nj->ni',rot,acceleration+[0,0,G]);rng=np.random.default_rng(seed)
    acc_rng, gyro_rng = rng, rng
    if noise_streams == 'independent-v1':
        # Channel streams do not move when a longer script consumes more samples.
        acc_seed, gyro_seed = np.random.SeedSequence(seed).spawn(2)
        acc_rng, gyro_rng = np.random.default_rng(acc_seed), np.random.default_rng(gyro_seed)
    return {'t':t,'fs':fs,'ts_ns':1700000000000000000+np.rint(t*1e9).astype(np.int64),'acc':clean_acc+acc_rng.normal(0,.035,clean_acc.shape)+[.02,-.01,.03],
      'gyro':gyro+gyro_rng.normal(0,.003,gyro.shape)+[.0005,-.0004,.0003],'clean_acc':clean_acc,'clean_gyro':gyro,
      'room_m':[12.,3.] if calibration else [scene['W'],scene['L']],
      'truth':{'pos':pos,'R':rot,'label':labels,'segments':[[s['start'],s['end'],s['label']] for s in segs]},
      'contract':CONTRACT,'calibration':calibration,'script':segs}
