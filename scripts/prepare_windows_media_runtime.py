"""Bundle the pinned compiler runtime required by the Windows media tools."""
import argparse
import hashlib
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'https://github.com/mstorsjo/llvm-mingw/releases/download/20261117/llvm-mingw-20261117-ucrt-ubuntu-22.04-x86_64.tar.xz'
SHA256 = 'e7a15a49a2ea95e9f3d8a9d0cfabe5052a4b10fb4777cc54de5a8c27b64bb701'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--media-dir', type=Path, required=True)
    args = parser.parse_args()
    media = args.media_dir.resolve()
    if not media.is_relative_to(ROOT) or not (media/'bin/ffmpeg.exe').is_file():
        parser.error('Select the built media directory inside the checkout.')
    notices = media/'source/compiler-runtime-notices'
    notices.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='runtime-', dir=media.parent) as folder:
        archive = Path(folder)/'compiler.tar.xz'
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open('wb') as output:
            shutil.copyfileobj(response, output)
        with archive.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != SHA256:
                raise ValueError('Compiler runtime archive checksum mismatch')
        copied = []
        license_count = 0
        with tarfile.open(archive) as bundle:
            for entry in bundle.getmembers():
                if not entry.isfile():
                    continue
                name = Path(entry.name).name
                if '/x86_64-w64-mingw32/bin/' in entry.name and name in ('libc++.dll', 'libunwind.dll'):
                    destination = media/'bin'/name
                    copied.append(name)
                elif name.upper().startswith(('LICENSE', 'COPYING')):
                    destination = notices/entry.name.replace('/', '__')
                    license_count += 1
                else:
                    continue
                with bundle.extractfile(entry) as source, destination.open('wb') as target:
                    shutil.copyfileobj(source, target)
        if 'libc++.dll' not in copied or not license_count:
            raise ValueError('The compiler runtime or its license notices are missing')
    shutil.copy2(__file__, notices/'prepare_windows_media_runtime.py')
    print('Bundled compiler runtime and license notices. '+', '.join(copied))


if __name__ == '__main__':
    main()
