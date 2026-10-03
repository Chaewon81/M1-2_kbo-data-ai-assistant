"""Use the configured Git credential helper; print repository metadata, never tokens."""
import json
import os
import subprocess
import sys
from urllib.request import Request, urlopen

OWNER, REPOSITORY = 'Chaewon81', 'M1-2_kbo-data-ai-assistant'


def main():
    environment = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'}
    result = subprocess.run(['git', 'credential', 'fill'],
                            input=f'protocol=https\nhost=github.com\npath={OWNER}/{REPOSITORY}.git\n\n',
                            text=True, capture_output=True, env=environment, check=True)
    fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    token = fields.get('password')
    if not token:
        raise RuntimeError('No configured GitHub credential')
    request = Request(f'https://api.github.com/repos/{OWNER}/{REPOSITORY}',
                      headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                               'User-Agent': 'kbo-upload-safety-check'})
    with urlopen(request, timeout=20) as response:
        repository = json.load(response)
    safe = {'full_name': repository['full_name'], 'private': repository['private'],
            'can_push': repository.get('permissions', {}).get('push', False),
            'default_branch': repository.get('default_branch')}
    print(json.dumps(safe))
    allow_public = '--allow-public' in sys.argv[1:]
    if (repository['full_name'].lower() != f'{OWNER}/{REPOSITORY}'.lower()
            or not safe['can_push']
            or (not safe['private'] and not allow_public)):
        raise SystemExit(2)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(f'Repository check failed ({type(error).__name__}); no credentials printed.') from None
