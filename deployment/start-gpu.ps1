param(
 [ValidateSet('vulkan','cuda')][string]$Backend='vulkan',
 [int]$Port=18031,
 [string]$Device=''
)
$ErrorActionPreference='Stop'
$exe=Join-Path $PSScriptRoot "runtimes/$Backend/llama-server.exe"
$model=Join-Path $PSScriptRoot 'gguf/CAD-completion-3B-v1-Q4_K_M.gguf'
if(-not (Test-Path -LiteralPath $exe)){throw "Missing $Backend runtime: use setup-runtime.ps1 first"}
if(-not (Test-Path -LiteralPath $model)){throw "Missing model: $model"}
if(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue){throw "Port $Port is already in use"}
$inventory=(& $exe --list-devices 2>&1 | Out-String)
Write-Output $inventory
if(-not $Device){$Device=if($Backend -eq 'cuda'){'CUDA0'}else{'Vulkan0'}}
if($Device -notmatch '^(CUDA|Vulkan)\d+$' -or $inventory -notmatch ([regex]::Escape($Device)+':')){throw "Requested GPU $Device not available; no CPU fallback"}
$logs=Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$argsList=@('-m',('"{0}"' -f $model),'--host','127.0.0.1','--port',"$Port",'--device',$Device,'-ngl','99','-c','2048','--parallel','1','-b','512','-ub','512','-t','8','--flash-attn','off','--no-context-shift','--no-warmup')
$proc=Start-Process -FilePath $exe -ArgumentList $argsList -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logs/$stamp.stdout.log" -RedirectStandardError "$logs/$stamp.stderr.log"
try {
 $ready=$false
 for($i=0;$i -lt 600;$i++){
  $proc.Refresh();if($proc.HasExited){throw "Server exited; inspect $logs/$stamp.stderr.log"}
  try {if((Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 2).status -eq 'ok'){$ready=$true;break}}catch{}
  Start-Sleep -Milliseconds 200
 }
 if(-not $ready){throw 'Server startup timed out'}
 Write-Output "CAD v1 Q4 ready: http://127.0.0.1:$Port ; GPU=$Device ; PID=$($proc.Id)"
 Write-Output "Stop this instance with: Stop-Process -Id $($proc.Id)"
}catch{
 $proc.Refresh();if(-not $proc.HasExited){Stop-Process -Id $proc.Id}
 throw
}
