param([int]$Port=18030,[switch]$NoBrowser)
$ErrorActionPreference='Stop'
$python=(Get-Command python -ErrorAction Stop).Source
$launchArgs=@(('"'+(Join-Path $PSScriptRoot 'app.py')+'"'),'--port',"$Port",'--no-browser')
$process=Start-Process -FilePath $python -ArgumentList $launchArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 1
$process.Refresh()
if($process.HasExited){throw '加载器未启动；请运行 python app.py 查看错误（检查端口是否被占用）。'}
Write-Output "CAD model loader: http://127.0.0.1:$Port (PID $($process.Id))"
if(-not $NoBrowser){Start-Process "http://127.0.0.1:$Port"}
