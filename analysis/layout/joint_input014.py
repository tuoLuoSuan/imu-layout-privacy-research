"""Opt-in signal-only gyro tracking; no evaluation scene or script accepted."""
import argparse,json
from pathlib import Path
from . import multi_raw010 as X
from .displacement011 import load,replay
from .bias_tracker014b import gated_gyro
from .contact_loops011 import refine as loops
from .wall_refine012 import refine as wall
from .oriented_raw011 import decode


def infer_saved(session,priors,motion_model,wrist_model):
    if set(priors)!={'room','start','inventory'}:raise ValueError('Only room/start/inventory accepted')
    model=load(motion_model)
    def front(t,A,G):
        _,Gc,meta=gated_gyro(t,A,G);p,R,info=replay(t,A,Gc,model,heading_regularization=True)
        meta['acceleration_correction_applied']=False;info['gyro_tracker014']=meta
        return p,R,info
    def refine(t,p,R,runs,known):
        p,a=loops(t,p,R,runs,known);p,b=wall(t,p,R,runs,known)
        return p,{'point_plane_loops':a,'cabinet_wall':b}
    result=X.infer(session,priors,wrist_model,trajectory_frontend=front,candidate_limit=128,trajectory_refiner=refine,
                   layout_decoder=lambda *a:decode(*a,support_cost_weight=.3))
    result['input_contract']={'phone_axes':6,'watch_axes':3,'watch_gyro':False,'cabinet_source':'watch_only',
                              'truth_pose_read':False,'truth_scene_read':False,'script_labels_read':False,
                              'initial_stationary_hold_s':2,'same_domain_supervised_displacement':True,
                              'offline':True,'experimental014_not_legacy_real_pipeline':True}
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['session','priors','model','wrist','out']:p.add_argument('--'+k,required=True)
    a=p.parse_args();Path(a.out).write_text(json.dumps(infer_saved(a.session,json.loads(Path(a.priors).read_text()),a.model,a.wrist),indent=1))
