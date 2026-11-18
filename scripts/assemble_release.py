"""Assemble verified hosted installers, source materials and the public website."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.prepare_website_live import PLATFORMS, sha256


def main():
    incoming = ROOT / 'incoming'
    output = ROOT / 'dist/release-0.6.1'
    output.mkdir(parents=True)
    manifest_path = ROOT / 'website/phrasift/release-input.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['version'] == '0.6.1'
    for platform, pattern in PLATFORMS.items():
        filename = pattern.format(version=manifest['version'])
        matches = list(incoming.rglob(filename))
        if len(matches) != 1:
            raise ValueError('Expected exactly one '+filename)
        artifact = matches[0]
        info = artifact.with_name(filename+'.build-info.json')
        data = json.loads(info.read_text())
        digest = sha256(artifact)
        if (data.get('sha256') != digest or data.get('version') != '0.6.1'
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
        if data.get('version') != '0.6.1' or data.get('offline_bundled_model') is not True:
            raise ValueError('Missing installed-app validation')
        reports.append(data)
    if len(reports) != 3:
        raise ValueError('Expected the Windows and two native Mac validation reports')
    mac_reports = [data for data in reports if data.get('installed_from_dmg')]
    if {data['architecture'] for data in mac_reports} != {'arm64', 'x86_64'}:
        raise ValueError('Both Mac architectures must pass the installed-DMG check')
    if not any(data.get('installed_executable') for data in reports):
        raise ValueError('Windows installed-app check is missing')

    source_archive = output/'Phrasift-0.6.1-media-sources.zip'
    with zipfile.ZipFile(source_archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for source in incoming.rglob('*-media-sources.zip'):
            bundle.write(source, source.name)
        windows_source = incoming/'windows-media/source'
        if not windows_source.is_dir():
            raise ValueError('Windows media source is missing')
        for source in sorted(windows_source.rglob('*')):
            if source.is_file():
                bundle.write(source, Path('windows')/source.relative_to(windows_source))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    subprocess.run([
        sys.executable, 'scripts/prepare_website_live.py', '--input', str(manifest_path),
        '--artifacts', str(output), '--output', str(ROOT/'build/website-0.6.1-live'),
        '--paddle-checkout', 'release/checkout.json', '--commercial', '--unsigned',
    ], cwd=ROOT, check=True)
    shutil.copy2(ROOT/'build/website-0.6.1-live/downloads/SHA256SUMS.txt', output/'SHA256SUMS.txt')
    shutil.copy2(manifest_path, output/'release-input.json')
    (output/'VALIDATION.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    shutil.copy2(ROOT/'build/website-0.6.1-live.zip', output/'Phrasift-0.6.1-website.zip')
    subprocess.run(['gh', 'release', 'upload', 'v0.6.1', *map(str, sorted(output.iterdir())),
                    '--repo', 'sisoLeb/phrasift-releases', '--clobber'], cwd=ROOT, check=True)
    print('Uploaded verified installers and website to the draft v0.6.1 release.')


if __name__ == '__main__':
    main()
