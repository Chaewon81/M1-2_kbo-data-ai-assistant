# Submission: OpenAI GPT + required Firestore. Credentials are loaded from root .env/environment.
param([switch]$DisableAutoSync)
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location -LiteralPath $projectRoot
$env:LOCAL_CSV_MODE = 'false'
$env:REQUIRE_FIRESTORE = 'true'
$env:AUTO_SYNC_ENABLED = if ($DisableAutoSync) { 'false' } else { 'true' }
$env:OPENAI_MOCK_MODE = 'false'
$env:AI_PROVIDER = 'openai'
$env:OPENAI_MODEL = 'gpt-4o-mini'
$pythonExecutable = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $pythonExecutable)) { throw 'Create the project .venv first.' }
Write-Host 'Submission mode: OpenAI GPT + required Firestore (no memory fallback).'
& $pythonExecutable -m uvicorn backend.main:app --reload
