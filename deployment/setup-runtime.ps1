param([ValidateSet('vulkan','cuda')][string]$Backend='vulkan')
$ErrorActionPreference='Stop'
$manifest=Get-Content (Join-Path $PSScriptRoot 'runtime-assets.json') -Raw | ConvertFrom-Json
$destination=Join-Path $PSScriptRoot "runtimes/$Backend"
if(Test-Path -LiteralPath $destination){throw 'Runtime directory already exists; preserve it and inspect its version first'}
$downloads=Join-Path $PSScriptRoot 'downloads'
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
foreach($asset in $manifest.$Backend){
 $path=Join-Path $downloads $asset.name
 if(-not (Test-Path -LiteralPath $path)){Invoke-WebRequest -Uri $asset.url -OutFile $path -UseBasicParsing}
 if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower() -ne $asset.sha256){throw "SHA256 mismatch: $path"}
}
foreach($asset in $manifest.$Backend){Expand-Archive -LiteralPath (Join-Path $downloads $asset.name) -DestinationPath $destination -Force}
if(-not (Test-Path (Join-Path $destination 'llama-server.exe'))){throw 'Unexpected official archive layout'}
Write-Output "Installed official llama.cpp b11669 $Backend runtime."
