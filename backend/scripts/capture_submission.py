"""Launch headless capture without exposing the demonstration key in CLI arguments."""
import argparse
import os
from pathlib import Path
import subprocess

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('public', 'authenticated', 'crud'), default='public')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / '.env')
    key = os.getenv('DEMO_ACCESS_KEY', '').strip()
    if args.mode != 'public' and not key:
        raise SystemExit('Set DEMO_ACCESS_KEY privately in the root .env first.')
    child_env = {**os.environ, 'CAPTURE_DEMO_KEY': key}
    # Other secrets are not needed by the browser child.
    for name in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'GOOGLE_APPLICATION_CREDENTIALS', 'FIREBASE_SERVICE_ACCOUNT_JSON'):
        child_env.pop(name, None)
    result = subprocess.run(['node', str(root / 'backend/scripts/capture_submission.cjs'), args.mode],
                            cwd=root, env=child_env)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
