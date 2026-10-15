"""Software-only archive and outer-signature inspection, not device acceptance."""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'dist/org.imuresearch.s5probe.release.0.1.0.rpk'
SIGN = Path(os.environ.get('S5_SIGN_DIR') or (ROOT / 'sign' if (ROOT / 'sign/private.pem').exists() else ROOT.parent / 'band9pro-probe/sign'))


def u32(data, index):
    return struct.unpack_from('<I', data, index)[0]


def check_signature(data):
    # Format inspected in aiot-toolkit 2.0.5 SignUtil.js.
    eocd = data.rfind(b'PK\x05\x06')
    assert eocd >= 0
    central = u32(data, eocd + 16)
    assert data[central-16:central].rstrip(b'\0') == b'RPK Sig Block 42'
    block_size = struct.unpack_from('<Q', data, central - 24)[0]
    start = central - block_size - 8
    assert start >= 0 and struct.unpack_from('<Q', data, start)[0] == block_size
    pos = start + 8
    signed_data = signature = public_key = None
    while pos < central - 24:
        size = struct.unpack_from('<Q', data, pos)[0]
        identifier = u32(data, pos + 8)
        if identifier == 0x01000101:
            cursor = pos + 12
            cursor += 8  # signers size + signer size
            length = u32(data, cursor); cursor += 4
            signed_data = data[cursor:cursor + length]; cursor += length
            signatures_length = u32(data, cursor); cursor += 4
            signatures_end = cursor + signatures_length
            assert u32(data, cursor + 4) == 0x0103
            signature_length = u32(data, cursor + 8)
            signature = data[cursor + 12:cursor + 12 + signature_length]
            cursor = signatures_end
            length = u32(data, cursor); cursor += 4
            public_key = serialization.load_der_public_key(data[cursor:cursor + length])
        pos += 8 + size
    assert signed_data and signature and public_key
    public_key.verify(signature, signed_data, padding.PKCS1v15(), hashes.SHA256())
    digest_list_length = u32(signed_data, 0)
    assert u32(signed_data, 8) == 0x0103 and u32(signed_data, 12) == 32
    embedded_digest = signed_data[16:48]
    cursor = 4 + digest_list_length + 4
    certificate_length = u32(signed_data, cursor); cursor += 4
    certificate = x509.load_der_x509_certificate(signed_data[cursor:cursor + certificate_length])
    pem = x509.load_pem_x509_certificate((SIGN / 'certificate.pem').read_bytes())
    assert certificate.fingerprint(hashes.SHA256()) == pem.fingerprint(hashes.SHA256())
    assert certificate.public_key().public_numbers() == public_key.public_numbers()
    footer = bytearray(data[eocd:])
    struct.pack_into('<I', footer, 16, start)
    sections = [data[:start], data[central:eocd], bytes(footer)]
    digests = [hashlib.sha256(b'\xa5' + struct.pack('<I', len(part)) + part).digest() for part in sections]
    actual = hashlib.sha256(b'\x5a' + struct.pack('<I', 3) + b''.join(digests)).digest()
    assert actual == embedded_digest, 'RPK content digest differs from signed digest'
    return certificate.fingerprint(hashes.SHA256()).hex()


def main():
    data = TARGET.read_bytes()
    fingerprint = check_signature(data)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['package'] == 'org.imuresearch.s5probe'
        assert {feature['name'] for feature in manifest['features']} == {'system.sensor', 'system.file'}
        assert all(name in names for name in ['app.jsc', 'Probe/index.jsc',
                                               'Probe/index.template.bin', 'Probe/index.style.bin'])
        assert not any(name.endswith('private.pem') for name in names)
    report = {'artifact': TARGET.name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
              'zip_crc': 'passed', 'outer_rsa_sha256_signature': 'passed',
              'signed_package_content_digest': 'passed', 'local_certificate_match': 'passed',
              'certificate_sha256': fingerprint, 'required_jsc_protobuf_files': 'passed',
              'feature_declarations': ['system.sensor', 'system.file'],
              'private_key_in_archive': False, 'device_validation': 'not performed'}
    (ROOT / 'dist/package-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
