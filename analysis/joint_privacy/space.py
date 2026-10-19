"""Trajectory inverse-distance representation inspired by Walk2Map's input.

This implements a small geometric representation, not their learned model.
It consumes modeled paths only; no unobserved wall/free-space claims follow.
"""
import argparse,json,math
from pathlib import Path
import numpy as np

def distance_field(points,*,cell_m=.5,margin_m=1.,max_cells=10000):
    p=np.asarray(points,dtype=float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<2 or not np.isfinite(p).all():raise ValueError('Finite modeled XY path required')
    if not all(math.isfinite(x) and x>0 for x in (cell_m,margin_m)):raise ValueError('Positive finite raster parameters required')
    lo=np.floor((p.min(0)-margin_m)/cell_m)*cell_m;hi=np.ceil((p.max(0)+margin_m)/cell_m)*cell_m
    shape=np.rint((hi-lo)/cell_m).astype(int)+1
    if int(shape[0])*int(shape[1])>max_cells:raise ValueError('Raster exceeds fixed resource bound')
    x=lo[0]+np.arange(shape[0])*cell_m;y=lo[1]+np.arange(shape[1])*cell_m
    grid=np.stack(np.meshgrid(x,y),axis=-1).reshape(-1,2);d=np.full(len(grid),np.inf)
    for a,b in zip(p,p[1:]):
        v=b-a;norm=float(v@v)
        u=np.clip((grid-a)@v/norm,0,1) if norm>0 else np.zeros(len(grid))
        d=np.minimum(d,np.linalg.norm(grid-(a+u[:,None]*v),axis=1))
    d=d.reshape(len(y),len(x))
    return {'representation':'distance to modeled polyline; inverse-distance feature only',
        'cell_m_model':cell_m,'x_centers_m_model':x.tolist(),'y_centers_m_model':y.tolist(),
        'distance_to_modeled_path_m':d.tolist(),'inverse_distance_feature':(cell_m/(cell_m+d)).tolist(),
        'walls':None,'free_space_validated':False,'model_metric_scale_validated':False,
        'unknown_space':'Unvisited locations and all walls remain unknown; grid is not an occupancy map'}

def main():
    from .output import write_json
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('attack',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    report=json.loads(args.attack.read_text(encoding='utf-8'))
    value={'synthetic':report['synthetic'],'research_validated':False,
        'fields':{name:distance_field(v['positions']) for name,v in report['variants'].items()}}
    write_json(args.output,value);print(str(args.output))

if __name__=='__main__':main()
