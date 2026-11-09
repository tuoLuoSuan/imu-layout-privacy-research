"""Complete every integer visit budget0..28 at100% coverage.

Core/fine tables already contain ten budgets. This independent job fills
the nineteen missing integers, so a minimum count at FULL coverage is not
an artifact of jumping from14 to21. Other coverage thresholds stay sampled.
"""
import argparse,concurrent.futures,hashlib,json,time
from pathlib import Path
from . import threshold009 as TH

VISITS=[1,3,4,9,10,12,13,15,16,17,18,19,20,22,23,24,25,26,27]


def one(task):
    TH.CELLS=[(1.,n) for n in VISITS]
    return TH.one(task)


def run(repo,package,workers=6,start_index=0,stop_index=10000):
    package=Path(package);out=package/'dense-visits';out.mkdir(exist_ok=True)
    freeze={'n_rooms':10000,'coverage':1.,'additional_visits':VISITS,'combined_integer_budgets':list(range(29)),'method':'outline','tolerance_m':.5,'frozen_before_additional_scores':True,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'protocol.json').write_text(json.dumps(freeze,indent=1),encoding='utf-8')
    # Preserve CPU for the already-running primary confirmation first.
    while not (package/'new5000/evaluation/run.json').exists():time.sleep(5)
    sources=TH.sources(repo,package)[start_index:stop_index];expected={p.stem for p in sources}
    done={p.stem for p in (out/'rooms').glob('*.json') if p.stem in expected};tasks=[(str(p),str(out/'rooms'/p.name)) for p in sources if p.stem not in done]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for i,name in enumerate(pool.map(one,tasks),len(done)+1):
            (out/'progress.json').write_text(json.dumps({'completed_local':i,'total_local':len(sources),'partition':[start_index,stop_index],'completed':len(list((out/'rooms').glob('*.json'))),'total':10000}),encoding='utf-8')
            if i%250==0:print(json.dumps({'dense_room':i,'total_local':len(sources)}),flush=True)
    return {'completed_local':len(sources),'partition':[start_index,stop_index]}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',default='.');p.add_argument('--package',required=True);p.add_argument('--workers',type=int,default=6);p.add_argument('--start-index',type=int,default=0);p.add_argument('--stop-index',type=int,default=10000);a=p.parse_args();run(a.repo,a.package,a.workers,a.start_index,a.stop_index)
