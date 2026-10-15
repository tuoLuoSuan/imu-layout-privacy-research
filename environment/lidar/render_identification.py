"""Private point-identification sheets; raw sensor axes, no geometric truth claims."""
import argparse
import json
from pathlib import Path

from bag_check import digest


def render(npz,expected_sha,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    source=Path(npz).resolve();output=Path(output)
    actual=digest(source)
    if actual!=expected_sha:raise ValueError('Source preview hash mismatch')
    with np.load(source,allow_pickle=False) as z:
        xyz=z['xyz'].copy()
    mask=np.isfinite(xyz).all(axis=1)&(np.linalg.norm(xyz.astype('float64'),axis=1)<=6)
    points=xyz[mask]
    if not len(points):raise ValueError('No points in display range')
    output.mkdir(parents=True,exist_ok=False)
    fig,axes=plt.subplots(1,3,figsize=(21,8),layout='constrained')
    grids=[]
    for ax,(a,b,c) in zip(axes,[(0,1,2),(0,2,1),(1,2,0)]):
        scatter=ax.scatter(points[:,a],points[:,b],c=points[:,c],s=.45,cmap='viridis',rasterized=True,linewidths=0)
        ax.set_aspect('equal',adjustable='box');ax.set_xlabel('XYZ'[a]+' in livox_frame (m)');ax.set_ylabel('XYZ'[b]+' in livox_frame (m)')
        low=points[:,[a,b]].min(axis=0);high=points[:,[a,b]].max(axis=0)
        edges=[np.linspace(low[i],high[i],5) for i in range(2)]
        for x in edges[0]:ax.axvline(x,color='#183047',lw=.45,alpha=.5)
        for y in edges[1]:ax.axhline(y,color='#183047',lw=.45,alpha=.5)
        for i in range(4):
            for j in range(4):
                ax.text((edges[0][i]+edges[0][i+1])/2,(edges[1][j]+edges[1][j+1])/2,
                        f'{chr(65+i)}{j+1}',fontsize=9,ha='center',va='center',
                        bbox={'facecolor':'white','alpha':.8,'edgecolor':'none','pad':1.5})
        view='XYZ'[a]+'XYZ'[b];ax.set_title(view+' projection | identify by grid cell')
        fig.colorbar(scatter,ax=ax,shrink=.65,label='Raw '+'XYZ'[c]+' (m)')
        grids.append({'projection':view,'horizontal_edges_m':edges[0].tolist(),'vertical_edges_m':edges[1].tolist()})
    fig.suptitle('PRIVATE: point identification only | '+source.parent.name,fontsize=15)
    fig.text(.5,.008,'Grid IDs are image regions, not furniture labels. Raw Z is NOT a verified height. Views are not aligned between sessions.',ha='center',fontsize=10)
    image=output/'identification.png';fig.savefig(image,dpi=150);plt.close(fig)
    report={'source_sha256':actual,'source_preview_rows':int(len(xyz)),'display_rows':int(len(points)),
            'outside_display_rows_retained_in_source':int(len(xyz)-len(points)),'display_rule':'finite coordinates, Euclidean radius <=6m; no interpolation or registration',
            'coordinate_frame':'session-local livox_frame; not gravity-aligned; not shared across captures',
            'object_correspondence':'unconfirmed','geometry_quality':'not_assessed','grids':grids,
            'image_sha256':digest(image),'source_unchanged':actual==digest(source)}
    (output/'provenance.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--npz',required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();print(json.dumps(render(args.npz,args.expected_sha256,args.output),indent=2))
