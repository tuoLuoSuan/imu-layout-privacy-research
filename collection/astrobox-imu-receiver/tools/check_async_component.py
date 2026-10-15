"""Check actual core export entries, not arbitrary strings, for receiver async tasks.

This is a narrow ABI admission check, not a complete WebAssembly validator or
AstroBox/device test. All four callbacks must have task entry/callback exports
in one actual core module. No external tools are required.
"""
import argparse
import json
from pathlib import Path
import zipfile

CORE=b'\0asm\x01\0\0\0'
COMPONENT=b'\0asm\x0d\0\x01\0'
METHODS=('on-event','on-ui-event-v3','on-ui-render','on-card-render')
PREFIX='astrobox:psys-plugin/event-v3#'

def number(data,pos):
    value=0
    for shift in range(0,35,7):
        if pos>=len(data):raise ValueError('Truncated LEB')
        b=data[pos];pos+=1;value|=(b&127)<<shift
        if b<128:
            if value>0xffffffff:raise ValueError('Invalid u32')
            return value,pos
    raise ValueError('Invalid LEB')

def sections(data):
    pos=8
    while pos<len(data):
        kind=data[pos];length,start=number(data,pos+1);end=start+length
        if end>len(data):raise ValueError('Truncated section')
        yield kind,data[start:end]
        pos=end

def core_exports(data):
    names=set()
    for kind,payload in sections(data):
        if kind!=7:continue
        count,pos=number(payload,0)
        if count>100000:raise ValueError('Unreasonable exports')
        for _ in range(count):
            length,pos=number(payload,pos);end=pos+length
            if end>=len(payload):raise ValueError('Truncated export')
            name=payload[pos:end].decode('utf-8');kind=payload[end]
            _,pos=number(payload,end+1)
            if kind==0:names.add(name)
        if pos!=len(payload):raise ValueError('Malformed export section')
    return names

def modules(data,depth=0):
    if depth>8:raise ValueError('Component nesting too deep')
    if data.startswith(CORE):return [core_exports(data)]
    if not data.startswith(COMPONENT):raise ValueError('Not a core module/component')
    result=[]
    for kind,payload in sections(data):
        if kind in (1,4):result.extend(modules(payload,depth+1))
    return result

def check_async_component(data):
    for names in modules(data):
        entries=['[async-lift]'+PREFIX+m for m in METHODS]
        callbacks=['[callback][async-lift]'+PREFIX+m for m in METHODS]
        if all(n in names for n in entries+callbacks):
            return {'abi':'receiver_callbacks_explicit_async','task_entries':entries,'task_callbacks':callbacks,
                    'boundary':'ABI presence only; host runtime, permissions and Bluetooth unverified'}
    raise ValueError('Receiver callbacks lack explicit async task entry/callback exports')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('component');args=parser.parse_args()
    p=Path(args.component)
    data=zipfile.ZipFile(p).read('imus5_receiver.wasm') if p.suffix=='.abp' else p.read_bytes()
    print(json.dumps(check_async_component(data),indent=2))
