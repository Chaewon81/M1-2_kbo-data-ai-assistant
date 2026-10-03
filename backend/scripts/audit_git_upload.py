"""Inspect Git upload candidates without printing secrets or matched source text.

Defense in depth, not a guarantee against every possible secret/image leak.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = (
    ('OPENAI_KEY', re.compile(r'\bsk-[A-Za-z0-9_-]{24,}')),
    ('GITHUB_TOKEN', re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})')),
    ('GOOGLE_API_KEY', re.compile(r'\bAIza[A-Za-z0-9_-]{30,}')),
    ('AWS_ACCESS_KEY', re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('PRIVATE_KEY', re.compile(r'^\s*-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', re.MULTILINE)),
    ('SERVICE_ACCOUNT_JSON', re.compile(r'"type"\s*:\s*"service_account"')),
    ('JSON_PRIVATE_KEY', re.compile(r'"private_key"\s*:\s*"[^"\r\n]{24,}')),
    ('CREDENTIAL_URL', re.compile(r'https?://[^\s/@:]+:[^\s/@]{24,}@')),
)
TEXT_SUFFIXES = {'.py', '.js', '.cjs', '.html', '.css', '.md', '.csv', '.json', '.txt', '.ps1', '.toml', '.yml', '.yaml'}


def git(*args):
    return subprocess.check_output(['git', '-c', f'safe.directory={ROOT.as_posix()}', *args], cwd=ROOT)


def known_local_secrets():
    values = set()
    for path in (ROOT / '.env', ROOT / 'backend/.env'):
        if not path.is_file():
            continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            name, sep, value = line.partition('=')
            if sep and re.search(r'(KEY|TOKEN|SECRET|PASSWORD)', name.upper()):
                value = value.strip().strip('"\'')
                if len(value) >= 16:
                    values.add(value)
    return values


def audit(staged=False):
    data = git('ls-files', '--cached', '-z') if staged else git('ls-files', '--others', '--exclude-standard', '-z')
    paths = sorted(set(p.decode('utf-8') for p in data.split(b'\0') if p))
    secrets = known_local_secrets()
    findings, text_count, binary = [], 0, []
    for relative in paths:
        path = ROOT / relative
        name = path.name.lower()
        if name.startswith('.env') and name != '.env.example' or path.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.har'} or 'adminsdk' in name:
            findings.append({'file': relative, 'rule': 'FORBIDDEN_UPLOAD_FILE'})
            continue
        raw = git('show', ':' + relative) if staged else path.read_bytes()
        if path.suffix.lower() not in TEXT_SUFFIXES and name not in {'.gitignore', '.gitkeep', '.env.example'}:
            binary.append(relative)
            continue
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            findings.append({'file': relative, 'rule': 'TEXT_ENCODING_REQUIRES_REVIEW'})
            continue
        text_count += 1
        for rule, pattern in RULES:
            for match in pattern.finditer(content):
                findings.append({'file': relative, 'line': content.count('\n', 0, match.start()) + 1, 'rule': rule})
        for value in secrets:
            if value in content:
                findings.append({'file': relative, 'rule': 'LOCAL_SECRET_VALUE_FOUND'})
    return {'mode': 'staged' if staged else 'untracked_candidates', 'file_count': len(paths),
            'text_files_scanned': text_count, 'binary_files_require_visual_review': binary,
            'findings': findings, 'status': 'PASS' if not findings else 'BLOCKED'}


def main():
    parser = argparse.ArgumentParser(description='Git upload secret scan (matched values never printed)')
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    report = audit(args.staged)
    print(json.dumps(report, ensure_ascii=True))
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
