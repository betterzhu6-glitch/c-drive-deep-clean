[CmdletBinding()]
param(
    [ValidateSet('Audit','Apply')][string]$Mode = 'Audit',
    [ValidateSet('Temp','CrashDumps','D3DSCache','NpmCache','PipCache')]
    [string[]]$Category = @('Temp','CrashDumps','D3DSCache','NpmCache','PipCache'),
    [ValidateRange(7,3650)][int]$MinAgeDays = 7,
    [Parameter(Mandatory)][string]$ReportDirectory,
    [string]$PlanPath, [string]$ReviewedPlanSha256, [string]$BackupDirectory
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Assert-PlainPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $cursor = $full
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Reparse point in path: $cursor"
            }
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
    return $full
}
function Assert-Under([string]$Path, [string]$Root) {
    $full = Assert-PlainPath $Path
    $base = (Assert-PlainPath $Root).TrimEnd('\') + '\'
    if (-not $full.StartsWith($base, [StringComparison]::OrdinalIgnoreCase)) { throw "Outside allowed root: $full" }
    return $full
}
$local = Assert-PlainPath ([Environment]::GetFolderPath('LocalApplicationData'))
if ([IO.Path]::GetPathRoot($local) -ine 'C:\') { throw 'Only current-user caches on C: are supported.' }
$roots = @{
    Temp = Join-Path $local 'Temp'
    CrashDumps = Join-Path $local 'CrashDumps'
    D3DSCache = Join-Path $local 'D3DSCache'
    NpmCache = Join-Path $local 'npm-cache\_cacache'
    PipCache = Join-Path $local 'pip\cache'
}
$report = Assert-PlainPath $ReportDirectory
if ([IO.Path]::GetPathRoot($report) -ieq 'C:\') { throw 'Reports must be on another drive.' }
New-Item -ItemType Directory -Path $report -Force | Out-Null
$cutoff = [DateTime]::UtcNow.AddDays(-$MinAgeDays)
if ($Mode -eq 'Audit') {
    $candidates = [Collections.Generic.List[object]]::new()
    $issues = [Collections.Generic.List[object]]::new()
    foreach ($name in $Category) {
        $root = $roots[$name]
        if (-not (Test-Path -LiteralPath $root)) { continue }
        try { $null = Assert-PlainPath $root } catch {
            $issues.Add(@{Path=$root;Reason=$_.Exception.Message}); continue
        }
        $pending = [Collections.Generic.Stack[string]]::new()
        $pending.Push($root)
        while ($pending.Count) {
            $dir = $pending.Pop()
            try {
                $null = Assert-PlainPath $dir
                foreach ($item in Get-ChildItem -LiteralPath $dir -Force) {
                    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                        $issues.Add(@{Path=$item.FullName;Reason='Reparse point skipped'}); continue
                    }
                    if ($item.PSIsContainer) { $pending.Push($item.FullName); continue }
                    if ($item.Extension -in @('.lock','.lck') -or
                        ($name -eq 'Temp' -and $item.Extension -in @('.sys','.dll','.exe','.msi','.msp','.cab','.ps1','.bat','.cmd','.vbs','.node'))) { continue }
                    if ($item.LastWriteTimeUtc -ge $cutoff -or $item.CreationTimeUtc -ge $cutoff) { continue }
                    $candidates.Add([pscustomobject]@{Category=$name;Path=$item.FullName;Length=$item.Length
                        LastWriteUtc=$item.LastWriteTimeUtc.ToString('o');CreationUtc=$item.CreationTimeUtc.ToString('o')})
                }
            } catch { $issues.Add(@{Path=$dir;Reason=$_.Exception.Message}) }
        }
    }
    $plan = Join-Path $report 'plan.csv'
    if (Test-Path -LiteralPath $plan) { throw 'An existing plan will not be overwritten; use a new report directory.' }
    if ($candidates.Count) { $candidates | Export-Csv -LiteralPath $plan -NoTypeInformation -Encoding utf8 }
    else { '"Category","Path","Length","LastWriteUtc","CreationUtc"' | Set-Content -LiteralPath $plan -Encoding utf8 }
    ConvertTo-Json -InputObject @($issues.ToArray()) -Depth 4 | Set-Content -LiteralPath (Join-Path $report 'audit-issues.json') -Encoding utf8
    $candidates | Group-Object Category | ForEach-Object {
        [pscustomobject]@{Category=$_.Name;Files=$_.Count;GiB=[math]::Round(($_.Group | Measure-Object Length -Sum).Sum/1GB,3)}
    } | Format-Table | Out-String | Write-Output
    Write-Output "Plan: $plan"
    Write-Output "SHA256: $((Get-FileHash -LiteralPath $plan -Algorithm SHA256).Hash)"
    Write-Output "Audit issues: $($issues.Count). No source files changed."
    exit 0
}
if (-not $PlanPath -or -not $BackupDirectory -or -not $ReviewedPlanSha256) { throw 'Apply requires PlanPath, ReviewedPlanSha256 and BackupDirectory.' }
$plan = Assert-PlainPath $PlanPath
if ((Get-FileHash -LiteralPath $plan -Algorithm SHA256).Hash -ine $ReviewedPlanSha256) { throw 'Reviewed plan hash mismatch.' }
$backup = Assert-PlainPath $BackupDirectory
if ([IO.Path]::GetPathRoot($backup) -ieq 'C:\') { throw 'Backup must be on another drive.' }
if (Test-Path -LiteralPath $backup) { throw 'BackupDirectory must be new.' }
$rows = @(Import-Csv -LiteralPath $plan)
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$total = [long]0
foreach ($row in $rows) {
    if ($row.Category -notin $Category -or -not $roots.ContainsKey($row.Category)) { throw 'Unknown or unselected category.' }
    $source = Assert-Under $row.Path $roots[$row.Category]
    if (-not $seen.Add($source)) { throw "Duplicate source: $source" }
    if ([long]$row.Length -lt 0) { throw 'Invalid length.' }
    $total += [long]$row.Length
    if ([DateTime]::Parse($row.LastWriteUtc).ToUniversalTime() -ge $cutoff -or
        [DateTime]::Parse($row.CreationUtc).ToUniversalTime() -ge $cutoff) { throw 'Recent file in plan.' }
}
$drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($backup))
if ($drive.AvailableFreeSpace -lt ($total + 1GB)) { throw 'Insufficient backup space plus 1 GiB reserve.' }
$journal = Join-Path $report 'operations.jsonl'
if (Test-Path -LiteralPath $journal) { throw 'Use a new apply report directory.' }
New-Item -ItemType Directory -Path $backup | Out-Null
function Write-Journal($Record) { $Record | ConvertTo-Json -Compress -Depth 5 | Add-Content -LiteralPath $journal -Encoding utf8 }
$before = [IO.DriveInfo]::new('C:\').AvailableFreeSpace
$removedBytes = [long]0
$removedCount = 0
$failedCount = 0
foreach ($row in $rows) {
    $destination = $null
    try {
        $source = Assert-Under $row.Path $roots[$row.Category]
        $item = Get-Item -LiteralPath $source -Force
        if ($item.Extension -in @('.lock','.lck') -or
            ($row.Category -eq 'Temp' -and $item.Extension -in @('.sys','.dll','.exe','.msi','.msp','.cab','.ps1','.bat','.cmd','.vbs','.node'))) { throw 'Excluded executable, installer or lock file.' }
        if ($item.PSIsContainer -or $item.Length -ne [long]$row.Length -or
            $item.LastWriteTimeUtc.ToString('o') -ne $row.LastWriteUtc -or
            $item.CreationTimeUtc.ToString('o') -ne $row.CreationUtc) { throw 'Source changed since audit.' }
        $relative = $source.Substring($roots[$row.Category].TrimEnd('\').Length).TrimStart('\')
        $destination = Assert-Under (Join-Path (Join-Path $backup $row.Category) $relative) $backup
        $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($destination)) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination
        if ((Get-Item -LiteralPath $destination -Force).Length -ne $item.Length -or
            (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $sourceHash) { throw 'Backup verification failed; source retained.' }
        $null = Assert-Under $source $roots[$row.Category]
        $current = Get-Item -LiteralPath $source -Force
        if ($current.Length -ne $item.Length -or $current.LastWriteTimeUtc -ne $item.LastWriteTimeUtc -or
            $current.CreationTimeUtc -ne $item.CreationTimeUtc -or
            (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $sourceHash) { throw 'Source changed during backup.' }
        Write-Journal @{Status='BackupVerified';Source=$source;Backup=$destination;Bytes=$item.Length;SHA256=$sourceHash}
        Remove-Item -LiteralPath $source -Force -ErrorAction Stop
        if (Test-Path -LiteralPath $source) { throw 'Source still exists after removal.' }
        $removedCount++
        $removedBytes += $item.Length
        Write-Journal @{Status='SourceAbsent';Source=$source;Backup=$destination;Bytes=$item.Length;SHA256=$sourceHash}
    } catch {
        $failedCount++
        Write-Journal @{Status='SkippedOrFailed';Source=$row.Path;Backup=$destination;Reason=$_.Exception.Message}
    }
}
$after = [IO.DriveInfo]::new('C:\').AvailableFreeSpace
$summary = [pscustomobject]@{SourceAbsentFiles=$removedCount;SourceAbsentLogicalBytes=$removedBytes;SkippedOrFailed=$failedCount
    FreeBeforeBytes=$before;FreeAfterBytes=$after;ObservedFreeDeltaBytes=($after-$before);BackupDirectory=$backup
    PlanSha256=$ReviewedPlanSha256;Note='Disk delta includes concurrent activity; logical bytes are not guaranteed reclaimed bytes.'}
$summary | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $report 'summary.json') -Encoding utf8
$summary | Format-List | Out-String | Write-Output
if ($failedCount) { exit 2 }
