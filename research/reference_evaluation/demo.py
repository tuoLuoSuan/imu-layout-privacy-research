"""Deterministic synthetic example; no real sensor data."""
import argparse,json
from pathlib import Path
from evaluation_adapter import evaluate_sites

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists(): raise ValueError('Choose a new output path')
    model=[[0.,0.],[1.,0.],[0.,1.],[.1,.2]]
    echo=[[3.,4.],[5.,4.],[3.3,6.4],[3.2,4.4]]
    result=evaluate_sites(model,echo,['A1','B1','C1','A2'],['A1','B1'])
    result['data_kind']='synthetic_only'
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'data_kind':result['data_kind'],'heldout':result['similarity']['heldout']}))

if __name__=='__main__': main()
