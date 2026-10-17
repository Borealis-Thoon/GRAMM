param(
    [Parameter(Mandatory=$true)][string]$BaselineDll,
    [Parameter(Mandatory=$true)][string]$CandidateDll,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$BaselinePrandtlSource,
    [Parameter(Mandatory=$true)][string]$CandidatePrandtlSource,
    [Parameter(Mandatory=$true)][string]$InitializerSource,
    [string]$DotnetExe = 'C:\Program Files\dotnet\dotnet.exe'
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
& $DotnetExe build (Join-Path $PSScriptRoot 'TemporalCheck.csproj') -c Release --nologo -warnaserror 2>&1 | Tee-Object -FilePath (Join-Path $OutputDirectory 'strict_build.log')
if ($LASTEXITCODE -ne 0) { throw 'Temporal harness build failed.' }
& $DotnetExe (Join-Path $PSScriptRoot 'bin\Release\net10.0\TemporalCheck.dll') $BaselineDll $CandidateDll $OutputDirectory $BaselinePrandtlSource $CandidatePrandtlSource $InitializerSource 2>&1 | Tee-Object -FilePath (Join-Path $OutputDirectory 'execution.log')
if ($LASTEXITCODE -ne 0) { throw 'Temporal checks failed.' }
