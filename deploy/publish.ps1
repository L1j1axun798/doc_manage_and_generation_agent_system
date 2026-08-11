[CmdletBinding()]
param(
    [ValidateSet('Publish', 'Rollback')]
    [string]$Action = 'Publish',

    [switch]$AllowDirty,
    [switch]$AllowMigrations,
    [switch]$SkipLocalChecks,
    [switch]$DryRun,
    [string]$Release,
    [string]$ConfigPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $PSScriptRoot 'publish.config.local.json'
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

function Get-RequiredConfigValue {
    param(
        [Parameter(Mandatory = $true)]$Config,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $property = $Config.PSObject.Properties[$Name]
    if ($null -eq $property -or [string]::IsNullOrWhiteSpace([string]$property.Value)) {
        throw "Missing required configuration value: $Name"
    }
    return $property.Value
}

function Assert-CommandExists {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command is not available: $Name"
    }
}

function Assert-PackagePathSafe {
    param([Parameter(Mandatory = $true)][string]$Path)

    $normalized = $Path.Replace('\', '/')
    if ($normalized.StartsWith('/') -or $normalized -match '(^|/)\.\.(/|$)') {
        throw "Unsafe package path: $Path"
    }

    $leaf = [IO.Path]::GetFileName($normalized)
    $isEnvironmentSecret = $leaf -eq '.env' -or (
        $leaf.StartsWith('.env.') -and -not $leaf.EndsWith('.example')
    )
    if ($isEnvironmentSecret -or $leaf -eq 'publish.config.local.json') {
        throw "Refusing to package a local configuration or secret file: $Path"
    }

    if ([IO.Path]::GetExtension($leaf) -match '^\.(pem|key|p12|pfx)$') {
        throw "Refusing to package a private-key file: $Path"
    }
}

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$serverScript = Join-Path $PSScriptRoot 'release-server.sh'
$configFullPath = [IO.Path]::GetFullPath($ConfigPath)

if (-not (Test-Path -LiteralPath $configFullPath -PathType Leaf)) {
    throw "Deployment config not found: $configFullPath. Copy publish.config.example.json first."
}
if (-not (Test-Path -LiteralPath $serverScript -PathType Leaf)) {
    throw "Server release script not found: $serverScript"
}

$configText = [IO.File]::ReadAllText($configFullPath, [Text.Encoding]::UTF8)
$config = $configText | ConvertFrom-Json
$serverHost = [string](Get-RequiredConfigValue $config 'Host')
$serverPort = [int](Get-RequiredConfigValue $config 'Port')
$serverUser = [string](Get-RequiredConfigValue $config 'User')
$identityFile = [IO.Path]::GetFullPath([string](Get-RequiredConfigValue $config 'IdentityFile'))
$domain = [string](Get-RequiredConfigValue $config 'Domain')
$python = [IO.Path]::GetFullPath([string](Get-RequiredConfigValue $config 'Python'))
$frontendEnvSetting = [string](Get-RequiredConfigValue $config 'FrontendEnvFile')
$frontendEnvFile = if ([IO.Path]::IsPathRooted($frontendEnvSetting)) {
    [IO.Path]::GetFullPath($frontendEnvSetting)
} else {
    [IO.Path]::GetFullPath((Join-Path $repoRoot $frontendEnvSetting))
}
$keepReleases = if ($null -ne $config.PSObject.Properties['KeepReleases']) {
    [int]$config.KeepReleases
} else {
    5
}
$documentAgentEnabled = if ($null -ne $config.PSObject.Properties['DocumentAgentEnabled']) {
    [bool]$config.DocumentAgentEnabled
} else {
    $true
}

if ($serverHost -notmatch '^[A-Za-z0-9.-]+$') { throw 'Host contains unsupported characters' }
if ($serverPort -lt 1 -or $serverPort -gt 65535) { throw 'Port is outside 1-65535' }
if ($serverUser -notmatch '^[A-Za-z_][A-Za-z0-9_-]*$') { throw 'User contains unsupported characters' }
if ($domain -notmatch '^[A-Za-z0-9.-]+$') { throw 'Domain contains unsupported characters' }
if ($keepReleases -lt 2 -or $keepReleases -gt 20) { throw 'KeepReleases must be between 2 and 20' }
if (-not (Test-Path -LiteralPath $identityFile -PathType Leaf)) { throw "SSH key not found: $identityFile" }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python not found: $python" }
if (-not (Test-Path -LiteralPath $frontendEnvFile -PathType Leaf)) { throw "Frontend environment file not found: $frontendEnvFile" }

$frontendEnvLines = [IO.File]::ReadAllLines($frontendEnvFile, [Text.Encoding]::UTF8)
foreach ($frontendEnvLine in $frontendEnvLines) {
    $trimmedEnvLine = $frontendEnvLine.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmedEnvLine) -or $trimmedEnvLine.StartsWith('#')) { continue }
    if ($frontendEnvLine -notmatch '^VITE_[A-Z0-9_]+=') {
        throw "Frontend environment file contains a non-VITE variable: $frontendEnvLine"
    }
}

