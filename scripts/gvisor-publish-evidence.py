#!/usr/bin/env python3
"""Turn a raw local evidence directory into a redacted bundle that may be committed.

Scrubbing inside the harness is not enough: the PID runner pipes shell and probe
output straight to a file, and runsc writes its own debug logs, so neither passes
through Matrix.write/log. This walks every file in the raw directory instead, so
the redaction boundary is "what gets published", not "what the harness wrote".

Raw evidence stays outside the repo. Hashes are computed over the published
files, so bundle-sha256.json describes exactly what reviewers can see.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gvisor_redact', ROOT / 'scripts/gvisor_redact.py')
redact_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redact_module)

# Published bundles are text. Anything else is copied byte for byte and reported,
# because this tool cannot mask inside an opaque format.
TEXT_SUFFIXES = {'.json', '.jsonl', '.txt', '.log', '.md', '.yaml', '.yml', '.csv', '.tsv', ''}
HASH_FILE = 'bundle-sha256.json'


def scrub_text(redactor, text, suffix):
    """Structure-aware for JSON so secret-named fields are masked, text otherwise."""
    if suffix == '.json':
        try:
            return json.dumps(redactor.scrub(json.loads(text)), indent=2, ensure_ascii=False) + '\n'
        except ValueError:
            pass
    if suffix == '.jsonl':
        lines, ok = [], True
        for line in text.splitlines():
            if not line.strip():
                lines.append(line)
                continue
            try:
                lines.append(json.dumps(redactor.scrub(json.loads(line)), ensure_ascii=False))
            except ValueError:
                ok = False
                break
        if ok:
            return '\n'.join(lines) + ('\n' if text.endswith('\n') else '')
    return redactor.text(text)


def publish(raw, out, redactor):
    report = {'files': 0, 'binary': [], 'leaks': [], 'hashes': {}}
    for source in sorted(p for p in raw.rglob('*') if p.is_file()):
        relative = source.relative_to(raw)
        if relative.name == HASH_FILE:
            continue
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if source.suffix.lower() in TEXT_SUFFIXES:
            try:
                target.write_text(scrub_text(redactor, data.decode('utf-8'), source.suffix.lower()),
                                  encoding='utf-8')
            except UnicodeDecodeError:
                shutil.copyfile(source, target)
                report['binary'].append(str(relative))
        else:
            shutil.copyfile(source, target)
            report['binary'].append(str(relative))
        published = target.read_bytes()
        # Belt and braces: a registered secret must not survive in any published byte.
        for secret in redactor.values:
            if secret.encode('utf-8') in published:
                report['leaks'].append({'file': str(relative), 'secret_length': len(secret)})
        report['hashes'][str(relative)] = hashlib.sha256(published).hexdigest()
        report['files'] += 1
    (out / HASH_FILE).write_text(json.dumps(report['hashes'], indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, required=True, help='Local directory holding unredacted evidence')
    parser.add_argument('--out', type=Path, required=True, help='Bundle to create; must not exist')
    parser.add_argument('--redact', action='append', metavar='VALUE',
                        help='Literal secret to mask. Repeatable. A file keeps it out of shell history.')
    parser.add_argument('--redact-file', type=Path, metavar='PATH', help='One literal secret per line')
    args = parser.parse_args()
    if not args.raw.is_dir():
        parser.error('--raw must be an existing directory')
    if args.out.exists():
        parser.error('--out already exists; publish into a fresh directory')

    redactor = redact_module.Redactor().add_from_environ()
    for secret in args.redact or []:
        redactor.add(secret)
    if args.redact_file:
        for line in args.redact_file.read_text().splitlines():
            redactor.add(line.strip())

    args.out.mkdir(parents=True)
    report = publish(args.raw, args.out, redactor)
    print(json.dumps({'published_files': report['files'], 'copied_unscrubbed': report['binary'],
                      'leaks': report['leaks'], 'registered_secrets': len(redactor.values),
                      'note': 'Redaction reduces accidental disclosure; a human must still review.'},
                     indent=2, ensure_ascii=False))
    if report['leaks']:
        print('A registered secret survived. Do not commit this bundle.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
