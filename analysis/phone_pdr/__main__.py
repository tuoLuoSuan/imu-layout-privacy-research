import argparse,json
from pathlib import Path
from .pdr import diagnose
from .session import load_session,write_diagnostic,validated_output

def main():
    parser=argparse.ArgumentParser(description='Phone PDR diagnostic only: no walls, no map, no hardware operation.')
    parser.add_argument('--session',type=Path,required=True,help='Existing native ZIP or original-contents directory')
    parser.add_argument('--output',type=Path,required=True,help='Fresh directory below workspace output/phone-pdr')
    parser.add_argument('--stride-coefficient',type=float,help='Independent calibration only; not a verified metric scale')
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    allowed=root/'output/phone-pdr'
    try:target=validated_output(args.output,allowed)
    except ValueError as e:parser.error(str(e))
    # Read and validate everything before creating any output.
    a,g,source=load_session(args.session);result=diagnose(a,g,args.stride_coefficient)
    write_diagnostic(target,result,source)
    print(json.dumps({'output':str(target),'candidate_count':result['candidate_count'],
                     'coordinate_units':result['coordinate_units'],'research_validated':False},ensure_ascii=True))

if __name__=='__main__':main()
