"""Extend the existing phone vector with a round background; originals stay untouched.

Render the generated SVG at 192px with a browser, preserving transparent corners.
"""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
from export_phone_icon import svg_source

def round_svg():
    root=ET.fromstring(svg_source())
    first=list(root)[0]
    assert first.get('fill')=='#176B6D' and first.get('d').startswith('M12,2L36,2'), 'Unexpected base icon'
    root.remove(first)
    root.insert(0,ET.Element('{http://www.w3.org/2000/svg}circle',{'cx':'24','cy':'24','r':'24','fill':'#176B6D'}))
    ET.register_namespace('','http://www.w3.org/2000/svg')
    return ET.tostring(root,encoding='unicode')+'\n'

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(round_svg(),encoding='utf-8')
