param(
    [Parameter(Mandatory=$true)][string]$WorkRoot,
    [Parameter(Mandatory=$true)][string]$Python,
    [string]$Dotnet = 'dotnet',
    [string]$Git = 'git'
)
$ErrorActionPreference = 'Stop'
$baseSha = 'a6fc7a3fd4d48ee057706daef09539caccfaf9bd'
$workspace = [IO.Path]::GetFullPath($WorkRoot)
if (Test-Path -LiteralPath $workspace) { throw 'Choose a new, empty work path.' }
New-Item -ItemType Directory -Path $workspace | Out-Null
foreach ($name in @('work','build','qa','logs','tmp','cache')) { New-Item -ItemType Directory -Path (Join-Path $workspace $name) | Out-Null }
$env:TEMP = Join-Path $workspace 'tmp'
$env:TMP = $env:TEMP
$env:DOTNET_CLI_HOME = Join-Path $workspace 'cache/dotnet'
$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:GRAMM_TEST_DOTNET = (Get-Command $Dotnet -ErrorAction Stop).Source
$env:PATH = (Split-Path $env:GRAMM_TEST_DOTNET) + ';' + $env:PATH
& $Python --version
if ($LASTEXITCODE -ne 0) { throw 'Python executable failed.' }
& $Dotnet --version
if ($LASTEXITCODE -ne 0) { throw '.NET SDK failed.' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'tests') -Destination $workspace -Recurse
$baseline = Join-Path $workspace 'work/upstream'
$candidate = Join-Path $workspace 'work/candidate'
& $Git clone 'https://github.com/GralDispersionModel/GRAMM.git' $baseline
if ($LASTEXITCODE -ne 0) { throw 'Clone failed.' }
& $Git -C $baseline checkout --detach $baseSha
if ($LASTEXITCODE -ne 0) { throw 'Pinned upstream checkout failed.' }
& $Git -C $baseline worktree add --detach $candidate $baseSha
if ($LASTEXITCODE -ne 0) { throw 'Candidate worktree creation failed.' }
$patch = Join-Path $PSScriptRoot 'patches/water-stability-diagnostic.patch'
& $Git -C $candidate apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch preflight failed.' }
& $Git -C $candidate apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed.' }
foreach ($kind in @('baseline','candidate')) {
    $src = if ($kind -eq 'baseline') { $baseline } else { $candidate }
    & $Dotnet build (Join-Path $src 'src/GRAMM.csproj') -c Release -warnaserror --nologo -p:NuGetAudit=false -o (Join-Path $workspace "build/$kind")
    if ($LASTEXITCODE -ne 0) { throw "Engine build failed: $kind" }
}
$component = Join-Path $workspace 'tests/component/ComponentCheck.csproj'
& $Dotnet build $component -c Release -warnaserror --nologo -p:NuGetAudit=false
if ($LASTEXITCODE -ne 0) { throw 'Component harness build failed.' }
& $Dotnet (Join-Path $workspace 'tests/component/bin/Release/net10.0/ComponentCheck.dll') (Join-Path $workspace 'build/baseline/GRAMM.dll') (Join-Path $workspace 'build/candidate/GRAMM.dll') (Join-Path $workspace 'qa/component') (Join-Path $candidate 'src/PRANDTL.cs')
if ($LASTEXITCODE -ne 0) { throw 'Component verification failed.' }
& $Python -X utf8 -B (Join-Path $workspace 'tests/native/run_matrix.py') --root $workspace
$nativeExit = $LASTEXITCODE
if ($nativeExit -eq 2) { Write-Warning 'review_required: inspect saved wind-output differences in qa/native; classification and non-wind checks passed.' }
elseif ($nativeExit -ne 0) { throw 'Native verification failed.' }
& (Join-Path $workspace 'tests/temporal/run_temporal.ps1') -BaselineDll (Join-Path $workspace 'build/baseline/GRAMM.dll') -CandidateDll (Join-Path $workspace 'build/candidate/GRAMM.dll') -OutputDirectory (Join-Path $workspace 'qa/temporal') -BaselinePrandtlSource (Join-Path $baseline 'src/PRANDTL.cs') -CandidatePrandtlSource (Join-Path $candidate 'src/PRANDTL.cs') -InitializerSource (Join-Path $workspace 'tests/component/Program.cs') -DotnetExe $Dotnet
$gral = Join-Path $workspace 'work/gral'
& $Git clone 'https://github.com/GralDispersionModel/GRAL.git' $gral
if ($LASTEXITCODE -ne 0) { throw 'GRAL clone failed.' }
& $Git -C $gral checkout --detach 'cd540abf4eda380e5669a891911323351d789e86'
if ($LASTEXITCODE -ne 0) { throw 'Pinned GRAL checkout failed.' }
& $Dotnet build (Join-Path $gral 'src/GRAL.csproj') -c Release -warnaserror --nologo -p:NuGetAudit=false -o (Join-Path $workspace 'build/gral')
if ($LASTEXITCODE -ne 0) { throw 'GRAL build failed.' }
$native = Join-Path $workspace 'runs/native'
& $Python -X utf8 -B (Join-Path $workspace 'tests/coupling/run_coupling.py') --job-root $workspace --native-root $native --gral-dll (Join-Path $workspace 'build/gral/GRAL.dll')
if ($LASTEXITCODE -ne 0) { throw 'GRAL coupling runs failed.' }
& $Python -X utf8 -B (Join-Path $workspace 'tests/coupling/diagnostic.py') --job-root $workspace --gral-source (Join-Path $gral 'src')
if ($LASTEXITCODE -ne 0) { throw 'GRAL import diagnostics failed.' }
& $Python -X utf8 -B (Join-Path $workspace 'tests/coupling/verify.py') --job-root $workspace --native-root $native
if ($LASTEXITCODE -ne 0) { throw 'GRAL coupling verification failed.' }
& $Python -X utf8 -B (Join-Path $workspace 'tests/coupling/final_audit.py') --job-root $workspace
if ($LASTEXITCODE -ne 0) { throw 'GRAL coupling integrity check failed.' }
if ($nativeExit -eq 2) { Write-Output "[REVIEW_REQUIRED] $workspace"; exit 2 }
Write-Output "[PASS] $workspace"
