"""All joint outputs are new files strictly below the private output root."""
import json
from pathlib import Path
from analysis.phone_pdr.session import validated_output

OUTPUT_ROOT=Path(__file__).resolve().parents[2]/'output/joint-privacy'

def write_json(path,value,*,allowed_root=OUTPUT_ROOT):
    path=validated_output(path,allowed_root)
    if path.exists():raise FileExistsError('Joint output must be fresh')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
    return path
