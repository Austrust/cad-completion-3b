param([int]$Port=18031)
$ErrorActionPreference='Stop'
$pythonExe=Join-Path $PSScriptRoot '.venv-npu/Scripts/python.exe'
$script=Join-Path $PSScriptRoot 'openvino-server.py'
if(-not (Test-Path -LiteralPath $pythonExe)){throw 'Run setup-npu.ps1 first'}
if(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue){throw "Port $Port is already in use"}
& $pythonExe $script --device NPU --check-device
if($LASTEXITCODE -ne 0){throw 'NPU unavailable; no fallback selected'}
$logs=Join-Path $PSScriptRoot 'logs';New-Item -ItemType Directory -Force -Path $logs | Out-Null
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$proc=Start-Process -FilePath $pythonExe -ArgumentList @('-u',('"{0}"' -f $script),'--device','NPU','--port',"$Port") -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logs/$stamp.npu.stdout.log" -RedirectStandardError "$logs/$stamp.npu.stderr.log"
Write-Output "NPU compilation started, PID=$($proc.Id). Logs: $logs/$stamp.npu.stderr.log"
Write-Output "Wait for ready in stdout, or check: Invoke-RestMethod http://127.0.0.1:$Port/health"
Write-Output "Stop this instance with: Stop-Process -Id $($proc.Id)"
