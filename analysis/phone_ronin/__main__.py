"""Run adapted pretrained inference on an existing native phone bundle."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from analysis.phone_pdr.session import load_session,validated_output
from .adapter import (OUTPUT_ROOT,WINDOW,STRIDE,prepare_features,make_windows,
    integrate_centers,predict,write_result)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('--architecture',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--checkpoint-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=validated_output(args.output,OUTPUT_ROOT)
    if output.exists():raise FileExistsError('Output must be fresh')
    a,g,source=load_session(args.input)
    grid,features,preparation=prepare_features(a,g)
    windows,timing=make_windows(grid,features)
    velocities,model=predict(windows,args.architecture,args.checkpoint,args.checkpoint_sha256)
    centers=timing[:,2];positions=integrate_centers(centers,velocities)
    path_length=float(np.linalg.norm(np.diff(positions,axis=0),axis=1).sum())
    report={'schema_version':1,'status':'adapted_pretrained_inference_only','accuracy_validated':False,
        'research_validated':False,'body_heading_estimated':False,'layout':None,'source':source,'model':model,
        'preparation':preparation,'window_frames':WINDOW,'stride_frames':STRIDE,'prediction_count':len(windows),
        'prediction_time_semantics':'one-second average velocity; saved at target-interval center',
        'trajectory_time_start_s':float(centers[0]),'trajectory_time_end_s':float(centers[-1]),
        'integration':'trapezoid between prediction centers; origin (0,0) at first center; no endpoint extrapolation',
        'coordinate_units':'meters predicted by pretrained model, unvalidated on this device/record',
        'path_length_m_model':path_length,'endpoint_m_model':positions[-1].tolist(),
        'speed_m_s_model_quantiles':dict(zip(['p0','p50','p95','p100'],np.quantile(np.linalg.norm(velocities,axis=1),[0,.5,.95,1]).tolist())),
        'ground_truth_or_user_geometry_used':False,'scale_yaw_alignment_or_closed_loop':False,
        'feature_bytes_sha256':hashlib.sha256(features.tobytes()).hexdigest(),
        'limitations':['offline quaternion replaces author orientation input; no attitude or bias validation',
            'native approximately 118 Hz interpolated to model 200 Hz; no new measured bandwidth',
            'author model trained on entire released dataset; this is not independent published-benchmark reproduction',
            'no precise walking windows, dense trajectory/body-heading reference or validated room truth',
            'overlapping model windows are correlated; prediction count is not independent sample size',
            'model scale and direction may fail under domain/carry changes; no accuracy or room-layout claim']}
    write_result(output,report,centers,velocities,positions,timing=timing,features=features,grid=grid)
    print(json.dumps({'output':str(output),'predictions':len(windows),'path_length_m_model':path_length,'accuracy_validated':False},ensure_ascii=False))

if __name__=='__main__':main()
