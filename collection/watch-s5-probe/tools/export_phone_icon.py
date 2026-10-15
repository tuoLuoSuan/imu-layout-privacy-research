"""Convert the unchanged Android vector to SVG; render that SVG to PNG with a browser."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
ANDROID = '{http://schemas.android.com/apk/res/android}'
PHONE_ICON = ROOT / 'collection/phone-imu-recorder/app/src/main/res/drawable/ic_app.xml'


def svg_source():
    source = ET.parse(PHONE_ICON).getroot()
    svg = ET.Element('svg', {'xmlns': 'http://www.w3.org/2000/svg', 'width': '192', 'height': '192',
                            'viewBox': '0 0 ' + source.get(ANDROID + 'viewportWidth') + ' ' + source.get(ANDROID + 'viewportHeight')})
    mapping = {'pathData': 'd', 'fillColor': 'fill', 'strokeColor': 'stroke', 'strokeWidth': 'stroke-width',
               'strokeLineCap': 'stroke-linecap', 'strokeLineJoin': 'stroke-linejoin'}
    for path in source:
        assert path.tag == 'path', 'only the current reviewed vector paths are supported'
        attrs = {dest: path.get(ANDROID + key) for key, dest in mapping.items() if path.get(ANDROID + key) is not None}
        if attrs.get('fill') == '@android:color/transparent':
            attrs['fill'] = 'none'
        ET.SubElement(svg, 'path', attrs)
    return ET.tostring(svg, encoding='unicode') + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg_source(), encoding='utf-8')
