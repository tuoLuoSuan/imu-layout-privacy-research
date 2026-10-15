"""Inspect a no-permission JS/JSON diagnostic archive; not device acceptance."""
import io
import json
import zipfile

def check_source_format(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if z.testzip() is not None:
            raise ValueError('archive CRC failed')
        names=z.namelist()
        if any(n.endswith(('.jsc','.bin')) for n in names):
            raise ValueError('bytecode or binary template remains in source candidate')
        # Toolkit 2 embeds non-Protobuf layout/style in the page JS module.
        required=['manifest.json','app.js','Probe/index.js']
        if not all(n in names for n in required):
            raise ValueError('required JS/JSON source entry missing')
        m=json.loads(z.read('manifest.json'))
        if m.get('package')!='org.imuresearch.s5start' or m.get('versionName')!='0.0.2' or m.get('versionCode')!=2:
            raise ValueError('unexpected diagnostic package identity')
        if m.get('features')!=[]:
            raise ValueError('startup diagnostic must not declare system capabilities')
        for name in required[1:]:
            if 'export default' not in z.read(name).decode('utf-8'):
                raise ValueError('expected UTF-8 source module wrapper missing')
        return {'version':m['versionName'],'required_source_entries':required,
                'layout_storage':'inline in Probe/index.js; not separate JSON files',
                'bytecode_or_protobuf_entries':[],'features':[],
                'device_launch':'not_verified','entry_sizes':{n:len(z.read(n)) for n in names}}
