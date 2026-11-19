"""Build a reproducible website from tracked templates and verified installers."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import zipfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = {
    'windows': 'Phrasift-{version}-Setup.exe',
    'mac_arm64': 'Phrasift-{version}-macOS-arm64.dmg',
    'mac_x86_64': 'Phrasift-{version}-macOS-x86_64.dmg',
}


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_live_config(path):
    config = json.loads(path.read_text(encoding='utf-8'))
    allowed = {'store_mode', 'store_id', 'product_id', 'variant_ids',
               'pro_variant_ids', 'checkout_url', 'pro_checkout_url', 'configuration_url'}
    if not isinstance(config, dict) or set(config) - allowed or config.get('store_mode') != 'live':
        raise ValueError('Use only verified public live store configuration, never API secrets.')
    if any(type(config.get(k)) is not int or config[k] <= 0 for k in ('store_id', 'product_id')):
        raise ValueError('Complete the live store and product identifiers.')
    variants, pro = config.get('variant_ids'), config.get('pro_variant_ids')
    if (not isinstance(variants, list) or not variants or
            any(type(v) is not int or v <= 0 for v in variants) or
            not isinstance(pro, list) or not pro or any(type(v) is not int or v not in variants for v in pro)):
        raise ValueError('Complete the accepted live variants and Pro mapping.')
    if config.get('configuration_url') != 'https://phrasift.pages.dev/licensing.json':
        raise ValueError('Use the trusted Phrasift public configuration URL.')
    return config


def read_paddle_checkout(path, commercial):
    config = json.loads(path.read_text(encoding='utf-8'))
    mode = 'live' if commercial else 'test'
    if (not isinstance(config, dict) or set(config) != {'mode', 'client_token', 'standard_price_id', 'pro_price_id'}
            or config.get('mode') != mode):
        raise ValueError('Use a Paddle checkout config matching the website build mode.')
    token, standard, pro = config['client_token'], config['standard_price_id'], config['pro_price_id']
    if (not all(isinstance(value, str) for value in (token, standard, pro))
            or not re.fullmatch(mode + r'_[a-zA-Z0-9]+', token)
            or any(not re.fullmatch(r'pri_[a-z0-9]{26}', price) for price in (standard, pro)) or standard == pro):
        raise ValueError('Supply a public Paddle client token and two distinct price IDs.')
    return {'PADDLE_MODE': mode, 'PADDLE_TOKEN': token, 'PADDLE_STANDARD': standard, 'PADDLE_PRO': pro}


def prepare(inputs, artifacts, source, live_config=None, commercial=False, paddle_checkout=None, unsigned=False):
    version = inputs['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Use a numeric major.minor.patch version.')
    base = inputs['release_base']
    url = urlsplit(base)
    if url.scheme != 'https' or url.netloc != 'github.com' or url.query or url.fragment:
        raise ValueError('Installer hosting must use a public HTTPS GitHub release URL.')
    if not url.path.endswith('/releases/download/v' + version):
        raise ValueError('Download URLs must use the selected release version.')
    manifest = json.loads(json.dumps(inputs))
    manifest['channel'] = 'release' if commercial else 'test'
    live = read_live_config(live_config) if live_config else None
    if live and paddle_checkout:
        raise ValueError('Choose one checkout provider.')
    paddle = read_paddle_checkout(paddle_checkout, commercial) if paddle_checkout else None
    if commercial and not live and not paddle:
        raise ValueError('Commercial publication requires verified live product configuration.')
    if live and not live.get('pro_checkout_url'):
        raise ValueError('Complete the live Pro checkout URL before publication.')
    if live:
        manifest['standard_checkout_url'] = live['checkout_url']
        manifest['pro_checkout_url'] = live['pro_checkout_url']
    if paddle:
        manifest['standard_checkout_url'] = 'checkout.html?edition=standard'
        manifest['pro_checkout_url'] = 'checkout.html?edition=pro'
    elif live:
        for field in ['standard_checkout_url', 'pro_checkout_url']:
            checkout = urlsplit(manifest[field])
            if checkout.scheme != 'https' or not checkout.hostname or not checkout.hostname.endswith('.lemonsqueezy.com'):
                raise ValueError('Use HTTPS Lemon Squeezy checkout links.')
    else:
        manifest['standard_checkout_url'] = None
        manifest['pro_checkout_url'] = None
    files = {}
    sums = []
    for platform, pattern in PLATFORMS.items():
        filename = pattern.format(version=version)
        path = artifacts / filename
        if not path.is_file() or path.stat().st_size < 1024:
            raise ValueError('Missing or incomplete installer: ' + str(path))
        digest = sha256(path)
        old = inputs['platforms'][platform]
        if digest != old['sha256'] or path.stat().st_size != old['bytes']:
            raise ValueError('Installer differs from reviewed release input: ' + filename)
        row = {**old, 'filename': filename, 'ready': True,
               'bytes': path.stat().st_size, 'sha256': digest,
               'download_url': base + '/' + filename}
        if commercial:
            evidence_path = path.with_name(filename + ('.build-info.json' if unsigned else '.signing.json'))
            evidence = json.loads(evidence_path.read_text())
            if evidence.get('sha256') != digest or evidence.get('store_mode') != 'live':
                raise ValueError('Missing matching live installer evidence: ' + filename)
            if unsigned:
                if evidence.get('version') != version or evidence.get('configured_store') is not True:
                    raise ValueError('The installer must contain the live configuration for this release: ' + filename)
            else:
                expected = 'authenticode' if platform == 'windows' else 'developer-id-notarized'
                if evidence.get('verified') is not True or evidence.get('kind') != expected:
                    raise ValueError('Missing matching signing evidence: ' + filename)
            if evidence.get('license_provider', 'lemonsqueezy') != ('paddle' if paddle else 'lemonsqueezy'):
                raise ValueError('The installer uses the wrong licensing provider: ' + filename)
        manifest['platforms'][platform] = row
        line = digest + '  ' + filename + '\n'
        files['downloads/' + filename + '.sha256'] = line
        sums.append(line)
    evidence=json.loads((source/'hardware.json').read_text(encoding='utf-8'))
    if evidence.get('version')!=version:
        raise ValueError('Hardware evidence must identify this release version.')
    cpu=evidence['controlled_cpu_test']
    numeric={'CPU_ANALYSIS_SECONDS':'analysis_seconds','CPU_TRANSLATION_SECONDS':'translated_caption_seconds',
             'CPU_RENDER_SECONDS':'captioned_effects_render_seconds','CPU_PEAK_GIB':'peak_process_tree_commit_gib'}
    if any(type(cpu.get(field)) not in (int,float) or not math.isfinite(cpu[field]) or cpu[field]<=0 for field in numeric.values()):
        raise ValueError('Hardware evidence needs positive, finite measured values.')
    has_checkout = bool(paddle or live)
    notice = '' if commercial else (
        'Test checkout only. No real payment will be collected.' if has_checkout
        else 'The free trial is available. License purchases are coming soon.'
    )
    notice_block = f'      <p class="release-notice">{html.escape(notice)}</p>\n' if notice else ''
    values = {'VERSION': version, 'RELEASE_BASE': base,
              'STANDARD_CHECKOUT': manifest['standard_checkout_url'] or '#download',
              'PRO_CHECKOUT': manifest['pro_checkout_url'] or '#download'}
    values.update({
        'MAIN_CTA': 'Buy Phrasift' if commercial else ('Test checkout' if has_checkout else 'Download the free trial'),
        'MAIN_CTA_TARGET': '#pricing' if has_checkout else '#download',
        'SECONDARY_CTA': 'Download installers' if has_checkout else 'Compare editions',
        'SECONDARY_CTA_TARGET': '#download' if has_checkout else '#pricing',
    })
    for edition, label, price in [('STANDARD', 'Standard', '€49.99'), ('PRO', 'Pro', '€99.99')]:
        values[f'{edition}_CTA'] = f'Buy Phrasift {label} — {price}' if commercial else (
            f'Test {label} checkout' if has_checkout else 'Download the free trial'
        )
    values['LICENSE_SERVICE'] = ('Phrasift’s licensing service on Cloudflare' if paddle else
                                 'Lemon Squeezy' if live else 'the licensing service configured in your build')
    values['CHECKOUT_DISCLOSURE'] = (
        'Paddle processes payments and sends payment receipts. Phrasift uses Brevo to send your license key and '
        'download link to the email address you use at checkout. The download page provides installers for Windows, '
        'Mac with Apple Silicon, and Mac with Intel.' if paddle else (
            'Lemon Squeezy processes payments and issues license keys. Customers receive download links and '
            'their unique license key on the order confirmation screen and by email after purchase.' if live else
            'The free trial is available for Windows, Mac with Apple Silicon, and Mac with Intel. '
            'Checkout is currently closed.'
        ))
    if paddle:
        values.update(paddle)
    values.update({token:str(cpu[field]) for token,field in numeric.items()})
    values['MEASURED_VERSION'] = str(evidence.get('measured_release_version', evidence['version']))
    for platform, row in manifest['platforms'].items():
        values['SIZE_' + platform.upper()] = f"{row['bytes'] / 1024**2:.1f}"
    names = ['index.html', 'privacy.html', 'site.js', 'style.css', 'mark.svg', '_headers', 'robots.txt']
    if paddle:
        names.extend(['checkout.html', 'checkout.css', 'checkout.js'])
    for name in names:
        text = (source / name).read_text(encoding='utf-8')
        if name == 'index.html':
            text = text.replace('{{RELEASE_NOTICE_BLOCK}}\n', notice_block)
        if paddle and name == '_headers':
            text = text.replace("script-src 'self';", "script-src 'self' https://cdn.paddle.com;")
            text = text.replace("connect-src 'self';", "connect-src 'self' https://*.paddle.com; frame-src https://*.paddle.com;")
            # Paddle sizes its injected iframe through an inline style attribute.
            text = text.replace("style-src 'self';", "style-src 'self'; style-src-attr 'unsafe-inline';")
        for key, value in values.items():
            text = text.replace('{{' + key + '}}', html.escape(value, quote=True))
        if re.search(r'\{\{[A-Z_]+\}\}', text):
            raise ValueError('Unresolved website placeholder in ' + name)
        files[name] = text
    files['downloads/SHA256SUMS.txt'] = ''.join(sums)
    files['release.json'] = json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'
    files['licensing.json'] = json.dumps({'schema': 1, 'live': live}, indent=2) + '\n'
    files['hardware.json']=json.dumps(evidence,indent=2,ensure_ascii=False)+'\n'
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'website/phrasift/release-input.json')
    parser.add_argument('--artifacts', type=Path, default=ROOT/'dist')
    parser.add_argument('--output', type=Path, help='New output directory; existing builds are preserved.')
    parser.add_argument('--live-config', type=Path)
    parser.add_argument('--paddle-checkout', type=Path)
    parser.add_argument('--commercial', action='store_true')
    parser.add_argument('--unsigned', action='store_true', help='Publish unsigned installers with live build metadata and first-launch disclosures.')
    args = parser.parse_args()
    inputs = json.loads(args.input.read_text(encoding='utf-8'))
    # Validate everything before creating or changing output files.
    files = prepare(inputs, args.artifacts.resolve(), ROOT/'website/phrasift/source', args.live_config, args.commercial, args.paddle_checkout, args.unsigned)
    target = (args.output or ROOT/('build/website-' + inputs['version'])).resolve()
    if not target.is_relative_to(ROOT) or target.exists():
        parser.error('Choose a new output directory inside this workspace.')
    archive = target.with_name(target.name + '.zip')
    if archive.exists():
        parser.error('The output ZIP already exists; choose another output directory.')
    target.mkdir(parents=True)
    for name, content in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='\n')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(files):
            entry = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, files[name].encode('utf-8'))
    archive.with_suffix('.zip.sha256').write_text(sha256(archive)+'  '+archive.name+'\n')
    print(json.dumps({'website_directory': str(target), 'website_zip': str(archive), 'sha256': sha256(archive)}, indent=2))


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(ROOT))
    main()
