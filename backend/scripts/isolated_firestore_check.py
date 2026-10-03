"""Explicit test credentials only; no ADC or production configuration fallback."""
import argparse
import json
import os
import re
from pathlib import Path

PRODUCTION_PROJECT = 'kbo-data-ai-assistant'
ALLOWED_COLLECTIONS = {'data', 'data_deletions', 'sync_control', 'retry_probe'}


def validate_target(project, credential_project):
    if project == PRODUCTION_PROJECT or credential_project == PRODUCTION_PROJECT:
        raise ValueError('Production project is forbidden')
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', project or ''):
        raise ValueError('Invalid project ID')
    if 'test' not in project.split('-'):
        raise ValueError('Use a dedicated project with a test token in its ID')
    if project != credential_project:
        raise ValueError('Requested project and service-account project differ')


def connect(project, credential_path):
    # Validate the credential identity BEFORE importing application modules or
    # constructing a network client. Never print the credential contents/path.
    payload = json.loads(Path(credential_path).read_text(encoding='utf-8-sig'))
    validate_target(project, payload.get('project_id'))
    if payload.get('type') != 'service_account':
        raise ValueError('A dedicated test service account is required')
    if os.environ.get('FIRESTORE_EMULATOR_HOST'):
        raise ValueError('This command targets a real isolated Firebase project, not an emulator')
    from google.oauth2 import service_account
    from google.cloud import firestore
    credentials = service_account.Credentials.from_service_account_info(payload)
    client = firestore.Client(project=project, credentials=credentials)
    if client.project != project:
        raise ValueError('Resolved client project differs')
    return client


class ScopedClient:
    """Test functions can reach only unique per-run collections in the test project."""
    def __init__(self, client, project, prefix):
        validate_target(project, client.project)
        if not re.fullmatch(r'kbo_it_[a-f0-9]{12}_[a-z0-9_]+', prefix):
            raise ValueError('Invalid test namespace')
        self.client, self.project, self.prefix = client, project, prefix

    def collection(self, name):
        validate_target(self.project, self.client.project)
        if name not in ALLOWED_COLLECTIONS:
            raise ValueError('Collection outside test allowlist')
        return self.client.collection(f'{self.prefix}_{name}')

    def transaction(self, **kwargs):
        validate_target(self.project, self.client.project)
        return self.client.transaction(**kwargs)

    def get_all(self, references, **kwargs):
        validate_target(self.project, self.client.project)
        for reference in references:
            if reference.path.split('/')[0] not in {f'{self.prefix}_{name}' for name in ALLOWED_COLLECTIONS}:
                raise ValueError('Reference outside test namespace')
            if reference._client.project != self.project:
                raise ValueError('Reference belongs to another project')
        return self.client.get_all(references, **kwargs)


def main():
    parser = argparse.ArgumentParser(description='Read-only isolated Firestore safety check')
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--credentials', required=True)
    args = parser.parse_args()
    client = connect(args.project_id, args.credentials)
    # A fixed probe document READ, not a write or a full collection scan.
    client.collection('kbo_test_preflight').document('connectivity').get(timeout=10, retry=None)
    print(json.dumps({'project_id': client.project, 'mode': 'read_only', 'connected': True,
                      'firestore_writes': 0, 'ai_calls': 0}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(f'Isolated check stopped: {type(error).__name__}. No credential details printed.') from None
