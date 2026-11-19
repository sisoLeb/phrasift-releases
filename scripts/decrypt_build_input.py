"""Decrypt the owner-approved source archive inside a hosted build job."""
import io
import os
from pathlib import Path
import re
import sys
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


version = sys.argv[1] if len(sys.argv) > 1 else '0.6.1'
if not re.fullmatch(r'\d+\.\d+\.\d+', version):
    raise ValueError('Expected a numeric desktop release version')
name = 'source.enc' if version == '0.6.1' else f'source-{version}.enc'
data = (Path('build-input') / name).read_bytes()
key = bytes.fromhex(os.environ.pop('SOURCE_KEY'))
plain = AESGCM(key).decrypt(data[:12], data[12:], f'Phrasift-build-{version}'.encode())
destination = Path('private-source').resolve()
with zipfile.ZipFile(io.BytesIO(plain)) as bundle:
    for member in bundle.infolist():
        if not (destination / member.filename).resolve().is_relative_to(destination):
            raise ValueError('Source entry escaped the build directory')
    bundle.extractall(destination)
print('Private build input decrypted.')
