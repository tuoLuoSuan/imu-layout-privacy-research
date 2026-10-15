"""Offline archive contract; device/runtime acceptance is explicitly separate."""
import io
import json
import re
import zipfile


def check_research_source(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if archive.testzip() is not None or len(names) != len(set(names)):
            raise ValueError('CRC or duplicate archive entry')
        if any(n.lower().endswith(('.jsc', '.bin', '.pem', '.key', '.p12', '.pfx')) for n in names):
            raise ValueError('unexpected bytecode, protobuf or signing material')
        if not all(n in names for n in ('manifest.json', 'app.js', 'Probe/index.js', 'common/icon.png')):
            raise ValueError('source module or icon missing')
        manifest = json.loads(archive.read('manifest.json'))
        if (manifest.get('package'), manifest.get('versionName'), manifest.get('versionCode')) != ('org.imuresearch.s5probe', '0.3.0', 4):
            raise ValueError('research candidate identity mismatch')
        if sorted(f.get('name') for f in manifest.get('features', [])) != ['system.file', 'system.sensor']:
            raise ValueError('unexpected features')
        if manifest.get('minAPILevel') != 2 or manifest.get('config', {}).get('designWidth') != 466:
            raise ValueError('API or logical width mismatch')
        source = '\n'.join(archive.read(n).decode('utf-8') for n in names if n.endswith('.js'))
        if not re.search(r'''["']?app_version["']?\s*:\s*["']0\.3\.0["']''', source):
            raise ValueError('research metadata version missing')
        if 'IMUS5' not in source or 'queue_overflow' not in source or 'callback_epoch_ms' not in source:
            raise ValueError('research stream/export core missing')
        return {'version':'0.3.0','version_code':4,'source_format':'JavaScript_JSON', 'zip_crc':'passed',
                'features':['system.sensor','system.file'],'hardware_acceptance':'not_performed'}
