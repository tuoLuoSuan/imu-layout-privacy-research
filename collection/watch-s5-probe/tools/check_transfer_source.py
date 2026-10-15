"""Inspect 0.3.1 archive identity/capabilities; runtime and signature checks are separate."""
import io
import json
import re
import zipfile

def check_transfer_source(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names=archive.namelist()
        if archive.testzip() is not None or len(names)!=len(set(names)):
            raise ValueError('CRC/duplicate entry failure')
        if any(n.lower().endswith(('.jsc','.bin','.pem','.key','.p12','.pfx')) for n in names):
            raise ValueError('Unexpected format/private material')
        if not all(n in names for n in ['manifest.json','app.js','Probe/index.js','common/icon.png']):
            raise ValueError('Required module missing')
        manifest=json.loads(archive.read('manifest.json'))
        if (manifest.get('package'),manifest.get('versionName'),manifest.get('versionCode'))!=('org.imuresearch.s5probe','0.3.1',5):
            raise ValueError('Wrong transfer profile identity')
        if sorted(f['name'] for f in manifest.get('features',[]))!=['system.file','system.interconnect','system.sensor']:
            raise ValueError('Unexpected capability declarations')
        source='\n'.join(archive.read(n).decode('utf-8') for n in names if n.endswith('.js'))
        if 'S5TX1' not in source or 'S5ACK1' not in source or not re.search(r'''["']?app_version["']?\s*:\s*["']0\.3\.1["']''',source):
            raise ValueError('Wrong transport or metadata module')
        return {'version':'0.3.1','code':5,'source_format':'passed','capabilities':sorted(f['name'] for f in manifest['features']),
                'real_wireless_transfer':'not_verified','device_runtime':'not_verified'}
