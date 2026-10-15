"""Inspect the 0.1.1 source acquisition archive; signature/runtime acceptance are separate."""
import io
import json
import re
import zipfile


def check_acquisition_source(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        if z.testzip() is not None or len(names) != len(set(names)):
            raise ValueError('archive CRC or duplicate entry failure')
        if any(n.lower().endswith(('.jsc', '.bin', '.pem', '.key', '.p12', '.pfx')) for n in names):
            raise ValueError('unexpected binary format or private signing material')
        required = ['manifest.json', 'app.js', 'Probe/index.js']
        if not all(n in names for n in required):
            raise ValueError('required source module missing')
        m = json.loads(z.read('manifest.json'))
        if (m.get('package'), m.get('versionName'), m.get('versionCode')) != ('org.imuresearch.s5probe', '0.1.1', 2):
            raise ValueError('unexpected acquisition candidate identity')
        if sorted(x.get('name', '') for x in m.get('features', [])) != ['system.file', 'system.sensor']:
            raise ValueError('unexpected capability declarations')
        if m.get('minAPILevel') != 2 or m.get('config', {}).get('designWidth') != 466:
            raise ValueError('unexpected API/layout change')
        if any('export default' not in z.read(n).decode('utf-8') for n in required[1:]):
            raise ValueError('source wrapper missing')
        modules = '\n'.join(z.read(n).decode('utf-8') for n in names if n.endswith('.js'))
        if not re.search(r'''["']?app_version["']?\s*:\s*["']0\.1\.1["']''', modules):
            raise ValueError('new export metadata version missing')
        if re.search(r'''["']?app_version["']?\s*:\s*["']0\.1\.0["']''', modules):
            raise ValueError('stale export metadata version remains')
        return {'package': m['package'], 'version': m['versionName'], 'version_code': m['versionCode'],
                'features': [x['name'] for x in m['features']], 'bytecode_or_protobuf_entries': [],
                'required_source_entries': required, 'export_metadata_version': '0.1.1',
                'zip_crc': 'passed', 'device_launch': 'not_verified', 'sensor_data': 'not_obtained'}
