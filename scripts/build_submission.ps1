param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+$')]
    [string]$GroupNumber,
    [string]$OutputDirectory = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$destinationRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
$archivePath = Join-Path $destinationRoot ("Src_G{0}.zip" -f $GroupNumber)
if (Test-Path -LiteralPath $archivePath) {
    throw "Refusing to overwrite existing archive: $archivePath"
}

$stageName = "yelptext-submission-{0}" -f ([guid]::NewGuid().ToString('N'))
$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) $stageName
$expectedPrefix = [System.IO.Path]::GetFullPath(
    (Join-Path ([System.IO.Path]::GetTempPath()) 'yelptext-submission-')
)
$resolvedStage = [System.IO.Path]::GetFullPath($stageRoot)
if (-not $resolvedStage.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unexpected staging path: $resolvedStage"
}

$files = @('.python-version', 'pyproject.toml', 'requirements.txt', 'README.md', 'Readme.txt')
$directories = @('configs', 'docs', 'notebooks', 'scripts', 'src', 'tests')

try {
    New-Item -ItemType Directory -Path $resolvedStage | Out-Null
    foreach ($relative in $files) {
        $source = Join-Path $projectRoot $relative
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "Required submission file is missing: $relative"
        }
        Copy-Item -LiteralPath $source -Destination $resolvedStage
    }
    foreach ($relative in $directories) {
        $source = Join-Path $projectRoot $relative
        if (-not (Test-Path -LiteralPath $source -PathType Container)) {
            throw "Required submission directory is missing: $relative"
        }
        Copy-Item -LiteralPath $source -Destination $resolvedStage -Recurse
    }

    Get-ChildItem -LiteralPath $resolvedStage -Recurse -Force -Directory |
        Where-Object { $_.Name -in @('__pycache__', '.pytest_cache', '.ipynb_checkpoints') } |
        Sort-Object { $_.FullName.Length } -Descending |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $resolvedStage -Recurse -Force -File |
        Where-Object { $_.Extension -in @('.pyc', '.pyo') } |
        Remove-Item -Force

    $archiveItems = Get-ChildItem -LiteralPath $resolvedStage -Force
    Compress-Archive -LiteralPath $archiveItems.FullName -DestinationPath $archivePath
    Write-Output "Created $archivePath"
}
finally {
    if (Test-Path -LiteralPath $resolvedStage) {
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
}
