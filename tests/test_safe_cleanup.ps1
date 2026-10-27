$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$script = Join-Path $repo 'scripts\safe_cleanup.ps1'
$fixture = Join-Path $repo ('.test-work\' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixture | Out-Null
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($script,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
# Load the real path guards without running the production entrypoint.
$ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]},$false) |
    Where-Object Name -in @('Assert-PlainPath','Assert-Under') |
    ForEach-Object { . ([scriptblock]::Create($_.Extent.Text)) }
$allowed = Join-Path $fixture 'allowed'
New-Item -ItemType Directory -Path $allowed | Out-Null
$null = Assert-Under (Join-Path $allowed 'file') $allowed
foreach ($bad in @($allowed,(Join-Path $fixture 'allowed-other\file'),(Join-Path $allowed '..\outside'))) {
    $refused = $false
    try { $null = Assert-Under $bad $allowed } catch { $refused = $true }
    if (-not $refused) { throw "Guard accepted outside path: $bad" }
}
$outside = Join-Path $fixture 'outside'
New-Item -ItemType Directory -Path $outside | Out-Null
$junction = Join-Path $allowed 'link'
New-Item -ItemType Junction -Path $junction -Target $outside | Out-Null
$refused = $false
try { $null = Assert-Under (Join-Path $junction 'file') $allowed } catch { $refused = $true }
if (-not $refused) { throw 'Guard followed a junction.' }
$plan = Join-Path $fixture 'empty.csv'
'"Category","Path","Length","LastWriteUtc","CreationUtc"' | Set-Content -LiteralPath $plan
$hash = (Get-FileHash -LiteralPath $plan -Algorithm SHA256).Hash
$pwsh = (Get-Process -Id $PID).Path
$result = & $pwsh -NoProfile -File $script -Mode Apply -PlanPath $plan -ReviewedPlanSha256 ('0'*64) -ReportDirectory (Join-Path $fixture 'bad-hash') -BackupDirectory (Join-Path $fixture 'bad-backup') 2>&1
if ($LASTEXITCODE -eq 0 -or (Test-Path -LiteralPath (Join-Path $fixture 'bad-backup'))) { throw 'Invalid plan hash did not fail closed.' }
$outsidePlan = Join-Path $fixture 'outside.csv'
[pscustomobject]@{Category='D3DSCache';Path=(Join-Path $fixture 'personal.txt');Length=0;LastWriteUtc='2000-01-01T00:00:00Z';CreationUtc='2000-01-01T00:00:00Z'} |
    Export-Csv -LiteralPath $outsidePlan -NoTypeInformation
$outsideHash = (Get-FileHash -LiteralPath $outsidePlan -Algorithm SHA256).Hash
$result = & $pwsh -NoProfile -File $script -Mode Apply -PlanPath $outsidePlan -ReviewedPlanSha256 $outsideHash -ReportDirectory (Join-Path $fixture 'outside-apply') -BackupDirectory (Join-Path $fixture 'outside-backup') 2>&1
if ($LASTEXITCODE -eq 0 -or (Test-Path -LiteralPath (Join-Path $fixture 'outside-backup'))) { throw 'Production entrypoint accepted an outside source.' }
$result = & $pwsh -NoProfile -File $script -Mode Apply -PlanPath $plan -ReviewedPlanSha256 $hash -ReportDirectory (Join-Path $fixture 'empty-apply') -BackupDirectory (Join-Path $fixture 'empty-backup') 2>&1
if ($LASTEXITCODE -ne 0) { throw ($result | Out-String) }
$summary = Get-Content -LiteralPath (Join-Path $fixture 'empty-apply\summary.json') -Raw | ConvertFrom-Json
if ($summary.SourceAbsentFiles -ne 0 -or $summary.SourceAbsentLogicalBytes -ne 0) { throw 'Empty plan reported removed data.' }
Write-Output 'PASS: syntax, path boundaries, junction rejection, plan hash refusal, production source rejection, empty-plan apply.'
Write-Output "Test artifacts retained at $fixture"
