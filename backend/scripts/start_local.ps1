# Local CSV mode. Default: Mock; -AiMode gpt: OpenAI GPT; configured: legacy provider settings.
param([ValidateSet('mock', 'gpt', 'configured')][string]$AiMode = 'mock')
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location -LiteralPath $projectRoot
$gameFiles = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'data/games') -File |
    Where-Object { $_.Name -match '^game_results_\d{4}\.csv$' } | Sort-Object Name
$pitcherFiles = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'data/pitchers') -File |
    Where-Object { $_.Name -match '^pitcher_stats_\d{4}\.csv$' } | Sort-Object Name
if (!$gameFiles -or !$pitcherFiles) { throw 'Season CSV files are required.' }
$env:DATA_PATHS = ($gameFiles.FullName -join ';')
$env:PITCHER_DATA_PATHS = ($pitcherFiles.FullName -join ';')
$env:GOOGLE_APPLICATION_CREDENTIALS = $null
$env:LOCAL_CSV_MODE = 'true'
$env:REQUIRE_FIRESTORE = 'false'
$env:AUTO_SYNC_ENABLED = 'false'
$env:OPENAI_MOCK_MODE = if ($AiMode -eq 'mock') { 'true' } else { 'false' }
if ($AiMode -eq 'gpt') {
    $env:AI_PROVIDER = 'openai'
    $env:OPENAI_MODEL = 'gpt-4o-mini'
}
$pythonExecutable = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $pythonExecutable)) { throw 'Create the project .venv first.' }
Write-Host "Local CSV mode: $($gameFiles.Count) game seasons, $($pitcherFiles.Count) pitcher seasons."
Write-Host "AI mode: $AiMode"
& $pythonExecutable -m uvicorn backend.main:app --reload