Assert-CommandExists 'git'
Assert-CommandExists 'ssh'
Assert-CommandExists 'scp'

$sshOptions = @(
    '-i', $identityFile,
    '-p', [string]$serverPort,
    '-o', 'BatchMode=yes',
    '-o', 'IdentitiesOnly=yes',
    '-o', 'ConnectTimeout=10'
)
$scpOptions = @(
    '-i', $identityFile,
    '-P', [string]$serverPort,
    '-o', 'BatchMode=yes',
    '-o', 'IdentitiesOnly=yes',
    '-o', 'ConnectTimeout=10'
)
$sshTarget = "${serverUser}@${serverHost}"
$remoteServerScript = '/tmp/wind-doc-release-server.sh'

if ($Action -eq 'Rollback') {
    if ($DryRun) {
        $rollbackDescription = if ([string]::IsNullOrWhiteSpace($Release)) {
            'the recorded previous release'
        } else {
            $Release
        }
        Write-Host "DRY RUN: would roll back $sshTarget to $rollbackDescription"
        exit 0
    }

    Invoke-NativeCommand 'scp' ($scpOptions + @($serverScript, "${sshTarget}:${remoteServerScript}")) $repoRoot
    $rollbackArguments = $sshOptions + @(
        $sshTarget,
        'bash', $remoteServerScript, 'rollback',
        '--domain', $domain,
        '--keep', [string]$keepReleases,
        '--document-agent-enabled', $documentAgentEnabled.ToString().ToLowerInvariant()
    )
    if (-not [string]::IsNullOrWhiteSpace($Release)) {
        if ($Release -notmatch '^[A-Za-z0-9._-]+$') { throw 'Release contains unsupported characters' }
        $rollbackArguments += @('--target', $Release)
    }

    try {
        Invoke-NativeCommand 'ssh' $rollbackArguments $repoRoot
    }
    finally {
        & ssh @sshOptions $sshTarget 'rm' '-f' '--' $remoteServerScript 2>$null
    }
    Write-Host 'Rollback completed and health checks passed.'
    exit 0
}

$gitStatus = @(& git -C $repoRoot status --porcelain=v1 --untracked-files=normal)
if ($LASTEXITCODE -ne 0) { throw 'Unable to read Git status' }
$isDirty = $gitStatus.Count -gt 0
if ($isDirty -and -not $AllowDirty) {
    Write-Host 'The worktree has uncommitted changes:'
    $gitStatus | ForEach-Object { Write-Host "  $_" }
    throw 'Commit the release first, or explicitly use -AllowDirty for an emergency snapshot.'
}

$sourceCommit = ((& git -C $repoRoot rev-parse HEAD) | Select-Object -First 1).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceCommit -notmatch '^[0-9a-f]{40}$') {
    throw 'Unable to determine the source commit'
}
$shortCommit = $sourceCommit.Substring(0, 12)
$releaseId = "$(Get-Date -Format 'yyyyMMdd-HHmmss')-${shortCommit}"
if ($isDirty) { $releaseId += '-dirty' }

