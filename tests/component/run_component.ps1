param(
    [Parameter(Mandatory=$true)][string]$BaselineDll,
    [Parameter(Mandatory=$true)][string]$CandidateDll,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$CandidatePrandtlSource = ''
)
$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot 'ComponentCheck.csproj'
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
& dotnet build $project -c Release --nologo -warnaserror 2>&1 | Tee-Object -FilePath (Join-Path $OutputDirectory 'strict_build.log')
if ($LASTEXITCODE -ne 0) { throw 'Component harness build failed.' }
$harness = Join-Path $PSScriptRoot 'bin\Release\net10.0\ComponentCheck.dll'
$arguments = @($harness, $BaselineDll, $CandidateDll, $OutputDirectory)
if ($CandidatePrandtlSource) { $arguments += $CandidatePrandtlSource }
& dotnet @arguments 2>&1 | Tee-Object -FilePath (Join-Path $OutputDirectory 'execution.log')
if ($LASTEXITCODE -ne 0) { throw 'Component checks failed.' }
