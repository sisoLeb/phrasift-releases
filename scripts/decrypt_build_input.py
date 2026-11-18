"""Decrypt the owner-approved source archive inside a hosted build job."""
import io
import os
from pathlib import Path
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


data = Path('build-input/source.enc').read_bytes()
key = bytes.fromhex(os.environ.pop('SOURCE_KEY'))
plain = AESGCM(key).decrypt(data[:12], data[12:], b'Phrasift-build-0.6.1')
destination = Path('private-source').resolve()
with zipfile.ZipFile(io.BytesIO(plain)) as bundle:
    for member in bundle.infolist():
        if not (destination / member.filename).resolve().is_relative_to(destination):
            raise ValueError('Source entry escaped the build directory')
    bundle.extractall(destination)
print('Private build input decrypted.')
