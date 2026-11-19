"""Assemble verified hosted installers, source materials and the public website."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.prepare_website_live import PLATFORMS, sha256


def main():
    incoming = ROOT / 'incoming'
    manifest_path = ROOT / 'website/phrasift/release-input.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    version = manifest['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Expected a numeric desktop release version')
    output = ROOT / 'dist' / f'release-{version}'
    output.mkdir(parents=True)
    website = ROOT / 'build' / f'website-{version}-live'
    for platform, pattern in PLATFORMS.items():
        filename = pattern.format(version=manifest['version'])
        matches = list(incoming.rglob(filename))
        if len(matches) != 1:
            raise ValueError('Expected exactly one '+filename)
        artifact = matches[0]
        info = artifact.with_name(filename+'.build-info.json')
        data = json.loads(info.read_text())
        digest = sha256(artifact)
        if (data.get('sha256') != digest or data.get('version') != version
                or data.get('store_mode') != 'live' or data.get('license_provider') != 'paddle'):
            raise ValueError('Build metadata mismatch for '+filename)
        checksum = artifact.with_name(filename+'.sha256')
        if checksum.read_text().split()[0] != digest:
            raise ValueError('Checksum mismatch for '+filename)
        for path in (artifact, info, checksum):
            shutil.copy2(path, output/path.name)
        manifest['platforms'][platform].update(
            filename=filename, bytes=artifact.stat().st_size, sha256=digest, ready=True,
        )

    reports = []
    for path in incoming.rglob('report.json'):
        data = json.loads(path.read_text())
        if data.get('version') != version or data.get('offline_bundled_model') is not True:
            raise ValueError('Missing installed-app validation')
        reports.append(data)
    if len(reports) != 3:
        raise ValueError('Expected the Windows and two native Mac validation reports')
    mac_reports = [data for data in reports if data.get('installed_from_dmg')]
    if {data['architecture'] for data in mac_reports} != {'arm64', 'x86_64'}:
        raise ValueError('Both Mac architectures must pass the installed-DMG check')
    if not any(data.get('installed_executable') for data in reports):
        raise ValueError('Windows installed-app check is missing')

    source_archives = sorted(incoming.rglob('*-media-sources.zip'))
    expected_sources = {f'Phrasift-{version}-{platform}-media-sources.zip'
                        for platform in ('Windows', 'macOS-arm64', 'macOS-x86_64')}
    if len(source_archives) != 3 or {p.name for p in source_archives} != expected_sources:
        raise ValueError('Expected corresponding media sources for each installer')
    source_archive = output/f'Phrasift-{version}-media-sources.zip'
    with zipfile.ZipFile(source_archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for source in source_archives:
            bundle.write(source, source.name)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    subprocess.run([
        sys.executable, 'scripts/prepare_website_live.py', '--input', str(manifest_path),
        '--artifacts', str(output), '--output', str(website),
        '--paddle-checkout', 'release/checkout.json', '--commercial', '--unsigned',
    ], cwd=ROOT, check=True)
    shutil.copy2(website/'downloads/SHA256SUMS.txt', output/'SHA256SUMS.txt')
    shutil.copy2(manifest_path, output/'release-input.json')
    (output/'VALIDATION.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    shutil.copy2(website.with_name(website.name+'.zip'),
                 output/f'Phrasift-{version}-website.zip')
    subprocess.run(['gh', 'release', 'upload', f'v{version}', *map(str, sorted(output.iterdir())),
                    '--repo', 'sisoLeb/phrasift-releases', '--clobber'], cwd=ROOT, check=True)
    print(f'Uploaded verified installers and website to the draft v{version} release.')


if __name__ == '__main__':
    main()