if (-not $SkipLocalChecks) {
    Assert-CommandExists 'node'
    Assert-CommandExists 'npm.cmd'
    Write-Host 'Running backend checks...'
    Invoke-NativeCommand $python @('manage.py', 'check') (Join-Path $repoRoot 'backend')
    Invoke-NativeCommand $python @('manage.py', 'makemigrations', '--check', '--dry-run') (Join-Path $repoRoot 'backend')
    Invoke-NativeCommand $python @('-m', 'pytest') (Join-Path $repoRoot 'backend')

    Write-Host 'Running frontend checks...'
    $frontedRoot = Join-Path $repoRoot 'fronted'
    Invoke-NativeCommand 'npm.cmd' @('ci') $frontedRoot
    Invoke-NativeCommand 'npm.cmd' @('run', 'lint') $frontedRoot
    Invoke-NativeCommand 'npm.cmd' @('run', 'type-check') $frontedRoot
    Invoke-NativeCommand 'npm.cmd' @('run', 'test:unit') $frontedRoot
    Invoke-NativeCommand 'npm.cmd' @('run', 'build') $frontedRoot
    Invoke-NativeCommand 'npm.cmd' @('audit', '--omit=dev') $frontedRoot
} else {
    Write-Warning 'Local checks were explicitly skipped.'
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$tempDirectory = Join-Path $tempBase ("wind-doc-release-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempDirectory | Out-Null
$resolvedTempDirectory = [IO.Path]::GetFullPath($tempDirectory)
if (-not $resolvedTempDirectory.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe temporary directory: $resolvedTempDirectory"
}

$archivePath = Join-Path $resolvedTempDirectory ("${releaseId}.tar.gz")
$manifestPath = Join-Path $resolvedTempDirectory 'manifest.txt'
$remoteArchive = "/tmp/${releaseId}.tar.gz"
$remoteFrontendEnv = "/tmp/${releaseId}.fronted.env"
$remoteFilesUploaded = $false

try {
    $packagePaths = @(& git -C $repoRoot -c core.quotepath=false ls-files --cached --others --exclude-standard -- backend fronted deploy requirements.txt)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to build the package manifest' }
    $packagePaths = @($packagePaths | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
    if ($packagePaths.Count -eq 0) { throw 'The package manifest is empty' }
    foreach ($packagePath in $packagePaths) { Assert-PackagePathSafe $packagePath }

    [IO.File]::WriteAllLines($manifestPath, $packagePaths, (New-Object Text.UTF8Encoding($false)))
    Invoke-NativeCommand $python @(
        (Join-Path $PSScriptRoot 'create_release_archive.py'),
        '--root', $repoRoot,
        '--manifest', $manifestPath,
        '--output', $archivePath
    ) $repoRoot
    $archiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
    $archiveSize = (Get-Item -LiteralPath $archivePath).Length
    Write-Host "Prepared release $releaseId ($archiveSize bytes, sha256=$archiveHash)"

    if ($DryRun) {
        Write-Host "DRY RUN: package contains $($packagePaths.Count) files; no server changes were made."
        exit 0
    }

    Invoke-NativeCommand 'scp' ($scpOptions + @($archivePath, "${sshTarget}:${remoteArchive}")) $repoRoot
    $remoteFilesUploaded = $true
    Invoke-NativeCommand 'scp' ($scpOptions + @($frontendEnvFile, "${sshTarget}:${remoteFrontendEnv}")) $repoRoot
    Invoke-NativeCommand 'scp' ($scpOptions + @($serverScript, "${sshTarget}:${remoteServerScript}")) $repoRoot

    $deployArguments = $sshOptions + @(
        $sshTarget,
        'bash', $remoteServerScript, 'deploy',
        '--archive', $remoteArchive,
        '--frontend-env', $remoteFrontendEnv,
        '--release', $releaseId,
        '--domain', $domain,
        '--keep', [string]$keepReleases,
        '--allow-migrations', $AllowMigrations.ToString().ToLowerInvariant(),
        '--document-agent-enabled', $documentAgentEnabled.ToString().ToLowerInvariant(),
        '--source-commit', $sourceCommit,
        '--source-dirty', $isDirty.ToString().ToLowerInvariant()
    )
    Invoke-NativeCommand 'ssh' $deployArguments $repoRoot
    Write-Host "Deployment completed: https://${domain}/"
    Write-Host 'Rollback command: .\deploy\publish.ps1 -Action Rollback'
}
finally {
    if ($remoteFilesUploaded) {
        & ssh @sshOptions $sshTarget 'rm' '-f' '--' $remoteServerScript $remoteArchive $remoteFrontendEnv 2>$null
    }
    if (Test-Path -LiteralPath $resolvedTempDirectory) {
        Remove-Item -LiteralPath $resolvedTempDirectory -Recurse -Force
    }
}
